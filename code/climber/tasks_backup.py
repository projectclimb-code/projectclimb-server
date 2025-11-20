# This file contains the updated stop_session_tracker_task function
# Replace the function in tasks.py with this version

from celery import shared_task
from django.contrib.auth.models import User
from .models import CeleryTask
from loguru import logger


@shared_task
def stop_session_tracker_task(task_id):
    """
    Stop a running session tracker task by ID.
    
    Args:
        task_id: ID of the task to stop
    """
    try:
        # Update database record
        task_record = CeleryTask.objects.filter(task_id=task_id).first()
        if task_record:
            task_record.status = 'stopping'
            task_record.save()
            
            # Revoke the task
            from celery import current_app
            current_app.control.revoke(task_id, terminate=True)
            
            return {
                'status': 'success',
                'message': f'session tracker task {task_id} stopped'
            }
        else:
            return {
                'status': 'error',
                'message': f'session tracker task {task_id} not found'
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error stopping task: {e}'
        }