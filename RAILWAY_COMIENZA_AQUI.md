# 🚀 DEPLOYMENT EN RAILWAY - GUÍA RÁPIDA

## ¿QUÉ TENGO LISTO?

✅ **Dashboard Mobile-First** - Optimizado para celular  
✅ **Bot Telegram** - Con funcionalidades avanzadas  
✅ **Dockerfile** - Configurado para Railway  
✅ **Base de datos** - SQLite iniciada automáticamente  
✅ **Servidor** - Waitress production server  

---

## 📁 ARCHIVOS RAILWAY DISPONIBLES

| Archivo | Descripción | Dónde |
|---------|-------------|-------|
| `RAILWAY_PASO_A_PASO.md` | 📋 Tutorial paso a paso | **COMIENZA AQUÍ** |
| `VARIABLES_RAILWAY.md` | 🔑 Variables de entorno | Cómo obtener tokens |
| `RAILWAY_CHECKLIST.md` | ✅ Checklist completo | Validar cada paso |
| `RAILWAY_GUIA_COMPLETA.md` | 📚 Guía detallada + troubleshooting | Problemas? |
| `.railway.json` | ⚙️ Config Railway | Auto |
| `railway_start.py` | 🚂 Script startup | Auto |

---

## ⏱️ TIEMPO TOTAL

**15-20 minutos** desde cero hasta en producción

---

## 3 OPCIONES

### 🟢 OPCIÓN 1: MÁS FÁCIL (Recomendado)

1. Código en GitHub ✅
2. Crear proyecto Railway
3. Conectar GitHub
4. Agregar 3 variables
5. **¡Listo!** (Railway hace el deploy automático)

[Ver tutorial →](RAILWAY_PASO_A_PASO.md)

---

### 🔵 OPCIÓN 2: CON CLI

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Deploy
railway up
```

[Detalles →](RAILWAY_GUIA_COMPLETA.md)

---

### 🟡 OPCIÓN 3: DOCKER LOCAL

```bash
# Probar en local primero
docker build -t mi-bot .
docker run -e TELEGRAM_BOT_TOKEN=xxx -p 5000:5000 mi-bot
```

---

## 🎯 EMPEZAR AHORA

### RECOMENDADO: Opción 1 (Más fácil)

**Paso 1: Lee esto primero** (5 min)
```
RAILWAY_PASO_A_PASO.md
```

**Paso 2: Obtén tus variables** (5 min)
```
VARIABLES_RAILWAY.md
```

**Paso 3: Deploy en Railway** (5 min)
```
- Ve a railway.app
- Conecta GitHub
- Agrega variables
- ¡Listo!
```

**Paso 4: Verifica todo** (5 min)
```
RAILWAY_CHECKLIST.md
```

---

## 🤔 PREGUNTAS FRECUENTES

### ¿Necesito pagar?
**No.** Railway tiene free tier:
- 500 MB RAM
- 100 GB bandwidth/mes
- Suficiente para empezar

### ¿Qué datos necesito?
3 variables de entorno:
1. **TELEGRAM_BOT_TOKEN** (de @BotFather)
2. **ADMIN_PASSWORD** (inventas)
3. **SECRET_KEY** (generamos)

Ver: [VARIABLES_RAILWAY.md](VARIABLES_RAILWAY.md)

### ¿Cuánto tarda el deploy?
**2-5 minutos** en total

### ¿Puedo actualizaciones código?
**Sí.** Simplemente haces push a GitHub y Railway redeploy automáticamente

### ¿Funciona en móvil?
**Sí.** Dashboard está optimizado para celular

### ¿Qué pasa con mis datos?
Se guardan en SQLite en Railway. Railway hace backups automáticos.

---

## 📊 ARQUITECTURA

```
GitHub Repo
    ↓
Railway (conecta automáticamente)
    ↓
Dockerfile (construye imagen)
    ↓
Python 3.10 + Bot + Dashboard
    ├── 🤖 Bot Telegram (thread daemon)
    ├── 🌐 Dashboard Flask (puerto 5000)
    └── 💾 SQLite DB (persistente)
```

---

## ✨ CARACTERÍSTICAS

| Característica | Estado |
|---|---|
| Bot responde 24/7 | ✅ |
| Dashboard accesible | ✅ |
| Optimizado móvil | ✅ |
| Base de datos | ✅ |
| HTTPS | ✅ |
| Auto-redeploy | ✅ |
| Health checks | ✅ |
| Logs en tiempo real | ✅ |

---

## 🚨 PROBLEMAS?

Si algo falla durante el deploy:

1. **Revisa los Logs** en Railway Dashboard
2. **Verifica variables** (typos?)
3. **Consulta:** [RAILWAY_GUIA_COMPLETA.md](RAILWAY_GUIA_COMPLETA.md#troubleshooting)
4. **Pregunta:** Abre issue en GitHub

---

## 📞 SOPORTE

- [RAILWAY_GUIA_COMPLETA.md](RAILWAY_GUIA_COMPLETA.md) - Todos los detalles
- [RAILWAY_CHECKLIST.md](RAILWAY_CHECKLIST.md) - Valida cada paso
- Railway Docs: https://docs.railway.app

---

## 🎉 SIGUIENTE

Una vez deployado en Railway:

1. ✅ Compartir URL con usuarios
2. ✅ Monitorear logs periódicamente
3. ✅ Actualizar código cuando necesites
4. ✅ Escalar si crece el tráfico

---

**¡Vamos! 🚀** Comienza con [RAILWAY_PASO_A_PASO.md](RAILWAY_PASO_A_PASO.md)
