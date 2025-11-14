#!/usr/bin/env python3
"""
Pose Replayer Script

Reads pose data from a JSONS file (JSON Lines format) and replays it 
to a WebSocket endpoint with proper timing based on timestamps in the data.
The script loops indefinitely when reaching the end of the file.

Usage:
    python pose_replayer.py --file data.jsons --websocket ws://localhost:8000/ws/pose/
"""

import os
import sys
import json
import time
import asyncio
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Optional, Union

import websockets
from loguru import logger


class PoseReplayerError(Exception):
    """Base exception for pose replayer"""
    pass


class FileLoadError(PoseReplayerError):
    """Error loading file"""
    pass


class WebSocketConnectionError(PoseReplayerError):
    """WebSocket connection error"""
    pass


class TimestampError(PoseReplayerError):
    """Error with timestamps"""
    pass


class WebSocketClient:
    """WebSocket client for sending pose data with reconnection logic"""
    
    def __init__(self, url: str, reconnect_delay: float = 5.0):
        self.url = url
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        self.message_queue = asyncio.Queue()
        self.sender_task = None
        
    async def connect(self):
        """Connect to WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to WebSocket")
                self.current_reconnect_delay = self.reconnect_delay  # Reset delay on success
                
                # Start sender task
                self.sender_task = asyncio.create_task(self.message_sender())
                
                # Keep connection alive
                await self.keep_alive()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
            except Exception as e:
                logger.error(f"Unexpected error in WebSocket: {e}")
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
            logger.warning("WebSocket connection closed during keep-alive")
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
                logger.warning("WebSocket connection closed while sending")
                # Re-queue message
                await self.message_queue.put(message)
                raise
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                # Re-queue message
                await self.message_queue.put(message)
    
    async def send_message(self, message: Dict):
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


class JsonsFileReader:
    """Reader for JSONS (JSON Lines) format files"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.json_data = []
        self.timestamps = []
        
    async def load_file(self):
        """Load and parse all JSON lines from file"""
        try:
            with open(self.file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        json_obj = json.loads(line)
                        self.json_data.append(json_obj)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON on line {line_num}: {e}")
                        continue
            
            logger.info(f"Loaded {len(self.json_data)} JSON objects from {self.file_path}")
            
            if not self.json_data:
                raise FileLoadError(f"No valid JSON objects found in {self.file_path}")
            
        except FileNotFoundError:
            raise FileLoadError(f"File not found: {self.file_path}")
        except Exception as e:
            raise FileLoadError(f"Error reading file {self.file_path}: {e}")
    
    def extract_timestamps(self, timestamp_field: str = "timestamp"):
        """Extract timestamps from JSON objects"""
        self.timestamps = []
        
        for i, obj in enumerate(self.json_data):
            timestamp = None
            
            # Try direct field access
            if timestamp_field in obj:
                timestamp = obj[timestamp_field]
            
            # Try nested in session
            elif 'session' in obj and timestamp_field in obj['session']:
                timestamp = obj['session'][timestamp_field]
            
            # Try other common fields
            elif 'time' in obj:
                timestamp = obj['time']
            elif 'created_at' in obj:
                timestamp = obj['created_at']
            elif 'startTime' in obj:
                timestamp = obj['startTime']
            
            if timestamp is None:
                logger.warning(f"No timestamp found in object {i}, using index")
                timestamp = i  # Fallback to index
            
            # Convert to float if needed
            if isinstance(timestamp, str):
                try:
                    # Try ISO format first
                    timestamp = datetime.fromisoformat(
                        timestamp.replace('Z', '+00:00')
                    ).timestamp()
                except ValueError:
                    try:
                        # Try parsing as float
                        timestamp = float(timestamp)
                        # Check if it's likely in microseconds or milliseconds (large number)
                        # These timestamps appear to be in microseconds since they're around 1.7e15
                        # Convert microseconds to seconds by dividing by 1,000,000
                        if isinstance(timestamp, int) and timestamp > 1e12:  # Large integer timestamps are likely microseconds
                            timestamp = timestamp / 1000000.0
                    except ValueError:
                        logger.warning(f"Cannot parse timestamp '{timestamp}' in object {i}")
                        timestamp = i
            
            self.timestamps.append(float(timestamp))
        
        return self.timestamps
    
    def calculate_delays(self) -> List[float]:
        """Calculate delays between consecutive messages"""
        if len(self.timestamps) < 2:
            return [0.0] * len(self.timestamps)
        
        delays = []
        for i in range(len(self.timestamps)):
            if i == 0:
                delays.append(0.0)  # No delay for first message (send immediately)
            else:
                delay = self.timestamps[i] - self.timestamps[i-1]
                # Convert milliseconds to seconds if needed
                # If timestamps are in milliseconds (likely if values > 1e6), convert to seconds
                if isinstance(timestamp, int) and timestamp > 1000000:  # Large integer timestamps are likely milliseconds
                    delay = delay / 1000.0
                # Ensure non-negative delay
                delays.append(max(0.0, delay))
        
        return delays


class PoseReplayer:
    """Main pose replayer class"""
    
    def __init__(self, file_path: str, websocket_url: str, 
                 timestamp_field: str = "timestamp", 
                 loop: bool = True,
                 reconnect_delay: float = 5.0,
                 debug: bool = False):
        self.file_path = file_path
        self.websocket_url = websocket_url
        self.timestamp_field = timestamp_field
        self.loop = loop
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        
        # Components
        self.file_reader = JsonsFileReader(file_path)
        self.websocket_client = WebSocketClient(websocket_url, reconnect_delay)
        
        # State
        self.running = False
        self.delays = []
        
    async def setup(self):
        """Setup all components"""
        try:
            # Load and parse file
            await self.file_reader.load_file()
            
            # Extract timestamps
            self.file_reader.extract_timestamps(self.timestamp_field)
            
            # Calculate delays
            self.delays = self.file_reader.calculate_delays()
            
            logger.info(f"Setup complete with {len(self.file_reader.json_data)} messages")
            logger.info(f"Total replay duration: {sum(self.delays):.2f} seconds")
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            raise
    
    async def replay_loop(self):
        """Main replay loop"""
        json_data = self.file_reader.json_data
        
        while self.running:
            logger.info("Starting replay cycle")
            
            for i, (message, delay) in enumerate(zip(json_data, self.delays)):
                if not self.running:
                    break
                
                # Send message immediately (first message has 0 delay)
                await self.websocket_client.send_message(message)
                
                if self.debug:
                    logger.debug(f"Sent message {i+1}/{len(json_data)}")
                
                # Show timing until next message
                if i < len(json_data) - 1:
                    if delay > 0:
                        logger.info(f"Waiting {delay:.3f} seconds until next message...")
                        await asyncio.sleep(delay)
                    else:
                        logger.debug("No delay needed for next message (concurrent timestamps)")
                else:
                    logger.info("End of replay cycle reached")
            
            # Check if we should continue looping
            if not self.loop:
                logger.info("Replay complete (loop disabled)")
                break
            
            logger.info("Replay cycle complete, restarting...")
    
    async def run(self):
        """Main entry point"""
        try:
            # Setup
            await self.setup()
            
            # Start WebSocket client
            self.running = True
            self.websocket_client.running = True
            websocket_task = self.websocket_client.start()
            
            # Wait a bit for connection
            await asyncio.sleep(1)
            
            # Start replay
            await self.replay_loop()
            
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
        self.websocket_client.stop()
        
        logger.info("Cleanup complete")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Replay pose data from JSONS file to WebSocket endpoint"
    )
    
    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Path to the input JSONS file'
    )
    parser.add_argument(
        '--websocket',
        type=str,
        required=True,
        help='WebSocket endpoint URL'
    )
    parser.add_argument(
        '--timestamp-field',
        type=str,
        default='timestamp',
        help='Field name containing timestamp (default: timestamp)'
    )
    parser.add_argument(
        '--no-loop',
        action='store_true',
        help='Disable looping (play once)'
    )
    parser.add_argument(
        '--reconnect-delay',
        type=float,
        default=5.0,
        help='Delay between reconnection attempts in seconds (default: 5.0)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Configure logging
    logger.remove()
    if args.debug:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        )
    
    # Validate file exists
    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)
    
    # Validate WebSocket URL
    if not args.websocket.startswith(('ws://', 'wss://')):
        logger.error(f"Invalid WebSocket URL: {args.websocket}")
        logger.error("WebSocket URL must start with ws:// or wss://")
        sys.exit(1)
    
    # Create and run replayer
    replayer = PoseReplayer(
        file_path=args.file,
        websocket_url=args.websocket,
        timestamp_field=args.timestamp_field,
        loop=not args.no_loop,
        reconnect_delay=args.reconnect_delay,
        debug=args.debug
    )
    
    try:
        asyncio.run(replayer.run())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()