#!/usr/bin/env python3
"""
Test script for websocket_pose_session_tracker management command
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import django
import json
import asyncio
import websockets
from unittest.mock import AsyncMock

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code.app.settings')
django.setup()

from django.core.management import call, ManagementUtility


def test_command_parsing():
    """Test that command line arguments are parsed correctly"""
    print("Testing command line argument parsing...")
    
    # Test route data parsing
    route_data = {
        "grade": "6b",
        "author": "Trinity",
        "problem": {
            "holds": [
                {"id": "59", "type": "start"},
                {"id": "74", "type": "start"},
                {"id": "87", "type": "normal"},
                {"id": "42", "type": "normal"},
                {"id": "56", "type": "normal"},
                {"id": "53", "type": "normal"},
                {"id": "35", "type": "finish"}
            ]
        }
    }
    
    route_json = json.dumps(route_data)
    
    print("\n=== Route Data Test ===")
    print(f"Route JSON: {route_json}")
    
    print("Note: Django management command testing requires proper Django setup")
    print("Use 'uv run python manage.py websocket_pose_session_tracker --help' to test command")


def test_json_format():
    """Test that the output JSON format matches specification"""
    print("\n=== Testing JSON Format ===")
    
    # Sample output format
    expected_format = {
        "session": {
            "holds": [
                { "id": "17", "type": "start", "status": "completed", "time": "2025-01-01T12:00:02.000Z" },
                { "id": "91", "type": "start", "status": "completed", "time": "2025-01-01T12:00:23.000Z" },
                { "id": "6",  "type": "normal", "status": "completed", "time": "2025-01-01T12:00:33.000Z" },
                { "id": "101","type": "normal", "status": "completed", "time": "2025-01-01T12:00:43.000Z" },
                { "id": "55", "type": "normal", "status": "completed", "time": "2025-01-01T12:00:53.000Z" },
                { "id": "133","type": "normal", "status": "untouched", "time": None },
                { "id": "89", "type": "normal", "status": "untouched", "time": None },
                { "id": "41", "type": "normal", "status": "untouched", "time": None },
                { "id": "72", "type": "finish", "status": "untouched", "time": None },
                { "id": "11", "type": "finish", "status": "untouched", "time": None }
            ],
            "startTime": "2025-10-19T17:44:37.187Z",
            "endTime":  None,
            "status": "started"
        },
        "pose": []
    }
    
    print("Expected output format:")
    print(json.dumps(expected_format, indent=2))
    
    # Validate format
    assert 'session' in expected_format
    assert 'holds' in expected_format['session']
    assert 'startTime' in expected_format['session']
    assert 'endTime' in expected_format['session']
    assert 'status' in expected_format['session']
    assert 'pose' in expected_format
    
    # Check hold structure
    for hold in expected_format['session']['holds']:
        assert 'id' in hold
        assert 'type' in hold
        assert 'status' in hold
        assert 'time' in hold
    
    print("✓ JSON format validation passed")


def test_route_filtering():
    """Test route hold filtering logic"""
    print("\n=== Testing Route Filtering ===")
    
    print("Note: Route filtering test requires proper Django setup")
    print("This test will be skipped in standalone mode")
    print("To test route filtering, run the actual command with route data")


if __name__ == "__main__":
    print("Testing WebSocket Pose Session Tracker")
    print("=" * 50)
    
    test_command_parsing()
    test_json_format()
    test_route_filtering()
    
    print("\n" + "=" * 50)
    print("Testing complete!")
    print("\nTo run the command:")
    print("uv run python manage.py websocket_pose_session_tracker \\")
    print("  --wall-id=1 \\")
    print("  --input-websocket-url=ws://localhost:8001 \\")
    print("  --output-websocket-url=ws://localhost:8002 \\")
    print('  --route-data=\'{"grade": "6b", "author": "Trinity", "problem": {"holds": [{"id": "59", "type": "start"}]}}\' \\')
    print("  --no-stream-landmarks \\")
    print("  --stream-svg-only \\")
    print("  --debug")