# WebSocket Reset Holds Functionality

## Overview

The WebSocket pose session tracker now supports resetting all holds to an untouched state via a special WebSocket message. This feature allows external systems to clear the current climbing session state and start fresh.

## How to Use

### Sending a Reset Message

To reset all holds to untouched state, send a JSON message to the input WebSocket with the following format:

```json
{
    "type": "reset_holds"
}
```

### Message Flow

1. Client sends reset message to input WebSocket
2. Tracker receives and processes the reset message
3. All hold states are cleared and set to 'untouched'
4. Tracker sends updated session data with a 'reset: true' flag
5. Client receives confirmation that reset was successful

## Implementation Details

### WebSocket Message Handler

The `handle_pose_data` method in `WebSocketPoseSessionTracker` class now checks for control messages before processing pose data:

```python
# Check if this is a control message to reset all holds
if isinstance(pose_data, dict) and pose_data.get('type') == 'reset_holds':
    logger.info("Received reset_holds message, marking all holds as untouched")
    self.reset_all_holds()
    # Send updated session data after reset
    await self.send_session_data_after_reset()
    return
```

### Reset Functionality

The reset functionality is implemented in two places:

1. **SVGHoldDetector.reset_all_holds()**: Clears all hold tracking data
2. **WebSocketPoseSessionTracker.reset_all_holds()**: Calls the detector's reset method

### Response Message

After a reset, the tracker sends a session data message with an additional field:

```json
{
    "session": {
        "holds": [...],
        "startTime": "...",
        "endTime": null,
        "status": "started"
    },
    "reset": true
}
```

The `reset: true` flag indicates this message was sent in response to a reset operation.

## Testing

A test script is provided at `code/test_reset_holds_functionality.py` to demonstrate the reset functionality.

### Running the Test

1. Start the WebSocket pose session tracker:
```bash
uv run python manage.py websocket_pose_session_tracker \
  --wall-id 1 \
  --input-websocket-url ws://localhost:8001 \
  --output-websocket-url ws://localhost:8002 \
  --debug
```

2. Run the test script:
```bash
uv run python test_reset_holds_functionality.py
```

The test will:
- Connect to both input and output WebSockets
- Send a reset message
- Display the response showing all holds as untouched
- Send fake pose data to verify normal operation
- Send another reset message

## Use Cases

This functionality is useful for:

1. **Session Management**: Starting a new climbing session without restarting the tracker
2. **Testing**: Resetting hold states during development and testing
3. **User Interface**: Providing a "reset" button in climbing applications
4. **Automation**: Programmatically resetting sessions between climbs

## Error Handling

- Invalid JSON messages are logged and ignored
- Messages without the correct `type: "reset_holds"` format are treated as normal pose data
- Reset operations are logged for debugging and monitoring

## Compatibility

This feature is backward compatible. Existing pose data processing continues to work as before, with the reset functionality as an additional feature.