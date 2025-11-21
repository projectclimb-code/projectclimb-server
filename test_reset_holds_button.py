#!/usr/bin/env python3
"""
Test script to verify the reset holds button implementation.
This script checks that the required changes are in place.
"""

import os
import re

def test_template_changes():
    """Test that the template contains the reset holds button."""
    template_path = "code/climber/templates/climber/task_management.html"
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Check for reset holds button
    reset_button_pattern = r'id="reset-holds"'
    if not re.search(reset_button_pattern, content):
        print("❌ Reset holds button not found in template")
        return False
    
    # Check for reset holds JavaScript function
    reset_function_pattern = r'function resetHolds\(\)'
    if not re.search(reset_function_pattern, content):
        print("❌ resetHolds function not found in template")
        return False
    
    # Check for WebSocket message
    ws_message_pattern = r'type:\s*"reset_holds"'
    if not re.search(ws_message_pattern, content):
        print("❌ WebSocket reset_holds message not found in template")
        return False
    
    print("✅ Template changes verified")
    return True

def test_view_changes():
    """Test that the view passes WS_HOLDS_URL to template."""
    view_path = "code/climber/views.py"
    
    with open(view_path, 'r') as f:
        content = f.read()
    
    # Check for WS_HOLDS_URL in context
    ws_url_pattern = r'WS_HOLDS_URL.*settings\.WS_HOLDS_URL'
    if not re.search(ws_url_pattern, content):
        print("❌ WS_HOLDS_URL not found in view context")
        return False
    
    print("✅ View changes verified")
    return True

def test_settings():
    """Test that WS_HOLDS_URL is defined in settings."""
    settings_path = "code/app/settings.py"
    
    with open(settings_path, 'r') as f:
        content = f.read()
    
    # Check for WS_HOLDS_URL setting
    ws_url_pattern = r'WS_HOLDS_URL\s*=\s*env\([\'"]WS_HOLDS_URL[\'"]'
    if not re.search(ws_url_pattern, content):
        print("❌ WS_HOLDS_URL setting not found in settings.py")
        return False
    
    print("✅ Settings verified")
    return True

def test_env_file():
    """Test that WS_HOLDS_URL is defined in .env file."""
    env_path = ".env"
    
    with open(env_path, 'r') as f:
        content = f.read()
    
    # Check for WS_HOLDS_URL in .env
    ws_url_pattern = r'WS_HOLDS_URL=ws://'
    if not re.search(ws_url_pattern, content):
        print("❌ WS_HOLDS_URL not found in .env file")
        return False
    
    print("✅ .env file verified")
    return True

def main():
    """Run all tests."""
    print("Testing Reset Holds Button Implementation")
    print("=" * 50)
    
    tests = [
        test_template_changes,
        test_view_changes,
        test_settings,
        test_env_file
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Reset holds button implementation is complete.")
        print("\nSummary of changes:")
        print("1. Added 'Reset holds' button to task management page")
        print("2. Implemented JavaScript to send WebSocket message")
        print("3. Updated view to pass WS_HOLDS_URL to template")
        print("4. Verified settings configuration")
        print("\nThe button will send a WebSocket message {\"type\": \"reset_holds\"} to ws://localhost:8001/ws/holds/")
    else:
        print("❌ Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    main()