import asyncio
import websockets
import json
import time
from datetime import datetime, timedelta
from celery import shared_task
from django.contrib.auth.models import User
from climber.models import Session, Route, CeleryTask
from channels.db import database_sync_to_async
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


@shared_task(bind=True)
def websocket_pose_session_tracker_task(self, wall_id=1, input_websocket_url="ws://localhost:8011/ws/pose/",
                                       output_websocket_url="ws://localhost:8011/ws/holds/",
                                       proximity_threshold=50.0, touch_duration=2.0,
                                       reconnect_delay=5.0, debug=False,
                                       no_stream_landmarks=False, stream_svg_only=False,
                                       route_data=None, route_id=None):
    """
    Celery task to run WebSocket pose session tracker with hold detection for climbing walls.
    
    This task connects to an input WebSocket to receive MediaPipe pose data,
    transforms the landmarks using wall calibration,
    detects hold touches based on hand proximity to SVG paths,
    and outputs session data to an output WebSocket.
    
    Args:
        wall_id: ID of wall to use for calibration transformation
        input_websocket_url: WebSocket URL for receiving pose data
        output_websocket_url: WebSocket URL for sending session data
        proximity_threshold: Distance in pixels to consider hand near hold (default: 50.0)
        touch_duration: Time in seconds hand must be near hold to count as touch (default: 2.0)
        reconnect_delay: Delay between reconnection attempts in seconds (default: 5.0)
        debug: Enable debug output (default: False)
        no_stream_landmarks: Skip streaming transformed landmarks in output (default: False)
        stream_svg_only: Stream only SVG paths that are touched (default: False)
        route_data: Route data as JSON string with holds specification (default: None)
        route_id: Route ID to retrieve from database (default: None)
    """
    try:
        # Import here to avoid circular imports
        from loguru import logger
        from climber.management.commands.websocket_pose_session_tracker import WebSocketPoseSessionTracker
        import json
        
        # Create task record in database
        try:
            CeleryTask.objects.update_or_create(
                task_id=self.request.id,
                defaults={
                    'task_name': 'websocket_pose_session_tracker_task',
                    'status': 'PENDING'
                }
            )
        except Exception as e:
            logger.error(f"Failed to create task record: {e}")
        
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Initializing WebSocket pose session tracker...'})
        
        # Parse route data if provided
        parsed_route_data = None
        if route_data:
            try:
                parsed_route_data = json.loads(route_data)
                logger.info(f"Loaded route data: {parsed_route_data}")
            except json.JSONDecodeError as e:
                error_msg = f"Invalid route data JSON: {e}"
                logger.error(error_msg)
                return {'status': 'error', 'message': error_msg}
        
        # Create and configure session tracker
        tracker = WebSocketPoseSessionTracker(
            wall_id=wall_id,
            input_websocket_url=input_websocket_url,
            output_websocket_url=output_websocket_url,
            proximity_threshold=proximity_threshold,
            touch_duration=touch_duration,
            reconnect_delay=reconnect_delay,
            debug=debug,
            no_stream_landmarks=no_stream_landmarks,
            stream_svg_only=stream_svg_only,
            route_data=parsed_route_data,
            route_id=route_id
        )
        
        # Update task status in database
        try:
            CeleryTask.objects.filter(task_id=self.request.id).update(status='PROGRESS')
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
        
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Setting up components...'})
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run the async tracker function
            result = loop.run_until_complete(run_tracker_with_progress(tracker, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        error_msg = f'WebSocket pose session tracker task failed: {e}'
        logger.error(error_msg)
        
        # Update task status in database
        if hasattr(self, 'request') and self.request:
            try:
                CeleryTask.objects.filter(task_id=self.request.id).update(status='FAILURE')
            except Exception as e:
                logger.error(f"Failed to update task status: {e}")
        
        return {'status': 'error', 'message': error_msg}


async def run_tracker_with_progress(tracker, task):
    """
    Run the WebSocket pose session tracker with progress monitoring.
    
    Args:
        tracker: WebSocketPoseSessionTracker instance
        task: Celery task instance for progress updates
        
    Returns:
        Result dictionary with status and statistics
    """
    from loguru import logger
    
    try:
        # Setup the tracker
        task.update_state(state='PROGRESS', meta={'status': 'Setting up tracker components...'})
        
        # Update task status in database (skip for now to avoid async issues)
        # await update_task_status('PROGRESS')
        
        setup_success = await tracker.setup()
        if not setup_success:
            # Update task status in database (skip for now to avoid async issues)
            # await update_task_status('FAILURE')
            return {'status': 'error', 'message': 'Failed to setup session tracker'}
        
        task.update_state(state='PROGRESS', meta={'status': 'Starting WebSocket connections...'})
        
        # Update task status in database (skip for now to avoid async issues)
        # await update_task_status('PROGRESS')
        
        # Start WebSocket clients
        input_task = tracker.input_client.start()
        output_task = tracker.output_client.start()
        
        # Monitor progress while tasks are running
        start_time = time.time()
        last_progress_update = start_time
        
        # Create a task to monitor progress
        async def monitor_progress():
            while tracker.running:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Update progress every 10 seconds
                if current_time - last_progress_update >= 10:
                    progress_data = {
                        'status': f'Tracking session... {tracker.message_count} messages processed',
                        'elapsed': elapsed,
                        'message_count': tracker.message_count,
                        'rate': tracker.message_count / elapsed if elapsed > 0 else 0
                    }
                    
                    task.update_state(state='PROGRESS', meta=progress_data)
                    last_progress_update = current_time
                
                await asyncio.sleep(1)
        
        # Start progress monitoring
        monitor_task = asyncio.create_task(monitor_progress())
        
        try:
            # Wait for tasks to complete (they should run indefinitely until stopped)
            await asyncio.gather(input_task, output_task)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            tracker.session_tracker.end_session()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
            # Update task status in database (skip for now to avoid async issues)
            # await update_task_status('FAILURE')
            
            return {'status': 'error', 'message': f'Error in tracker: {e}'}
        finally:
            # Cancel progress monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup
        await tracker.cleanup()
        
        # Calculate final statistics
        elapsed = time.time() - start_time
        final_stats = {
            'status': 'success',
            'message': 'WebSocket pose session tracker completed successfully',
            'wall_id': tracker.wall_id,
            'message_count': tracker.message_count,
            'elapsed_time': elapsed,
            'average_rate': tracker.message_count / elapsed if elapsed > 0 else 0
        }
        
        task.update_state(state='SUCCESS', meta=final_stats)
        
        # Update task status in database (skip for now to avoid async issues)
        # await update_task_status('SUCCESS')
        
        return final_stats
        
    except Exception as e:
        error_msg = f'Error running tracker: {e}'
        logger.error(error_msg)
        
        # Update task status in database (skip for now to avoid async issues)
        # await update_task_status('FAILURE')
        
        return {'status': 'error', 'message': error_msg}


@shared_task(bind=True)
def stop_celery_task(self, task_id):
    """
    Stop a running Celery task.
    
    Args:
        task_id: ID of the task to stop
        
    Returns:
        Result dictionary with status and message
    """
    try:
        from celery.result import AsyncResult
        from loguru import logger
        
        # Get the task result
        result = AsyncResult(task_id)
        
        if result.state in ['PENDING', 'PROGRESS', 'RETRY']:
            # Try to revoke the task
            result.revoke(terminate=True)
            
            # Update task status in database
            try:
                CeleryTask.objects.filter(task_id=task_id).update(status='REVOKED')
            except Exception as e:
                logger.error(f"Failed to update task status in database: {e}")
            
            logger.info(f"Task {task_id} revoked successfully")
            return {
                'status': 'success',
                'message': f'Task {task_id} stopped successfully'
            }
        else:
            return {
                'status': 'error',
                'message': f'Task {task_id} is not running (status: {result.state})'
            }
            
    except Exception as e:
        error_msg = f'Failed to stop task {task_id}: {e}'
        logger.error(error_msg)
        return {'status': 'error', 'message': error_msg}