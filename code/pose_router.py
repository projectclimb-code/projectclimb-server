import argparse
import asyncio
import json
from typing import Any, Optional

import websockets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect to a source WebSocket, monitor messages, and optionally forward\n"
        "selected/transformed messages to a target WebSocket."
    )
    parser.add_argument(
        "--ws_uri",
        default="ws://localhost:8000/ws/pose/",
        help="Source WebSocket URI to connect to.",
    )
    parser.add_argument(
        "--to_ws_uri",
        default=None,
        help="Optional target WebSocket URI to forward messages to.",
    )
    parser.add_argument(
        "--include_type",
        default=None,
        help="Comma-separated list of message types to include (matches top-level 'type').",
    )
    parser.add_argument(
        "--extract",
        default=None,
        help="Dotted path to extract from the JSON message before forwarding (e.g., 'data.items.0').",
    )
    parser.add_argument(
        "--wrap",
        default=None,
        help="If provided, wraps the (optionally extracted) payload as {WRAP: payload}.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print processed messages to stdout.",
    )
    return parser.parse_args()


def extract_by_path(payload: Any, dotted_path: str) -> Any:
    if dotted_path is None:
        return payload
    current: Any = payload
    for part in dotted_path.split("."):
        if isinstance(current, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def transform_message(
    raw_message: str,
    include_types: Optional[set],
    extract_path: Optional[str],
    wrap_key: Optional[str],
) -> Optional[str]:
    try:
        parsed = json.loads(raw_message)
    except json.JSONDecodeError:
        # Not JSON; forward as-is only if no include_types/extract/wrap requested
        if include_types or extract_path or wrap_key:
            return None
        return raw_message

    # Filtering by type (only if provided and message is a dict with 'type')
    if include_types is not None:
        if not isinstance(parsed, dict):
            return None
        msg_type = parsed.get("type")
        if msg_type not in include_types:
            return None

    # Extraction
    processed: Any = parsed
    if extract_path:
        processed = extract_by_path(processed, extract_path)

    # Wrapping
    if wrap_key:
        processed = {wrap_key: processed}

    try:
        return json.dumps(processed)
    except (TypeError, ValueError):
        return None


async def router() -> None:
    args = parse_args()

    include_types: Optional[set] = None
    if args.include_type:
        include_types = {t.strip() for t in args.include_type.split(",") if t.strip()}

    target_ws: Optional[websockets.WebSocketClientProtocol] = None

    async def ensure_target_ws() -> Optional[websockets.WebSocketClientProtocol]:
        nonlocal target_ws
        if not args.to_ws_uri:
            return None
        if target_ws is not None and not target_ws.closed:
            return target_ws
        try:
            target_ws = await websockets.connect(args.to_ws_uri)
            print(f"Connected to target WebSocket at {args.to_ws_uri}")
            return target_ws
        except Exception as e:
            print(f"Failed to connect to target {args.to_ws_uri}: {e}")
            return None

    while True:
        print(f"Connecting to source WebSocket at {args.ws_uri}...")
        try:
            async with websockets.connect(args.ws_uri) as source_ws:
                print("Connected to source WebSocket.")

                try:
                    async for message in source_ws:
                        processed = transform_message(
                            raw_message=message,
                            include_types=include_types,
                            extract_path=args.extract,
                            wrap_key=args.wrap,
                        )

                        if processed is None:
                            continue

                        if args.print:
                            print(processed)

                        if args.to_ws_uri:
                            target = await ensure_target_ws()
                            if target is not None:
                                try:
                                    await target.send(processed)
                                except Exception as e:
                                    print(f"Failed to send to target: {e}")
                                    try:
                                        await target.close()
                                    except Exception:
                                        pass
                                    target_ws = None
                finally:
                    if target_ws is not None:
                        try:
                            await target_ws.close()
                        except Exception:
                            pass
                        target_ws = None

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"Source connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(router())
    except KeyboardInterrupt:
        print("Router stopped by user.")
