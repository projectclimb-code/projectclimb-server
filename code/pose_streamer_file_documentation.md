# Pose Streamer File Input Documentation

The `pose_streamer.py` script has been extended to support input from video files with optional looping functionality.

## New Command Line Options

### `--file <path>`
Specifies a video file to use as input instead of a camera. This overrides the `--source` option.

Example:
```bash
python pose_streamer.py --file data/bolder2.mov
```

### `--loop`
When using file input, this option causes the video to loop indefinitely when it reaches the end. Without this option, the streamer will exit after playing the file once.

Example:
```bash
python pose_streamer.py --file data/bolder2.mov --loop
```

## Usage Examples

### 1. Stream from a video file once
```bash
cd code
uv run python pose_streamer.py --file data/bolder2.mov
```

### 2. Stream from a video file in a loop
```bash
cd code
uv run python pose_streamer.py --file data/bolder2.mov --loop
```

### 3. Using the test script
A test script is provided to simplify running the streamer with file input:

```bash
# Run once
cd code
uv run python test_pose_streamer_file.py data/bolder2.mov

# Run in a loop
cd code
uv run python test_pose_streamer_file.py data/bolder2.mov --loop
```

## Implementation Details

1. **File Detection**: The script now determines whether the input is a file or camera based on the presence of the `--file` parameter.

2. **Looping Logic**: When `--loop` is specified and the end of the video file is reached, the video position is reset to the beginning using `cv2.CAP_PROP_POS_FRAMES`.

3. **Exit Behavior**: 
   - With `--loop`: The video continues streaming indefinitely
   - Without `--loop`: The streamer exits after playing the file once
   - For camera input: The behavior remains unchanged

4. **Error Handling**: The script provides appropriate messages when:
   - The video file cannot be opened
   - The end of the file is reached
   - The video is being restarted for looping

## Notes

- The script supports any video format that OpenCV can read (MP4, MOV, AVI, etc.)
- When using file input, the frame count will reset to 0 each time the video loops
- The WebSocket connection will remain active throughout the looping process
- All other functionality (pose detection, recording controls, etc.) works the same with file input as with camera input