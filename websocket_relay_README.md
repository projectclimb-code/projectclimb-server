# WebSocket Relay Implementation

This document describes the WebSocket relay functionality that has been implemented in the ProjectClimb server.

## Overview

The WebSocket relay provides a simple broadcast mechanism where any message sent by any connected client is relayed to all other connected clients. This creates a simple chat/broadcast system that can be used for real-time communication between multiple clients.

## Implementation Details

### Files Modified/Created

1. **`code/climber/consumers.py`** - Added `RelayConsumer` class
2. **`code/climber/routing.py`** - Added WebSocket URL pattern for the relay
3. **`code/climber/views.py`** - Added `WebSocketRelayTestView` class
4. **`code/climber/urls.py`** - Added URL pattern for the test page
5. **`code/climber/templates/climber/websocket_relay_test.html`** - Test page for the relay
6. **`code/test_websocket_relay.py`** - Python test client script
7. **`code/app/settings.py`** - Added '127.0.0.1' to ALLOWED_HOSTS

### WebSocket Endpoint

The WebSocket relay is available at: `ws://localhost:8000/ws/relay/`

### Test Page

A web-based test interface is available at: `http://localhost:8000/websocket-relay-test/`

## Usage

### Web Interface

1. Navigate to `http://localhost:8000/websocket-relay-test/`
2. Open the page in multiple browser tabs or windows
3. Type a message in one tab and click "Send"
4. The message will appear in all connected tabs

### Python Client

You can test the relay functionality using the provided Python test client:

```bash
# Run a test client with a specific ID
cd code && uv run python test_websocket_relay.py client1

# Run an interactive client
cd code && uv run python test_websocket_relay.py interactive
```

### JavaScript Client

To connect to the relay from JavaScript:

```javascript
const socket = new WebSocket('ws://localhost:8000/ws/relay/');

socket.onopen = function(e) {
    console.log('Connected to WebSocket relay');
};

socket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    console.log('Received:', data);
};

// Send a message
socket.send(JSON.stringify({
    type: 'message',
    text: 'Hello from client',
    timestamp: new Date().toISOString()
}));
```

## Message Format

The relay doesn't enforce any specific message format - it simply relays whatever is sent. However, it's recommended to use JSON with a `type` field for message identification:

```json
{
    "type": "message",
    "text": "Hello world",
    "timestamp": "2025-10-30T19:00:00.000Z"
}
```

## Technical Details

### RelayConsumer

The `RelayConsumer` class in `consumers.py` handles the WebSocket connections:

- **connect()**: Adds the client to the 'relay_broadcast' group
- **disconnect()**: Removes the client from the group
- **receive()**: Broadcasts received messages to all clients in the group
- **relay_message()**: Handles incoming messages from the group and sends them to the WebSocket

### Channel Layers

The implementation uses Django Channels with Redis as the channel layer backend for message broadcasting between multiple server processes.

## Testing

To verify the relay functionality:

1. Start the Django development server: `uv run python manage.py runserver 8000`
2. Open the test page in multiple browser tabs
3. Send messages from one tab and verify they appear in all tabs
4. Alternatively, run multiple Python test clients to verify programmatic functionality

## Potential Use Cases

This relay functionality can be used for:

- Real-time chat applications
- Live notifications
- Collaborative editing
- Real-time game state synchronization
- Live data streaming to multiple clients
- Debugging WebSocket connections

## Security Considerations

- The current implementation allows any message to be relayed without validation
- In production, you may want to add authentication and message validation
- Consider rate limiting to prevent abuse
- Add proper error handling for malformed messages

## Extending the Implementation

To extend the relay functionality:

1. Add message validation in the `receive()` method
2. Implement authentication/authorization
3. Add message filtering or routing based on content
4. Implement message persistence if needed
5. Add support for different message types with specific handling