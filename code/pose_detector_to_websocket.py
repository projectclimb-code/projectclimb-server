#!/usr/bin/env python3
"""
Pose Detector to WebSocket Script

This script captures video from a camera or file, detects pose using MediaPipe,
and streams the pose data in MediaPipe JSON format to a WebSocket.
"""

import cv2
import mediapipe as mp
import argparse
import asyncio
import websockets
import json
import base64
import numpy as np
import time
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PoseDetectorToWebSocket:
    """Main class for detecting pose and streaming to WebSocket"""
    
    def __init__(
        self,
        websocket_url: str = "wss://climber.dev.maptnh.net:443/ws/pose/",
        video_source: str = "0",
        loop_video: bool = False,
        target_fps: int = 30,
        debug: bool = False,
        dry_run: bool = False
    ):
        """
        Initialize the pose detector
        
        Args:
            websocket_url: WebSocket URL to stream pose data to
            video_source: Video source (camera index or file path)
            loop_video: Whether to loop video files indefinitely
            target_fps: Target frame rate for processing
            debug: Enable debug logging
            dry_run: Run without WebSocket connection (just log pose data)
        """
        self.websocket_url = websocket_url
        self.video_source = video_source
        self.loop_video = loop_video
        self.target_fps = target_fps
        self.debug = debug
        self.dry_run = dry_run
        
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # Determine if video source is a file
        self.is_file = video_source.endswith(('.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv'))
        
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
        # State variables
        self.running = False
        self.websocket = None
        self.cap = None
        self.frame_count = 0
        self.start_time = time.time()
        
    def setup_video_capture(self):
        """Setup video capture from camera or file"""
        try:
            if self.is_file:
                self.cap = cv2.VideoCapture(self.video_source)
                logger.info(f"Opened video file: {self.video_source}")
            else:
                # Try to convert to integer for camera index
                try:
                    camera_index = int(self.video_source)
                    self.cap = cv2.VideoCapture(camera_index)
                    logger.info(f"Opened camera with index: {camera_index}")
                except ValueError:
                    # If not an integer, treat as string (e.g., camera URL)
                    self.cap = cv2.VideoCapture(self.video_source)
                    logger.info(f"Opened video source: {self.video_source}")
            
            if not self.cap.isOpened():
                raise Exception(f"Could not open video source: {self.video_source}")
                
            # Set camera properties if using a camera
            if not self.is_file:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                
            return True
            
        except Exception as e:
            logger.error(f"Error setting up video capture: {e}")
            return False
    
    def process_frame(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Process a frame to detect pose landmarks
        
        Args:
            frame: Input frame as numpy array
            
        Returns:
            Dictionary containing pose landmarks data or None if no pose detected
        """
        try:
            # Convert BGR to RGB
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process the image and detect pose
            results = self.pose.process(image_rgb)
            
            # Prepare pose data in MediaPipe JSON format
            pose_data = {
                "landmarks": [],
                "world_landmarks": [],
                "pose_landmarks": None,
                "pose_world_landmarks": None,
                "frame_number": self.frame_count,
                "timestamp": time.time() - self.start_time
            }
            
            # Extract pose landmarks if detected
            if results.pose_landmarks:
                pose_data["pose_landmarks"] = []
                for landmark in results.pose_landmarks.landmark:
                    pose_data["pose_landmarks"].append({
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z,
                        "visibility": landmark.visibility
                    })
                
                # Also add to landmarks array for compatibility
                pose_data["landmarks"] = pose_data["pose_landmarks"]
            
            # Extract world landmarks if detected
            if results.pose_world_landmarks:
                pose_data["pose_world_landmarks"] = []
                for landmark in results.pose_world_landmarks.landmark:
                    pose_data["pose_world_landmarks"].append({
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z,
                        "visibility": landmark.visibility
                    })
                
                # Also add to world_landmarks array for compatibility
                pose_data["world_landmarks"] = pose_data["pose_world_landmarks"]
            
            return pose_data if pose_data["pose_landmarks"] else None
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return None
    
    async def connect_websocket(self):
        """Connect to WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to WebSocket: {self.websocket_url}")
                self.websocket = await websockets.connect(
                    self.websocket_url,
                    ping_interval=20,
                    ping_timeout=10,
                    open_timeout=10  # Add timeout for connection attempt
                )
                logger.info("Successfully connected to WebSocket")
                return True
                
            except (websockets.exceptions.ConnectionClosedError,
                   websockets.exceptions.InvalidURI,
                   websockets.exceptions.InvalidHandshake,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"WebSocket connection error: {e}")
                if self.running:
                    logger.info("Retrying in 5 seconds...")
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error connecting to WebSocket: {e}")
                if self.running:
                    logger.info("Retrying in 5 seconds...")
                    await asyncio.sleep(5)
        
        return False
    
    async def stream_pose_data(self):
        """Main streaming loop"""
        if not self.setup_video_capture():
            logger.error("Failed to setup video capture")
            return
        
        # Set running flag before attempting WebSocket connection
        self.running = True
        
        # Connect to WebSocket unless in dry-run mode
        if not self.dry_run:
            logger.info("Attempting to connect to WebSocket...")
            if not await self.connect_websocket():
                logger.error("Failed to connect to WebSocket")
                logger.info("Tip: Use --dry-run to test pose detection without WebSocket")
                return
        else:
            logger.info("Running in dry-run mode - pose data will be logged but not sent to WebSocket")
        
        frame_delay = 1.0 / self.target_fps
        
        try:
            while self.running:
                ret, frame = self.cap.read()
                
                if not ret:
                    if self.is_file:
                        logger.info("End of video file reached")
                        if self.loop_video:
                            logger.info("Restarting video from beginning...")
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        else:
                            logger.info("Video file completed. Exiting...")
                            break
                    else:
                        logger.error("Failed to grab frame from camera")
                        break
                
                self.frame_count += 1
                
                # Process frame for pose detection
                pose_data = self.process_frame(frame)
                
                # Send pose data if detected
                if pose_data:
                    if self.dry_run:
                        # In dry-run mode, just log the pose data
                        logger.info(f"Frame {self.frame_count}: Detected pose with {len(pose_data.get('landmarks', []))} landmarks")
                        if self.debug:
                            logger.debug(f"Pose data: {json.dumps(pose_data, indent=2)}")
                    elif self.websocket:
                        try:
                            await self.websocket.send(json.dumps(pose_data))
                            logger.debug(f"Sent frame {self.frame_count} with pose data")
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("WebSocket connection closed")
                            # Try to reconnect
                            if not await self.connect_websocket():
                                logger.error("Failed to reconnect to WebSocket")
                                break
                
                # Log progress every 100 frames
                if self.frame_count % 100 == 0:
                    elapsed = time.time() - self.start_time
                    fps = self.frame_count / elapsed
                    logger.info(f"Processed {self.frame_count} frames ({fps:.2f} fps)")
                
                # Control frame rate
                await asyncio.sleep(frame_delay)
                
        except KeyboardInterrupt:
            logger.info("Streaming interrupted by user")
        except Exception as e:
            logger.error(f"Error in streaming loop: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        self.running = False
        
        if self.websocket and not self.dry_run:
            await self.websocket.close()
        
        if self.cap:
            self.cap.release()
        
        # Log final statistics
        elapsed = time.time() - self.start_time
        logger.info(f"Processed {self.frame_count} frames in {elapsed:.2f} seconds")
        if elapsed > 0:
            logger.info(f"Average FPS: {self.frame_count / elapsed:.2f}")
        
        logger.info("Cleanup complete")
    
    async def run(self):
        """Main entry point"""
        logger.info("Starting Pose Detector to WebSocket...")
        await self.stream_pose_data()


async def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Detect pose from video and stream to WebSocket"
    )
    parser.add_argument(
        "--websocket-url",
        default="wss://climber.dev.maptnh.net:443/ws/pose/",
        help="WebSocket URL to stream pose data to"
    )
    parser.add_argument(
        "--video-source",
        default="0",
        help="Video source (camera index or file path)"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop video files indefinitely"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target frame rate for processing"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without WebSocket connection (just log pose data)"
    )
    
    args = parser.parse_args()
    
    # Create and run pose detector
    detector = PoseDetectorToWebSocket(
        websocket_url=args.websocket_url,
        video_source=args.video_source,
        loop_video=args.loop,
        target_fps=args.fps,
        debug=args.debug,
        dry_run=args.dry_run
    )
    
    await detector.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program stopped by user")