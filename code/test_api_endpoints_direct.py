#!/usr/bin/env python3
"""
Direct test script for new API endpoints without requiring server:
1. start_default_task function
2. kill_all_tasks function
"""

import os
import sys
import django
import json
from unittest.mock import Mock, MagicMock

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth.models import User
from climber.models import Wall, Route, CeleryTask, Venue
from climber.views import start_default_task, kill_all_tasks
from rest_framework.test import APIRequestFactory

def test_start_default_task_direct():
    """Test start_default_task function directly"""
    print("\n=== Testing Start Default Task Function Directly ===")
    
    try:
        # Create test data with venue (required for Wall)
        test_venue = Venue.objects.create(name="Test Venue")
        test_wall = Wall.objects.create(name="Test Wall", venue=test_venue)
        test_route = Route.objects.create(name="Test Route")
        
        # Create mock request
        factory = APIRequestFactory()
        request = factory.post(
            '/api/tasks/start-default/',
            data={'route_id': test_route.id},
            format='json'
        )
        
        # Mock websocket_pose_session_tracker_task.delay to avoid actually starting a task
        with Mock() as mock_task:
            mock_task.id = 'test-task-id-123'
            mock_task.return_value = mock_task
            
            # Import and patch the task
            from climber import views
            original_task = views.websocket_pose_session_tracker_task
            views.websocket_pose_session_tracker_task = mock_task
            
            try:
                # Call function
                response = start_default_task(request)
                
                print(f"Response Status: {response.status_code}")
                # Parse JSON from JsonResponse
                response_data = json.loads(response.content)
                print(f"Response Data: {response_data}")
                
                if response.status_code == 200:
                    data = response_data
                    if data.get('status') == 'success':
                        print(f"✅ Task would be started with ID: {data.get('task_id')}")
                        print(f"📋 Parameters used: {json.dumps(data.get('parameters'), indent=2)}")
                        return True
                    else:
                        print(f"❌ Error: {data.get('message')}")
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
            finally:
                # Restore original task
                views.websocket_pose_session_tracker_task = original_task
                
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    
    return False

def test_start_default_task_without_route():
    """Test start_default_task without route_id parameter"""
    print("\n=== Testing Start Task Without Route ID (Direct) ===")
    
    try:
        # Create test data with venue (required for Wall)
        test_venue = Venue.objects.create(name="Test Venue 2")
        test_wall = Wall.objects.create(name="Test Wall 2", venue=test_venue)
        
        # Create mock request without route_id
        factory = APIRequestFactory()
        request = factory.post(
            '/api/tasks/start-default/',
            data={},
            format='json'
        )
        
        # Call the function
        response = start_default_task(request)
        
        print(f"Response Status: {response.status_code}")
        # Parse JSON from JsonResponse
        response_data = json.loads(response.content)
        print(f"Response Data: {response_data}")
        
        if response.status_code == 400:
            data = response_data
            if 'route_id is required' in data.get('message', ''):
                print("✅ Correctly required route_id parameter")
                return True
            else:
                print(f"❌ Unexpected error message: {data.get('message')}")
        else:
            print(f"❌ Expected 400 error, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    
    return False

def test_start_default_task_without_walls():
    """Test start_default_task when no walls exist"""
    print("\n=== Testing Start Task Without Walls (Direct) ===")
    
    try:
        # Create test data
        test_route = Route.objects.create(name="Test Route 2")
        
        # Temporarily delete all walls
        original_walls = list(Wall.objects.all())
        Wall.objects.all().delete()
        
        # Create mock request
        factory = APIRequestFactory()
        request = factory.post(
            '/api/tasks/start-default/',
            data={'route_id': test_route.id},
            format='json'
        )
        
        try:
            # Call the function
            response = start_default_task(request)
            
            print(f"Response Status: {response.status_code}")
            # Parse JSON from JsonResponse
            response_data = json.loads(response.content)
            print(f"Response Data: {response_data}")
            
            if response.status_code == 400:
                data = response_data
                if 'No walls available' in data.get('message', ''):
                    print("✅ Correctly handled case with no walls")
                    return True
                else:
                    print(f"❌ Unexpected error message: {data.get('message')}")
            else:
                print(f"❌ Expected 400 error, got {response.status_code}")
                
        finally:
            # Restore walls
            for wall in original_walls:
                wall.pk = None  # Create new copy
                wall.save()
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    
    return False

def test_kill_all_tasks_direct():
    """Test kill_all_tasks function directly"""
    print("\n=== Testing Kill All Tasks Function Directly ===")
    
    try:
        # Create some mock task records
        task1 = CeleryTask.objects.create(
            task_id='test-task-1',
            task_name='test_task_1',
            status='PENDING'
        )
        task2 = CeleryTask.objects.create(
            task_id='test-task-2',
            task_name='test_task_2',
            status='PROGRESS'
        )
        
        # Create mock request
        factory = APIRequestFactory()
        request = factory.post('/api/tasks/kill-all/')
        
        # Mock AsyncResult to avoid actual Celery operations
        mock_result = MagicMock()
        mock_result.state = 'PENDING'
        mock_result.revoke = MagicMock()
        
        # Import and patch AsyncResult
        from celery.result import AsyncResult
        original_result = AsyncResult
        AsyncResult = MagicMock(return_value=mock_result)
        
        try:
            # Call the function
            response = kill_all_tasks(request)
            
            print(f"Response Status: {response.status_code}")
            # Parse JSON from JsonResponse
            response_data = json.loads(response.content)
            print(f"Response Data: {response_data}")
            
            if response.status_code == 200:
                data = response_data
                if data.get('status') == 'success':
                    killed_count = data.get('killed_count', 0)
                    print(f"✅ Successfully would kill {killed_count} tasks")
                    return True
                else:
                    print(f"❌ Error: {data.get('message')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
        finally:
            # Restore original AsyncResult
            import celery.result
            celery.result.AsyncResult = original_result
                
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    
    return False

def main():
    """Main test function"""
    print("🚀 Starting Direct API Function Tests")
    print("📍 Testing functions directly without server")
    
    # Test 1: Start task with valid data
    test1_passed = test_start_default_task_direct()
    
    # Test 2: Start task without route_id
    test2_passed = test_start_default_task_without_route()
    
    # Test 3: Start task without walls
    test3_passed = test_start_default_task_without_walls()
    
    # Test 4: Kill all tasks
    test4_passed = test_kill_all_tasks_direct()
    
    # Summary
    print("\n" + "="*50)
    print("📋 DIRECT TEST SUMMARY")
    print("="*50)
    print(f"Start task with valid data: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Start task without route_id: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print(f"Start task without walls: {'✅ PASSED' if test3_passed else '❌ FAILED'}")
    print(f"Kill all tasks: {'✅ PASSED' if test4_passed else '❌ FAILED'}")
    
    all_passed = test1_passed and test2_passed and test3_passed and test4_passed
    
    if all_passed:
        print("\n✅ All tests passed! API functions are working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")

if __name__ == '__main__':
    main()