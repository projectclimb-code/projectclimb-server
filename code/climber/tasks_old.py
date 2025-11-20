import asyncio
import websockets
import json
import time
import os
import numpy as np
from datetime import datetime, timezone, timedelta
from celery import shared_task
from django.contrib.auth.models import User
from django.conf import settings
from channels.db import database_sync_to_async
from loguru import logger
from climber.models import Session, Route, Wall, WallCalibration
from climber.tansformation_utils import apply_homography_to_mediapipe_json
from climber.svg_utils import parse_svg_file, get_hold_centers
from climber.calibration.calibration_utils import CalibrationUtils
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


# Import the CeleryTask model for database tracking
from .models import CeleryTask


@shared_task(bind=True)
def websocket_pose_session_tracker_task(self, wall_id, input_websocket_url, output_websocket_url,
                                     proximity_threshold=50.0, touch_duration=2.0,
                                     reconnect_delay=5.0, debug=False,
                                     no_stream_landmarks=False, stream_svg_only=False, 
                                     route_data=None, route_id=None):
    """
    Celery task that replicates WebSocket pose session tracker functionality.
    
    This task connects to an input WebSocket to receive MediaPipe pose data,
    transforms the landmarks using wall calibration,
    detects hold touches based on hand proximity to SVG paths,
    and outputs session data in the specified JSON format.
    
    Args:
        wall_id: ID of wall to use for calibration transformation
        input_websocket_url: WebSocket URL for receiving pose data
        output_websocket_url: WebSocket URL for sending session data
        proximity_threshold: Distance in pixels to consider hand near hold
        touch_duration: Time in seconds hand must be near hold to count as touch
        reconnect_delay: Delay between reconnection attempts in seconds
        debug: Enable debug output
        no_stream_landmarks: Skip streaming transformed landmarks in output
        stream_svg_only: Stream only SVG paths that are touched
        route_data: Route data as JSON string with holds specification
        route_id: Route ID to retrieve from database
    """
    try:
        # Store task reference for potential cancellation
        task_id = self.request.id
        
        # Create database record for this task
        CeleryTask.objects.update_or_create(
            task_id=task_id,
            task_name='WebSocket Pose Session Tracker',
            status='initializing',
            wall_id=wall_id,
            route_id=route_id
        )
        
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Initializing session tracker...'})
        
        # Parse route data if provided
        parsed_route_data = None
        if route_data:
            try:
                parsed_route_data = json.loads(route_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid route data JSON: {e}")
                return {'status': 'error', 'message': f'Invalid route data JSON: {e}'}
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                run_session_tracker(
                    self, wall_id, input_websocket_url, output_websocket_url,
                    proximity_threshold, touch_duration, reconnect_delay, debug,
                    no_stream_landmarks, stream_svg_only, parsed_route_data, route_id
                )
            )
            return result
        finally:
            loop.close()
            # Clean up task reference
            CeleryTask.objects.filter(task_id=task_id).update(status='stopped')
                
    except Exception as e:
        logger.error(f"Session tracker task failed: {e}")
        # Clean up task reference
        task_id = self.request.id
        if task_id in running_session_trackers:
            del running_session_trackers[task_id]
        return {'status': 'error', 'message': f'Task failed: {e}'}


async def run_session_tracker(task, wall_id, input_websocket_url, output_websocket_url,
                           proximity_threshold, touch_duration, reconnect_delay, debug,
                           no_stream_landmarks, stream_svg_only, route_data, route_id):
    """Run session tracker with WebSocket connections"""
    
    # Import classes from management command
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'management', 'commands'))
    
    from websocket_pose_session_tracker import (
        InputWebSocketClient, OutputWebSocketClient, SVGHoldDetector,
        SessionTracker, validate_pose_data, calculate_extended_hand_landmarks
    )
    
    try:
        # Create session tracker instance
        tracker = WebSocketPoseSessionTrackerCelery(
            wall_id=wall_id,
            input_websocket_url=input_websocket_url,
            output_websocket_url=output_websocket_url,
            proximity_threshold=proximity_threshold,
            touch_duration=touch_duration,
            reconnect_delay=reconnect_delay,
            debug=debug,
            no_stream_landmarks=no_stream_landmarks,
            stream_svg_only=stream_svg_only,
            route_data=route_data,
            route_id=route_id,
            task=task
        )
        
        # Update task status
        task.update_state(state='PROGRESS', meta={'status': 'Setting up session tracker...'})
        
        # Setup components
        if not await tracker.setup():
            return {'status': 'error', 'message': 'Setup failed'}
        
        # Update task status
        task.update_state(state='PROGRESS', meta={'status': 'Starting WebSocket connections...'})
        
        # Update database record
        CeleryTask.objects.filter(task_id=task.request.id).update(status='running')
        
        # Run tracker
        await tracker.run()
        
        # Update database record
        CeleryTask.objects.filter(task_id=task.request.id).update(status='completed')
        
        return {'status': 'success', 'message': 'Session tracker completed'}
        
    except Exception as e:
        logger.error(f"Error running session tracker: {e}")
        return {'status': 'error', 'message': f'Error running session tracker: {e}'}


class WebSocketPoseSessionTrackerCelery:
    """Celery-compatible version of WebSocketPoseSessionTracker"""
    
    def __init__(self, wall_id, input_websocket_url, output_websocket_url,
                 proximity_threshold=50.0, touch_duration=2.0,
                 reconnect_delay=5.0, debug=False,
                 no_stream_landmarks=False, stream_svg_only=False, route_data=None, route_id=None, task=None):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.proximity_threshold = proximity_threshold
        self.touch_duration = touch_duration
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        self.no_stream_landmarks = no_stream_landmarks
        self.stream_svg_only = stream_svg_only
        self.route_data = route_data
        self.route_id = route_id
        self.task = task  # Celery task instance for status updates
        
        # Components
        self.wall = None
        self.calibration = None
        self.calibration_utils = None
        self.transform_matrix = None
        self.hand_extension_percent = 20.0
        self.svg_parser = None
        self.hold_detector = None
        self.session_tracker = None
        
        # WebSocket clients
        self.input_client = None
        self.output_client = None
        
        # State
        self.running = False
        self.message_count = 0
        self.start_time = time.time()
        
    async def setup(self):
        """Setup all components"""
        # Load wall and calibration
        try:
            self.wall = await database_sync_to_async(Wall.objects.get)(id=self.wall_id)
            logger.info(f"Loaded wall: {self.wall.name}")
        except Wall.DoesNotExist:
            logger.error(f"Wall with ID {self.wall_id} not found")
            return False
        
        # Get active calibration
        try:
            self.calibration = await database_sync_to_async(
                lambda: self.wall.calibrations.filter(is_active=True).first()
            )()
            if not self.calibration:
                # Fallback to latest calibration
                self.calibration = await database_sync_to_async(
                    lambda: self.wall.calibrations.latest('created')
                )()
            logger.info(f"Loaded calibration: {self.calibration.name}")
        except WallCalibration.DoesNotExist:
            logger.error(f"No calibration found for wall {self.wall.name}")
            return False
        
        # Setup calibration utils
        self.calibration_utils = CalibrationUtils()
        
        # Extract transformation matrix from calibration
        if not self.calibration.perspective_transform:
            logger.error("No perspective transform found in calibration")
            return False
        
        try:
            self.transform_matrix = np.array(self.calibration.perspective_transform, dtype=np.float32)
            logger.info(f"Loaded transformation matrix: {self.transform_matrix}")
        except Exception as e:
            logger.error(f"Error loading transformation matrix: {e}")
            return False
        
        # Get hand extension percent from calibration
        self.hand_extension_percent = self.calibration.hand_extension_percent
        logger.info(f"Using hand extension percent: {self.hand_extension_percent}%")
        
        # Load SVG file
        try:
            if self.wall.svg_file:
                self.svg_parser = parse_svg_file(self.wall.svg_file.path)
                logger.info(f"Loaded SVG file: {self.wall.svg_file.path}")
            else:
                logger.error("No SVG file found for wall")
                return False
        except Exception as e:
            logger.error(f"Error loading SVG file: {e}")
            return False
        
        # Get route data (from parameter or database)
        if self.route_id:
            try:
                route = await database_sync_to_async(Route.objects.get)(id=self.route_id)
                logger.info(f"Loaded route from database: {route.name} (ID: {self.route_id})")
                
                # Convert route to expected format
                route_data = {
                    'grade': route.grade or '',
                    'author': route.author or '',
                    'problem': {
                        'holds': route.data.get('holds', []) if route.data else []
                    }
                }
            except Route.DoesNotExist:
                logger.error(f"Route with ID {self.route_id} not found")
                route_data = None
        else:
            route_data = self.route_data
        
        # Import SVGHoldDetector class
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'management', 'commands'))
        
        from websocket_pose_session_tracker import SVGHoldDetector
        
        # Setup hold detector with route filtering
        self.hold_detector = SVGHoldDetector(
            self.svg_parser,
            self.proximity_threshold,
            self.touch_duration,
            route_holds=self._extract_route_holds(route_data) if route_data else None,
            video_dimensions=(640, 480)  # Default video dimensions as specified
        )
        
        # Import SessionTracker class
        from websocket_pose_session_tracker import SessionTracker
        
        # Setup session tracker
        self.session_tracker = SessionTracker(self.wall_id, self.hold_detector)
        
        # Import WebSocket client classes
        from websocket_pose_session_tracker import (
            InputWebSocketClient, OutputWebSocketClient
        )
        
        # Setup WebSocket clients
        self.input_client = InputWebSocketClient(
            self.input_websocket_url,
            self.handle_pose_data,
            self.reconnect_delay
        )
        
        self.output_client = OutputWebSocketClient(
            self.output_websocket_url,
            self.reconnect_delay
        )
        
        return True
    
    def _extract_route_holds(self, route_data=None):
        """Extract hold IDs from route data"""
        if not route_data:
            route_data = self.route_data
        
        if not route_data or 'problem' not in route_data:
            return None
        
        problem = route_data['problem']
        if 'holds' not in problem:
            return None
        
        route_holds = {}
        for hold in problem['holds']:
            hold_id = hold.get('id')
            hold_type = hold.get('type', 'normal')
            if hold_id:
                route_holds[str(hold_id)] = hold_type
        
        logger.info(f"Loaded route with {len(route_holds)} holds: {list(route_holds.keys())}")
        return route_holds
    
    async def handle_pose_data(self, pose_data):
        """Handle incoming pose data"""
        try:
            # Update task status periodically
            if self.message_count % 100 == 0 and self.task:
                self.task.update_state(
                    state='PROGRESS', 
                    meta={
                        'status': f'Processing pose data... ({self.message_count} messages processed)',
                        'message_count': self.message_count,
                        'elapsed_time': time.time() - self.start_time
                    }
                )
            
            # Validate pose data
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'management', 'commands'))
            
            from websocket_pose_session_tracker import validate_pose_data
            is_valid, error_msg = validate_pose_data(pose_data)
            if not is_valid:
                logger.warning(f"Invalid pose data: {error_msg}")
                return
            
            # Apply transformation using calibration matrix
            transformed_data = apply_homography_to_mediapipe_json(
                pose_data.copy(), 
                self.transform_matrix
            )
            
            # Add extended hand landmarks
            from websocket_pose_session_tracker import calculate_extended_hand_landmarks
            landmarks = transformed_data.get('landmarks', [])
            if landmarks:
                extended_landmarks = calculate_extended_hand_landmarks(
                    landmarks, 
                    self.hand_extension_percent
                )
                
                # Add new landmarks to data
                if 'extended_hand_landmarks' not in transformed_data:
                    transformed_data['extended_hand_landmarks'] = []
                transformed_data['extended_hand_landmarks'].extend(extended_landmarks)
                
                # Also add them to main landmarks list for compatibility
                landmarks.extend(extended_landmarks)
                transformed_data['landmarks'] = landmarks
            
            # Update session with transformed landmarks
            session_data = self.session_tracker.update_session(landmarks)
            
            # Format output based on flags
            output_data = self.session_tracker.get_session_data(
                include_pose=not self.no_stream_landmarks,
                include_svg_paths=self.stream_svg_only
            )
            
            # Add pose data if included
            if not self.no_stream_landmarks:
                output_data['pose'] = landmarks
            
            # Send session data
            await self.send_session_data(output_data)
            
            self.message_count += 1
            
            if self.debug:
                logger.info(f"Processed pose data with {len(landmarks)} landmarks")
                
        except Exception as e:
            logger.error(f"Error handling pose data: {e}")
    
    async def send_session_data(self, session_data):
        """Send session data to output WebSocket"""
        await self.output_client.send_message(session_data)
        logger.debug(f"Sent session data")
    
    async def run(self):
        """Main event loop"""
        logger.info("Starting WebSocket pose session tracker...")
        self.running = True
        self.start_time = time.time()
        
        try:
            # Start WebSocket clients
            input_task = self.input_client.start()
            output_task = self.output_client.start()
            
            # Wait for tasks to complete (they should run indefinitely)
            await asyncio.gather(input_task, output_task)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            if self.task:
                self.task.update_state(
                    state='FAILURE', 
                    meta={'status': f'Error in main loop: {e}'}
                )
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up...")
        self.running = False
        
        if self.input_client:
            self.input_client.stop()
        
        if self.output_client:
            self.output_client.stop()
        
        # Give some time for tasks to complete properly
        await asyncio.sleep(0.1)
        
        # Log final statistics
        elapsed = time.time() - self.start_time
        logger.info(f"Processed {self.message_count} messages in {elapsed:.2f} seconds")
        if elapsed > 0:
            logger.info(f"Average rate: {self.message_count / elapsed:.2f} messages/second")
        
        logger.info("Cleanup complete")


@shared_task
def stop_session_tracker_task(task_id):
    """
    Stop a running session tracker task by ID.
    
    Args:
        task_id: ID of the task to stop
    """
    try:
        if task_id in running_session_trackers:
            tracker_info = running_session_trackers[task_id]
            tracker_info['status'] = 'stopping'
            
            # Revoke the task
            from celery import current_app
            current_app.control.revoke(task_id, terminate=True)
            
            # Remove from tracking
            del running_session_trackers[task_id]
            
            return {
                'status': 'success',
                'message': f'Session tracker task {task_id} stopped'
            }
        else:
            return {
                'status': 'error',
                'message': f'Session tracker task {task_id} not found'
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error stopping task: {e}'
        }


@shared_task
def get_running_session_trackers():
    """
    Get list of running session tracker tasks.
    
    Returns:
        Dictionary with running tracker information
    """
    try:
        # Get all running tasks from database
        running_tasks = CeleryTask.objects.filter(status__in=['initializing', 'running'])
        
        trackers = {}
        for task in running_tasks:
            # Calculate elapsed time
            elapsed_time = None
            if task.started_at:
                elapsed_time = (datetime.now() - task.started_at).total_seconds()
            
            trackers[task.task_id] = {
                'task_id': task.task_id,
                'task_name': task.task_name,
                'wall_id': task.wall_id,
                'route_id': task.route_id,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'status': task.status,
                'elapsed_time': elapsed_time
            }
        
        return {
            'status': 'success',
            'trackers': trackers
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error getting running trackers: {e}'
        }