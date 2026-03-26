# Performance Analysis: Interactive Wall System GLM

## Executive Summary

The [`interactive_wall_system_glm.py`](code/climber/management/commands/interactive_wall_system_glm.py) file processes pose data in real-time and appears to have several performance bottlenecks that could cause lag. This analysis identifies critical issues and provides prioritized recommendations.

## Critical Performance Issues

### 1. **Per-Frame State Broadcasting (Lines 705-709)**
**Severity: HIGH** | **Impact: HIGH**

**Current Code:**
```python
# 5. Send state on every pose frame (throttled to pose_send_interval)
now = time.time()
if now - self.last_pose_send_time >= self.pose_send_interval:
    self.last_pose_send_time = now
    await self.send_system_state()
```

**Problem:**
- State is sent at 30 FPS (`pose_send_interval = 1.0/30`)
- Each state message includes full route data, palm positions, text, etc.
- WebSocket queue may back up if network is slow
- Unnecessary to send full state on every frame for unchanged data

**Impact:** Network bandwidth saturation, message queue buildup, increased latency

**Recommendation:**
- Only send state when it actually changes (diff-based updates)
- Separate high-frequency data (palms) from low-frequency data (route info)
- Use binary protocol or compression for large payloads
- Implement state change detection before sending

---

### 2. **O(n) Path Intersection Checks (Lines 412-435)**
**Severity: HIGH** | **Impact: MEDIUM-HIGH**

**Current Code:**
```python
def check_hold_intersections(position, precomputed_paths=None, buttons=None):
    if position is None:
        return set(), set()
    touched_holds = set()
    touched_buttons = set()
    
    # Check holds using pre-computed matplotlib Path objects with bbox fast rejection
    if precomputed_paths:
        point = (position[0], position[1])
        for path_id, precomputed in precomputed_paths.items():
            try:
                if SVGParser.point_in_precomputed_path(point, precomputed):
                    touched_holds.add(path_id)
            except Exception:
                pass
```

**Problem:**
- Iterates through ALL holds for every hand position check
- Even with bbox rejection, still checks every path
- Called 2x per frame (left + right hand)
- Called again for ArUco markers in draw mode
- For 100 holds, that's 300+ path checks per frame at 30 FPS = 9,000 checks/second

**Impact:** CPU-intensive, especially with many holds

**Recommendation:**
- Implement spatial indexing (R-tree or Quadtree) for holds
- Only check holds within a reasonable radius of hand position
- Cache recently touched holds to avoid re-checking
- Use numpy vectorization for batch distance calculations

---

### 3. **Synchronous Database Queries in Async Context (Lines 533-536, 576)**
**Severity: MEDIUM** | **Impact: MEDIUM**

**Current Code:**
```python
@database_sync_to_async
def fetch_routes_by_difficulty(self, difficulty: str):
    routes = list(Route.objects.filter(difficulty=difficulty))
    return routes
```

**Problem:**
- Database queries block the async event loop
- Called on every mode switch
- Fetches ALL routes for a difficulty at once
- Routes are stored in memory but could be lazy-loaded

**Impact:** Event loop blocking during mode switches, potential lag spikes

**Recommendation:**
- Use Django's async ORM (Django 4.1+) if available
- Implement route caching with TTL
- Only fetch routes when actually needed (lazy loading)
- Consider using `select_related`/`prefetch_related` if routes have relationships

---

### 4. **Redundant Coordinate Transformations (Lines 650, 664, 683)**
**Severity: MEDIUM** | **Impact: MEDIUM**

**Current Code:**
```python
# Line 650 - Transform for hand intersection check
svg_pos = transform_to_svg_coordinates(h, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)

# Line 664 - Transform for ArUco (same function)
svg_pos = transform_to_svg_coordinates(pos, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)

# Line 683 - Transform again for debug output
svg_pos = transform_to_svg_coordinates(hand_pos, self.calibration_utils, self.transform_matrix, self.svg_size, img_width, img_height, calibration_type=self.calibration.calibration_type)
```

**Problem:**
- Same hand position transformed multiple times per frame
- Matrix multiplication is expensive when done repeatedly
- Calibration type check inside hot path

**Impact:** Unnecessary CPU cycles in the main processing loop

**Recommendation:**
- Cache transformed coordinates within the frame
- Pre-compute transformation matrix based on calibration type
- Transform once and reuse the result

---

### 5. **Distance Calculations in Debug Mode (Lines 688-693)**
**Severity: LOW** | **Impact: MEDIUM (if enabled)**

**Current Code:**
```python
if self.hold_centers:
    distances = [
        (h_id, np.sqrt((svg_pos[0]-cx)**2 + (svg_pos[1]-cy)**2))
        for h_id, (cx, cy) in self.hold_centers.items()
    ]
    if distances:
        closest_id, min_dist = min(distances, key=lambda x: x[1])
```

**Problem:**
- O(n) distance calculation to ALL holds
- Called every 5 seconds per hand
- Uses Python list comprehension with lambda (slow)
- Calculates sqrt for every distance (only needed for min)

**Impact:** CPU spike every 5 seconds when debug mode is enabled

**Recommendation:**
- Use squared distance for comparison (avoid sqrt)
- Use numpy vectorization
- Cache closest hold and only recalculate if moved significantly

---

### 6. **Inefficient Touch Tracker Data Structures (Lines 32-68)**
**Severity: LOW-MEDIUM** | **Impact: LOW-MEDIUM**

**Current Code:**
```python
self.touch_start_times = {}  # hold_id -> timestamp
self.touch_last_seen = {}    # hold_id -> timestamp
self.sent_events = {}       # hold_id -> last threshold index reached (int)
```

**Problem:**
- Multiple dictionaries for related data
- Dictionary lookups are fast but could be optimized
- `list()` usage in iteration (line 47, 74) creates unnecessary copies

**Impact:** Minor overhead, but adds up over many iterations

**Recommendation:**
- Use a single dataclass or named tuple for touch state
- Avoid creating list copies when iterating
- Consider using `collections.defaultdict` for cleaner code

---

### 7. **JSON Serialization on Every Send (Line 246, 762-782)**
**Severity: MEDIUM** | **Impact: MEDIUM**

**Current Code:**
```python
# In OutputWebSocketClient.message_sender
await self.websocket.send(json.dumps(message))

# In send_system_state
message = {
    'type': 'interactive_state',
    'wall_id': self.wall_id,
    'mode': self.state.mode,
    'active_holds': active_holds,
    'route_holds': active_holds if self.state.mode in ['easy', 'medium', 'hard', 'draw'] else [],
    'route_data': route_data,
    'touched_holds': list(self.state.current_touched_holds),
    'palms': {...},
    'route_name': route_name,
    'text': text,
    'custom_text': custom_text,
    'svg_width': self.svg_size[0],
    'svg_height': self.svg_size[1],
    'timestamp': time.time()
}
```

**Problem:**
- `json.dumps()` is called for every message
- Converting sets to lists creates new objects
- Timestamp calculated on every message
- Large route_data serialized repeatedly

**Impact:** CPU overhead from serialization, especially at high frequency

**Recommendation:**
- Use a faster JSON library (orjson, ujson)
- Pre-serialize static data
- Use binary format (MessagePack, protobuf) for high-frequency data
- Only include changed fields in updates

---

### 8. **Blocking I/O in WebSocket Clients (Lines 136-146, 186-222)**
**Severity: LOW** | **Impact: LOW-MEDIUM**

**Current Code:**
```python
async def connect(self):
    while self.running:
        try:
            logger.info(f"Connecting to input WebSocket: {self.url}")
            self.websocket = await websockets.connect(self.url)
```

**Problem:**
- Connection attempts block the event loop
- Exponential backoff can cause long delays
- No timeout on connection attempts

**Impact:** Potential event loop blocking during reconnection

**Recommendation:**
- Use `asyncio.wait_for()` with timeout
- Implement connection pooling
- Consider using a connection manager

---

## Additional Observations

### Setup Phase (Lines 476-531)
- SVG parsing and path precomputation happen synchronously
- Could be slow for large SVG files
- Consider caching precomputed data

### Touch Tracking Logic
- Touch duration thresholds are hardcoded (2.0s for hands, 1.0s for ArUco)
- Lost tolerance values are also hardcoded
- Consider making these configurable

### Error Handling
- Broad `except Exception` blocks (lines 158, 425, 711)
- Could mask performance issues
- Consider more specific exception handling

---

## Priority Recommendations Summary

| Priority | Issue | Impact | Effort |
|----------|-------|--------|--------|
| **P0** | Per-frame state broadcasting | HIGH | MEDIUM |
| **P0** | O(n) path intersection checks | HIGH | MEDIUM |
| **P1** | Redundant coordinate transformations | MEDIUM | LOW |
| **P1** | JSON serialization overhead | MEDIUM | LOW |
| **P2** | Synchronous database queries | MEDIUM | MEDIUM |
| **P2** | Debug mode distance calculations | MEDIUM | LOW |
| **P3** | Touch tracker data structures | LOW-MEDIUM | LOW |
| **P3** | Blocking WebSocket connections | LOW-MEDIUM | MEDIUM |

---

## Implementation Roadmap

### Phase 1: Quick Wins (Low effort, high impact)
1. Cache transformed coordinates within frame
2. Use faster JSON library (orjson)
3. Remove list() copies in touch tracker
4. Optimize debug distance calculations

### Phase 2: Core Optimizations (Medium effort, high impact)
1. Implement diff-based state updates
2. Add spatial indexing for hold intersections
3. Separate high/low frequency data streams

### Phase 3: Advanced Optimizations (Higher effort)
1. Migrate to async ORM
2. Implement route caching
3. Add binary protocol support
4. Optimize setup phase with caching

---

## Performance Metrics to Track

- **Frame processing time**: Time from pose data receipt to completion
- **State send frequency**: Actual vs. intended send rate
- **WebSocket queue depth**: Messages waiting to be sent
- **CPU usage**: Per-frame and average
- **Memory usage**: Peak and average
- **Network bandwidth**: Bytes sent per second
- **Intersection check count**: Per frame and total

---

## Testing Strategy

1. **Load Testing**: Simulate high-frequency pose data (30+ FPS)
2. **Stress Testing**: Test with large number of holds (100+)
3. **Network Simulation**: Test with slow/high-latency connections
4. **Profiling**: Use cProfile to identify hotspots
5. **Benchmarking**: Compare before/after metrics

---

## Conclusion

The system's primary performance bottleneck is the combination of:
1. Sending full state updates at 30 FPS
2. Checking every hold for every hand position
3. Redundant coordinate transformations

Addressing these three issues alone should provide significant performance improvements. The spatial indexing optimization is particularly important as it will reduce the O(n) intersection checks to O(log n) or better.

Implementing the Phase 1 recommendations first will provide immediate relief with minimal code changes, while Phase 2 and 3 optimizations will provide more substantial long-term improvements.
