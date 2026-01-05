#!/bin/bash
USER_ID=624579068

echo "=== Probando endpoints con usuario real (ID: $USER_ID) ==="
echo ""

echo "1. GET /api/miniapp/referrals?user_id=$USER_ID"
curl -s "http://127.0.0.1:5000/api/miniapp/referrals?user_id=$USER_ID" | jq '.'
echo ""

echo "2. POST /api/miniapp/user"
curl -s -X POST http://127.0.0.1:5000/api/miniapp/user \
  -H "Content-Type: application/json" \
  -d "{\"user\": {\"id\": $USER_ID, \"first_name\": \"Eduardo\"}}" | jq '.'
echo ""

echo "3. POST /api/miniapp/configure"
curl -s -X POST http://127.0.0.1:5000/api/miniapp/configure \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": $USER_ID}" | jq '.'
echo ""

echo "=== Pruebas completadas ==="
