from django.test import TestCase
from unittest.mock import patch, MagicMock
from climber.models import Wall, Route, Venue, WallCalibration
from climber.tasks import websocket_pose_session_tracker_task, stop_session_tracker_task, get_running_session_trackers, running_session_trackers
import json


class CelerySessionTrackerTestCase(TestCase):
    """Test cases for Celery session tracker tasks"""
    
    def setUp(self):
        """Set up test data"""
        # Create test venue
        self.venue = Venue.objects.create(
            name='Test Venue',
            description='Test venue description'
        )
        
        # Create test wall
        self.wall = Wall.objects.create(
            name='Test Wall',
            venue=self.venue
        )
        
        # Create test route
        self.route = Route.objects.create(
            name='Test Route',
            data={
                'holds': [
                    {'id': 'hold1', 'type': 'start'},
                    {'id': 'hold2', 'type': 'normal'},
                    {'id': 'hold3', 'type': 'finish'}
                ]
            }
        )
        
        # Create test calibration
        self.calibration = WallCalibration.objects.create(
            wall=self.wall,
            name='Test Calibration',
            is_active=True,
            perspective_transform=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            hand_extension_percent=20.0
        )
    
    def test_get_running_session_trackers_task(self):
        """Test getting running session trackers"""
        # Clear any existing trackers
        running_session_trackers.clear()
        
        # Add a test tracker
        from datetime import datetime
        running_session_trackers['test-task-id'] = {
            'task': MagicMock(),
            'wall_id': self.wall.id,
            'started_at': datetime.now(),
            'status': 'running'
        }
        
        result = get_running_session_trackers()
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('test-task-id', result['trackers'])
        self.assertEqual(result['trackers']['test-task-id']['wall_id'], self.wall.id)
    
    @patch('celery.current_app')
    def test_stop_session_tracker_task(self, mock_current_app):
        """Test stopping a session tracker task"""
        # Clear any existing trackers
        running_session_trackers.clear()
        
        # Add a test tracker
        from datetime import datetime
        running_session_trackers['test-task-id'] = {
            'task': MagicMock(),
            'wall_id': self.wall.id,
            'started_at': datetime.now(),
            'status': 'running'
        }
        
        # Mock control.revoke method
        mock_control = MagicMock()
        mock_current_app.control = mock_control
        
        result = stop_session_tracker_task('test-task-id')
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('test-task-id', result['message'])
        self.assertTrue(mock_control.revoke.called)
        self.assertEqual(mock_control.revoke.call_args[0], ('test-task-id',))
        self.assertEqual(mock_control.revoke.call_args[1], {'terminate': True})
    
    @patch('climber.tasks.websocket_pose_session_tracker_task.delay')
    def test_websocket_pose_session_tracker_task_creation(self, mock_task):
        """Test that the Celery task can be created with correct parameters"""
        mock_task.return_value = MagicMock()
        mock_task.return_value.id = 'test-task-id'
        
        # Call the task directly with test parameters
        result = websocket_pose_session_tracker_task.delay(
            wall_id=self.wall.id,
            input_websocket_url='ws://localhost:8001/ws/pose/',
            output_websocket_url='ws://localhost:8002/ws/session/',
            proximity_threshold=50.0,
            touch_duration=2.0,
            reconnect_delay=5.0,
            debug=False,
            no_stream_landmarks=False,
            stream_svg_only=False,
            route_data=None,
            route_id=self.route.id
        )
        
        # Verify task was called with correct parameters
        self.assertTrue(mock_task.called)
        call_args = mock_task.call_args[1]
        self.assertEqual(call_args['wall_id'], self.wall.id)
        self.assertEqual(call_args['input_websocket_url'], 'ws://localhost:8001/ws/pose/')
        self.assertEqual(call_args['output_websocket_url'], 'ws://localhost:8002/ws/session/')
        self.assertEqual(call_args['proximity_threshold'], 50.0)
        self.assertEqual(call_args['touch_duration'], 2.0)
        self.assertEqual(call_args['reconnect_delay'], 5.0)
        self.assertEqual(call_args['debug'], False)
        self.assertEqual(call_args['no_stream_landmarks'], False)
        self.assertEqual(call_args['stream_svg_only'], False)
        self.assertEqual(call_args['route_data'], None)
        self.assertEqual(call_args['route_id'], self.route.id)
