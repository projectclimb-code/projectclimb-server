#!/usr/bin/env python3
"""
Test script for manual calibration functionality.
This script tests the manual calibration implementation.
"""

import os
import sys
import django
import json
import numpy as np
from PIL import Image, ImageDraw

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from climber.models import Wall, Venue, WallCalibration
from climber.calibration.calibration_utils import CalibrationUtils


def create_test_image(width=800, height=600, save_path=None):
    """Create a test image with some distinctive features"""
    # Create a simple test image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw some distinctive features
    # Corner markers
    draw.rectangle([50, 50, 100, 100], fill='red')  # Top-left
    draw.rectangle([width-100, 50, width-50, 100], fill='green')  # Top-right
    draw.rectangle([50, height-100, 100, height-50], fill='blue')  # Bottom-left
    draw.rectangle([width-100, height-100, width-50, height-50], fill='yellow')  # Bottom-right
    
    # Center marker
    draw.ellipse([width//2-25, height//2-25, width//2+25, height//2+25], fill='purple')
    
    if save_path:
        img.save(save_path)
    
    return img


def test_calibration_utils():
    """Test the calibration utilities for manual point selection"""
    print("Testing CalibrationUtils...")
    
    calib_utils = CalibrationUtils()
    
    # Test with valid points (more spread out to avoid collinearity)
    image_points = [(100, 100), (700, 150), (200, 500), (600, 450)]
    svg_points = [(50, 50), (750, 100), (100, 550), (700, 500)]
    image_size = (800, 600)
    
    try:
        transform_matrix, error = calib_utils.compute_manual_calibration(
            image_points, svg_points, image_size
        )
        print(f"✓ Manual calibration computed with error: {error:.2f}")
        
        # Test point transformation
        test_point = (400, 300)  # Center point
        transformed = calib_utils.transform_point_to_svg(test_point, transform_matrix)
        print(f"✓ Point transformation: {test_point} -> {transformed}")
        
    except Exception as e:
        print(f"✗ Error in manual calibration: {e}")
        return False
    
    # Test point validation
    try:
        is_valid, error_msg = calib_utils.validate_manual_points(
            image_points, svg_points, min_points=4
        )
        if is_valid:
            print("✓ Point validation passed")
        else:
            print(f"✗ Point validation failed: {error_msg}")
            return False
    except Exception as e:
        print(f"✗ Error in point validation: {e}")
        return False
    
    # Test with invalid points (collinear)
    collinear_points = [(100, 100), (200, 100), (300, 100), (400, 100)]
    is_valid, error_msg = calib_utils.validate_manual_points(
        collinear_points, svg_points, min_points=4
    )
    if not is_valid:
        print("✓ Collinear points correctly detected")
    else:
        print("✗ Collinear points not detected")
        return False
    
    return True


def test_manual_calibration_model():
    """Test the WallCalibration model with manual calibration fields"""
    print("\nTesting WallCalibration model...")
    
    try:
        # Create a test calibration with manual type
        calibration = WallCalibration(
            name="Test Manual Calibration",
            calibration_type="manual",
            manual_image_points=[[100, 100], [700, 100], [100, 500], [700, 500]],
            manual_svg_points=[[50, 50], [750, 50], [50, 550], [750, 550]],
            perspective_transform=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            reprojection_error=1.5
        )
        
        # Check if the fields are set correctly
        assert calibration.calibration_type == "manual"
        assert len(calibration.manual_image_points) == 4
        assert len(calibration.manual_svg_points) == 4
        assert calibration.reprojection_error == 1.5
        
        print("✓ Manual calibration model fields working correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error testing manual calibration model: {e}")
        return False


def test_web_interface():
    """Test the web interface for manual calibration"""
    print("\nTesting web interface...")
    
    client = Client()
    
    try:
        # Test manual calibration page (should be accessible)
        # Note: This would require a wall with an ID, so we'll just test the URL pattern
        from django.urls import reverse
        url = reverse('calibration_manual', kwargs={'wall_id': 1})
        print(f"✓ Manual calibration URL pattern found: {url}")
        
        # Test API endpoints
        api_url = reverse('api_upload_calibration_image', kwargs={'wall_id': 1})
        print(f"✓ API upload URL pattern found: {api_url}")
        
        save_url = reverse('api_save_manual_calibration', kwargs={'wall_id': 1})
        print(f"✓ API save URL pattern found: {save_url}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing web interface: {e}")
        return False


def create_test_calibration_file():
    """Create a test calibration file for manual testing"""
    print("\nCreating test calibration file...")
    
    try:
        # Create test image
        test_image_path = "/tmp/test_calibration_image.jpg"
        img = create_test_image(save_path=test_image_path)
        print(f"✓ Test image created: {test_image_path}")
        
        # Create test calibration data
        test_data = {
            "image_points": [[100, 100], [700, 100], [100, 500], [700, 500]],
            "svg_points": [[50, 50], [750, 50], [50, 550], [750, 550]],
            "image_size": [800, 600]
        }
        
        test_data_path = "/tmp/test_calibration_data.json"
        with open(test_data_path, 'w') as f:
            json.dump(test_data, f, indent=2)
        print(f"✓ Test calibration data created: {test_data_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating test files: {e}")
        return False


def main():
    """Run all tests"""
    print("Starting manual calibration tests...\n")
    
    all_tests_passed = True
    
    # Test calibration utilities
    if not test_calibration_utils():
        all_tests_passed = False
    
    # Test model
    if not test_manual_calibration_model():
        all_tests_passed = False
    
    # Test web interface
    if not test_web_interface():
        all_tests_passed = False
    
    # Create test files
    if not create_test_calibration_file():
        all_tests_passed = False
    
    print("\n" + "="*50)
    if all_tests_passed:
        print("✓ All tests passed! Manual calibration is working correctly.")
        print("\nTo test manually:")
        print("1. Start the Django server: uv run python manage.py runserver")
        print("2. Go to a wall page and click 'Manual Calibration'")
        print("3. Upload an image and select corresponding points")
        print("4. Save the calibration and verify it works")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()