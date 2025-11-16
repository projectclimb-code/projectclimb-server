#!/usr/bin/env python3
"""
Standalone script to visualize climbing session data from WebSocket.

This script connects to a WebSocket that streams session data from
websocket_pose_session_tracker.py and displays:
- The climbing wall SVG with holds
- The climber's skeleton based on pose landmarks
- Real-time updates of hold status (touched/untouched)

Usage:
    python pose_visualizer.py --websocket-url ws://localhost:8000 --wall-svg path/to/wall.svg
"""

import asyncio
import json
import argparse
import sys
import time
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import websockets
except ImportError:
    print("Error: websockets package not found. Install with: pip install websockets")
    sys.exit(1)

try:
    import pygame
except ImportError:
    print("Error: pygame package not found. Install with: pip install pygame")
    sys.exit(1)

try:
    import xml.etree.ElementTree as ET
except ImportError:
    print("Error: xml.etree.ElementTree not available")
    sys.exit(1)

# MediaPipe pose landmark connections for drawing skeleton
POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),  # Face
    (9, 10),  # Mouth
    (11, 12),  # Shoulders
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),  # Left arm
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),  # Right arm
    (11, 23), (12, 24), (23, 24),  # Torso
    (23, 25), (25, 27), (27, 29), (29, 31),  # Left leg
    (24, 26), (26, 28), (28, 30), (30, 32),  # Right leg
    (27, 29), (28, 30), (29, 31), (30, 32)  # Feet
]

# MediaPipe landmark names for reference
LANDMARK_NAMES = [
    'nose_tip', 'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
    'right_eye_inner', 'right_eye', 'right_eye_outer', 'left_ear',
    'right_ear', 'mouth_left', 'mouth_right', 'left_shoulder',
    'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist',
    'right_wrist', 'left_pinky', 'right_pinky', 'left_index',
    'right_index', 'left_thumb', 'right_thumb', 'left_hip',
    'right_hip', 'left_knee', 'right_knee', 'left_ankle',
    'right_ankle', 'left_heel', 'right_heel'
]


class SVGParser:
    """Simple SVG parser for extracting hold information"""
    
    def __init__(self, svg_file_path: str):
        """Initialize SVG parser with file path"""
        self.svg_file_path = svg_file_path
        self.holds = {}
        self.svg_width = 0
        self.svg_height = 0
        self._parse_svg()
    
    def _parse_svg(self):
        """Parse SVG file and extract hold information"""
        try:
            tree = ET.parse(self.svg_file_path)
            root = tree.getroot()
            
            # Handle SVG namespaces
            namespace = {'svg': 'http://www.w3.org/2000/svg'}
            
            # Get SVG dimensions
            self.svg_width = float(root.get('width', 0))
            self.svg_height = float(root.get('height', 0))
            
            # Check for viewBox
            viewbox = root.get('viewBox')
            if viewbox:
                try:
                    values = list(map(float, viewbox.split()))
                    if len(values) >= 4:
                        self.svg_width = values[2]
                        self.svg_height = values[3]
                except (ValueError, IndexError):
                    pass
            
            # Extract holds (elements with class="hold" and id starting with "hold_")
            # Handle both rect and path elements with proper namespace
            for element in root.findall('.//svg:*[@class="hold"]', namespace):
                hold_id = element.get('id')
                if hold_id and hold_id.startswith('hold_'):
                    # Remove namespace from tag for comparison
                    tag_name = element.tag.split('}')[-1] if '}' in element.tag else element.tag
                    
                    if tag_name == 'rect':
                        # Handle rectangle elements
                        x = float(element.get('x', 0))
                        y = float(element.get('y', 0))
                        width = float(element.get('width', 0))
                        height = float(element.get('height', 0))
                        
                        self.holds[hold_id] = {
                            'id': hold_id,
                            'x': x,
                            'y': y,
                            'width': width,
                            'height': height,
                            'center_x': x + width / 2,
                            'center_y': y + height / 2,
                            'status': 'untouched'  # Will be updated from WebSocket data
                        }
                    elif tag_name == 'path':
                        # Handle path elements - extract bounding box from path data
                        path_d = element.get('d', '')
                        bbox = self._get_path_bbox(path_d)
                        if bbox:
                            self.holds[hold_id] = {
                                'id': hold_id,
                                'x': bbox['min_x'],
                                'y': bbox['min_y'],
                                'width': bbox['max_x'] - bbox['min_x'],
                                'height': bbox['max_y'] - bbox['min_y'],
                                'center_x': (bbox['min_x'] + bbox['max_x']) / 2,
                                'center_y': (bbox['min_y'] + bbox['max_y']) / 2,
                                'status': 'untouched'  # Will be updated from WebSocket data
                            }
            
            print(f"Loaded {len(self.holds)} holds from SVG")
            print(f"SVG dimensions: {self.svg_width} x {self.svg_height}")
            
        except Exception as e:
            print(f"Error parsing SVG file: {e}")
            raise
    
    def _get_path_bbox(self, path_d: str) -> Optional[Dict]:
        """
        Extract bounding box from SVG path data
        
        Args:
            path_d: SVG path d attribute string
            
        Returns:
            Dictionary with min_x, min_y, max_x, max_y or None if parsing fails
        """
        try:
            import re
            
            # Extract all coordinates from path data
            # Look for numbers after commands (M, L, C, etc.)
            coords = re.findall(r'[MLC][\s,]*([\d.-]+)', path_d)
            all_points = []
            
            # Parse the path data more comprehensively
            # Split by commands and extract coordinates
            parts = re.split(r'([MLC])', path_d)
            current_x, current_y = 0, 0
            
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    command = parts[i]
                    coord_str = parts[i + 1]
                    
                    # Extract numbers from coordinate string
                    numbers = re.findall(r'-?\d+\.?\d*', coord_str)
                    
                    if command == 'M':  # Move to
                        if len(numbers) >= 2:
                            current_x = float(numbers[0])
                            current_y = float(numbers[1])
                            all_points.append((current_x, current_y))
                    elif command == 'L':  # Line to
                        if len(numbers) >= 2:
                            current_x = float(numbers[0])
                            current_y = float(numbers[1])
                            all_points.append((current_x, current_y))
                    elif command == 'C':  # Curve to
                        if len(numbers) >= 6:
                            # For curves, we'll use the end point
                            current_x = float(numbers[4])
                            current_y = float(numbers[5])
                            all_points.append((current_x, current_y))
            
            if not all_points:
                return None
            
            # Calculate bounding box
            x_coords = [p[0] for p in all_points]
            y_coords = [p[1] for p in all_points]
            
            return {
                'min_x': min(x_coords),
                'max_x': max(x_coords),
                'min_y': min(y_coords),
                'max_y': max(y_coords)
            }
            
        except Exception as e:
            print(f"Error parsing path bounding box: {e}")
            return None
    
    def update_hold_status(self, hold_data: List[Dict]):
        """Update hold status from session data"""
        for hold in hold_data:
            hold_id = hold.get('id')
            if hold_id and hold_id in self.holds:
                self.holds[hold_id]['status'] = hold.get('status', 'untouched')


class PoseVisualizer:
    """Main visualization class"""
    
    def __init__(self, websocket_url: str, svg_file_path: str, 
                 window_width: int = 1200, window_height: int = 800,
                 fps: int = 30):
        """Initialize the visualizer"""
        self.websocket_url = websocket_url
        self.svg_parser = SVGParser(svg_file_path)
        
        # Display settings
        self.window_width = window_width
        self.window_height = window_height
        self.fps = fps
        
        # Calculate scaling to fit SVG in window
        svg_aspect = self.svg_parser.svg_width / self.svg_parser.svg_height
        window_aspect = window_width / window_height
        
        if svg_aspect > window_aspect:
            # SVG is wider, fit to width
            self.scale = window_width / self.svg_parser.svg_width
            self.offset_x = 0
            self.offset_y = (window_height - self.svg_parser.svg_height * self.scale) / 2
        else:
            # SVG is taller, fit to height
            self.scale = window_height / self.svg_parser.svg_height
            self.offset_x = (window_width - self.svg_parser.svg_width * self.scale) / 2
            self.offset_y = 0
        
        # Colors
        self.BG_COLOR = (20, 20, 30)
        self.HOLD_UNTOUCHED_COLOR = (100, 100, 100)
        self.HOLD_TOUCHED_COLOR = (50, 200, 50)
        self.HOLD_COMPLETED_COLOR = (200, 50, 50)
        self.SKELETON_COLOR = (100, 150, 255)
        self.LANDMARK_COLOR = (255, 200, 100)
        self.TEXT_COLOR = (255, 255, 255)
        
        # State
        self.running = False
        self.current_pose = []
        self.session_info = {}
        self.last_update_time = 0
        self.message_count = 0
        
        # Initialize Pygame
        pygame.init()
        self.screen = pygame.display.set_mode((window_width, window_height))
        pygame.display.set_caption("Climbing Session Visualizer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
    
    def svg_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """Convert SVG coordinates to screen coordinates"""
        screen_x = int(x * self.scale + self.offset_x)
        screen_y = int(y * self.scale + self.offset_y)
        return screen_x, screen_y
    
    def draw_holds(self):
        """Draw all holds on the wall"""
        for hold in self.svg_parser.holds.values():
            # Convert coordinates
            x, y = self.svg_to_screen(hold['x'], hold['y'])
            width = int(hold['width'] * self.scale)
            height = int(hold['height'] * self.scale)
            
            # Choose color based on status
            if hold['status'] == 'completed':
                color = self.HOLD_COMPLETED_COLOR
            elif hold['status'] == 'touched':
                color = self.HOLD_TOUCHED_COLOR
            else:
                color = self.HOLD_UNTOUCHED_COLOR
            
            # Draw hold rectangle
            pygame.draw.rect(self.screen, color, (x, y, width, height))
            pygame.draw.rect(self.screen, (255, 255, 255), (x, y, width, height), 1)
            
            # Draw hold ID
            text = self.small_font.render(hold['id'], True, self.TEXT_COLOR)
            text_rect = text.get_rect(center=(x + width//2, y + height//2))
            self.screen.blit(text, text_rect)
    
    def draw_skeleton(self):
        """Draw the climber skeleton from pose landmarks"""
        if not self.current_pose or len(self.current_pose) < 33:
            return
        
        # Convert landmarks to screen coordinates
        screen_landmarks = []
        for landmark in self.current_pose:
            x, y = self.svg_to_screen(landmark['x'], landmark['y'])
            screen_landmarks.append((x, y))
        
        # Draw connections
        for start_idx, end_idx in POSE_CONNECTIONS:
            if (start_idx < len(screen_landmarks) and end_idx < len(screen_landmarks) and
                self.current_pose[start_idx]['visibility'] > 0.5 and
                self.current_pose[end_idx]['visibility'] > 0.5):
                
                start_pos = screen_landmarks[start_idx]
                end_pos = screen_landmarks[end_idx]
                pygame.draw.line(self.screen, self.SKELETON_COLOR, start_pos, end_pos, 3)
        
        # Draw landmarks
        for i, (x, y) in enumerate(screen_landmarks):
            if i < len(self.current_pose) and self.current_pose[i]['visibility'] > 0.5:
                # Color based on landmark type
                if i in [15, 16]:  # Wrists
                    color = (255, 100, 100)  # Red for hands
                    radius = 8
                elif i in [19, 20, 21, 22]:  # Fingers
                    color = (255, 150, 150)  # Light red for fingers
                    radius = 6
                else:
                    color = self.LANDMARK_COLOR
                    radius = 5
                
                pygame.draw.circle(self.screen, color, (x, y), radius)
                pygame.draw.circle(self.screen, (255, 255, 255), (x, y), radius, 1)
    
    def draw_info(self):
        """Draw session information"""
        info_texts = [
            f"Messages received: {self.message_count}",
            f"FPS: {int(self.clock.get_fps())}",
        ]
        
        if self.session_info:
            start_time = self.session_info.get('startTime', 'Unknown')
            status = self.session_info.get('status', 'Unknown')
            info_texts.append(f"Session started: {start_time}")
            info_texts.append(f"Status: {status}")
            
            # Count holds by status
            holds = self.svg_parser.holds
            completed = sum(1 for h in holds.values() if h['status'] == 'completed')
            total = len(holds)
            info_texts.append(f"Holds completed: {completed}/{total}")
        
        y_offset = 10
        for text in info_texts:
            surface = self.font.render(text, True, self.TEXT_COLOR)
            self.screen.blit(surface, (10, y_offset))
            y_offset += 30
    
    async def connect_websocket(self):
        """Connect to WebSocket and listen for messages"""
        try:
            print(f"Connecting to WebSocket: {self.websocket_url}")
            async with websockets.connect(self.websocket_url) as websocket:
                print("Connected to WebSocket")
                
                while self.running:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        # Update pose data
                        if 'pose' in data:
                            self.current_pose = data['pose']
                        
                        # Update session info
                        if 'session' in data:
                            self.session_info = data['session']
                            if 'holds' in data['session']:
                                self.svg_parser.update_hold_status(data['session']['holds'])
                        
                        self.message_count += 1
                        self.last_update_time = time.time()
                        
                    except websockets.exceptions.ConnectionClosed:
                        print("WebSocket connection closed")
                        break
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON received: {e}")
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        
        except Exception as e:
            print(f"WebSocket connection error: {e}")
    
    async def run(self):
        """Main visualization loop"""
        self.running = True
        
        # Start WebSocket connection in background
        websocket_task = asyncio.create_task(self.connect_websocket())
        
        try:
            while self.running:
                # Handle pygame events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
                        elif event.key == pygame.K_SPACE:
                            # Print current session info
                            print("\n=== Current Session Info ===")
                            print(json.dumps(self.session_info, indent=2))
                
                # Clear screen
                self.screen.fill(self.BG_COLOR)
                
                # Draw everything
                self.draw_holds()
                self.draw_skeleton()
                self.draw_info()
                
                # Update display
                pygame.display.flip()
                self.clock.tick(self.fps)
                
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        finally:
            self.running = False
            websocket_task.cancel()
            pygame.quit()
            print("Visualizer stopped")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Visualize climbing session data from WebSocket")
    parser.add_argument(
        '--websocket-url',
        type=str,
        required=True,
        help='WebSocket URL to connect to (e.g., ws://localhost:8000)'
    )
    parser.add_argument(
        '--wall-svg',
        type=str,
        required=True,
        help='Path to the wall SVG file'
    )
    parser.add_argument(
        '--window-width',
        type=int,
        default=1200,
        help='Window width in pixels (default: 1200)'
    )
    parser.add_argument(
        '--window-height',
        type=int,
        default=800,
        help='Window height in pixels (default: 800)'
    )
    parser.add_argument(
        '--fps',
        type=int,
        default=30,
        help='Target FPS for visualization (default: 30)'
    )
    
    args = parser.parse_args()
    
    # Create and run visualizer
    visualizer = PoseVisualizer(
        websocket_url=args.websocket_url,
        svg_file_path=args.wall_svg,
        window_width=args.window_width,
        window_height=args.window_height,
        fps=args.fps
    )
    
    await visualizer.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")