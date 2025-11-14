"""
Management command to track climbing sessions with pose transformation and hold detection.

This command connects to an input WebSocket to receive MediaPipe pose data,
transforms the landmarks using wall calibration,
detects hold touches based on hand proximity to SVG paths,
and outputs session data in the specified JSON format.

Features:
- Pose transformation using wall calibration
- Extended hand landmarks beyond the palm
- Hold detection using SVG paths
- Configurable output (landmarks and/or SVG paths)
- Session tracking with hold status and timestamps
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

from climber.models import Wall, WallCalibration, Hold, Route
from climber.tansformation_utils import apply_homography_to_mediapipe_json
from climber.svg_utils import parse_svg_file, get_hold_centers
from climber.calibration.calibration_utils import CalibrationUtils


class InputWebSocketClient:
    """WebSocket client for receiving MediaPipe pose data"""
    
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
                    await self.websocket.send(json.dumps(message))
                    logger.debug(f"Sent message: {message}")
                    
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


class SVGHoldDetector:
    """Detects hold touches based on hand proximity to SVG paths"""
    
    def __init__(self, svg_parser, proximity_threshold: float = 50.0,
                 touch_duration: float = 2.0, route_holds=None):
        """
        Initialize SVG hold detector
        
        Args:
            svg_parser: SVGParser instance with loaded wall SVG
            proximity_threshold: Distance in pixels to consider hand near hold
            touch_duration: Time in seconds hand must be near hold to count as touch
            route_holds: Dictionary mapping hold_id -> hold_type for route filtering
        """
        self.svg_parser = svg_parser
        self.proximity_threshold = proximity_threshold
        self.touch_duration = touch_duration
        self.route_holds = route_holds
        
        # Extract hold paths from SVG
        self.hold_paths = svg_parser.extract_paths()
        self.hold_centers = get_hold_centers(svg_parser)
        
        # Filter holds based on route if provided
        if self.route_holds:
            self._filter_holds_by_route()
        
        # Track hold touch state
        self.hold_touch_start_times = {}  # hold_id -> timestamp when touch started
        self.hold_status = {}  # hold_id -> status ('untouched', 'completed')
        self.touched_holds = set()  # Track holds that have been touched in current session
        
        # MediaPipe landmark indices for hands
        self.left_hand_indices = [19, 20, 21]  # Left wrist, thumb, index
        self.right_hand_indices = [22, 23, 24]  # Right wrist, thumb, index
    
    def _filter_holds_by_route(self):
        """Filter holds and paths based on route specification"""
        if not self.route_holds:
            return
        
        # Filter hold centers
        filtered_centers = {}
        for hold_id, center in self.hold_centers.items():
            if hold_id in self.route_holds:
                filtered_centers[hold_id] = center
        self.hold_centers = filtered_centers
        
        # Filter hold paths
        filtered_paths = {}
        for hold_id, path_data in self.hold_paths.items():
            if hold_id in self.route_holds:
                filtered_paths[hold_id] = path_data
        self.hold_paths = filtered_paths
        
        logger.info(f"Filtered to {len(self.hold_centers)} holds from route")
    
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
        
        current_time = time.time()
        status_changes = {}
        
        # Check each hold for proximity to hands
        for hold_id, hold_center in self.hold_centers.items():
            # Calculate distances
            left_dist = self._distance(left_hand_pos, hold_center) if left_hand_pos else float('inf')
            right_dist = self._distance(right_hand_pos, hold_center) if right_hand_pos else float('inf')
            min_dist = min(left_dist, right_dist)
            
            is_near_left = left_hand_pos and left_dist < self.proximity_threshold
            is_near_right = right_hand_pos and right_dist < self.proximity_threshold
            is_near_any_hand = is_near_left or is_near_right
            
            current_status = self.hold_status.get(hold_id, 'untouched')
            
            if is_near_any_hand:
                # Hand is near the hold
                if hold_id not in self.hold_touch_start_times:
                    # Just started touching this hold
                    self.hold_touch_start_times[hold_id] = current_time
                    logger.debug(f"Hold {hold_id} touch started at {current_time}")
                elif current_time - self.hold_touch_start_times[hold_id] >= self.touch_duration:
                    # Has been touching long enough to count as completed
                    if current_status == 'untouched':
                        self.hold_status[hold_id] = 'completed'
                        status_changes[hold_id] = 'completed'
                        self.touched_holds.add(hold_id)
                        logger.info(f"Hold {hold_id} completed after {self.touch_duration}s touch")
            else:
                # Hand is not near the hold
                if hold_id in self.hold_touch_start_times:
                    # Was touching but now stopped
                    del self.hold_touch_start_times[hold_id]
                    logger.debug(f"Hold {hold_id} touch stopped")
        
        return status_changes
    
    def get_touched_svg_paths(self) -> List[Dict]:
        """
        Get SVG path data for holds that have been touched
        
        Returns:
            List of SVG path dictionaries for touched holds
        """
        touched_paths = []
        for hold_id in self.touched_holds:
            if hold_id in self.hold_paths:
                path_data = self.hold_paths[hold_id].copy()
                path_data['touched'] = True
                path_data['touch_time'] = self.hold_touch_start_times.get(hold_id)
                touched_paths.append(path_data)
        return touched_paths
    
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
            
            # Determine hold type from route or based on ID
            if self.route_holds and hold_id in self.route_holds:
                hold_type = self.route_holds[hold_id]
            else:
                # Fallback to ID-based detection
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
    
    def __init__(self, wall_id: int, hold_detector: SVGHoldDetector):
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
    
    def get_session_data(self, include_pose: bool = True, include_svg_paths: bool = False) -> Dict:
        """
        Get current session data in specified format
        
        Args:
            include_pose: Whether to include pose data in output
            include_svg_paths: Whether to include SVG path data for touched holds
            
        Returns:
            Session data dictionary
        """
        # Get current hold status
        all_holds = self.hold_detector.get_all_hold_status()
        holds_list = list(all_holds.values())
        
        # Create base session data
        session_data = {
            'session': {
                'holds': holds_list,
                'startTime': self.session_start_time.isoformat().replace('+00:00', 'Z'),
                'endTime': self.session_end_time.isoformat().replace('+00:00', 'Z') if self.session_end_time else None,
                'status': self.session_status
            }
        }
        
        # Add pose data if requested
        if include_pose:
            session_data['pose'] = []  # Will be populated by caller
        
        # Add SVG paths if requested
        if include_svg_paths:
            session_data['touched_svg_paths'] = self.hold_detector.get_touched_svg_paths()
        
        return session_data
    
    def end_session(self):
        """End the current session"""
        self.session_end_time = datetime.now(timezone.utc)
        self.session_status = 'completed'
        logger.info(f"Session ended at {self.session_end_time.isoformat()}")


def validate_pose_data(data):
    """Validate incoming pose data format"""
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"
    
    if 'landmarks' not in data:
        return False, "Missing 'landmarks' field"
    
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


def calculate_extended_hand_landmarks(landmarks: List[Dict], extension_percent: float) -> List[Dict]:
    """
    Calculate extended hand landmarks beyond the palm.
    
    Args:
        landmarks: List of MediaPipe pose landmarks
        extension_percent: Percentage to extend beyond the palm (0-100)
        
    Returns:
        List of two new landmarks (left and right hand extensions)
    """
    # MediaPipe pose landmark indices for hands
    # Left hand landmarks
    LEFT_WRIST = 15
    LEFT_PINKY = 17
    LEFT_INDEX = 19
    LEFT_THUMB = 21
    
    # Right hand landmarks
    RIGHT_WRIST = 16
    RIGHT_PINKY = 18
    RIGHT_INDEX = 20
    RIGHT_THUMB = 22
    
    # Elbow landmarks for direction calculation
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    
    new_landmarks = []
    
    # Calculate left hand extension
    if (LEFT_WRIST < len(landmarks) and LEFT_PINKY < len(landmarks) and 
        LEFT_INDEX < len(landmarks) and LEFT_THUMB < len(landmarks) and 
        LEFT_ELBOW < len(landmarks)):
        
        # Get palm center as average of hand landmarks
        palm_center_x = (landmarks[LEFT_WRIST]['x'] + landmarks[LEFT_PINKY]['x'] + 
                         landmarks[LEFT_INDEX]['x'] + landmarks[LEFT_THUMB]['x']) / 4
        palm_center_y = (landmarks[LEFT_WRIST]['y'] + landmarks[LEFT_PINKY]['y'] + 
                         landmarks[LEFT_INDEX]['y'] + landmarks[LEFT_THUMB]['y']) / 4
        palm_center_z = (landmarks[LEFT_WRIST]['z'] + landmarks[LEFT_PINKY]['z'] + 
                         landmarks[LEFT_INDEX]['z'] + landmarks[LEFT_THUMB]['z']) / 4
        
        # Calculate direction from elbow to palm center
        elbow_to_palm_x = palm_center_x - landmarks[LEFT_ELBOW]['x']
        elbow_to_palm_y = palm_center_y - landmarks[LEFT_ELBOW]['y']
        elbow_to_palm_z = palm_center_z - landmarks[LEFT_ELBOW]['z']
        
        # Normalize direction vector
        magnitude = np.sqrt(elbow_to_palm_x**2 + elbow_to_palm_y**2 + elbow_to_palm_z**2)
        if magnitude > 0:
            elbow_to_palm_x /= magnitude
            elbow_to_palm_y /= magnitude
            elbow_to_palm_z /= magnitude
        
        # Calculate palm size for scaling
        palm_size = np.sqrt(
            (landmarks[LEFT_PINKY]['x'] - landmarks[LEFT_INDEX]['x'])**2 +
            (landmarks[LEFT_PINKY]['y'] - landmarks[LEFT_INDEX]['y'])**2 +
            (landmarks[LEFT_PINKY]['z'] - landmarks[LEFT_INDEX]['z'])**2
        )
        
        # Calculate extension distance
        extension_distance = palm_size * (extension_percent / 100.0)
        
        # Create new landmark
        new_landmark = {
            'x': palm_center_x + elbow_to_palm_x * extension_distance,
            'y': palm_center_y + elbow_to_palm_y * extension_distance,
            'z': palm_center_z + elbow_to_palm_z * extension_distance,
            'visibility': min(landmarks[LEFT_WRIST]['visibility'], 
                            landmarks[LEFT_PINKY]['visibility'],
                            landmarks[LEFT_INDEX]['visibility'],
                            landmarks[LEFT_THUMB]['visibility'])
        }
        new_landmarks.append(new_landmark)
    
    # Calculate right hand extension
    if (RIGHT_WRIST < len(landmarks) and RIGHT_PINKY < len(landmarks) and 
        RIGHT_INDEX < len(landmarks) and RIGHT_THUMB < len(landmarks) and 
        RIGHT_ELBOW < len(landmarks)):
        
        # Get palm center as average of hand landmarks
        palm_center_x = (landmarks[RIGHT_WRIST]['x'] + landmarks[RIGHT_PINKY]['x'] + 
                         landmarks[RIGHT_INDEX]['x'] + landmarks[RIGHT_THUMB]['x']) / 4
        palm_center_y = (landmarks[RIGHT_WRIST]['y'] + landmarks[RIGHT_PINKY]['y'] + 
                         landmarks[RIGHT_INDEX]['y'] + landmarks[RIGHT_THUMB]['y']) / 4
        palm_center_z = (landmarks[RIGHT_WRIST]['z'] + landmarks[RIGHT_PINKY]['z'] + 
                         landmarks[RIGHT_INDEX]['z'] + landmarks[RIGHT_THUMB]['z']) / 4
        
        # Calculate direction from elbow to palm center
        elbow_to_palm_x = palm_center_x - landmarks[RIGHT_ELBOW]['x']
        elbow_to_palm_y = palm_center_y - landmarks[RIGHT_ELBOW]['y']
        elbow_to_palm_z = palm_center_z - landmarks[RIGHT_ELBOW]['z']
        
        # Normalize direction vector
        magnitude = np.sqrt(elbow_to_palm_x**2 + elbow_to_palm_y**2 + elbow_to_palm_z**2)
        if magnitude > 0:
            elbow_to_palm_x /= magnitude
            elbow_to_palm_y /= magnitude
            elbow_to_palm_z /= magnitude
        
        # Calculate palm size for scaling
        palm_size = np.sqrt(
            (landmarks[RIGHT_PINKY]['x'] - landmarks[RIGHT_INDEX]['x'])**2 +
            (landmarks[RIGHT_PINKY]['y'] - landmarks[RIGHT_INDEX]['y'])**2 +
            (landmarks[RIGHT_PINKY]['z'] - landmarks[RIGHT_INDEX]['z'])**2
        )
        
        # Calculate extension distance
        extension_distance = palm_size * (extension_percent / 100.0)
        
        # Create new landmark
        new_landmark = {
            'x': palm_center_x + elbow_to_palm_x * extension_distance,
            'y': palm_center_y + elbow_to_palm_y * extension_distance,
            'z': palm_center_z + elbow_to_palm_z * extension_distance,
            'visibility': min(landmarks[RIGHT_WRIST]['visibility'], 
                            landmarks[RIGHT_PINKY]['visibility'],
                            landmarks[RIGHT_INDEX]['visibility'],
                            landmarks[RIGHT_THUMB]['visibility'])
        }
        new_landmarks.append(new_landmark)
    
    return new_landmarks


class WebSocketPoseSessionTracker:
    """Main class for WebSocket-based pose session tracking with hold detection"""
    
    def __init__(self, wall_id, input_websocket_url, output_websocket_url,
                 proximity_threshold=50.0, touch_duration=2.0,
                 reconnect_delay=5.0, debug=False,
                 no_stream_landmarks=False, stream_svg_only=False, route_data=None, route_id=None):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.proximity_threshold = proximity_threshold
        self.touch_duration = touch_duration
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        self.no_stream_landmarks = no_stream_landmarks
        self.stream_svg_only = stream_svg_only
        self.route_data = route_data  # Route specification with holds
        self.route_id = route_id  # Route ID to retrieve from database
        
        # Components
        self.wall = None
        self.calibration = None
        self.calibration_utils = None
        self.transform_matrix = None
        self.hand_extension_percent = 20.0  # Default value
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
        
        # Setup hold detector with route filtering
        self.hold_detector = SVGHoldDetector(
            self.svg_parser,
            self.proximity_threshold,
            self.touch_duration,
            route_holds=self._extract_route_holds(route_data) if route_data else None
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
    
    def _get_route_data(self):
        """Retrieve route data from database if route_id is provided"""
        if self.route_id:
            # This method should not be called directly, use the inline version in setup
            logger.warning("_get_route_data should not be called directly")
            return None
        
        return self.route_data
    
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
            # Validate pose data
            is_valid, error_msg = validate_pose_data(pose_data)
            if not is_valid:
                logger.warning(f"Invalid pose data: {error_msg}")
                return
            
            # Apply transformation using the calibration matrix
            transformed_data = apply_homography_to_mediapipe_json(
                pose_data.copy(), 
                self.transform_matrix
            )
            
            # Add extended hand landmarks
            landmarks = transformed_data.get('landmarks', [])
            if landmarks:
                extended_landmarks = calculate_extended_hand_landmarks(
                    landmarks, 
                    self.hand_extension_percent
                )
                
                # Add the new landmarks to the data
                if 'extended_hand_landmarks' not in transformed_data:
                    transformed_data['extended_hand_landmarks'] = []
                transformed_data['extended_hand_landmarks'].extend(extended_landmarks)
                
                # Also add them to the main landmarks list for compatibility
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
            
            # Log progress every 100 messages
            if self.message_count % 100 == 0:
                elapsed = time.time() - self.start_time
                rate = self.message_count / elapsed
                logger.info(f"Processed {self.message_count} messages ({rate:.2f} msg/sec)")
            
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
        if not await self.setup():
            logger.error("Setup failed, exiting")
            return
        
        logger.info("Starting WebSocket pose session tracker...")
        self.running = True
        self.start_time = time.time()
        
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
        
        # Log final statistics
        elapsed = time.time() - self.start_time
        logger.info(f"Processed {self.message_count} messages in {elapsed:.2f} seconds")
        if elapsed > 0:
            logger.info(f"Average rate: {self.message_count / elapsed:.2f} messages/second")
        
        logger.info("Cleanup complete")


class Command(BaseCommand):
    help = 'WebSocket-based pose session tracker with hold detection for climbing walls'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--wall-id',
            type=int,
            required=True,
            help='ID of wall to use for calibration transformation'
        )
        parser.add_argument(
            '--input-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for receiving pose data'
        )
        parser.add_argument(
            '--output-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for sending session data'
        )
        parser.add_argument(
            '--no-stream-landmarks',
            action='store_true',
            help='Skip streaming transformed landmarks in output'
        )
        parser.add_argument(
            '--stream-svg-only',
            action='store_true',
            help='Stream only SVG paths that are touched'
        )
        parser.add_argument(
            '--route-data',
            type=str,
            help='Route data as JSON string with holds specification'
        )
        parser.add_argument(
            '--route-id',
            type=int,
            help='Route ID to retrieve from database'
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
            "logs/websocket_pose_session_tracker.log",
            rotation="1 day",
            retention="1 week",
            level="DEBUG" if options['debug'] else "INFO"
        )
        logger.add(
            lambda msg: self.stdout.write(msg),
            level="DEBUG" if options['debug'] else "INFO"
        )
        
        # Parse route data if provided
        route_data = None
        if options.get('route_data'):
            try:
                route_data = json.loads(options['route_data'])
                logger.info(f"Loaded route data: {route_data}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid route data JSON: {e}")
                return
        
        # Create and run session tracker
        tracker = WebSocketPoseSessionTracker(
            wall_id=options['wall_id'],
            input_websocket_url=options['input_websocket_url'],
            output_websocket_url=options['output_websocket_url'],
            proximity_threshold=options['proximity_threshold'],
            touch_duration=options['touch_duration'],
            reconnect_delay=options['reconnect_delay'],
            debug=options['debug'],
            no_stream_landmarks=options['no_stream_landmarks'],
            stream_svg_only=options['stream_svg_only'],
            route_data=route_data
        )
        
        # Run tracker
        asyncio.run(tracker.run())