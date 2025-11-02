#!/usr/bin/env python3
"""
Detailed test script to investigate .mov file orientation issues.
"""

import cv2
import sys

def test_mov_orientation(video_path):
    """Test .mov file orientation detection in detail."""
    print(f"Testing .mov video: {video_path}")
    
    # Open video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file: {video_path}")
        return False
    
    # Get all available properties
    print("\n=== OpenCV Video Properties ===")
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Get sample aspect ratio
    sar_num = cap.get(cv2.CAP_PROP_SAR_NUM)
    sar_den = cap.get(cv2.CAP_PROP_SAR_DEN)
    
    # Get other potentially useful properties
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Width: {width}")
    print(f"Height: {height}")
    print(f"FPS: {fps}")
    print(f"Sample Aspect Ratio: {sar_num}:{sar_den}")
    print(f"FOURCC: {fourcc}")
    print(f"Frame Count: {frame_count}")
    
    # Try to get orientation metadata (if available)
    try:
        # Some backends might expose orientation
        orientation = cap.get(cv2.CAP_PROP_ORIENTATION_META)
        print(f"Orientation Meta: {orientation}")
    except:
        print("Orientation meta not available")
    
    # Calculate display aspect ratio
    if sar_den > 0:
        display_width = width * sar_num / sar_den
        display_height = height
        display_aspect_ratio = display_width / display_height
    else:
        display_aspect_ratio = width / height
    
    print(f"Display Aspect Ratio: {display_aspect_ratio:.2f}")
    
    # Determine if we need to swap dimensions for portrait videos
    needs_rotation = False
    if display_aspect_ratio < 1.0:  # Portrait orientation
        needs_rotation = True
        display_width, display_height = height, width
    
    if needs_rotation:
        print(f"Detected as PORTRAIT - needs resizing to {int(display_width)}x{int(display_height)}")
    else:
        print(f"Detected as LANDSCAPE - no resize needed")
    
    # Read first frame to see actual dimensions
    ret, frame = cap.read()
    if ret:
        print(f"\n=== First Frame Analysis ===")
        print(f"Frame shape: {frame.shape}")
        print(f"Frame dtype: {frame.dtype}")
        
        # Handle portrait video orientation by resizing if needed
        if needs_rotation:
            # Resize frame to correct portrait dimensions
            resized_frame = cv2.resize(frame, (int(display_width), int(display_height)))
            print(f"Resized frame shape: {resized_frame.shape}")
        else:
            print("No resize applied")
    else:
        print("Error: Could not read first frame")
        cap.release()
        return False
    
    cap.release()
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_mov_orientation.py <video_file>")
        sys.exit(1)
    
    video_file = sys.argv[1]
    success = test_mov_orientation(video_file)
    
    if success:
        print("\n✓ .mov orientation test completed successfully")
    else:
        print("\n✗ .mov orientation test failed")
        sys.exit(1)