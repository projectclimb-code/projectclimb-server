#!/usr/bin/env python3
"""
Simple script to open a video file, detect human pose with MediaPipe, and display the video with pose overlay.
"""

import cv2
import mediapipe as mp
import argparse
import os

def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Display video with pose detection overlay.")
    parser.add_argument("--file", default="data/bolder2.mov", help="Path to video file. Default is data/bolder2.mov")
    parser.add_argument("--loop", action="store_true", help="Loop the video indefinitely.")
    args = parser.parse_args()

    # Check if the video file exists
    if not os.path.exists(args.file):
        print(f"Error: Video file '{args.file}' not found.")
        return

    # Initialize MediaPipe Pose
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    
    # For static images:
    # pose = mp_pose.Pose(static_image_mode=True, model_complexity=2, enable_segmentation=True)
    
    # For video input:
    pose = mp_pose.Pose(
        static_image_mode=False, 
        model_complexity=1, 
        enable_segmentation=False, 
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # Open video file
    cap = cv2.VideoCapture(args.file)
    if not cap.isOpened():
        print(f"Error: Could not open video file: {args.file}")
        return

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Get sample aspect ratio to detect portrait videos with incorrect metadata
    # OpenCV stores SAR as (num, den) where the actual display aspect ratio = SAR * (width/height)
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
        # We should check if actual frame orientation matches what we expect
        # If video is already in correct orientation, don't rotate
        if (orientation_meta == 90 or orientation_meta == 270):
            # For 90/270 degree rotation, stored dimensions should be swapped
            # If actual frame is already portrait, OpenCV has handled it
            if actual_frame_height > actual_frame_width:  # Already portrait
                # OpenCV already applied rotation, no action needed
                needs_rotation = False
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
    
    print(f"Video: {args.file}")
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
    print("Press 'q' to quit, ' ' to pause/resume")

    paused = False
    frame_count = 0

    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret:
                if args.loop:
                    print("Restarting video from beginning...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    frame_count = 0
                    continue
                else:
                    print("End of video.")
                    break
            
            frame_count += 1
            
            # Handle video orientation based on detected needs
            if needs_rotation:
                # For .mov files with orientation metadata, rotate the frame
                if orientation_meta == 90:
                    # Rotate 90 degrees clockwise
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif orientation_meta == 270:
                    # Rotate 90 degrees counter-clockwise
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif needs_resize:
                # For .mp4 files with SAR, resize to correct portrait dimensions
                frame = cv2.resize(frame, (int(display_width), int(display_height)))
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process the frame and detect pose
            results = pose.process(frame_rgb)
            
            # Draw pose landmarks on the frame
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
            
            # Add frame counter
            cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display the frame
            cv2.imshow('Pose Detection', frame)
        
        # Handle key presses
        key = cv2.waitKey(int(1000/fps) if fps > 0 else 30) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '):
            paused = not paused
            print("Paused" if paused else "Resumed")

    # Clean up
    cap.release()
    cv2.destroyAllWindows()
    pose.close()

if __name__ == "__main__":
    main()