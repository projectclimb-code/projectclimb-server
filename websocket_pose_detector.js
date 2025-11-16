const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

class PoseDetector {
    constructor(inputWsUrl, outputWsUrl, svgFilePath, sessionFilePath) {
        this.inputWsUrl = inputWsUrl;
        this.outputWsUrl = outputWsUrl;
        this.svgFilePath = svgFilePath;
        this.sessionFilePath = sessionFilePath;
        this.inputWs = null;
        this.outputWs = null;
        this.svgPaths = [];
        this.sessionData = null;
        this.holdStatus = new Map(); // Track hold touch status
        this.touchStartTime = new Map(); // Track when holds were first touched
        this.requiredTouchTime = 1000; // 1 second in milliseconds
        
        // MediaPipe pose landmark indices for wrists
        this.LEFT_WRIST = 15;
        this.RIGHT_WRIST = 16;
    }

    async initialize() {
        try {
            // Load and parse SVG file
            await this.loadSvgPaths();
            
            // Load session data
            await this.loadSessionData();
            
            // Initialize hold status from session data
            this.initializeHoldStatus();
            
            // Connect to WebSockets
            this.connectWebSockets();
            
            console.log('Pose detector initialized successfully');
        } catch (error) {
            console.error('Failed to initialize pose detector:', error);
            process.exit(1);
        }
    }

    async loadSvgPaths() {
        try {
            const svgContent = fs.readFileSync(this.svgFilePath, 'utf8');
            this.svgPaths = this.parseSvgPaths(svgContent);
            this.svgDimensions = this.parseSvgDimensions(svgContent);
            console.log(`Loaded ${this.svgPaths.length} SVG paths`);
            console.log(`SVG dimensions: ${this.svgDimensions.width}x${this.svgDimensions.height}`);
        } catch (error) {
            throw new Error(`Failed to load SVG file: ${error.message}`);
        }
    }

    parseSvgPaths(svgContent) {
        const paths = [];
        const pathRegex = /<path[^>]*id="([^"]*)"[^>]*d="([^"]*)"[^>]*>/g;
        let match;
        
        while ((match = pathRegex.exec(svgContent)) !== null) {
            const [, id, d] = match;
            paths.push({
                id: id,
                pathData: d,
                points: this.parsePathData(d)
            });
        }
        
        return paths;
    }

    parseSvgDimensions(svgContent) {
        // Extract SVG dimensions from viewBox or width/height attributes
        const viewBoxMatch = svgContent.match(/viewBox="([^"]*)"/);
        const widthMatch = svgContent.match(/width="([^"]*)"/);
        const heightMatch = svgContent.match(/height="([^"]*)"/);
        
        let width, height, viewBoxX = 0, viewBoxY = 0;
        
        if (viewBoxMatch) {
            const [, x, y, w, h] = viewBoxMatch[1].split(' ').map(Number);
            width = w;
            height = h;
            viewBoxX = x;
            viewBoxY = y;
            console.log(`Found viewBox: ${x} ${y} ${w} ${h}`);
        } else if (widthMatch && heightMatch) {
            width = parseFloat(widthMatch[1]);
            height = parseFloat(heightMatch[1]);
            console.log(`Found width/height: ${width} ${height}`);
        } else {
            // Default dimensions
            width = 2500;
            height = 3330;
            console.log('Using default dimensions: 2500x3330');
        }
        
        return { width, height, viewBoxX, viewBoxY };
    }

    parsePathData(pathData) {
        // Simple path parser for basic SVG path commands
        const points = [];
        const commands = pathData.match(/[MmLlHhVvCcSsQqTtAaZz][^MmLlHhVvCcSsQqTtAaZz]*/g) || [];
        
        let currentX = 0, currentY = 0;
        
        commands.forEach(command => {
            const type = command[0];
            const coords = command.slice(1).trim().split(/[\s,]+/).map(Number);
            
            switch (type.toUpperCase()) {
                case 'M': // Move to
                    if (coords.length >= 2) {
                        currentX = type === 'M' ? coords[0] : currentX + coords[0];
                        currentY = type === 'M' ? coords[1] : currentY + coords[1];
                        points.push({ x: currentX, y: currentY });
                    }
                    break;
                case 'L': // Line to
                    if (coords.length >= 2) {
                        currentX = type === 'L' ? coords[0] : currentX + coords[0];
                        currentY = type === 'L' ? coords[1] : currentY + coords[1];
                        points.push({ x: currentX, y: currentY });
                    }
                    break;
                case 'Z': // Close path
                    if (points.length > 0) {
                        points.push({ x: points[0].x, y: points[0].y });
                    }
                    break;
            }
        });
        
        return points;
    }

    async loadSessionData() {
        try {
            const sessionContent = fs.readFileSync(this.sessionFilePath, 'utf8');
            this.sessionData = JSON.parse(sessionContent);
            console.log('Session data loaded successfully');
        } catch (error) {
            throw new Error(`Failed to load session file: ${error.message}`);
        }
    }

    initializeHoldStatus() {
        if (!this.sessionData || !this.sessionData.problem || !this.sessionData.problem.holds) {
            throw new Error('Invalid session data structure');
        }
        
        this.sessionData.problem.holds.forEach(hold => {
            const holdId = `hold_${hold.id}`;
            this.holdStatus.set(holdId, {
                id: holdId,
                type: hold.type,
                status: 'untouched',
                time: null
            });
            this.touchStartTime.set(holdId, null);
        });
        
        console.log(`Initialized ${this.holdStatus.size} holds`);
    }

    connectWebSockets() {
        // Connect to input WebSocket
        this.inputWs = new WebSocket(this.inputWsUrl);
        
        this.inputWs.on('open', () => {
            console.log('Connected to input WebSocket');
        });
        
        this.inputWs.on('message', (data) => {
            try {
                const poseData = JSON.parse(data.toString());
                this.processPoseData(poseData);
            } catch (error) {
                console.error('Error processing pose data:', error);
            }
        });
        
        this.inputWs.on('error', (error) => {
            console.error('Input WebSocket error:', error);
        });
        
        this.inputWs.on('close', () => {
            console.log('Input WebSocket connection closed');
            // Attempt to reconnect after 5 seconds
            setTimeout(() => this.connectWebSockets(), 5000);
        });
        
        // Connect to output WebSocket
        this.outputWs = new WebSocket(this.outputWsUrl);
        
        this.outputWs.on('open', () => {
            console.log('Connected to output WebSocket');
        });
        
        this.outputWs.on('error', (error) => {
            console.error('Output WebSocket error:', error);
        });
        
        this.outputWs.on('close', () => {
            console.log('Output WebSocket connection closed');
            // Attempt to reconnect after 5 seconds
            setTimeout(() => this.connectWebSockets(), 5000);
        });
    }

    processPoseData(poseData) {
        if (!poseData.landmarks || poseData.landmarks.length < 17) {
            console.warn('Invalid pose data: insufficient landmarks');
            return;
        }
        
        const timestamp = poseData.timestamp || Date.now();
        this.imageWidth = poseData.width || 480;
        this.imageHeight = poseData.height || 640;
        
        // Get left and right wrist positions
        const leftWrist = poseData.landmarks[this.LEFT_WRIST];
        const rightWrist = poseData.landmarks[this.RIGHT_WRIST];
        
        if (!leftWrist || !rightWrist) {
            console.warn('Wrist landmarks not found');
            return;
        }
        
        // Convert normalized coordinates to SVG coordinate system
        const leftWristSvg = this.normalizeToSvgCoordinates(leftWrist, this.imageWidth, this.imageHeight);
        const rightWristSvg = this.normalizeToSvgCoordinates(rightWrist, this.imageWidth, this.imageHeight);
        
        // Check which holds are being touched
        this.updateHoldTouches(leftWristSvg, rightWristSvg, timestamp);
        
        // Generate and send output
        this.sendOutput(timestamp, poseData.landmarks);
    }

    normalizeToSvgCoordinates(landmark, imageWidth, imageHeight) {
        // Convert normalized coordinates (0-1) to SVG coordinate system
        const svgX = (landmark.x * imageWidth);
        const svgY = (landmark.y * imageHeight);
        
        return {
            x: svgX,
            y: svgY
        };
    }

    updateHoldTouches(leftWrist, rightWrist, timestamp) {
        const currentTime = timestamp;
        
        // Scale SVG coordinates to match image dimensions
        const scaleX = this.svgDimensions.width / (this.imageWidth || 480);
        const scaleY = this.svgDimensions.height / (this.imageHeight || 640);
        
        this.svgPaths.forEach(svgPath => {
            const holdId = svgPath.id;
            if (!this.holdStatus.has(holdId)) {
                return; // Skip if not in session holds
            }
            
            // Scale SVG path points to image coordinate system
            const scaledPathPoints = svgPath.points.map(point => ({
                x: (point.x - this.svgDimensions.viewBoxX) * scaleX,
                y: (point.y - this.svgDimensions.viewBoxY) * scaleY
            }));
            
            const isLeftTouching = this.isPointInPath(leftWrist, scaledPathPoints);
            const isRightTouching = this.isPointInPath(rightWrist, scaledPathPoints);
            const isTouching = isLeftTouching || isRightTouching;
            
            const holdStatus = this.holdStatus.get(holdId);
            const touchStartTime = this.touchStartTime.get(holdId);
            
            if (isTouching) {
                if (touchStartTime === null) {
                    // Just started touching
                    this.touchStartTime.set(holdId, currentTime);
                } else if (currentTime - touchStartTime >= this.requiredTouchTime) {
                    // Has been touching for required time
                    if (holdStatus.status === 'untouched') {
                        holdStatus.status = 'touched';
                        holdStatus.time = new Date(currentTime).toISOString();
                        console.log(`Hold ${holdId} touched at ${holdStatus.time}`);
                    }
                }
            } else {
                // Not touching anymore
                this.touchStartTime.set(holdId, null);
            }
        });
    }

    isPointInPath(point, pathPoints) {
        if (pathPoints.length < 3) {
            return false;
        }
        
        // Ray casting algorithm for point in polygon
        let inside = false;
        const x = point.x;
        const y = point.y;
        
        for (let i = 0, j = pathPoints.length - 1; i < pathPoints.length; j = i++) {
            const xi = pathPoints[i].x;
            const yi = pathPoints[i].y;
            const xj = pathPoints[j].x;
            const yj = pathPoints[j].y;
            
            const intersect = ((yi > y) !== (yj > y))
                && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        
        return inside;
    }

    sendOutput(timestamp, landmarks) {
        if (!this.outputWs || this.outputWs.readyState !== WebSocket.OPEN) {
            console.warn('Output WebSocket not ready');
            return;
        }
        
        const output = {
            session: {
                holds: Array.from(this.holdStatus.values()),
                startTime: this.sessionData ? this.sessionData.startTime || new Date().toISOString() : new Date().toISOString(),
                endTime: null,
                status: 'started'
            },
            pose: landmarks
        };
        
        try {
            this.outputWs.send(JSON.stringify(output));
            //console.log(output)
        } catch (error) {
            console.error('Error sending output:', error);
        }
    }

    // Graceful shutdown
    shutdown() {
        console.log('Shutting down pose detector...');
        if (this.inputWs) {
            this.inputWs.close();
        }
        if (this.outputWs) {
            this.outputWs.close();
        }
    }
}

// Command line usage
if (require.main === module) {
    const args = process.argv.slice(2);
    
    if (args.length < 4) {
        console.log('Usage: node websocket_pose_detector.js <input_ws_url> <output_ws_url> <svg_file_path> <session_file_path>');
        console.log('Example: node websocket_pose_detector.js ws://localhost:8080/input ws://localhost:8081/output ./wall.svg ./session.json');
        process.exit(1);
    }
    
    const [inputWsUrl, outputWsUrl, svgFilePath, sessionFilePath] = args;
    
    const detector = new PoseDetector(inputWsUrl, outputWsUrl, svgFilePath, sessionFilePath);
    
    // Handle graceful shutdown
    process.on('SIGINT', () => {
        detector.shutdown();
        process.exit(0);
    });
    
    process.on('SIGTERM', () => {
        detector.shutdown();
        process.exit(0);
    });
    
    // Initialize and start
    detector.initialize().catch(error => {
        console.error('Failed to start pose detector:', error);
        process.exit(1);
    });
}

module.exports = PoseDetector;