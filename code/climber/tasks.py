import asyncio
import websockets
import json
import time
from datetime import datetime, timedelta
from celery import shared_task
from django.contrib.auth.models import User
from climber.models import Session, Route
import uuid


@shared_task(bind=True)
def send_fake_session_data_task(self, session_id=None, ws_url='ws://localhost:8000/ws/session-live/', duration=60, create_session=False):
    """
    Celery task to send fake session data to WebSocket for testing.
    
    Args:
        session_id: UUID of the session to send data for (creates a new one if not provided)
        ws_url: WebSocket URL to connect to
        duration: Duration of the fake session in seconds
        create_session: Whether to create a new session in the database
    """
    try:
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Initializing session...'})
        
        if create_session or not session_id:
            # Create a new session
            try:
                user = User.objects.first()
                if not user:
                    return {'status': 'error', 'message': 'No users found in the database'}
                
                route = Route.objects.first()
                
                session = Session.objects.create(
                    user=user,
                    route=route,
                    start_time=datetime.now(),
                    status='started'
                )
                session_id = str(session.uuid)
            except Exception as e:
                return {'status': 'error', 'message': f'Failed to create session: {e}'}
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_fake_data(ws_url, session_id, duration, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        return {'status': 'error', 'message': f'Task failed: {e}'}


async def send_fake_data(ws_url, session_id, duration, task):
    """Send fake session data to WebSocket"""
    full_ws_url = f"{ws_url}{session_id}/"
    
    fake_climb_data = {
        "climb": {
            "holds": [
                {"id": "17", "type": "start", "status": "completed", "time": "2025-01-01T12:00:02.000Z"},
                {"id": "91", "type": "start", "status": "completed", "time": "2025-01-01T12:00:23.000Z"},
                {"id": "6",  "type": "normal", "status": "completed", "time": "2025-01-01T12:00:33.000Z"},
                {"id": "101","type": "normal", "status": "completed", "time": "2025-01-01T12:00:43.000Z"},
                {"id": "55", "type": "normal", "status": "completed", "time": "2025-01-01T12:00:53.000Z"},
                {"id": "133","type": "normal", "status": "untouched", "time": None},
                {"id": "89", "type": "normal", "status": "untouched", "time": None},
                {"id": "41", "type": "normal", "status": "untouched", "time": None},
                {"id": "72", "type": "finish", "status": "untouched", "time": None},
                {"id": "11", "type": "finish", "status": "untouched", "time": None}
            ],
            "startTime": "2025-10-19T17:44:37.187Z",
            "endTime": None,
            "status": "started"
        },
        "pose": []
    }
    
    try:
        # Update task status
        task.update_state(state='PROGRESS', meta={'status': f'Connecting to WebSocket: {full_ws_url}'})
        
        async with websockets.connect(full_ws_url) as websocket:
            task.update_state(state='PROGRESS', meta={'status': 'Connected to WebSocket'})
            
            # Send initial session data
            await websocket.send(json.dumps({
                'type': 'session_update',
                'status': 'started',
                'start_time': datetime.now().isoformat()
            }))
            
            # Send initial climb data
            await websocket.send(json.dumps({
                'type': 'climb_update',
                'climb': fake_climb_data['climb']
            }))
            
            start_time = time.time()
            update_interval = 2  # Send updates every 2 seconds
            
            # Simulate progress over time
            completed_holds = 0
            total_holds = len(fake_climb_data['climb']['holds'])
            
            while time.time() - start_time < duration:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Update a hold status every few seconds
                if elapsed > 0 and int(elapsed) % 5 == 0 and completed_holds < total_holds:
                    # Find the next untouched hold
                    for i, hold in enumerate(fake_climb_data['climb']['holds']):
                        if hold['status'] == 'untouched':
                            hold['status'] = 'completed'
                            hold['time'] = (datetime.now() + timedelta(seconds=i)).isoformat() + 'Z'
                            completed_holds += 1
                            break
                    
                    # Send updated climb data
                    await websocket.send(json.dumps({
                        'type': 'climb_update',
                        'climb': fake_climb_data['climb']
                    }))
                    
                    # Update task progress
                    progress = int((elapsed / duration) * 100)
                    task.update_state(
                        state='PROGRESS', 
                        meta={
                            'status': f'Updated climb data: {completed_holds}/{total_holds} holds completed',
                            'progress': progress,
                            'elapsed': elapsed,
                            'duration': duration
                        }
                    )
                
                # Send fake pose data occasionally
                if int(elapsed) % 3 == 0:
                    fake_pose_data = [
                        {'x': 0.5, 'y': 0.3, 'z': 0.2, 'visibility': 0.9},
                        {'x': 0.4, 'y': 0.4, 'z': 0.1, 'visibility': 0.8},
                        # Add more pose landmarks as needed
                    ]
                    
                    await websocket.send(json.dumps({
                        'type': 'pose_update',
                        'pose': fake_pose_data
                    }))
                
                await asyncio.sleep(update_interval)
            
            # Final update - mark session as completed
            fake_climb_data['climb']['endTime'] = datetime.now().isoformat() + 'Z'
            fake_climb_data['climb']['status'] = 'completed'
            
            await websocket.send(json.dumps({
                'type': 'climb_update',
                'climb': fake_climb_data['climb']
            }))
            
            await websocket.send(json.dumps({
                'type': 'session_update',
                'status': 'completed',
                'end_time': datetime.now().isoformat()
            }))
            
            task.update_state(state='SUCCESS', meta={'status': 'Fake session data sent successfully'})
            return {
                'status': 'success',
                'message': 'Fake session data sent successfully',
                'session_id': session_id,
                'duration': duration
            }
            
    except websockets.exceptions.ConnectionRefused:
        return {'status': 'error', 'message': 'Connection refused. Make sure the Django server is running.'}
    except Exception as e:
        return {'status': 'error', 'message': f'Error: {e}'}