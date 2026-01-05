# 🚀 DEPLOY EN RAILWAY - PASO A PASO

## ✅ CÓDIGO YA ESTÁ EN GITHUB

Tu código está aquí:  
**https://github.com/diegod088/bot-bens11**

---

## 5 PASOS PARA DEPLOYER

### PASO 1: Abre railway.app
```
https://railway.app
```

### PASO 2: Login con GitHub
- Click "Login"
- Elige "GitHub"
- Autoriza Railway

### PASO 3: Crear Nuevo Proyecto
- Click "Create New Project"
- Selecciona "Deploy from GitHub"
- Busca "bot-bens11"
- Click en el repo

Railway **inicia el build automáticamente** (2-5 minutos)

### PASO 4: Agrega 3 Variables (IMPORTANTE)

En Railway Dashboard:
1. Click en tu Proyecto
2. Click en el Service
3. Pestaña "Variables"
4. Agrega:

```
TELEGRAM_BOT_TOKEN = Tu_Token_De_BotFather

ADMIN_PASSWORD = Tu_Password_Inventado_8_Caracteres

SECRET_KEY = Tu_Secret_Key_Generado
```

**Cómo obtener cada una:**

#### TELEGRAM_BOT_TOKEN
1. Abre Telegram
2. Busca @BotFather
3. Envía /newbot
4. Dale nombre y username
5. Copias el token

#### ADMIN_PASSWORD
- Inventar (8+ caracteres)
- Ejemplo: MiPassword123!

#### SECRET_KEY
En terminal:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copias el resultado

### PASO 5: ¡LISTO!

Espera a que el status diga:  
✅ **Running**

Tu URL pública:  
**https://tu-proyecto.railway.app**

---

## 🎯 QUÉ VAS A VER

**Dashboard:**
- URL: https://tu-proyecto.railway.app
- Usuario: `admin`
- Contraseña: Tu `ADMIN_PASSWORD`

**Características:**
- ✅ Responsive (móvil + desktop)
- ✅ Dark mode automático
- ✅ Estadísticas en tiempo real
- ✅ Usuarios y analytics

---

## ⏱️ TIEMPO TOTAL

- 2 min: Railway setup + GitHub auth
- 2 min: Crear proyecto
- 1 min: Agrega variables
- 3 min: Build automático (2-5 min)
- **Total: ~8 minutos**

---

## 📞 SI ALGO FALLA

**Status dice "Building" (normal)**
- Espera 2-5 minutos
- No hagas nada, es automático

**Status dice "Error"**
- Click "Logs"
- Lee el error
- Revisa las variables (typos?)

**Variables mal escrita**
- Railway → Variables
- Revisa letra por letra
- Sin espacios al inicio/final

---

## ✅ CHECKLIST

- [ ] Código en GitHub ✅
- [ ] Railway account creada
- [ ] Proyecto creado en Railway
- [ ] TELEGRAM_BOT_TOKEN agregada
- [ ] ADMIN_PASSWORD agregada
- [ ] SECRET_KEY agregada
- [ ] Status: ✅ Running
- [ ] Accedí al dashboard
- [ ] Funciona todo

---

## 🎉 ¡LISTO PARA PRODUCCIÓN!

Tu dashboard está en:  
**https://tu-proyecto.railway.app**

¡Ahora está 24/7 en la nube! 🚀
