# Celery Task for WebSocket Pose Session Tracking

This document explains how to use the Celery task implementation for WebSocket pose session tracking.

## Overview

The WebSocket pose session tracker has been implemented as a Celery task that can be started and stopped from the web interface. This allows session tracking to run in the background without blocking the main Django application.

The implementation includes:
- A Celery task that runs the WebSocket pose session tracker in the background
- Task management functions to start and stop running trackers
- API endpoints to control tasks
- A web interface with HTMX for managing tasks without page reloads
- Docker support for easy deployment
- Comprehensive testing suite

## Prerequisites

1. Redis server running (configured in settings.py)
2. Celery worker process running

## Starting the Celery Worker

### Option 1: Manual Terminal

```bash
cd code
uv run celery -A app worker -l info
```

### Option 2: Docker Compose

```bash
docker-compose up celery
```

This will start the Celery worker service defined in docker-compose.yml.

## Using the Web Interface

1. Navigate to `/tasks/` in your browser
2. Fill in the form to start a new session:
   - Select a wall and route
   - Configure WebSocket URLs
   - Adjust proximity threshold and touch duration as needed
3. Click "Start Session" to begin tracking
4. Monitor running trackers in the table above
5. Click "Stop" to terminate a running tracker

Features:
- Real-time updates without page reloads (HTMX)
- Start/stop sessions with form validation
- Auto-refreshing tracker status table
- Responsive design with Tailwind CSS

## Using the API Endpoints

### Start a Session

```bash
curl "http://localhost:8000/api/start_session/1/?input_websocket_url=ws://localhost:8001/ws/pose/&output_websocket_url=ws://localhost:8002/ws/session/"
```

### Stop a Session

```bash
curl "http://localhost:8000/api/start_stop/?task_id=<task_id>"
```

### Get Running Tasks

```bash
curl "http://localhost:8000/api/running-tasks/"
```

## Implementation Details

The Celery task implementation includes:

1. **Task Creation** (`websocket_pose_session_tracker_task`)
   - Accepts all parameters from the original management command
   - Tracks running tasks in a global dictionary
   - Updates task status during execution

2. **Task Management** (`stop_session_tracker_task`, `get_running_session_trackers`)
   - Stop running tasks by ID
   - List all currently running trackers
   - Clean up task references when stopped

3. **WebSocket Session Tracker** (`WebSocketPoseSessionTrackerCelery`)
   - Celery-compatible version of the original tracker
   - Handles WebSocket connections for input/output
   - Performs pose transformation and hold detection
   - Sends progress updates to the Celery task

4. **HTMX Integration**
   - Partial page updates for better UX
   - No full page reloads when starting/stopping tasks
   - Auto-refreshing tracker status every 5 seconds
   - Form submission without page navigation

## Testing

Run the test script to verify the implementation:

```bash
cd code
uv run python test_celery_integration.py
```

The test script verifies:
- Database models are accessible
- Task functions are available
- API endpoints are working (if the server is running)
- Task state management

## Troubleshooting

### Task Not Starting

1. Check that Redis is running
2. Start the Celery worker (see above)
3. Check the Django logs for any errors

### Task Stuck in PENDING

1. Verify that the Celery worker is running
2. Check that the worker has loaded the task module
3. Look for any import errors in the worker logs

### WebSocket Connection Issues

1. Verify that the WebSocket URLs are correct
2. Check that WebSocket servers are running
3. Ensure firewall settings allow the connections

### HTMX Not Working

1. Ensure that the HTMX library is loaded (included in base.html)
2. Check the browser console for JavaScript errors
3. Verify that the CSRF token is present

### Debug Mode

Enable debug mode for detailed logging:
- Set `debug=true` in API parameters
- Check `logs/celery.log` for worker logs
- Use the Django admin to monitor the task status

### Browser Compatibility

The implementation uses modern JavaScript features:
- Fetch API for HTTP requests
- HTMX for partial page updates
- Arrow functions for cleaner code

Tested on:
- Chrome 90+
- Firefox 88+
- Safari 14+