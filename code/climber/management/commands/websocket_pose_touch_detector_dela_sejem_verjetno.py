import os
import json
import time
import asyncio
import argparse
from datetime import datetime
from typing import Dict, Set, Optional, Tuple

import websockets
import numpy as np
from loguru import logger
from django.core.management.base import BaseCommand
from django.conf import settings
from channels.db import database_sync_to_async

from climber.models import Wall, WallCalibration
from climber.svg_utils import SVGParser
from climber.calibration.calibration_utils import CalibrationUtils


class TouchTracker:
    """Track touch durations for each hold"""
    
    def __init__(self, touch_duration=1.0):
        self.touch_duration = touch_duration
        self.touch_start_times = {}  # hold_id -> timestamp
        self.sent_events = set()     # Set of hold_ids for which events were sent
        
    def start_touch(self, hold_id, timestamp):
        """Record when a hold is first touched"""
        if hold_id not in self.touch_start_times:
            self.touch_start_times[hold_id] = timestamp
            logger.debug(f"Started tracking touch for hold {hold_id}")
    
    def end_touch(self, hold_id):
        """Clear touch tracking for a hold"""
        if hold_id in self.touch_start_times:
            del self.touch_start_times[hold_id]
        
        # Reset sent event flag when touch ends
        if hold_id in self.sent_events:
            self.sent_events.remove(hold_id)
            logger.debug(f"Reset touch tracking for hold {hold_id}")
    
    def update_touches(self, touched_holds, timestamp):
        """Update tracking based on currently touched holds"""
        # Start tracking new touches
        for hold_id in touched_holds:
            if hold_id not in self.touch_start_times:
                self.start_touch(hold_id, timestamp)
        
        # End tracking for holds no longer touched
        current_holds = set(touched_holds)
        ended_touches = set(self.touch_start_times.keys()) - current_holds
        for hold_id in ended_touches:
            self.end_touch(hold_id)
    
    def get_ready_holds(self, timestamp):
        """Return holds that have been touched long enough to send events"""
        ready_holds = []
        
        for hold_id, start_time in list(self.touch_start_times.items()):
            touch_duration = timestamp - start_time
            
            if touch_duration >= self.touch_duration:
                # Only send event once per touch
                if hold_id not in self.sent_events:
                    ready_holds.append({
                        'hold_id': hold_id,
                        'touch_duration': touch_duration
                    })
                    self.sent_events.add(hold_id)
                    logger.debug(f"Hold {hold_id} ready after {touch_duration:.2f}s")
        
        return ready_holds


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
    """WebSocket client for sending hold touch events"""
    
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


def extract_hand_positions(landmarks):
    """Extract hand positions from pose landmarks"""
    left_hand_landmarks = []
    right_hand_landmarks = []
    
    # MediaPipe pose landmark indices for hands
    # Left hand: 15 (elbow), 17 (wrist), 19 (index finger), 21 (pinky)
    # Right hand: 16 (elbow), 18 (wrist), 20 (index finger), 22 (pinky)
    
    try:
        # Left hand landmarks (using wrist and index finger for stability)
        left_wrist = landmarks[15] if len(landmarks) > 15 else None
        left_index = landmarks[19] if len(landmarks) > 19 else None
        left_pinky = landmarks[21] if len(landmarks) > 21 else None
        
        if left_wrist and left_index and left_wrist['visibility'] > 0.5 and left_index['visibility'] > 0.5:
            # Use average of wrist and index finger for more stable position
            left_hand_landmarks = [
                (left_wrist['x'], left_wrist['y']),
                (left_index['x'], left_index['y'])
            ]
            if left_pinky and left_pinky['visibility'] > 0.5:
                left_hand_landmarks.append((left_pinky['x'], left_pinky['y']))
        
        # Right hand landmarks
        right_wrist = landmarks[16] if len(landmarks) > 16 else None
        right_index = landmarks[20] if len(landmarks) > 20 else None
        right_pinky = landmarks[22] if len(landmarks) > 22 else None
        
        if right_wrist and right_index and right_wrist['visibility'] > 0.5 and right_index['visibility'] > 0.5:
            # Use average of wrist and index finger for more stable position
            right_hand_landmarks = [
                (right_wrist['x'], right_wrist['y']),
                (right_index['x'], right_index['y'])
            ]
            if right_pinky and right_pinky['visibility'] > 0.5:
                right_hand_landmarks.append((right_pinky['x'], right_pinky['y']))
                
    except (IndexError, KeyError) as e:
        logger.warning(f"Error extracting hand landmarks: {e}")
    
    # Calculate average positions
    left_hand_pos = None
    right_hand_pos = None
    
    if left_hand_landmarks:
        left_hand_pos = np.mean(left_hand_landmarks, axis=0)
    
    if right_hand_landmarks:
        right_hand_pos = np.mean(right_hand_landmarks, axis=0)
    
    return left_hand_pos, right_hand_pos


def transform_to_svg_coordinates(position, calibration_utils, transform_matrix, image_size=(1280, 720)):
    """Transform normalized position to SVG coordinates"""
    if position is None:
        return None
    
    # Convert normalized position to image coordinates
    img_x = position[0] * image_size[0]
    img_y = position[1] * image_size[1]
    
    # Transform to SVG coordinates using calibration
    svg_point = calibration_utils.transform_point_to_svg(
        (img_x, img_y),
        transform_matrix
    )
    
    return svg_point


def check_hold_intersections(svg_parser, hand_position):
    """Check which holds are touched by hand position"""
    if hand_position is None:
        return set()
    
    touched_holds = set()
    
    for path_id, path_data in svg_parser.paths.items():
        try:
            if svg_parser.point_in_path((hand_position[0], hand_position[1]), path_data['d']):
                touched_holds.add(path_id)
        except Exception as e:
            logger.warning(f"Error checking intersection for hold {path_id}: {e}")
    
    return touched_holds


class WebSocketPoseTouchDetector:
    """Main class for WebSocket-based pose touch detection"""
    
    def __init__(self, wall_id, input_websocket_url, output_websocket_url, 
                 touch_duration=1.0, reconnect_delay=5.0, debug=False):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.touch_duration = touch_duration
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        
        # Components
        self.wall = None
        self.calibration = None
        self.svg_parser = None
        self.calibration_utils = None
        self.transform_matrix = None
        
        # WebSocket clients
        self.input_client = None
        self.output_client = None
        
        # Touch tracking
        self.touch_tracker = TouchTracker(touch_duration)
        
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
        
        # Get calibration
        try:
            self.calibration = await database_sync_to_async(
                WallCalibration.objects.filter(wall=self.wall).latest
            )('created')
            logger.info(f"Loaded calibration: {self.calibration.name}")
        except WallCalibration.DoesNotExist:
            logger.error(f"No calibration found for wall {self.wall.name}")
            return False
        
        # Setup SVG parser
        if not self.wall.svg_file:
            logger.error(f"No SVG file associated with wall {self.wall.name}")
            return False
        
        svg_path = os.path.join(settings.MEDIA_ROOT, self.wall.svg_file.name)
        if not os.path.exists(svg_path):
            logger.error(f"SVG file not found: {svg_path}")
            return False
        
        self.svg_parser = SVGParser(svg_file_path=svg_path)
        self.svg_parser.paths = self.svg_parser.extract_paths()
        logger.info(f"Loaded SVG with {len(self.svg_parser.paths)} paths")
        
        # Setup calibration utils
        self.calibration_utils = CalibrationUtils()
        self.transform_matrix = np.array(self.calibration.perspective_transform, dtype=np.float32)
        
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
        """Handle incoming pose data"""
        try:
            # Validate pose data
            is_valid, error_msg = validate_pose_data(pose_data)
            if not is_valid:
                logger.warning(f"Invalid pose data: {error_msg}")
                return
            
            # Extract hand positions
            landmarks = pose_data['landmarks']
            left_hand_pos, right_hand_pos = extract_hand_positions(landmarks)
            
            # Transform coordinates
            left_hand_svg = transform_to_svg_coordinates(
                left_hand_pos, self.calibration_utils, self.transform_matrix
            )
            right_hand_svg = transform_to_svg_coordinates(
                right_hand_pos, self.calibration_utils, self.transform_matrix
            )
            
            # Check hold intersections
            touched_holds = set()
            
            if left_hand_svg:
                touched_holds.update(check_hold_intersections(self.svg_parser, left_hand_svg))
            
            if right_hand_svg:
                touched_holds.update(check_hold_intersections(self.svg_parser, right_hand_svg))
            
            # Update touch tracking
            timestamp = pose_data.get('timestamp', time.time())
            self.touch_tracker.update_touches(touched_holds, timestamp)
            
            # Get holds ready for events
            ready_holds = self.touch_tracker.get_ready_holds(timestamp)
            
            # Send hold touch events
            for hold_data in ready_holds:
                await self.send_hold_touch_event(hold_data['hold_id'], hold_data['touch_duration'])
            
            if self.debug and touched_holds:
                logger.info(f"Touched holds: {touched_holds}")
                
        except Exception as e:
            logger.error(f"Error handling pose data: {e}")
    
    async def send_hold_touch_event(self, hold_id, touch_duration):
        """Send hold touch event to output WebSocket"""
        event = {
            'type': 'hold_touch',
            'hold_id': hold_id,
            'wall_id': self.wall_id,
            'timestamp': time.time(),
            'touch_duration': touch_duration
        }
        
        await self.output_client.send_message(event)
        logger.info(f"Sent hold touch event: {hold_id} (duration: {touch_duration:.2f}s)")
    
    async def run(self):
        """Main event loop"""
        if not await self.setup():
            logger.error("Setup failed, exiting")
            return
        
        logger.info("Starting WebSocket pose touch detector...")
        self.running = True
        
        try:
            # Start WebSocket clients
            input_task = self.input_client.start()
            output_task = self.output_client.start()
            
            # Wait for tasks to complete (they should run indefinitely)
            await asyncio.gather(input_task, output_task)
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
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


class Command(BaseCommand):
    help = 'WebSocket-based pose touch detector for climbing walls'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--wall-id',
            type=int,
            required=True,
            help='ID of wall to process'
        )
        parser.add_argument(
            '--input-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for receiving MediaPipe pose data'
        )
        parser.add_argument(
            '--output-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for sending hold touch events'
        )
        parser.add_argument(
            '--touch-duration',
            type=float,
            default=1.0,
            help='Minimum duration (seconds) hand must touch hold before sending event'
        )
        parser.add_argument(
            '--reconnect-delay',
            type=float,
            default=5.0,
            help='Delay between reconnection attempts'
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
            "logs/websocket_pose_touch_detector.log",
            rotation="1 day",
            retention="1 week",
            level="DEBUG" if options['debug'] else "INFO"
        )
        logger.add(
            lambda msg: self.stdout.write(msg),
            level="DEBUG" if options['debug'] else "INFO"
        )
        
        # Create and run detector
        detector = WebSocketPoseTouchDetector(
            wall_id=options['wall_id'],
            input_websocket_url=options['input_websocket_url'],
            output_websocket_url=options['output_websocket_url'],
            touch_duration=options['touch_duration'],
            reconnect_delay=options['reconnect_delay'],
            debug=options['debug']
        )
        
        # Run detector
        asyncio.run(detector.run())
