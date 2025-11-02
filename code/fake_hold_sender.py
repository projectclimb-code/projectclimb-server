import asyncio
import json
import random
import datetime
import websockets

# --- CONFIG ---
WS_URL = "wss://climber.dev.maptnh.net/ws/holds/"  # replace with your target WebSocket server
#HOLD_IDS = [6, 17, 41, 55, 72, 89, 91, 101, 133, 11]
HOLD_IDS = range(1,140)
STATUSES = ["untouched", "touched", "completed"]

async def generate_fake_data():
    """Create fake JSON payload matching expected SVG format."""
    holds = []
    for hold_id in HOLD_IDS:
        status = random.choices(STATUSES, weights=[12, 2, 2])[0]
        time = None
        if status != "untouched":
            time = datetime.datetime.utcnow().isoformat() + "Z"

        holds.append({
            "id": str(hold_id),
            "type": random.choice(["start", "normal", "finish"]),
            "status": status,
            "time": time
        })

    return {
        "session": {
            "holds": holds,
            "startTime": "2025-10-19T17:44:37.187Z",
            "endTime": None,
            "status": "started"
        },
        "pose": []
    }

async def send_fake_updates():
    """Continuously connect and send fake JSON messages."""
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                print(f"Connected to {WS_URL}")
                while True:
                    data = await generate_fake_data()
                    await ws.send(json.dumps(data))
                    print(f"Sent {len(data['session']['holds'])} holds")
                    await asyncio.sleep(3)
        except (ConnectionRefusedError, websockets.InvalidURI, websockets.ConnectionClosedError) as e:
            print(f"Connection failed: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

async def main():
    await send_fake_updates()

if __name__ == "__main__":
    asyncio.run(main())
