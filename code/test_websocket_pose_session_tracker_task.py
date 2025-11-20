#!/usr/bin/env python3
"""
Test script for the WebSocket pose session tracker Celery task.

This script demonstrates how to use the websocket_pose_session_tracker_task
to run pose tracking as a background job.
"""

import os
import sys
import django
import json
from time import sleep

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from climber.tasks import websocket_pose_session_tracker_task


def test_websocket_pose_session_tracker_task():
    """Test the WebSocket pose session tracker Celery task"""
    
    # Example route data (same format as in the management command)
    route_data = {
        "grade": "V5",
        "author": "Test User",
        "problem": {
            "holds": [
                {"id": "17", "type": "start"},
                {"id": "91", "type": "start"},
                {"id": "6", "type": "normal"},
                {"id": "101", "type": "normal"},
                {"id": "55", "type": "normal"},
                {"id": "133", "type": "normal"},
                {"id": "89", "type": "normal"},
                {"id": "41", "type": "normal"},
                {"id": "72", "type": "finish"},
                {"id": "11", "type": "finish"}
            ]
        }
    }
    
    # Convert route data to JSON string for the task
    route_data_json = json.dumps(route_data)
    
    print("Starting WebSocket pose session tracker Celery task...")
    
    # Start the task with default values (can be overridden if needed)
    task = websocket_pose_session_tracker_task.delay(
        # Using default values: wall_id=1, input_websocket_url="http://192.168.11.2:8011/ws/pose/"
        # output_websocket_url="http://192.168.11.2:8011/ws/holds/", proximity_threshold=300.0
        # touch_duration=0.5, reconnect_delay=0.5, route_id=99
        debug=True,  # Enable debug output
        route_data=route_data_json  # Override route_id with explicit route data
    )
    
    print(f"Task started with ID: {task.id}")
    
    # Monitor task progress
    while not task.ready():
        result = task.result
        if result:
            if hasattr(result, 'state'):
                print(f"Task state: {result.state}")
                if hasattr(result, 'info') and result.info:
                    print(f"Task info: {result.info}")
        
        sleep(2)
    
    # Get final result
    final_result = task.get()
    print(f"Task completed with result: {final_result}")
    
    return final_result


if __name__ == "__main__":
    print("Testing WebSocket pose session tracker Celery task...")
    print("Make sure Celery worker is running: celery -A code worker -l info")
    print()
    
    try:
        result = test_websocket_pose_session_tracker_task()
        print("Test completed successfully!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        sys.exit(1)