# go2rtc Integration for ProjectClimb

This document describes how to set up and use the go2rtc integration for video streaming in the ProjectClimb application.

## Overview

go2rtc is a powerful camera streaming application that allows you to capture video from various sources and make it available to multiple consumers via different protocols (RTSP, WebRTC, HLS, etc.). This integration allows the ProjectClimb application to use go2rtc as a central video streaming server.

## Architecture

```
Camera → go2rtc → Multiple Consumers (Web, Mobile, etc.)
         ↓
   ProjectClimb App
```

## Setup Instructions

### 1. Start go2rtc Service

Using Docker Compose:
```bash
docker-compose up go2rtc
```

This will start go2rtc with the following ports:
- 1984: HTTP API and web interface
- 8554: RTSP server
- 5000-5001: UDP ports for RTP/RTCP

### 2. Configure and Start Video Stream

Run the setup script:
```bash
cd code
uv run python start_go2rtc_stream.py
```

Or with custom camera source:
```bash
uv run python start_go2rtc_stream.py --camera 1
```

### 3. Access the Stream

Open the camera page in your browser:
```
http://localhost:8012/camera/
```

## Configuration

### go2rtc Configuration

The go2rtc configuration is stored in `go2rtc.yml`:

```yaml
# Log settings
log:
  level: info
  out: stdout

# API settings
api:
  listen: ":1984"

# RTSP server settings
rtsp:
  listen: ":8554"

# WebRTC settings
webrtc:
  ice_servers:
    - urls: [stun:stun.l.google.com:19302]

# Streams configuration (added dynamically)
streams: {}
```

### Camera Stream Configuration

The camera stream is configured via the go2rtc API:
- Stream name: `camera`
- Source: `ffmpeg:{camera_id}?input_format=mjpeg&video_size=1280x720&framerate=30`
- Output URL: `http://localhost:1984/stream.mp4?src=camera`

## API Endpoints

### go2rtc API

- GET `http://localhost:1984/api/info` - Server information
- POST `http://localhost:1984/api/streams` - Add/update a stream
- GET `http://localhost:1984/api/streams` - List all streams
- GET `http://localhost:1984/stream.mp4?src={stream_name}` - Stream as MP4
- GET `http://localhost:1984/stream.mjpeg?src={stream_name}` - Stream as MJPEG

### ProjectClimb Endpoints

- GET `/camera/` - Camera view page
- WebSocket `/ws/pose/` - Pose data streaming

## Usage

### Adding Multiple Cameras

You can add multiple cameras by configuring different stream names:

```bash
uv run python start_go2rtc_stream.py --stream-name "camera1" --camera 0
uv run python start_go2rtc_stream.py --stream-name "camera2" --camera 1
```

Access them via:
```
http://localhost:1984/stream.mp4?src=camera1
http://localhost:1984/stream.mp4?src=camera2
```

### Using External Streams

You can also configure go2rtc to use external streams (IP cameras, etc.):

```bash
curl -X POST http://localhost:1984/api/streams \
  -H "Content-Type: application/json" \
  -d '{"name": "external_cam", "src": "rtsp://camera-ip:554/stream"}'
```

### WebRTC Support

go2rtc supports WebRTC for low-latency streaming. You can access the WebRTC interface at:
```
http://localhost:1984/
```

## Troubleshooting

### Common Issues

1. **go2rtc not accessible**
   - Check if the container is running: `docker ps`
   - Check logs: `docker logs climber_go2rtc`

2. **Camera not working**
   - Verify camera is available to the system
   - Try different camera indices (0, 1, 2, etc.)

3. **Stream not loading in browser**
   - Check browser console for errors
   - Verify the stream URL is correct

4. **Permission issues**
   - On macOS, you may need to grant browser camera permissions
   - On Linux, ensure the user has access to video devices

### Debugging

Check go2rtc logs:
```bash
docker logs climber_go2rtc
```

Check stream configuration:
```bash
curl http://localhost:1984/api/streams
```

Test stream directly:
```bash
curl http://localhost:1984/stream.mp4?src=camera -o test.mp4
```

## Integration with Pose Detection

The `video_go2rtc.py` script integrates with the existing pose detection system:

1. Captures video from the camera
2. Configures go2rtc to make the stream available
3. Sends pose data to the Django WebSocket
4. Allows multiple consumers to access the video stream

This enables multiple users to view the same camera stream while receiving pose data in real-time.