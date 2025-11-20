#!/usr/bin/env python
"""
Script to start a Celery worker for processing tasks
"""
import os
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
os.environ.setdefault('PYTHONPATH', '/code')

# Start Celery worker
if __name__ == "__main__":
    from celery import current_app
    from celery.bin import worker
    
    # Create worker with our app
    worker = worker.worker(app=current_app)
    
    # Start worker with log level info
    worker.start(loglevel='info')