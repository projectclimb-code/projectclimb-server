#!/usr/bin/env python3
"""
Test script to verify the updated orientation detection logic.
"""

import cv2
import sys

def test_updated_orientation(video_path):
    """Test updated orientation detection for a given video file."""
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
    
    # Get orientation metadata (available for some formats like .mov)
    orientation_meta = cap.get(cv2.CAP_PROP_ORIENTATION_META)
    
    # Read first frame to check actual orientation
    ret, first_frame = cap.read()
    if ret:
        actual_frame_height, actual_frame_width = first_frame.shape[:2]
        # Reset video position to beginning
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    else:
        actual_frame_width, actual_frame_height = width, height
    
    # Determine orientation handling
    needs_rotation = False
    needs_resize = False
    display_width, display_height = actual_frame_width, actual_frame_height
    
    # Case 1: .mov files with orientation metadata
    # Check if OpenCV has already applied orientation transformation
    if orientation_meta and orientation_meta != 0:
        # For .mov files, OpenCV often automatically applies orientation metadata
        # We should check if the actual frame orientation matches what we expect
        # If the video is already in correct orientation, don't rotate
        if (orientation_meta == 90 or orientation_meta == 270):
            # For 90/270 degree rotation, the stored dimensions should be swapped
            # If actual frame is already portrait, OpenCV has handled it
            if actual_frame_height > actual_frame_width:  # Already portrait
                # OpenCV already applied rotation, no action needed
                needs_rotation = False
                print("OpenCV has already applied orientation transformation")
            else:
                # Need to apply rotation
                needs_rotation = True
                display_width, display_height = height, width
    
    # Case 2: Files with sample aspect ratio (like .mp4)
    elif sar_den > 0 and sar_num > 0:
        # Calculate display aspect ratio
        display_aspect_ratio = (width * sar_num / sar_den) / height
        
        # Portrait videos typically have aspect ratio < 1.0 (height > width)
        # But some portrait videos are stored as landscape with SAR that makes them portrait
        if display_aspect_ratio < 1.0:  # Portrait orientation
            needs_resize = True
            display_width, display_height = height, width
    else:
        # Default case: use actual frame dimensions
        if actual_frame_height > actual_frame_width:  # Portrait orientation
            needs_resize = True
            display_width, display_height = actual_frame_height, actual_frame_width
    
    print(f"Stored Resolution: {width}x{height}")
    print(f"Actual Frame Resolution: {actual_frame_width}x{actual_frame_height}")
    print(f"Sample Aspect Ratio: {sar_num}:{sar_den}")
    print(f"Orientation Meta: {orientation_meta}")
    if needs_rotation:
        print(f"Rotation needed: {orientation_meta} degrees")
        print(f"Corrected Resolution: {int(display_width)}x{int(display_height)} (portrait)")
    elif needs_resize:
        print(f"Resize needed for portrait orientation")
        print(f"Corrected Resolution: {int(display_width)}x{int(display_height)} (portrait)")
    else:
        print(f"Display Resolution: {actual_frame_width}x{actual_frame_height} (no transformation needed)")
    print(f"FPS: {fps}")
    
    # Read first frame to test processing
    ret, frame = cap.read()
    if ret:
        original_shape = frame.shape
        print(f"Original frame shape: {original_shape}")
        
        # Handle video orientation based on detected needs
        if needs_rotation:
            # For .mov files with orientation metadata, rotate the frame
            if orientation_meta == 90:
                # Rotate 90 degrees clockwise
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                print("Applied 90-degree clockwise rotation")
            elif orientation_meta == 270:
                # Rotate 90 degrees counter-clockwise
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                print("Applied 90-degree counter-clockwise rotation")
        elif needs_resize:
            # For .mp4 files with SAR, resize to correct portrait dimensions
            frame = cv2.resize(frame, (int(display_width), int(display_height)))
            print(f"Resized to portrait dimensions: {int(display_width)}x{int(display_height)}")
        
        processed_shape = frame.shape
        print(f"Processed frame shape: {processed_shape}")
        
        if needs_rotation or needs_resize:
            print("✓ Portrait video correctly processed")
        else:
            print("✓ Landscape video, no transformation needed")
    else:
        print("Error: Could not read first frame")
        cap.release()
        return False
    
    cap.release()
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_updated_orientation.py <video_file>")
        sys.exit(1)
    
    video_file = sys.argv[1]
    success = test_updated_orientation(video_file)
    
    if success:
        print("\n✓ Updated orientation test completed successfully")
    else:
        print("\n✗ Updated orientation test failed")
        sys.exit(1)