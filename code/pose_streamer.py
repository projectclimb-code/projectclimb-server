import cv2
import mediapipe as mp
import argparse
import asyncio
import websockets
import json

# Setup argument parser
parser = argparse.ArgumentParser(description="Capture video, detect pose, and stream landmarks via WebSocket.")
parser.add_argument("--source", default="0", help="Video source (camera index or file path). Default is 0 (webcam).")
parser.add_argument("--ws_uri", default="ws://localhost:8000/ws/pose/", help="WebSocket URI of the Django server.")
args = parser.parse_args()

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# Define a target frame rate
TARGET_FPS = 30
DELAY = 1 / TARGET_FPS

async def stream_pose_landmarks():
    """
    Connects to the WebSocket server and streams pose landmarks, with auto-reconnect.
    """
    while True:
        print(f"Attempting to connect to WebSocket server at {args.ws_uri}...")
        try:
            async with websockets.connect(args.ws_uri) as websocket:
                print("Successfully connected to WebSocket server.")
                
                video_source = int(args.source) if args.source.isdigit() else args.source
                cap = cv2.VideoCapture(video_source)

                if not cap.isOpened():
                    print(f"Error: Could not open video source: {args.source}")
                    await asyncio.sleep(5)
                    continue

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        print("End of video stream or cannot grab frame.")
                        break

                    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = pose.process(image_rgb)

                    landmarks_data = []
                    if results.pose_world_landmarks:
                        for landmark in results.pose_world_landmarks.landmark:
                            landmarks_data.append({
                                'x': landmark.x,
                                'y': landmark.y,
                                'z': landmark.z,
                                'visibility': landmark.visibility,
                            })
                    
                    try:
                        if landmarks_data:
                            await websocket.send(json.dumps(landmarks_data))
                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection lost. Reconnecting...")
                        break 
                    
                    # Enforce the target frame rate
                    await asyncio.sleep(DELAY)

                cap.release()

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"Failed to connect: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(stream_pose_landmarks())
    except KeyboardInterrupt:
        print("Streamer stopped by user.")
