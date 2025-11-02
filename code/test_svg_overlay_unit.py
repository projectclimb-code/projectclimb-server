#!/usr/bin/env python3
"""
Unit test for SVG overlay functionality in pose_touch_detector.py
"""

import os
import sys
import django
import numpy as np
import cv2
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.append(str(Path(__file__).parent))
django.setup()

def main():
    print("Unit Test for SVG Overlay")
    print("=" * 60)
    
    # Import after Django setup
    from climber.models import Wall, WallCalibration
    from climber.management.commands.pose_touch_detector import PoseTouchDetector
    
    # Check if we have a wall with calibration
    walls = Wall.objects.all()
    if not walls:
        print("No walls found in database. Please create a wall first.")
        return False
    
    # Find first wall with calibration
    test_wall = None
    for wall in walls:
        if WallCalibration.objects.filter(wall=wall).exists():
            test_wall = wall
            break
    
    if not test_wall:
        print("No calibrated walls found. Please create a wall with calibration first.")
        return False
    
    print(f"Using wall: {test_wall.name} (ID: {test_wall.id})")
    
    # Create a detector instance with minimal settings
    detector = PoseTouchDetector(
        wall_id=test_wall.id,
        show_video=False,  # Don't show video
        show_svg=True,    # Enable SVG overlay
        debug=True
    )
    
    # Run setup
    if not detector.setup():
        print("Failed to setup detector")
        return False
    
    # Check if SVG overlay was created
    if detector.svg_overlay is None:
        print("SVG overlay was not created")
        return False
    
    print("SVG overlay created successfully")
    
    # Check if overlay has non-zero pixels (indicating shapes were drawn)
    non_zero_pixels = np.count_nonzero(detector.svg_overlay)
    total_pixels = detector.svg_overlay.size
    percentage = (non_zero_pixels / total_pixels) * 100
    
    print(f"SVG overlay has {non_zero_pixels} non-zero pixels out of {total_pixels} ({percentage:.2f}%)")
    
    if percentage < 0.1:  # Less than 0.1% of pixels are non-zero
        print("Warning: SVG overlay appears to be mostly empty")
        return False
    
    # Save a sample of the overlay for visual inspection
    output_path = "test_svg_overlay.png"
    cv2.imwrite(output_path, detector.svg_overlay)
    print(f"SVG overlay sample saved to: {output_path}")
    
    # Print additional debugging info
    print(f"SVG overlay shape: {detector.svg_overlay.shape}")
    print(f"SVG overlay min/max values: BGR")
    for i, color in enumerate(['Blue', 'Green', 'Red']):
        min_val = np.min(detector.svg_overlay[:,:,i])
        max_val = np.max(detector.svg_overlay[:,:,i])
        non_zero = np.count_nonzero(detector.svg_overlay[:,:,i])
        print(f"  {color}: min={min_val}, max={max_val}, non_zero={non_zero}")
    
    # Check if file was actually created
    import os
    if os.path.exists(output_path):
        print(f"✅ File {output_path} was created successfully")
        file_size = os.path.getsize(output_path)
        print(f"File size: {file_size} bytes")
    else:
        print(f"❌ File {output_path} was NOT created")
    
    # Test with a blank frame
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # Simulate the display process
    detector._display_frame(test_frame, [])
    
    print("SVG overlay test completed successfully")
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ SVG overlay test PASSED")
        sys.exit(0)
    else:
        print("\n❌ SVG overlay test FAILED")
        sys.exit(1)