#!/usr/bin/env python3
"""
Test script to see what OpenCV actually reads from .mov files without any transformations.
"""

import cv2
import sys

def test_mov_raw(video_path):
    """Test what OpenCV reads from .mov file without transformations."""
    print(f"Testing raw .mov video: {video_path}")
    
    # Open video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file: {video_path}")
        return False
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Get sample aspect ratio
    sar_num = cap.get(cv2.CAP_PROP_SAR_NUM)
    sar_den = cap.get(cv2.CAP_PROP_SAR_DEN)
    
    # Get orientation metadata
    orientation_meta = cap.get(cv2.CAP_PROP_ORIENTATION_META)
    
    print(f"OpenCV reports:")
    print(f"  Width: {width}")
    print(f"  Height: {height}")
    print(f"  Sample Aspect Ratio: {sar_num}:{sar_den}")
    print(f"  Orientation Meta: {orientation_meta}")
    print(f"  FPS: {fps}")
    
    # Read first frame to see actual dimensions
    ret, frame = cap.read()
    if ret:
        print(f"  First frame shape: {frame.shape}")
        print(f"  Frame appears as: {'portrait' if frame.shape[0] > frame.shape[1] else 'landscape'}")
        
        # Save a small sample to check visually
        sample_frame = frame[0:100, 0:100]  # Top-left corner
        print(f"  Top-left 100x100 sample shape: {sample_frame.shape}")
    else:
        print("Error: Could not read first frame")
        cap.release()
        return False
    
    cap.release()
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_mov_raw.py <video_file>")
        sys.exit(1)
    
    video_file = sys.argv[1]
    success = test_mov_raw(video_file)
    
    if success:
        print("\n✓ Raw .mov test completed")
    else:
        print("\n✗ Raw .mov test failed")
        sys.exit(1)