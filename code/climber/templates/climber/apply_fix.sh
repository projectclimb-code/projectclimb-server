#!/bin/bash
set -e

# File paths
ORIGINAL_FILE="/Users/martin/Documents/Projects/ProjectClimb/projectclimb-server/code/climber/templates/climber/mock_climber.html"
BACKUP_FILE="${ORIGINAL_FILE}.backup2"
FIX_CONTENT="/Users/martin/Documents/Projects/ProjectClimb/projectclimb-server/code/climber/templates/climber/fix_content.txt"

echo "=== Applying SVG Visibility and Hand Tracking Fixes ==="

# Create incremental backup
if [ ! -f "$BACKUP_FILE" ]; then
    echo "1. Creating incremental backup..."
    cp -p "$ORIGINAL_FILE" "$BACKUP_FILE"
    echo "   Backup created: $BACKUP_FILE"
else
    echo "1. Backup file already exists"
fi

# Apply fixes from the generated fix content
echo "2. Applying fixes to mock_climber.html..."
cat > "$ORIGINAL_FILE" <<'INNER_EOF'
{% extends "base.html" %}
{% load static %}

{% block content %}
<div class="container mx-auto px-4 py-8">
    <div class="flex flex-col lg:flex-row gap-8">
        <!-- Sidebar Controls -->
        <div class="w-full lg:w-1/4 space-y-6">
            <div class="bg-white p-6 rounded-xl shadow-lg border border-gray-100">
                <h2 class="text-xl font-bold text-gray-800 mb-4 flex items-center">
                    <span class="mr-2">🎮</span> Mock Climber
                </h2>
                
                <div class="space-y-4">
                    <div class="flex items-center gap-2">
                        <input id="showSvgToggle" type="checkbox" class="w-4 h-4 text-blue-600 rounded focus:ring-blue-500" checked>
                        <label for="showSvgToggle" class="text-sm font-semibold text-gray-700">Show SVG Overlay</label>
                    </div>
                    <div class="pt-4 border-t border-gray-200">
                        <label for="svgOpacity" class="block text-sm font-medium text-gray-700 mb-2">
                            SVG Opacity: <span id="opacityValue">100%</span>
                        </label>
                        <input type="range" 
                               id="svgOpacity" 
                               min="0" 
                               max="100" 
                               value="100" 
                               class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                               oninput="updateOpacity(this.value)">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-600 mb-1">Pose Input WS</label>
                        <input id="inputWsUrl" type="text" class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" 
                               value="ws://localhost:8080/ws/pose/">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-600 mb-1">State Output WS</label>
                        <input id="outputWsUrl" type="text" class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" 
                               value="ws://localhost:8080/ws/holds/">
                    </div>
                    <div class="flex gap-2 pt-2">
                        <button id="connectBtn" class="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                            Connect
                        </button>
                        <button id="disconnectBtn" class="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold py-2 px-4 rounded-lg transition-colors">
                            Disconnect
                        </button>
                    </div>
                    <div id="status" class="text-xs font-mono p-2 bg-gray-50 rounded border text-center text-gray-500 italic">
                        Disconnected
                    </div>
                </div>
            </div>

            <div class="bg-white p-6 rounded-xl shadow-lg border border-gray-100">
                <h3 class="text-lg font-bold text-gray-800 mb-3">System State</h3>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Mode:</span>
                        <span id="stateMode" class="font-bold text-blue-600">--</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Route:</span>
                        <span id="stateRoute" class="font-bold text-gray-700">--</span>
                    </div>
                    <div class="pt-2">
                        <div id="stateText" class="text-xs italic text-gray-500 leading-tight">Waiting for data...</div>
                    </div>
                </div>
            </div>

            <div class="bg-white p-6 rounded-xl shadow-lg border border-gray-100">
                <h3 class="text-lg font-bold text-gray-800 mb-3">Landmark Legend</h3>
                <div class="space-y-3 text-xs">
                    <div class="flex items-center gap-2">
                        <div class="w-4 h-4 rounded-full bg-green-500 border-2 border-white flex items-center justify-center text-[8px] font-bold text-white shadow-sm">L</div>
                        <span class="text-gray-600 font-medium">Left Hand</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <div class="w-4 h-4 rounded-full bg-green-500 border-2 border-white flex items-center justify-center text-[8px] font-bold text-white shadow-sm">R</div>
                        <span class="text-gray-600 font-medium">Right Hand</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <div class="w-3 h-3 rounded-full bg-blue-500 opacity-60 border border-white"></div>
                        <span class="text-gray-600 font-medium">System Elbow</span>
                    </div>
                    <div class="flex items-center gap-2 pt-1 border-t border-gray-50">
                        <div class="w-3 h-3 rounded-full bg-yellow-400 opacity-40 animate-pulse border border-yellow-600"></div>
                        <span class="text-gray-500 italic">Detected Hold</span>
                    </div>
                </div>
            </div>

            <div class="bg-blue-50 p-4 rounded-lg border border-blue-100 text-xs text-blue-800">
                <p class="font-bold mb-1">Instructions:</p>
                <ul class="list-disc pl-4 space-y-1">
                    <li>Drag the green circles to move landmarks.</li>
                    <li>Move hands over wall holds/buttons to trigger system.</li>
                    <li>Yellow circles show detected touches (feedback).</li>
                </ul>
            </div>
        </div>

        <!-- Main Workspace -->
        <div class="w-full lg:w-3/4 flex flex-col items-center">
            <div id="wallContainer" class="relative group" style="max-width: 100%; aspect-ratio: {{ wall.wall_image.width }}/{{ wall.wall_image.height }};">
                <!-- Wall Image -->
                {% if wall.wall_image %}
                <img id="wallImage" src="{{ wall.wall_image.url }}" alt="{{ wall.name }}" class="w-full h-auto rounded-lg shadow-2xl border-4 border-white transition-opacity duration-300">
                {% else %}
                <div class="w-full aspect-video bg-gray-200 rounded-lg flex items-center justify-center text-gray-400">No Image Available</div>
                {% endif %}
                
                <!-- SVG Overlay (simple image tag approach like calibration page) -->
                {% if wall.svg_file %}
                <img id="svgOverlay" 
                     src="{{ wall.svg_file.url }}" 
                     alt="Wall SVG Overlay" 
                     class="absolute top-0 left-0 w-full h-full pointer-events-none opacity-100 transition-opacity duration-300"
                     style="transform-origin: 0 0;" />
                {% endif %}
                
                <!-- Interactive Layer for Landmarks -->
                <svg id="interactiveLayer" class="absolute top-0 left-0 w-full h-full" viewBox="0 0 {{ wall.wall_image.width|default:100 }} {{ wall.wall_image.height|default:100 }}" preserveAspectRatio="none">
                    <!-- Feedback layer (holds detected by system) -->
                    <g id="feedbackLayer"></g>
                    
                    <!-- Landmarks layer -->
                    <g id="landmarksLayer">
                        <!-- Draggable Points -->
                        <g>
                            <circle id="lm_15" cx="{{ wall.wall_image.width|default:100 * 0.45 }}" cy="{{ wall.wall_image.height|default:100 * 0.50 }}" r="10" class="fill-green-500 stroke-white stroke-2 cursor-move landmark-handle" data-id="15"></circle>
                            <text id="lbl_15" x="{{ wall.wall_image.width|default:100 * 0.45 }}" y="{{ wall.wall_image.height|default:100 * 0.50 }}" font-size="12" class="fill-white font-bold pointer-events-none text-shadow" text-anchor="middle" dominant-baseline="middle">L</text>
                        </g>

                        <g>
                            <circle id="lm_16" cx="{{ wall.wall_image.width|default:100 * 0.55 }}" cy="{{ wall.wall_image.height|default:100 * 0.50 }}" r="10" class="fill-green-500 stroke-white stroke-2 cursor-move landmark-handle" data-id="16"></circle>
                            <text id="lbl_16" x="{{ wall.wall_image.width|default:100 * 0.55 }}" y="{{ wall.wall_image.height|default:100 * 0.50 }}" font-size="12" class="fill-white font-bold pointer-events-none text-shadow" text-anchor="middle" dominant-baseline="middle">R</text>
                        </g>
                        
                        <!-- System Feedback Elbows -->
                        <circle id="sys_elbow_l" r="6" class="fill-blue-500 opacity-0 transition-opacity duration-300 pointer-events-none stroke-white stroke-1" cx="0" cy="0"></circle>
                        <circle id="sys_elbow_r" r="6" class="fill-blue-500 opacity-0 transition-opacity duration-300 pointer-events-none stroke-white stroke-1" cx="0" cy="0"></circle>
                    </g>
                </svg>
                
                <!-- Loading Overlay -->
                <div id="loadingOverlay" class="loading-overlay" style="display: none;">
                    <div class="loading-spinner"></div>
                </div>
            </div>
            
            <div class="mt-4 w-full flex justify-between items-center text-xs text-gray-400 px-2">
                <div>Wall: <span class="font-bold text-gray-600">{{ wall.name }}</span></div>
                <div id="lastPoseTime">Last Pose: --</div>
            </div>
        </div>
    </div>
</div>

<style>
    .landmark-handle:hover {
        filter: brightness(1.2);
        r: 12;
    }
    .landmark-handle.dragging {
        fill: #3b82f6 !important;
        r: 12;
    }
    #interactiveLayer {
        cursor: crosshair;
    }
    .feedback-highlight {
        fill: #facc15 !important;
        fill-opacity: 0.6 !important;
        stroke: #eab308 !important;
        stroke-width: 2px !important;
        filter: drop-shadow(0 0 5px #facc15);
    }
    .route-hold {
        stroke: #3b82f6 !important;
        stroke-width: 3px !important;
        stroke-opacity: 0.8 !important;
    }
    #interactiveLayer {
        overflow: visible;
    }
    .text-shadow {
        text-shadow: 0.5px 0.5px 1px rgba(0,0,0,0.5);
    }
    @keyframes pulse {
        0% { fill-opacity: 0.3; }
        50% { fill-opacity: 0.6; }
        100% { fill-opacity: 0.3; }
    }
    .loading-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(255, 255, 255, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        border-radius: 8px;
    }
    
    .loading-spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #3498db;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
</style>

<script>
    const wallId = {{ wall.id }};
    const wallWidth = {{ wall.wall_image.width|default:100 }};
    const wallHeight = {{ wall.wall_image.height|default:100 }};
    const inputWsUrlInput = document.getElementById('inputWsUrl');
    const outputWsUrlInput = document.getElementById('outputWsUrl');

    // Default to port 8011 for Docker environment
    if (inputWsUrlInput.value.includes(':8080')) {
        inputWsUrlInput.value = inputWsUrlInput.value.replace(':8080', ':8011');
    }
    if (outputWsUrlInput.value.includes(':8080')) {
        outputWsUrlInput.value = outputWsUrlInput.value.replace(':8080', ':8011');
    }

    const connectBtn = document.getElementById('connectBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const statusEl = document.getElementById('status');
    const svgLayer = document.getElementById('interactiveLayer');
    const landmarksLayer = document.getElementById('landmarksLayer');
    const feedbackLayer = document.getElementById('feedbackLayer');
    const showSvgToggle = document.getElementById('showSvgToggle');
    
    let inputWs = null;
    let outputWs = null;
    let draggingElement = null;
    
    // Mediapipe landmarks dictionary (normalized 0-1)
    const landmarks = {
        15: { x: 0.45, y: 0.50 }, // L Hand
        16: { x: 0.55, y: 0.50 }  // R Hand
    };

    // Initialize UI from landmarks
    function updateUIFromLandmarks() {
        Object.keys(landmarks).forEach(id => {
            const el = document.getElementById(`lm_${id}`);
            const lbl = document.getElementById(`lbl_${id}`);
            if (el) {
                el.setAttribute('cx', landmarks[id].x * wallWidth);
                el.setAttribute('cy', landmarks[id].y * wallHeight);
            }
            if (lbl) {
                lbl.setAttribute('x', landmarks[id].x * wallWidth);
                lbl.setAttribute('y', landmarks[id].y * wallHeight);
            }
        });
    }

    // Drag and Drop Logic
    svgLayer.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('landmark-handle')) {
            draggingElement = e.target;
            draggingElement.classList.add('dragging');
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!draggingElement) return;

        const rect = svgLayer.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;

        const id = draggingElement.getAttribute('data-id');
        landmarks[id] = { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) };
        
        updateUIFromLandmarks();
        sendPose();
    });

    window.addEventListener('mouseup', () => {
        if (draggingElement) {
            draggingElement.classList.remove('dragging');
            draggingElement = null;
        }
    });

    // WebSocket Emission
    function sendPose() {
        if (inputWs && inputWs.readyState === WebSocket.OPEN) {
            const hand_l = landmarks[15];
            const hand_r = landmarks[16];
            
            // Create a full array of 33 landmarks for MediaPipe compatibility
            const pose_landmarks = Array(33).fill(null).map((_, index) => ({
                id: index,
                x: 0,
                y: 0,
                z: 0,
                visibility: 0
            }));

            // Left hand landmarks (15: wrist, 17: pinky, 19: index, 21: thumb, 13: elbow)
            const leftIndices = [13, 15, 17, 19, 21];
            leftIndices.forEach(idx => {
                pose_landmarks[idx] = {
                    id: idx,
                    x: hand_l.x,
                    y: idx === 13 ? hand_l.y + 0.1 : hand_l.y, // Offset elbow slightly
                    visibility: 1.0
                };
            });

            // Right hand landmarks (16: wrist, 18: pinky, 20: index, 22: thumb, 14: elbow)
            const rightIndices = [14, 16, 18, 20, 22];
            rightIndices.forEach(idx => {
                pose_landmarks[idx] = {
                    id: idx,
                    x: hand_r.x,
                    y: idx === 14 ? hand_r.y + 0.1 : hand_r.y, // Offset elbow slightly
                    visibility: 1.0
                };
            });

            const data = {
                type: 'pose',
                timestamp: Date.now() / 1000,
                width: 100, // Use 100 because our mock coordinates are 0-100 percentages
                height: 100,
                landmarks: pose_landmarks
            };
            inputWs.send(JSON.stringify(data));
            lastPoseTimeEl.textContent = `Last Pose: ${new Date().toLocaleTimeString()}`;
        }
    }

    // WebSocket Management
    function setStatus(text, colorClass) {
        statusEl.textContent = text;
        statusEl.className = `text-xs font-mono p-2 bg-gray-50 rounded border text-center ${colorClass}`;
    }

    connectBtn.onclick = () => {
        const inUrl = inputWsUrlInput.value;
        const outUrl = outputWsUrlInput.value;
        
        setStatus('Connecting...', 'text-yellow-600');

        // Input Socket
        inputWs = new WebSocket(inUrl);
        inputWs.onopen = () => {
            sendPose();
            checkBothConnected();
        };
        inputWs.onclose = () => setStatus('Input WS Disconnected', 'text-red-500');
        inputWs.onerror = (e) => console.error('Input WS Error', e);

        // Output Socket
        outputWs = new WebSocket(outUrl);
        outputWs.onopen = () => checkBothConnected();
        outputWs.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.type === 'interactive_state') {
                handleStateUpdate(data);
            }
        };
        outputWs.onclose = () => setStatus('Output WS Disconnected', 'text-red-500');
        outputWs.onerror = (e) => console.error('Output WS Error', e);
    };

    function checkBothConnected() {
        if (inputWs?.readyState === WebSocket.OPEN && outputWs?.readyState === WebSocket.OPEN) {
            setStatus('Active & Connected', 'text-green-600 font-bold');
        }
    }

    disconnectBtn.onclick = () => {
        inputWs?.close();
        outputWs?.close();
        setStatus('Disconnected', 'text-gray-500');
    };

    function handleStateUpdate(data) {
        stateMode.textContent = data.mode?.toUpperCase() || 'NONE';
        stateRoute.textContent = data.route_name || '--';
        stateText.textContent = data.custom_text || '';

        // Reset previous highlights in the SVG
        const container = document.getElementById('wallSvgContainer');
        if (container) {
            container.querySelectorAll('.feedback-highlight, .route-hold').forEach(el => {
                el.classList.remove('feedback-highlight', 'route-hold');
            });
        }

        // 1. Highlight Route Holds (persistent)
        if (data.route_holds && container) {
            data.route_holds.forEach(holdId => {
                let el = container.getElementById(holdId);
                if (el) el.classList.add('route-hold');
            });
        }

        // 2. Highlight Touched Holds (temporary feedback)
        if (data.touched_holds && data.touched_holds.length > 0) {
            stateText.classList.add('text-blue-600', 'font-bold');
            if (container) {
                data.touched_holds.forEach(holdId => {
                    let el = container.getElementById(holdId);
                    if (el) el.classList.add('feedback-highlight');
                });
            }
        } else {
            stateText.classList.remove('text-blue-600', 'font-bold');
        }

        // Update elbows if present
        if (data.elbows) {
            const l = data.elbows.left_img || (data.elbows.left ? {x: data.elbows.left.x * wallWidth / (data.svg_width||1), y: data.elbows.left.y * wallHeight / (data.svg_height||1)} : null);
            const r = data.elbows.right_img || (data.elbows.right ? {x: data.elbows.right.x * wallWidth / (data.svg_width||1), y: data.elbows.right.y * wallHeight / (data.svg_height||1)} : null);
            updateSystemElbow('sys_elbow_l', l);
            updateSystemElbow('sys_elbow_r', r);
        }
    }

    function updateSystemElbow(id, pos) {
        const el = document.getElementById(id);
        const label = document.getElementById(id + '_label');
        if (!el) return;
        
        if (pos) {
            el.setAttribute('cx', pos.x);
            el.setAttribute('cy', pos.y);
            el.classList.remove('opacity-0');
            el.classList.add('opacity-60');
            if (label) {
                label.setAttribute('x', pos.x);
                label.setAttribute('y', pos.y);
                label.classList.remove('opacity-0');
                label.classList.add('opacity-100');
            }
        } else {
            el.classList.add('opacity-0');
            el.classList.remove('opacity-60');
            if (label) {
                label.classList.add('opacity-0');
                label.classList.remove('opacity-100');
            }
        }
    }

    // Calibration data from Django context
    const calibrationInv = {% if perspective_transform_inv %}{{ perspective_transform_inv|safe }}{% else %}null{% endif %};
    const wallImage = document.getElementById('wallImage');
    const wallWidthOrig = {{ wall.wall_image.width|default:100 }};

    function applyCalibration() {
        console.log('applyCalibration called');
        if (!calibrationInv) {
            console.log('No calibrationInv');
            return;
        }
        
        const svgOverlay = document.getElementById('svgOverlay');
        if (!svgOverlay) {
            console.log('No svgOverlay');
            return;
        }
        
        const h11 = calibrationInv[0][0], h12 = calibrationInv[0][1], h13 = calibrationInv[0][2];
        const h21 = calibrationInv[1][0], h22 = calibrationInv[1][1], h23 = calibrationInv[1][2];
        const h31 = calibrationInv[2][0], h32 = calibrationInv[2][1]; // h33 is 1
        
        // Build CSS matrix3d in COLUMN-MAJOR order
        const cssMatrix = [
            h11, h21, 0, h31,
            h12, h22, 0, h32,
            0, 0, 1, 0,
            h13, h23, 0, 1
        ];
        
        svgOverlay.style.transform = `matrix3d(${cssMatrix.map(n => Number.isFinite(n) ? n : 0).join(',')})`;
        svgOverlay.style.transformOrigin = '0 0';
        console.log('Transformation applied:', cssMatrix);
        console.log('Calibration applied successfully');
    }

    function updateOpacity(value) {
        const svgOverlay = document.getElementById('svgOverlay');
        if (svgOverlay) {
            const opacity = value / 100;
            svgOverlay.style.opacity = opacity;
            document.getElementById('opacityValue').textContent = `${value}%`;
        }
    }

    if (wallImage) {
        window.addEventListener('resize', applyCalibration);
        wallImage.onload = applyCalibration;
    }

    showSvgToggle.onchange = (e) => {
        console.log('SVG toggle changed:', e.target.checked);
        const svgOverlay = document.getElementById('svgOverlay');
        if (!svgOverlay) {
            console.log('No svgOverlay');
            return;
        }
        
        if (e.target.checked) {
            svgOverlay.classList.remove('opacity-0');
            svgOverlay.classList.add('opacity-100');
            svgOverlay.classList.remove('pointer-events-none');
            applyCalibration();
        } else {
            svgOverlay.classList.add('opacity-0');
            svgOverlay.classList.remove('opacity-100');
            svgOverlay.classList.add('pointer-events-none');
        }
    };
    
    // System State Elements
    const stateMode = document.getElementById('stateMode');
    const stateRoute = document.getElementById('stateRoute');
    const stateText = document.getElementById('stateText');
    const lastPoseTimeEl = document.getElementById('lastPoseTime');

    // Initial setup
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded event listener called');
        
        // Show loading indicator while page initializes
        const loadingOverlay = document.getElementById('loadingOverlay');
        loadingOverlay.style.display = 'flex';
        
        updateUIFromLandmarks();
        
        // Apply calibration after a short delay (comment out to test without calibration)
        /*
        setTimeout(() => {
            if (showSvgToggle.checked) {
                applyCalibration();
            }
            loadingOverlay.style.display = 'none';
        }, 500);
        */
        loadingOverlay.style.display = 'none';
    });
</script>
{% endblock %}
INNER_EOF

echo "3. Fixes applied successfully!"

echo "
Changes made:
- Increased SVG opacity from 50% to 100%
- Removed mix-blend-mode: multiply to make SVG opaque
- Changed interactive layer viewBox to actual wall dimensions
- Updated hand landmark initial positions to use pixel coordinates
- Modified updateUIFromLandmarks() to use wall dimensions
- Commented out calibration application to test without calibration

Please test the fixes by reloading the page:
http://localhost:8000/walls/264d7633-65b2-41a8-92a4-34eb79a891bb/mock-climber/
"
