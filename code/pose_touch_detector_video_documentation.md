# Pose Touch Detector Video Input Documentation

The `pose_touch_detector` management command has been extended to support video file input for pose detection, in addition to the existing camera and fake pose options.

## New Command Line Options

### `--video-file <path>`
Specifies a video file to use as input instead of a camera. This allows you to process pre-recorded videos for pose detection.

Example:
```bash
uv run python manage.py pose_touch_detector --wall-id 1 --video-file data/bolder2.mov
```

### `--loop`
When using video file input, this option causes the video to loop indefinitely when it reaches the end. Without this option, the detector will exit after processing the video once.

Example:
```bash
uv run python manage.py pose_touch_detector --wall-id 1 --video-file data/bolder2.mov --loop
```

## Usage Examples

### 1. Process a video file once
```bash
cd code
uv run python manage.py pose_touch_detector --wall-id 1 --video-file data/bolder2.mov --debug
```

### 2. Process a video file in a loop
```bash
cd code
uv run python manage.py pose_touch_detector --wall-id 1 --video-file data/bolder2.mov --loop --debug
```

### 3. Process a video file with WebSocket streaming
```bash
cd code
uv run python manage.py pose_touch_detector --wall-id 1 --session-id 123 --video-file data/bolder2.mov --loop --debug
```

## Input Priority

The command follows this priority for input sources:
1. `--fake-pose` - If specified, uses fake pose data
2. `--video-file` - If specified, uses the video file
3. `--camera-source` - Default, uses camera input

## Implementation Details

1. **Video File Handling**: The command uses OpenCV to read video files, supporting any format that OpenCV can handle (MP4, MOV, AVI, etc.)

2. **Looping Logic**: When `--loop` is specified and the end of the video file is reached, the video position is reset to the beginning using `cv2.CAP_PROP_POS_FRAMES`

3. **Exit Behavior**: 
   - With `--loop`: The video continues processing indefinitely
   - Without `--loop`: The detector exits after processing the file once

4. **Error Handling**: The command provides appropriate messages when:
   - The video file cannot be found
   - The video file cannot be opened
   - The end of the file is reached

## Notes

- The video file input works with all existing functionality (pose detection, touch detection, WebSocket streaming)
- The frame rate is determined by the video file's native frame rate
- All pose detection and touch detection parameters work the same with video input as with camera input
- The `--debug` flag is recommended when first using video input to see detailed processing information