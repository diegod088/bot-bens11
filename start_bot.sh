#!/bin/bash
# Script para iniciar el bot

cd "$(dirname "$0")" || exit 1

echo "🚀 Iniciando BOT TELEGRAM..."
echo ""

# Activar venv y ejecutar
./.venv/bin/python3 railway_start.py

