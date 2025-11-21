#!/usr/bin/env python
"""
Test script to verify that Retry objects can be properly serialized in get_running_tasks view.
"""
import os
import sys
import django
from unittest.mock import Mock, patch

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.views import get_running_tasks
from climber.models import CeleryTask
from celery.exceptions import Retry
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser


def test_retry_serialization():
    """Test that Retry objects are properly serialized in get_running_tasks."""
    print("Testing Retry object serialization...")
    
    # Create a mock request
    factory = RequestFactory()
    request = factory.get('/api/running-tasks/')
    request.user = AnonymousUser()
    
    # Create a mock Retry object
    mock_retry = Retry("Test retry message", when=None)
    
    # Create a mock CeleryTask record
    from datetime import datetime, timezone
    mock_task_record = Mock()
    mock_task_record.task_id = "test-task-id"
    mock_task_record.task_name = "test_task"
    mock_task_record.created = datetime.now(timezone.utc)
    
    # Mock CeleryTask queryset
    with patch('climber.views.CeleryTask.objects.filter') as mock_filter:
        mock_filter.return_value.order_by.return_value = [mock_task_record]
        
        # Mock AsyncResult - need to patch where it's imported (celery.result)
        with patch('celery.result.AsyncResult') as mock_async_result:
            mock_result = Mock()
            mock_result.status = 'RETRY'
            mock_result.result = mock_retry  # This is the problematic Retry object
            mock_async_result.return_value = mock_result
            
            # Call the view
            response = get_running_tasks(request)
            
            # Check the response
            assert response.status_code == 200
            import json
            data = json.loads(response.content)
            
            # Verify that the task is included in the response
            assert 'tasks' in data
            assert len(data['tasks']) == 1
            
            task_info = data['tasks'][0]
            assert task_info['task_id'] == "test-task-id"
            assert task_info['task_name'] == "test_task"
            assert task_info['status'] == 'RETRY'
            
            # Verify that the Retry object was properly serialized
            assert 'result' in task_info
            assert isinstance(task_info['result'], dict)
            assert task_info['result']['type'] == 'Retry'
            assert 'message' in task_info['result']
            
            print("✓ Retry object properly serialized")
            print(f"  Serialized result: {task_info['result']}")
            
    print("All tests passed!")


if __name__ == "__main__":
    test_retry_serialization()