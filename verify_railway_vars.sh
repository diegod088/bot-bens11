#!/bin/bash
# Script de verificación para Railway
# Verifica que todas las variables de entorno necesarias estén configuradas

echo "🔍 Verificando Variables de Entorno para Railway..."
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contador de errores
errors=0

# Variables obligatorias
declare -a required_vars=(
    "TELEGRAM_BOT_TOKEN"
    "TELEGRAM_API_ID"
    "TELEGRAM_API_HASH"
    "ADMIN_TOKEN"
    "ADMIN_ID"
    "ENCRYPTION_KEY"
    "DASHBOARD_SECRET_KEY"
)

echo "Verificando variables obligatorias:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for var in "${required_vars[@]}"; do
    # Verificar en Railway
    if railway variables | grep -q "^$var"; then
        value=$(railway variables | grep "^$var" | awk '{print $2}')
        if [ -n "$value" ] && [ "$value" != "null" ]; then
            echo -e "${GREEN}✓${NC} $var está configurada"
        else
            echo -e "${RED}✗${NC} $var está vacía"
            ((errors++))
        fi
    else
        echo -e "${RED}✗${NC} $var NO está configurada"
        ((errors++))
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $errors -eq 0 ]; then
    echo -e "${GREEN}✅ Todas las variables están configuradas correctamente${NC}"
    echo ""
    echo "Puedes hacer deploy con:"
    echo "  railway up"
    exit 0
else
    echo -e "${RED}❌ Faltan $errors variable(s)${NC}"
    echo ""
    echo "Configura las variables faltantes con:"
    echo "  railway variables set NOMBRE_VARIABLE=valor"
    echo ""
    echo "O consulta: RAILWAY_VARIABLES.md"
    exit 1
fi
