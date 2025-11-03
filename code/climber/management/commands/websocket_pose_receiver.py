"""
Management command to receive MediaPipe pose landmarks from phone camera WebSocket,
transform them according to wall calibration, and send to output WebSocket.

This command connects to an input WebSocket to receive pose data from phone_camera.html,
transforms the landmarks from image coordinates to SVG wall coordinates using wall calibration,
and forwards the transformed data to an output WebSocket for further processing.
"""

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
from climber.calibration.calibration_utils import CalibrationUtils


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
    
    for i, landmark in enumerate(landmarks):
        # Convert normalized position to image coordinates
        img_x = landmark['x'] * width
        img_y = landmark['y'] * height
        
        # Transform to SVG coordinates using calibration
        svg_point = calibration_utils.transform_point_to_svg(
            (img_x, img_y),
            transform_matrix
        )
        
        if svg_point:
            transformed_landmarks.append({
                'index': i,
                'x': svg_point[0],
                'y': svg_point[1],
                'z': landmark['z'],  # Keep original z-coordinate
                'visibility': landmark['visibility']
            })
    
    return transformed_landmarks


class WebSocketPoseReceiver:
    """Main class for WebSocket-based pose coordinate transformation"""
    
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
        self.calibration_utils = None
        self.transform_matrix = None
        
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
            
            # Send transformed pose data
            await self.send_transformed_pose_data(transformed_landmarks, pose_data)
            
            if self.debug and transformed_landmarks:
                logger.info(f"Transformed {len(transformed_landmarks)} landmarks")
                
        except Exception as e:
            logger.error(f"Error handling pose data: {e}")
    
    async def send_transformed_pose_data(self, transformed_landmarks, original_data):
        """Send transformed pose data to output WebSocket"""
        message = {
            'type': 'transformed_pose',
            'wall_id': self.wall_id,
            'timestamp': original_data.get('timestamp', time.time()),
            'landmarks': transformed_landmarks,
            'original_landmark_count': len(original_data.get('landmarks', [])),
            'transformed_landmark_count': len(transformed_landmarks),
            'image_width': original_data.get('width'),
            'image_height': original_data.get('height')
        }
        
        await self.output_client.send_message(message)
        logger.debug(f"Sent transformed pose data with {len(transformed_landmarks)} landmarks")
    
    async def run(self):
        """Main event loop"""
        if not await self.setup():
            logger.error("Setup failed, exiting")
            return
        
        logger.info("Starting WebSocket pose receiver...")
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
    help = 'WebSocket-based pose receiver for transforming MediaPipe pose landmarks from phone camera'
    
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
            help='WebSocket URL for receiving pose data from phone camera'
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
            "logs/websocket_pose_receiver.log",
            rotation="1 day",
            retention="1 week",
            level="DEBUG" if options['debug'] else "INFO"
        )
        logger.add(
            lambda msg: self.stdout.write(msg),
            level="DEBUG" if options['debug'] else "INFO"
        )
        
        # Create and run receiver
        receiver = WebSocketPoseReceiver(
            wall_id=options['wall_id'],
            input_websocket_url=options['input_websocket_url'],
            output_websocket_url=options['output_websocket_url'],
            reconnect_delay=options['reconnect_delay'],
            debug=options['debug']
        )
        
        # Run receiver
        asyncio.run(receiver.run())