# go2rtc Camera Setup Guide

This guide explains how to use the updated go2rtc configuration to access USB cameras or MacBook's built-in camera.

## What's Changed

1. **docker-compose.yml**: Now uses the official `alex-a/go2rtc` container instead of `bluenviron/mediamtx`
2. **go2rtc.yml**: Pre-configured with camera stream settings
3. **Device Mapping**: Added device mapping for `/dev/video0` to access the camera from the container

## Quick Start

1. **Start the go2rtc service:**
   ```bash
   docker-compose up go2rtc
   ```

2. **Test the configuration:**
   ```bash
   python test_go2rtc_camera.py
   ```

3. **Access the camera stream:**
   - Web UI: http://localhost:1984/
   - Stream: http://localhost:1984/stream.mp4?src=camera
   - RTSP: rtsp://localhost:8554/camera

## Detailed Instructions

### Prerequisites

- Docker and Docker Compose installed
- A camera connected to your system (USB camera or built-in camera)
- On Linux/macOS: Camera should be available at `/dev/video0`

### Starting the Service

```bash
# Start only go2rtc
docker-compose up go2rtc

# Or start it with other services
docker-compose up
```

### Verifying the Setup

Run the test script to verify everything is working:

```bash
python test_go2rtc_camera.py
```

This will check:
- go2rtc is running and accessible
- Camera stream is configured
- Stream can be accessed
- Web UI is available

### Accessing the Camera

1. **Web Interface**: Open http://localhost:1984/ in your browser
   - View stream status
   - Access stream information
   - Test different stream formats

2. **Direct Stream Access**:
   - MP4 stream: http://localhost:1984/stream.mp4?src=camera
   - MJPEG stream: http://localhost:1984/stream.mjpeg?src=camera
   - RTSP stream: rtsp://localhost:8554/camera

### Using with the Application

The camera stream can now be used with your Django application:

1. The `video_go2rtc.py` script is already configured to work with the new setup
2. Start the streamer with:
   ```bash
   python code/start_go2rtc_stream.py
   ```

## Troubleshooting

### Camera Not Found

1. **Check if camera is available:**
   - On Linux: `ls -la /dev/video*`
   - On macOS: `system_profiler SPCameraDataType`

2. **Check docker logs:**
   ```bash
   docker-compose logs go2rtc
   ```

3. **Verify device permissions:**
   - On Linux: Make sure your user has access to `/dev/video0`
   - You may need to add your user to the `video` group: `sudo usermod -a -G video $USER`

### Stream Not Working

1. **Check if go2rtc is running:**
   ```bash
   curl http://localhost:1984/api/info
   ```

2. **Check stream configuration:**
   ```bash
   curl http://localhost:1984/api/streams
   ```

3. **Try different camera configurations:**
   - Edit `go2rtc.yml` and uncomment alternative configurations
   - Restart go2rtc: `docker-compose restart go2rtc`

### Alternative Camera Configurations

If the default configuration doesn't work, try these alternatives in `go2rtc.yml`:

#### For macOS:
```yaml
streams:
  mac_camera:
    - avfoundation:0
    - ffmpeg:video="FaceTime HD Camera"
```

#### For Linux USB cameras:
```yaml
streams:
  usb_camera:
    - v4l2:/dev/video0
    - ffmpeg:/dev/video0
```

#### For specific camera formats:
```yaml
streams:
  camera:
    - ffmpeg:video=/dev/video0?input_format=yuyv&video_size=640x480&framerate=30
```

## Advanced Configuration

### Multiple Cameras

You can configure multiple cameras by adding more stream entries:

```yaml
streams:
  camera1:
    - ffmpeg:video=/dev/video0
  camera2:
    - ffmpeg:video=/dev/video1
```

### Custom Stream Settings

Adjust video parameters in the stream configuration:

```yaml
streams:
  camera:
    - ffmpeg:video=/dev/video0?input_format=mjpeg&video_size=1920x1080&framerate=30
```

Parameters:
- `input_format`: mjpeg, yuyv, etc.
- `video_size`: 640x480, 1280x720, 1920x1080, etc.
- `framerate`: 15, 30, 60, etc.

## Security Notes

- The go2rtc web UI is accessible from your local network
- Consider adding authentication if running in production
- Camera streams are not encrypted by default

## Next Steps

1. Test the camera stream with your application
2. Adjust video quality settings as needed
3. Set up proper authentication for production use
4. Consider adding SSL/TLS for secure streaming