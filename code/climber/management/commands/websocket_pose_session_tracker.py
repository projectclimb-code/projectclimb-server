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
                # Add connection parameters for better reliability
                self.websocket = await websockets.connect(
                    self.url,
                    ping_timeout=30,  # 30 second ping timeout
                    ping_interval=10   # 10 second ping interval
                )
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
                # Set ping timeout and close timeout to handle connection issues better
                # Use a longer ping timeout and shorter ping interval for better reliability
                self.websocket = await websockets.connect(
                    self.url,
                    ping_timeout=30,  # 30 second ping timeout (increased from 20)
                    close_timeout=10,  # 10 second close timeout
                    ping_interval=10   # 10 second ping interval (explicitly set)
                )
                logger.info("Successfully connected to output WebSocket")
                self.current_reconnect_delay = self.reconnect_delay  # Reset delay on success
                
                # Start sender task
                self.sender_task = asyncio.create_task(self.message_sender())
                
                # Start keep-alive task
                keep_alive_task = asyncio.create_task(self.keep_alive())
                
                # Wait for either the connection to close or tasks to be cancelled
                try:
                    await asyncio.gather(
                        self.websocket.wait_closed(),
                        keep_alive_task,
                        return_exceptions=True
                    )
                except Exception as e:
                    logger.debug(f"Connection monitoring task completed: {e}")
                
                # Cancel the sender task if it's still running
                if self.sender_task and not self.sender_task.done():
                    self.sender_task.cancel()
                    try:
                        await self.sender_task
                    except asyncio.CancelledError:
                        pass
                
            except (websockets.exceptions.ConnectionClosed,
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"Output WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
            except asyncio.CancelledError:
                logger.info("Output WebSocket connection task cancelled")
                break
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
                try:
                    # Use a shorter interval than the ping_timeout to ensure we ping before timeout
                    await asyncio.sleep(10)  # Ping every 10 seconds (half of ping_timeout)
                    
                    # Check if websocket is still valid before pinging
                    if self.websocket:
                        await self.websocket.ping()
                        logger.debug("Ping sent to keep connection alive")
                    else:
                        logger.warning("WebSocket is closed, stopping keep-alive")
                        break
                        
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"Output WebSocket connection closed during ping: {e}")
                    break  # Exit the loop instead of raising, to avoid unhandled exceptions
                except Exception as e:
                    logger.error(f"Error sending ping: {e}")
                    break  # Exit the loop on other errors as well
                    
        except asyncio.CancelledError:
            logger.info("Keep-alive task cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in keep-alive: {e}")
    
    async def message_sender(self):
        """Send queued messages to WebSocket"""
        while self.running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                # Check if websocket is still valid before sending
                if self.websocket:
                    try:
                        await self.websocket.send(json.dumps(message))
                        #logger.debug(f"Sent message: {message}")
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.warning(f"Output WebSocket connection closed while sending: {e}")
                        # Re-queue message only if we're still running
                        if self.running:
                            await self.message_queue.put(message)
                        break  # Exit the loop to trigger reconnection
                    except Exception as e:
                        logger.error(f"Error sending message: {e}")
                        # Re-queue message only if we're still running
                        if self.running:
                            await self.message_queue.put(message)
                        # Continue trying to send other messages
                        continue
                else:
                    # WebSocket is closed, re-queue message and exit
                    logger.warning("WebSocket is closed, re-queuing message")
                    if self.running:
                        await self.message_queue.put(message)
                    break
                    
            except asyncio.TimeoutError:
                continue  # No message to send, continue loop
            except asyncio.CancelledError:
                logger.info("Message sender task cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in message sender: {e}")
                await asyncio.sleep(0.1)  # Brief pause before continuing
    
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
            # Create a task to close the websocket properly
            close_task = asyncio.create_task(self.websocket.close())
            # Don't wait for it to complete to avoid blocking


class SVGHoldDetector:
    """Detects hold touches based on hand proximity to SVG paths"""
    
    def __init__(self, svg_parser, proximity_threshold: float = 50.0,
                 touch_duration: float = 2.0, route_holds=None,
                 video_aspect_ratio=(3, 4), svg_aspect_ratio=None, video_dimensions=(480, 640)):
        """
        Initialize SVG hold detector
        
        Args:
            svg_parser: SVGParser instance with loaded wall SVG
            proximity_threshold: Distance in pixels to consider hand near hold
            touch_duration: Time in seconds hand must be near hold to count as touch
            route_holds: Dictionary mapping hold_id -> hold_type for route filtering
            video_aspect_ratio: Tuple of (width, height) for video aspect ratio
            svg_aspect_ratio: Tuple of (width, height) for SVG aspect ratio (auto-detected if None)
            video_dimensions: Tuple of (width, height) for actual video dimensions (default: 640x480)
        """
        self.svg_parser = svg_parser
        self.proximity_threshold = proximity_threshold
        self.touch_duration = touch_duration
        self.route_holds = route_holds
        self.video_aspect_ratio = video_aspect_ratio
        self.video_dimensions = video_dimensions
        
        # Get SVG dimensions and calculate aspect ratio
        if svg_aspect_ratio is None:
            svg_width, svg_height = svg_parser.get_svg_dimensions()
            self.svg_aspect_ratio = (svg_width, svg_height)
        else:
            self.svg_aspect_ratio = svg_aspect_ratio
            
        # Calculate scaling factors to handle different aspect ratios
        # Video is scaled to fill height, SVG is scaled to fill height
        # This means we need to account for horizontal scaling differences
        video_width, video_height = video_aspect_ratio
        svg_width, svg_height = self.svg_aspect_ratio
        
        # Calculate the scaling factor for horizontal dimension
        # when both video and SVG are scaled to fill the same height
        self.horizontal_scale_factor = (video_width / video_height) / (svg_width / svg_height)
        
        # Calculate centering offset for proper coordinate transformation
        # Both video and SVG are centered when displayed with different aspect ratios
        self._calculate_centering_offsets()
        
        # Extract hold paths from SVG
        self.hold_paths = svg_parser.extract_paths()
        self.hold_centers = get_hold_centers(svg_parser)
        
        # Filter holds based on route if provided
        if self.route_holds:
            self._filter_holds_by_route()
        
        # Track hold touch state
        self.hold_touch_start_times = {}  # hold_id -> timestamp when touch started
        self.hold_status = {}  # hold_id -> status ('untouched', 'touched')
        self.touched_holds = set()  # Track holds that have been touched in current session
        
        # MediaPipe landmark indices for hands
        self.left_hand_indices = [15, 17, 19, 21]  # Left wrist, pinky, index, thumb
        self.right_hand_indices = [16, 18, 20, 22]  # Right wrist, pinky, index, thumb

        #self.left_hand_indices = [15,]  # Left wrist, pinky, index, thumb
        #self.right_hand_indices = [16,]  # Right wrist, pinky, index, thumb


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
    
    def _calculate_centering_offsets(self):
        """
        Calculate centering offsets for proper coordinate transformation between video and SVG.
        
        Both video and SVG are centered when displayed with different aspect ratios.
        This method calculates the offsets needed to properly transform coordinates.
        """
        video_width, video_height = self.video_dimensions
        video_aspect_width, video_aspect_height = self.video_aspect_ratio
        svg_width, svg_height = self.svg_aspect_ratio
        
        # Get actual SVG dimensions from parser
        actual_svg_width, actual_svg_height = self.svg_parser.get_svg_dimensions()
        
        logger.info(f"DEBUG: Video dimensions: {video_width}x{video_height}")
        logger.info(f"DEBUG: Video aspect ratio: {video_aspect_width}:{video_aspect_height}")
        logger.info(f"DEBUG: SVG aspect ratio: {svg_width}:{svg_height}")
        logger.info(f"DEBUG: Actual SVG dimensions: {actual_svg_width}x{actual_svg_height}")
        
        # Calculate the actual display dimensions for video (maintaining aspect ratio)
        video_display_height = video_height  # Video fills the height
        video_display_width = video_display_height * (video_aspect_width / video_aspect_height)
        
        # Calculate the actual display dimensions for SVG (maintaining aspect ratio)
        svg_display_height = video_height  # SVG also fills the height
        svg_display_width = svg_display_height * (svg_width / svg_height)
        
        # Calculate centering offsets (both are centered horizontally)
        # Video centering offset (how much video is shifted from left edge)
        self.video_center_offset = (video_width - video_display_width) / 2
        
        # SVG centering offset (how much SVG is shifted from left edge)
        self.svg_center_offset = (video_width - svg_display_width) / 2
        
        # Calculate the offset between video and SVG coordinate systems
        # This accounts for the different centering when both are displayed
        self.coordinate_offset = self.video_center_offset - self.svg_center_offset
        
        logger.debug(f"Video display dimensions: {video_display_width}x{video_display_height}")
        logger.debug(f"SVG display dimensions: {svg_display_width}x{svg_display_height}")
        logger.debug(f"Video center offset: {self.video_center_offset}")
        logger.debug(f"SVG center offset: {self.svg_center_offset}")
        logger.debug(f"Coordinate offset: {self.coordinate_offset}")
        logger.debug(f"Horizontal scale factor: {self.horizontal_scale_factor}")
    
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
        
        # Debug print hand positions
        logger.info(f"DEBUG: Left hand position: {left_hand_pos}")
        logger.info(f"DEBUG: Right hand position: {right_hand_pos}")
        
        current_time = time.time()
        status_changes = {}
        
        # Check each hold for hand contact
        for hold_id, hold_path_data in self.hold_paths.items():
            # Skip if not in route holds (if filtering is enabled)
            if self.route_holds and hold_id not in self.route_holds:
                continue
            
            # Check if either hand is touching the hold
            left_touching = False
            right_touching = False
            
            if left_hand_pos:
                left_touching = self._is_hand_touching_hold(left_hand_pos, hold_path_data)

            
            if right_hand_pos:
                right_touching = self._is_hand_touching_hold(right_hand_pos, hold_path_data)

            
            is_touching = left_touching or right_touching
            current_status = self.hold_status.get(hold_id, 'untouched')
            
            if is_touching:
                # Hand is touching the hold
                if hold_id not in self.hold_touch_start_times:
                    # Just started touching this hold
                    self.hold_touch_start_times[hold_id] = current_time
                    logger.debug(f"Hold {hold_id} touch started at {current_time}")
                elif current_time - self.hold_touch_start_times[hold_id] >= self.touch_duration:
                    # Has been touching long enough to count as touched
                    if current_status == 'untouched':
                        self.hold_status[hold_id] = 'touched'
                        status_changes[hold_id] = 'touched'
                        self.touched_holds.add(hold_id)
                        logger.info(f"Hold {hold_id} touched after {self.touch_duration}s touch")
            else:
                # Hand is not touching the hold
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
        """
        Get average position of hand landmarks with proper coordinate transformation.
        
        This method transforms pose coordinates from relative coordinate space to SVG coordinate space,
        accounting for both scaling differences and centering offsets.
        """
        hand_positions = []
        
        # Debug logging for raw landmark coordinates
        raw_positions = []
        
        for idx in hand_indices:
            if idx < len(landmarks):
                landmark = landmarks[idx]
                if landmark.get('visibility', 0) > 0.2:  # Only use visible landmarks
                    # The landmarks are already transformed by homography to SVG coordinate space
                    # but we need to account for the different aspect ratios and centering
                    x = landmark['x']
                    y = landmark['y']
                    
                    # Store raw position for debugging
                    raw_positions.append((x, y))
                    
                    # The coordinates appear to be in relative space (0-1 range) while SVG coordinates are much larger
                    # We need to transform from relative coordinates to SVG coordinate space
                    # First, get actual SVG dimensions
                    actual_svg_width, actual_svg_height = self.svg_parser.get_svg_dimensions()
                    logger.info(f"DEBUG: SVG width, height: {actual_svg_width}, {actual_svg_height}")
                    # Transform from relative coordinates to SVG coordinates
                    # Scale up to SVG dimensions and apply centering offset
                    svg_x = x * actual_svg_width
                    svg_y = y * actual_svg_height
                    
                    # Apply centering offset to account for different aspect ratios
                    # Both video and SVG are centered when displayed
                    transformed_x = svg_x * self.horizontal_scale_factor - self.coordinate_offset
                    
                    hand_positions.append((svg_x, svg_y))
                    hand_positions.append((transformed_x, svg_y))
        
        # Debug logging for hand positions
        if raw_positions:
            hand_type = "Left" if hand_indices == self.left_hand_indices else "Right"
            logger.info(f"DEBUG: {hand_type} hand raw positions: {raw_positions}")
            logger.info(f"DEBUG: {hand_type} hand transformed positions: {hand_positions}")
            logger.info(f"DEBUG: Horizontal scale factor: {self.horizontal_scale_factor}")
            logger.info(f"DEBUG: Coordinate offset: {self.coordinate_offset}")
        
        if hand_positions:
            # Return average position
            avg_x = sum(pos[0] for pos in hand_positions) / len(hand_positions)
            avg_y = sum(pos[1] for pos in hand_positions) / len(hand_positions)
            return (avg_x, avg_y)
        
        return None
    
    def _is_hand_touching_hold(self, hand_pos: Tuple[float, float], hold_path_data: Dict) -> bool:
        """
        Check if hand position is touching the hold by testing if point is inside the SVG path
        
        Args:
            hand_pos: (x, y) coordinates of hand position
            hold_path_data: Dictionary containing hold path data
            
        Returns:
            True if hand is touching the hold, False otherwise
        """
        if not hand_pos:
            return False
            
        # First check if hand is within proximity threshold (faster check)
        hold_id = hold_path_data['id']
        if hold_id in self.hold_centers:
            center = self.hold_centers[hold_id]
            distance = self._distance(hand_pos, center)
            

            
            if distance > self.proximity_threshold:

                return False
        
        # Then check if hand is actually inside the SVG path
        try:
            path_d = hold_path_data['d']
            is_inside_path = self.svg_parser.point_in_path(hand_pos, path_d)
            
   
            return is_inside_path
        except Exception as e:
            logger.warning(f"Error checking if hand is inside path for hold {hold_id}: {e}")
            # Fallback to distance-based detection
            return distance <= self.proximity_threshold
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points"""
        return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def get_all_hold_status(self) -> Dict[str, Dict]:
        """Get current status of all holds"""
        all_holds = {}
        
        for hold_id in self.hold_centers:
            status = self.hold_status.get(hold_id, 'untouched')
            completion_time = None
            
            if status == 'touched' and hold_id in self.hold_touch_start_times:
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
        self.session_status = 'touched'
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
            route_holds=self._extract_route_holds(route_data) if route_data else None,
            video_dimensions=(640, 480)  # Default video dimensions as specified
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
        
        # Give some time for tasks to complete properly
        await asyncio.sleep(0.1)
        
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