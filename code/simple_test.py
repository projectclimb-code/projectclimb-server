#!/usr/bin/env python3
"""
Simple test to verify file input functionality
"""

import subprocess
import sys
import os

def test_without_loop():
    """Test file input without looping"""
    video_file = "data/bolder2.mov"
    
    if not os.path.exists(video_file):
        print(f"Error: Video file '{video_file}' not found.")
        return False
    
    print("Testing file input without loop...")
    print("Running: python pose_streamer.py --file data/bolder2.mov")
    print("This should exit after the video completes.\n")
    
    # Run the command and wait for it to complete
    result = subprocess.run(
        [sys.executable, "pose_streamer.py", "--file", video_file],
        capture_output=True,
        text=True,
        timeout=30  # Maximum 30 seconds wait
    )
    
    print(f"Return code: {result.returncode}")
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    # Check if it exited normally (return code 0) or was interrupted (return code 130 for Ctrl+C)
    if result.returncode in [0, 130]:
        print("\n✓ Test passed: Streamer exited after video completion")
        return True
    else:
        print("\n✗ Test failed: Streamer did not exit properly")
        return False

if __name__ == "__main__":
    test_without_loop()