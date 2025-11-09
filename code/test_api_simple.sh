#!/bin/bash

# Simple test script for the wall image upload API endpoint
# This script tests the endpoint with a base64 encoded image

API_URL="http://localhost:8000/api/upload-wall-image/"
WALL_ID="264d7633-65b2-41a8-92a4-34eb79a891bb"  # "Rdeče-kvadratna stena"
IMAGE_PATH="data/IMG_2568.jpeg"

echo "=== Testing Wall Image Upload API Endpoint ==="
echo "API URL: $API_URL"
echo "Wall ID: $WALL_ID"
echo "Image Path: $IMAGE_PATH"

# Check if image exists
if [ ! -f "$IMAGE_PATH" ]; then
    echo "Error: Test image not found at $IMAGE_PATH"
    echo "Please update the IMAGE_PATH variable to point to an existing image file."
    exit 1
fi

# Convert image to base64
echo "Converting image to base64..."
IMAGE_BASE64=$(base64 -i "$IMAGE_PATH")

# Create JSON payload
PAYLOAD=$(cat <<EOF
{
    "wall_id": "$WALL_ID",
    "image_data": "data:image/jpeg;base64,$IMAGE_BASE64"
}
EOF
)

echo "Making API request..."
echo "Payload size: ${#PAYLOAD} characters"

# Make the API request (without authentication for now)
RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$API_URL")

echo "Response Status: $?"
echo "Response Content:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""
echo "=== Test Complete ==="