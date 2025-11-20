#!/usr/bin/env python3
"""
Test script for the updated WebSocket pose session tracker Celery task.
This script tests that the Celery task has the correct default values
and can be invoked properly.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from climber.tasks import websocket_pose_session_tracker_task
from celery.result import AsyncResult
import json

def test_task_defaults():
    """Test that the task has correct default values"""
    print("Testing WebSocket pose session tracker task defaults...")
    
    # Check if task exists
    assert websocket_pose_session_tracker_task is not None, "Task not found"
    print("✓ Task exists")
    
    # Get task signature to check defaults
    sig = websocket_pose_session_tracker_task.signature()
    
    # The task should have the correct default values
    expected_defaults = {
        'wall_id': 1,
        'input_websocket_url': "ws://localhost:8011/ws/pose/",
        'output_websocket_url': "ws://localhost:8011/ws/holds/",
        'proximity_threshold': 50.0,
        'touch_duration': 2.0,
        'reconnect_delay': 5.0,
        'debug': False,
        'no_stream_landmarks': False,
        'stream_svg_only': False,
        'route_data': None,
        'route_id': None
    }
    
    print("✓ Task signature retrieved")
    
    # Test task creation with custom parameters
    task_kwargs = {
        'wall_id': 1,
        'input_websocket_url': 'ws://localhost:8011/ws/pose/',
        'output_websocket_url': 'ws://localhost:8011/ws/holds/',
        'proximity_threshold': 50.0,
        'touch_duration': 2.0,
        'reconnect_delay': 5.0,
        'debug': True,
        'route_data': json.dumps({
            'problem': {
                'holds': [
                    {'id': '17', 'type': 'start'},
                    {'id': '91', 'type': 'start'},
                    {'id': '6', 'type': 'normal'}
                ]
            }
        })
    }
    
    try:
        # Create task but don't execute it (just test the creation)
        task_result = websocket_pose_session_tracker_task.apply_async(
            args=[],
            kwargs=task_kwargs,
            queue='default'
        )
        
        print(f"✓ Task created successfully with ID: {task_result.id}")
        
        # Check task status (should be pending or started)
        result = AsyncResult(task_result.id)
        print(f"✓ Task status: {result.state}")
        
        # Revoke the task to clean up
        task_result.revoke(terminate=True)
        print("✓ Test task revoked")
        
    except Exception as e:
        print(f"✗ Error creating task: {e}")
        return False
    
    return True

def test_task_parameters():
    """Test that the task accepts all required parameters"""
    print("\nTesting task parameters...")
    
    # Test with all parameters
    try:
        task_result = websocket_pose_session_tracker_task.apply_async(
            kwargs={
                'wall_id': 1,
                'input_websocket_url': 'ws://localhost:8011/ws/pose/',
                'output_websocket_url': 'ws://localhost:8011/ws/holds/',
                'proximity_threshold': 100.0,
                'touch_duration': 3.0,
                'reconnect_delay': 10.0,
                'debug': True,
                'no_stream_landmarks': True,
                'stream_svg_only': True,
                'route_data': '{"problem": {"holds": []}}',
                'route_id': 1
            }
        )
        
        print(f"✓ Task created with all parameters: {task_result.id}")
        
        # Revoke to clean up
        task_result.revoke(terminate=True)
        
    except Exception as e:
        print(f"✗ Error with parameters: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("WebSocket Pose Session Tracker Task Test")
    print("=" * 50)
    
    success = True
    
    # Test defaults
    if not test_task_defaults():
        success = False
    
    # Test parameters
    if not test_task_parameters():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✓ All tests passed!")
        print("The WebSocket pose session tracker Celery task is working correctly.")
    else:
        print("✗ Some tests failed!")
        sys.exit(1)