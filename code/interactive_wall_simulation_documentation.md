# Interactive Wall Simulation Documentation

This document describes how to use the command simulation interface for the Interactive Wall System. This interface allows you to remotely trigger button presses and mode changes without needing a physical pose detection setup.

## Connection Details

The interactive wall system listens for commands on a dedicated WebSocket connection.
- **Default Path**: `/ws/command/`
- **Configuration**: Set via the `--command-websocket-url` CLI argument or the "Command Simulation (WebSocket)" field on the `/tasks/` page.

## Message Format

All commands must be sent as JSON objects. The system currently supports the `simulate_button` command type.

### Command Structure

```json
{
    "type": "simulate_button",
    "index": number,      // 0: Draw, 1: Hard, 2: Medium, 3: Easy
    "mode": "string",     // Optional: "draw", "hard", "medium", or "easy"
    "step": number        // 1: Activate/Toggle (2s), 2+: Cycle (4s+)
}
```

> [!NOTE]
> You can target a button using either `index` or `mode`. If both are provided, `index` takes priority.

## Example Messages

### 1. Toggle Draw Mode
To enter Draw mode or clear the current drawing:
```json
{
    "type": "simulate_button",
    "mode": "draw",
    "step": 1
}
```

### 2. Activate Easy Mode
To switch the wall to Easy difficulty:
```json
{
    "type": "simulate_button",
    "index": 3,
    "step": 1
}
```

### 3. Cycle to Next Hard Route
If already in Hard mode, use `step: 2` to cycle to the next available route:
```json
{
    "type": "simulate_button",
    "mode": "hard",
    "step": 2
}
```

## Step Definitions

The `step` parameter simulates how long a button is held:
- **Step 1 (2 Seconds)**: Primary action. Enters the mode. For "Draw" mode, it toggles clearing the route.
- **Step 2+ (4+ Seconds)**: Secondary action. Cycles through available routes in the current difficulty mode.

---

## Python Example (websockets)

```python
import asyncio
import json
import websockets

async def send_command():
    uri = "ws://localhost:8000/ws/command/"
    async with websockets.connect(uri) as websocket:
        command = {
            "type": "simulate_button",
            "mode": "medium",
            "step": 1
        }
        await websocket.send(json.dumps(command))
        print(f"Sent: {command}")

asyncio.run(send_command())
```
