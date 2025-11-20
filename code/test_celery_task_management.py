#!/usr/bin/env python
"""
Test script for Celery task management functionality
"""
import os
import sys
import django
import json
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.tasks import websocket_pose_session_tracker_task, stop_session_tracker_task, get_running_session_trackers
from climber.models import Wall, Route

def test_task_management():
    """Test starting, listing, and stopping tasks"""
    print("Testing Celery Task Management")
    print("=" * 50)
    
    # Get a wall for testing
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No walls found in database. Please create a wall first.")
            return
        
        print(f"Using wall: {wall.name} (ID: {wall.id})")
    except Exception as e:
        print(f"Error getting wall: {e}")
        return
    
    # Test 1: Get initial running tasks
    print("\n1. Getting initial running tasks...")
    running_tasks = get_running_session_trackers()
    print(f"Initial running tasks: {len(running_tasks)}")
    for task in running_tasks:
        print(f"  - Task ID: {task['task_id']}, Status: {task['status']}")
    
    # Test 2: Start a new task
    print("\n2. Starting a new session tracker task...")
    try:
        task = websocket_pose_session_tracker_task.delay(
            wall_id=wall.id,
            input_websocket_url="ws://localhost:8080/pose",  # Dummy URL for testing
            output_websocket_url="ws://localhost:8081/session",  # Dummy URL for testing
            debug=True
        )
        print(f"Task started with ID: {task.id}")
        
        # Wait a moment for task to initialize
        time.sleep(2)
        
        # Test 3: Check running tasks again
        print("\n3. Checking running tasks after starting new task...")
        running_tasks = get_running_session_trackers()
        print(f"Running tasks after start: {len(running_tasks)}")
        for task in running_tasks:
            print(f"  - Task ID: {task['task_id']}, Status: {task['status']}, Wall: {task['wall_id']}")
        
        # Test 4: Stop the task
        print("\n4. Stopping the task...")
        result = stop_session_tracker_task(task.id)
        print(f"Stop result: {result}")
        
        # Wait a moment for task to stop
        time.sleep(2)
        
        # Test 5: Check running tasks after stopping
        print("\n5. Checking running tasks after stopping...")
        running_tasks = get_running_session_trackers()
        print(f"Running tasks after stop: {len(running_tasks)}")
        for task in running_tasks:
            print(f"  - Task ID: {task['task_id']}, Status: {task['status']}")
        
    except Exception as e:
        print(f"Error in task management test: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_task_management()