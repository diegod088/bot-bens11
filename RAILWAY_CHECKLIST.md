# ✅ CHECKLIST COMPLETO - DESPLIEGUE EN RAILWAY

## 📋 PASO A PASO

### PASO 1: Obtener Credenciales de Telegram

- [ ] **Token del Bot**
  - Ve a [@BotFather](https://t.me/BotFather) en Telegram
  - Envía `/newbot` (o usa un bot existente con `/mybots`)
  - Copia el token (formato: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

- [ ] **API ID y API Hash**
  - Ve a [my.telegram.org](https://my.telegram.org)
  - Inicia sesión con tu número de Telegram
  - Ve a "API development tools"
  - Crea una app si no tienes una
  - Copia `api_id` y `api_hash`

- [ ] **Tu User ID**
  - Abre [@userinfobot](https://t.me/userinfobot) en Telegram
  - Envía cualquier mensaje
  - Copia tu User ID (número)

### PASO 2: Generar Claves de Seguridad

Ejecuta en tu terminal:

```bash
cd "/home/yadied/Escritorio/bot descargar contenido"
python3 generate_keys.py
```

- [ ] Copia `ENCRYPTION_KEY`
- [ ] Copia `DASHBOARD_SECRET_KEY`
- [ ] Copia `ADMIN_TOKEN` (o crea tu propia contraseña)

### PASO 3: Configurar Variables en Railway

Ve a [Railway Dashboard](https://railway.app/dashboard):

1. [ ] Selecciona tu proyecto
2. [ ] Click en tu servicio
3. [ ] Click en pestaña **"Variables"**
4. [ ] Agrega cada variable:

```bash
TELEGRAM_BOT_TOKEN=tu_token_del_botfather
TELEGRAM_API_ID=tu_api_id
TELEGRAM_API_HASH=tu_api_hash
ADMIN_TOKEN=tu_password_para_dashboard
ADMIN_ID=tu_telegram_user_id
ENCRYPTION_KEY=la_clave_generada
DASHBOARD_SECRET_KEY=la_clave_generada
```

### PASO 4: Desplegar

- [ ] Railway automáticamente redesplegará cuando agregues variables
- [ ] O manualmente: Click en **"Deploy"**

### PASO 5: Verificar Despliegue

Espera 2-3 minutos, luego:

- [ ] Ve a **"Deployments"** > **"View Logs"**
- [ ] Busca estos mensajes:
  ```
  ✅ All required environment variables found
  🤖 Starting Telegram Bot...
  🌐 Starting Dashboard...
  ```

- [ ] Verifica el healthcheck:
  - Ve a **"Settings"** > **"Domains"**
  - Copia tu URL (ej: `https://bot-production-xxxx.up.railway.app`)
  - Abre: `https://tu-url/health`
  - Deberías ver: `{"status": "healthy", ...}`

### PASO 6: Acceder al Dashboard

- [ ] Abre tu URL de Railway
- [ ] Deberías ver la página de login
- [ ] Ingresa la contraseña de `ADMIN_TOKEN`
- [ ] ¡Listo! Ya puedes administrar tu bot

### PASO 7: Probar el Bot

- [ ] Abre Telegram
- [ ] Busca tu bot por su username
- [ ] Envía `/start`
- [ ] Deberías recibir el mensaje de bienvenida

## 🔍 VERIFICACIÓN RÁPIDA

### Variables Configuradas

Verifica que tienes las 7 variables:

```bash
# Opción 1: Desde Railway Web UI
Settings > Variables (deberías ver 7 variables)

# Opción 2: Desde Railway CLI
railway variables
```

### Estado del Servicio

```bash
# Ver logs en tiempo real
railway logs -f

# Ver estado
railway status
```

## ❌ SOLUCIÓN DE PROBLEMAS

### Error: "service unavailable"

**Causa:** Faltan variables de entorno

**Solución:**
1. Verifica que las 7 variables estén configuradas
2. Revisa que los valores sean correctos
3. Redespliega: `railway up --detach`

### Error: "Missing required environment variables"

**Solución:** 
1. Lee los logs para ver qué variables faltan
2. Agrega las variables faltantes
3. Railway redesplegará automáticamente

### Error: Bot no responde en Telegram

**Posibles causas:**
1. Token del bot incorrecto
2. Bot no está iniciado (revisa logs)
3. API_ID o API_HASH incorrectos

**Solución:**
1. Verifica el token con @BotFather
2. Revisa logs: `railway logs -f`
3. Verifica las credenciales en my.telegram.org

### Dashboard muestra error 500

**Solución:**
1. Verifica `DASHBOARD_SECRET_KEY` esté configurado
2. Revisa logs del dashboard
3. Asegúrate que `ADMIN_TOKEN` esté configurado

### Los logs muestran "Database initialization failed"

**Solución:**
1. Esto es normal la primera vez
2. Railway debería crear el archivo automáticamente
3. Si persiste, contacta soporte de Railway

## 📊 MONITOREO CONTINUO

### Logs

```bash
# Ver últimos logs
railway logs

# Ver logs en tiempo real
railway logs -f

# Ver logs de un deployment específico
railway logs --deployment DEPLOYMENT_ID
```

### Métricas

En Railway Dashboard:
1. Ve a **"Metrics"**
2. Revisa CPU, RAM, Network
3. Asegúrate de estar dentro de los límites de tu plan

## 🎉 SIGUIENTE PASO

Una vez que todo funcione:

1. [ ] Configura un dominio personalizado (opcional)
2. [ ] Configura backups de la base de datos (recomendado)
3. [ ] Monitorea el uso de recursos
4. [ ] Prueba todas las funcionalidades del bot

## 📞 AYUDA

Si algo no funciona:

1. Lee [RAILWAY_VARIABLES.md](RAILWAY_VARIABLES.md) para detalles de variables
2. Lee [SOLUCION_RAILWAY.txt](SOLUCION_RAILWAY.txt) para solución rápida
3. Ejecuta `./verify_railway_vars.sh` para verificar variables
4. Revisa los logs: `railway logs`

---

**Última actualización:** 5 de enero de 2026
