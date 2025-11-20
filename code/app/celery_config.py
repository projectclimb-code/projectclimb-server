from celery import Celery

# Create the Celery app
app = Celery('app')

# Export the app as celery_app for imports
celery_app = app

# Configure the app
app.config_from_object('django.conf:settings')

# Auto-discover tasks
app.autodiscover_tasks()