#!/usr/bin/env python3
"""
Example usage of pose_visualizer.py with websocket_pose_session_tracker.py

This example shows how to set up the complete pipeline:
1. Start websocket_pose_session_tracker.py with Django
2. Connect pose_visualizer.py to the output WebSocket
"""

import asyncio
import subprocess
import time
import sys
import os

def print_banner():
    """Print usage banner"""
    print("=" * 60)
    print("POSE VISUALIZER INTEGRATION EXAMPLE")
    print("=" * 60)
    print()
    print("This example demonstrates how to use pose_visualizer.py")
    print("with the websocket_pose_session_tracker.py Django command.")
    print()
    print("Prerequisites:")
    print("- Django project configured and running")
    print("- Wall with calibration in database")
    print("- Input WebSocket streaming pose data")
    print()
    print("Example workflow:")
    print("1. Start pose detector or pose streamer")
    print("2. Start websocket_pose_session_tracker.py")
    print("3. Start pose_visualizer.py")
    print()
    print("=" * 60)

def example_commands():
    """Show example commands"""
    print("EXAMPLE COMMANDS")
    print("=" * 30)
    print()
    print("1. Start pose detector (example):")
    print("   uv run python pose_detector_to_websocket.py \\")
    print("     --websocket-url ws://localhost:9000 \\")
    print("     --camera-id 0")
    print()
    print("2. Start session tracker:")
    print("   uv run python manage.py websocket_pose_session_tracker \\")
    print("     --wall-id 1 \\")
    print("     --input-websocket-url ws://localhost:9000 \\")
    print("     --output-websocket-url ws://localhost:8000 \\")
    print("     --debug")
    print()
    print("3. Start visualizer:")
    print("   uv run python pose_visualizer.py \\")
    print("     --websocket-url ws://localhost:8000 \\")
    print("     --wall-svg path/to/your/wall.svg")
    print()
    print("Or use the demo script:")
    print("   ./run_pose_visualizer_demo.sh")
    print()

def quick_demo():
    """Run quick demo with mock server"""
    print("QUICK DEMO WITH MOCK SERVER")
    print("=" * 35)
    print()
    print("Starting demo with mock WebSocket server...")
    print("This simulates a climbing session without requiring")
    print("the full Django setup.")
    print()
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    demo_script = os.path.join(script_dir, "run_pose_visualizer_demo.sh")
    
    if os.path.exists(demo_script):
        print(f"Running: {demo_script}")
        print()
        try:
            # Run the demo script
            subprocess.run([demo_script], check=True)
        except KeyboardInterrupt:
            print("\nDemo interrupted by user")
        except subprocess.CalledProcessError as e:
            print(f"Error running demo: {e}")
        except FileNotFoundError:
            print("Error: Demo script not found")
    else:
        print("Error: Demo script not found")
        print("Make sure run_pose_visualizer_demo.sh is in the same directory")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        quick_demo()
    else:
        print_banner()
        example_commands()
        
        print("OPTIONS:")
        print("  --demo    Run quick demo with mock server")
        print()
        print("Press Ctrl+C to exit")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nGoodbye!")

if __name__ == "__main__":
    main()