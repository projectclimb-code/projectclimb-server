#!/usr/bin/env python3
"""
Test script to verify the file input functionality of pose_streamer.py
"""

import subprocess
import time
import sys
import os

def test_file_input():
    """Test the file input functionality"""
    video_file = "data/bolder2.mov"
    
    # Check if the video file exists
    if not os.path.exists(video_file):
        print(f"Error: Video file '{video_file}' not found.")
        return False
    
    print("Testing file input without looping...")
    
    # Start the pose_streamer process
    process = subprocess.Popen(
        [sys.executable, "pose_streamer.py", "--file", video_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Print some output while running
    start_time = time.time()
    output_lines = []
    
    # Let it run for a longer time to ensure the video completes
    # but check output periodically
    while time.time() - start_time < 15:
        time.sleep(1)
        # Check if there's any output
        if process.poll() is not None:
            break
    
    # Get any remaining output
    remaining_output, _ = process.communicate()
    if remaining_output:
        output_lines.append(remaining_output)
    
    # Check if the process is still running
    if process.poll() is None:
        print("Process is still running after 15 seconds...")
        # Terminate the process
        process.terminate()
        process.wait()
        print("Process terminated.")
        if output_lines:
            print("Output while running:")
            for line in output_lines:
                print(line[:200])  # Truncate long lines
        return False
    else:
        print("Process has completed on its own.")
        if output_lines:
            print("Output while running:")
            for line in output_lines:
                print(line[:200])  # Truncate long lines
        return True

def test_file_input_with_loop():
    """Test the file input functionality with looping"""
    video_file = "data/bolder2.mov"
    
    # Check if the video file exists
    if not os.path.exists(video_file):
        print(f"Error: Video file '{video_file}' not found.")
        return False
    
    print("\nTesting file input with looping...")
    
    # Start the pose_streamer process with loop option
    process = subprocess.Popen(
        [sys.executable, "pose_streamer.py", "--file", video_file, "--loop"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Let it run for a longer time to ensure the video loops
    time.sleep(10)
    
    # Check if the process is still running
    if process.poll() is None:
        print("Process is still running after 5 seconds (expected with loop)...")
        # Terminate the process
        process.terminate()
        process.wait()
        print("Process terminated.")
        return True
    else:
        print("Process has completed unexpectedly.")
        stdout, stderr = process.communicate()
        if stdout:
            print("STDOUT:", stdout)
        if stderr:
            print("STDERR:", stderr)
        return False

if __name__ == "__main__":
    print("Testing pose_streamer.py file input functionality...\n")
    
    # Test without looping
    test1_passed = test_file_input()
    
    # Test with looping
    test2_passed = test_file_input_with_loop()
    
    print("\nTest Results:")
    print(f"File input without loop: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"File input with loop: {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)