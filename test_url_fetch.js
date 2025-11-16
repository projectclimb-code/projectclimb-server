#!/usr/bin/env node

const https = require('https');
const http = require('http');

async function fetchCalibrationFromUrl(url) {
  return new Promise((resolve, reject) => {
    const protocol = url.startsWith('https://') ? https : http;
    
    const request = protocol.get(url, (response) => {
      let data = '';
      
      response.on('data', (chunk) => {
        data += chunk;
      });
      
      response.on('end', () => {
        try {
          const calibration = JSON.parse(data);
          resolve(calibration);
        } catch (error) {
          reject(new Error(`Failed to parse calibration JSON: ${error.message}`));
        }
      });
    });
    
    request.on('error', (error) => {
      reject(new Error(`Failed to fetch calibration: ${error.message}`));
    });
    
    request.setTimeout(10000, () => {
      request.destroy();
      reject(new Error('Calibration fetch timeout after 10 seconds'));
    });
  });
}

// Test the URL fetching
async function test() {
  try {
    console.log('Testing URL fetch with httpbin.org...');
    const calibration = await fetchCalibrationFromUrl('https://httpbin.org/json');
    console.log('Success! Fetched calibration:', JSON.stringify(calibration, null, 2));
  } catch (error) {
    console.error('Error:', error.message);
  }
}

test();