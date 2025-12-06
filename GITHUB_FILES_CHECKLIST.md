# 📋 LISTA DE ARCHIVOS PARA GITHUB → RAILWAY

## ✅ ARCHIVOS QUE DEBES SUBIR (numerados en orden)

### 🐍 Código Principal (Python)
1. `bot_with_paywall.py` - Bot principal de Telegram
2. `database.py` - Manejo de base de datos SQLite
3. `backend_paypal.py` - Backend para pagos PayPal
4. `run_backend.py` - Script para ejecutar backend

### 🛠️ Utilidades
5. `generate_session.py` - Generar SESSION_STRING de Telethon
6. `verify_config.py` - Verificar configuración

### 📦 Configuración y Dependencias
7. `requirements.txt` - Dependencias de Python
8. `.env.example` - Ejemplo de variables de entorno (SIN valores reales)
9. `.gitignore` - Archivos a ignorar en Git

### 🐳 Docker y Railway
10. `Dockerfile.bot` - Docker para el bot de Telegram
11. `Dockerfile.backend` - Docker para el backend PayPal
12. `railway.toml` - Configuración de Railway

### 📚 Documentación
13. `README.md` - Descripción general del proyecto
14. `RAILWAY_DEPLOY_GUIDE.md` - Guía completa de deployment
15. `PRODUCTION_IMPROVEMENTS.md` - Documentación técnica
16. `PROJECT_SUMMARY.md` - Resumen del proyecto
17. `CLEANUP_GUIDE.md` - Guía de limpieza
18. `EXECUTIVE_SUMMARY.md` - Resumen ejecutivo

---

## ❌ ARCHIVOS QUE **NO** DEBES SUBIR

### 🔒 Archivos Sensibles (NUNCA subir)
- ❌ `.env` - Contiene credenciales reales
- ❌ `users.db` - Base de datos con información de usuarios
- ❌ `*.session` - Archivos de sesión de Telethon
- ❌ `*.session-journal` - Journals de sesión

### 🗑️ Archivos Temporales
- ❌ `*.log` - Logs del bot
- ❌ `bot.log` - Log principal
- ❌ `__pycache__/` - Cache de Python
- ❌ `.venv/` - Entorno virtual
- ❌ `downloads/` - Archivos descargados temporales
- ❌ `compressed/` - Archivos comprimidos temporales
- ❌ `backups/` - Backups de base de datos

---

## 🚀 COMANDOS PARA SUBIR A GITHUB

### Paso 1: Limpiar archivos sensibles
```bash
cd "/home/yadied/Escritorio/bot descargar contenido"

# Ejecutar script de limpieza
chmod +x cleanup_repo.sh
./cleanup_repo.sh
```

### Paso 2: Verificar qué archivos se subirán
```bash
git status
```

### Paso 3: Agregar SOLO los 18 archivos necesarios
```bash
# Código Python (1-4)
git add bot_with_paywall.py database.py backend_paypal.py run_backend.py

# Utilidades (5-6)
git add generate_session.py verify_config.py

# Configuración (7-9)
git add requirements.txt .env.example .gitignore

# Docker y Railway (10-12)
git add Dockerfile.bot Dockerfile.backend railway.toml

# Documentación (13-18)
git add README.md RAILWAY_DEPLOY_GUIDE.md PRODUCTION_IMPROVEMENTS.md
git add PROJECT_SUMMARY.md CLEANUP_GUIDE.md EXECUTIVE_SUMMARY.md
```

### Paso 4: Commit
```bash
git commit -m "🚀 Production ready: Bot completo para Railway deployment"
```

### Paso 5: Push a GitHub
```bash
git push origin main
```

---

## ✅ CHECKLIST ANTES DE PUSH

Verifica que estos archivos **NO** estén en tu repositorio:

```bash
# Verificar archivos sensibles
git ls-files | grep -E '\.env$|users\.db|\.session'

# Si aparece algo, removerlo:
git rm --cached .env
git rm --cached users.db
git rm --cached *.session
```

---

## 🚂 DESPUÉS DE SUBIR A GITHUB

Una vez que los **18 archivos** estén en GitHub:

1. Ve a [Railway.app](https://railway.app)
2. Crea nuevo proyecto
3. Conecta tu repositorio de GitHub
4. Railway detectará automáticamente los Dockerfiles
5. Configura las variables de entorno
6. ¡Deploy automático!

Sigue la guía completa en: `RAILWAY_DEPLOY_GUIDE.md`

---

**RESUMEN**: Subir exactamente **18 archivos** a GitHub, nunca subir `.env`, `users.db` o `*.session`
