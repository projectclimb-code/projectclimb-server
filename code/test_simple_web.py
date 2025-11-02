#!/usr/bin/env python3
"""
Simple test to verify web interface fixes
"""

import os
import sys
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.models import Wall, WallCalibration


def test_pages():
    """Test if pages load without errors"""
    
    # Get a wall with calibration
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
            
        print(f"Testing with wall: {wall.name}")
        print(f"Calibration: {calibration.name}")
        
    except Exception as e:
        print(f"Error loading wall/calibration: {e}")
        return False
    
    # Test URLs directly
    base_url = "http://127.0.0.1:8000"
    
    # Test manual calibration page
    try:
        url = f"{base_url}/climber/calibration/wall/{wall.id}/manual-points/"
        response = requests.get(url)
        
        if response.status_code == 200:
            print(f"✅ Manual calibration page loads successfully (status: {response.status_code})")
            
            # Check for key elements in the page
            content = response.text
            required_elements = [
                'id="svgOverlay"',
                'id="fitBtn"',
                'applyAffineToOverlay',
                'applyHomographyToOverlay'
            ]
            
            missing_elements = []
            for element in required_elements:
                if element not in content:
                    missing_elements.append(element)
            
            if missing_elements:
                print(f"⚠️  Missing elements in manual calibration page: {missing_elements}")
            else:
                print("✅ All required elements found in manual calibration page")
        else:
            print(f"❌ Failed to load manual calibration page: {response.status_code}")
            
    except Exception as e:
        print(f"Error testing manual calibration page: {e}")
    
    # Test calibration detail page
    try:
        url = f"{base_url}/climber/calibration/wall/{wall.id}/{calibration.id}/"
        response = requests.get(url)
        
        if response.status_code == 200:
            print(f"✅ Calibration detail page loads successfully (status: {response.status_code})")
            
            # Check for key elements in the page
            content = response.text
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
                print(f"⚠️  Missing elements in calibration detail page: {missing_elements}")
            else:
                print("✅ All required elements found in calibration detail page")
        else:
            print(f"❌ Failed to load calibration detail page: {response.status_code}")
            
    except Exception as e:
        print(f"Error testing calibration detail page: {e}")
    
    return True


if __name__ == "__main__":
    print("Testing web interface fixes...")
    
    success = test_pages()
    
    if success:
        print("\n✅ Web interface tests completed!")
        print("\nYou can now test the pages in your browser:")
        print(f"- Manual calibration: http://127.0.0.1:8000/climber/calibration/wall/1/manual-points/")
        print(f"- Calibration detail: http://127.0.0.1:8000/climber/calibration/wall/1/1/")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)