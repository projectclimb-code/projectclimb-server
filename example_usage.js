#!/usr/bin/env node

const PoseDetector = require('./websocket_pose_detector.js');

// Example usage with the provided files
async function runExample() {
    console.log('Starting WebSocket Pose Detector Example...');
    
    // Configuration
    const inputWsUrl = 'ws://localhost:8080/input';  // Replace with your input WebSocket URL
    const outputWsUrl = 'ws://localhost:8081/output'; // Replace with your output WebSocket URL
    const svgFilePath = './code/data/2025-11-16_wall.svg'; // Path to your SVG file
    const sessionFilePath = './session.json'; // Path to your session file
    
    // Create and initialize the detector
    const detector = new PoseDetector(
        inputWsUrl,
        outputWsUrl,
        svgFilePath,
        sessionFilePath
    );
    
    try {
        await detector.initialize();
        console.log('Pose detector started successfully!');
        console.log('Listening for pose data on:', inputWsUrl);
        console.log('Sending session data to:', outputWsUrl);
        console.log('Press Ctrl+C to stop');
        
        // Keep the process running
        process.on('SIGINT', () => {
            console.log('\nShutting down...');
            detector.shutdown();
            process.exit(0);
        });
        
        process.on('SIGTERM', () => {
            console.log('\nShutting down...');
            detector.shutdown();
            process.exit(0);
        });
        
    } catch (error) {
        console.error('Failed to start pose detector:', error);
        process.exit(1);
    }
}

// Run the example
if (require.main === module) {
    runExample();
}

module.exports = { runExample };