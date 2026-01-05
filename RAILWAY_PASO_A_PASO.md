# 🚀 RAILWAY DEPLOY - PASO A PASO

## ¿Cuánto toma?
**15-20 minutos** en total

---

## 📋 PASO 1: PREPARAR TU CÓDIGO

### Verificar que tienes estos archivos:

```bash
ls -la | grep -E "Dockerfile|requirements.txt|railway_start.py|.railway.json|Procfile"
```

Debes ver:
```
✅ Dockerfile
✅ requirements.txt
✅ railway_start.py
✅ .railway.json
✅ Procfile
```

---

## 🐙 PASO 2: GITHUB SETUP

### Si NO tienes GitHub repo:

```bash
# Inicializar git
git init

# Agregar archivos
git add .

# Commit
git commit -m "Bot Telegram ready for Railway"

# Crear repo en GitHub.com (sin inicializar)

# Conectar
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git

# Push
git branch -M main
git push -u origin main
```

### Si YA tienes repo:
```bash
git add .
git commit -m "Railway deployment"
git push
```

---

## 🚂 PASO 3: CREAR RAILWAY PROJECT

### Opción A: Desde Web (FÁCIL) ⭐

1. Ve a [railway.app](https://railway.app)
2. Click **"Dashboard"** (si está logeado)
3. Click **"New Project"**
4. Selecciona **"Deploy from GitHub"**
5. Autoriza Railway en GitHub
6. Selecciona tu repo
7. **Railway inicia el deploy automáticamente**

### Opción B: Desde CLI

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Crear proyecto
railway init

# Deploy
railway up
```

---

## 🔑 PASO 4: CONFIGURAR VARIABLES

### En Railway Dashboard:

1. Haz click en tu **proyecto**
2. Haz click en el **servicio** (el contenedor)
3. Click en **Variables** (pestaña arriba)
4. Haz click en **"Add Variable"**

### Agrega estas variables:

| Variable | Valor | Obtener De |
|----------|-------|-----------|
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | @BotFather en Telegram |
| `ADMIN_PASSWORD` | `TuPassword123!` | Inventar (mín 8 chars) |
| `SECRET_KEY` | Ejecutar en Python | Ver abajo |

### Generar SECRET_KEY:

```python
# Ejecuta esto en Python
import secrets
print(secrets.token_urlsafe(32))

# Copia el resultado
```

Ejemplo:
```
5L8vK2mP9qR3xW7yZ1nT6jB4dF0hG_u-vXsYaBcDeF
```

---

## ✅ PASO 5: VERIFICAR DEPLOY

### Viendo Logs:

1. Railway Dashboard → Tu proyecto
2. Click en **"Logs"** (botón derecha)
3. Debes ver:
```
🚀 RAILWAY DEPLOYMENT STARTING
✅ Database initialized
✅ Bot thread started
🌐 Dashboard on 0.0.0.0:5000
📦 Using Waitress
```

Si ves ❌ o ERROR, revisa variables.

### Verificar que funciona:

1. Railway te da una **URL** (ej: `https://bot-telegram-production.up.railway.app`)
2. Abre en navegador: `https://tu-url/login`
3. Ingresa tu ADMIN_PASSWORD
4. Debes ver el dashboard

---

## 🤖 PASO 6: PROBAR BOT

### Verificar que recibe mensajes:

1. Abre Telegram
2. Busca tu bot por nombre
3. Envía `/start`
4. Bot debe responder
5. Si no responde:
   - Revisa logs en Railway
   - Verifica TELEGRAM_BOT_TOKEN
   - Reinicia el deploy

---

## 📊 ESTADO DEL DEPLOY

### Dashboard de Railway muestra:

```
✅ Running     = Todo bien
🟡 Deploying   = Está subiendo
❌ Failed      = Error (revisa logs)
🔄 Restarting  = Se está reiniciando
```

---

## 🔗 OBTENER URL PÚBLICA

Después de deploy exitoso:

1. Railway Dashboard → Tu proyecto
2. Click en el servicio
3. Arriba verás la URL (ej):
   ```
   https://bot-telegram-production.up.railway.app
   ```
4. Esa es tu URL pública

---

## 🔄 REDEPLOY (Actualizar código)

Si cambias el código:

```bash
# Cambiar código
nano bot_with_paywall.py

# Commit y push
git add .
git commit -m "Fix: ..."
git push

# Railway redeploy automáticamente en ~2-3 minutos
```

O manualmente:
- Railway Dashboard → Click **Redeploy** button

---

## 🛑 DETENER DEPLOY

Si necesitas pausar:

1. Railway Dashboard → Tu proyecto
2. Click en el servicio
3. Click en **Settings** (engranaje)
4. Click **Remove** o **Pause**

---

## 📝 CHECKLIST FINAL

- [ ] Código en GitHub
- [ ] Dockerfile presente
- [ ] requirements.txt presente
- [ ] railway_start.py presente
- [ ] TELEGRAM_BOT_TOKEN configurada
- [ ] ADMIN_PASSWORD configurada
- [ ] SECRET_KEY configurada
- [ ] Deploy completado (✅ Running)
- [ ] Logs sin errores
- [ ] Dashboard accesible
- [ ] Bot responde en Telegram

---

## 🎉 ¡LISTO!

Tu bot está en **PRODUCCIÓN** en Railway.

### Ahora puedes:
- ✅ Acceder al dashboard desde cualquier lugar
- ✅ El bot recibe mensajes 24/7
- ✅ Auto-scaling si crece el tráfico
- ✅ Backups automáticos

---

## 📞 PROBLEMAS?

Ver: **RAILWAY_GUIA_COMPLETA.md** → Troubleshooting

---

**Total time: ~15 minutos** ⏱️

**¡Éxito! 🚀**
