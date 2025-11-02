#!/usr/bin/env python3
"""
Test script to verify the complete pose_touch_detector functionality
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from climber.management.commands.pose_touch_detector import PoseTouchDetector
from climber.models import Wall, WallCalibration

def test_pose_touch_detector():
    """Test that PoseTouchDetector works without errors"""
    print("Testing PoseTouchDetector with all fixes...")
    
    # Get the first wall from the database
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No walls found in database. Please create a wall first.")
            return False
        
        print(f"Using wall: {wall.name} (ID: {wall.id})")
        
        # Check if wall has calibration
        try:
            calibration = WallCalibration.objects.filter(wall=wall).latest('created')
            print(f"Using calibration: {calibration.name}")
        except WallCalibration.DoesNotExist:
            print("No calibration found for this wall. Please create a calibration first.")
            return False
        
        # Test with fake pose
        print("\n1. Testing with fake pose...")
        detector = PoseTouchDetector(
            wall_id=wall.id,
            fake_pose=True,
            debug=True
        )
        
        if detector.setup():
            print("✓ Setup successful with fake pose")
            detector.cleanup()
        else:
            print("✗ Setup failed with fake pose")
            return False
        
        # Test with video file if it exists
        video_file = "data/bolder2.mov"
        if os.path.exists(video_file):
            print(f"\n2. Testing with video file: {video_file}")
            detector = PoseTouchDetector(
                wall_id=wall.id,
                video_file=video_file,
                debug=True
            )
            
            if detector.setup():
                print("✓ Setup successful with video file")
                detector.cleanup()
            else:
                print("✗ Setup failed with video file")
                return False
        else:
            print(f"\n2. Skipping video file test (file not found: {video_file})")
        
        print("\n✓ All tests passed!")
        return True
            
    except Exception as e:
        print(f"✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pose_touch_detector()
    sys.exit(0 if success else 1)