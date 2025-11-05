from channels.generic.websocket import AsyncWebsocketConsumer
import json
import asyncio
from channels.db import database_sync_to_async
from .models import SessionRecording, SessionFrame, Session

class PoseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'pose_stream'
        self.recording_session = None
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        print("WebSocket connection established.")

    async def disconnect(self, close_code):
        # Stop any active recording
        if self.recording_session:
            await self.stop_recording()
            
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"WebSocket connection closed: {close_code}")

    # Receive message from WebSocket (from the streamer)
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
        """Start a new recording session"""
        from django.contrib.auth.models import AnonymousUser
        
        # Get user from scope (if authenticated)
        user = self.scope.get('user')
        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            # For now, create a default user or handle anonymous sessions
            # In production, you'd require authentication
            from django.contrib.auth.models import User
            try:
                user = await database_sync_to_async(User.objects.first)()
                if not user:
                    # Create a default user if none exists
                    user = await database_sync_to_async(User.objects.create)(
                        username='default_user',
                        email='default@example.com'
                    )()
            except Exception:
                # If we can't get or create a user, send an error message
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Authentication required for recording'
                }))
                return
        
        # Create new session recording
        self.recording_session = await database_sync_to_async(SessionRecording.objects.create)(
            name=data.get('name', 'Untitled Session'),
            description=data.get('description', ''),
            user=user,
            status='recording'
        )
        
        await self.send(text_data=json.dumps({
            'type': 'recording_started',
            'session_id': str(self.recording_session.uuid)
        }))
        print(f"Started recording session: {self.recording_session.uuid}")

    async def stop_recording(self):
        """Stop the current recording session"""
        if self.recording_session:
            self.recording_session.status = 'completed'
            await database_sync_to_async(self.recording_session.save)()
            
            session_id = str(self.recording_session.uuid)
            self.recording_session = None
            
            await self.send(text_data=json.dumps({
                'type': 'recording_stopped',
                'session_id': session_id
            }))
            print(f"Stopped recording session: {session_id}")

    async def handle_pose_data(self, data):
        """Handle incoming pose data"""
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

    @database_sync_to_async
    def store_frame(self, data):
        """Store a frame in the database"""
        SessionFrame.objects.create(
            session=self.recording_session,
            timestamp=data.get('timestamp', 0),
            frame_number=data.get('frame_number', 0),
            pose_data=data.get('landmarks', [])
        )

    # Receive message from room group (to send to the web client)
    async def pose_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=message)


class SessionReplayConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'session_replay_{self.session_id}'
        self.is_playing = False
        self.current_frame = 0
        self.playback_speed = 1.0
        
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
            self.is_playing = True
            await self.start_replay()
        elif data.get('type') == 'pause':
            self.is_playing = False
        elif data.get('type') == 'seek':
            self.current_frame = data.get('frame_number', 0)
            await self.seek_to_frame(self.current_frame)
        elif data.get('type') == 'set_speed':
            self.playback_speed = data.get('speed', 1.0)

    async def start_replay(self):
        """Start streaming the session frames"""
        from channels.db import database_sync_to_async
        
        # Get session frames from database
        frames = await database_sync_to_async(
            lambda: list(SessionFrame.objects.filter(
                session__uuid=self.session_id
            ).order_by('frame_number').values(
                'frame_number', 'timestamp', 'pose_data'
            ))
        )()
        
        if not frames:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'No frames found for this session'
            }))
            return
        
        # Start from current frame
        start_index = next((i for i, f in enumerate(frames) if f['frame_number'] >= self.current_frame), 0)
        
        for frame in frames[start_index:]:
            if not self.is_playing:
                break
                
            self.current_frame = frame['frame_number']
            
            await self.send(text_data=json.dumps({
                'type': 'frame_data',
                'frame_number': frame['frame_number'],
                'timestamp': frame['timestamp'],
                'pose_data': frame['pose_data']
            }))
            
            # Calculate delay based on playback speed
            # Default to ~30fps if no timestamp
            delay = 0.033 / self.playback_speed
            if frame['timestamp']:
                # Use actual timestamp difference
                if frame['frame_number'] > 0:
                    prev_frame = frames[frame['frame_number'] - 1]
                    if prev_frame and prev_frame['timestamp']:
                        delay = (frame['timestamp'] - prev_frame['timestamp']) / self.playback_speed
            
            await asyncio.sleep(delay)

    async def seek_to_frame(self, frame_number):
        """Seek to a specific frame number"""
        from channels.db import database_sync_to_async
        
        try:
            frame = await database_sync_to_async(
                SessionFrame.objects.get(
                    session__uuid=self.session_id,
                    frame_number=frame_number
                )
            )()
            
            await self.send(text_data=json.dumps({
                'type': 'frame_data',
                'frame_number': frame.frame_number,
                'timestamp': frame.timestamp,
                'pose_data': frame.pose_data
            }))
        except SessionFrame.DoesNotExist:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Frame {frame_number} not found'
            }))


class TestPoseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'test_pose_stream'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        print("WebSocket connection established.")

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"WebSocket connection closed: {close_code}")

    # Receive message from WebSocket (from the streamer)
    async def receive(self, text_data):
        # Broadcast the received data to the web client group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'pose_message',
                'message': text_data
            }
        )

    # Receive message from room group (to send to the web client)
    async def pose_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=message)


class SessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'session_{self.session_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.session_group_name,
            self.channel_name
        )
        await self.accept()
        print(f"Session WebSocket connection established for session {self.session_id}")

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.session_group_name,
            self.channel_name
        )
        print(f"Session WebSocket connection closed: {close_code}")

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Handle different message types
        if data.get('type') == 'session_update':
            await self.handle_session_update(data)
        elif data.get('type') == 'climb_update':
            await self.handle_climb_update(data)
        elif data.get('type') == 'pose_update':
            await self.handle_pose_update(data)
        else:
            # Broadcast any other messages to the session group
            await self.channel_layer.group_send(
                self.session_group_name,
                {
                    'type': 'session_message',
                    'message': json.dumps(data)
                }
            )

    async def handle_session_update(self, data):
        """Handle session status updates"""
        from channels.db import database_sync_to_async
        
        try:
            session = await database_sync_to_async(Session.objects.get)(uuid=self.session_id)
            
            # Update session fields based on data
            if 'status' in data:
                session.status = data['status']
            if 'end_time' in data:
                from datetime import datetime
                if data['end_time']:
                    session.end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            
            await database_sync_to_async(session.save)()
            
            # Broadcast the update to all clients
            await self.channel_layer.group_send(
                self.session_group_name,
                {
                    'type': 'session_message',
                    'message': json.dumps({
                        'type': 'session_updated',
                        'session_id': self.session_id,
                        'status': session.status,
                        'end_time': session.end_time.isoformat() if session.end_time else None
                    })
                }
            )
        except Session.DoesNotExist:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Session {self.session_id} not found'
            }))

    async def handle_climb_update(self, data):
        """Handle climb progress updates"""
        from channels.db import database_sync_to_async
        
        try:
            session = await database_sync_to_async(Session.objects.get)(uuid=self.session_id)
            
            # Update climb data
            if 'climb' in data:
                session.climb_data = data['climb']
                await database_sync_to_async(session.save)()
            
            # Broadcast the update to all clients
            await self.channel_layer.group_send(
                self.session_group_name,
                {
                    'type': 'session_message',
                    'message': json.dumps({
                        'type': 'climb_updated',
                        'session_id': self.session_id,
                        'climb': data.get('climb', {})
                    })
                }
            )
        except Session.DoesNotExist:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Session {self.session_id} not found'
            }))

    async def handle_pose_update(self, data):
        """Handle pose data updates"""
        # Broadcast pose data to all clients in the session
        await self.channel_layer.group_send(
            self.session_group_name,
            {
                'type': 'session_message',
                'message': json.dumps({
                    'type': 'pose_updated',
                    'session_id': self.session_id,
                    'pose': data.get('pose', [])
                })
            }
        )

    # Receive message from room group (to send to the web client)
    async def session_message(self, event):
        message = event['message']
        
        # Send message to WebSocket
        await self.send(text_data=message)


class RelayConsumer(AsyncWebsocketConsumer):
    """
    Simple WebSocket consumer that relays all received messages to all connected clients.
    This creates a simple chat/broadcast system where any message sent by any client
    is broadcast to all other connected clients.
    """
    async def connect(self):
        self.room_group_name = 'relay_broadcast'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        print(f"Relay WebSocket connection established: {self.channel_name}")

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"Relay WebSocket connection closed: {self.channel_name} - {close_code}")

    async def receive(self, text_data):
        """
        Receive message from WebSocket and relay it to all connected clients.
        """
        # Broadcast the received data to all clients in the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'relay_message',
                'message': text_data,
                'sender': self.channel_name
            }
        )

    async def relay_message(self, event):
        """
        Receive message from room group and send it to WebSocket.
        """
        message = event['message']
        sender = event.get('sender', 'unknown')
        
        # Send message to WebSocket
        await self.send(text_data=message)

    # Handler for pose touch messages from management command
    async def pose_touch_message(self, event):
        """Handle pose touch updates from the pose touch detector"""
        message = event['message']
        
        # Send touch update to WebSocket
        await self.send(text_data=json.dumps(message))

    # Receive message from room group (to send to the web client)
    async def session_message(self, event):
        message = event['message']
        
        # Send message to WebSocket
        await self.send(text_data=message)




# for debuging, pose from poseconsumer, transformed according to wall calibration
class TransformedPoseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'transformed_pose_stream'
        self.recording_session = None
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        print("WebSocket connection established.")

    async def disconnect(self, close_code):
        # Stop any active recording
        if self.recording_session:
            await self.stop_recording()
            
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"WebSocket connection closed: {close_code}")

    # Receive message from WebSocket (from the streamer)
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Handle recording commands
        if data.get('type') == 'start_recording_off':
            await self.start_recording(data)
        elif data.get('type') == 'stop_recording_off':
            await self.stop_recording()
        else:
            # Regular pose data
            await self.handle_pose_data(data)

    async def start_recording(self, data):
        """Start a new recording session"""
        from django.contrib.auth.models import AnonymousUser
        
        # Get user from scope (if authenticated)
        user = self.scope.get('user')
        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            # For now, create a default user or handle anonymous sessions
            # In production, you'd require authentication
            from django.contrib.auth.models import User
            try:
                user = await database_sync_to_async(User.objects.first)()
                if not user:
                    # Create a default user if none exists
                    user = await database_sync_to_async(User.objects.create)(
                        username='default_user',
                        email='default@example.com'
                    )()
            except Exception:
                # If we can't get or create a user, send an error message
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Authentication required for recording'
                }))
                return
        
        # Create new session recording
        self.recording_session = await database_sync_to_async(SessionRecording.objects.create)(
            name=data.get('name', 'Untitled Session'),
            description=data.get('description', ''),
            user=user,
            status='recording'
        )
        
        await self.send(text_data=json.dumps({
            'type': 'recording_started',
            'session_id': str(self.recording_session.uuid)
        }))
        print(f"Started recording session: {self.recording_session.uuid}")

    async def stop_recording(self):
        """Stop the current recording session"""
        if self.recording_session:
            self.recording_session.status = 'completed'
            await database_sync_to_async(self.recording_session.save)()
            
            session_id = str(self.recording_session.uuid)
            self.recording_session = None
            
            await self.send(text_data=json.dumps({
                'type': 'recording_stopped',
                'session_id': session_id
            }))
            print(f"Stopped recording session: {session_id}")

    async def handle_pose_data(self, data):
        """Handle incoming pose data"""

        # Broadcast to all clients
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'pose_message',
                'message': json.dumps(data)
            }
        )


    # Receive message from room group (to send to the web client)
    async def pose_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=message)