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


class TouchTracker:
    """Track touch durations with tolerance for dropped frames"""
    
    def __init__(self, touch_duration=1.0, lost_tolerance=0.5):
        self.touch_duration = touch_duration
        self.lost_tolerance = lost_tolerance
        
        self.touch_start_times = {}  # hold_id -> timestamp
        self.touch_last_seen = {}    # hold_id -> timestamp
        self.sent_events = set()     # Set of hold_ids for which events were sent
        
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
            self.sent_events.remove(hold_id)
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
            if touch_duration >= self.touch_duration:
                # Only report as ready once per touch sequence
                if hold_id not in self.sent_events:
                    ready_holds.append({
                        'hold_id': hold_id,
                        'touch_duration': touch_duration
                    })
                    self.sent_events.add(hold_id)
                    logger.debug(f"Hold {hold_id} ready after {touch_duration:.2f}s")
        
        return ready_holds


class InteractiveState:
    """Manages the interactive wall state machine"""
    
    MODES = [None, 'draw', 'easy', 'medium', 'hard']
    DEFAULT_CONTROL_BUTTONS = ['btn_draw', 'btn_easy', 'btn_medium', 'btn_hard']
    
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
                self.sender_task = asyncio.create_task(self.message_sender())
                await self.keep_alive()
            except Exception as e:
                logger.error(f"Output WebSocket error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
    
    async def _wait_and_reconnect(self):
        await asyncio.sleep(self.current_reconnect_delay)
        self.current_reconnect_delay = min(self.current_reconnect_delay * 2, 60.0)
    
    async def keep_alive(self):
        while self.running and self.websocket:
            await asyncio.sleep(30)
            if self.websocket:
                await self.websocket.ping()
    
    async def message_sender(self):
        while self.running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                if self.websocket:
                    await self.websocket.send(json.dumps(message))
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                await self.message_queue.put(message)
    
    async def send_message(self, message):
        await self.message_queue.put(message)
    
    def start(self):
        self.running = True
        return asyncio.create_task(self.connect())
    
    def stop(self):
        self.running = False
        if self.sender_task:
            self.sender_task.cancel()
        if self.websocket:
            asyncio.create_task(self.websocket.close())


def validate_pose_data(data):
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"
    if 'landmarks' not in data and 'aruco_markers' not in data:
        return False, "Missing 'landmarks' or 'aruco_markers' array"
    return True, "Valid"


def calculate_extended_hand_landmarks(landmarks, extension_percent=20.0):
    """Calculate extended hand landmarks beyond the palm (ported from session tracker)"""
    # Left hand: 15 (wrist), 17 (pinky), 19 (index), 21 (thumb), 13 (elbow)
    # Right hand: 16 (wrist), 18 (pinky), 20 (index), 22 (thumb), 14 (elbow)
    new_positions = []
    
    for side in ['left', 'right']:
        wrist_idx = 15 if side == 'left' else 16
        pinky_idx = 17 if side == 'left' else 18
        index_idx = 19 if side == 'left' else 20
        thumb_idx = 21 if side == 'left' else 22
        elbow_idx = 13 if side == 'left' else 14
        
        if (len(landmarks) > max(wrist_idx, pinky_idx, index_idx, thumb_idx, elbow_idx)):
            wrist = landmarks[wrist_idx]
            pinky = landmarks[pinky_idx]
            index = landmarks[index_idx]
            thumb = landmarks[thumb_idx]
            elbow = landmarks[elbow_idx]
            
            # Palm center
            palm_x = (wrist['x'] + pinky['x'] + index['x'] + thumb['x']) / 4
            palm_y = (wrist['y'] + pinky['y'] + index['y'] + thumb['y']) / 4
            
            # Direction elbow -> palm
            dir_x = palm_x - elbow['x']
            dir_y = palm_y - elbow['y']
            mag = np.sqrt(dir_x**2 + dir_y**2)
            if mag > 0:
                dir_x /= mag
                dir_y /= mag
                
            # Palm size
            palm_size = np.sqrt((pinky['x'] - index['x'])**2 + (pinky['y'] - index['y'])**2)
            ext_dist = palm_size * (extension_percent / 100.0)
            
            extended_palm = (palm_x + dir_x * ext_dist, palm_y + dir_y * ext_dist)
            elbow_pos = (elbow['x'], elbow['y'])
            new_positions.append((extended_palm, elbow_pos))
        else:
            new_positions.append((None, None))
            
    return new_positions


def extract_hand_positions(landmarks):
    # Use extended landmarks if available, otherwise fallback to mean of wrist/index
    hand_data = calculate_extended_hand_landmarks(landmarks)
    ext_left, elbow_left = hand_data[0]
    ext_right, elbow_right = hand_data[1]
    
    # Fallback logic if extension fails but basic landmarks exist
    if not ext_left and len(landmarks) > 19:
        left_wrist = landmarks[15]
        left_index = landmarks[19]
        if left_wrist['visibility'] > 0.5 and left_index['visibility'] > 0.5:
            ext_left = ( (left_wrist['x'] + left_index['x'])/2, (left_wrist['y'] + left_index['y'])/2 )
            
    if not ext_right and len(landmarks) > 20:
        right_wrist = landmarks[16]
        right_index = landmarks[20]
        if right_wrist['visibility'] > 0.5 and right_index['visibility'] > 0.5:
            ext_right = ( (right_wrist['x'] + right_index['x'])/2, (right_wrist['y'] + right_index['y'])/2 )
            
    # Also extract elbows directly if not already found
    if not elbow_left and len(landmarks) > 13:
        elbow_left = (landmarks[13]['x'], landmarks[13]['y'])
    if not elbow_right and len(landmarks) > 14:
        elbow_right = (landmarks[14]['x'], landmarks[14]['y'])
            
    return ext_left, ext_right, elbow_left, elbow_right


def extract_aruco_positions(data):
    aruco_positions = []
    markers = data.get('aruco_markers', [])
    for marker in markers:
        try:
            if 'x' in marker and 'y' in marker:
                aruco_positions.append((marker['x'], marker['y']))
            elif 'center' in marker:
                aruco_positions.append((marker['center']['x'], marker['center']['y']))
        except Exception:
            pass
    return aruco_positions


def transform_to_svg_coordinates(position, calibration_utils, transform_matrix, svg_size, img_width, img_height, calibration_type='aruco'):
    if position is None:
        return None
        
    if calibration_type == 'manual_points':
        # Manual calibration uses normalized [0, 1] coordinates for both image and SVG in this system
        transformed_norm = calibration_utils.transform_point_to_svg(position, transform_matrix)
        
        if transformed_norm:
            res = (transformed_norm[0] * svg_size[0], transformed_norm[1] * svg_size[1])
            logger.info(f"Transform (manual): norm {position} -> norm_svg {transformed_norm} -> svg {res}")
            return res
        return None
    else:
        abs_x = position[0] * img_width
        abs_y = position[1] * img_height
        
        transformed_pos = calibration_utils.transform_point_to_svg((abs_x, abs_y), transform_matrix)
        logger.info(f"Transform (aruco): norm {position} -> abs {abs_x, abs_y} -> svg {transformed_pos}")
        
        return transformed_pos


def check_hold_intersections(svg_parser, position, buttons=None):
    if position is None:
        return set(), set()
    touched_holds = set()
    touched_buttons = set()
    
    # Check holds (paths)
    for path_id, path_data in svg_parser.paths.items():
        try:
            if svg_parser.point_in_path((position[0], position[1]), path_data['d']):
                touched_holds.add(path_id)
        except Exception:
            pass
            
    # Check buttons (rects)
    if buttons:
        for btn_id, btn_data in buttons.items():
            # Simple point-in-rect check
            if (btn_data['x'] <= position[0] <= btn_data['x'] + btn_data['width'] and
                btn_data['y'] <= position[1] <= btn_data['y'] + btn_data['height']):
                touched_buttons.add(btn_id)
                
    return touched_holds, touched_buttons


class InteractiveWallCommandSystem:
    def __init__(self, wall_id, input_websocket_url, output_websocket_url, loop_time, debug=False, debug_proximity=False):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.loop_time = loop_time
        self.debug = debug
        self.debug_proximity = debug_proximity
        
        self.hold_centers = {}
        self.last_debug_output_time = 0.0
        
        self.wall = None
        self.calibration = None
        self.svg_parser = None
        self.svg_size = (0, 0)
        self.calibration_utils = None
        self.transform_matrix = None
        
        self.input_client = None
        self.output_client = None
        
        self.buttons = {} # btn_id -> btn_data from SVG
        
        # We track hands fast (0.5s) to trigger buttons, ArUco slow (2.0s) to lock in holds
        self.hand_tracker = TouchTracker(touch_duration=0.5, lost_tolerance=0.5)
        self.aruco_tracker = TouchTracker(touch_duration=2.0, lost_tolerance=0.5)
        
        self.last_elbow_l = None
        self.last_elbow_r = None
        
        self.state = InteractiveState(loop_time=loop_time)
        self.running = False
        
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
                'button1': 'easy',
                'button2': 'medium',
                'button3': 'hard'
            }
            for btn_id, btn_data in self.buttons.items():
                for cls in btn_data['classes']:
                    if cls in class_to_mode:
                        self.state.button_to_mode[btn_id] = class_to_mode[cls]
                        break
        
        # Calculate hold centers for debug purposes
        self.hold_centers = get_hold_centers(self.svg_parser)
        
        self.calibration_utils = CalibrationUtils()
        self.transform_matrix = np.array(self.calibration.perspective_transform, dtype=np.float32)
        
        self.input_client = InputWebSocketClient(self.input_websocket_url, self.handle_pose_data)
        self.output_client = OutputWebSocketClient(self.output_websocket_url)
        return True

    @database_sync_to_async
    def fetch_routes_by_difficulty(self, difficulty: str):
        routes = list(Route.objects.filter(difficulty=difficulty))
        return routes
        
    async def _handle_hand_touches(self, touched_holds: Set[str], timestamp: float):
        """Process hand touches for menu navigation"""
        self.hand_tracker.update_touches(touched_holds, timestamp)
        
        # Check newly completed touches
        ready = self.hand_tracker.get_ready_holds(timestamp)
        for hold_data in ready:
            hold_id = hold_data['hold_id']
            if hold_id in self.state.control_buttons:
                await self._on_control_button_pressed(hold_id, timestamp)
        
        # If in a continuous hold mode (easy, medium, hard), we exit mode immediately 
        # when the button is released.
        if self.state.mode in ['easy', 'medium', 'hard']:
            # Find the button ID for the current mode
            btn_id = None
            for b_id, mode in self.state.button_to_mode.items():
                if mode == self.state.mode:
                    btn_id = b_id
                    break
                    
            # If tracking says we've completely lost the touch
            if btn_id and btn_id not in self.hand_tracker.touch_start_times:
                logger.info(f"Hand removed from {btn_id}. Exiting {self.state.mode} mode.")
                self.state.mode = None
                await self.send_system_state()

    async def _on_control_button_pressed(self, btn_id: str, timestamp: float):
        """User pressed a control button with their hand"""
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
                logger.info("Entered DRAW mode.")
            await self.send_system_state()
            return
            
        # Modes: easy, medium, hard
        if self.state.mode != mode:
            # Entered a new difficulty mode
            self.state.mode = mode
            logger.info(f"Entered {mode.upper()} mode.")
            
            # Fetch routes
            self.state.available_routes = await self.fetch_routes_by_difficulty(mode)
            self.state.current_route_index = 0
            self.state.last_route_switch_time = timestamp
            
            await self.send_system_state()
            
    async def _handle_aruco_touches(self, touched_holds: Set[str], timestamp: float):
        """Process ArUco marker touches for route drawing"""
        if self.state.mode != 'draw':
            self.aruco_tracker.clear_all()
            return
            
        # Filter out control buttons from being selectable
        selectable_holds = {h for h in touched_holds if h not in self.state.control_buttons}
        self.aruco_tracker.update_touches(selectable_holds, timestamp)
        
        ready = self.aruco_tracker.get_ready_holds(timestamp)
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
            
        if state_changed:
            await self.send_system_state()
            
    async def _process_looping(self, timestamp: float):
        """Process switching routes periodically for difficulty modes"""
        if self.state.mode not in ['easy', 'medium', 'hard']:
            return
            
        if not self.state.available_routes:
            return
            
        if timestamp - self.state.last_route_switch_time >= self.state.loop_time:
            self.state.current_route_index = (self.state.current_route_index + 1) % len(self.state.available_routes)
            self.state.last_route_switch_time = timestamp
            logger.debug(f"Looped to route index {self.state.current_route_index}")
            await self.send_system_state()

    async def handle_pose_data(self, data):
        try:
            is_valid, _ = validate_pose_data(data)
            if not is_valid: return
            
            timestamp = data.get('timestamp', time.time())
            img_width = data.get('width', 100)
            img_height = data.get('height', 100)
            
            # 1. Process Hands
            left_hand, right_hand, elbow_l, elbow_r = extract_hand_positions(data.get('landmarks', []))
            
            # Transform and store elbow data for export
            self.last_elbow_l = transform_to_svg_coordinates(elbow_l, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
            self.last_elbow_r = transform_to_svg_coordinates(elbow_r, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)

            touched_holds_hand = set()
            for h in [left_hand, right_hand]:
                svg_pos = transform_to_svg_coordinates(h, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
                if svg_pos:
                    holds, buttons = check_hold_intersections(self.svg_parser, svg_pos, self.buttons)
                    touched_holds_hand.update(holds)
                    touched_holds_hand.update(buttons) # Include buttons in hand touches
                    
            await self._handle_hand_touches(touched_holds_hand, timestamp)
            
            # 2. Process ArUco
            aruco_positions = extract_aruco_positions(data)
            touched_holds_aruco = set()
            for pos in aruco_positions:
                svg_pos = transform_to_svg_coordinates(pos, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
                if svg_pos:
                    holds, _ = check_hold_intersections(self.svg_parser, svg_pos, self.buttons)
                    touched_holds_aruco.update(holds)
                    
            await self._handle_aruco_touches(touched_holds_aruco, timestamp)
            
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
                                    hand_info += f"closest {closest_id} ({min_dist:.1f})"
                            
                            if btn0_center:
                                btn_dist = np.sqrt((svg_pos[0]-btn0_center[0])**2 + (svg_pos[1]-btn0_center[1])**2)
                                hand_info += f" | btn0 dist: {btn_dist:.1f}"
                                
                            debug_info.append(hand_info)
                
                if debug_info:
                    logger.debug(f"DEBUG | {' | '.join(debug_info)}")
            
        except Exception as e:
            logger.error(f"Error handling data: {e}")

    async def send_system_state(self):
        """Gather state and send to frontend"""
        active_holds = []
        custom_text = ""
        route_name = ""
        
        if self.state.mode == 'draw':
            active_holds = list(self.state.temporary_route_holds)
            custom_text = f"DRAW MODE: {len(active_holds)} Holds"
            
        elif self.state.mode in ['easy', 'medium', 'hard']:
            if self.state.available_routes:
                route = self.state.available_routes[self.state.current_route_index]
                route_name = route.name
                
                # Assume route.data has a 'holds' property that is a list of strings
                if isinstance(route.data, dict) and 'holds' in route.data:
                    active_holds = [str(h) for h in route.data['holds']]
                    
                custom_text = f"{self.state.mode.capitalize()} ({self.state.current_route_index+1}/{len(self.state.available_routes)}): {route_name}"
            else:
                custom_text = f"{self.state.mode.capitalize()} Mode: No routes found"

        # Construct generic message that frontend can use to illuminate holds
        message = {
            'type': 'interactive_state',
            'wall_id': self.wall_id,
            'mode': self.state.mode,
            'active_holds': active_holds,
            'elbows': {
                'left': {'x': self.last_elbow_l[0], 'y': self.last_elbow_l[1]} if self.last_elbow_l else None,
                'right': {'x': self.last_elbow_r[0], 'y': self.last_elbow_r[1]} if self.last_elbow_r else None
            },
            'route_name': route_name,
            'custom_text': custom_text,
            'svg_width': self.svg_size[0],
            'svg_height': self.svg_size[1],
            'timestamp': time.time()
        }
        
        await self.output_client.send_message(message)
        logger.debug(f"Sent state update: {custom_text}")

    async def run(self):
        if not await self.setup():
            return
        self.running = True
        logger.info("Started Interactive Wall System")
        try:
            await asyncio.gather(
                self.input_client.start(),
                self.output_client.start()
            )
        finally:
            self.running = False
            self.input_client.stop()
            self.output_client.stop()


class Command(BaseCommand):
    help = 'Interactive Climbing Wall System (Draw/Easy/Medium/Hard mode manager)'
    
    def add_arguments(self, parser):
        parser.add_argument('--wall-id', type=int, required=True, help='ID of wall')
        parser.add_argument('--input-websocket-url', type=str, required=True, help='ws://... for MediaPipe/ArUco')
        parser.add_argument('--output-websocket-url', type=str, required=True, help='ws://... for frontend display')
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
            loop_time=options['loop_time'],
            debug=options['debug'],
            debug_proximity=options['debug_proximity']
        )
        asyncio.run(system.run())
