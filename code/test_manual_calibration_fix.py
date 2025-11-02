#!/usr/bin/env python3
"""
Test script to verify manual point calibration fixes
"""

import os
import sys
import django
import numpy as np
import cv2

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.models import Wall, WallCalibration
from climber.calibration.calibration_utils import CalibrationUtils


def test_manual_calibration():
    """Test manual point calibration functionality"""
    
    # Get a wall with calibration
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No wall found in database")
            return False
            
        # Look for manual point calibration
        calibration = WallCalibration.objects.filter(
            wall=wall, 
            calibration_type='manual_points'
        ).first()
        
        if not calibration:
            print("No manual point calibration found for wall")
            return False
            
        print(f"Testing with wall: {wall.name}")
        print(f"Calibration: {calibration.name}")
        print(f"Calibration type: {calibration.calibration_type}")
        
    except Exception as e:
        print(f"Error loading wall/calibration: {e}")
        return False
    
    # Check if calibration has required data
    if not calibration.perspective_transform:
        print("No perspective transform matrix in calibration")
        return False
    
    if not calibration.manual_image_points or not calibration.manual_svg_points:
        print("No manual points in calibration")
        return False
    
    print(f"Image points: {calibration.manual_image_points}")
    print(f"SVG points: {calibration.manual_svg_points}")
    print(f"Transform matrix: {calibration.perspective_transform}")
    
    # Initialize calibration utils
    calib_utils = CalibrationUtils()
    
    # Test transformation matrix
    try:
        transform_matrix = np.array(calibration.perspective_transform, dtype=np.float32)
        print("Loaded calibration transformation matrix")
        
        # Test transforming a few points from SVG to image coordinates
        test_points = [
            (0, 0),  # Top-left corner
            (100, 100),  # Test point
            (200, 200),  # Another test point
        ]
        
        print("\nTesting point transformations:")
        for i, point in enumerate(test_points):
            transformed = calib_utils.transform_point_from_svg(point, transform_matrix)
            print(f"Point {i+1}: SVG({point[0]:.1f}, {point[1]:.1f}) -> Image({transformed[0]:.1f}, {transformed[1]:.1f})")
        
        # Test transforming image points to SVG coordinates
        image_points = calibration.manual_image_points
        svg_points = calibration.manual_svg_points
        
        print("\nTesting manual point transformations:")
        for i, (img_pt, svg_pt) in enumerate(zip(image_points, svg_points)):
            # Transform image point to SVG
            transformed_svg = calib_utils.transform_point_to_svg(img_pt, transform_matrix)
            # Calculate error
            error = np.sqrt((transformed_svg[0] - svg_pt[0])**2 + (transformed_svg[1] - svg_pt[1])**2)
            print(f"Point {i+1}: Image({img_pt[0]:.1f}, {img_pt[1]:.1f}) -> SVG({transformed_svg[0]:.1f}, {transformed_svg[1]:.1f})")
            print(f"  Expected SVG: ({svg_pt[0]:.1f}, {svg_pt[1]:.1f}), Error: {error:.2f}")
        
        return True
        
    except Exception as e:
        print(f"Error with calibration transformation: {e}")
        return False


def test_calibration_detail_view():
    """Test if calibration detail view can properly display transformed SVG"""
    
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No wall found in database")
            return False
            
        calibration = WallCalibration.objects.filter(
            wall=wall, 
            calibration_type='manual_points'
        ).first()
        
        if not calibration:
            print("No manual point calibration found for wall")
            return False
        
        # Check if wall has required files
        if not wall.wall_image:
            print("No wall image found")
            return False
            
        if not wall.svg_file:
            print("No SVG file found")
            return False
        
        print(f"Wall image: {wall.wall_image.url}")
        print(f"Wall SVG: {wall.svg_file.url}")
        print(f"Calibration transform matrix available: {bool(calibration.perspective_transform)}")
        
        return True
        
    except Exception as e:
        print(f"Error checking calibration detail view requirements: {e}")
        return False


if __name__ == "__main__":
    print("Testing manual point calibration fixes...")
    
    print("\n=== Testing Manual Point Calibration ===")
    calibration_test = test_manual_calibration()
    
    print("\n=== Testing Calibration Detail View ===")
    detail_test = test_calibration_detail_view()
    
    if calibration_test and detail_test:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)