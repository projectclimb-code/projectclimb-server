import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
import pandas as pd
from datetime import datetime
import seaborn as sns

# Parse the pose data
pose_data = []
for line in data.split('\n'):
    if line.strip() and line.startswith('|'):
        try:
            json_str = line.split('|', 1)[1].strip()
            pose_entry = json.loads(json_str)
            pose_data.append(pose_entry)
        except:
            continue

print(f"Loaded {len(pose_data)} pose frames")
print(f"Time range: {pose_data[0]['timestamp']} to {pose_data[-1]['timestamp']}")
print(f"Duration: {(pose_data[-1]['timestamp'] - pose_data[0]['timestamp'])/1000:.2f} seconds")

# Extract landmarks into a more usable format
def extract_landmarks(pose_entry):
    landmarks = np.array([[lm['x'], lm['y'], lm['z'], lm['visibility']] 
                          for lm in pose_entry['landmarks']])
    return landmarks

# MediaPipe pose landmark names for reference
landmark_names = [
    'nose_tip', 'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
    'right_eye_inner', 'right_eye', 'right_eye_outer', 'left_ear',
    'right_ear', 'mouth_left', 'mouth_right', 'left_shoulder',
    'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist',
    'right_wrist', 'left_pinky', 'right_pinky', 'left_index',
    'right_index', 'left_thumb', 'right_thumb', 'left_hip',
    'right_hip', 'left_knee', 'right_knee', 'left_ankle',
    'right_ankle', 'left_heel', 'right_heel'
]

# Extract all landmarks
all_landmarks = np.array([extract_landmarks(entry) for entry in pose_data])
timestamps = np.array([entry['timestamp'] for entry in pose_data])

# Convert timestamps to seconds relative to start
time_seconds = (timestamps - timestamps[0]) / 1000

# Calculate movement statistics
def calculate_movement_stats():
    # Focus on key body parts for movement analysis
    key_points = {
        'head': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # face landmarks
        'left_arm': [11, 13, 15, 17, 19, 21],  # left arm
        'right_arm': [12, 14, 16, 18, 20, 22],  # right arm
        'torso': [11, 12, 23, 24],  # shoulders and hips
        'left_leg': [23, 25, 27, 29, 31],  # left leg
        'right_leg': [24, 26, 28, 30, 32]  # right leg
    }
    
    stats = {}
    for part_name, indices in key_points.items():
        positions = all_landmarks[:, indices, :3]  # x, y, z coordinates
        velocities = np.diff(positions, axis=0) / np.diff(time_seconds)[:, np.newaxis]
        
        # Calculate average speed for this body part
        speeds = np.linalg.norm(velocities, axis=2)
        stats[part_name] = {
            'avg_speed': np.mean(speeds),
            'max_speed': np.max(speeds),
            'total_distance': np.sum(np.linalg.norm(np.diff(positions, axis=0), axis=1))
        }
    
    return stats

movement_stats = calculate_movement_stats()

# Create visualizations
fig = plt.figure(figsize=(20, 12))

# 1. Movement speed analysis
plt.subplot(2, 3, 1)
parts = list(movement_stats.keys())
avg_speeds = [movement_stats[part]['avg_speed'] for part in parts]
bars = plt.bar(parts, avg_speeds)
plt.title('Average Movement Speed by Body Part', fontsize=14)
plt.ylabel('Speed (units/second)')
plt.xticks(rotation=45)
# Add value labels on bars
for bar, speed in zip(bars, avg_speeds):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
             f'{speed:.3f}', ha='center', va='bottom')

# 2. Total distance traveled
plt.subplot(2, 3, 2)
total_distances = [movement_stats[part]['total_distance'] for part in parts]
bars = plt.bar(parts, total_distances)
plt.title('Total Distance Traveled by Body Part', fontsize=14)
plt.ylabel('Distance (units)')
plt.xticks(rotation=45)
for bar, dist in zip(bars, total_distances):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
             f'{dist:.2f}', ha='center', va='bottom')

# 3. Trajectory of key points over time
plt.subplot(2, 3, 3)
# Plot nose trajectory
nose_x = all_landmarks[:, 0, 0]  # nose tip x
nose_y = all_landmarks[:, 0, 1]  # nose tip y
plt.scatter(nose_x, nose_y, c=time_seconds, cmap='viridis', s=2)
plt.colorbar(label='Time (s)')
plt.title('Nose Tip Trajectory Over Time', fontsize=14)
plt.xlabel('X coordinate')
plt.ylabel('Y coordinate')
plt.gca().invert_yaxis()  # Invert y to match image coordinates

# 4. Visibility analysis
plt.subplot(2, 3, 4)
all_visibilities = all_landmarks[:, :, 3].flatten()
plt.hist(all_visibilities, bins=50, alpha=0.7, edgecolor='black')
plt.title('Distribution of Landmark Visibility Scores', fontsize=14)
plt.xlabel('Visibility Score')
plt.ylabel('Frequency')
plt.axvline(x=0.5, color='r', linestyle='--', label='0.5 threshold')
plt.legend()

# 5. Height variation (y-coordinate of head)
plt.subplot(2, 3, 5)
head_y = np.mean(all_landmarks[:, :10, 1], axis=1)  # Average y of face landmarks
plt.plot(time_seconds, head_y, 'b-', linewidth=2)
plt.title('Head Height Variation Over Time', fontsize=14)
plt.xlabel('Time (seconds)')
plt.ylabel('Average Y-coordinate')
plt.grid(True, alpha=0.3)

# 6. Arm span variation
plt.subplot(2, 3, 6)
left_wrist = all_landmarks[:, 15, :2]  # left wrist
right_wrist = all_landmarks[:, 16, :2]  # right wrist
arm_span = np.linalg.norm(left_wrist - right_wrist, axis=1)
plt.plot(time_seconds, arm_span, 'r-', linewidth=2)
plt.title('Arm Span Variation Over Time', fontsize=14)
plt.xlabel('Time (seconds)')
plt.ylabel('Distance between wrists')
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# Create a 3D visualization of the pose at a specific frame
def plot_3d_pose(frame_idx=50):
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    landmarks = all_landmarks[frame_idx, :, :3]
    visibilities = all_landmarks[frame_idx, :, 3]
    
    # Plot connections between landmarks (simplified skeleton)
    connections = [
        (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
        (9, 11), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
        (10, 12), (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
        (11, 23), (12, 24), (23, 24), (23, 25), (24, 26), (25, 27), (26, 28),
        (27, 29), (28, 30), (29, 31), (30, 32), (31, 33), (32, 33)
    ]
    
    # Plot skeleton connections
    for start, end in connections:
        if visibilities[start] > 0.5 and visibilities[end] > 0.5:
            ax.plot3D([landmarks[start, 0], landmarks[end, 0]],
                     [landmarks[start, 1], landmarks[end, 1]],
                     [landmarks[start, 2], landmarks[end, 2]], 'b-', alpha=0.6)
    
    # Plot landmarks
    colors = ['red' if v > 0.5 else 'gray' for v in visibilities]
    sizes = [50 if v > 0.5 else 20 for v in visibilities]
    ax.scatter(landmarks[:, 0], landmarks[:, 1], landmarks[:, 2], 
               c=colors, s=sizes, alpha=0.8)
    
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(f'3D Pose Visualization (Frame {frame_idx}, Time: {time_seconds[frame_idx]:.2f}s)')
    
    # Set equal aspect ratio
    max_range = np.array([landmarks[:, :3].max(axis=0) - landmarks[:, :3].min(axis=0)]).max() / 2.0
    mid_x = (landmarks[:, 0].max() + landmarks[:, 0].min()) * 0.5
    mid_y = (landmarks[:, 1].max() + landmarks[:, 1].min()) * 0.5
    mid_z = (landmarks[:, 2].max() + landmarks[:, 2].min()) * 0.5
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
    
    plt.show()

# Plot 3D pose for middle frame
plot_3d_pose(frame_idx=len(pose_data)//2)

# Print summary statistics
print("\n=== MOVEMENT ANALYSIS SUMMARY ===")
print(f"Total recording duration: {time_seconds[-1]:.2f} seconds")
print(f"Number of frames: {len(pose_data)}")
print(f"Average frame rate: {len(pose_data)/time_seconds[-1]:.2f} FPS")

print("\n=== BODY PART MOVEMENT RANKINGS ===")
sorted_by_speed = sorted(movement_stats.items(), key=lambda x: x[1]['avg_speed'], reverse=True)
print("Fastest moving parts (average speed):")
for i, (part, stats) in enumerate(sorted_by_speed[:5]):
    print(f"{i+1}. {part}: {stats['avg_speed']:.4f} units/s")

sorted_by_distance = sorted(movement_stats.items(), key=lambda x: x[1]['total_distance'], reverse=True)
print("\nParts that traveled most distance:")
for i, (part, stats) in enumerate(sorted_by_distance[:5]):
    print(f"{i+1}. {part}: {stats['total_distance']:.2f} units")

print("\n=== VISIBILITY ANALYSIS ===")
print(f"Average visibility across all landmarks: {np.mean(all_visibilities):.3f}")
print(f"Percentage of landmarks with visibility > 0.5: {np.mean(all_visibilities > 0.5)*100:.1f}%")
print(f"Percentage of landmarks with visibility > 0.9: {np.mean(all_visibilities > 0.9)*100:.1f}%")

# Detect potential issues or interesting patterns
print("\n=== PATTERN DETECTION ===")
# Check for sudden movements
velocities = np.diff(all_landmarks[:, :, :3], axis=0)
speeds = np.linalg.norm(velocities, axis=2)
max_speed_frame = np.argmax(np.max(speeds, axis=1))
print(f"Frame with maximum movement: {max_speed_frame} (Time: {time_seconds[max_speed_frame]:.2f}s)")

# Check for pose stability
pose_stability = 1 - np.std(speeds) / np.mean(speeds)
print(f"Pose stability index (higher is more stable): {pose_stability:.3f}")

# Check for occlusion (low visibility)
low_vis_frames = np.sum(np.mean(all_landmarks[:, :, 3], axis=1) < 0.5)
print(f"Number of frames with average visibility < 0.5: {low_vis_frames}")
