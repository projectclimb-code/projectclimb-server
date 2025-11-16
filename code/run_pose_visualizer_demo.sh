#!/bin/bash

# Demo script for running pose visualizer with mock server
# This script starts the mock WebSocket server and then launches the visualizer

set -e

# Default values
PORT=8765
FRAME_RATE=10
SVG_FILE="data/wall.svg"
WINDOW_WIDTH=1200
WINDOW_HEIGHT=800

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --frame-rate)
            FRAME_RATE="$2"
            shift 2
            ;;
        --svg-file)
            SVG_FILE="$2"
            shift 2
            ;;
        --window-width)
            WINDOW_WIDTH="$2"
            shift 2
            ;;
        --window-height)
            WINDOW_HEIGHT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT           WebSocket port (default: 8765)"
            echo "  --frame-rate RATE      Mock server frame rate (default: 10)"
            echo "  --svg-file FILE       SVG file path (default: code/data/wall_bbox.svg)"
            echo "  --window-width WIDTH    Window width (default: 1200)"
            echo "  --window-height HEIGHT  Window height (default: 800)"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if required files exist
if [ ! -f "test_pose_visualizer.py" ]; then
    echo "Error: test_pose_visualizer.py not found"
    exit 1
fi

if [ ! -f "pose_visualizer.py" ]; then
    echo "Error: pose_visualizer.py not found"
    exit 1
fi

if [ ! -f "$SVG_FILE" ]; then
    echo "Error: SVG file not found: $SVG_FILE"
    exit 1
fi

echo "Starting Pose Visualizer Demo"
echo "==========================="
echo "WebSocket port: $PORT"
echo "Frame rate: $FRAME_RATE"
echo "SVG file: $SVG_FILE"
echo "Window size: ${WINDOW_WIDTH}x${WINDOW_HEIGHT}"
echo ""

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "Stopping background processes..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null || true
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start mock server in background
echo "Starting mock WebSocket server..."
uv run python test_pose_visualizer.py --port $PORT --frame-rate $FRAME_RATE &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

# Check if server started successfully
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "Error: Failed to start mock server"
    exit 1
fi

echo "Mock server started (PID: $SERVER_PID)"
echo ""
echo "Starting pose visualizer..."
echo "Connect to: ws://localhost:$PORT"
echo ""
echo "Press Ctrl+C to stop both server and visualizer"
echo ""

# Start visualizer (this will block until user exits)
uv run python pose_visualizer.py \
    --websocket-url ws://localhost:$PORT \
    --wall-svg "$SVG_FILE" \
    --window-width $WINDOW_WIDTH \
    --window-height $WINDOW_HEIGHT

# Cleanup when visualizer exits
cleanup