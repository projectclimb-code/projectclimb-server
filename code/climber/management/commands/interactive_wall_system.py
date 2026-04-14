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

from climber.models import Wall, WallCalibration, Route
from climber.svg_utils import SVGParser, get_hold_centers
from climber.calibration.calibration_utils import CalibrationUtils

# Type alias for pre-computed path data
PrecomputedPaths = Dict[str, tuple]  # path_id -> (matplotlib.path.Path, bbox)


class TouchTracker:
    """Track touch durations with tolerance for dropped frames"""
    
    def __init__(self, touch_duration=1.0, lost_tolerance=0.5, multi_trigger=False):
        self.touch_duration = touch_duration
        self.lost_tolerance = lost_tolerance
        self.multi_trigger = multi_trigger
        
        self.touch_start_times = {}  # hold_id -> timestamp
        self.touch_last_seen = {}    # hold_id -> timestamp
        self.sent_events = {}       # hold_id -> last threshold index reached (int)
        
    def update_touches(self, touched_holds, timestamp):
        """Update tracking based on currently touched holds"""
        # Start tracking new touches and update active ones
        for hold_id in touched_holds:
            if hold_id not in self.touch_start_times:
                self.touch_start_times[hold_id] = timestamp
                logger.debug(f"Started tracking touch for hold {hold_id}")
            self.touch_last_seen[hold_id] = timestamp
        
        # Check for dropped touches
        ended_touches = []
        for hold_id, last_seen in list(self.touch_last_seen.items()):
            time_lost = timestamp - last_seen
            if time_lost > self.lost_tolerance and hold_id not in touched_holds:
                ended_touches.append(hold_id)
                
        for hold_id in ended_touches:
            self.end_touch(hold_id)
            
    def end_touch(self, hold_id):
        """Clear touch tracking for a hold"""
        if hold_id in self.touch_start_times:
            del self.touch_start_times[hold_id]
        if hold_id in self.touch_last_seen:
            del self.touch_last_seen[hold_id]
        if hold_id in self.sent_events:
            del self.sent_events[hold_id]
            logger.debug(f"Reset touch tracking for hold {hold_id}")
            
    def clear_all(self):
        self.touch_start_times.clear()
        self.touch_last_seen.clear()
        self.sent_events.clear()
    
    def get_ready_holds(self, timestamp):
        """Return holds that have been touched long enough to trigger an event"""
        ready_holds = []
        
        for hold_id, start_time in list(self.touch_start_times.items()):
            touch_duration = timestamp - start_time
            # Here we hardcode 3.0s intervals for button cycling, 
            # though the Tracker could be made more generic.
            if touch_duration >= self.touch_duration:
                intervals = int(touch_duration // self.touch_duration) if self.touch_duration > 0.0 else 1
                last_triggered = self.sent_events.get(hold_id, 0)
                
                if intervals > last_triggered:
                    # If not multi-trigger, only fire once (step 1)
                    if not self.multi_trigger and last_triggered > 0:
                        continue
                        
                    ready_holds.append({
                        'hold_id': hold_id,
                        'touch_duration': touch_duration,
                        'step': intervals
                    })
                    self.sent_events[hold_id] = intervals
                    logger.debug(f"Hold {hold_id} trigger step {intervals} at {touch_duration:.2f}s")
        
        return ready_holds


class InteractiveState:
    """Manages the interactive wall state machine"""
    
    MODES = [None, 'draw', 'easy', 'medium', 'hard']
    #DEFAULT_CONTROL_BUTTONS = ['btn_draw', 'btn_easy', 'btn_medium', 'btn_hard']
    DEFAULT_CONTROL_BUTTONS = ['btn_draw', 'uuid-24ec8ba8-4347-4987-b4ab-1c8792eca50e', 'uuid-22feefef-f1d3-4130-bbd7-8155dabc1149', 'uuid-7ea1db2a-7fcc-43a4-9fc2-21409d77da2c']
    
    def __init__(self, loop_time=5.0):
        self.mode = None
        self.temporary_route_holds = set()
        
        self.loop_time = loop_time
        self.current_route_index = 0
        self.available_routes = []
        self.last_route_switch_time = 0.0
        
        self.last_state_sent = None
        self.control_buttons = self.DEFAULT_CONTROL_BUTTONS.copy()
        self.button_to_mode = {
            'btn_draw': 'draw',
            'btn_easy': 'easy',
            'btn_medium': 'medium',
            'btn_hard': 'hard'
        }
        self.current_touched_holds = set()


class InputWebSocketClient:
    """WebSocket client for receiving pose/aruco data"""
    
    def __init__(self, url, message_handler, reconnect_delay=5.0):
        self.url = url
        self.message_handler = message_handler
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        
    async def connect(self):
        while self.running:
            try:
                logger.info(f"Connecting to input WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to input WebSocket")
                self.current_reconnect_delay = self.reconnect_delay
                await self.listen_for_messages()
            except Exception as e:
                logger.error(f"Input WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
    
    async def _wait_and_reconnect(self):
        await asyncio.sleep(self.current_reconnect_delay)
        self.current_reconnect_delay = min(self.current_reconnect_delay * 2, 60.0)
    
    async def listen_for_messages(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.message_handler(data)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Input WebSocket connection closed")
            raise
    
    def start(self):
        self.running = True
        return asyncio.create_task(self.connect())
    
    def stop(self):
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())


class OutputWebSocketClient:
    """WebSocket client for sending interactive wall state events"""
    
    def __init__(self, url, reconnect_delay=5.0):
        self.url = url
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        self.message_queue = asyncio.Queue()
        self.sender_task = None
        
    async def connect(self):
        while self.running:
            try:
                logger.info(f"Connecting to output WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to output WebSocket")
                self.current_reconnect_delay = self.reconnect_delay
                
                # Start sender task
                if self.sender_task and not self.sender_task.done():
                    self.sender_task.cancel()
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
                
            except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
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
            finally:
                if self.sender_task and not self.sender_task.done():
                    self.sender_task.cancel()
    
    async def _wait_and_reconnect(self):
        await asyncio.sleep(self.current_reconnect_delay)
        self.current_reconnect_delay = min(self.current_reconnect_delay * 2, 60.0)
    
    async def keep_alive(self):
        try:
            while self.running and self.websocket:
                await asyncio.sleep(30)
                await self.websocket.ping()
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.debug(f"Keep-alive error: {e}")
    
    async def message_sender(self):
        try:
            while self.running and self.websocket:
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                    await self.websocket.send(json.dumps(message))
                    self.message_queue.task_done()
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("Output WebSocket connection closed while sending")
                    # Re-queue message for when we reconnect
                    await self.message_queue.put(message)
                    break
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    await asyncio.sleep(1) # Prevent tight infinite loops
                    # Don't re-queue on unexpected JSON errors, etc. unless it's a network issue
        except asyncio.CancelledError:
            pass
    
    async def send_message(self, message):
        await self.message_queue.put(message)
    
    def start(self):
        self.running = True
        return asyncio.create_task(self.connect())
    
    def stop(self):
        self.running = False
        if self.sender_task and not self.sender_task.done():
            self.sender_task.cancel()
        if self.websocket:
            asyncio.create_task(self.websocket.close())


def validate_pose_data(data):
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"
    if 'landmarks' not in data and 'aruco_markers' not in data and 'light_points' not in data and 'mode' not in data:
        return False, "Missing 'landmarks', 'aruco_markers', 'light_points', or 'mode' key"
    return True, "Valid"


def calculate_extended_hand_landmarks(landmarks, extension_percent=1.0):
    """Calculate extended hand landmarks beyond the palm with robustness for missing landmarks"""
    # Left hand indices: 15 (wrist), 17 (pinky), 19 (index), 21 (thumb), 13 (elbow)
    # Right hand indices: 16 (wrist), 18 (pinky), 20 (index), 22 (thumb), 14 (elbow)
    new_positions = []
    
    for side in ['left', 'right']:
        wrist_idx = 15 if side == 'left' else 16
        pinky_idx = 17 if side == 'left' else 18
        index_idx = 19 if side == 'left' else 20
        thumb_idx = 21 if side == 'left' else 22
        elbow_idx = 13 if side == 'left' else 14
        
        palm_indices = [wrist_idx, pinky_idx, index_idx, thumb_idx]
        available_palm = []
        for idx in palm_indices:
            if idx < len(landmarks):
                l = landmarks[idx]
                # Check visibility if present; some formats might not have it
                if l.get('visibility', 1.0) > 0.1:
                    available_palm.append(l)
        
        if available_palm:
            # Palm center: average of all visible palm landmarks
            palm_x = sum(l['x'] for l in available_palm) / len(available_palm)
            palm_y = sum(l['y'] for l in available_palm) / len(available_palm)
            
            # Direction elbow -> palm (default to "up" if elbow missing)
            elbow = None
            if elbow_idx < len(landmarks):
                e = landmarks[elbow_idx]
                if e.get('visibility', 1.0) > 0.1:
                    elbow = e
            
            if elbow:
                dir_x = palm_x - elbow['x']
                dir_y = palm_y - elbow['y']
                mag = np.sqrt(dir_x**2 + dir_y**2)
                if mag > 0:
                    dir_x /= mag
                    dir_y /= mag
                else:
                    dir_x, dir_y = 0.0, -1.0
            else:
                dir_x, dir_y = 0.0, -1.0 # Default "up" in image coordinates (Y decreases upwards)

            # Palm size estimation
            palm_size = 0.05 # Default fallback
            # Try to get distance between pinky and index if both are available
            p_landmark = landmarks[pinky_idx] if pinky_idx < len(landmarks) and landmarks[pinky_idx].get('visibility', 1.0) > 0.1 else None
            i_landmark = landmarks[index_idx] if index_idx < len(landmarks) and landmarks[index_idx].get('visibility', 1.0) > 0.1 else None
            
            if p_landmark and i_landmark:
                palm_size = np.sqrt((p_landmark['x'] - i_landmark['x'])**2 + (p_landmark['y'] - i_landmark['y'])**2)
            elif len(available_palm) >= 2:
                # Use max distance between any two available palm landmarks as secondary fallback
                max_d = 0
                for a in available_palm:
                    for b in available_palm:
                        d = np.sqrt((a['x'] - b['x'])**2 + (a['y'] - b['y'])**2)
                        if d > max_d: max_d = d
                if max_d > 0: palm_size = max_d
            
            ext_dist = palm_size * (extension_percent / 100.0)
            extended_palm = (palm_x + dir_x * ext_dist, palm_y + dir_y * ext_dist)
            elbow_pos = (elbow['x'], elbow['y']) if elbow else None
            new_positions.append((extended_palm, elbow_pos))
        else:
            new_positions.append((None, None))
            
    return new_positions


def extract_hand_positions(landmarks):
    # Use extended landmarks if available, otherwise fallback to mean of wrist/index
    hand_data = calculate_extended_hand_landmarks(landmarks)
    ext_left, elbow_left = hand_data[0]
    ext_right, elbow_right = hand_data[1]
    
    # Fallback logic removed, rely entirely on robust calculate_extended_hand_landmarks
            
    # Also extract elbows directly if not already found
    if not elbow_left and len(landmarks) > 13:
        elbow_left = (landmarks[13]['x'], landmarks[13]['y'])
    if not elbow_right and len(landmarks) > 14:
        elbow_right = (landmarks[14]['x'], landmarks[14]['y'])
            
    return ext_left, ext_right, elbow_left, elbow_right


def extract_detection_positions(data):
    """Extract positions from both ArUco markers and Light detection points"""
    positions = []
    
    # 1. ArUco markers
    markers = data.get('aruco_markers', [])
    for marker in markers:
        try:
            if 'x' in marker and 'y' in marker:
                positions.append((marker['x'], marker['y']))
            elif 'center' in marker:
                positions.append((marker['center']['x'], marker['center']['y']))
        except Exception:
            pass
            
    # 2. Light points (Laser pointers / Bright lights)
    light_points = data.get('light_points', [])
    for pt in light_points:
        try:
            if 'x' in pt and 'y' in pt:
                positions.append((pt['x'], pt['y']))
        except Exception:
            pass
            
    return positions


def transform_to_svg_coordinates(position, calibration_utils, transform_matrix, svg_size, img_width, img_height, calibration_type='aruco'):
    if position is None:
        return None
        
    if calibration_type == 'manual_points':
        # Manual calibration uses normalized [0, 1] coordinates for both image and SVG in this system
        transformed_norm = calibration_utils.transform_point_to_svg(position, transform_matrix)
        
        if transformed_norm:
            res = (transformed_norm[0] * svg_size[0], transformed_norm[1] * svg_size[1])
            #logger.info(f"Transform (manual): norm {position} -> norm_svg {transformed_norm} -> svg {res}")
            return res
        return None
    else:
        abs_x = position[0] * img_width
        abs_y = position[1] * img_height
        
        transformed_pos = calibration_utils.transform_point_to_svg((abs_x, abs_y), transform_matrix)
        logger.debug(f"Transform (aruco): norm {position} -> abs {abs_x, abs_y} -> svg {transformed_pos}")
        
        return transformed_pos


def check_hold_intersections(position, precomputed_paths=None, buttons=None):
    if position is None:
        return set(), set()
    touched_holds = set()
    touched_buttons = set()
    
    # Check holds using pre-computed matplotlib Path objects with bbox fast rejection
    if precomputed_paths:
        point = (position[0], position[1])
        for path_id, precomputed in precomputed_paths.items():
            try:
                if SVGParser.point_in_precomputed_path(point, precomputed):
                    touched_holds.add(path_id)
            except Exception:
                pass
            
    # Check buttons (rects) - already fast, no change needed
    if buttons:
        for btn_id, btn_data in buttons.items():
            if (btn_data['x'] <= position[0] <= btn_data['x'] + btn_data['width'] and
                btn_data['y'] <= position[1] <= btn_data['y'] + btn_data['height']):
                touched_buttons.add(btn_id)
                
    return touched_holds, touched_buttons


class InteractiveWallCommandSystem:
    def __init__(self, wall_id, input_websocket_url, output_websocket_url, command_websocket_url=None, loop_time=5.0, debug=False, debug_proximity=False):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.command_websocket_url = command_websocket_url
        self.loop_time = loop_time
        self.debug = debug
        self.debug_proximity = debug_proximity
        
        self.hold_centers = {}
        self.last_debug_output_time = 0.0
        self.precomputed_paths = {}  # Pre-computed matplotlib Path objects + bboxes
        
        self.wall = None
        self.calibration = None
        self.svg_parser = None
        self.svg_size = (0, 0)
        self.calibration_utils = None
        self.transform_matrix = None
        
        self.input_client = None
        self.output_client = None
        self.command_client = None
        
        self.buttons = {} # btn_id -> btn_data from SVG
        
        # We track hands fast (1.0s tolerance) to trigger buttons, Detection slow (0.5s tolerance) to lock in holds
        self.hand_tracker = TouchTracker(touch_duration=2.0, lost_tolerance=1.0, multi_trigger=True)
        self.detection_tracker = TouchTracker(touch_duration=0.0, lost_tolerance=0.5, multi_trigger=False)
        
        self.last_palm_l_img = None
        self.last_palm_r_img = None
        self.last_palm_l_svg = None
        self.last_palm_r_svg = None
        self.last_calibrated_landmarks = []
        
        self.state = InteractiveState(loop_time=loop_time)
        self.running = False
        self.last_state_send_time = 0.0
        self.last_pose_send_time = 0.0  # Throttle per-frame state sends
        self.pose_send_interval = 1.0 / 30  # Max 30 sends/sec from pose frames
        
    async def setup(self):
        try:
            self.wall = await database_sync_to_async(Wall.objects.get)(id=self.wall_id)
        except Wall.DoesNotExist:
            logger.error("Wall not found")
            return False
            
        try:
            self.calibration = await database_sync_to_async(
                WallCalibration.objects.filter(wall=self.wall).latest
            )('created')
        except WallCalibration.DoesNotExist:
            logger.error("No calibration found")
            return False
            
        if not self.wall.svg_file or not os.path.exists(os.path.join(settings.MEDIA_ROOT, self.wall.svg_file.name)):
            logger.error("SVG file not found")
            return False
            
        svg_path = os.path.join(settings.MEDIA_ROOT, self.wall.svg_file.name)
        self.svg_parser = SVGParser(svg_file_path=svg_path)
        self.svg_parser.paths = self.svg_parser.extract_paths()
        self.svg_size = self.svg_parser.get_svg_dimensions()
        
        # Extract buttons from SVG
        self.buttons = self.svg_parser.extract_buttons()
        self.button_centers = {b['id']: (b['x'] + b['width']/2, b['y'] + b['height']/2) for b in self.buttons.values()}
        if self.buttons:
            logger.info(f"Loaded {len(self.buttons)} control buttons from SVG")
            self.state.control_buttons = list(self.buttons.keys())
            # Map buttonx classes to modes
            self.state.button_to_mode = {}
            class_to_mode = {
                'button0': 'draw',
                'button1': 'hard',
                'button2': 'medium',
                'button3': 'easy'
            }
            for btn_id, btn_data in self.buttons.items():
                for cls in btn_data['classes']:
                    if cls in class_to_mode:
                        self.state.button_to_mode[btn_id] = class_to_mode[cls]
                        break
        
        # Calculate hold centers for debug purposes
        self.hold_centers = get_hold_centers(self.svg_parser)
        
        # Pre-compute matplotlib Path objects and bounding boxes for fast intersection checks
        self.precomputed_paths = self.svg_parser.precompute_paths()
        
        self.calibration_utils = CalibrationUtils()
        self.transform_matrix = np.array(self.calibration.perspective_transform, dtype=np.float32)
        
        self.input_client = InputWebSocketClient(self.input_websocket_url, self.handle_pose_data)
        self.output_client = OutputWebSocketClient(self.output_websocket_url)
        
        if self.command_websocket_url:
            self.command_client = InputWebSocketClient(self.command_websocket_url, self.handle_command_data)
            logger.info(f"Command listener configured for: {self.command_websocket_url}")
            
        return True

    @database_sync_to_async
    def fetch_routes_by_difficulty(self, difficulty: str):
        routes = list(Route.objects.filter(difficulty=difficulty))
        return routes
        
    async def _handle_hand_touches(self, touched_holds: Set[str], timestamp: float):
        """Process hand touches for menu navigation"""
        self.hand_tracker.update_touches(touched_holds, timestamp)
        
        # Check newly completed touches (every 3s)
        ready = self.hand_tracker.get_ready_holds(timestamp)
        for hold_data in ready:
            hold_id = hold_data['hold_id']
            if hold_id in self.state.control_buttons:
                await self._on_control_button_pressed(hold_id, timestamp, step=hold_data['step'])

    async def _on_control_button_pressed(self, btn_id: str, timestamp: float, step: int = 1):
        """User pressed a control button with their hand. 
        step 1 = 2s (mode activation), step 2+ = 4s+ (cycling)"""
        mode = self.state.button_to_mode.get(btn_id)
        if not mode:
            logger.warning(f"Button {btn_id} pressed but not mapped to a mode")
            return

        if mode == 'draw':
            if self.state.mode == 'draw':
                # Toggle clear route if already in draw mode
                self.state.temporary_route_holds.clear()
                logger.info("Cleared temporary draw route.")
            else:
                self.state.mode = 'draw'
                self.state.temporary_route_holds.clear()
                logger.info("Entered DRAW mode (holds cleared).")
            await self.send_system_state()
            return
            
        # Modes: easy, medium, hard
        if self.state.mode != mode:
            if step >= 1:
                # Entered a new difficulty mode
                self.state.mode = mode
                logger.info(f"Entered {mode.upper()} mode at 2s.")
                
                # Fetch routes
                self.state.available_routes = await self.fetch_routes_by_difficulty(mode)
                self.state.current_route_index = 0
                self.state.last_route_switch_time = timestamp
        else:
            # Already in this mode, cycle to next route if step >= 2 (4s, 6s...)
            if step >= 2 and self.state.available_routes:
                self.state.current_route_index = (self.state.current_route_index + 1) % len(self.state.available_routes)
                logger.info(f"Cycled to next {mode.upper()} route at {step*2}s: {self.state.current_route_index}")
            
        await self.send_system_state()
            
    async def _handle_detection_touches(self, touched_holds: Set[str], timestamp: float):
        """Process ArUco or Light detection touches for route drawing"""
        if self.state.mode != 'draw':
            self.detection_tracker.clear_all()
            return
            
        # If light hits a control button, exit draw mode
        hit_buttons = {h for h in touched_holds if h in self.state.control_buttons}
        if hit_buttons:
            logger.info("Button hit by light detection, exiting draw mode.")
            self.state.mode = None
            self.state.temporary_route_holds.clear()
            await self.send_system_state()
            return

        # Filter out control buttons from being selectable
        selectable_holds = {h for h in touched_holds if h not in self.state.control_buttons}
        self.detection_tracker.update_touches(selectable_holds, timestamp)
        
        ready = self.detection_tracker.get_ready_holds(timestamp)
        state_changed = False
        
        for hold_data in ready:
            hold_id = hold_data['hold_id']
            if hold_id in self.state.temporary_route_holds:
                self.state.temporary_route_holds.remove(hold_id)
                logger.info(f"Removed '{hold_id}' from draw route.")
            else:
                self.state.temporary_route_holds.add(hold_id)
                logger.info(f"Added '{hold_id}' to draw route.")
            state_changed = True
            break # Single hold enforcement: only process the first hold detected in this window
            
        if state_changed:
            await self.send_system_state()
            
    async def _process_looping(self, timestamp: float):
        """Automatic route looping is disabled in favor of manual selection"""
        pass

    async def handle_pose_data(self, data):
        try:
            is_valid, _ = validate_pose_data(data)
            if not is_valid: return
            
            # Handle manual mode switch from phone
            if 'mode' in data and data.get('type') in ['change_mode', 'state']:
                new_mode = data['mode']
                if new_mode in self.state.MODES:
                    if self.state.mode != new_mode:
                        self.state.mode = new_mode
                        logger.info(f"Manual mode switch from phone: {new_mode}")
                        if new_mode == 'draw':
                            self.state.temporary_route_holds.clear()
                        elif new_mode in ['easy', 'medium', 'hard']:
                            self.state.available_routes = await self.fetch_routes_by_difficulty(new_mode)
                            self.state.current_route_index = 0
                        await self.send_system_state()
                return

            timestamp = data.get('timestamp', time.time())
            img_width = data.get('width', 100)
            img_height = data.get('height', 100)
            
            # 1. Process Hands
            landmarks = data.get('landmarks', [])
            left_hand, right_hand, _, _ = extract_hand_positions(landmarks)
            
            if left_hand: self.last_palm_l_img = (left_hand[0], left_hand[1])
            else: self.last_palm_l_img = None
            
            if right_hand: self.last_palm_r_img = (right_hand[0], right_hand[1])
            else: self.last_palm_r_img = None

            self.last_palm_l_svg = None
            self.last_palm_r_svg = None
            touched_holds_hand = set()
            
            for i, h in enumerate([left_hand, right_hand]):
                svg_pos = transform_to_svg_coordinates(h, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
                if i == 0: self.last_palm_l_svg = svg_pos
                else: self.last_palm_r_svg = svg_pos
                
                if svg_pos:
                    holds, buttons = check_hold_intersections(svg_pos, self.precomputed_paths, self.buttons)
                    touched_holds_hand.update(holds)
                    touched_holds_hand.update(buttons) # Include buttons in hand touches
            
            self.state.current_touched_holds = touched_holds_hand
            await self._handle_hand_touches(touched_holds_hand, timestamp)

            # 2. Process Full Calibrated Pose
            self.last_calibrated_landmarks = []
            if landmarks:
                for l in landmarks:
                    pos = (l['x'], l['y'])
                    svg_pos = transform_to_svg_coordinates(pos, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
                    if svg_pos:
                        self.last_calibrated_landmarks.append({
                            'x': svg_pos[0],
                            'y': svg_pos[1],
                            'visibility': l.get('visibility', 1.0)
                        })
                    else:
                        self.last_calibrated_landmarks.append(None)
            
            # 2. Process Detection Points (ArUco or Light) in draw mode
            touched_holds_detection = set()
            if self.state.mode == 'draw':
                detection_positions = extract_detection_positions(data)
                for pos in detection_positions:
                    svg_pos = transform_to_svg_coordinates(pos, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
                    if svg_pos:
                        holds, _ = check_hold_intersections(svg_pos, self.precomputed_paths, self.buttons)
                        touched_holds_detection.update(holds)
                    
            await self._handle_detection_touches(touched_holds_detection, timestamp)
            
            # 3. Process Loop Iteration
            await self._process_looping(timestamp)
            
            # 4. Debug output: Closest hold for each hand every 5s
            if self.debug_proximity and timestamp - self.last_debug_output_time >= 5.0:
                self.last_debug_output_time = timestamp
                
                debug_info = []
                btn0_center = self.button_centers.get('button-0')
                
                for hand_label, hand_pos in [("Left", left_hand), ("Right", right_hand)]:
                    if hand_pos is not None:
                        svg_pos = transform_to_svg_coordinates(hand_pos, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
                        if svg_pos:
                            hand_info = f"{hand_label}: "
                            
                            if self.hold_centers:
                                distances = [
                                    (h_id, np.sqrt((svg_pos[0]-cx)**2 + (svg_pos[1]-cy)**2))
                                    for h_id, (cx, cy) in self.hold_centers.items()
                                ]
                                if distances:
                                    closest_id, min_dist = min(distances, key=lambda x: x[1])
                                    h_id = f"hold_{closest_id}" if not str(closest_id).startswith(('hold_', 'btn_')) else closest_id
                                    hand_info += f"closest {h_id} ({min_dist:.1f})"
                            
                            if btn0_center:
                                btn_dist = np.sqrt((svg_pos[0]-btn0_center[0])**2 + (svg_pos[1]-btn0_center[1])**2)
                                hand_info += f" | btn0 dist: {btn_dist:.1f}"
                                
                            debug_info.append(hand_info)
                
                if debug_info:
                    logger.debug(f"DEBUG | {' | '.join(debug_info)}")
            
            # 5. Send state on every pose frame (throttled to pose_send_interval)
            now = time.time()
            if now - self.last_pose_send_time >= self.pose_send_interval:
                self.last_pose_send_time = now
                await self.send_system_state()
            
        except Exception as e:
            logger.error(f"Error handling data: {e}")

    async def handle_command_data(self, data):
        """
        Handle simulation commands from the /ws/command/ listener.
        Expected command structure:
        {
            "type": "simulate_button",
            "index": 0, // 0: draw, 1: hard, 2: medium, 3: easy
            "mode": "hard", // Optional, alternative to index
            "step": 1   // 1: activate (2s hold), 2: loop/cycle (4s hold)
        }
        """
        try:
            if not isinstance(data, dict):
                return
            
            if data.get('type') == 'simulate_button':
                btn_id = None
                step = data.get('step', 1)
                timestamp = time.time()
                
                # Option 1: Simulate by index (0-3)
                if 'index' in data:
                    index = data['index']
                    if 0 <= index < len(self.state.control_buttons):
                        btn_id = self.state.control_buttons[index]
                        logger.info(f"Simulating button press by index {index}: {btn_id}")
                
                # Option 2: Simulate by mode name
                elif 'mode' in data:
                    target_mode = data['mode']
                    for bid, mode in self.state.button_to_mode.items():
                        if mode == target_mode:
                            btn_id = bid
                            logger.info(f"Simulating button press by mode: {target_mode} -> {btn_id}")
                            break
                
                if btn_id:
                    await self._on_control_button_pressed(btn_id, timestamp, step=step)
                else:
                    logger.warning(f"Simulate command received but no button matched: {data}")
                    
        except Exception as e:
            logger.error(f"Error handling command data: {e}")

    async def send_system_state(self):
        """Gather state and send to frontend"""
        self.last_state_send_time = time.time()
        active_holds = []
        custom_text = ""
        text = ""
        route_name = ""
        route_data = None
        
        if self.state.mode == 'draw':
            active_holds = [h if str(h).startswith(('hold_', 'btn_')) else f"hold_{h}" for h in self.state.temporary_route_holds]
            custom_text = f"DRAW MODE: {len(active_holds)} Holds"
            text = "Create your route"
            
        elif self.state.mode in ['easy', 'medium', 'hard']:
            if self.state.available_routes:
                route = self.state.available_routes[self.state.current_route_index]
                route_name = route.name
                text = route_name
                route_data = route.data
                
                # Robust extraction of holds from route.data
                def extract_from_list(h_list):
                    res = []
                    for h in h_list:
                        h_id = str(h['id']) if isinstance(h, dict) and 'id' in h else str(h)
                        if not h_id.startswith(('hold_', 'btn_')):
                            h_id = f"hold_{h_id}"
                        res.append(h_id)
                    return res

                if isinstance(route.data, list):
                    active_holds = extract_from_list(route.data)
                elif isinstance(route.data, dict):
                    if 'holds' in route.data and isinstance(route.data['holds'], list):
                        active_holds = extract_from_list(route.data['holds'])
                    elif 'ids' in route.data and isinstance(route.data['ids'], list):
                        active_holds = extract_from_list(route.data['ids'])
                    elif 'problem' in route.data and isinstance(route.data['problem'], dict):
                        prob = route.data['problem']
                        if 'holds' in prob and isinstance(prob['holds'], list):
                            active_holds = extract_from_list(prob['holds'])
                    
                custom_text = f"{self.state.mode.capitalize()} ({self.state.current_route_index+1}/{len(self.state.available_routes)}): {route_name}"
            else:
                custom_text = f"{self.state.mode.capitalize()} Mode: No routes found"

        # Construct generic message that frontend can use to illuminate holds
        message = {
            'type': 'interactive_state',
            'wall_id': self.wall_id,
            'mode': self.state.mode,
            'active_holds': active_holds, # Legacy field for compatibility
            'route_holds': active_holds if self.state.mode in ['easy', 'medium', 'hard', 'draw'] else [],
            'route_data': route_data,
            'touched_holds': [h if str(h).startswith(('hold_', 'btn_')) else f"hold_{h}" for h in self.state.current_touched_holds],
            'palms': {
                'left_img': {'x': self.last_palm_l_img[0], 'y': self.last_palm_l_img[1]} if self.last_palm_l_img else None,
                'right_img': {'x': self.last_palm_r_img[0], 'y': self.last_palm_r_img[1]} if self.last_palm_r_img else None,
                'left_svg': {'x': self.last_palm_l_svg[0], 'y': self.last_palm_l_svg[1]} if self.last_palm_l_svg else None,
                'right_svg': {'x': self.last_palm_r_svg[0], 'y': self.last_palm_r_svg[1]} if self.last_palm_r_svg else None
            },
            'calibrated_landmarks': self.last_calibrated_landmarks,
            'route_name': route_name,
            'text': text,
            'custom_text': custom_text,
            'svg_width': self.svg_size[0],
            'svg_height': self.svg_size[1],
            'timestamp': time.time()
        }
        
        await self.output_client.send_message(message)
        logger.debug(f"Sent state update: {custom_text}")

    async def _periodic_state_sender(self):
        """Background task to ensure state is sent even when no pose frames arrive"""
        while self.running:
            now = time.time()
            if now - self.last_state_send_time >= 2.0:
                await self.send_system_state()
            await asyncio.sleep(1.0)

    async def run(self):
        if not await self.setup():
            return
        self.running = True
        logger.info("Started Interactive Wall System")
        
        tasks = [
            self.input_client.start(),
            self.output_client.start(),
            self._periodic_state_sender()
        ]
        
        if self.command_client:
            tasks.append(self.command_client.start())
            
        try:
            await asyncio.gather(*tasks)
        finally:
            self.running = False
            self.input_client.stop()
            self.output_client.stop()
            if self.command_client:
                self.command_client.stop()


class Command(BaseCommand):
    help = 'Interactive Climbing Wall System (Draw/Easy/Medium/Hard mode manager)'
    
    def add_arguments(self, parser):
        parser.add_argument('--wall-id', type=int, required=True, help='ID of wall')
        parser.add_argument('--input-websocket-url', type=str, required=True, help='ws://... for MediaPipe/ArUco')
        parser.add_argument('--output-websocket-url', type=str, required=True, help='ws://... for frontend display')
        parser.add_argument('--command-websocket-url', type=str, help='ws://... for simulation commands')
        parser.add_argument('--loop-time', type=float, default=5.0, help='Seconds interval for difficulty route looping')
        parser.add_argument('--debug', action='store_true', help='Debug log')
        parser.add_argument('--debug-proximity', action='store_true', help='Debug output for closest hold and button distance')
        
    def handle(self, *args, **options):
        logger.remove()
        logger.add("logs/interactive_wall_system.log", rotation="1 day", level="DEBUG" if options['debug'] else "INFO")
        logger.add(lambda msg: self.stdout.write(msg), level="DEBUG" if options['debug'] else "INFO")
        
        system = InteractiveWallCommandSystem(
            wall_id=options['wall_id'],
            input_websocket_url=options['input_websocket_url'],
            output_websocket_url=options['output_websocket_url'],
            command_websocket_url=options.get('command_websocket_url'),
            loop_time=options['loop_time'],
            debug=options['debug'],
            debug_proximity=options['debug_proximity']
        )
        asyncio.run(system.run())
