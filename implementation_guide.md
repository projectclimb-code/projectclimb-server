
# Implementation Guide

## 1. Database Models (code/climber/models.py)

```python
# Add to models.py
class SessionRecording(BaseModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    duration = models.IntegerField(default=0)  # Duration in seconds
    frame_count = models.IntegerField(default=0)
    video_file_path = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('recording', 'Recording'),
            ('completed', 'Completed'),
            ('processing', 'Processing'),
        ],
        default='recording'
    )
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"

class SessionFrame(models.Model):
    session = models.ForeignKey(SessionRecording, on_delete=models.CASCADE, related_name='frames')
    timestamp = models.FloatField()  # Timestamp in seconds from start
    frame_number = models.IntegerField()
    pose_data = models.JSONField()  # Store pose landmarks as JSON
    image_path = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        ordering = ['frame_number']
        indexes = [
            models.Index(fields=['session', 'frame_number']),
        ]
    
    def __str__(self):
        return f"Frame {self.frame_number} of {self.session.name}"
```

## 2. Serializers (code/climber/serializers.py)

```python
# Add to serializers.py
class SessionRecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionRecording
        fields = ['uuid', 'name', 'description', 'created', 'duration', 
                 'frame_count', 'status', 'user']
        read_only_fields = ['uuid', 'created', 'user']

class SessionFrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionFrame
        fields = ['timestamp', 'frame_number', 'pose_data', 'image_path']
```

## 3. WebSocket Consumer Modifications (code/climber/consumers.py)

```python
# Modify PoseConsumer to handle recording
class PoseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'pose_stream'
        self.recording_session = None
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Handle recording commands
        if data.get('type') == 'start_recording':
            await self.start_recording(data)
        elif data.get('type') == 'stop_recording':
            await self.stop_recording()
        else:
            # Regular pose data
            await self.handle_pose_data(data)
    
    async def start_recording(self, data):
        # Create new session recording
        from .models import SessionRecording
        from django.contrib.auth.models import User
        
        user = await self.get_user()
        self.recording_session = SessionRecording.objects.create(
            name=data.get('name', 'Untitled Session'),
            description=data.get('description', ''),
            user=user,
            status='recording'
        )
        
        await self.send(text_data=json.dumps({
            'type': 'recording_started',
            'session_id': str(self.recording_session.uuid)
        }))
    
    async def stop_recording(self):
        if self.recording_session:
            self.recording_session.status = 'completed'
            self.recording_session.save()
            
            await self.send(text_data=json.dumps({
                'type': 'recording_stopped',
                'session_id': str(self.recording_session.uuid)
            }))
            
            self.recording_session = None
    
    async def handle_pose_data(self, data):
        # Store frame if recording
        if self.recording_session:
            await self.store_frame(data)
        
        # Broadcast to all clients
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'pose_message',
                'message': json.dumps(data)
            }
        )
    
    async def store_frame(self, data):
        from .models import SessionFrame
        
        # Implementation depends on how you want to store frames
        # This is a simplified version
        SessionFrame.objects.create(
            session=self.recording_session,
            timestamp=data.get('timestamp', 0),
            frame_number=data.get('frame_number', 0),
            pose_data=data.get('landmarks', [])
        )

# Add new consumer for replay
class SessionReplayConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'session_replay_{self.session_id}'
        
        await self.channel_layer.group_add(
            self.session_group_name,
            self.channel_name
        )
        await self.accept()
        
        # Start streaming session data
        await self.start_replay()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.session_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data.get('type') == 'play':
            await self.start_replay()
        elif data.get('type') == 'pause':
            await self.pause_replay()
        elif data.get('type') == 'seek':
            await self.seek_to_frame(data.get('frame_number'))
    
    async def start_replay(self):
        from .models import SessionFrame
        
        frames = SessionFrame.objects.filter(
            session__uuid=self.session_id
        ).order_by('frame_number')
        
        for frame in frames:
            await self.send(text_data=json.dumps({
                'type': 'frame_data',
                'frame_number': frame.frame_number,
                'timestamp': frame.timestamp,
                'pose_data': frame.pose_data
            }))
            
            # Adjust delay based on frame timing
            await asyncio.sleep(0.033)  # ~30fps
```

## 4. Views (code/climber/views.py)

```python
# Add to views.py
class SessionRecordingViewSet(viewsets.ModelViewSet):
    queryset = SessionRecording.objects.all()
    serializer_class = SessionRecordingSerializer
    
    def get_queryset(self):
        # Filter by current user
        return SessionRecording.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class SessionListView(ListView):
    model = SessionRecording
    template_name = 'climber/session_list.html'
    context_object_name = 'sessions'
    
    def get_queryset(self):
        return SessionRecording.objects.filter(user=self.request.user)

class SessionDetailView(UUIDLookupMixin, DetailView):
    model = SessionRecording
    template_name = 'climber/session_detail.html'
    context_object_name = 'session'

class SessionDeleteView(UUIDLookupMixin, DeleteView):
    model = SessionRecording
    template_name = 'climber/session_confirm_delete.html'
    success_url = reverse_lazy('session_list')

class SessionReplayView(UUIDLookupMixin, DetailView):
    model = SessionRecording
    template_name = 'climber/session_replay.html'
    context_object_name = 'session'
```

## 5. URL Routing (code/climber/urls.py)

```python
# Add to urlpatterns
path('sessions/', SessionListView.as_view(), name='session_list'),
path('sessions/<uuid:pk>/', SessionDetailView.as_view(), name='session_detail'),
path('sessions/<uuid:pk>/delete/', SessionDeleteView.as_view(), name='session_delete'),
path('sessions/<uuid:pk>/replay/', SessionReplayView.as_view(), name='session_replay'),

# Add to router
router.register(r'sessions', SessionRecordingViewSet)
```

## 6. WebSocket Routing (code/climber/routing.py)

```python
# Add to websocket_urlpatterns
re_path(r'ws/session/(?P<session_id>[^/]+)/$', SessionReplayConsumer.as_asgi()),
```

## 7. Template Modifications

### pose_realtime.html - Add Recording Controls
```html
<!-- Add to pose_realtime.html after the connection status div -->
<div id="recording-controls" class="absolute top-4 right-4 bg-gray-800 bg-opacity-75 p-4 rounded-lg">
    <div id="recording-status" class="text-white mb-2">Not Recording</div>
    <div id="recording-timer" class="text-white mb-2">00:00</div>
    <div class="mb-2">
        <input type="text" id="session-name" placeholder="Session name" 
               class="px-2 py-1 rounded text-black">
    </div>
    <button id="start-recording" class="bg-red-500 hover:bg-red-700 text-white px-3 py-1 rounded mr-2">
        Start Recording
    </button>
    <button id="stop-recording" class="bg-gray-500 hover:bg-gray-700 text-white px-3 py-1 rounded" disabled>
        Stop Recording
    </button>
</div>

<!-- Add JavaScript for recording functionality -->
<script>
    let isRecording = false;
    let recordingStartTime = null;
    let recordingTimer = null;
    let currentSessionId = null;

    document.getElementById('start-recording').addEventListener('click', startRecording);
    document.getElementById('stop-recording').addEventListener('click', stopRecording);

    function startRecording() {
        const sessionName = document.getElementById('session-name').value || 'Untitled Session';
        
        socket.send(JSON.stringify({
            type: 'start_recording',
            name: sessionName
        }));
        
        isRecording = true;
        recordingStartTime = Date.now();
        updateRecordingUI();
        startTimer();
    }

    function stopRecording() {
        socket.send(JSON.stringify({
            type: 'stop_recording'
        }));
        
        isRecording = false;
        updateRecordingUI();
        stopTimer();
    }

    function updateRecordingUI() {
        const statusEl = document.getElementById('recording-status');
        const startBtn = document.getElementById('start-recording');
        const stopBtn = document.getElementById('stop-recording');
        
        if (isRecording) {
            statusEl.textContent = 'Recording...';
            statusEl.className = 'text-red-500 mb-2';
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusEl.textContent = 'Not Recording';
            statusEl.className = 'text-white mb-2';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    }

    function startTimer() {
        recordingTimer = setInterval(() => {
            const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
            const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
            const seconds = (elapsed % 60).toString().padStart(2, '0');
            document.getElementById('recording-timer').textContent = `${minutes}:${seconds}`;
        }, 1000);
    }

    function stopTimer() {
        clearInterval(recordingTimer);
        document.getElementById('recording-timer').textContent = '00:00';
    }

    // Handle WebSocket messages for recording
    socket.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'recording_started') {
            currentSessionId = data.session_id;
        } else if (data.type === 'recording_stopped') {
            currentSessionId = null;
        }
    });
</script>
```

## 8. New Templates

### session_list.html
```html
{% extends "base.html" %}

{% block title %}Session Recordings{% endblock %}

{% block content %}
<h1 class="text-3xl font-semibold text-gray-800 mb-6">Session Recordings</h1>

<div class="bg-white shadow-md rounded-lg p-6">
    {% if sessions %}
        <div class="space-y-4">
            {% for session in sessions %}
                <div class="border-b pb-4">
                    <div class="flex justify-between items-start">
                        <div>
                            <h2 class="text-xl font-semibold">{{ session.name }}</h2>
                            <p class="text-gray-600">{{ session.description|default:"No description" }}</p>
                            <p class="text-sm text-gray-500">
                                Created: {{ session.created|date:"Y-m-d H:i" }} | 
                                Duration: {{ session.duration }}s | 
                                Frames: {{ session.frame_count }}
                            </p>
                        </div>
                        <div class="space-x-2">
                            <a href="{% url 'session_replay' session.uuid %}" 
                               class="bg-blue-500 hover:bg-blue-700 text-white px-3 py-1 rounded">
                                Replay
                            </a>
                            <a href="{% url 'session_detail' session.uuid %}" 
                               class="bg-gray-500 hover:bg-gray-700 text-white px-3 py-1 rounded">
                                Details
                            </a>
                            <a href="{% url 'session_delete' session.uuid %}" 
                               class="bg-red-500 hover:bg-red-700 text-white px-3 py-1 rounded">
                                Delete
                            </a>
                        </div>
                    </div>
                </div>
            {% endfor %}
        </div>
    {% else %}
        <p class="text-gray-600">No recordings found. Start a recording from the <a href="{% url 'pose_realtime' %}" class="text-blue-500 hover:underline">Pose page</a>.</p>
    {% endif %}
</div>
{% endblock %}
```

### session_replay.html
```html
{% extends "base.html" %}

{% block title %}Replay Session{% endblock %}

{% block content %}
<h1 class="text-3xl font-semibold text-gray-800 mb-4">Replay: {{ session.name }}</h1>

<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
    <!-- Main replay area -->
    <div class="lg:col-span-3">
        <div class="relative bg-black rounded-lg overflow-hidden" style="height: 600px;">
            <!-- Live webcam feed -->
            <img id="webcam-feed" src="{% url 'video_feed' %}" alt="Live webcam" 
                 class="absolute inset-0 w-full h-full object-cover">
            
            <!-- Pose overlay container -->
            <div id="pose-overlay" class="absolute inset-0"></div>
            
            <!-- Connection status -->
            <div id="connection-status" class="absolute top-4 left-4 text-white font-semibold bg-red-500 px-3 py-1 rounded">
                Connecting...
            </div>
        </div>
        
        <!-- Playback controls -->
        <div class="bg-gray-800 p-4 rounded-b-lg">
            <div class="flex items-center space-x-4">
                <button id="play-pause" class="bg-blue-500 hover:bg-blue-700 text-white px-4 py-2 rounded">
                    Play
                </button>
                <div class="flex-1">
                    <input type="range" id="timeline" min="0" max="{{ session.frame_count }}" value="0" 
                           class="w-full">
                    <div class="flex justify-between text-white text-sm mt-1">
                        <span id="current-time">00:00</span>
                        <span id="total-time">{{ session.duration }}s</span>
                    </div>
                </div>
                <div class="text-white">
                    Speed: 
                    <select id="playback-speed" class="bg-gray-700 px-2 py-1 rounded">
                        <option value="0.5">0.5x</option>
                        <option value="1" selected>1x</option>
                        <option value="1.5">1.5x</option>
                        <option value="2">2x</option>
                    </select>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Session info sidebar -->
    <div class="lg:col-span-1">
        <div class="bg-white shadow-md rounded-lg p-6">
            <h2 class="text-xl font-semibold mb-4">Session Info</h2>
            <div class="space-y-2 text-sm">
                <p><strong>Name:</strong> {{ session.name }}</p>
                <p><strong>Description:</strong> {{ session.description|default:"No description" }}</p>
                <p><strong>Created:</strong> {{ session.created|date:"Y-m-d H:i" }}</p>
                <p><strong>Duration:</strong> {{ session.duration }} seconds</p>
                <p><strong>Frames:</strong> {{ session.frame_count }}</p>
                <p><strong>Status:</strong> {{ session.status|title }}</p>
            </div>
            
            <div class="mt-6 space-y-2">
                <a href="{% url 'session_detail' session.uuid %}" 
                   class="block w-full bg-gray-500 hover:bg-gray-700 text-white px-4 py-2 rounded text-center">
                    Back to Details
                </a>
                <a href="{% url 'session_list' %}" 
                   class="block w-full bg-blue-500 hover:bg-blue-700 text-white px-4 py-2 rounded text-center">
                    All Sessions
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function () {
        const sessionId = "{{ session.uuid }}";
        const statusElement = document.getElementById('connection-status');
        const overlayElement = document.getElementById('pose-overlay');
        const playPauseBtn = document.getElementById('play-pause');
        const timeline = document.getElementById('timeline');
        const currentTimeEl = document.getElementById('current-time');
        const playbackSpeed = document.getElementById('playback-speed');
        
        let socket;
        let isPlaying = false;
        let currentFrame = 0;
        let scene, camera, renderer, poseLines, posePoints;
        
        // WebSocket setup for replay
        function connect() {
            const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
            const wsPath = wsScheme + '://' + window.location.host + `/ws/session/${sessionId}/`;
            
            socket = new WebSocket(wsPath);
            
            socket.onopen = function () {
                statusElement.textContent = 'Connected';
                statusElement.className = 'absolute top-4 left-4 text-white font-semibold bg-green-500 px-3 py-1 rounded';
            };
            
            socket.onclose = function () {
                statusElement.textContent = 'Disconnected';
                statusElement.className = 'absolute top-4 left-4 text-white font-semibold bg-red-500 px-3 py-1 rounded';
            };
            
            socket.onmessage = function (event) {
                const data = JSON.parse(event.data);
                if (data.type === 'frame_data') {
                    currentFrame = data.frame_number;
                    timeline.value = currentFrame;
                    currentTimeEl.textContent = formatTime(data.timestamp);
                    updatePose(data.pose_data);
                }
            };
        }
        
        // Initialize Three.js for pose overlay
        function initScene() {
           