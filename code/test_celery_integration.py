#!/usr/bin/env python3
"""
Test script to verify Celery task integration for WebSocket pose session tracker.
This script tests the API endpoints and task functionality.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django
django.setup()

from climber.models import Wall, Route
from climber.tasks import websocket_pose_session_tracker_task, stop_session_tracker_task, get_running_session_trackers


def test_api_endpoints():
    """Test the API endpoints for starting/stopping sessions"""
    base_url = "http://localhost:8000"
    
    print("Testing API endpoints...")
    
    # Test getting running tasks
    try:
        response = requests.get(f"{base_url}/api/running-tasks/")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/running-tasks/ - Status: {response.status_code}")
            print(f"  Response: {json.dumps(data, indent=2)}")
        else:
            print(f"✗ GET /api/running-tasks/ - Status: {response.status_code}")
    except Exception as e:
        print(f"✗ Error testing running tasks endpoint: {e}")
    
    # Get first route for testing
    try:
        route = Route.objects.first()
        if not route:
            print("✗ No routes found in database. Please create a route first.")
            return False
        
        print(f"\nUsing route: {route.name} (ID: {route.id})")
        
        # Test starting a session
        start_url = f"{base_url}/api/start_session/{route.id}/"
        params = {
            'input_websocket_url': 'ws://localhost:8001/ws/pose/',
            'output_websocket_url': 'ws://localhost:8002/ws/session/',
            'proximity_threshold': 50.0,
            'touch_duration': 2.0,
            'debug': 'true'
        }
        
        response = requests.get(start_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                task_id = data.get('task_id')
                print(f"✓ GET /api/start_session/{route.id}/ - Task started")
                print(f"  Task ID: {task_id}")
                
                # Wait a moment then test stopping
                time.sleep(2)
                
                # Test stopping the session
                stop_url = f"{base_url}/api/start_stop/?task_id={task_id}"
                response = requests.get(stop_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        print(f"✓ GET /api/start_stop/ - Task stopped")
                        return True
                    else:
                        print(f"✗ Error stopping task: {data.get('error')}")
                else:
                    print(f"✗ GET /api/start_stop/ - Status: {response.status_code}")
            else:
                print(f"✗ Error starting task: {data.get('error')}")
        else:
            print(f"✗ GET /api/start_session/{route.id}/ - Status: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error testing session endpoints: {e}")
    
    return False


def test_direct_task_functions():
    """Test the task functions directly"""
    print("\nTesting direct task functions...")
    
    # Get first wall and route
    wall = Wall.objects.first()
    route = Route.objects.first()
    
    if not wall or not route:
        print("✗ No wall or route found in database")
        return False
    
    print(f"Using wall: {wall.name} (ID: {wall.id})")
    print(f"Using route: {route.name} (ID: {route.id})")
    
    try:
        # Test getting running trackers
        result = get_running_session_trackers()
        print(f"✓ get_running_session_trackers() - Status: {result.get('status')}")
        print(f"  Trackers: {len(result.get('trackers', {}))}")
        
        # Note: We won't actually start a task here as it requires WebSocket connections
        # But we can verify the task function exists and can be called
        print("✓ websocket_pose_session_tracker_task function is available")
        print("✓ stop_session_tracker_task function is available")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing task functions: {e}")
        return False


def test_database_models():
    """Test that required database models exist"""
    print("\nTesting database models...")
    
    try:
        wall_count = Wall.objects.count()
        route_count = Route.objects.count()
        
        print(f"✓ Wall model - {wall_count} walls found")
        print(f"✓ Route model - {route_count} routes found")
        
        if wall_count == 0:
            print("  Warning: No walls in database. Create at least one wall with calibration.")
        
        if route_count == 0:
            print("  Warning: No routes in database. Create at least one route.")
        
        return wall_count > 0 and route_count > 0
        
    except Exception as e:
        print(f"✗ Error testing models: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Celery Task Integration Test")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Run tests
    models_ok = test_database_models()
    functions_ok = test_direct_task_functions()
    
    # Only test API endpoints if server is running
    try:
        response = requests.get("http://localhost:8000", timeout=2)
        if response.status_code == 200:
            api_ok = test_api_endpoints()
        else:
            print("\nSkipping API tests - server returned non-200 status")
            api_ok = False
    except:
        print("\nSkipping API tests - server not running or not accessible")
        api_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Database Models: {'✓ PASS' if models_ok else '✗ FAIL'}")
    print(f"Task Functions: {'✓ PASS' if functions_ok else '✗ FAIL'}")
    print(f"API Endpoints: {'✓ PASS' if api_ok else '✗ SKIP/FAIL'}")
    
    if models_ok and functions_ok:
        print("\n✓ Core functionality is working!")
        print("To complete testing:")
        print("1. Start Django server: uv run python manage.py runserver")
        print("2. Start Celery worker: uv run celery -A app worker -l info")
        print("3. Access task management: http://localhost:8000/tasks/")
        return True
    else:
        print("\n✗ Some tests failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)