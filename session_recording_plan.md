# Session Recording and Replay Implementation Plan

## Overview
This plan outlines the implementation of a session recording and replay system for the climbing project, allowing users to record climbing sessions (both pose data and video feed) and replay them over a live webcam feed.

## System Architecture

### Data Models
1. **SessionRecording** - Main model to store session metadata
   - name: Session name
   - description: Optional description
   - created_at: Creation timestamp
   - duration: Session duration in seconds
   - frame_count: Total number of frames
   - user: Foreign key to User model
   - video_file_path: Path to stored video file
   - status: Enum (recording, completed, processing)

2. **SessionFrame** - Model to store individual frame data
   - session: Foreign key to SessionRecording
   - timestamp: Frame timestamp within session
   - frame_number: Sequential frame number
   - pose_data: JSON field storing pose landmarks
   - image_path: Path to frame image (optional for keyframes)

### WebSocket Communication
1. **Recording Flow**:
   - Client sends "start_recording" message with session metadata
   - Server creates SessionRecording instance
   - Client streams pose data and video frames
   - Server stores data and updates session
   - Client sends "stop_recording" message
   - Server finalizes session

2. **Replay Flow**:
   - Client connects to replay WebSocket with session ID
   - Server streams frame data in sequence
   - Client displays pose overlay on live webcam feed
   - Client can control playback (play, pause, seek)

### UI Components
1. **Recording Controls**:
   - Start/Stop recording buttons
   - Session name input
   - Recording status indicator
   - Timer display

2. **Session Management**:
   - List of recorded sessions
   - Session details view
   - Delete session functionality

3. **Replay Interface**:
   - Video player with webcam overlay
   - Timeline slider for seeking
   - Play/pause controls
   - Speed control

## Implementation Steps

### Phase 1: Backend Foundation
1. Create database models for sessions and frames
2. Create serializers for API endpoints
3. Implement basic CRUD views for sessions
4. Add URL routing for session management

### Phase 2: WebSocket Implementation
1. Extend PoseConsumer to handle recording messages
2. Create SessionReplayConsumer for playback functionality
3. Implement recording logic in pose_streamer.py
4. Add WebSocket routing for replay endpoints

### Phase 3: Frontend Integration
1. Add recording controls to pose_realtime.html
2. Create session list/detail templates
3. Implement replay interface with webcam overlay
4. Add session management to sidebar

### Phase 4: Advanced Features
1. Timeline controls for replay
2. Speed adjustment functionality
3. Frame-by-frame navigation
4. Export/share functionality

## Technical Considerations

### Storage
- Video files stored in media directory
- Pose data stored in database as JSON
- Consider implementing file cleanup for old sessions

### Performance
- Implement lazy loading for frame data
- Use pagination for session lists
- Optimize WebSocket message size

### Security
- Validate user permissions for session access
- Sanitize file uploads
- Implement rate limiting for WebSocket connections

## File Structure
```
code/climber/
├── models.py (add SessionRecording, SessionFrame)
├── views.py (add session CRUD views)
├── consumers.py (extend PoseConsumer, add SessionReplayConsumer)
├── urls.py (add session URLs)
├── serializers.py (add session serializers)
├── templates/climber/
│   ├── session_list.html
│   ├── session_detail.html
│   ├── session_replay.html
│   └── pose_realtime.html (modify)
└── routing.py (add replay WebSocket route)