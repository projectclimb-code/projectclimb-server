# Wall Image Upload API Endpoint

## Overview
This API endpoint allows authenticated users to upload a base64 encoded image and associate it with a wall in the climber.models.

## Endpoint Details
- **URL**: `/api/upload-wall-image/`
- **Method**: POST
- **Authentication**: Required (IsAuthenticated)
- **Content-Type**: application/json

## Request Payload
```json
{
    "wall_id": "uuid-of-the-wall",
    "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ..."
}
```

### Parameters
- `wall_id` (required): UUID of the wall to associate the image with
- `image_data` (required): Base64 encoded image data with data URL prefix

## Response

### Success Response (200 OK)
```json
{
    "success": true,
    "message": "Wall image uploaded successfully",
    "wall_id": "uuid-of-the-wall",
    "image_url": "/media/wall_images/wall_image_uuid.jpg"
}
```

### Error Responses

#### Missing Parameters (400 Bad Request)
```json
{
    "success": false,
    "error": "Both wall_id and image_data are required"
}
```

#### Wall Not Found (404 Not Found)
```json
{
    "success": false,
    "error": "Wall with ID uuid-not-found not found"
}
```

#### Invalid Image Data (400 Bad Request)
```json
{
    "success": false,
    "error": "Error processing image: [error details]"
}
```

#### Authentication Required (403 Forbidden)
```json
{
    "detail": "Authentication credentials were not provided."
}
```

## Implementation Details

### Image Processing
1. The endpoint accepts base64 encoded image data with or without data URL prefix
2. Images are automatically converted to RGB format for JPEG compatibility
3. Images are saved as JPEG with 85% quality
4. The image is stored in the `wall.wall_image` field with upload path `wall_images/`

### File Naming
- Uploaded images are named using the pattern: `wall_image_{wall_uuid}.jpg`
- This ensures unique filenames for each wall

### Security
- Endpoint requires authentication
- Image data is validated before processing
- Only JPEG, PNG, and WebP formats are supported (via PIL processing)

## Usage Example

### JavaScript/Fetch
```javascript
const wallId = 'your-wall-uuid';
const imageFile = document.getElementById('image-input').files[0];

const reader = new FileReader();
reader.onload = function(e) {
    const imageData = e.target.result;
    
    fetch('/api/upload-wall-image/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') // If using Django CSRF
        },
        body: JSON.stringify({
            wall_id: wallId,
            image_data: imageData
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Image uploaded successfully:', data.image_url);
        } else {
            console.error('Upload failed:', data.error);
        }
    });
};

reader.readAsDataURL(imageFile);
```

### Python/Requests
```python
import base64
import requests

# Read and encode image
with open('path/to/image.jpg', 'rb') as f:
    image_data = base64.b64encode(f.read()).decode('utf-8')

# Prepare payload
payload = {
    'wall_id': 'your-wall-uuid',
    'image_data': f'data:image/jpeg;base64,{image_data}'
}

# Make request (with authentication)
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your-token'  # Or use session auth
}

response = requests.post(
    'http://localhost:8000/api/upload-wall-image/',
    json=payload,
    headers=headers
)

result = response.json()
if result.get('success'):
    print(f"Image uploaded: {result['image_url']}")
else:
    print(f"Error: {result.get('error')}")
```

## Testing
Two test scripts are provided:
1. `test_api_simple.sh` - Tests successful upload
2. `test_api_error_cases.sh` - Tests error conditions

Run tests with:
```bash
cd code
./test_api_simple.sh
./test_api_error_cases.sh