# Session Recording and Replay - Setup Instructions

## Overview
This document provides the setup instructions for the newly implemented session recording and replay functionality in the climbing project.

## Database Migration

After implementing all the code changes, you need to create and apply the database migrations:

```bash
uv run python manage.py makemigrations climber
uv run python manage.py migrate
```

## Testing the Implementation

### 1. Start the Django Development Server
```bash
uv run python manage.py runserver 8000
```

### 2. Start the Pose Streamer
In a new terminal, run the pose streamer:
```bash
uv run python code/pose_streamer.py --source 0
```

### 3. Test Recording Functionality
1. Navigate to http://localhost:8000/pose/
2. Wait for the WebSocket connection to establish (status should show "Connected")
3. Enter a session name in the recording controls
4. Click "Start Recording"
5. Move around to capture pose data
6. Click "Stop Recording" when done

### 4. Test Session Management
1. Navigate to http://localhost:8000/sessions/
2. You should see your recorded session in the list
3. Click "Details" to view session information
4. Click "Replay" to open the replay interface

### 5. Test Replay Functionality
1. In the replay interface, ensure your webcam is active
2. Click "Play" to start the replay
3. The recorded pose should overlay on your live webcam feed
4. Use the timeline to seek to specific moments
5. Adjust playback speed as needed

## File Structure Summary

### New Files Created:
- `code/climber/templates/climber/session_list.html`
- `code/climber/templates/climber/session_detail.html`
- `code/climber/templates/climber/session_confirm_delete.html`
- `code/climber/templates/climber/session_replay.html`

### Modified Files:
- `code/climber/models.py` - Added SessionRecording and SessionFrame models
- `code/climber/serializers.py` - Added serializers for new models
- `code/climber/views.py` - Added session views and ViewSets
- `code/climber/urls.py` - Added session URLs
- `code/climber/routing.py` - Added WebSocket route for session replay
- `code/climber/consumers.py` - Modified PoseConsumer and added SessionReplayConsumer
- `code/climber/templates/climber/pose_realtime.html` - Added recording controls
- `code/climber/templates/climber/_sidebar.html` - Added Sessions link
- `code/pose_streamer.py` - Added recording support

## Key Features Implemented

1. **Session Recording**:
   - Start/stop recording from the pose visualization page
   - Store pose data with timestamps
   - Session metadata (name, description, duration, etc.)

2. **Session Management**:
   - List all recorded sessions
   - View session details
   - Delete sessions
   - User-specific session filtering

3. **Session Replay**:
   - Replay recorded sessions with pose overlay
   - Playback controls (play/pause, seek, speed adjustment)
   - Timeline interface
   - Live webcam feed with recorded pose overlay

4. **WebSocket Communication**:
   - Real-time pose streaming
   - Recording control messages
   - Replay frame streaming
   - Bidirectional communication for controls

## Troubleshooting

### Common Issues:

1. **WebSocket Connection Fails**:
   - Ensure the Django server is running
   - Check that the WebSocket URL is correct
   - Verify the routing configuration

2. **Recording Doesn't Start**:
   - Check browser console for JavaScript errors
   - Verify the WebSocket connection is established
   - Check the Django logs for any errors

3. **Replay Doesn't Work**:
   - Ensure the session has recorded frames
   - Check the WebSocket connection for replay
   - Verify the session UUID is correct

4. **Pose Overlay Not Visible**:
   - Check that Three.js is loading correctly
   - Ensure the pose data is being received
   - Verify the overlay container is properly positioned

## Next Steps

1. **Authentication**: Currently the system uses the first available user for anonymous sessions. In production, you should implement proper user authentication.

2. **Video Storage**: The current implementation stores pose data but not video frames. Consider implementing video file storage for complete session recordings.

3. **Performance Optimization**: For long sessions, consider implementing frame sampling or lazy loading to improve performance.

4. **Error Handling**: Add more comprehensive error handling and user feedback throughout the application.

5. **Testing**: Write unit and integration tests for the new functionality.

## Security Considerations

1. Ensure users can only access their own sessions
2. Validate all input data
3. Implement rate limiting for WebSocket connections
4. Secure file uploads if implementing video storage

This implementation provides a solid foundation for session recording and replay functionality in your climbing project. The modular design allows for future enhancements and optimizations.