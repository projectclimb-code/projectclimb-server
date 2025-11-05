#!/bin/bash

# Pose Detector to WebSocket Runner Script
# This script runs the pose detector with default settings

# Default WebSocket URL
WEBSOCKET_URL="wss://climber.dev.maptnh.net:443/ws/pose/"

# Default video source (0 = default camera)
VIDEO_SOURCE="0"

# Default frame rate
FPS="30"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --websocket-url)
            WEBSOCKET_URL="$2"
            shift 2
            ;;
        --video-source)
            VIDEO_SOURCE="$2"
            shift 2
            ;;
        --fps)
            FPS="$2"
            shift 2
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        --loop)
            LOOP="--loop"
            shift
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --websocket-url URL    WebSocket URL to stream to (default: $WEBSOCKET_URL)"
            echo "  --video-source SOURCE  Video source (camera index or file path, default: $VIDEO_SOURCE)"
            echo "  --fps FPS              Target frame rate (default: $FPS)"
            echo "  --debug                Enable debug logging"
            echo "  --loop                 Loop video files indefinitely"
            echo "  --dry-run              Run without WebSocket connection (just log pose data)"
            echo "  -h, --help             Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run with defaults"
            echo "  $0 --video-source 1                  # Use camera index 1"
            echo "  $0 --video-source video.mp4 --loop   # Loop video file"
            echo "  $0 --debug                           # Enable debug logging"
            echo "  $0 --dry-run --video-source video.mp4 # Test pose detection without WebSocket"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "Starting Pose Detector to WebSocket..."
echo "WebSocket URL: $WEBSOCKET_URL"
echo "Video Source: $VIDEO_SOURCE"
echo "Frame Rate: $FPS"
if [ -n "$DEBUG" ]; then
    echo "Debug Mode: Enabled"
fi
if [ -n "$LOOP" ]; then
    echo "Loop Mode: Enabled"
fi
if [ -n "$DRY_RUN" ]; then
    echo "Dry Run Mode: Enabled (pose data will be logged but not sent to WebSocket)"
fi
echo ""

# Run the pose detector
uv run python code/pose_detector_to_websocket.py \
    --websocket-url "$WEBSOCKET_URL" \
    --video-source "$VIDEO_SOURCE" \
    --fps "$FPS" \
    $DEBUG $LOOP $DRY_RUN