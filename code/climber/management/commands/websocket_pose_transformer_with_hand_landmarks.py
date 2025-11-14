"""
Management command to transform MediaPipe pose landmarks using wall calibration
and add extended hand landmarks.

This command connects to an input WebSocket to receive pose data,
transforms the landmarks using the active wall calibration,
adds extended hand landmarks beyond the palm,
and forwards the transformed data to an output WebSocket.
"""

import os
import json
import time
import asyncio
import argparse
from datetime import datetime
from typing import Dict, Set, Optional, Tuple, List

import websockets
import numpy as np
from loguru import logger
from django.core.management.base import BaseCommand
from django.conf import settings
from channels.db import database_sync_to_async

from climber.models import Wall, WallCalibration
from climber.tansformation_utils import apply_homography_to_mediapipe_json


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
    """WebSocket client for sending transformed pose data"""
    
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


class WebSocketPoseTransformerWithHandLandmarks:
    """Main class for WebSocket-based pose coordinate transformation with hand landmarks"""
    
    def __init__(self, wall_id, input_websocket_url, output_websocket_url,
                 reconnect_delay=5.0, debug=False):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        
        # Components
        self.wall = None
        self.calibration = None
        self.transform_matrix = None
        self.hand_extension_percent = 20.0  # Default value
        
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
        
        # Extract transformation matrix from calibration
        if not self.calibration.perspective_transform:
            logger.error("No perspective transform found in calibration")
            return False
        
        try:
            self.transform_matrix = self.calibration.perspective_transform
            logger.info(f"Loaded transformation matrix: {self.transform_matrix}")
        except Exception as e:
            logger.error(f"Error loading transformation matrix: {e}")
            return False
        
        # Get hand extension percent from calibration
        self.hand_extension_percent = self.calibration.hand_extension_percent
        logger.info(f"Using hand extension percent: {self.hand_extension_percent}%")
        
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
            
            # Add metadata
            transformed_data['_transformed'] = True
            transformed_data['_transform_timestamp'] = time.time()
            transformed_data['_wall_id'] = self.wall_id
            transformed_data['_calibration_id'] = self.calibration.id
            transformed_data['_message_count'] = self.message_count + 1
            transformed_data['_hand_extension_percent'] = self.hand_extension_percent
            
            # Send transformed data
            await self.send_transformed_pose_data(transformed_data)
            
            self.message_count += 1
            
            # Log progress every 100 messages
            if self.message_count % 100 == 0:
                elapsed = time.time() - self.start_time
                rate = self.message_count / elapsed
                logger.info(f"Processed {self.message_count} messages ({rate:.2f} msg/sec)")
            
            if self.debug:
                logger.info(f"Transformed pose data with {len(pose_data.get('landmarks', []))} landmarks and {len(transformed_data.get('extended_hand_landmarks', []))} extended hand landmarks")
                
        except Exception as e:
            logger.error(f"Error handling pose data: {e}")
    
    async def send_transformed_pose_data(self, transformed_data):
        """Send transformed pose data to output WebSocket"""
        await self.output_client.send_message(transformed_data)
        logger.debug(f"Sent transformed pose data")
    
    async def run(self):
        """Main event loop"""
        if not await self.setup():
            logger.error("Setup failed, exiting")
            return
        
        logger.info("Starting WebSocket pose transformer with hand landmarks...")
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
    help = 'WebSocket-based pose transformer using wall calibration with extended hand landmarks'
    
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
            help='WebSocket URL for sending transformed pose data'
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
            "logs/websocket_pose_transformer_with_hand_landmarks.log",
            rotation="1 day",
            retention="1 week",
            level="DEBUG" if options['debug'] else "INFO"
        )
        logger.add(
            lambda msg: self.stdout.write(msg),
            level="DEBUG" if options['debug'] else "INFO"
        )
        
        # Create and run transformer
        transformer = WebSocketPoseTransformerWithHandLandmarks(
            wall_id=options['wall_id'],
            input_websocket_url=options['input_websocket_url'],
            output_websocket_url=options['output_websocket_url'],
            reconnect_delay=options['reconnect_delay'],
            debug=options['debug']
        )
        
        # Run transformer
        asyncio.run(transformer.run())