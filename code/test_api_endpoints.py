#!/usr/bin/env python3
"""
Test script for the new API endpoints:
1. /api/tasks/start-default/ - Start task with default values
2. /api/tasks/kill-all/ - Kill all running tasks
"""

import os
import sys
import django
import json
import requests
import time
from datetime import datetime

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth.models import User
from climber.models import Wall, CeleryTask

# Configuration
BASE_URL = 'http://localhost:8000'
API_BASE = f'{BASE_URL}/api'

def test_start_default_task():
    """Test the start_default_task endpoint"""
    print("\n=== Testing Start Default Task Endpoint ===")
    
    try:
        # Get a route ID for testing
        from climber.models import Route
        test_route = Route.objects.first()
        if not test_route:
            print("❌ No routes found. Please create a route first.")
            return None
        
        # Test with minimal required parameters
        response = requests.post(f'{API_BASE}/tasks/start-default/', json={'route_id': test_route.id})
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print(f"✅ Task started successfully with ID: {data.get('task_id')}")
                print(f"📋 Parameters used: {json.dumps(data.get('parameters'), indent=2)}")
                return data.get('task_id')
            else:
                print(f"❌ Error: {data.get('message')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    return None

def test_start_default_task_with_params():
    """Test the start_default_task endpoint with custom parameters"""
    print("\n=== Testing Start Default Task with Custom Parameters ===")
    
    try:
        # Get a route ID for testing
        from climber.models import Route
        test_route = Route.objects.first()
        if not test_route:
            print("❌ No routes found. Please create a route first.")
            return None
        
        # Test with custom parameters
        custom_params = {
            'route_id': test_route.id,
            'debug': True,
            'proximity_threshold': 30.0,
            'touch_duration': 1.5
        }
        
        response = requests.post(f'{API_BASE}/tasks/start-default/', json=custom_params)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print(f"✅ Task started successfully with ID: {data.get('task_id')}")
                print(f"📋 Parameters used: {json.dumps(data.get('parameters'), indent=2)}")
                return data.get('task_id')
            else:
                print(f"❌ Error: {data.get('message')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    return None

def test_get_running_tasks():
    """Test getting running tasks before and after starting"""
    print("\n=== Testing Get Running Tasks ===")
    
    try:
        response = requests.get(f'{API_BASE}/tasks/running/')
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            tasks = data.get('tasks', [])
            print(f"📊 Currently running tasks: {len(tasks)}")
            
            for task in tasks:
                print(f"  - Task ID: {task.get('task_id')}")
                print(f"    Name: {task.get('task_name')}")
                print(f"    Status: {task.get('status')}")
                print(f"    Started: {task.get('start_time')}")
                if task.get('elapsed_time'):
                    print(f"    Elapsed: {task.get('elapsed_time'):.2f}s")
                print()
            
            return tasks
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    return []

def test_kill_all_tasks():
    """Test the kill_all_tasks endpoint"""
    print("\n=== Testing Kill All Tasks Endpoint ===")
    
    try:
        response = requests.post(f'{API_BASE}/tasks/kill-all/')
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                killed_count = data.get('killed_count', 0)
                print(f"✅ Successfully killed {killed_count} tasks")
                
                errors = data.get('errors')
                if errors:
                    print(f"⚠️  Errors encountered:")
                    for error in errors:
                        print(f"    - {error}")
            else:
                print(f"❌ Error: {data.get('message')}")
        elif response.status_code == 404:
            print("ℹ️  No running tasks found to kill")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

def test_endpoint_without_walls():
    """Test start_default_task when no walls exist"""
    print("\n=== Testing Start Task Without Walls ===")
    
    # Temporarily delete all walls
    original_walls = list(Wall.objects.all())
    Wall.objects.all().delete()
    
    try:
        # Get a route ID for testing
        from climber.models import Route
        test_route = Route.objects.first()
        if not test_route:
            print("❌ No routes found. Skipping this test.")
            # Restore walls and return
            for wall in original_walls:
                wall.pk = None
                wall.save()
            return
        
        response = requests.post(f'{API_BASE}/tasks/start-default/', json={'route_id': test_route.id})
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 400:
            data = response.json()
            if 'No walls available' in data.get('message', ''):
                print("✅ Correctly handled case with no walls")
            else:
                print(f"❌ Unexpected error message: {data.get('message')}")
        else:
            print(f"❌ Expected 400 error, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    # Restore walls
    for wall in original_walls:
        wall.pk = None  # Create new copy
        wall.save()


def test_endpoint_without_route_id():
    """Test start_default_task without route_id parameter"""
    print("\n=== Testing Start Task Without Route ID ===")
    
    try:
        response = requests.post(f'{API_BASE}/tasks/start-default/', json={})
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 400:
            data = response.json()
            if 'route_id is required' in data.get('message', ''):
                print("✅ Correctly required route_id parameter")
            else:
                print(f"❌ Unexpected error message: {data.get('message')}")
        else:
            print(f"❌ Expected 400 error, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

def main():
    """Main test function"""
    print("🚀 Starting API Endpoint Tests")
    print(f"📍 Target URL: {BASE_URL}")
    
    # Check if server is running
    try:
        response = requests.get(f'{BASE_URL}/', timeout=5)
        if response.status_code != 200:
            print("❌ Server is not responding correctly")
            return
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server. Make sure Django development server is running.")
        print("   Run: uv run python manage.py runserver")
        return
    
    print("✅ Server is running\n")
    
    # Test 1: Get initial running tasks
    initial_tasks = test_get_running_tasks()
    
    # Test 2: Start task with defaults
    task_id_1 = test_start_default_task()
    
    # Test 3: Start task with custom parameters
    task_id_2 = test_start_default_task_with_params()
    
    # Wait a moment for tasks to register
    print("\n⏳ Waiting 2 seconds for tasks to register...")
    time.sleep(2)
    
    # Test 4: Check running tasks after starting
    print("\n📊 Checking running tasks after starting new ones:")
    running_tasks = test_get_running_tasks()
    
    # Test 5: Kill all tasks
    test_kill_all_tasks()
    
    # Wait a moment for tasks to be killed
    print("\n⏳ Waiting 2 seconds for tasks to be killed...")
    time.sleep(2)
    
    # Test 6: Check running tasks after killing
    print("\n📊 Checking running tasks after killing all:")
    final_tasks = test_get_running_tasks()
    
    # Test 7: Test edge case with no walls
    test_endpoint_without_walls()
    
    # Test 8: Test missing route_id parameter
    test_endpoint_without_route_id()
    
    # Summary
    print("\n" + "="*50)
    print("📋 TEST SUMMARY")
    print("="*50)
    print(f"Initial running tasks: {len(initial_tasks)}")
    print(f"Tasks started: 2 (default + custom params)")
    print(f"Running tasks after start: {len(running_tasks)}")
    print(f"Running tasks after kill: {len(final_tasks)}")
    
    if len(running_tasks) >= 2 and len(final_tasks) == 0:
        print("✅ All tests passed! API endpoints are working correctly.")
    else:
        print("⚠️  Some tests may have failed. Check the output above.")

if __name__ == '__main__':
    main()