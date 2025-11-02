#!/usr/bin/env python3
"""
Test script to verify web interface fixes
"""

import os
import sys
import django
from django.test import Client

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Disable Django's security checks for testing
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

django.setup()

from climber.models import Wall, WallCalibration


def test_calibration_detail_page():
    """Test if calibration detail page loads without JavaScript errors"""
    
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
        
    except Exception as e:
        print(f"Error loading wall/calibration: {e}")
        return False
    
    # Create a test client
    client = Client()
    
    # Get the calibration detail page
    try:
        url = f'/climber/calibration/{wall.id}/{calibration.id}/'
        response = client.get(url)
        
        if response.status_code != 200:
            print(f"Failed to load calibration detail page: {response.status_code}")
            return False
        
        # Check if the page contains our transformation controls
        content = response.content.decode('utf-8')
        
        # Check for key elements
        required_elements = [
            'id="svgOverlay"',
            'id="applyTransform"',
            'id="resetTransform"',
            'id="showTransform"',
            'window.calibrationTransform'
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in content:
                missing_elements.append(element)
        
        if missing_elements:
            print(f"Missing elements in page: {missing_elements}")
            return False
        
        print("✅ Calibration detail page loads correctly with all required elements")
        return True
        
    except Exception as e:
        print(f"Error testing calibration detail page: {e}")
        return False


def test_manual_calibration_page():
    """Test if manual calibration page loads without JavaScript errors"""
    
    # Get a wall
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No wall found in database")
            return False
            
        print(f"Testing manual calibration page with wall: {wall.name}")
        
    except Exception as e:
        print(f"Error loading wall: {e}")
        return False
    
    # Create a test client
    client = Client()
    
    # Get the manual calibration page
    try:
        url = f'/climber/calibration/manual_points/{wall.id}/'
        response = client.get(url)
        
        if response.status_code != 200:
            print(f"Failed to load manual calibration page: {response.status_code}")
            return False
        
        # Check if the page contains our calibration controls
        content = response.content.decode('utf-8')
        
        # Check for key elements
        required_elements = [
            'id="svgOverlay"',
            'id="fitBtn"',
            'id="resetTransform"',
            'applyAffineToOverlay',
            'applyHomographyToOverlay'
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in content:
                missing_elements.append(element)
        
        if missing_elements:
            print(f"Missing elements in manual calibration page: {missing_elements}")
            return False
        
        print("✅ Manual calibration page loads correctly with all required elements")
        return True
        
    except Exception as e:
        print(f"Error testing manual calibration page: {e}")
        return False


if __name__ == "__main__":
    print("Testing web interface fixes...")
    
    print("\n=== Testing Manual Calibration Page ===")
    manual_test = test_manual_calibration_page()
    
    print("\n=== Testing Calibration Detail Page ===")
    detail_test = test_calibration_detail_page()
    
    if manual_test and detail_test:
        print("\n✅ All web interface tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some web interface tests failed!")
        sys.exit(1)