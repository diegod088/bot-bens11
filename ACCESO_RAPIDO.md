# 🎯 ACCESO RÁPIDO A SERVICIOS

## URLs de Acceso Directo

| Servicio | URL | Estado |
|----------|-----|--------|
| **Dashboard** | http://localhost:5000 | ✅ Activo |
| **MiniApp** | http://localhost:5000/miniapp | ✅ Activo |
| **Bot Telegram** | @tu_bot_username | ✅ Escuchando |

---

## 📊 DASHBOARD

**Acceso:** http://localhost:5000

### Funcionalidades:
- Ver estadísticas de usuarios
- Gestionar planes premium
- Monitoreo del sistema
- Exportar datos
- Panel de administración completo

**Autenticación:** Requiere ADMIN_TOKEN (desde .env)

---

## 📱 MINIAPP

**Acceso:** http://localhost:5000/miniapp

### Features:
- ✅ Visualizar planes premium
- ✅ Sistema de referidos
- ✅ Estadísticas personales
- ✅ Realizar pagos con Telegram Stars
- ✅ Soporte en 3 idiomas (ES, EN, PT)

**Nota:** Mejor experiencia desde el bot de Telegram

---

## 🤖 BOT TELEGRAM

### Cómo usar:
1. Abre Telegram
2. Busca tu bot por nombre de usuario
3. Inicia conversación con `/start`

### Comandos principales:
```
/start          - Inicia el bot
/panel          - Panel de usuario
/premium        - Ver planes
/miniapp        - Abrir app web
/stats          - Ver estadísticas
/referidos      - Sistema de referidos
```

---

## 🔧 Solución de Problemas Rápida

### Dashboard no carga
```bash
curl http://localhost:5000/health
```

### MiniApp no responde
```bash
curl http://localhost:5000/miniapp | head -1
```

### Bot no responde
```bash
tail -f /tmp/bot.log | grep ERROR
```

### Reiniciar todo
```bash
pkill -f "python"
sleep 3
cd "/home/yadied/Escritorio/bot descargar contenido"
source .venv/bin/activate
python dashboard.py > /tmp/dashboard.log 2>&1 &
sleep 2
python run_bot.py > /tmp/bot.log 2>&1 &
```

---

## 📍 URLs Rápidas para Copiar/Pegar

```
Dashboard:  http://localhost:5000
MiniApp:    http://localhost:5000/miniapp
Health:     http://localhost:5000/health
API User:   http://localhost:5000/api/miniapp/user
API Stats:  http://localhost:5000/api/miniapp/stats
```

---

**Última verificación:** 7 de enero de 2026  
**Todos los servicios:** ✅ FUNCIONALES
