#!/usr/bin/env python3
"""
Test script to verify calibration transformation is working correctly
"""

import os
import sys
import django
import numpy as np

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from climber.models import Wall, WallCalibration

def test_calibration_transformation():
    """Test that calibration transformation is being applied correctly"""
    
    # Get a wall with calibrations
    walls = Wall.objects.all()
    
    if not walls:
        print("No walls found in database")
        return
    
    for wall in walls:
        print(f"\n=== Wall: {wall.name} (ID: {wall.id}) ===")
        
        # Check if wall has SVG and image
        if not wall.svg_file:
            print("  No SVG file associated with this wall")
            continue
            
        if not wall.wall_image:
            print("  No wall image associated with this wall")
            continue
        
        # Get calibrations for this wall
        calibrations = wall.calibrations.all()
        
        if not calibrations:
            print("  No calibrations found for this wall")
            continue
            
        for calibration in calibrations:
            print(f"\n  --- Calibration: {calibration.name} (ID: {calibration.id}) ---")
            print(f"  Type: {calibration.calibration_type}")
            print(f"  Active: {calibration.is_active}")
            
            # Check perspective transform
            if calibration.perspective_transform:
                transform = calibration.perspective_transform
                print(f"  Perspective Transform: {transform}")
                
                # Verify it's a 3x3 matrix
                if isinstance(transform, list) and len(transform) == 3:
                    if all(isinstance(row, list) and len(row) == 3 for row in transform):
                        print("  ✓ Transform matrix has correct dimensions (3x3)")
                        
                        # Convert to numpy array for testing
                        np_transform = np.array(transform, dtype=np.float32)
                        print(f"  Numpy array shape: {np_transform.shape}")
                        
                        # Test transformation with a sample point
                        test_point = np.array([100, 100, 1.0])  # Sample point in homogeneous coordinates
                        transformed = np_transform @ test_point
                        
                        if transformed[2] != 0:
                            result = (transformed[0] / transformed[2], transformed[1] / transformed[2])
                            print(f"  Test point [100, 100] transforms to [{result[0]:.2f}, {result[1]:.2f}]")
                        else:
                            print("  ✗ Transform results in invalid homogeneous coordinates")
                    else:
                        print("  ✗ Transform matrix rows don't have 3 elements each")
                else:
                    print("  ✗ Transform matrix is not a 3x3 matrix")
            else:
                print("  ✗ No perspective transform found")
            
            # Check manual points
            if calibration.manual_image_points and calibration.manual_svg_points:
                print(f"  Manual image points: {calibration.manual_image_points}")
                print(f"  Manual SVG points: {calibration.manual_svg_points}")
                
                if len(calibration.manual_image_points) == len(calibration.manual_svg_points):
                    print("  ✓ Manual points have matching counts")
                else:
                    print("  ✗ Manual points have mismatched counts")

if __name__ == "__main__":
    test_calibration_transformation()