#!/bin/bash

# Test script for error cases of the wall image upload API endpoint

API_URL="http://localhost:8000/api/upload-wall-image/"
WALL_ID="264d7633-65b2-41a8-92a4-34eb79a891bb"  # "Rdeče-kvadratna stena"

echo "=== Testing Error Cases for Wall Image Upload API ==="

# Test 1: Missing wall_id
echo ""
echo "Test 1: Missing wall_id"
PAYLOAD='{"image_data": "data:image/jpeg;base64,invalid"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$API_URL")
echo "Response: $RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Test 2: Missing image_data
echo ""
echo "Test 2: Missing image_data"
PAYLOAD="{\"wall_id\": \"$WALL_ID\"}"
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$API_URL")
echo "Response: $RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Test 3: Invalid wall_id
echo ""
echo "Test 3: Invalid wall_id"
PAYLOAD='{"wall_id": "invalid-uuid", "image_data": "data:image/jpeg;base64,invalid"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$API_URL")
echo "Response: $RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Test 4: Invalid image data
echo ""
echo "Test 4: Invalid image data"
PAYLOAD="{\"wall_id\": \"$WALL_ID\", \"image_data\": \"data:image/jpeg;base64,invalid-base64-data\"}"
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$API_URL")
echo "Response: $RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Test 5: Authentication required
echo ""
echo "Test 5: Authentication required"
IMAGE_BASE64=$(base64 -i "data/IMG_2568.jpeg" | head -c 100)  # Just a small part
PAYLOAD="{\"wall_id\": \"$WALL_ID\", \"image_data\": \"data:image/jpeg;base64,$IMAGE_BASE64\"}"
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$API_URL")
echo "Response: $RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""
echo "=== Error Case Tests Complete ==="