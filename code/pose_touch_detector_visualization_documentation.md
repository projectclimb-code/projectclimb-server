# Pose Touch Detector Visualization Features

This document explains the new visualization features added to the `pose_touch_detector` management command.

## Overview

The pose touch detector now supports real-time visualization of:
1. The video feed from camera or video file
2. The detected skeleton overlay on the video
3. SVG holds overlay on the video

These features help with debugging and understanding the pose detection and touch detection process.

## New Command-Line Options

### --show-video
Display the video feed in an OpenCV window.

```bash
uv run python manage.py pose_touch_detector --wall-id 1 --show-video
```

### --show-skeleton
Display the detected skeleton overlay on the video feed. This option requires `--show-video` to be enabled.

```bash
uv run python manage.py pose_touch_detector --wall-id 1 --show-video --show-skeleton
```

The skeleton visualization includes:
- Full body pose landmarks connected with lines
- Left hand landmarks marked in red
- Right hand landmarks marked in blue
- Green circles around hands when touching holds

### --show-svg
Display the SVG holds overlay on the video feed. This option requires `--show-video` to be enabled.

```bash
uv run python manage.py pose_touch_detector --wall-id 1 --show-video --show-svg
```

The SVG overlay shows:
- All holds from the wall's SVG file
- Holds are displayed as green shapes with darker green outlines
- Semi-transparent overlay (30% opacity) to see the video underneath

## Usage Examples

### Basic Video Display
```bash
uv run python manage.py pose_touch_detector --wall-id 1 --show-video
```

### Full Visualization (Video + Skeleton + SVG)
```bash
uv run python manage.py pose_touch_detector --wall-id 1 --show-video --show-skeleton --show-svg
```

### Using a Video File with Visualization
```bash
uv run python manage.py pose_touch_detector --wall-id 1 --video-file data/bolder2.mov --show-video --show-skeleton --show-svg --loop
```

### With WebSocket Streaming
```bash
uv run python manage.py pose_touch_detector --wall-id 1 --session-id 1 --show-video --show-skeleton --show-svg
```

## Testing the Visualization

A test script is provided to easily test the visualization features:

```bash
./code/test_pose_touch_detector_visualization.py
```

This script will:
1. Find the first calibrated wall in the database
2. Look for a video file in the data directory
3. Run the pose touch detector with all visualization options enabled

## Controls

When the video window is displayed:
- Press **'q'** to quit the detector
- Press **Ctrl+C** in the terminal to stop the detector

## Implementation Details

### SVG Overlay Creation
The SVG overlay is created during initialization when `--show-svg` is enabled:
1. The SVG file is parsed to extract all path elements
2. Each path is converted to a polygon
3. The polygons are drawn on a transparent overlay image
4. The overlay is blended with the video frame during processing

### Skeleton Visualization
The skeleton is drawn using MediaPipe's drawing utilities:
1. Landmarks are connected according to pose connections
2. Hand landmarks are highlighted with different colors
3. Touch indicators are drawn when hands touch holds

### Performance Considerations
- Visualization adds some overhead to the processing
- For production use without visualization, omit the `--show-*` options
- The detector runs at approximately 30 FPS with visualization enabled

## Troubleshooting

### No Video Window Appears
- Ensure OpenCV with GUI support is installed
- On Linux, you may need to install `python3-opencv-gui` or similar
- On macOS, ensure you're not running in a headless environment

### SVG Overlay Not Visible
- Check that the wall has an SVG file associated with it
- Verify the SVG file contains valid path elements
- The overlay is semi-transparent, so holds might be hard to see on light backgrounds

### Skeleton Not Detected
- Ensure the person is clearly visible in the video
- Good lighting conditions improve detection accuracy
- The person should be facing the camera for best results

## Dependencies

The visualization features require:
- OpenCV (`cv2`)
- MediaPipe (`mediapipe`)
- NumPy (`numpy`)

These should already be installed as part of the project dependencies.