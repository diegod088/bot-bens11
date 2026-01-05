#!/bin/bash
echo "=== Probando endpoints de la MiniApp ==="
echo ""

# Endpoint 1: /api/miniapp/user
echo "1. POST /api/miniapp/user (con datos de prueba)"
curl -s -X POST http://127.0.0.1:5000/api/miniapp/user \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123456789}' | jq -r '.ok // .error // .'
echo ""

# Endpoint 2: /api/miniapp/stats
echo "2. GET /api/miniapp/stats?user_id=123456789"
curl -s "http://127.0.0.1:5000/api/miniapp/stats?user_id=123456789" | jq -r '.ok // .error // .'
echo ""

# Endpoint 3: /api/miniapp/downloads  
echo "3. GET /api/miniapp/downloads?user_id=123456789"
curl -s "http://127.0.0.1:5000/api/miniapp/downloads?user_id=123456789" | jq -r '.ok // .error // .'
echo ""

# Endpoint 4: /api/miniapp/referrals
echo "4. GET /api/miniapp/referrals?user_id=123456789"
curl -s "http://127.0.0.1:5000/api/miniapp/referrals?user_id=123456789" | jq -r '.ok // .error // .'
echo ""

# Endpoint 5: /api/miniapp/create-invoice
echo "5. POST /api/miniapp/create-invoice"
curl -s -X POST http://127.0.0.1:5000/api/miniapp/create-invoice \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123456789, "days": 7}' | jq -r '.ok // .error // .'
echo ""

echo "=== Pruebas completadas ==="
