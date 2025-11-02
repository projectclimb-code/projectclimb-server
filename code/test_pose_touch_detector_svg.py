#!/usr/bin/env python3
"""
Test script to verify pose touch detector with SVG overlay
"""

import os
import sys
import django
import argparse

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.management.commands.pose_touch_detector import PoseTouchDetector


def test_pose_touch_detector_with_svg(wall_id, video_file=None):
    """Test the pose touch detector with SVG overlay enabled"""
    
    print(f"Testing pose touch detector with SVG overlay for wall {wall_id}")
    
    # Create detector with SVG overlay enabled
    detector = PoseTouchDetector(
        wall_id=wall_id,
        session_id=None,
        camera_source=0,
        fake_pose=False,
        video_file=video_file,
        loop=False,
        touch_threshold=0.1,
        debug=True,
        show_video=True,
        show_skeleton=True,
        show_svg=True  # Enable SVG overlay
    )
    
    # Setup detector
    if not detector.setup():
        print("Failed to setup detector")
        return False
    
    print("Detector setup successful")
    print("Starting pose touch detection with SVG overlay...")
    print("Press 'q' to quit")
    
    # Run detector for a short time
    import time
    start_time = time.time()
    max_duration = 30  # Run for 30 seconds max
    
    detector.running = True
    
    try:
        while detector.running and (time.time() - start_time) < max_duration:
            if video_file:
                # Get frame from video file
                ret, frame = detector.cap.read()
                if not ret:
                    print("End of video file")
                    break
                
                # Apply orientation correction if needed
                corrected_frame = detector._apply_orientation_correction(frame)
                
                # Detect touches
                touched_objects, annotated_frame = detector.detect_touches(corrected_frame)
                
                # Display frame with visualizations
                detector._display_frame(annotated_frame, touched_objects)
                
                # Debug output
                if touched_objects:
                    print(f"Touched objects: {touched_objects}")
                
                # Small delay
                time.sleep(0.03)
            else:
                print("Live camera testing not implemented in this test script")
                break
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        detector.cleanup()
    
    print("Test completed")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test pose touch detector with SVG overlay')
    parser.add_argument('--wall-id', type=int, required=True, help='ID of wall to test')
    parser.add_argument('--video-file', type=str, help='Path to video file to use as input')
    
    args = parser.parse_args()
    
    success = test_pose_touch_detector_with_svg(args.wall_id, args.video_file)
    if not success:
        sys.exit(1)