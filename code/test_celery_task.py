#!/usr/bin/env python
"""
Test script to check if Celery task can be started
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from climber.tasks import websocket_pose_session_tracker_task

def test_task():
    """Test if Celery task can be created"""
    try:
        # Create a task with test parameters
        task = websocket_pose_session_tracker_task.delay(
            wall_id=1,  # Assuming wall with ID 1 exists
            input_websocket_url='ws://localhost:8001/ws/pose/',
            output_websocket_url='ws://localhost:8002/ws/session/',
            proximity_threshold=50.0,
            touch_duration=2.0,
            reconnect_delay=5.0,
            debug=True,
            no_stream_landmarks=False,
            stream_svg_only=False,
            route_data=None,
            route_id=1  # Assuming route with ID 1 exists
        )
        
        print(f"Task created successfully with ID: {task.id}")
        print(f"Task status: {task.status}")
        return True
    except Exception as e:
        print(f"Error creating task: {e}")
        return False

if __name__ == "__main__":
    success = test_task()
    if success:
        print("SUCCESS: Celery task can be created")
    else:
        print("FAILED: Could not create Celery task")
        sys.exit(1)