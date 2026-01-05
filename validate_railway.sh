#!/bin/bash

# 🧪 VALIDAR RAILWAY SETUP
# Este script verifica que todo esté listo para deployer en Railway

echo "🚂 VALIDANDO SETUP PARA RAILWAY"
echo "=================================="
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

# Función para validar archivo
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1 existe"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC} $1 NO existe"
        ((FAILED++))
    fi
}

# Función para validar contenido
check_content() {
    if grep -q "$2" "$1" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} $1 contiene '$2'"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC} $1 NO contiene '$2'"
        ((FAILED++))
    fi
}

echo "📋 ARCHIVOS REQUERIDOS:"
echo ""

check_file "Dockerfile"
check_file "requirements.txt"
check_file "railway_start.py"
check_file ".railway.json"
check_file "bot_with_paywall.py"
check_file "dashboard.py"
check_file "database.py"

echo ""
echo "📦 CONTENIDO CRÍTICO:"
echo ""

check_content "requirements.txt" "python-telegram-bot"
check_content "requirements.txt" "Flask"
check_content "requirements.txt" "waitress"
check_content "Dockerfile" "python:3.10"
check_content "Procfile" "railway_start.py"
check_content ".railway.json" "DOCKERFILE"
check_content "railway_start.py" "run_dashboard"
check_content "railway_start.py" "run_bot"

echo ""
echo "🌐 CARPETAS:"
echo ""

if [ -d "templates" ]; then
    echo -e "${GREEN}✅${NC} templates/ existe"
    ((PASSED++))
else
    echo -e "${RED}❌${NC} templates/ NO existe"
    ((FAILED++))
fi

if [ -d "miniapp" ]; then
    echo -e "${GREEN}✅${NC} miniapp/ existe"
    ((PASSED++))
else
    echo -e "${RED}❌${NC} miniapp/ NO existe"
    ((FAILED++))
fi

echo ""
echo "🐍 PYTHON SETUP:"
echo ""

if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✅${NC} Python: $VERSION"
    ((PASSED++))
else
    echo -e "${RED}❌${NC} Python NO instalado"
    ((FAILED++))
fi

if [ -f ".env" ]; then
    echo -e "${YELLOW}ℹ️${NC} .env existe (no necesario para Railway)"
else
    echo -e "${YELLOW}ℹ️${NC} .env NO existe (OK para Railway)"
fi

echo ""
echo "📚 DOCUMENTACIÓN:"
echo ""

check_file "RAILWAY_PASO_A_PASO.md"
check_file "VARIABLES_RAILWAY.md"
check_file "RAILWAY_CHECKLIST.md"
check_file "RAILWAY_GUIA_COMPLETA.md"

echo ""
echo "=================================="
echo "📊 RESULTADOS:"
echo ""
echo -e "${GREEN}✅ PASADAS: $PASSED${NC}"
echo -e "${RED}❌ FALLIDAS: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ¡TODO ESTÁ LISTO PARA RAILWAY!${NC}"
    echo ""
    echo "Próximos pasos:"
    echo "1. Lee: RAILWAY_PASO_A_PASO.md"
    echo "2. Obtén variables: VARIABLES_RAILWAY.md"
    echo "3. Sube a GitHub"
    echo "4. Deploy en Railway"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  FALTAN $FAILED ELEMENTOS${NC}"
    echo ""
    echo "Revisa los elementos marcados con ❌"
    echo ""
    exit 1
fi
