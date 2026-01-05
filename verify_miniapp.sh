#!/bin/bash

echo "🔍 VERIFICACIÓN COMPLETA DE LA MINIAPP"
echo "======================================"
echo ""

# 1. Verificar que todos los tabs existen
echo "✅ Verificando estructura HTML de la MiniApp..."
TABS=$(grep -c 'id="tab-' miniapp/index.html)
echo "   - Tabs encontrados: $TABS (esperados: 4)"

# 2. Verificar funciones JavaScript críticas
echo ""
echo "✅ Verificando funciones JavaScript..."
for func in "loadUserData" "loadReferralStats" "switchTab" "copyReferralLink" "shareReferralLink" "requestDownload" "configureAccount" "buyPremium"; do
    if grep -q "function $func" miniapp/index.html || grep -q "const $func" miniapp/index.html; then
        echo "   ✓ $func"
    else
        echo "   ✗ $func - FALTA"
    fi
done

# 3. Verificar endpoints en dashboard.py
echo ""
echo "✅ Verificando endpoints API en dashboard.py..."
for endpoint in "/api/miniapp/user" "/api/miniapp/stats" "/api/miniapp/referrals" "/api/miniapp/download" "/api/miniapp/configure" "/api/miniapp/disconnect" "/api/miniapp/create-invoice"; do
    if grep -q "@app.route('$endpoint'" dashboard.py; then
        echo "   ✓ $endpoint"
    else
        echo "   ✗ $endpoint - FALTA"
    fi
done

# 4. Test endpoints en vivo
echo ""
echo "✅ Probando endpoints en vivo..."
USER_ID=624579068

# Test user endpoint
RESPONSE=$(curl -s -X POST http://127.0.0.1:5000/api/miniapp/user \
  -H "Content-Type: application/json" \
  -d "{\"user\": {\"id\": $USER_ID}}")
if echo "$RESPONSE" | jq -e '.user_id' > /dev/null 2>&1; then
    echo "   ✓ POST /api/miniapp/user - Funciona"
else
    echo "   ✗ POST /api/miniapp/user - Error: $RESPONSE"
fi

# Test referrals endpoint
RESPONSE=$(curl -s "http://127.0.0.1:5000/api/miniapp/referrals?user_id=$USER_ID")
if echo "$RESPONSE" | jq -e '.ok' > /dev/null 2>&1; then
    echo "   ✓ GET /api/miniapp/referrals - Funciona"
    LINK=$(echo "$RESPONSE" | jq -r '.referral_link')
    echo "     Link: $LINK"
else
    echo "   ✗ GET /api/miniapp/referrals - Error"
fi

# Test stats endpoint
RESPONSE=$(curl -s "http://127.0.0.1:5000/api/miniapp/stats")
if echo "$RESPONSE" | jq -e '.total_users' > /dev/null 2>&1; then
    USERS=$(echo "$RESPONSE" | jq -r '.total_users')
    echo "   ✓ GET /api/miniapp/stats - Funciona ($USERS usuarios)"
else
    echo "   ✗ GET /api/miniapp/stats - Error"
fi

# Test invoice endpoint
RESPONSE=$(curl -s -X POST http://127.0.0.1:5000/api/miniapp/create-invoice \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": $USER_ID, \"days\": 7}")
if echo "$RESPONSE" | jq -e '.ok // .invoice_link' > /dev/null 2>&1; then
    echo "   ✓ POST /api/miniapp/create-invoice - Funciona"
else
    echo "   ✗ POST /api/miniapp/create-invoice - Error"
fi

echo ""
echo "======================================"
echo "✨ Verificación completada"
echo ""
echo "🌐 MiniApp URL: https://seizable-maile-nonencyclopaedic.ngrok-free.dev/miniapp"
echo "📱 Puedes probarla en Telegram"
echo ""

