# Session WebSocket Integration

This document describes the new session WebSocket implementation for the ProjectClimb application.

## Overview

The session WebSocket integration provides real-time communication for climbing sessions, allowing multiple clients to receive updates about session progress, climb data, and pose information.

## Architecture

```
Client App → WebSocket → SessionConsumer → Django Models
                      ↑
                Management Command (Fake Data)
```

## Components

### 1. Session Model

The `Session` model represents a single climbing attempt:

```python
class Session(BaseModel):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    ], default='started')
    climb_data = models.JSONField(default=dict, blank=True)
```

### 2. SessionRecording Model Update

The `SessionRecording` model now includes a foreign key to `Session`:

```python
session = models.ForeignKey(Session, on_delete=models.CASCADE, null=True, blank=True, related_name='recordings')
```

### 3. WebSocket Consumer

The `SessionConsumer` handles real-time communication:

- URL: `ws://localhost:8000/ws/session-live/{session_id}/`
- Handles message types: `session_update`, `climb_update`, `pose_update`
- Broadcasts updates to all connected clients in the same session

### 4. Management Command

The `send_fake_session_data` command generates test data:

```bash
uv run python manage.py send_fake_session_data --create-session --duration 60
```

## Data Format

### Climb Data Format

```json
{
  "climb": {
    "holds": [
      { "id": "17", "type": "start", "status": "completed", "time": "2025-01-01T12:00:02.000Z" },
      { "id": "91", "type": "start", "status": "completed", "time": "2025-01-01T12:00:23.000Z" },
      { "id": "6",  "type": "normal", "status": "completed", "time": "2025-01-01T12:00:33.000Z" },
      { "id": "101","type": "normal", "status": "completed", "time": "2025-01-01T12:00:43.000Z" },
      { "id": "55", "type": "normal", "status": "completed", "time": "2025-01-01T12:00:53.000Z" },
      { "id": "133","type": "normal", "status": "untouched", "time": null },
      { "id": "89", "type": "normal", "status": "untouched", "time": null },
      { "id": "41", "type": "normal", "status": "untouched", "time": null },
      { "id": "72", "type": "finish", "status": "untouched", "time": null },
      { "id": "11", "type": "finish", "status": "untouched", "time": null }
    ],
    "startTime": "2025-10-19T17:44:37.187Z",
    "endTime":  null,
    "status": "started"
  },
  "pose": []
}
```

### WebSocket Message Types

1. **session_update**: Updates session status and timing
2. **climb_update**: Updates climb progress data
3. **pose_update**: Sends pose detection data

## Usage

### 1. Start Django Server

```bash
cd code
uv run python manage.py runserver 8012
```

### 2. Create and Test a Session

```bash
# Create a new session and send fake data
uv run python manage.py send_fake_session_data --create-session --duration 60

# Or use an existing session
uv run python manage.py send_fake_session_data --session-id <uuid> --duration 60
```

### 3. Connect from Client

```javascript
const session_id = '<session-uuid>';
const ws = new WebSocket(`ws://localhost:8000/ws/session-live/${session_id}/`);

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    
    switch(data.type) {
        case 'session_updated':
            // Handle session status updates
            break;
        case 'climb_updated':
            // Handle climb progress updates
            updateClimbDisplay(data.climb);
            break;
        case 'pose_updated':
            // Handle pose data
            updatePoseDisplay(data.pose);
            break;
    }
};
```

## Testing

Use the test script to verify the implementation:

```bash
cd code
uv run python test_session_websocket.py --session-id <uuid> --test-fake-data
```

## API Endpoints

### REST API

- `GET /api/sessions/` - List sessions
- `POST /api/sessions/` - Create a new session
- `GET /api/sessions/{id}/` - Get session details
- `PUT /api/sessions/{id}/` - Update session
- `DELETE /api/sessions/{id}/` - Delete session

- `GET /api/session-recordings/` - List session recordings
- `POST /api/session-recordings/` - Create a new recording

### WebSocket Endpoints

- `ws://localhost:8000/ws/session-live/{session_id}/` - Live session updates
- `ws://localhost:8000/ws/session/{session_id}/` - Session replay

## Migration

After updating the models, create and apply migrations:

```bash
cd code
uv run python manage.py makemigrations
uv run python manage.py migrate
```

## Troubleshooting

### Common Issues

1. **WebSocket connection refused**
   - Ensure Django server is running
   - Check if WebSocket URL is correct

2. **Session not found**
   - Verify session ID is correct
   - Check if session exists in database

3. **Permission denied**
   - Ensure user is authenticated
   - Check user permissions

### Debugging

Enable Django debug mode to see detailed error messages:

```python
DEBUG = True
```

Check WebSocket connection in browser developer tools:
1. Open Developer Tools
2. Go to Network tab
3. Filter by WS (WebSockets)
4. Look for connection errors