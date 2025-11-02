import os
import json
import time
import threading
import argparse
from datetime import datetime

import cv2
import numpy as np
import mediapipe as mp
from loguru import logger
from django.core.management.base import BaseCommand
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from climber.models import Wall, WallCalibration, Session
from climber.svg_utils import SVGParser
from climber.calibration.aruco_detector import ArUcoDetector
from climber.calibration.calibration_utils import CalibrationUtils


class PoseTouchDetector:
    """
    Main class for detecting pose touches on climbing wall objects.
    Integrates camera input, pose detection, coordinate transformation,
    and WebSocket streaming.
    """
    
    def __init__(self, wall_id, session_id=None, camera_source=0,
                 fake_pose=False, video_file=None, loop=False, touch_threshold=0.1, debug=False):
        """
        Initialize the pose touch detector.
        
        Args:
            wall_id: ID of the wall to process
            session_id: ID of the session for WebSocket streaming
            camera_source: Camera source (0 for default, or URL for IP camera)
            fake_pose: Use fake pose streamer for testing
            video_file: Path to video file to use as input
            loop: Loop the video file indefinitely when using file input
            touch_threshold: Threshold for determining touch
            debug: Enable debug output
        """
        self.wall_id = wall_id
        self.session_id = session_id
        self.camera_source = camera_source
        self.fake_pose = fake_pose
        self.video_file = video_file
        self.loop = loop
        self.touch_threshold = touch_threshold
        self.debug = debug
        
        # Initialize MediaPipe
        self.mp_pose = mp.solutions.pose
        self.mp_hands = mp.solutions.hands
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Initialize components
        self.wall = None
        self.calibration = None
        self.svg_parser = None
        self.channel_layer = get_channel_layer()
        logger.info(self.channel_layer)
        
        # Camera setup
        self.cap = None
        self.running = False
        
        # Previous touched objects for change detection
        self.previous_touched = set()
        
        logger.info(f"Initialized PoseTouchDetector for wall {wall_id}")
    
    def setup(self):
        """Setup all components and validate configuration."""
        logger.info("Setting up PoseTouchDetector...")
        
        # Get wall
        try:
            self.wall = Wall.objects.get(id=self.wall_id)
            logger.info(f"Loaded wall: {self.wall.name}")
        except Wall.DoesNotExist:
            logger.error(f"Wall with ID {self.wall_id} not found")
            return False
        
        # Get calibration
        try:
            self.calibration = WallCalibration.objects.filter(wall=self.wall).latest('created')
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
        #print(svg_path)
        self.svg_parser = SVGParser(svg_file_path=svg_path)
        # Extract paths and store them as an attribute
        self.svg_parser.paths = self.svg_parser.extract_paths()
        logger.info(f"Loaded SVG with {len(self.svg_parser.paths)} paths")
        
        # Setup camera or video file
        if self.fake_pose:
            logger.info("Using fake pose streamer")
            # Setup fake pose streamer
            from pose_streamer_fake import FakePoseStreamer
            self.pose_streamer = FakePoseStreamer()
        elif self.video_file:
            logger.info(f"Using video file: {self.video_file}")
            if not os.path.exists(self.video_file):
                logger.error(f"Video file not found: {self.video_file}")
                return False
            self.cap = cv2.VideoCapture(self.video_file)
            if not self.cap.isOpened():
                logger.error(f"Failed to open video file: {self.video_file}")
                return False
            self.is_video_file = True
        else:
            logger.info(f"Setting up camera: {self.camera_source}")
            self.cap = cv2.VideoCapture(self.camera_source)
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera: {self.camera_source}")
                return False
            self.is_video_file = False
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        logger.info("Setup complete")
        return True
    
    def detect_touches(self, frame):
        """
        Detect touches in a frame.
        
        Args:
            frame: Camera frame
            
        Returns:
            List of touched object IDs
        """
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process with MediaPipe
        pose_results = self.pose.process(rgb_frame)
        #hand_results = self.hands.process(rgb_frame)
        
        touched_objects = set()
        
        if pose_results.pose_landmarks:
            # Get hand landmarks from pose
            #logger.info(f"Detected {pose_results.pose_landmarks}")
            left_hand_landmarks = []
            right_hand_landmarks = []
            
            # Left hand landmarks (pose indices 17-21)
            for i in [17, 19, 21]:  # Wrist, index finger tip, pinky tip
                landmark = pose_results.pose_landmarks.landmark[i]
                left_hand_landmarks.append([landmark.x, landmark.y])
            
            # Right hand landmarks (pose indices 18-20)
            for i in [18, 20]:  # Wrist, index finger tip
                landmark = pose_results.pose_landmarks.landmark[i]
                right_hand_landmarks.append([landmark.x, landmark.y])
            
            # Add hand-specific landmarks if available
            # if hand_results.multi_hand_landmarks:
            #     for hand_idx, hand_landmarks in enumerate(hand_results.multi_hand_landmarks):
            #         handedness = hand_results.multi_handedness[hand_idx].classification[0].label
                    
            #         # Get finger tips (indices 4, 8, 12, 16, 20)
            #         for tip_idx in [4, 8, 12, 16, 20]:
            #             landmark = hand_landmarks.landmark[tip_idx]
            #             if handedness == "Left":
            #                 left_hand_landmarks.append([landmark.x, landmark.y])
            #             else:
            #                 right_hand_landmarks.append([landmark.x, landmark.y])
            
            # Calculate average hand positions
            if left_hand_landmarks:
                left_hand_pos = np.mean(left_hand_landmarks, axis=0)
                touched_objects.update(self._check_touch_at_position(left_hand_pos))
            
            if right_hand_landmarks:
                right_hand_pos = np.mean(right_hand_landmarks, axis=0)
                touched_objects.update(self._check_touch_at_position(right_hand_pos))
        logger.info(f"Touched: {touched_objects}")
        return list(touched_objects)
    
    def _check_touch_at_position(self, position):
        """
        Check if a position touches any SVG objects.
        
        Args:
            position: Normalized position [x, y] where x,y in [0,1]
            
        Returns:
            Set of touched object IDs
        """
        # Convert normalized position to image coordinates
        h, w = 720, 1280  # Camera resolution
        img_x = int(position[0] * w)
        img_y = int(position[1] * h)
        
        # Transform to SVG coordinates using calibration
        calibration_utils = CalibrationUtils()
        svg_point = calibration_utils.transform_point_to_svg(
            (img_x, img_y),
            self.calibration.perspective_transform
        )
        
        # Check which SVG paths contain this point
        touched_objects = set()
        for path_id, path_data in self.svg_parser.paths.items():
            if self.svg_parser.point_in_path((svg_point[0], svg_point[1]), path_data['d']):
                touched_objects.add(path_id)
        
        return touched_objects
    
    def stream_touched_objects(self, touched_objects):
        """
        Stream touched objects to WebSocket channel.
        
        Args:
            touched_objects: List of touched object IDs
        """
        if not self.session_id:
            return
        
        # Only send if touched objects changed
        current_touched = set(touched_objects)
        if current_touched == self.previous_touched:
            return
        
        self.previous_touched = current_touched
        
        # Prepare message
        message = {
            'type': 'pose_touch_update',
            'timestamp': datetime.now().isoformat(),
            'wall_id': self.wall_id,
            'touched_objects': list(current_touched)
        }
        
        # Send to WebSocket
        try:
            async_to_sync(self.channel_layer.group_send)(
                f"session_{self.session_id}",
                {
                    'type': 'pose_touch_message',
                    'message': message
                }
            )
            logger.debug(f"Sent touch update: {current_touched}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
    
    def run(self):
        """Main processing loop."""
        if not self.setup():
            logger.error("Setup failed, exiting")
            return
        
        logger.info("Starting pose touch detection...")
        self.running = True
        
        try:
            while self.running:
                if self.fake_pose:
                    # Get fake pose data
                    frame, pose_data = self.pose_streamer.get_frame()
                    if frame is None:
                        time.sleep(0.03)  # ~30 FPS
                        continue
                    
                    # Process pose data directly
                    touched_objects = self._process_fake_pose_data(pose_data)
                else:
                    # Get frame from camera or video file
                    ret, frame = self.cap.read()
                    if not ret:
                        if hasattr(self, 'is_video_file') and self.is_video_file:
                            if self.loop:
                                logger.info("Restarting video from beginning...")
                                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                continue
                            else:
                                logger.info("End of video file. Exiting...")
                                break
                        else:
                            logger.warning("Failed to read frame from camera")
                            time.sleep(0.1)
                            continue
                    
                    # Detect touches
                    touched_objects = self.detect_touches(frame)
                
                # Stream touched objects
                self.stream_touched_objects(touched_objects)
                
                # Debug output
                if self.debug and touched_objects:
                    logger.info(f"Touched objects: {touched_objects}")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.cleanup()
    
    def _process_fake_pose_data(self, pose_data):
        """
        Process fake pose data and detect touches.
        
        Args:
            pose_data: Fake pose data dictionary
            
        Returns:
            List of touched object IDs
        """
        touched_objects = set()
        
        if 'pose_landmarks' in pose_data:
            # Extract hand positions from fake pose data
            landmarks = pose_data['pose_landmarks']
            
            # Left hand (simplified)
            if 'left_wrist' in landmarks and 'left_index' in landmarks:
                left_hand_pos = np.mean([
                    landmarks['left_wrist'],
                    landmarks['left_index']
                ], axis=0)
                touched_objects.update(self._check_touch_at_position(left_hand_pos))
            
            # Right hand (simplified)
            if 'right_wrist' in landmarks and 'right_index' in landmarks:
                right_hand_pos = np.mean([
                    landmarks['right_wrist'],
                    landmarks['right_index']
                ], axis=0)
                touched_objects.update(self._check_touch_at_position(right_hand_pos))
        
        return list(touched_objects)
    
    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up...")
        self.running = False
        
        if self.cap and self.cap.isOpened():
            self.cap.release()
        
        self.pose.close()
        self.hands.close()
        
        logger.info("Cleanup complete")


class Command(BaseCommand):
    help = 'Detect pose touches on climbing wall objects and stream to WebSocket'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--wall-id',
            type=int,
            required=True,
            help='ID of the wall to process'
        )
        parser.add_argument(
            '--session-id',
            type=int,
            help='ID of the session for WebSocket streaming'
        )
        parser.add_argument(
            '--camera-source',
            type=str,
            default='0',
            help='Camera source (0 for default, or URL for IP camera)'
        )
        parser.add_argument(
            '--fake-pose',
            action='store_true',
            help='Use fake pose streamer for testing'
        )
        parser.add_argument(
            '--video-file',
            type=str,
            help='Path to video file to use as input'
        )
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Loop the video file indefinitely when using file input'
        )
        parser.add_argument(
            '--touch-threshold',
            type=float,
            default=0.1,
            help='Threshold for determining touch'
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
            "logs/pose_touch_detector.log",
            rotation="1 day",
            retention="1 week",
            level="DEBUG" if options['debug'] else "INFO"
        )
        logger.add(
            lambda msg: self.stdout.write(msg),
            level="DEBUG" if options['debug'] else "INFO"
        )
        
        # Create and run detector
        detector = PoseTouchDetector(
            wall_id=options['wall_id'],
            session_id=options.get('session_id'),
            camera_source=options['camera_source'],
            fake_pose=options['fake_pose'],
            video_file=options.get('video_file'),
            loop=options['loop'],
            touch_threshold=options['touch_threshold'],
            debug=options['debug']
        )
        
        detector.run()