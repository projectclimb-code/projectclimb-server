import argparse
import asyncio
import json
import math
import random
import time

import websockets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate fake pose landmarks and stream via WebSocket (no camera required)."
    )
    parser.add_argument(
        "--ws_uri",
        default="ws://localhost:8000/ws/pose/",
        help="WebSocket URI of the Django server.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target frames per second for sending frames.",
    )
    parser.add_argument(
        "--num_landmarks",
        type=int,
        default=33,
        help="Number of landmarks to generate per frame (MediaPipe Pose default is 33).",
    )
    parser.add_argument(
        "--mode",
        choices=["random", "sine", "walk", "idle", "climb"],
        default="sine",
        help="Pattern used to generate fake landmark motion.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible streams.",
    )
    return parser.parse_args()


class ClimbController:
    """Very lightweight climbing controller to mimic bouldering/rock-climbing.

    - Maintains a set of holds on a wall plane (z ~= const)
    - Alternates moving limbs: RH -> LH -> RF -> LF -> pause -> repeat
    - During a move, the moving limb interpolates toward a new higher hold
    - Pelvis shifts toward supporting holds and slightly into the wall
    - Other limbs remain planted with micro-jitter
    """

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random
        self.wall_z = 0.14
        self.holds = self._generate_holds()

        # Limb indices and order
        self.order = ["RH", "LH", "RF", "LF"]
        self.move_index = 0
        self.move_start_frame = 0
        self.move_duration = 45  # frames per move
        self.pause_frames = 25
        self.in_pause = False

        # Start posture: feet low, hands higher
        self.limb_to_hold: dict[str, int] = {}
        base_x = 0.0
        self.limb_to_hold["LF"] = self._nearest_hold(base_x - 0.18, 0.80)
        self.limb_to_hold["RF"] = self._nearest_hold(base_x + 0.18, 0.80)
        self.limb_to_hold["LH"] = self._nearest_hold(base_x - 0.14, 1.25)
        self.limb_to_hold["RH"] = self._nearest_hold(base_x + 0.14, 1.25)

        # Move target bookkeeping
        self.active_limb: str | None = None
        self.src_pos: tuple[float, float, float] | None = None
        self.dst_pos: tuple[float, float, float] | None = None

    def _generate_holds(self) -> list[tuple[float, float, float]]:
        holds: list[tuple[float, float, float]] = []
        # Grid with jitter: x in [-0.5..0.5], y in [0.7..1.8] (more compact)
        for yi in range(8):
            y = 0.7 + yi * 0.14 + self.rng.uniform(-0.02, 0.02)
            cols = 4 + (yi % 2)  # staggered
            for xi in range(cols):
                x_span = 0.6
                if cols <= 1:
                    x = 0.0
                else:
                    x = -x_span / 2 + xi * (x_span / (cols - 1))
                x += self.rng.uniform(-0.03, 0.03)
                holds.append((x, y, self.wall_z))
        return holds

    def _nearest_hold(self, x: float, y: float) -> int:
        best_i = 0
        best_d = float("inf")
        for i, (hx, hy, _) in enumerate(self.holds):
            d = (hx - x) ** 2 + (hy - y) ** 2
            if d < best_d:
                best_d = d
                best_i = i
        return best_i

    def _candidate_hold_above(self, ref_x: float, ref_y: float, min_dy: float, max_dy: float) -> int:
        candidates: list[int] = []
        for i, (hx, hy, _) in enumerate(self.holds):
            if hy > ref_y + min_dy and hy < ref_y + max_dy and abs(hx - ref_x) < 0.35:
                candidates.append(i)
        if not candidates:
            return self._nearest_hold(ref_x + self.rng.uniform(-0.2, 0.2), ref_y + max_dy)
        return self.rng.choice(candidates)

    def _limb_pos(self, limb: str) -> tuple[float, float, float]:
        idx = self.limb_to_hold[limb]
        return self.holds[idx]

    def _start_move(self, limb: str, frame_index: int) -> None:
        self.active_limb = limb
        self.move_start_frame = frame_index
        sx, sy, sz = self._limb_pos(limb)
        self.src_pos = (sx, sy, sz)

        # Choose destination hold
        if limb in ("LH", "RH"):
            # Reach hands higher than current hand height
            min_dy, max_dy = 0.12, 0.25
        else:
            # Feet step up smaller amount
            min_dy, max_dy = 0.08, 0.18

        # Reference x from current limb, allow a little lateral variation
        dst_index = self._candidate_hold_above(sx, sy, min_dy=min_dy, max_dy=max_dy)
        dx, dy, dz = self.holds[dst_index]
        self.dst_pos = (dx, dy, dz)

    def _interpolate(self, a: tuple[float, float, float], b: tuple[float, float, float], u: float, arc_z: float) -> tuple[float, float, float]:
        u2 = u * u * (3 - 2 * u)  # smoothstep
        x = a[0] + (b[0] - a[0]) * u2
        y = a[1] + (b[1] - a[1]) * u2
        # Small out-from-wall arc during motion
        z_mid = max(a[2], b[2]) + arc_z
        z = (1 - u2) * ((a[2] + z_mid) * 0.5) + u2 * ((z_mid + b[2]) * 0.5)
        return (x, y, z)

    def update(self, frame_index: int) -> dict[str, tuple[float, float, float]]:
        # Possibly transition states
        if self.active_limb is None and not self.in_pause:
            limb = self.order[self.move_index]
            self._start_move(limb, frame_index)
        elif self.active_limb is not None:
            # Check if finished
            u = (frame_index - self.move_start_frame) / max(1, self.move_duration)
            if u >= 1.0:
                # Snap to destination and pause
                self.limb_to_hold[self.active_limb] = self._nearest_hold(self.dst_pos[0], self.dst_pos[1])  # type: ignore[arg-type]
                self.active_limb = None
                self.src_pos = None
                self.dst_pos = None
                self.in_pause = True
                self.move_start_frame = frame_index
                # advance order
                self.move_index = (self.move_index + 1) % len(self.order)
        else:
            # Pause handling
            if frame_index - self.move_start_frame >= self.pause_frames:
                self.in_pause = False

        # Compute current limb positions
        limb_pos: dict[str, tuple[float, float, float]] = {}
        for limb in ["LH", "RH", "LF", "RF"]:
            if limb == self.active_limb and self.src_pos and self.dst_pos:
                arc = 0.03 if limb in ("LH", "RH") else 0.02
                u = (frame_index - self.move_start_frame) / max(1, self.move_duration)
                u = max(0.0, min(1.0, u))
                limb_pos[limb] = self._interpolate(self.src_pos, self.dst_pos, u, arc)
            else:
                sx, sy, sz = self._limb_pos(limb)
                # micro jitter
                limb_pos[limb] = (
                    sx + self.rng.uniform(-0.005, 0.005),
                    sy + self.rng.uniform(-0.005, 0.005),
                    sz + self.rng.uniform(-0.003, 0.003),
                )

        return limb_pos


# Persistent controller instance
_CLIMB_CTRL: ClimbController | None = None

def generate_fake_landmarks(
    frame_index: int,
    num_landmarks: int,
    mode: str,
) -> list[dict]:
    """Generate anatomically plausible MediaPipe Pose landmarks (33 points).

    The skeleton is built from simple segment lengths and animated with a
    lightweight gait/idle model. Coordinates are in meters-ish, with
    x (right), y (up), z (forward).
    """

    # MediaPipe Pose landmark indices (subset of names for clarity)
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32

    # Segment lengths (meters) and widths
    shoulder_width = 0.36
    hip_width = 0.30
    torso_height = 0.55
    neck_length = 0.10
    head_radius = 0.09
    upper_arm = 0.28
    lower_arm = 0.26
    hand_len = 0.10
    upper_leg = 0.45
    lower_leg = 0.45
    foot_len = 0.24

    # Animation parameters
    t = frame_index / 60.0
    omega = 2.0 * math.pi * 0.7  # step frequency ~0.7 Hz
    stride = 0.25
    sway_amp = 0.03
    bob_amp = 0.04

    # Interpret modes: "sine" behaves like a walk cycle; "idle" gentle sway; "climb" slower cadence
    if mode == "idle":
        omega = 2.0 * math.pi * 0.25
        stride = 0.0
        bob_amp = 0.01
    elif mode == "climb":
        omega = 2.0 * math.pi * 0.4
        stride = 0.0
        sway_amp = 0.015
        bob_amp = 0.02

    # Pelvis center (mid-hip). Small bob and lateral sway.
    pelvis_y_base = 1.0
    if mode == "climb":
        # Climbing: pelvis stays at fixed height, just sways for balance
        bob = bob_amp * math.sin(2.0 * omega * t) * 0.3
        sway = sway_amp * math.sin(omega * t * 0.7) * 0.8
        pelvis_center = (0.0 + sway, pelvis_y_base + bob, 0.02)
    else:
        bob = bob_amp * math.sin(2.0 * omega * t)
        sway = sway_amp * math.sin(omega * t)
        pelvis_center = (0.0 + sway, pelvis_y_base + bob, 0.0)

    # Helper to add small noise, keeping stability
    def jitter(scale: float = 0.01) -> float:
        return random.uniform(-scale, scale)

    # Initialize output array
    points: list[dict | None] = [None] * 33

    def set_point(idx: int, x: float, y: float, z: float, vis: float = 0.95) -> None:
        points[idx] = {
            "x": x,
            "y": y,
            "z": z,
            "visibility": max(0.0, min(1.0, vis + jitter(0.02))),
        }

    # Hips (left/right)
    lx = -hip_width / 2.0
    rx = hip_width / 2.0
    lhip = (pelvis_center[0] + lx, pelvis_center[1], pelvis_center[2])
    rhip = (pelvis_center[0] + rx, pelvis_center[1], pelvis_center[2])
    set_point(LEFT_HIP, *lhip)
    set_point(RIGHT_HIP, *rhip)

    # Shoulders relative to pelvis
    shoulder_y = pelvis_center[1] + torso_height
    lsh = (pelvis_center[0] - shoulder_width / 2.0, shoulder_y, pelvis_center[2])
    rsh = (pelvis_center[0] + shoulder_width / 2.0, shoulder_y, pelvis_center[2])
    set_point(LEFT_SHOULDER, *lsh)
    set_point(RIGHT_SHOULDER, *rsh)

    # Neck and head
    neck = (pelvis_center[0], shoulder_y + neck_length, pelvis_center[2])
    head_center = (neck[0], neck[1] + head_radius * 1.2, neck[2])
    nose = (head_center[0], head_center[1], head_center[2] + head_radius * 0.8)
    set_point(NOSE, nose[0] + jitter(0.005), nose[1] + jitter(0.005), nose[2] + jitter(0.005))

    eye_off_y = 0.02
    eye_off_x = 0.03
    eye_off_z = 0.06
    set_point(LEFT_EYE_INNER, head_center[0] - eye_off_x * 0.5, head_center[1] + eye_off_y, head_center[2] + eye_off_z)
    set_point(LEFT_EYE, head_center[0] - eye_off_x, head_center[1] + eye_off_y, head_center[2] + eye_off_z)
    set_point(LEFT_EYE_OUTER, head_center[0] - eye_off_x * 1.5, head_center[1] + eye_off_y, head_center[2] + eye_off_z * 0.9)
    set_point(RIGHT_EYE_INNER, head_center[0] + eye_off_x * 0.5, head_center[1] + eye_off_y, head_center[2] + eye_off_z)
    set_point(RIGHT_EYE, head_center[0] + eye_off_x, head_center[1] + eye_off_y, head_center[2] + eye_off_z)
    set_point(RIGHT_EYE_OUTER, head_center[0] + eye_off_x * 1.5, head_center[1] + eye_off_y, head_center[2] + eye_off_z * 0.9)

    ear_off_x = 0.07
    ear_off_z = -0.01
    set_point(LEFT_EAR, head_center[0] - ear_off_x, head_center[1] + 0.0, head_center[2] + ear_off_z)
    set_point(RIGHT_EAR, head_center[0] + ear_off_x, head_center[1] + 0.0, head_center[2] + ear_off_z)

    mouth_off_y = -0.025
    mouth_off_x = 0.02
    mouth_off_z = 0.07
    set_point(MOUTH_LEFT, head_center[0] - mouth_off_x, head_center[1] + mouth_off_y, head_center[2] + mouth_off_z)
    set_point(MOUTH_RIGHT, head_center[0] + mouth_off_x, head_center[1] + mouth_off_y, head_center[2] + mouth_off_z)

    if mode == "climb":
        # Use climbing controller for realistic limb placements on wall holds
        global _CLIMB_CTRL
        if _CLIMB_CTRL is None:
            _CLIMB_CTRL = ClimbController()
        limb_positions = _CLIMB_CTRL.update(frame_index)

        # Torso lean toward wall and slight bias to active hand
        torso_lean_z = 0.05
        active_bias = 0.0
        if _CLIMB_CTRL.active_limb in ("LH", "RH"):
            active_bias = -0.03 if _CLIMB_CTRL.active_limb == "LH" else 0.03
        lsh = (lsh[0] - active_bias, lsh[1], lsh[2] + torso_lean_z)
        rsh = (rsh[0] + active_bias, rsh[1], rsh[2] + torso_lean_z)
        lhip = (lhip[0] - active_bias * 0.5, lhip[1], lhip[2] + torso_lean_z * 0.4)
        rhip = (rhip[0] + active_bias * 0.5, rhip[1], rhip[2] + torso_lean_z * 0.4)

        # Hands to holds and elbows bent toward shoulders
        lwrist = limb_positions["LH"]
        rwrist = limb_positions["RH"]
        lelbow = ((lsh[0] + lwrist[0]) * 0.5, (lsh[1] + lwrist[1]) * 0.5, (lsh[2] + lwrist[2]) * 0.5)
        relbow = ((rsh[0] + rwrist[0]) * 0.5, (rsh[1] + rwrist[1]) * 0.5, (rsh[2] + rwrist[2]) * 0.5)
        set_point(LEFT_ELBOW, *lelbow)
        set_point(RIGHT_ELBOW, *relbow)
        set_point(LEFT_WRIST, *lwrist)
        set_point(RIGHT_WRIST, *rwrist)

        # Feet to holds and knees slightly bent forward
        lankle = limb_positions["LF"]
        rankle = limb_positions["RF"]
        lknee = ((lhip[0] + lankle[0]) * 0.5, (lhip[1] + lankle[1]) * 0.6, (lhip[2] + lankle[2]) * 0.5)
        rknee = ((rhip[0] + rankle[0]) * 0.5, (rhip[1] + rankle[1]) * 0.6, (rhip[2] + rankle[2]) * 0.5)
        set_point(LEFT_KNEE, *lknee)
        set_point(RIGHT_KNEE, *rknee)
        set_point(LEFT_ANKLE, *lankle)
        set_point(RIGHT_ANKLE, *rankle)

        # Feet pressing the wall
        lheel = (lankle[0], lankle[1] - 0.02, lankle[2] - foot_len * 0.15)
        rheel = (rankle[0], rankle[1] - 0.02, rankle[2] - foot_len * 0.15)
        ltoe = (lankle[0], lankle[1] - 0.005, lankle[2] + foot_len * 0.5)
        rtoe = (rankle[0], rankle[1] - 0.005, rankle[2] + foot_len * 0.5)
        set_point(LEFT_HEEL, *lheel)
        set_point(RIGHT_HEEL, *rheel)
        set_point(LEFT_FOOT_INDEX, *ltoe)
        set_point(RIGHT_FOOT_INDEX, *rtoe)

        # Finger approximations on the wall
        def hand_points_wall(wrist: tuple[float, float, float], side_sign: float) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
            index_pt = (wrist[0] + side_sign * 0.015, wrist[1] - 0.01, wrist[2] + 0.005)
            pinky_pt = (wrist[0] - side_sign * 0.015, wrist[1] - 0.01, wrist[2] + 0.005)
            thumb_pt = (wrist[0] + side_sign * 0.02, wrist[1] - 0.005, wrist[2] - 0.005)
            return index_pt, pinky_pt, thumb_pt

        l_index, l_pinky, l_thumb = hand_points_wall(lwrist, -1.0)
        r_index, r_pinky, r_thumb = hand_points_wall(rwrist, 1.0)
        set_point(LEFT_INDEX, *l_index)
        set_point(LEFT_PINKY, *l_pinky)
        set_point(LEFT_THUMB, *l_thumb)
        set_point(RIGHT_INDEX, *r_index)
        set_point(RIGHT_PINKY, *r_pinky)
        set_point(RIGHT_THUMB, *r_thumb)
    else:
        # Default walk/idle/sine/random behavior
        def leg_chain(hip: tuple[float, float, float], phase: float) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
            s = math.sin(omega * t + phase)
            c = math.cos(omega * t + phase)
            z_off = stride * s
            knee_y = hip[1] - upper_leg + 0.05 * (1.0 - c)
            knee_z = hip[2] + z_off * 0.5
            ankle_y = knee_y - lower_leg + 0.03 * (1.0 - math.cos(omega * t * 2.0 + phase))
            ankle_z = hip[2] + z_off
            return (knee_y, knee_z), (ankle_y, ankle_z), (z_off,)

        (l_knee_y, l_knee_z), (l_ankle_y, l_ankle_z), _ = leg_chain(lhip, 0.0)
        (r_knee_y, r_knee_z), (r_ankle_y, r_ankle_z), _ = leg_chain(rhip, math.pi)

        lknee = (lhip[0], l_knee_y, l_knee_z)
        rknee = (rhip[0], r_knee_y, r_knee_z)
        lankle = (lhip[0], l_ankle_y, l_ankle_z)
        rankle = (rhip[0], r_ankle_y, r_ankle_z)

        set_point(LEFT_KNEE, *lknee)
        set_point(RIGHT_KNEE, *rknee)
        set_point(LEFT_ANKLE, *lankle)
        set_point(RIGHT_ANKLE, *rankle)

        lheel = (lankle[0], lankle[1] - 0.02, lankle[2] - foot_len * 0.3)
        rheel = (rankle[0], rankle[1] - 0.02, rankle[2] - foot_len * 0.3)
        ltoe = (lankle[0], lankle[1] - 0.01, lankle[2] + foot_len)
        rtoe = (rankle[0], rankle[1] - 0.01, rankle[2] + foot_len)
        set_point(LEFT_HEEL, *lheel)
        set_point(RIGHT_HEEL, *rheel)
        set_point(LEFT_FOOT_INDEX, *ltoe)
        set_point(RIGHT_FOOT_INDEX, *rtoe)

        def arm_chain(shoulder: tuple[float, float, float], opposite_leg_phase: float, side_sign: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
            s = math.sin(omega * t + opposite_leg_phase)
            z_off = -0.6 * stride * s
            elbow_y = shoulder[1] - upper_arm + 0.02 * (1.0 - math.cos(omega * t * 1.5 + opposite_leg_phase))
            elbow_z = shoulder[2] + z_off * 0.5
            wrist_y = elbow_y - lower_arm
            wrist_z = shoulder[2] + z_off
            elbow_x = shoulder[0] + side_sign * 0.03
            wrist_x = shoulder[0] + side_sign * 0.05
            return (elbow_x, elbow_y, elbow_z), (wrist_x, wrist_y, wrist_z)

        lelbow, lwrist = arm_chain(lsh, math.pi, -1.0)
        relbow, rwrist = arm_chain(rsh, 0.0, 1.0)
        set_point(LEFT_ELBOW, *lelbow)
        set_point(RIGHT_ELBOW, *relbow)
        set_point(LEFT_WRIST, *lwrist)
        set_point(RIGHT_WRIST, *rwrist)

        def hand_points(wrist: tuple[float, float, float], side_sign: float) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
            index_pt = (wrist[0] + side_sign * 0.02, wrist[1] - 0.02, wrist[2] + hand_len)
            pinky_pt = (wrist[0] - side_sign * 0.02, wrist[1] - 0.02, wrist[2] + hand_len * 0.9)
            thumb_pt = (wrist[0] + side_sign * 0.03, wrist[1] - 0.01, wrist[2] + hand_len * 0.5)
            return index_pt, pinky_pt, thumb_pt

        l_index, l_pinky, l_thumb = hand_points(lwrist, -1.0)
        r_index, r_pinky, r_thumb = hand_points(rwrist, 1.0)
        set_point(LEFT_INDEX, *l_index)
        set_point(LEFT_PINKY, *l_pinky)
        set_point(LEFT_THUMB, *l_thumb)
        set_point(RIGHT_INDEX, *r_index)
        set_point(RIGHT_PINKY, *r_pinky)
        set_point(RIGHT_THUMB, *r_thumb)

    # Apply extra jitter for "random" mode
    if mode == "random":
        for i, p in enumerate(points):
            if p is None:
                continue
            p["x"] += jitter(0.04)
            p["y"] += jitter(0.04)
            p["z"] += jitter(0.04)

    # Fill any remaining points with reasonable fallbacks (shouldn't happen)
    for i in range(len(points)):
        if points[i] is None:
            points[i] = {
                "x": pelvis_center[0] + jitter(0.01),
                "y": pelvis_center[1] + jitter(0.01),
                "z": pelvis_center[2] + jitter(0.01),
                "visibility": 0.9,
            }

    # Re-center around pelvis and flip Y so the viewer (which negates axes) shows upright pose.
    cx, cy, cz = pelvis_center
    for p in points:
        if p is None:
            continue
        p["x"] = p["x"] - cx
        p["y"] = -(p["y"] - cy)
        p["z"] = p["z"] - cz

    # Respect requested landmark count by truncating (kept for compatibility)
    return points[:num_landmarks]


async def stream_fake_pose_landmarks() -> None:
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    target_fps = max(1, args.fps)
    delay = 1.0 / target_fps
    frame_index = 0

    while True:
        print(f"Attempting to connect to WebSocket server at {args.ws_uri}...")
        try:
            async with websockets.connect(args.ws_uri) as websocket:
                print("Successfully connected to WebSocket server.")
                while True:
                    start = time.perf_counter()

                    landmarks = generate_fake_landmarks(
                        frame_index=frame_index,
                        num_landmarks=args.num_landmarks,
                        mode=args.mode,
                    )

                    try:
                        if landmarks:
                            out = {
                                "type": "pose",
                                "timestamp": 1762281159873,
                                "width": 640,
                                "height": 480,
                                "landmarks":landmarks
                            }
                            await websocket.send(json.dumps(out))
                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection lost. Reconnecting...")
                        break

                    frame_index += 1

                    # Enforce target FPS accounting for time spent computing/sending
                    elapsed = time.perf_counter() - start
                    sleep_for = max(0.0, delay - elapsed)
                    await asyncio.sleep(sleep_for)

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"Failed to connect: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)


class FakePoseStreamer:
    """
    Class-based fake pose streamer that can be imported and used by other modules.
    Generates fake pose landmarks for testing purposes.
    """
    
    def __init__(self, mode="climb", fps=30, seed=None):
        """
        Initialize the fake pose streamer.
        
        Args:
            mode: Motion mode ("random", "sine", "walk", "idle", "climb")
            fps: Target frames per second
            seed: Random seed for reproducible streams
        """
        self.mode = mode
        self.fps = fps
        self.frame_index = 0
        
        if seed is not None:
            random.seed(seed)
        
        # Initialize climb controller if needed
        if mode == "climb":
            global _CLIMB_CTRL
            if _CLIMB_CTRL is None:
                _CLIMB_CTRL = ClimbController()
    
    def get_frame(self):
        """
        Get the next frame of fake pose data.
        
        Returns:
            Tuple of (frame_image, pose_data) where frame_image is None for fake streamer
            and pose_data is a dictionary with pose landmarks.
        """
        # Generate fake landmarks
        landmarks = generate_fake_landmarks(
            frame_index=self.frame_index,
            num_landmarks=33,
            mode=self.mode,
        )
        
        # Convert to expected format for pose touch detector
        pose_data = {
            'pose_landmarks': self._convert_to_pose_dict(landmarks),
            'timestamp': time.time(),
            'frame_number': self.frame_index
        }
        
        self.frame_index += 1
        
        # Return None for frame image since we're not generating actual video
        return None, pose_data
    
    def _convert_to_pose_dict(self, landmarks):
        """
        Convert MediaPipe landmark format to a simplified dictionary format.
        
        Args:
            landmarks: List of landmark dictionaries from generate_fake_landmarks
            
        Returns:
            Dictionary with key landmark positions
        """
        pose_dict = {}
        
        # Map landmark indices to names
        landmark_names = {
            0: 'nose',
            11: 'left_shoulder',
            12: 'right_shoulder',
            13: 'left_elbow',
            14: 'right_elbow',
            15: 'left_wrist',
            16: 'right_wrist',
            19: 'left_index',
            20: 'right_index',
            23: 'left_hip',
            24: 'right_hip',
            25: 'left_knee',
            26: 'right_knee',
            27: 'left_ankle',
            28: 'right_ankle'
        }
        
        for i, landmark in enumerate(landmarks):
            if i in landmark_names:
                pose_dict[landmark_names[i]] = [landmark['x'], landmark['y'], landmark['z']]
        
        return pose_dict


if __name__ == "__main__":
    try:
        asyncio.run(stream_fake_pose_landmarks())
    except KeyboardInterrupt:
        print("Fake streamer stopped by user.")


