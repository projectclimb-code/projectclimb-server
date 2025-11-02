#!/usr/bin/env python3
"""
Test script to demonstrate the file input functionality of pose_streamer.py
"""

import subprocess
import sys
import os

def main():
    # Check if a video file path is provided
    if len(sys.argv) < 2:
        print("Usage: python test_pose_streamer_file.py <video_file_path> [--loop]")
        print("Example: python test_pose_streamer_file.py data/bolder2.mov --loop")
        sys.exit(1)
    
    video_file = sys.argv[1]
    loop = "--loop" in sys.argv
    
    # Check if the video file exists
    if not os.path.exists(video_file):
        print(f"Error: Video file '{video_file}' not found.")
        sys.exit(1)
    
    # Build the command to run pose_streamer.py with file input
    cmd = [
        sys.executable, "pose_streamer.py",
        "--file", video_file
    ]
    
    if loop:
        cmd.append("--loop")
    
    print(f"Running command: {' '.join(cmd)}")
    print("Press Ctrl+C to stop the streamer")
    
    try:
        # Run the pose_streamer.py script
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStreamer stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"Error running pose_streamer.py: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()