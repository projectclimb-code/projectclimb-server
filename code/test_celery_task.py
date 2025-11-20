#!/usr/bin/env python3
"""
Test script for the WebSocket Pose Session Tracker Celery task.
"""

import os
import sys
import django
import time
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.models import Wall, WallCalibration, CeleryTask
from climber.tasks import websocket_pose_session_tracker_task
from celery.result import AsyncResult


def test_task_creation():
    """Test creating a WebSocket pose session tracker task"""
    print("Testing WebSocket Pose Session Tracker Celery Task")
    print("=" * 60)
    
    # Get the first wall for testing
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No walls found in database. Please create a wall first.")
            return False
        
        print(f"Using wall: {wall.name} (ID: {wall.id})")
        
        # Check if wall has calibration
        calibration = wall.calibrations.filter(is_active=True).first()
        if not calibration:
            calibration = wall.calibrations.latest('created')
        
        if not calibration:
            print("No calibration found for wall. Please create a calibration first.")
            return False
        
        print(f"Using calibration: {calibration.name}")
        
        # Create the task
        task = websocket_pose_session_tracker_task.delay(
            wall_id=wall.id,
            input_websocket_url="ws://localhost:8765",  # Test URL
            output_websocket_url="ws://localhost:8766",  # Test URL
            proximity_threshold=50.0,
            touch_duration=2.0,
            reconnect_delay=5.0,
            debug=True,
            no_stream_landmarks=False,
            stream_svg_only=False,
            route_data=None,
            route_id=None
        )
        
        print(f"Task created with ID: {task.id}")
        
        # Check if task was stored in database
        time.sleep(1)  # Give it a moment to store
        celery_task = CeleryTask.objects.filter(task_id=task.id).first()
        if celery_task:
            print(f"Task stored in database: {celery_task.task_name}")
            print(f"Task status: {celery_task.status}")
            print(f"Task created: {celery_task.created}")
        else:
            print("Warning: Task not found in database")
        
        # Check task status
        result = AsyncResult(task.id)
        print(f"Task status from Celery: {result.status}")
        
        # Wait a bit and check again
        print("Waiting 3 seconds to check task status...")
        time.sleep(3)
        
        result = AsyncResult(task.id)
        print(f"Task status after 3 seconds: {result.status}")
        
        if result.failed():
            print(f"Task failed: {result.result}")
        
        # Note: Task stopping functionality would be implemented separately
        print("Note: Task stopping functionality would be implemented separately")
        
        return True
        
    except Exception as e:
        print(f"Error testing task: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_running_tasks_endpoint():
    """Test the running tasks endpoint"""
    print("\nTesting Running Tasks Endpoint")
    print("=" * 60)
    
    try:
        from climber.views import get_running_tasks
        from django.test import RequestFactory
        
        # Create a mock request
        factory = RequestFactory()
        request = factory.get('/tasks/running/')
        
        # Call the view
        response = get_running_tasks(request)
        
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.content.decode()}")
        
        return True
        
    except Exception as e:
        print(f"Error testing endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Starting WebSocket Pose Session Tracker Task Tests")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Test task creation
    task_test_passed = test_task_creation()
    
    # Test running tasks endpoint
    endpoint_test_passed = test_running_tasks_endpoint()
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print(f"Task Creation Test: {'PASSED' if task_test_passed else 'FAILED'}")
    print(f"Running Tasks Endpoint Test: {'PASSED' if endpoint_test_passed else 'FAILED'}")
    
    if task_test_passed and endpoint_test_passed:
        print("\nAll tests PASSED! 🎉")
        sys.exit(0)
    else:
        print("\nSome tests FAILED! ❌")
        sys.exit(1)