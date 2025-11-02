# Pose Viewer Documentation

The `pose_viewer.py` script is a simple standalone application that opens a video file, detects human pose using MediaPipe, and displays the video with pose overlay.

## Features

- Opens and plays video files
- Real-time pose detection using MediaPipe
- Visual overlay of pose landmarks and connections
- Frame counter display
- Pause/resume functionality
- Optional video looping

## Usage

### Basic Usage (with default video file)
```bash
cd code
uv run python pose_viewer.py
```

### Specify a Video File
```bash
cd code
uv run python pose_viewer.py --file path/to/your/video.mp4
```

### Loop the Video Indefinitely
```bash
cd code
uv run python pose_viewer.py --file data/bolder2.mov --loop
```

## Command Line Options

- `--file <path>`: Path to the video file (default: data/bolder2.mov)
- `--loop`: Loop the video indefinitely when it reaches the end

## Controls

While the video is playing, you can use the following keyboard controls:

- **q**: Quit the application
- **Spacebar**: Pause/Resume the video

## Requirements

The script requires the following Python packages:
- OpenCV (`cv2`)
- MediaPipe

These are already included in the project's dependencies.

## How It Works

1. The script opens the specified video file using OpenCV
2. Each frame is converted from BGR to RGB color space (required by MediaPipe)
3. MediaPipe processes the frame to detect pose landmarks
4. The detected pose landmarks and connections are drawn on the frame
5. The frame with the pose overlay is displayed in a window
6. The script continues until the video ends or the user presses 'q'

## Notes

- The script displays video information (resolution, FPS) when starting
- A frame counter is shown in the top-left corner of the video
- The pose detection model is optimized for video input (not static images)
- If the video file cannot be found or opened, an error message will be displayed