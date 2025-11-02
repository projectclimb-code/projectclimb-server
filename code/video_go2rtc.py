import cv2
import argparse
import asyncio
import websockets
import json
import base64
import numpy as np
import requests
import threading
import time
from datetime import datetime
import subprocess
import signal
import sys
import os

# Setup argument parser
parser = argparse.ArgumentParser(description="Capture video and stream it via go2rtc.")
parser.add_argument("--source", default="0", help="Video source (camera index or file path). Default is 0 (webcam).")
parser.add_argument("--ws_uri", default="ws://localhost:8000/ws/pose/", help="WebSocket URI of the Django server.")
parser.add_argument("--go2rtc_uri", default="http://localhost:1984", help="go2rtc server URI.")
parser.add_argument("--stream_name", default="camera", help="Stream name for go2rtc.")
args = parser.parse_args()

# Define a target frame rate
TARGET_FPS = 30
DELAY = 1 / TARGET_FPS

class Go2RTCStreamer:
    def __init__(self, video_source, go2rtc_uri, stream_name):
        self.video_source = int(video_source) if video_source.isdigit() else video_source
        self.go2rtc_uri = go2rtc_uri
        self.stream_name = stream_name
        self.cap = None
        self.running = False
        self.go2rtc_process = None
        
    def start_go2rtc(self):
        """Start go2rtc as a subprocess if not already running."""
        # Check if go2rtc is already running
        try:
            response = requests.get(f"{self.go2rtc_uri}/api/info", timeout=2)
            print("go2rtc is already running")
            return True
        except (requests.ConnectionError, requests.Timeout):
            print("go2rtc is not running, starting it...")
            
        # Start go2rtc as a subprocess
        try:
            # Try to find go2rtc in PATH
            cmd = ["go2rtc", "-listen", ":1984"]
            self.go2rtc_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a bit for go2rtc to start
            time.sleep(2)
            
            # Check if it started successfully
            response = requests.get(f"{self.go2rtc_uri}/api/info", timeout=2)
            print("go2rtc started successfully")
            return True
        except (subprocess.SubprocessError, requests.ConnectionError, requests.Timeout) as e:
            print(f"Failed to start go2rtc: {e}")
            print("Please install go2rtc or start it manually")
            return False
    
    def configure_stream(self):
        """Configure the stream in go2rtc."""
        # Configure the stream to use ffmpeg for camera input
        stream_config = f"ffmpeg:{self.video_source}?input_format=mjpeg&video_size=1280x720&framerate=30"
        
        try:
            response = requests.post(
                f"{self.go2rtc_uri}/api/streams",
                json={"name": self.stream_name, "src": stream_config},
                timeout=5
            )
            if response.status_code == 200:
                print(f"Stream '{self.stream_name}' configured successfully")
                return True
            else:
                print(f"Failed to configure stream: {response.text}")
                return False
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"Failed to configure stream: {e}")
            return False
    
    def start_camera(self):
        """Start camera capture."""
        self.cap = cv2.VideoCapture(self.video_source)
        if not self.cap.isOpened():
            print(f"Error: Could not open video source: {self.video_source}")
            return False
        
        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        
        print(f"Camera started with source: {self.video_source}")
        return True
    
    def get_stream_url(self):
        """Get the URL for accessing the stream from go2rtc."""
        return f"{self.go2rtc_uri}/stream.mp4?src={self.stream_name}"
    
    def stop(self):
        """Stop all processes."""
        self.running = False
        if self.cap:
            self.cap.release()
        if self.go2rtc_process:
            self.go2rtc_process.terminate()
            self.go2rtc_process.wait()

async def stream_pose_landmarks():
    """
    Connects to the WebSocket server and streams pose landmarks, with auto-reconnect.
    """
    is_recording = False
    recording_session_id = None
    frame_count = 0
    recording_start_time = None
    
    # Initialize go2rtc streamer
    streamer = Go2RTCStreamer(args.source, args.go2rtc_uri, args.stream_name)
    
    # Start go2rtc
    if not streamer.start_go2rtc():
        print("Failed to start go2rtc, exiting...")
        return
    
    # Configure the stream
    if not streamer.configure_stream():
        print("Failed to configure stream, exiting...")
        streamer.stop()
        return
    
    # Start camera
    if not streamer.start_camera():
        print("Failed to start camera, exiting...")
        streamer.stop()
        return
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("Shutting down...")
        streamer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while True:
        print(f"Attempting to connect to WebSocket server at {args.ws_uri}...")
        try:
            async with websockets.connect(args.ws_uri) as websocket:
                print("Successfully connected to WebSocket server.")
                
                streamer.running = True

                while streamer.running and streamer.cap.isOpened():
                    ret, frame = streamer.cap.read()
                    if not ret:
                        print("End of video stream or cannot grab frame.")
                        break
                    
                    frame_count += 1
                    current_time = datetime.now()
                    
                    # Calculate timestamp if recording
                    timestamp = 0
                    if is_recording and recording_start_time:
                        timestamp = (current_time - recording_start_time).total_seconds()

                    # Process frame for pose detection
                    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # For now, we'll skip pose detection to focus on go2rtc integration
                    # In a full implementation, you would add MediaPipe pose detection here
                    landmarks_data = []
                    
                    # Prepare message data
                    message_data = {
                        'landmarks': landmarks_data,
                        'frame_number': frame_count,
                        'timestamp': timestamp
                    }
                    
                    # Always include frame image
                    # Encode frame as base64 for transmission
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')
                    message_data['frame_image'] = frame_base64
                    
                    try:
                        await websocket.send(json.dumps(message_data))
                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection lost. Reconnecting...")
                        break
                    
                    # Handle control messages from server
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                        control_data = json.loads(response)
                        
                        if control_data.get('type') == 'recording_started':
                            is_recording = True
                            recording_session_id = control_data.get('session_id')
                            recording_start_time = datetime.now()
                            frame_count = 0
                            print(f"Started recording session: {recording_session_id}")
                            
                        elif control_data.get('type') == 'recording_stopped':
                            is_recording = False
                            print(f"Stopped recording session: {recording_session_id}")
                            recording_session_id = None
                            recording_start_time = None
                            
                    except asyncio.TimeoutError:
                        # No control message, continue streaming
                        pass
                    
                    # Enforce the target frame rate
                    await asyncio.sleep(DELAY)

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"Failed to connect: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(stream_pose_landmarks())
    except KeyboardInterrupt:
        print("Streamer stopped by user.")