"""
Management command to track climbing sessions with hold detection.

This command connects to an input WebSocket to receive MediaPipe pose landmarks from phone_camera.html,
transforms them according to wall calibration, detects hold touches based on hand proximity,
and outputs session data in the specified JSON format.

2025-11-03 19:00
"""

import os
import json
import time
import asyncio
import argparse
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Tuple, List

import websockets
import numpy as np
from loguru import logger
from django.core.management.base import BaseCommand
from django.conf import settings
from channels.db import database_sync_to_async

from climber.models import Wall, WallCalibration, Hold
from climber.calibration.calibration_utils import CalibrationUtils
from climber.svg_utils import parse_svg_file, get_hold_centers


class InputWebSocketClient:
    """WebSocket client for receiving MediaPipe pose data from phone camera"""
    
    def __init__(self, url, message_handler, reconnect_delay=5.0):
        self.url = url
        self.message_handler = message_handler
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        
    async def connect(self):
        """Connect to input WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to input WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to input WebSocket")
                self.current_reconnect_delay = self.reconnect_delay  # Reset delay on success
                
                # Listen for messages
                await self.listen_for_messages()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"Input WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
            except Exception as e:
                logger.error(f"Unexpected error in input WebSocket: {e}")
                if self.running:
                    await self._wait_and_reconnect()
    
    async def _wait_and_reconnect(self):
        """Wait with exponential backoff before reconnecting"""
        logger.info(f"Reconnecting in {self.current_reconnect_delay} seconds...")
        await asyncio.sleep(self.current_reconnect_delay)
        self.current_reconnect_delay = min(self.current_reconnect_delay * 2, 60.0)  # Cap at 60 seconds
    
    async def listen_for_messages(self):
        """Listen for incoming messages and pass to handler"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.message_handler(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Input WebSocket connection closed")
            raise
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            raise
    
    def start(self):
        """Start WebSocket client"""
        self.running = True
        return asyncio.create_task(self.connect())
    
    def stop(self):
        """Stop WebSocket client"""
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())


class OutputWebSocketClient:
    """WebSocket client for sending session data"""
    
    def __init__(self, url, reconnect_delay=5.0):
        self.url = url
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        self.message_queue = asyncio.Queue()
        self.sender_task = None
        
    async def connect(self):
        """Connect to output WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to output WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to output WebSocket")
                self.current_reconnect_delay = self.reconnect_delay  # Reset delay on success
                
                # Start sender task
                self.sender_task = asyncio.create_task(self.message_sender())
                
                # Keep connection alive
                await self.keep_alive()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"Output WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
            except Exception as e:
                logger.error(f"Unexpected error in output WebSocket: {e}")
                if self.running:
                    await self._wait_and_reconnect()
    
    async def _wait_and_reconnect(self):
        """Wait with exponential backoff before reconnecting"""
        logger.info(f"Reconnecting in {self.current_reconnect_delay} seconds...")
        await asyncio.sleep(self.current_reconnect_delay)
        self.current_reconnect_delay = min(self.current_reconnect_delay * 2, 60.0)  # Cap at 60 seconds
    
    async def keep_alive(self):
        """Keep connection alive with periodic pings"""
        try:
            while self.running and self.websocket:
                await asyncio.sleep(30)  # Ping every 30 seconds
                if self.websocket:
                    await self.websocket.ping()
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Output WebSocket connection closed during keep-alive")
            raise
    
    async def message_sender(self):
        """Send queued messages to WebSocket"""
        while self.running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                if self.websocket:
                    try:
                        await self.websocket.send(json.dumps(message))
                        
                        logger.debug(f"Sent message: {type(message)}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Output WebSocket connection closed while sending message")
                        # Re-queue message
                        await self.message_queue.put(message)
                        raise
                    
            except asyncio.TimeoutError:
                continue  # No message to send, continue loop
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Output WebSocket connection closed while sending")
                # Re-queue message
                await self.message_queue.put(message)
                raise
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                # Re-queue message
                await self.message_queue.put(message)
    
    async def send_message(self, message):
        """Queue a message to be sent"""
        await self.message_queue.put(message)
    
    def start(self):
        """Start WebSocket client"""
        self.running = True
        return asyncio.create_task(self.connect())
    
    def stop(self):
        """Stop WebSocket client"""
        self.running = False
        if self.sender_task:
            self.sender_task.cancel()
        if self.websocket:
            asyncio.create_task(self.websocket.close())


class HoldDetector:
    """Detects hold touches based on hand proximity to hold paths"""
    
    def __init__(self, hold_centers: Dict[str, Tuple[float, float]], 
                 proximity_threshold: float = 50.0, 
                 touch_duration: float = 2.0):
        """
        Initialize hold detector
        
        Args:
            hold_centers: Dictionary mapping hold IDs to center coordinates
            proximity_threshold: Distance in pixels to consider hand near hold
            touch_duration: Time in seconds hand must be near hold to count as touch
        """
        self.hold_centers = hold_centers
        self.proximity_threshold = proximity_threshold
        self.touch_duration = touch_duration
        
        # Track hold touch state
        self.hold_touch_start_times = {}  # hold_id -> timestamp when touch started
        self.hold_status = {}  # hold_id -> status ('untouched', 'completed')
        
        # MediaPipe landmark indices for hands
        self.left_hand_indices = [19, 20, 21]  # Left wrist, thumb, index
        self.right_hand_indices = [22, 23, 24]  # Right wrist, thumb, index
    
    def detect_holds_touched(self, transformed_landmarks: List[Dict]) -> Dict[str, str]:
        """
        Detect which holds are being touched based on hand landmarks
        
        Args:
            transformed_landmarks: List of transformed pose landmarks
            
        Returns:
            Dictionary of hold_id -> status changes
        """
        if not transformed_landmarks:
            logger.debug("No transformed landmarks available")
            return {}
        
        # Extract hand positions
        left_hand_pos = self._get_hand_position(transformed_landmarks, self.left_hand_indices)
        right_hand_pos = self._get_hand_position(transformed_landmarks, self.right_hand_indices)
        
        # Debug output for hand positions
        logger.debug(f"Left hand position: {left_hand_pos}")
        logger.debug(f"Right hand position: {right_hand_pos}")
        logger.debug(f"Available landmarks: {len(transformed_landmarks)}")
        
        current_time = time.time()
        status_changes = {}
        
        # Debug output for hold centers
        if len(self.hold_centers) < 10:  # Only log if not too many holds
            logger.debug(f"Hold centers: {dict(list(self.hold_centers.items())[:5])}")  # Log first 5 holds
        
        # Check each hold for proximity to hands
        for hold_id, hold_center in self.hold_centers.items():
            # Calculate distances for debugging
            left_dist = self._distance(left_hand_pos, hold_center) if left_hand_pos else float('inf')
            right_dist = self._distance(right_hand_pos, hold_center) if right_hand_pos else float('inf')
            min_dist = min(left_dist, right_dist)
            
            # Debug output for proximity calculations
            if min_dist < float('inf'):
                logger.debug(f"Hold {hold_id} - center: {hold_center}, left_dist: {left_dist:.2f}, right_dist: {right_dist:.2f}, min_dist: {min_dist:.2f}, threshold: {self.proximity_threshold}")
            else:
                logger.debug(f"Hold {hold_id} - center: {hold_center}, no hand positions available")
            
            is_near_left = left_hand_pos and left_dist < self.proximity_threshold
            is_near_right = right_hand_pos and right_dist < self.proximity_threshold
            is_near_any_hand = is_near_left or is_near_right
            
            current_status = self.hold_status.get(hold_id, 'untouched')
            
            if is_near_any_hand:
                # Hand is near the hold
                logger.debug(f"Hold {hold_id} NEAR - threshold: {self.proximity_threshold}")
                if hold_id not in self.hold_touch_start_times:
                    # Just started touching this hold
                    self.hold_touch_start_times[hold_id] = current_time
                    logger.debug(f"Hold {hold_id} touch started at {current_time}")
                elif current_time - self.hold_touch_start_times[hold_id] >= self.touch_duration:
                    # Has been touching long enough to count as completed
                    if current_status == 'untouched':
                        self.hold_status[hold_id] = 'completed'
                        status_changes[hold_id] = 'completed'
                        logger.info(f"Hold {hold_id} completed after {self.touch_duration}s touch")
                else:
                    # Touching but not long enough yet
                    touch_time = current_time - self.hold_touch_start_times[hold_id]
                    logger.debug(f"Hold {hold_id} touching for {touch_time:.2f}s (need {self.touch_duration}s)")
            else:
                # Hand is not near the hold
                if hold_id in self.hold_touch_start_times:
                    # Was touching but now stopped
                    del self.hold_touch_start_times[hold_id]
                    logger.debug(f"Hold {hold_id} touch stopped")
        
        # Debug summary of completed holds
        if status_changes and self.debug:
            completed_holds = [hold_id for hold_id, status in status_changes.items() if status == 'completed']
            if completed_holds:
                logger.debug(f"Holds completed this frame: {completed_holds}")
        
        return status_changes
    
    def _get_hand_position(self, landmarks: List[Dict], hand_indices: List[int]) -> Optional[Tuple[float, float]]:
        """Get average position of hand landmarks"""
        hand_positions = []
        
        for idx in hand_indices:
            if idx < len(landmarks):
                landmark = landmarks[idx]
                if landmark.get('visibility', 0) > 0.5:  # Only use visible landmarks
                    hand_positions.append((landmark['x'], landmark['y']))
        
        if hand_positions:
            # Return average position
            avg_x = sum(pos[0] for pos in hand_positions) / len(hand_positions)
            avg_y = sum(pos[1] for pos in hand_positions) / len(hand_positions)
            return (avg_x, avg_y)
        
        return None
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points"""
        return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def get_all_hold_status(self) -> Dict[str, Dict]:
        """Get current status of all holds"""
        all_holds = {}
        
        for hold_id in self.hold_centers:
            status = self.hold_status.get(hold_id, 'untouched')
            completion_time = None
            
            if status == 'completed' and hold_id in self.hold_touch_start_times:
                completion_time = datetime.fromtimestamp(
                    self.hold_touch_start_times[hold_id] + self.touch_duration,
                    tz=timezone.utc
                ).isoformat().replace('+00:00', 'Z')
            
            # Determine hold type based on ID (this could be enhanced)
            hold_type = 'normal'
            if hold_id.startswith('start_'):
                hold_type = 'start'
            elif hold_id.startswith('finish_'):
                hold_type = 'finish'
            
            all_holds[hold_id] = {
                'id': hold_id,
                'type': hold_type,
                'status': status,
                'time': completion_time
            }
        
        return all_holds


class SessionTracker:
    """Tracks climbing session state and hold progress"""
    
    def __init__(self, wall_id: int, hold_detector: HoldDetector):
        self.wall_id = wall_id
        self.hold_detector = hold_detector
        
        # Session state
        self.session_start_time = datetime.now(timezone.utc)
        self.session_end_time = None
        self.session_status = 'started'
        
        # Track if this is the first pose data
        self.first_pose_received = False
    
    def update_session(self, transformed_landmarks: List[Dict]) -> Dict:
        """
        Update session with new pose data
        
        Args:
            transformed_landmarks: List of transformed pose landmarks
            
        Returns:
            Session data dictionary in required format
        """
        if not self.first_pose_received:
            self.first_pose_received = True
            logger.info(f"Session started at {self.session_start_time.isoformat()}")
        
        # Detect hold touches
        status_changes = self.hold_detector.detect_holds_touched(transformed_landmarks)
        
        # Get current hold status
        all_holds = self.hold_detector.get_all_hold_status()
        
        # Convert to list format
        holds_list = list(all_holds.values())
        
        # Create session data
        session_data = {
            'session': {
                'holds': holds_list,
                'startTime': self.session_start_time.isoformat().replace('+00:00', 'Z'),
                'endTime': self.session_end_time.isoformat().replace('+00:00', 'Z') if self.session_end_time else None,
                'status': self.session_status
            },
            'pose': transformed_landmarks
        }
        
        return session_data
    
    def end_session(self):
        """End the current session"""
        self.session_end_time = datetime.now(timezone.utc)
        self.session_status = 'completed'
        logger.info(f"Session ended at {self.session_end_time.isoformat()}")


class WebSocketSessionTracker:
    """Main class for WebSocket-based session tracking with hold detection"""
    
    def __init__(self, wall_id, input_websocket_url, output_websocket_url,
                 proximity_threshold=50.0, touch_duration=2.0,
                 reconnect_delay=5.0, debug=False):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.proximity_threshold = proximity_threshold
        self.touch_duration = touch_duration
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        
        # Components
        self.wall = None
        self.calibration = None
        self.calibration_utils = None
        self.transform_matrix = None
        self.hold_detector = None
        self.session_tracker = None
        
        # WebSocket clients
        self.input_client = None
        self.output_client = None
        
        # State
        self.running = False
        
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
        self.transform_matrix = np.array(self.calibration.perspective_transform, dtype=np.float32)
        
        # Debug: Log calibration details
        logger.debug(f"Calibration name: {self.calibration.name}")
        logger.debug(f"Wall dimensions: {self.wall.width_mm}x{self.wall.height_mm} mm")
        logger.debug(f"Wall SVG dimensions: {self.wall.wall_width_mm}x{self.wall.wall_height_mm} mm")
        logger.debug(f"Perspective transform matrix:\n{self.transform_matrix}")
        
        # Load hold centers from SVG
        try:
            if self.wall.svg_file:
                svg_parser = parse_svg_file(self.wall.svg_file.path)
                hold_centers = get_hold_centers(svg_parser)
                logger.info(f"Loaded {len(hold_centers)} holds from SVG")
            else:
                # Fallback to database holds
                holds = await database_sync_to_async(
                    lambda: list(self.wall.holds.all())
                )()
                hold_centers = {}
                for hold in holds:
                    if hold.coords:
                        hold_centers[hold.name] = (hold.coords.get('x', 0), hold.coords.get('y', 0))
                logger.info(f"Loaded {len(hold_centers)} holds from database")
        except Exception as e:
            logger.error(f"Error loading holds: {e}")
            return False
        
        # Debug: Log hold center coordinate ranges
        if hold_centers:
            x_coords = [pos[0] for pos in hold_centers.values()]
            y_coords = [pos[1] for pos in hold_centers.values()]
            logger.debug(f"Hold centers coordinate ranges:")
            logger.debug(f"  X: {min(x_coords):.1f} to {max(x_coords):.1f}")
            logger.debug(f"  Y: {min(y_coords):.1f} to {max(y_coords):.1f}")
            logger.debug(f"  Sample holds: {dict(list(hold_centers.items())[:3])}")
        
        # Setup hold detector
        self.hold_detector = HoldDetector(
            hold_centers,
            self.proximity_threshold,
            self.touch_duration
        )
        
        # Setup session tracker
        self.session_tracker = SessionTracker(self.wall_id, self.hold_detector)
        
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
    
    async def handle_pose_data(self, pose_data):
        """Handle incoming pose data from phone camera"""
        try:
            # Validate pose data
            is_valid, error_msg = validate_pose_data(pose_data)
            if not is_valid:
                logger.warning(f"Invalid pose data: {error_msg}")
                return
            
            # Extract image dimensions
            width = pose_data.get('width', 1280)
            height = pose_data.get('height', 720)
            image_size = (width, height)
            
            # Extract landmarks
            landmarks = pose_data['landmarks']
            
            # Transform coordinates
            transformed_landmarks = transform_landmarks_to_svg_coordinates(
                landmarks, self.calibration_utils, self.transform_matrix, image_size
            )
            
            # Update session with transformed landmarks
            session_data = self.session_tracker.update_session(transformed_landmarks)
            
            # Send session data
            await self.send_session_data(session_data)
            
            if self.debug and transformed_landmarks:
                logger.info(f"Processed {len(transformed_landmarks)} landmarks")
                # Log hand positions regularly for debugging
                if len(transformed_landmarks) > 0:
                    left_hand_pos = self.hold_detector._get_hand_position(transformed_landmarks, self.hold_detector.left_hand_indices)
                    right_hand_pos = self.hold_detector._get_hand_position(transformed_landmarks, self.hold_detector.right_hand_indices)
                    
                    # Format hand positions safely
                    left_str = f"({left_hand_pos[0]:.3f}, {left_hand_pos[1]:.3f})" if left_hand_pos else "None"
                    right_str = f"({right_hand_pos[0]:.3f}, {right_hand_pos[1]:.3f})" if right_hand_pos else "None"
                    logger.debug(f"DEBUG: Hand positions - Left: {left_str}, Right: {right_str}")
                
        except Exception as e:
            logger.error(f"Error handling pose data: {e}")
    
    async def send_session_data(self, session_data):
        """Send session data to output WebSocket"""
        await self.output_client.send_message(session_data)
        logger.debug(f"Sent session data with {len(session_data['pose'])} landmarks")
    
    async def run(self):
        """Main event loop"""
        if not await self.setup():
            logger.error("Setup failed, exiting")
            return
        
        logger.info("Starting WebSocket session tracker...")
        self.running = True
        
        try:
            # Start WebSocket clients
            input_task = self.input_client.start()
            output_task = self.output_client.start()
            
            # Wait for tasks to complete (they should run indefinitely)
            await asyncio.gather(input_task, output_task)
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self.session_tracker.end_session()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
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
        
        logger.info("Cleanup complete")


def validate_pose_data(data):
    """Validate incoming pose data format from phone camera"""
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"
    
    if 'type' not in data or data['type'] != 'pose':
        return False, "Missing or invalid 'type' field (expected 'pose')"
    
    if 'landmarks' not in data:
        return False, "Missing 'landmarks' field"
    
    if 'width' not in data or 'height' not in data:
        return False, "Missing 'width' or 'height' fields"
    
    landmarks = data['landmarks']
    if not isinstance(landmarks, list):
        return False, "Landmarks must be a list"
    
    for i, landmark in enumerate(landmarks):
        if not isinstance(landmark, dict):
            return False, f"Landmark {i} must be a dictionary"
        
        required_fields = ['x', 'y', 'z', 'visibility']
        for field in required_fields:
            if field not in landmark:
                return False, f"Landmark {i} missing '{field}' field"
            
            if not isinstance(landmark[field], (int, float)):
                return False, f"Landmark {i} field '{field}' must be numeric"
    
    return True, "Valid"


def transform_landmarks_to_svg_coordinates(landmarks, calibration_utils, transform_matrix, image_size):
    """Transform normalized landmark positions to SVG coordinates"""
    transformed_landmarks = []
    
    width, height = image_size
    
    # Debug: Log transformation parameters
    logger.debug(f"Image size: {width}x{height}")
    logger.debug(f"Transform matrix shape: {transform_matrix.shape}")
    logger.debug(f"Transform matrix:\n{transform_matrix}")
    
    for i, landmark in enumerate(landmarks):
        # Convert normalized position to image coordinates
        img_x = landmark['x'] * width
        img_y = landmark['y'] * height
        
        # Debug: Log hand landmarks specifically
        if i in [19, 20, 21, 22, 23, 24]:  # Hand landmarks
            logger.debug(f"Landmark {i}: normalized=({landmark['x']:.3f}, {landmark['y']:.3f}), image=({img_x:.1f}, {img_y:.1f})")
        
        # Transform to SVG coordinates using calibration
        svg_point = calibration_utils.transform_point_to_svg(
            (img_x, img_y),
            transform_matrix
        )
        
        # Debug: Log transformed hand landmarks
        if i in [19, 20, 21, 22, 23, 24] and svg_point:  # Hand landmarks
            logger.debug(f"Landmark {i} transformed: SVG=({svg_point[0]:.1f}, {svg_point[1]:.1f})")
        
        if svg_point:
            transformed_landmarks.append({
                'index': i,
                'x': svg_point[0],
                'y': svg_point[1],
                'z': landmark['z'],  # Keep original z-coordinate
                'visibility': landmark['visibility']
            })
    
    return transformed_landmarks


class Command(BaseCommand):
    help = 'WebSocket-based session tracker with hold detection for climbing walls'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--wall-id',
            type=int,
            required=True,
            help='ID of wall to use for hold detection'
        )
        parser.add_argument(
            '--input-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for receiving pose data from phone camera'
        )
        parser.add_argument(
            '--output-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for sending session data'
        )
        parser.add_argument(
            '--proximity-threshold',
            type=float,
            default=50.0,
            help='Distance in pixels to consider hand near hold (default: 50.0)'
        )
        parser.add_argument(
            '--touch-duration',
            type=float,
            default=2.0,
            help='Time in seconds hand must be near hold to count as touch (default: 2.0)'
        )
        parser.add_argument(
            '--reconnect-delay',
            type=float,
            default=5.0,
            help='Delay between reconnection attempts in seconds'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug output'
        )
    
    def handle(self, *args, **options):
        # Configure logging
        logger.remove()
        logger.add(
            "logs/websocket_session_tracker.log",
            rotation="1 day",
            retention="1 week",
            level="DEBUG" if options['debug'] else "INFO"
        )
        logger.add(
            lambda msg: self.stdout.write(msg),
            level="DEBUG" if options['debug'] else "INFO"
        )
        
        # Create and run session tracker
        tracker = WebSocketSessionTracker(
            wall_id=options['wall_id'],
            input_websocket_url=options['input_websocket_url'],
            output_websocket_url=options['output_websocket_url'],
            proximity_threshold=options['proximity_threshold'],
            touch_duration=options['touch_duration'],
            reconnect_delay=options['reconnect_delay'],
            debug=options['debug']
        )
        
        # Run tracker
        asyncio.run(tracker.run())