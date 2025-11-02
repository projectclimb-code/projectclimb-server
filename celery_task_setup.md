# Celery Task Setup Guide

This guide explains how to use the new Celery task functionality for sending fake session data.

## What's Been Added

1. **Celery Integration**: Added Celery with Redis as the broker for background task processing
2. **Task Management Page**: A new web interface to trigger and monitor tasks
3. **Updated Management Command**: The existing management command now uses Celery for background processing
4. **Real-time Task Monitoring**: Track task progress through the web interface

## Setup Instructions

### 1. Install Dependencies

The Celery dependencies have been added to `pyproject.toml`. Install them with:

```bash
uv sync
```

### 2. Start Redis

Make sure Redis is running (it should already be running in your docker-compose):

```bash
docker-compose up redis
```

### 3. Start Celery Worker

In a new terminal, start the Celery worker:

```bash
cd code
uv run celery -A app worker -l info
```

This will start the Celery worker that will process tasks in the background.

### 4. Start the Django Server

In another terminal, start the Django development server:

```bash
cd code
uv run python manage.py runserver 8000
```

## Using the Task Management Interface

### Access the Task Management Page

Navigate to: http://localhost:8000/tasks/

This page provides a web interface to:
- Configure and trigger the fake session data task
- Monitor task progress in real-time
- View task status and results

### Triggering a Task

1. Fill in the form fields:
   - **Session ID** (optional): Leave empty to create a new session
   - **Duration**: How long the fake session should run (in seconds)
   - **WebSocket URL**: The WebSocket endpoint to send data to
   - **Create new session**: Check this to create a new session in the database

2. Click "Start Task" to trigger the Celery task

3. The task will run in the background, and you can monitor its progress on the same page

### Monitoring Task Progress

The task status section shows:
- **Task ID**: Unique identifier for the task
- **Status**: Current state (PENDING, PROGRESS, SUCCESS, FAILURE)
- **Message**: Status message from the task
- **Progress**: Visual progress bar for long-running tasks

The status automatically updates every 2 seconds while the task is running.

## Using the Management Command

You can still use the management command, which now triggers a Celery task:

```bash
cd code
uv run python manage.py send_fake_session_data [options]
```

Options:
- `--session-id`: UUID of an existing session
- `--ws-url`: WebSocket URL (default: ws://localhost:8000/ws/session-live/)
- `--duration`: Duration in seconds (default: 60)
- `--create-session`: Create a new session in the database
- `--monitor`: Monitor the task progress until completion

Example:
```bash
# Create a new session and monitor progress
uv run python manage.py send_fake_session_data --create-session --duration=120 --monitor

# Use an existing session
uv run python manage.py send_fake_session_data --session-id=123e4567-e89b-12d3-a456-426614174000
```

## Task Details

### What the Task Does

The fake session data task:
1. Creates a new session (if requested)
2. Connects to the WebSocket endpoint
3. Sends initial session and climb data
4. Simulates climbing progress over time
5. Updates hold statuses periodically
6. Sends fake pose data
7. Marks the session as completed

### Task States

- **PENDING**: Task is waiting to be processed
- **PROGRESS**: Task is currently running (shows progress percentage)
- **SUCCESS**: Task completed successfully
- **FAILURE**: Task failed with an error

## Troubleshooting

### Task Not Starting

1. Make sure the Celery worker is running
2. Check that Redis is accessible
3. Verify the Django server is running

### Connection Errors

1. Ensure the WebSocket URL is correct
2. Check that the Django server with Channels is running
3. Verify the WebSocket endpoint exists

### Permission Errors

1. Make sure the user is logged in (for web interface)
2. Check that the user has permission to create sessions

### Common Issues

1. **"Connection refused" error**: Make sure the Django server is running on the correct port
2. **"Task not found" error**: Restart the Celery worker after code changes
3. **"Redis connection error"**: Check that Redis is running and accessible

## Development Notes

### Adding New Tasks

To add new Celery tasks:

1. Create the task in `climber/tasks.py` using the `@shared_task` decorator
2. Add a view to trigger the task if needed
3. Add URL routing for the view
4. Create a template if it's a user-facing task

### Task Best Practices

1. Always handle exceptions in tasks
2. Update task status for long-running operations
3. Use `self.update_state()` to report progress
4. Keep tasks idempotent (safe to run multiple times)

### Monitoring

You can monitor all Celery activity with:

```bash
# Monitor tasks in real-time
uv run celery -A app events

# Check active tasks
uv run celery -A app inspect active

# Check scheduled tasks
uv run celery -A app inspect scheduled
```

## Production Considerations

1. Use a proper message broker (Redis is fine for development)
2. Configure task result backend for persistence
3. Set up monitoring for Celery workers
4. Configure task timeouts and retry policies
5. Use proper logging for task debugging