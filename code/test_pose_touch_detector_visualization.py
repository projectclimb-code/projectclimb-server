#!/usr/bin/env python3
"""
Test script for the pose touch detector with visualization features.
This script demonstrates how to use the new command-line options for video display.
"""

import os
import sys
import django
import subprocess
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.append(str(Path(__file__).parent))
django.setup()

def main():
    print("Testing Pose Touch Detector with Visualization Options")
    print("=" * 60)
    
    # Check if we have a wall with calibration
    from climber.models import Wall, WallCalibration
    
    walls = Wall.objects.all()
    if not walls:
        print("No walls found in the database. Please create a wall first.")
        return
    
    # Find first wall with calibration
    test_wall = None
    for wall in walls:
        if WallCalibration.objects.filter(wall=wall).exists():
            test_wall = wall
            break
    
    if not test_wall:
        print("No calibrated walls found. Please create a wall with calibration first.")
        return
    
    print(f"Using wall: {test_wall.name} (ID: {test_wall.id})")
    
    # Check if we have a video file
    video_file = None
    possible_videos = [
        "data/bolder2.mov",
        "data/test_video.mp4",
        "data/pose_test.mp4"
    ]
    
    for v in possible_videos:
        if os.path.exists(v):
            video_file = v
            break
    
    # Build command
    cmd = [
        "uv", "run", "python", "manage.py", "pose_touch_detector",
        "--wall-id", str(test_wall.id),
        "--show-video",
        "--show-skeleton",
        "--show-svg",
        "--debug"
    ]
    
    if video_file:
        print(f"Using video file: {video_file}")
        cmd.extend(["--video-file", video_file])
        cmd.extend(["--loop"])
    else:
        print("No video file found, will use camera")
        cmd.extend(["--camera-source", "0"])
    
    print("\nCommand to run:")
    print(" ".join(cmd))
    print("\nPress Ctrl+C to stop the detector")
    print("Press 'q' in the video window to quit")
    
    # Run the command
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except subprocess.CalledProcessError as e:
        print(f"\nError running command: {e}")
    except FileNotFoundError:
        print("\nError: 'uv' command not found. Make sure uv is installed and in your PATH.")
        print("Alternatively, you can run:")
        print(f"{' '.join(cmd[2:])}")  # Skip 'uv run python' part

if __name__ == "__main__":
    main()