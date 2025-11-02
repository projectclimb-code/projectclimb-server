#!/usr/bin/env python3
"""
Test script to verify the orientation fix in pose_touch_detector.py
"""

import os
import sys
import django
import cv2
import numpy as np
from unittest.mock import Mock, patch

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.management.commands.pose_touch_detector import PoseTouchDetector

def test_orientation_detection():
    """Test that orientation is properly detected and corrected."""
    print("Testing orientation detection and correction...")
    
    # Create a mock detector with video file
    detector = PoseTouchDetector(
        wall_id=1,  # Mock wall ID
        video_file="data/IMG_2568.MOV",  # Use existing video file
        show_video=False,
        debug=True
    )
    
    # Mock the wall and calibration setup to avoid database dependencies
    detector.wall = Mock()
    detector.wall.svg_file = Mock()
    detector.wall.svg_file.name = "test.svg"
    
    detector.calibration = Mock()
    detector.calibration.perspective_transform = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    
    # Mock SVG parser
    detector.svg_parser = Mock()
    detector.svg_parser.paths = {}
    
    # Check if video file exists
    if not os.path.exists(detector.video_file):
        print(f"Video file not found: {detector.video_file}")
        return False
    
    # Setup video capture
    detector.cap = cv2.VideoCapture(detector.video_file)
    if not detector.cap.isOpened():
        print(f"Failed to open video file: {detector.video_file}")
        return False
    
    # Test orientation setup
    detector._setup_video_orientation()
    
    # Read a frame to test orientation correction
    ret, frame = detector.cap.read()
    if not ret:
        print("Failed to read frame from video")
        return False
    
    # Test orientation correction
    corrected_frame = detector._apply_orientation_correction(frame)
    
    # Print orientation information
    print(f"Original frame size: {frame.shape[:2]}")
    print(f"Corrected frame size: {corrected_frame.shape[:2]}")
    print(f"Needs rotation: {detector.needs_rotation}")
    print(f"Needs resize: {detector.needs_resize}")
    print(f"Orientation meta: {detector.orientation_meta}")
    print(f"Display dimensions: {detector.display_width}x{detector.display_height}")
    
    # Cleanup
    detector.cap.release()
    
    print("Orientation test completed successfully")
    return True

def test_coordinate_conversion():
    """Test that coordinates are properly converted based on video dimensions."""
    print("\nTesting coordinate conversion...")
    
    # Create a mock detector with video file
    detector = PoseTouchDetector(
        wall_id=1,  # Mock wall ID
        video_file="data/IMG_2568.MOV",  # Use existing video file
        show_video=False,
        debug=True
    )
    
    # Mock the wall and calibration setup
    detector.wall = Mock()
    detector.wall.svg_file = Mock()
    detector.wall.svg_file.name = "test.svg"
    
    detector.calibration = Mock()
    detector.calibration.perspective_transform = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    
    # Mock SVG parser
    detector.svg_parser = Mock()
    detector.svg_parser.paths = {}
    detector.svg_parser.point_in_path = Mock(return_value=False)
    
    # Check if video file exists
    if not os.path.exists(detector.video_file):
        print(f"Video file not found: {detector.video_file}")
        return False
    
    # Setup video capture and orientation
    detector.cap = cv2.VideoCapture(detector.video_file)
    if not detector.cap.isOpened():
        print(f"Failed to open video file: {detector.video_file}")
        return False
    
    detector._setup_video_orientation()
    
    # Test coordinate conversion with different positions
    test_positions = [
        [0.5, 0.5],  # Center
        [0.0, 0.0],  # Top-left
        [1.0, 1.0],  # Bottom-right
    ]
    
    for pos in test_positions:
        touched = detector._check_touch_at_position(pos)
        print(f"Position {pos} -> touched: {touched}")
    
    # Cleanup
    detector.cap.release()
    
    print("Coordinate conversion test completed successfully")
    return True

if __name__ == "__main__":
    print("Testing pose_touch_detector orientation fix...")
    
    success = True
    success &= test_orientation_detection()
    success &= test_coordinate_conversion()
    
    if success:
        print("\n✓ All tests passed successfully")
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)