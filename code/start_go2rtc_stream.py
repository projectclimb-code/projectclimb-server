#!/usr/bin/env python3
"""
Script to start video capture with go2rtc integration.
This script will:
1. Start or connect to go2rtc
2. Configure the camera stream
3. Make the stream available to multiple consumers
"""

import subprocess
import time
import requests
import json
import argparse
import sys
import os

def check_go2rtc_running(go2rtc_url="http://localhost:1984"):
    """Check if go2rtc is running."""
    try:
        response = requests.get(f"{go2rtc_url}/api/info", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False

def configure_camera_stream(go2rtc_url="http://localhost:1984", camera_source="0", stream_name="camera"):
    """Configure the camera stream in go2rtc."""
    # For direct camera access, we'll use ffmpeg
    stream_config = f"ffmpeg:{camera_source}?input_format=mjpeg&video_size=1280x720&framerate=30"
    
    try:
        response = requests.post(
            f"{go2rtc_url}/api/streams",
            json={"name": stream_name, "src": stream_config},
            timeout=5
        )
        if response.status_code == 200:
            print(f"Stream '{stream_name}' configured successfully")
            return True
        else:
            print(f"Failed to configure stream: {response.text}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"Failed to configure stream: {e}")
        return False

def start_video_streamer(script_path="video_go2rtc.py", camera_source="0"):
    """Start the video streamer script."""
    try:
        cmd = ["python", script_path, "--source", camera_source]
        process = subprocess.Popen(cmd)
        print(f"Started video streamer with PID: {process.pid}")
        return process
    except Exception as e:
        print(f"Failed to start video streamer: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Start video capture with go2rtc integration.")
    parser.add_argument("--camera", default="0", help="Camera source (default: 0)")
    parser.add_argument("--go2rtc-url", default="http://localhost:1984", help="go2rtc URL")
    parser.add_argument("--stream-name", default="camera", help="Stream name")
    parser.add_argument("--no-streamer", action="store_true", help="Don't start the video streamer script")
    
    args = parser.parse_args()
    
    print("Starting go2rtc video stream setup...")
    
    # Check if go2rtc is running
    if not check_go2rtc_running(args.go2rtc_url):
        print("go2rtc is not running. Please start it with: docker-compose up go2rtc")
        sys.exit(1)
    
    print("go2rtc is running.")
    
    # Configure the camera stream
    if configure_camera_stream(args.go2rtc_url, args.camera, args.stream_name):
        print(f"Camera stream configured at: {args.go2rtc_url}/stream.mp4?src={args.stream_name}")
    else:
        print("Failed to configure camera stream.")
        sys.exit(1)
    
    # Start the video streamer script
    if not args.no_streamer:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "video_go2rtc.py")
        
        if not os.path.exists(script_path):
            print(f"Video streamer script not found at: {script_path}")
            sys.exit(1)
        
        process = start_video_streamer(script_path, args.camera)
        if process:
            try:
                # Keep the script running
                print("Video streamer started. Press Ctrl+C to stop.")
                process.wait()
            except KeyboardInterrupt:
                print("\nStopping video streamer...")
                process.terminate()
                process.wait()
    
    print("Setup complete.")

if __name__ == "__main__":
    main()