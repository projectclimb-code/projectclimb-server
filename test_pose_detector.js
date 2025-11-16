const WebSocket = require('ws');
const PoseDetector = require('./websocket_pose_detector.js');
const fs = require('fs');

// Mock WebSocket server for testing
class MockWebSocketServer {
    constructor(port) {
        this.port = port;
        this.wss = null;
        this.clients = [];
    }

    start() {
        this.wss = new WebSocket.Server({ port: this.port });
        
        this.wss.on('connection', (ws) => {
            this.clients.push(ws);
            console.log(`Mock server connected on port ${this.port}`);
            
            ws.on('close', () => {
                this.clients = this.clients.filter(client => client !== ws);
            });
        });
        
        return new Promise((resolve) => {
            setTimeout(resolve, 100); // Give server time to start
        });
    }

    stop() {
        if (this.wss) {
            this.wss.close();
        }
    }

    broadcast(data) {
        const message = typeof data === 'string' ? data : JSON.stringify(data);
        this.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(message);
            }
        });
    }
}

// Create sample SVG file for testing
function createSampleSvgFile() {
    const svgContent = `<?xml version="1.0" encoding="UTF-8"?>
<svg width="480" height="640" viewBox="0 0 480 640" xmlns="http://www.w3.org/2000/svg">
    <path id="hold_0" d="M 120 128 L 180 128 L 180 192 L 120 192 Z" fill="red" opacity="0.5"/>
    <path id="hold_1" d="M 240 128 L 300 128 L 300 192 L 240 192 Z" fill="blue" opacity="0.5"/>
    <path id="hold_2" d="M 360 128 L 420 128 L 420 192 L 360 192 Z" fill="green" opacity="0.5"/>
    <path id="hold_3" d="M 120 256 L 180 256 L 180 320 L 120 320 Z" fill="yellow" opacity="0.5"/>
    <path id="hold_101" d="M 240 256 L 300 256 L 300 320 L 240 320 Z" fill="purple" opacity="0.5"/>
</svg>`;
    
    fs.writeFileSync('test_wall.svg', svgContent);
    return 'test_wall.svg';
}

// Create sample session file for testing
function createSampleSessionFile() {
    const sessionData = {
        grade: "6a",
        author: "Test",
        problem: {
            holds: [
                { id: "0", type: "start" },
                { id: "1", type: "normal" },
                { id: "2", type: "normal" },
                { id: "3", type: "normal" },
                { id: "101", type: "finish" }
            ]
        }
    };
    
    fs.writeFileSync('test_session.json', JSON.stringify(sessionData));
    return 'test_session.json';
}

// Create sample pose data
function createSamplePoseData() {
    return {
        type: "pose",
        timestamp: Date.now(),
        width: 480,
        height: 640,
        landmarks: [
            // ... (33 landmarks, we'll create a simplified version)
            // Left wrist (landmark 15) - positioned near hold_0
            { x: 0.25, y: 0.2, z: 0, visibility: 0.9 },
            // Right wrist (landmark 16) - positioned near hold_101
            { x: 0.5, y: 0.35, z: 0, visibility: 0.9 }
        ]
    };
}

// Fill in the remaining landmarks
function createFullPoseData() {
    const basePose = createSamplePoseData();
    const fullLandmarks = [];
    
    // Add 33 landmarks (MediaPipe pose standard)
    for (let i = 0; i < 33; i++) {
        if (i === 15) {
            // Left wrist - positioned near hold_0 (120-180x128-192)
            fullLandmarks.push({ x: 0.25, y: 0.2, z: 0, visibility: 0.9 });
        } else if (i === 16) {
            // Right wrist - positioned near hold_101 (240-300x256-320)
            fullLandmarks.push({ x: 0.5, y: 0.4, z: 0, visibility: 0.9 });
        } else {
            // Other landmarks
            fullLandmarks.push({
                x: 0.5 + (Math.random() - 0.5) * 0.2,
                y: 0.5 + (Math.random() - 0.5) * 0.2,
                z: 0,
                visibility: 0.9
            });
        }
    }
    
    basePose.landmarks = fullLandmarks;
    return basePose;
}

async function runTest() {
    console.log('Starting pose detector test...');
    
    // Create test files
    const svgFile = createSampleSvgFile();
    const sessionFile = createSampleSessionFile();
    
    // Start mock servers
    const inputServer = new MockWebSocketServer(8080);
    const outputServer = new MockWebSocketServer(8081);
    
    // Capture output messages
    let outputMessages = [];
    
    await inputServer.start();
    await outputServer.start();
    
    // Set up message handler after server starts
    outputServer.wss.on('connection', (ws) => {
        ws.on('message', (data) => {
            try {
                const message = JSON.parse(data.toString());
                outputMessages.push(message);
                console.log('Received output message:', JSON.stringify(message, null, 2));
            } catch (error) {
                console.error('Error parsing output message:', error);
            }
        });
    });
    
    // Start pose detector
    const detector = new PoseDetector(
        'ws://localhost:8080',
        'ws://localhost:8081',
        svgFile,
        sessionFile
    );
    
    await detector.initialize();
    
    // Wait a bit for initialization
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Send test pose data
    console.log('Sending test pose data...');
    const poseData = createFullPoseData();
    inputServer.broadcast(poseData);
    
    // Send multiple pose data to simulate timing
    for (let i = 0; i < 5; i++) {
        await new Promise(resolve => setTimeout(resolve, 300));
        const newPoseData = createFullPoseData();
        newPoseData.timestamp = Date.now();
        inputServer.broadcast(newPoseData);
    }
    
    // Wait for processing
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Check results
    console.log(`\nTest Results:`);
    console.log(`- Output messages received: ${outputMessages.length}`);
    
    if (outputMessages.length > 0) {
        const lastMessage = outputMessages[outputMessages.length - 1];
        console.log(`- Holds in session: ${lastMessage.session.holds.length}`);
        
        const touchedHolds = lastMessage.session.holds.filter(hold => hold.status === 'touched');
        console.log(`- Holds touched: ${touchedHolds.length}`);
        
        touchedHolds.forEach(hold => {
            console.log(`  * ${hold.id}: ${hold.status} at ${hold.time}`);
        });
    }
    
    // Cleanup
    console.log('\nCleaning up...');
    detector.shutdown();
    inputServer.stop();
    outputServer.stop();
    
    // Remove test files
    try {
        fs.unlinkSync(svgFile);
        fs.unlinkSync(sessionFile);
    } catch (error) {
        console.log('Error cleaning up test files:', error.message);
    }
    
    console.log('Test completed!');
    process.exit(0);
}

// Run the test
if (require.main === module) {
    runTest().catch(error => {
        console.error('Test failed:', error);
        process.exit(1);
    });
}

module.exports = { runTest, MockWebSocketServer };