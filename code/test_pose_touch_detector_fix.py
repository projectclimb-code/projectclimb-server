#!/usr/bin/env python3
"""
Test script to verify the pose_touch_detector AttributeError fix
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from climber.management.commands.pose_touch_detector import PoseTouchDetector
from climber.models import Wall

def test_pose_touch_detector_init():
    """Test that PoseTouchDetector can be initialized without AttributeError"""
    print("Testing PoseTouchDetector initialization...")
    
    # Get the first wall from the database
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No walls found in database. Creating a test wall...")
            # You might need to create a test wall here
            return False
        
        print(f"Using wall: {wall.name} (ID: {wall.id})")
        
        # Try to initialize the detector
        detector = PoseTouchDetector(
            wall_id=wall.id,
            fake_pose=True,  # Use fake pose to avoid camera issues
            debug=True
        )
        
        # Try to setup the detector
        if detector.setup():
            print("✓ PoseTouchDetector initialized and setup successfully!")
            detector.cleanup()
            return True
        else:
            print("✗ PoseTouchDetector setup failed")
            return False
            
    except Exception as e:
        print(f"✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pose_touch_detector_init()
    sys.exit(0 if success else 1)