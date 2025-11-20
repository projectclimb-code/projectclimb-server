# WebSocket Pose Session Tracker Celery Task

This document explains how to use the `websocket_pose_session_tracker_task` Celery task, which provides the same functionality as the `websocket_pose_session_tracker` management command but runs as a background job.

## Overview

The WebSocket pose session tracker task connects to an input WebSocket to receive MediaPipe pose data, transforms the landmarks using wall calibration, detects hold touches based on hand proximity to SVG paths, and outputs session data to an output WebSocket.

## Task Parameters

- `wall_id` (int, optional, default=1): ID of wall to use for calibration transformation
- `input_websocket_url` (str, optional, default="http://192.168.88.2:8011/ws/pose/"): WebSocket URL for receiving pose data
- `output_websocket_url` (str, optional, default="http://192.168.88.2:8011/ws/holds/"): WebSocket URL for sending session data
- `proximity_threshold` (float, optional, default=300.0): Distance in pixels to consider hand near hold
- `touch_duration` (float, optional, default=0.5): Time in seconds hand must be near hold to count as touch
- `reconnect_delay` (float, optional, default=0.5): Delay between reconnection attempts in seconds
- `debug` (bool, optional, default=False): Enable debug output
- `no_stream_landmarks` (bool, optional, default=False): Skip streaming transformed landmarks in output
- `stream_svg_only` (bool, optional, default=False): Stream only SVG paths that are touched
- `route_data` (str, optional): Route data as JSON string with holds specification
- `route_id` (int, optional, default=99): Route ID to retrieve from database

## Usage Examples

### Basic Usage

```python
from climber.tasks import websocket_pose_session_tracker_task

# Start the task with default values
task = websocket_pose_session_tracker_task.delay()

# Get task ID
task_id = task.id
print(f"Task started with ID: {task_id}")

# Or start with custom values
task = websocket_pose_session_tracker_task.delay(
    wall_id=2,
    input_websocket_url="ws://localhost:8080",
    output_websocket_url="ws://localhost:8000/ws/session-live/"
)
```

### With Route Data

```python
import json

# Define route data
route_data = {
    "grade": "V5",
    "author": "Test User",
    "problem": {
        "holds": [
            {"id": "17", "type": "start"},
            {"id": "91", "type": "start"},
            {"id": "6", "type": "normal"},
            {"id": "101", "type": "normal"},
            {"id": "55", "type": "normal"},
            {"id": "133", "type": "normal"},
            {"id": "89", "type": "normal"},
            {"id": "41", "type": "normal"},
            {"id": "72", "type": "finish"},
            {"id": "11", "type": "finish"}
        ]
    }
}

# Start the task with route data (using defaults for other parameters)
task = websocket_pose_session_tracker_task.delay(
    route_data=json.dumps(route_data),
    proximity_threshold=40.0,  # Override default proximity_threshold
    touch_duration=1.5,        # Override default touch_duration
    debug=True                # Enable debug output
)
```

### With Route ID from Database

```python
# Start the task with route ID (using defaults for other parameters)
task = websocket_pose_session_tracker_task.delay(
    route_id=5,  # Override default route_id
    debug=True   # Enable debug output
)
```

## Monitoring Task Progress

```python
from celery.result import AsyncResult

# Get task result
task_result = AsyncResult(task_id)

# Check task status
if task_result.ready():
    result = task_result.get()
    print(f"Task completed: {result}")
else:
    print(f"Task status: {task_result.status}")
    
    # Get progress info if available
    if task_result.info:
        print(f"Progress info: {task_result.info}")
```

## Running the Test Script

A test script is provided at `code/test_websocket_pose_session_tracker_task.py`:

```bash
# Make sure Celery worker is running
celery -A code worker -l info

# In another terminal, run the test script
cd code
python test_websocket_pose_session_tracker_task.py
```

## Task Result Format

When the task completes, it returns a dictionary with the following format:

```python
{
    'status': 'success',  # or 'error'
    'message': 'WebSocket pose session tracker completed successfully',
    'wall_id': 1,
    'message_count': 1234,
    'elapsed_time': 120.5,
    'average_rate': 10.24
}
```

## Error Handling

If the task encounters an error, it will return:

```python
{
    'status': 'error',
    'message': 'Error description'
}
```

## Comparison with Management Command

The Celery task provides the same functionality as the management command but with these advantages:

1. **Background execution**: Runs as a background job without blocking the main process
2. **Progress monitoring**: Built-in progress tracking and status updates
3. **Scalability**: Can be distributed across multiple Celery workers
4. **Persistence**: Task state is persisted and can be monitored even if the process restarts

## Prerequisites

1. **Celery worker must be running**: `celery -A code worker -l info`
2. **Django server must be running** for WebSocket connections
3. **Wall with calibration** must exist in the database
4. **Input WebSocket** must be providing pose data in the correct format

## Troubleshooting

1. **Task not starting**: Make sure Celery worker is running and can access the Django app
2. **Connection errors**: Check that WebSocket URLs are correct and servers are running
3. **Calibration errors**: Ensure the wall has an active calibration with perspective transform
4. **Route not found**: Verify route ID exists in the database if using route_id parameter