#!/bin/bash
# Script de limpieza del repositorio antes de subir a GitHub

echo "🧹 Limpiando repositorio para GitHub..."
echo ""

# Función para eliminar si existe
remove_if_exists() {
    if [ -e "$1" ]; then
        rm -rf "$1"
        echo "✓ Eliminado: $1"
    fi
}

# Eliminar archivos temporales de Python
echo "📦 Limpiando archivos de Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null
find . -type f -name "*.pyd" -delete 2>/dev/null
echo "✓ Cache de Python eliminado"

# Eliminar logs
echo ""
echo "📝 Limpiando logs..."
remove_if_exists "*.log"
remove_if_exists "bot.log"
remove_if_exists "backend.log"

# Eliminar base de datos local
echo ""
echo "🗄️ Limpiando base de datos local..."
remove_if_exists "users.db"
remove_if_exists "*.sqlite"
remove_if_exists "*.sqlite3"

# Eliminar sesiones de Telethon
echo ""
echo "🔐 Limpiando sesiones..."
remove_if_exists "*.session"
remove_if_exists "*.session-journal"

# Eliminar entornos virtuales
echo ""
echo "🐍 Limpiando entornos virtuales..."
remove_if_exists ".venv"
remove_if_exists "venv"
remove_if_exists "env"
remove_if_exists "ENV"

# Eliminar archivos de IDE
echo ""
echo "💻 Limpiando archivos de IDE..."
remove_if_exists ".vscode"
remove_if_exists ".idea"
remove_if_exists "*.swp"
remove_if_exists "*.swo"
remove_if_exists "*~"

# Eliminar archivos del sistema
echo ""
echo "🖥️ Limpiando archivos del sistema..."
remove_if_exists ".DS_Store"
remove_if_exists "Thumbs.db"

# Verificar que .env no esté en el repo
echo ""
echo "🔍 Verificando archivos sensibles..."
if [ -f ".env" ]; then
    echo "⚠️  ADVERTENCIA: .env encontrado"
    echo "   Asegúrate de que esté en .gitignore"
else
    echo "✓ .env no presente (correcto)"
fi

# Verificar .gitignore
if [ -f ".gitignore" ]; then
    echo "✓ .gitignore presente"
else
    echo "⚠️  ADVERTENCIA: .gitignore no encontrado"
fi

# Mostrar archivos que se subirán
echo ""
echo "📋 Archivos que se subirán a GitHub:"
echo "-----------------------------------"
ls -1 | grep -v ".venv" | grep -v ".env" | grep -v "users.db" | grep -v "*.log"

echo ""
echo "✅ Limpieza completada"
echo ""
echo "Próximos pasos:"
echo "1. Revisar archivos con: git status"
echo "2. Verificar que .env NO aparezca"
echo "3. Hacer commit: git add . && git commit -m 'Initial commit'"
echo "4. Push a GitHub: git push -u origin main"
