# 🚂 GUÍA COMPLETA - DEPLOY EN RAILWAY

## ¿Qué es Railway?

Railway es una plataforma moderna de hosting que permite desplegar aplicaciones Python, Node.js, etc. en minutos. Es perfecto para bots y dashboards.

---

## 📋 PASOS PARA DEPLOY EN RAILWAY

### PASO 1: Crear Cuenta en Railway

1. Entra a [railway.app](https://railway.app)
2. Click en **"Start Free"**
3. Registrate con GitHub (recomendado)
4. Verifica tu email

### PASO 2: Preparar Tu Código para Railway

Tu proyecto ya tiene:
- ✅ `Dockerfile` - Configurado
- ✅ `railway.json` - Listo
- ✅ `Procfile` - Incluido
- ✅ `requirements.txt` - Completado

### PASO 3: Conectar GitHub (OPCIÓN A - RECOMENDADO)

Si NO tienes GitHub repo:

```bash
# Inicializar git
cd "/home/yadied/Escritorio/bot descargar contenido"
git init

# Agregar todos los archivos
git add .

# Crear primer commit
git commit -m "Bot Telegram + Dashboard - Ready for Railway"

# Conectar a GitHub
# 1. Crea un nuevo repo en GitHub.com
# 2. Copia la URL (ej: https://github.com/tuusuario/bot-telegram.git)

git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### PASO 4: Deploy en Railway

#### Desde Dashboard Web:

1. Ve a [railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Selecciona **"Deploy from GitHub repo"**
4. Autoriza Railway en GitHub
5. Selecciona tu repo
6. Railway detectará automáticamente `Procfile` y `Dockerfile`
7. Click **"Deploy"**

#### Desde CLI (ALTERNATIVO):

```bash
# Instalar Railway CLI
npm install -g @railway/cli
# O con Homebrew:
brew install railway

# Iniciar sesión
railway login

# Crear nuevo proyecto
railway init

# Deploy
railway up
```

### PASO 5: Configurar Variables de Entorno

En Railway Dashboard:

1. Click en tu proyecto
2. Ir a **Variables** (botón de engranaje)
3. Agregar estas variables:

```
TELEGRAM_BOT_TOKEN = tu_token_aqui
ADMIN_PASSWORD = tu_contraseña_aqui
SECRET_KEY = genera_una_clave_segura_aqui
DATABASE_URL = se_crea_automaticamente
```

**Para generar SECRET_KEY segura:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

---

## 🔑 VARIABLES DE ENTORNO NECESARIAS

| Variable | Valor | Obligatorio |
|----------|-------|------------|
| `TELEGRAM_BOT_TOKEN` | Token de @BotFather | ✅ SÍ |
| `ADMIN_PASSWORD` | Tu contraseña | ✅ SÍ |
| `SECRET_KEY` | Clave segura aleatoria | ✅ SÍ |
| `PORT` | 5000 (Railway lo asigna) | No |
| `HOST` | 0.0.0.0 | No |

---

## 🚀 VERIFICAR DEPLOY

Después de hacer deploy:

1. Railway te dará una URL (ej: `https://bot-telegram-production.up.railway.app`)
2. Abre en navegador: `https://tu-url/login`
3. Login con tu contraseña
4. Verifica que el bot reciba mensajes en Telegram

---

## 🔧 CONFIGURAR WEBHOOK TELEGRAM

El bot necesita recibir mensajes desde Telegram:

```python
# En tu código (ya está hecho)
WEBHOOK_URL = "https://tu-dominio-railway.app/webhook"

# Railway asigna el dominio automáticamente
# Telegram lo configurará automáticamente
```

---

## ✅ CHECKLIST DE DEPLOY

- [ ] Cuenta Railway creada
- [ ] Código en GitHub
- [ ] Variables de entorno configuradas
- [ ] Deploy iniciado
- [ ] Dashboard accesible (URL de Railway)
- [ ] Bot responde en Telegram
- [ ] Database funciona
- [ ] Logs sin errores

---

## 🐛 TROUBLESHOOTING

### Problema: "Cannot find module"

**Solución:**
```bash
# Asegúrate que requirements.txt está en la raíz
# Y que todos los imports están correctos
pip install -r requirements.txt
```

### Problema: "Port already in use"

**Solución:**
```bash
# Railway asigna el PORT automáticamente
# El código ya maneja: os.environ.get('PORT', 5000)
```

### Problema: Bot no recibe mensajes

**Solución:**
1. Verifica `TELEGRAM_BOT_TOKEN` en Variables
2. Revisa logs: Click en proyecto → "Logs"
3. Comprueba que webhook está activo

### Problema: Database no funciona

**Solución:**
```python
# El código usa SQLite local
# Railway guarda archivos en /tmp (temporal)
# Para producción, considera PostgreSQL gratuito en Railway
```

---

## 📊 MONITOREO

### Ver Logs en Tiempo Real:

En Railway Dashboard:
1. Click en tu proyecto
2. Pestaña **"Logs"**
3. Ver salida en vivo

### Health Check:

```bash
curl https://tu-url-railway.app/health
```

---

## 💾 DATABASE EN RAILWAY

### Opción 1: SQLite (Actual)
- ✅ Funciona sin config
- ❌ Datos se pierden cada deploy
- ✅ Bueno para testing

### Opción 2: PostgreSQL (Recomendado para Producción)
1. En Railway: Click "Add" en proyecto
2. Selecciona "PostgreSQL"
3. Se crea automáticamente
4. Actualiza tu código para usar PostgreSQL:

```python
# database.py
import os
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
```

---

## 🔐 SEGURIDAD EN PRODUCCIÓN

1. **SECRET_KEY**: Usa valor aleatorio fuerte
2. **TELEGRAM_BOT_TOKEN**: Mantén secreto
3. **ADMIN_PASSWORD**: Clave fuerte (12+ caracteres)
4. **Firewall**: Railway tiene HTTPS automático
5. **Rate Limiting**: El código ya lo incluye

---

## 📈 ESCALABILIDAD

Railway soporta:
- ✅ Auto-scaling
- ✅ Multiple instances
- ✅ Load balancing
- ✅ Databases managed
- ✅ Environment variables

Tu aplicación está lista para escalar.

---

## 🎯 PRÓXIMOS PASOS

1. **Crear cuenta Railway** (2 min)
2. **Subir código a GitHub** (5 min)
3. **Conectar en Railway** (1 min)
4. **Configurar variables** (2 min)
5. **Deploy automático** (Railway lo hace)
6. **Verificar que funciona** (2 min)

**Tiempo total: ~15 minutos**

---

## 📞 SOPORTE

- Railway Docs: [docs.railway.app](https://docs.railway.app)
- Mi código incluye Health Check y logging
- Revisa logs si hay problemas

---

## ✨ CONCLUSIÓN

Tu bot está listo para Railway. Solo necesitas:

1. GitHub (repo de tu código)
2. Cuenta Railway
3. 5 variables de entorno
4. ¡Y listo!

Railway maneja:
- Docker
- Servidor web
- HTTPS
- Dominio público
- Escalabilidad

**¡Totalmente automatizado! 🚀**

