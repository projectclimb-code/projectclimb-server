import cv2
import mediapipe as mp
import argparse
import asyncio
import websockets
import json
import base64
import numpy as np
from datetime import datetime

# Setup argument parser
parser = argparse.ArgumentParser(description="Capture video, detect pose, and stream landmarks via WebSocket.")
parser.add_argument("--source", default="0", help="Video source (camera index or file path). Default is 0 (webcam).")
parser.add_argument("--ws_uri", default="ws://localhost:8000/ws/pose/", help="WebSocket URI of the Django server.")
parser.add_argument("--loop", action="store_true", help="Loop the video file indefinitely when using file input.")
parser.add_argument("--file", type=str, help="Path to video file to use as input (overrides --source).")
args = parser.parse_args()

# Determine the video source
if args.file:
    video_source = args.file
    is_file = True
else:
    video_source = int(args.source) if args.source.isdigit() else args.source
    is_file = False

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# Define a target frame rate
TARGET_FPS = 30
DELAY = 1 / TARGET_FPS

async def stream_pose_landmarks():
    """
    Connects to the WebSocket server and streams pose landmarks, with auto-reconnect.
    """
    is_recording = False
    recording_session_id = None
    frame_count = 0
    recording_start_time = None
    should_exit = False
    
    while not should_exit:
        print(f"Attempting to connect to WebSocket server at {args.ws_uri}...")
        try:
            async with websockets.connect(args.ws_uri) as websocket:
                print("Successfully connected to WebSocket server.")
                
                cap = cv2.VideoCapture(video_source)

                if not cap.isOpened():
                    print(f"Error: Could not open video source: {video_source}")
                    if is_file and not args.loop:
                        # If we can't open the file and we're not looping, exit
                        should_exit = True
                        break
                    await asyncio.sleep(5)
                    continue

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        if is_file:
                            print("End of video file.")
                            if args.loop:
                                print("Restarting video from beginning...")
                                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                continue
                            else:
                                print("File input completed. Exiting...")
                                should_exit = True
                                break
                        else:
                            print("Cannot grab frame from camera.")
                            break
                    
                    frame_count += 1
                    current_time = datetime.now()
                    
                    # Calculate timestamp if recording
                    timestamp = 0
                    if is_recording and recording_start_time:
                        timestamp = (current_time - recording_start_time).total_seconds()

                    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = pose.process(image_rgb)

                    landmarks_data = []
                    if results.pose_world_landmarks:
                        for landmark in results.pose_world_landmarks.landmark:
                            landmarks_data.append({
                                'x': landmark.x,
                                'y': landmark.y,
                                'z': landmark.z,
                                'visibility': landmark.visibility,
                            })
                    
                    # Prepare message data
                    message_data = {
                        'landmarks': landmarks_data,
                        'frame_number': frame_count,
                        'timestamp': timestamp
                    }
                    
                    # Always include frame image
                    # Encode frame as base64 for transmission
                    #_, buffer = cv2.imencode('.jpg', frame)
                    #frame_base64 = base64.b64encode(buffer).decode('utf-8')
                    #message_data['frame_image'] = frame_base64
                    
                    try:
                        if landmarks_data:
                            await websocket.send(json.dumps(message_data))
                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection lost. Reconnecting...")
                        break
                    
                    # Handle control messages from server
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.001)

                            
                    except asyncio.TimeoutError:
                        # No control message, continue streaming
                        pass
                    
                    # Enforce the target frame rate
                    await asyncio.sleep(DELAY)

                cap.release()
                
                # If we're not looping and we reached the end of a file, exit the outer loop
                if is_file and not args.loop and should_exit:
                    break

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"Failed to connect: {e}.", end="")
            if is_file and not args.loop:
                print(" Exiting since we're using file input without loop.")
                should_exit = True
                break
            else:
                print(" Retrying in 5 seconds...")
                await asyncio.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}.", end="")
            if is_file and not args.loop:
                print(" Exiting since we're using file input without loop.")
                should_exit = True
                break
            else:
                print(" Retrying in 5 seconds...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(stream_pose_landmarks())
    except KeyboardInterrupt:
        print("Streamer stopped by user.")
