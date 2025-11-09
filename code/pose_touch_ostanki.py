### pose touch detector hopefuly befor copy updated 2025-10-26 18:00


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
                 fake_pose=False, video_file=None, loop=False, touch_threshold=0.1,
                 debug=False, show_video=False, show_skeleton=False, show_svg=False):
        """
        Initialize pose touch detector.
        
        Args:
            wall_id: ID of the wall to process
            session_id: ID of the session for WebSocket streaming
            camera_source: Camera source (0 for default, or URL for IP camera)
            fake_pose: Use fake pose streamer for testing
            video_file: Path to the video file to use as input
            loop: Loop the video file indefinitely when using file input
            touch_threshold: Threshold for determining touch
            debug: Enable debug output
            show_video: Display the video feed with OpenCV
            show_skeleton: Display the detected skeleton overlay
            show_svg: Display the SVG holds overlay
        """
        self.wall_id = wall_id
        self.session_id = session_id
        self.camera_source = camera_source
        self.fake_pose = fake_pose
        self.video_file = video_file
        self.loop = loop
        self.touch_threshold = touch_threshold
        self.debug = debug
        self.show_video = show_video
        self.show_skeleton = show_skeleton
        self.show_svg = show_svg
        
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
        
        # Visualization setup
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.svg_overlay = None
        
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
        
        # Setup SVG overlay if visualization is enabled
        if self.show_svg:
            self._setup_svg_overlay()
        
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
    
    def _setup_svg_overlay(self):
        """Setup SVG overlay for visualization using calibration data."""
        try:
            # Get SVG dimensions
            svg_width, svg_height = self.svg_parser.get_svg_dimensions()
            logger.info(f"SVG dimensions: {svg_width}x{svg_height}")
            
            # Create a blank image for SVG overlay with the same dimensions as the camera
            self.svg_overlay = np.zeros((720, 1280, 3), dtype=np.uint8)
            
            # Initialize calibration utils
            calibration_utils = CalibrationUtils()
            
            # Get the inverse transformation matrix (SVG to camera coordinates)
            # The calibration transforms camera coordinates to SVG coordinates,
            # so we need the inverse to transform SVG to camera coordinates
            try:
                # Load the perspective transform from calibration
                transform_matrix = self.calibration.perspective_transform
                
                # Calculate the inverse transformation matrix
                inv_transform_matrix = cv2.invert(transform_matrix)
                logger.info("Using calibration transformation for SVG overlay")
            except Exception as e:
                logger.error(f"Failed to get calibration transform: {e}")
                # Fallback to simple scaling if calibration fails
                scale_x = 1280 / svg_width
                scale_y = 720 / svg_height
                scale = max(scale_x, scale_y) * 1.2
                offset_x = (1280 - svg_width * scale) / 2
                offset_y = (720 - svg_height * scale) / 2
                logger.info(f"Falling back to simple scaling: X={scale_x}, Y={scale_y}, Using={scale}")
                inv_transform_matrix = None
            
            # Draw SVG paths on the overlay
            for path_id, path_data in self.svg_parser.paths.items():
                try:
                    # Use path_to_polygon method to get a better representation of the path
                    polygon_points = self.svg_parser.path_to_polygon(path_data['d'], num_points=100)
                    
                    if polygon_points is not None and len(polygon_points) > 0:
                        if inv_transform_matrix is not None:
                            # Transform SVG points to camera coordinates using calibration
                            transformed_points = []
                            for point in polygon_points:
                                # Convert to homogeneous coordinates
                                svg_point = np.array([point[0], point[1], 1.0])
                                # Apply inverse transformation
                                camera_point = inv_transform_matrix @ svg_point
                                # Convert back from homogeneous coordinates
                                if camera_point[2] != 0:
                                    x = camera_point[0] / camera_point[2]
                                    y = camera_point[1] / camera_point[2]
                                    transformed_points.append([x, y])
                            
                            polygon_points = np.array(transformed_points)
                        else:
                            # Fallback to simple scaling
                            polygon_points[:, 0] = polygon_points[:, 0] * scale + offset_x
                            polygon_points[:, 1] = polygon_points[:, 1] * scale + offset_y
                        
                        # Convert to integer for OpenCV
                        points = polygon_points.astype(np.int32)
                        
                        # Draw the path as a filled polygon with more visible colors
                        cv2.fillPoly(self.svg_overlay, [points], (0, 255, 0))  # Green holds
                        cv2.polylines(self.svg_overlay, [points], True, (0, 150, 0), 2)  # Darker green outline
                        
                        logger.debug(f"Drew path {path_id} with {len(points)} points")
                    else:
                        logger.warning(f"Failed to extract polygon for path {path_id}")
                except Exception as e:
                    logger.warning(f"Error drawing path {path_id}: {e}")
                    continue
            
            logger.info("SVG overlay created for visualization")
        except Exception as e:
            logger.error(f"Failed to create SVG overlay: {e}")
            self.svg_overlay = None
    
    def detect_touches(self, frame):
        """
        Detect touches in a frame.
        
        Args:
            frame: Camera frame
            
        Returns:
            Tuple of (touched_objects, annotated_frame)
        """
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process with MediaPipe
        pose_results = self.pose.process(rgb_frame)
        #hand_results = self.hands.process(rgb_frame)
        
        touched_objects = set()
        annotated_frame = frame.copy()
        
        if pose_results.pose_landmarks:
            # Draw skeleton on frame if enabled
            if self.show_skeleton:
                self.mp_drawing.draw_landmarks(
                    annotated_frame,
                    pose_results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
                )
            
            # Get hand landmarks from pose
            #logger.info(f"Detected {pose_results.pose_landmarks}")
            left_hand_landmarks = []
            right_hand_landmarks = []
            
            # Left hand landmarks (pose indices 17-21)
            for i in [17, 19, 21]:  # Wrist, index finger tip, pinky tip
                landmark = pose_results.pose_landmarks.landmark[i]
                left_hand_landmarks.append([landmark.x, landmark.y])
                
                # Draw hand landmarks if skeleton visualization is enabled
                if self.show_skeleton:
                    x = int(landmark.x * annotated_frame.shape[1])
                    y = int(landmark.y * annotated_frame.shape[0])
                    cv2.circle(annotated_frame, (x, y), 5, (0, 0, 255), -1)  # Red for left hand
            
            # Right hand landmarks (pose indices 18-20)
            for i in [18, 20]:  # Wrist, index finger tip
                landmark = pose_results.pose_landmarks.landmark[i]
                right_hand_landmarks.append([landmark.x, landmark.y])
                
                # Draw hand landmarks if skeleton visualization is enabled
                if self.show_skeleton:
                    x = int(landmark.x * annotated_frame.shape[1])
                    y = int(landmark.y * annotated_frame.shape[0])
                    cv2.circle(annotated_frame, (x, y), 5, (255, 0, 0), -1)  # Blue for right hand
            
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
                
                # Draw touch indicator if visualization is enabled
                if self.show_skeleton and touched_objects:
                    x = int(left_hand_pos[0] * annotated_frame.shape[1])
                    y = int(left_hand_pos[1] * annotated_frame.shape[0])
                    cv2.circle(annotated_frame, (x, y), 15, (0, 255, 0), 3)  # Green circle for touch
            
            if right_hand_landmarks:
                right_hand_pos = np.mean(right_hand_landmarks, axis=0)
                touched_objects.update(self._check_touch_at_position(right_hand_pos))
                
                # Draw touch indicator if visualization is enabled
                if self.show_skeleton and touched_objects:
                    x = int(right_hand_pos[0] * annotated_frame.shape[1])
                    y = int(right_hand_pos[1] * annotated_frame.shape[0])
                    cv2.circle(annotated_frame, (x, y), 15, (0, 255, 0), 3)  # Green circle for touch
        
        if len(touched_objects):
            logger.info(f"Touched: {touched_objects}")
        return list(touched_objects), annotated_frame
    
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
    
    def _display_frame(self, frame, touched_objects):
        """
        Display frame with optional overlays.
        
        Args:
            frame: Camera frame
            touched_objects: List of touched object IDs
        """
        if not self.show_video:
            return
        
        display_frame = frame.copy()
        
        # Add SVG overlay if enabled
        if self.show_svg and self.svg_overlay is not None:
            # Resize SVG overlay to match frame dimensions
            frame_height, frame_width = display_frame.shape[:2]
            resized_svg_overlay = cv2.resize(self.svg_overlay, (frame_width, frame_height))
            
            # Create a mask for non-zero pixels in the SVG overlay
            mask = np.any(resized_svg_overlay > 0, axis=2).astype(np.uint8) * 255
            
            # Apply overlay only where mask is non-zero
            overlay_mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            overlay_mask = overlay_mask / 255.0  # Normalize to 0-1 range
            
            # Blend frame with SVG overlay using the mask
            alpha = 0.6  # Transparency factor for better visibility
            display_frame = display_frame * (1 - overlay_mask * alpha) + resized_svg_overlay * overlay_mask * alpha
            display_frame = display_frame.astype(np.uint8)
        
        # Add text showing touched objects
        if touched_objects:
            text = f"Touched: {', '.join(touched_objects)}"
            cv2.putText(display_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 255, 0), 2)
        
        # Display frame
        cv2.imshow('Pose Touch Detector', display_frame)
        
        # Check for key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.running = False
    
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
                    touched_objects, annotated_frame = self.detect_touches(frame)
                
                # Stream touched objects
                self.stream_touched_objects(touched_objects)
                
                # Display frame with visualizations
                if not self.fake_pose:
                    self._display_frame(annotated_frame, touched_objects)
                
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
        
        # Close OpenCV windows if they were opened
        if self.show_video:
            cv2.destroyAllWindows()
        
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
            help='ID of wall to process'
        )
        parser.add_argument(
            '--session-id',
            type=int,
            help='ID of session for WebSocket streaming'
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
            help='Loop video file indefinitely when using file input'
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
        parser.add_argument(
            '--show-video',
            action='store_true',
            help='Display video feed with OpenCV'
        )
        parser.add_argument(
            '--show-skeleton',
            action='store_true',
            help='Display detected skeleton overlay on video'
        )
        parser.add_argument(
            '--show-svg',
            action='store_true',
            help='Display SVG holds overlay on video'
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
            debug=options['debug'],
            show_video=options['show_video'],
            show_skeleton=options['show_skeleton'],
            show_svg=options['show_svg']
        )
        
        detector.run()