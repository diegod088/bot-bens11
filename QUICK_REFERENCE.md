# 📌 QUICK REFERENCE - RAILWAY DEPLOYMENT

## 🚀 20 MINUTOS PARA PRODUCCIÓN

### PASO 1: Obtén Variables (5 min)

```
🔑 TELEGRAM_BOT_TOKEN
   → Telegram: busca @BotFather
   → /start → /newbot
   → Copia el token
   Ejemplo: 1234567890:ABC-DEF

🔐 ADMIN_PASSWORD
   → Inventar (8+ caracteres)
   Ejemplo: MiPassword123!

🔒 SECRET_KEY
   → python -c "import secrets; print(secrets.token_urlsafe(32))"
   Ejemplo: 5L8vK2mP9qR3xW7...
```

### PASO 2: GitHub (3 min)

```bash
git init
git add .
git commit -m "Ready for Railway"
git remote add origin https://github.com/tu-usuario/tu-repo.git
git push -u origin main
```

### PASO 3: Railway Deploy (2 min)

1. railway.app → Dashboard
2. New Project → Deploy from GitHub
3. Selecciona tu repo
4. Railway inicia build

### PASO 4: Variables (2 min)

1. Railway Dashboard → Variables
2. Agrega 3 variables
3. Auto-redeploy (30-60s)

### PASO 5: Verificar (3 min)

1. Espera status: ✅ Running
2. Accede: https://tu-url/login
3. Prueba bot en Telegram

---

## 📚 DOCUMENTACIÓN RÁPIDA

| Necesito | Ver |
|----------|-----|
| Tutorial paso a paso | RAILWAY_PASO_A_PASO.md |
| Cómo obtener variables | VARIABLES_RAILWAY.md |
| Validar cada paso | RAILWAY_CHECKLIST.md |
| Error en deploy | RAILWAY_GUIA_COMPLETA.md |
| Todo sobre Railway | RAILWAY_COMIENZA_AQUI.md |

---

## ⚡ ULTRA-RÁPIDO (2 min)

```
3 variables + 4 pasos = LISTO ✅
```

Detalles: START_RAILWAY_AQUI.txt
