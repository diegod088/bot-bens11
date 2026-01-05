# 🔧 Variables de Entorno Requeridas para Railway

## ❌ Problema Actual

El healthcheck está fallando porque **faltan variables de entorno obligatorias** en Railway.

## ✅ Variables OBLIGATORIAS

Debes configurar estas variables en Railway:

### 1️⃣ Variables del Bot de Telegram

```bash
TELEGRAM_BOT_TOKEN=tu_token_del_bot_aqui
TELEGRAM_API_ID=tu_api_id_aqui
TELEGRAM_API_HASH=tu_api_hash_aqui
```

**Cómo obtenerlas:**
- `TELEGRAM_BOT_TOKEN`: De [@BotFather](https://t.me/BotFather) en Telegram
- `TELEGRAM_API_ID` y `TELEGRAM_API_HASH`: De [my.telegram.org](https://my.telegram.org)

### 2️⃣ Variables del Dashboard

```bash
ADMIN_TOKEN=tu_password_segura_aqui
ADMIN_ID=tu_telegram_user_id_aqui
```

**Cómo obtenerlas:**
- `ADMIN_TOKEN`: Cualquier contraseña segura para el dashboard
- `ADMIN_ID`: Tu User ID de Telegram (puedes obtenerlo con [@userinfobot](https://t.me/userinfobot))

### 3️⃣ Variables de Seguridad

```bash
ENCRYPTION_KEY=tu_encryption_key_aqui
DASHBOARD_SECRET_KEY=tu_secret_key_aqui
```

**Cómo generarlas:**

```bash
# Para ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Para DASHBOARD_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

## 📝 Paso a Paso en Railway

### Opción 1: Desde la Web UI

1. Ve a tu proyecto en Railway
2. Selecciona tu servicio
3. Click en la pestaña **"Variables"**
4. Click en **"+ New Variable"**
5. Agrega cada variable una por una:
   - Name: `TELEGRAM_BOT_TOKEN`
   - Value: `tu_token_aqui`
6. Click **"Add"**
7. Repite para todas las variables

### Opción 2: Desde Railway CLI

```bash
# Instalar CLI (si no lo tienes)
npm install -g @railway/cli

# Login
railway login

# Seleccionar tu proyecto
railway link

# Configurar variables
railway variables set TELEGRAM_BOT_TOKEN=tu_token_aqui
railway variables set TELEGRAM_API_ID=tu_api_id
railway variables set TELEGRAM_API_HASH=tu_api_hash
railway variables set ADMIN_TOKEN=tu_password_segura
railway variables set ADMIN_ID=tu_user_id
railway variables set ENCRYPTION_KEY=tu_encryption_key
railway variables set DASHBOARD_SECRET_KEY=tu_secret_key

# Verificar variables
railway variables

# Re-deploy
railway up
```

## 🔍 Verificar si las Variables Están Configuradas

Después de configurar las variables, verifica en los logs:

```bash
railway logs
```

Deberías ver:
```
✅ All required environment variables found
🤖 Starting Telegram Bot...
🌐 Starting Dashboard on 0.0.0.0:XXXX
```

## ⚠️ Errores Comunes

### Error: "Missing required environment variables"

**Causa:** No configuraste todas las variables obligatorias.

**Solución:** Configura TODAS las variables listadas arriba.

### Error: "service unavailable" en healthcheck

**Causas posibles:**
1. Variables no configuradas
2. Token del bot inválido
3. Puerto incorrecto

**Solución:** 
- Verifica las variables en Railway
- No configures la variable `PORT` manualmente (Railway la asigna automáticamente)

### Error: Database initialization failed

**Causa:** Problema con permisos de escritura.

**Solución:** Railway debería permitir escritura en `/app`. Si persiste, verifica los logs.

## 📊 Verificación del Healthcheck

Una vez configurado todo, puedes verificar el healthcheck:

```bash
# En tu navegador o con curl
https://tu-servicio.up.railway.app/health
```

Deberías ver:
```json
{
  "status": "healthy",
  "service": "dashboard",
  "timestamp": "2026-01-05T00:00:00"
}
```

## 🚀 Después de Configurar

1. Railway automáticamente redesplegará tu servicio
2. Espera unos minutos
3. Verifica los logs: `railway logs -f`
4. Accede al dashboard: `https://tu-servicio.up.railway.app/`

## 📞 Soporte

Si sigues teniendo problemas:
1. Copia los logs completos: `railway logs > logs.txt`
2. Verifica que las variables estén correctas
3. Asegúrate de que el token del bot sea válido
