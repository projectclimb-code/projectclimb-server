#!/usr/bin/env python
"""
Check the status of a Celery task
"""
import os
import sys
import django

# Setup Django
# Set the correct path for the .env file
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.append(project_root)
django.setup()

from celery.result import AsyncResult
from climber.models import CeleryTask

# Check task status
task_id = '7556ff38-f116-454d-a0dd-787317e6b3b0'
result = AsyncResult(task_id)

print(f"Task ID: {task_id}")
print(f"Task state: {result.state}")
print(f"Task info: {result.info}")
print(f"Task result: {result.result}")

# Check database record
db_task = CeleryTask.objects.filter(task_id=task_id).first()
if db_task:
    print(f"\nDatabase record:")
    print(f"  Task name: {db_task.task_name}")
    print(f"  Status: {db_task.status}")
    print(f"  Wall ID: {db_task.wall_id}")
    print(f"  Created at: {db_task.created_at}")
    print(f"  Updated at: {db_task.updated_at}")
else:
    print("\nNo database record found for this task")

# List all tasks in database
print("\nAll tasks in database:")
all_tasks = CeleryTask.objects.all()
for task in all_tasks:
    print(f"  {task.task_id}: {task.task_name} - {task.status}")