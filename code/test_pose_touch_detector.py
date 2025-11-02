#!/usr/bin/env python3
"""
Test script for the pose touch detector management command.
This script tests the integration with fake pose streamer.
"""

import os
import sys
import django
import subprocess
import time
import threading
import json
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
django.setup()

from climber.models import Wall, WallCalibration, Session
from django.contrib.auth.models import User


def setup_test_data():
    """Setup test data for the pose touch detector."""
    print("Setting up test data...")
    
    # Create test user if not exists
    user, created = User.objects.get_or_create(
        username='test_user',
        defaults={'email': 'test@example.com'}
    )
    if created:
        print(f"Created test user: {user.username}")
    
    # Create test wall if not exists
    wall, created = Wall.objects.get_or_create(
        name='Test Wall',
        defaults={
            'venue': None,  # Will be set later
            'height_mm': 3000,
            'width_mm': 4000,
            'svg_file': 'data/stena_export.svg'
        }
    )
    if created:
        print(f"Created test wall: {wall.name}")
    
    # Create test calibration if not exists
    import numpy as np
    calibration, created = WallCalibration.objects.get_or_create(
        wall=wall,
        name='Test Calibration',
        defaults={
            'camera_matrix': json.dumps({
                'fx': 1000.0, 'fy': 1000.0, 'cx': 640.0, 'cy': 360.0
            }),
            'distortion_coefficients': json.dumps([0.0, 0.0, 0.0, 0.0, 0.0]),
            'perspective_transform': json.dumps(
                np.eye(3).tolist()
            )
        }
    )
    if created:
        print(f"Created test calibration: {calibration.name}")
    
    # Create test session if not exists
    session, created = Session.objects.get_or_create(
        name='Test Session',
        defaults={
            'wall': wall,
            'user': user,
            'status': 'active'
        }
    )
    if created:
        print(f"Created test session: {session.name}")
    
    return wall, session


def run_pose_touch_detector(wall_id, session_id):
    """Run the pose touch detector management command."""
    print(f"Starting pose touch detector for wall {wall_id}, session {session_id}")
    
    cmd = [
        'uv', 'run', 'python', 'manage.py', 'pose_touch_detector',
        '--wall-id', str(wall_id),
        '--session-id', str(session_id),
        '--fake-pose',
        '--debug'
    ]
    
    # Run the command
    process = subprocess.Popen(
        cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Print output in real-time
    def print_output():
        for line in process.stdout:
            print(f"[PoseDetector] {line.strip()}")
    
    output_thread = threading.Thread(target=print_output)
    output_thread.daemon = True
    output_thread.start()
    
    return process


def main():
    """Main test function."""
    print("Testing Pose Touch Detector")
    print("=" * 50)
    
    # Setup test data
    wall, session = setup_test_data()
    
    print(f"Test setup complete:")
    print(f"  Wall: {wall.name} (ID: {wall.id})")
    print(f"  Session: {session.name} (ID: session_{session.uuid})")
    print(f"  SVG File: {wall.svg_file}")
    print()
    
    # Check if SVG file exists
    svg_path = os.path.join('media', wall.svg_file.name if wall.svg_file else '')
    if not os.path.exists(svg_path):
        print(f"Warning: SVG file not found at {svg_path}")
        print("The pose touch detector will fail without an SVG file.")
        print()
    
    print("Starting pose touch detector with fake pose streamer...")
    print("Press Ctrl+C to stop the test")
    print()
    
    try:
        # Run the pose touch detector
        process = run_pose_touch_detector(wall.id, session.uuid)
        
        # Wait for interruption
        while process.poll() is None:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nStopping test...")
        if 'process' in locals():
            process.terminate()
            process.wait()
        print("Test stopped")
    
    print("Test complete")


if __name__ == "__main__":
    main()