// JavaScript example to call start_default_task API endpoint with route_id=90
//
// This example demonstrates how to call the start_default_task API endpoint
// The correct URL is: /api/tasks/start-default/
//
// Required parameter: route_id (must be a valid route ID from your database)
// Optional parameters: debug, proximity_threshold, touch_duration, etc.

// Method 1: Using fetch API
async function startTaskWithRoute90() {
    try {
        const response = await fetch('/api/tasks/start-default/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken() // You'll need to implement this function
            },
            body: JSON.stringify({
                route_id: 90
                // You can also add other parameters if needed
                // debug: true,
                // proximity_threshold: 30.0,
                // touch_duration: 1.5
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('✅ Task started successfully!');
            console.log('Task ID:', data.task_id);
            console.log('Parameters used:', data.parameters);
        } else {
            console.error('❌ Error starting task:', data.message);
        }
    } catch (error) {
        console.error('❌ Exception:', error);
    }
}

// Method 2: Using the existing form on the page
function startTaskWithRoute90UsingForm() {
    // Set the route_id to 90 in the form
    const routeSelect = document.getElementById('tracker_route_id');
    if (routeSelect) {
        routeSelect.value = '90';
    }
    
    // Optionally set other parameters
    const debugCheckbox = document.getElementById('tracker_debug');
    if (debugCheckbox) {
        debugCheckbox.checked = true; // Enable debug
    }
    
    const proximityInput = document.getElementById('tracker_proximity');
    if (proximityInput) {
        proximityInput.value = '30.0'; // Custom proximity threshold
    }
    
    // Submit the form
    const form = document.getElementById('websocket-tracker-form');
    if (form) {
        form.dispatchEvent(new Event('submit'));
    }
}

// Helper function to get CSRF token (you may need to adjust based on your template)
function getCsrfToken() {
    const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
    return tokenElement ? tokenElement.value : '';
}

// Usage examples:
// 1. Call directly: startTaskWithRoute90();
// 2. Use existing form: startTaskWithRoute90UsingForm();

// For testing in browser console:
// startTaskWithRoute90();