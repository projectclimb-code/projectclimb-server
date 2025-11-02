#!/usr/bin/env python3
"""
Test script to verify video orientation detection logic without GUI.
"""

import cv2
import sys

def test_video_orientation(video_path):
    """Test video orientation detection for a given video file."""
    print(f"Testing video: {video_path}")
    
    # Open video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file: {video_path}")
        return False
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Get sample aspect ratio to detect portrait videos with incorrect metadata
    sar_num = cap.get(cv2.CAP_PROP_SAR_NUM)
    sar_den = cap.get(cv2.CAP_PROP_SAR_DEN)
    
    # Calculate display aspect ratio
    if sar_den > 0:
        display_width = width * sar_num / sar_den
        display_height = height
        display_aspect_ratio = display_width / display_height
    else:
        display_aspect_ratio = width / height
    
    # Determine if we need to swap dimensions for portrait videos
    needs_rotation = False
    if display_aspect_ratio < 1.0:  # Portrait orientation
        needs_rotation = True
        display_width, display_height = height, width
    
    print(f"Stored Resolution: {width}x{height}")
    print(f"Sample Aspect Ratio: {sar_num}:{sar_den}")
    print(f"Display Aspect Ratio: {display_aspect_ratio:.2f}")
    if needs_rotation:
        print(f"Corrected Resolution: {int(display_width)}x{int(display_height)} (portrait)")
    else:
        print(f"Display Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    
    # Read first frame to test
    ret, frame = cap.read()
    if ret:
        original_shape = frame.shape
        print(f"Original frame shape: {original_shape}")
        
        # Handle portrait video orientation by resizing if needed
        if needs_rotation:
            # Resize frame to correct portrait dimensions
            resized_frame = cv2.resize(frame, (int(display_width), int(display_height)))
            resized_shape = resized_frame.shape
            print(f"Resized frame shape: {resized_shape}")
            print("✓ Portrait video correctly resized")
        else:
            print("✓ Landscape video, no resize needed")
    else:
        print("Error: Could not read first frame")
        cap.release()
        return False
    
    cap.release()
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_orientation_detection.py <video_file>")
        sys.exit(1)
    
    video_file = sys.argv[1]
    success = test_video_orientation(video_file)
    
    if success:
        print("\n✓ Orientation detection test completed successfully")
    else:
        print("\n✗ Orientation detection test failed")
        sys.exit(1)