#!/usr/bin/env python3
"""
Test script for the task management interface
"""

import requests
import json

# Base URL for the Django server
BASE_URL = "http://localhost:8000"

def test_running_tasks_endpoint():
    """Test the running tasks endpoint"""
    print("Testing running tasks endpoint...")
    response = requests.get(f"{BASE_URL}/api/running-tasks/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_task_management_page():
    """Test the task management page"""
    print("Testing task management page...")
    response = requests.get(f"{BASE_URL}/tasks/")
    print(f"Status: {response.status_code}")
    print(f"Page loaded successfully: {response.status_code == 200}")
    print()

def test_start_session_endpoint():
    """Test the start session endpoint"""
    print("Testing start session endpoint...")
    params = {
        'input_websocket_url': 'ws://localhost:8000/ws/pose/',
        'output_websocket_url': 'ws://localhost:8000/ws/session/',
        'proximity_threshold': 50.0,
        'touch_duration': 2.0,
        'reconnect_delay': 5.0,
        'debug': 'false',
        'no_stream_landmarks': 'false',
        'stream_svg_only': 'false'
    }
    
    # First, let's get a list of routes to use a valid route_id
    routes_response = requests.get(f"{BASE_URL}/api/routes/")
    if routes_response.status_code == 200:
        routes = routes_response.json()
        if routes:
            route_id = routes[0]['id']
            print(f"Using route_id: {route_id}")
            
            response = requests.get(f"{BASE_URL}/api/start_session/{route_id}/", params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        else:
            print("No routes found in the database")
    else:
        print(f"Failed to get routes: {routes_response.status_code}")
    print()

if __name__ == "__main__":
    print("Task Management Interface Test")
    print("=" * 40)
    
    test_running_tasks_endpoint()
    test_task_management_page()
    test_start_session_endpoint()
    
    print("Test completed!")