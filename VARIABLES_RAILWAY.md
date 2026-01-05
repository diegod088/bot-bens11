# 🔑 VARIABLES DE ENTORNO PARA RAILWAY

## Requeridas (OBLIGATORIAS)

### 1. TELEGRAM_BOT_TOKEN
- **Dónde obtener:** @BotFather en Telegram
- **Pasos:**
  1. Abre Telegram
  2. Busca @BotFather
  3. Envía `/start`
  4. Envía `/newbot`
  5. Elige nombre (ej: "Mi Bot")
  6. Elige usuario (ej: "mi_bot_123")
  7. Copias el token: `123456:ABC-DEF-...`

- **Ejemplo:**
  ```
  TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklmnopQRSt-uvwxyz_1234567
  ```

- **Validación:** Debe tener número, `:`, y después caracteres

---

### 2. ADMIN_PASSWORD
- **Qué es:** Contraseña para acceder al dashboard
- **Cómo crear:** Inventar (mínimo 8 caracteres)
- **Recomendación:** Usar números + letras + símbolos

- **Ejemplo:**
  ```
  ADMIN_PASSWORD=MiPassword123!
  ```

- **Uso:** En el login del dashboard
  ```
  Usuario: admin
  Contraseña: MiPassword123!
  ```

---

### 3. SECRET_KEY
- **Qué es:** Clave secreta para sesiones Flask
- **Cómo generar:**

```python
# Opción 1: En Python
import secrets
print(secrets.token_urlsafe(32))

# Opción 2: En Linux/Mac
openssl rand -hex 32

# Opción 3: Online (NO RECOMENDADO para producción)
# https://tools.owasp.org/secrets.html
```

- **Ejemplo:**
  ```
  SECRET_KEY=5L8vK2mP9qR3xW7yZ1nT6jB4dF0hG_u-vXsYaBcDeF
  ```

---

## Opcionales (RECOMENDADAS)

### PORT (Puerto)
- **Default:** 5000
- **Cambiar si necesitas:**
  ```
  PORT=8000
  ```
- **Nota:** Railway asigna automáticamente

### HOST (Host)
- **Default:** 0.0.0.0
- **No cambiar para Railway**

---

## 📋 CÓMO CONFIGURARLAS EN RAILWAY

### Vía Web Dashboard:

1. **Railway.app** → Tu proyecto
2. **Click en tu servicio**
3. **Pestaña: Variables**
4. **Click: Add Variable**
5. **Llenar:**
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: `1234567890:ABC...`
6. **Click: Add Variable** (repetir para cada una)

### Resultado esperado:
```
✅ TELEGRAM_BOT_TOKEN = 1234567890:ABC...
✅ ADMIN_PASSWORD = MiPassword123!
✅ SECRET_KEY = 5L8vK2mP9qR3xW7yZ1nT6jB4dF0hG_u...
```

---

## 🧪 VALIDAR VARIABLES

### En Railway Logs:
```
✅ Database initialized
🤖 Bot starting...
🌐 Dashboard starting on 0.0.0.0:5000
```

### Si algo falla:
```
❌ TELEGRAM_BOT_TOKEN not found
❌ Database error: ...
❌ Bot error: ...
```

---

## ⚠️ SEGURIDAD

### DO's ✅
- Usar contraseña diferente para producción
- Regenerar SECRET_KEY cada vez
- Cambiar ADMIN_PASSWORD periodicamente
- Nunca compartir TELEGRAM_BOT_TOKEN

### DON'Ts ❌
- No poner variables en código
- No compartir en GitHub
- No usar password simples
- No reutilizar SECRET_KEY de test

---

## 🔄 ACTUALIZAR VARIABLES

### Si cambias una variable:
1. Railway Dashboard → Variables
2. Edita el valor
3. **Auto-redeploy en 30-60 segundos**

No necesitas hacer push a GitHub

---

## 📝 CHECKLIST

- [ ] TELEGRAM_BOT_TOKEN obtenido de @BotFather
- [ ] ADMIN_PASSWORD creada (8+ caracteres)
- [ ] SECRET_KEY generada
- [ ] Variables agregadas en Railway Dashboard
- [ ] Logs muestran ✅ inicialización
- [ ] Dashboard accesible con la contraseña
- [ ] Bot responde en Telegram

---

**Total: 3 variables requeridas** 🔑

**¿Dudas?** Ver RAILWAY_PASO_A_PASO.md
