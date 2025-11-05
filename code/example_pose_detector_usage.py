#!/usr/bin/env python3
"""
Example usage of the Pose Detector to WebSocket script

This script demonstrates how to use the PoseDetectorToWebSocket class
programmatically in your own code.
"""

import asyncio
import logging
from pose_detector_to_websocket import PoseDetectorToWebSocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_with_camera():
    """Example: Stream from camera to default WebSocket"""
    logger.info("Example: Streaming from camera to default WebSocket")
    
    detector = PoseDetectorToWebSocket(
        websocket_url="wss://climber.dev.maptnh.net:443/ws/pose/",
        video_source="0",  # Default camera
        loop_video=False,
        target_fps=15,  # Lower FPS for demonstration
        debug=True
    )
    
    try:
        await detector.run()
    except KeyboardInterrupt:
        logger.info("Example stopped by user")


async def example_with_camera_dry_run():
    """Example: Test pose detection from camera without WebSocket"""
    logger.info("Example: Testing pose detection from camera (dry-run mode)")
    
    detector = PoseDetectorToWebSocket(
        websocket_url="wss://climber.dev.maptnh.net:443/ws/pose/",
        video_source="0",  # Default camera
        loop_video=False,
        target_fps=15,  # Lower FPS for demonstration
        debug=True,
        dry_run=True  # Don't connect to WebSocket
    )
    
    try:
        await detector.run()
    except KeyboardInterrupt:
        logger.info("Example stopped by user")


async def example_with_video_file():
    """Example: Stream from video file with looping"""
    logger.info("Example: Streaming from video file with looping")
    
    # Use one of the existing video files in the project
    video_file = "code/data/IMG_2568.mp4"
    
    detector = PoseDetectorToWebSocket(
        websocket_url="wss://climber.dev.maptnh.net:443/ws/pose/",
        video_source=video_file,
        loop_video=True,  # Loop the video
        target_fps=10,  # Lower FPS for demonstration
        debug=True
    )
    
    try:
        await detector.run()
    except KeyboardInterrupt:
        logger.info("Example stopped by user")


async def example_with_video_file_dry_run():
    """Example: Test pose detection from video file without WebSocket"""
    logger.info("Example: Testing pose detection from video file (dry-run mode)")
    
    # Use one of the existing video files in the project
    video_file = "code/data/IMG_2568.mp4"
    
    detector = PoseDetectorToWebSocket(
        websocket_url="wss://climber.dev.maptnh.net:443/ws/pose/",
        video_source=video_file,
        loop_video=True,  # Loop the video
        target_fps=10,  # Lower FPS for demonstration
        debug=True,
        dry_run=True  # Don't connect to WebSocket
    )
    
    try:
        await detector.run()
    except KeyboardInterrupt:
        logger.info("Example stopped by user")


async def example_with_local_websocket():
    """Example: Stream to local WebSocket server"""
    logger.info("Example: Streaming to local WebSocket server")
    
    detector = PoseDetectorToWebSocket(
        websocket_url="ws://localhost:8000/ws/pose/",  # Local Django server
        video_source="0",  # Default camera
        loop_video=False,
        target_fps=20,
        debug=True
    )
    
    try:
        await detector.run()
    except KeyboardInterrupt:
        logger.info("Example stopped by user")


async def main():
    """Main function with example selection"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pose Detector Usage Examples")
    parser.add_argument(
        "--example",
        choices=["camera", "camera-dry", "video", "video-dry", "local"],
        default="camera",
        help="Example to run (camera, camera-dry, video, video-dry, or local)"
    )
    
    args = parser.parse_args()
    
    if args.example == "camera":
        await example_with_camera()
    elif args.example == "camera-dry":
        await example_with_camera_dry_run()
    elif args.example == "video":
        await example_with_video_file()
    elif args.example == "video-dry":
        await example_with_video_file_dry_run()
    elif args.example == "local":
        await example_with_local_websocket()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Example stopped by user")