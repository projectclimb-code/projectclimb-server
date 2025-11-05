# WebSocket Pose Transformer

A standalone Python script that connects to two WebSocket channels, receives messages from the first channel, applies a custom transformation function, and sends the result to the second channel.

## Overview

The `websocket_pose_transformer.py` script provides a flexible way to transform data between WebSocket channels. It's designed to work with pose data (like MediaPipe landmarks) but can handle any JSON-formatted data.

## Features

- **Bidirectional WebSocket connections**: Connects to an input channel (receives data) and an output channel (sends transformed data)
- **Custom transformation functions**: Apply your own transformation logic to the data
- **Automatic reconnection**: Handles connection failures with exponential backoff
- **Built-in dummy transformation**: Includes a default transformation function for testing
- **Example transformation**: Includes an example transformation function that demonstrates coordinate offset
- **Performance monitoring**: Tracks message processing rate and statistics
- **Debug logging**: Configurable logging levels for troubleshooting

## Installation

Install the required dependencies:

```bash
pip install websockets
```

## Usage

### Basic Usage

```bash
python websocket_pose_transformer.py \
    --input-url ws://localhost:8765 \
    --output-url ws://localhost:8766
```

### With Debug Logging

```bash
python websocket_pose_transformer.py \
    --input-url ws://localhost:8765 \
    --output-url ws://localhost:8766 \
    --debug
```

### Using the Example Transformation Function

```bash
python websocket_pose_transformer.py \
    --input-url ws://localhost:8765 \
    --output-url ws://localhost:8766 \
    --use-example-transform
```

### Custom Reconnection Delay

```bash
python websocket_pose_transformer.py \
    --input-url ws://localhost:8765 \
    --output-url ws://localhost:8766 \
    --reconnect-delay 10.0
```

## Command Line Options

- `--input-url`: WebSocket URL for receiving messages (required)
- `--output-url`: WebSocket URL for sending transformed messages (required)
- `--reconnect-delay`: Delay between reconnection attempts in seconds (default: 5.0)
- `--debug`: Enable debug logging
- `--use-example-transform`: Use the example transformation function instead of the dummy one

## Transformation Functions

### Default Dummy Transformation

The default dummy transformation:
- Adds a `dummy_transformed` flag
- Adds a `dummy_timestamp`
- For pose landmarks, adds `dummy_scaled_x` and `dummy_scaled_y` fields

### Example Transformation

The example transformation (`--use-example-transform`):
- Adds a `custom_transformed` flag
- Adds a `transform_name` field
- For pose landmarks, adds `transformed_x`, `transformed_y`, and `transformed_z` fields with a 0.1 offset

### Creating Custom Transformation Functions

You can create your own transformation function by modifying the script. The function should:

1. Accept a dictionary as input
2. Return a dictionary as output
3. Be an async function (or use `await` if needed)

Example:

```python
async def my_custom_transform(data: Dict[str, Any]) -> Dict[str, Any]:
    """My custom transformation function"""
    result = data.copy()
    
    # Add custom logic here
    if 'landmarks' in data:
        for landmark in data['landmarks']:
            # Apply your transformation
            landmark['my_field'] = landmark.get('x', 0) * 2.0
    
    return result
```

Then use it when creating the transformer:

```python
transformer = WebSocketPoseTransformer(
    input_url="ws://localhost:8765",
    output_url="ws://localhost:8766",
    transform_func=my_custom_transform
)
```

## Data Format

The script works with any JSON-formatted data, but it's optimized for pose data with the following structure:

```json
{
    "type": "pose_data",
    "timestamp": 1234567890.123,
    "landmarks": [
        {
            "x": 0.5,
            "y": 0.3,
            "z": 0.0,
            "visibility": 0.8
        },
        ...
    ]
}
```

## Testing

A test script is provided to demonstrate and test the transformer:

```bash
# Run simple connection test
python test_websocket_pose_transformer.py --simple

# Run full test with dummy transform
python test_websocket_pose_transformer.py

# Run full test with example transform
python test_websocket_pose_transformer.py --example-transform
```

The test script:
1. Creates mock WebSocket servers
2. Starts the transformer process
3. Sends sample pose data
4. Receives and displays the transformed data
5. Shows transformation statistics

## Integration with Existing Project

This standalone script is designed to complement the existing Django-based WebSocket pose transformer in the project:

- **Django version**: `code/climber/management/commands/websocket_pose_transformer.py`
  - Integrates with Django models
  - Uses wall calibration data
  - More complex coordinate transformations

- **Standalone version**: `websocket_pose_transformer.py`
  - No Django dependencies
  - Simpler transformation functions
  - Easier to test and customize

## Logging

The script uses Python's logging module with configurable levels:

- **INFO**: General operation information
- **DEBUG**: Detailed message information (enabled with `--debug`)
- **ERROR**: Error conditions

## Performance

The transformer includes performance monitoring:
- Tracks total messages processed
- Calculates processing rate (messages/second)
- Logs progress every 100 messages

## Error Handling

The script handles various error conditions:
- Connection failures with automatic reconnection
- Invalid JSON messages
- Transformation function errors
- WebSocket send failures

## Example Use Cases

1. **Pose Data Transformation**: Transform MediaPipe pose coordinates to wall coordinates
2. **Data Filtering**: Filter out low-visibility landmarks
3. **Data Enrichment**: Add additional metadata to pose data
4. **Protocol Translation**: Convert between different data formats
5. **Real-time Processing**: Apply real-time transformations to streaming data

## Troubleshooting

### Connection Issues

If the transformer can't connect to the WebSocket URLs:
1. Verify the WebSocket servers are running
2. Check the URLs are correct (include `ws://` or `wss://` prefix)
3. Ensure no firewall is blocking the connections

### Transformation Errors

If transformations are failing:
1. Enable debug logging with `--debug`
2. Check the input data format matches expectations
3. Verify your transformation function handles all edge cases

### Performance Issues

If the transformer is slow:
1. Check the transformation function is efficient
2. Monitor the message rate in the logs
3. Consider optimizing the transformation logic