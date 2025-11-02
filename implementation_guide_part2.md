# Implementation Guide - Part 2

## 9. Complete JavaScript for session_replay.html

```javascript
// Continuing from implementation_guide.md

        function initScene() {
            scene = new THREE.Scene();
            scene.background = null; // Transparent background for overlay
            
            // Set up camera to match video dimensions
            camera = new THREE.PerspectiveCamera(75, overlayElement.clientWidth / overlayElement.clientHeight, 0.1, 1000);
            camera.position.z = 2;
            
            renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
            renderer.setSize(overlayElement.clientWidth, overlayElement.clientHeight);
            renderer.setClearColor(0x000000, 0); // Transparent background
            overlayElement.appendChild(renderer.domElement);
            
            // Create pose visualization elements
            const pointsGeometry = new THREE.BufferGeometry();
            const pointsMaterial = new THREE.PointsMaterial({ 
                color: 0x00ff00, 
                size: 0.05,
                transparent: true,
                opacity: 0.8
            });
            posePoints = new THREE.Points(pointsGeometry, pointsMaterial);
            scene.add(posePoints);
            
            const lineMaterial = new THREE.LineBasicMaterial({ 
                color: 0xffffff,
                transparent: true,
                opacity: 0.8
            });
            const lineGeometry = new THREE.BufferGeometry();
            poseLines = new THREE.LineSegments(lineGeometry, lineMaterial);
            scene.add(poseLines);
            
            // Handle window resize
            window.addEventListener('resize () => {
                camera.aspect = overlayElement.clientWidth / overlayElement.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(overlayElement.clientWidth, overlayElement.clientHeight);
            });
            
            animate();
        }
        
        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
        
        function updatePose(landmarks) {
            if (!landmarks || landmarks.length === 0) return;
            
            const landmarkConnections = [
                [0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8],
                [9, 10], [11, 12], [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
                [12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [11, 23], [12, 24],
                [23, 24], [23, 25], [24, 26], [25, 27], [26, 28], [27, 29], [28, 30],
                [29, 31], [30, 32], [27, 31], [28, 32]
            ];
            
            const points = [];
            landmarks.forEach(lm => {
                points.push(-lm.x, -lm.y, -lm.z);
            });
            
            posePoints.geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
            
            const indices = [];
            landmarkConnections.forEach(conn => {
                if (landmarks[conn[0]] && landmarks[conn[1]] && 
                    landmarks[conn[0]].visibility > 0.5 && landmarks[conn[1]].visibility > 0.5) {
                    indices.push(conn[0], conn[1]);
                }
            });
            
            poseLines.geometry.setIndex(indices);
            poseLines.geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
            
            posePoints.geometry.attributes.position.needsUpdate = true;
            poseLines.geometry.attributes.position.needsUpdate = true;
            poseLines.geometry.index.needsUpdate = true;
        }
        
        function formatTime(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        
        // Playback controls
        playPauseBtn.addEventListener('click', () => {
            if (isPlaying) {
                socket.send(JSON.stringify({ type: 'pause' }));
                playPauseBtn.textContent = 'Play';
                isPlaying = false;
            } else {
                socket.send(JSON.stringify({ type: 'play' }));
                playPauseBtn.textContent = 'Pause';
                isPlaying = true;
            }
        });
        
        timeline.addEventListener('input', (e) => {
            const frameNumber = parseInt(e.target.value);
            socket.send(JSON.stringify({ 
                type: 'seek', 
                frame_number: frameNumber 
            }));
        });
        
        playbackSpeed.addEventListener('change', (e) => {
            // Send speed preference to server
            socket.send(JSON.stringify({ 
                type: 'set_speed', 
                speed: parseFloat(e.target.value) 
            }));
        });
        
        // Initialize
        connect();
        initScene();
    });
</script>
{% endblock %}
```

## 10. Sidebar Navigation Update (code/climber/templates/climber/_sidebar.html)

```html
<!-- Add the following line before the closing </ul> tag -->
<li><a href="{% url 'session_list' %}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-gray-700 hover:text-white">Sessions</a></li>
```

## 11. Pose Streamer Modifications (code/pose_streamer.py)

```python
# Add to pose_streamer.py
import base64
import numpy as np
from datetime import datetime

# Modify the stream_pose_landmarks function to include recording support
async def stream_pose_landmarks():
    is_recording = False
    recording_session_id = None
    frame_count = 0
    recording_start_time = None
    
    while True:
        print(f"Attempting to connect to WebSocket server at {args.ws_uri}...")
        try:
            async with websockets.connect(args.ws_uri) as websocket:
                print("Successfully connected to WebSocket server.")
                
                video_source = int(args.source) if args.source.isdigit() else args.source
                cap = cv2.VideoCapture(video_source)

                if not cap.isOpened():
                    print(f"Error: Could not open video source: {args.source}")
                    await asyncio.sleep(5)
                    continue

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        print("End of video stream or cannot grab frame.")
                        break
                    
                    frame_count += 1
                    current_time = datetime.now()
                    
                    # Calculate timestamp if recording
                    timestamp = 0
                    if is_recording and recording_start_time:
                        timestamp = (current_time - recording_start_time).total_seconds()

                    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = pose.process(image_rgb)

                    landmarks_data = []
                    if results.pose_world_landmarks:
                        for landmark in results.pose_world_landmarks.landmark:
                            landmarks_data.append({
                                'x': landmark.x,
                                'y': landmark.y,
                                'z': landmark.z,
                                'visibility': landmark.visibility,
                            })
                    
                    # Prepare message data
                    message_data = {
                        'landmarks': landmarks_data,
                        'frame_number': frame_count,
                        'timestamp': timestamp
                    }
                    
                    # Add frame image if recording
                    if is_recording:
                        # Encode frame as base64 for transmission
                        _, buffer = cv2.imencode('.jpg', frame)
                        frame_base64 = base64.b64encode(buffer).decode('utf-8')
                        message_data['frame_image'] = frame_base64
                    
                    try:
                        if landmarks_data:
                            await websocket.send(json.dumps(message_data))
                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection lost. Reconnecting...")
                        break
                    
                    # Handle control messages from server
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                        control_data = json.loads(response)
                        
                        if control_data.get('type') == 'start_recording':
                            is_recording = True
                            recording_session_id = control_data.get('session_id')
                            recording_start_time = datetime.now()
                            frame_count = 0
                            print(f"Started recording session: {recording_session_id}")
                            
                        elif control_data.get('type') == 'stop_recording':
                            is_recording = False
                            print(f"Stopped recording session: {recording_session_id}")
                            recording_session_id = None
                            recording_start_time = None
                            
                    except asyncio.TimeoutError:
                        # No control message, continue streaming
                        pass
                    
                    # Enforce the target frame rate
                    await asyncio.sleep(DELAY)

                cap.release()

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"Failed to connect: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
```

## 12. Media File Handling

Create a utility function to handle video file storage:

```python
# code/climber/utils.py
import os
import uuid
from django.conf import settings
from datetime import datetime

def get_session_video_path(session_instance, filename):
    """Generate a unique path for session video files"""
    session_id = str(session_instance.uuid)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{session_id}_{timestamp}.mp4"
    return os.path.join('sessions', 'videos', filename)

def create_video_from_frames(session_instance):
    """
    Create a video file from individual session frames
    This would be implemented as a background task using Celery or similar
    """
    # Implementation would involve:
    # 1. Collect all frame images for the session
    # 2. Use OpenCV's VideoWriter to create an MP4
    # 3. Save to media storage and update session.video_file_path
    pass
```

## 13. Database Migration

After adding the models, create and apply the migration:

```bash
uv run python manage.py makemigrations climber
uv run python manage.py migrate
```

## 14. Testing

Create test files for the new functionality:

```python
# code/climber/tests_sessions.py
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import SessionRecording, SessionFrame
import json

class SessionRecordingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_create_session_recording(self):
        response = self.client.post('/api/sessions/', {
            'name': 'Test Session',
            'description': 'A test recording session'
        })
        self.assertEqual(response.status_code, 201)
        
        session = SessionRecording.objects.get(name='Test Session')
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.status, 'recording')
    
    def test_session_list_view(self):
        SessionRecording.objects.create(
            name='Test Session',
            user=self.user,
            status='completed'
        )
        
        response = self.client.get('/sessions/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Session')
    
    def test_session_frame_creation(self):
        session = SessionRecording.objects.create(
            name='Test Session',
            user=self.user
        )
        
        frame_data = {
            'nose': {'x': 0.5, 'y': 0.3, 'z': 0.0, 'visibility': 0.9},
            'left_eye': {'x': 0.45, 'y': 0.28, 'z': 0.0, 'visibility': 0.8}
        }
        
        frame = SessionFrame.objects.create(
            session=session,
            timestamp=1.5,
            frame_number=30,
            pose_data=frame_data
        )
        
        self.assertEqual(frame.session, session)
        self.assertEqual(frame.timestamp, 1.5)
        self.assertEqual(frame.pose_data['nose']['x'], 0.5)
```

## 15. Performance Optimization

Consider implementing these optimizations:

1. **Frame Sampling**: Store every nth frame instead of every frame to reduce storage
2. **Lazy Loading**: Load frames on-demand during replay
3. **Compression**: Compress pose data before storing
4. **Background Processing**: Use Celery for video file processing

## 16. Security Considerations

1. **User Authentication**: Ensure users can only access their own sessions
2. **File Upload Validation**: Validate file types and sizes
3. **Rate Limiting**: Implement WebSocket rate limiting
4. **Input Sanitization**: Sanitize all user inputs

## 17. Deployment Notes

1. **Media Storage**: Configure appropriate media storage for production
2. **WebSocket Support**: Ensure your deployment supports WebSocket connections
3. **Background Tasks**: Set up Celery or similar for background video processing
4. **Monitoring**: Add logging for recording and replay activities

This implementation provides a comprehensive session recording and replay system that integrates with your existing pose tracking functionality. The system allows users to record climbing sessions with both pose data and video, then replay them with the pose overlayed on a live camera feed.