# 🚀 GUÍA DE SERVICIOS ACTIVOS

## ✅ ESTADO ACTUAL

| Servicio | Estado | URL | Función |
|----------|--------|-----|---------|
| 🤖 Bot Telegram | ✅ Ejecutándose | [@bot_username](https://t.me/bot_username) | Descarga + Pagos |
| 📊 Dashboard | ✅ Ejecutándose | http://localhost:5000 | Panel Admin |
| 📱 MiniApp | ✅ Disponible | http://localhost:5000/miniapp | WebApp embebida |

---

## 🔗 ACCESO RÁPIDO

### Bot Telegram
- **Descripción**: Bot principal para descargar contenido de Telegram
- **Funciones**:
  - Descarga de videos, fotos, música, APK
  - Compra de planes Premium con Telegram Stars
  - Sistema de referidos
  - Múltiples idiomas (ES, EN, PT)

### Dashboard Admin
- **URL**: http://localhost:5000
- **Función**: Panel de administración del bot
- **Características**:
  - Ver estadísticas de usuarios
  - Gestionar planes premium
  - Monitoreo del sistema
  - Exportar datos
- **Autenticación**: ADMIN_TOKEN

### MiniApp
- **URL**: http://localhost:5000/miniapp
- **Función**: Aplicación web embebida en Telegram
- **Características**:
  - Ver planes premium
  - Sistema de referidos
  - Estadísticas personales
  - Soporte multiidioma

---

## 📋 COMANDOS DEL BOT

```
/start          - Inicia el bot y muestra menú principal
/panel          - Panel de control del usuario
/premium        - Información de planes premium
/miniapp        - Abre la aplicación web embebida
/stats          - Muestra estadísticas de uso
/referidos      - Sistema de referidos
/adminstats     - Estadísticas (solo admin)
/testpay        - Prueba de pagos (desarrollo)
/configurar     - Configurar cuenta de Telegram
/logout         - Cerrar sesión
```

---

## 🛠️ COMANDOS DE TERMINAL

### Ver Logs
```bash
# Bot
tail -f /tmp/bot.log

# Dashboard  
tail -f dashboard.log

# Ambos en tiempo real
watch -n 1 'tail -5 /tmp/bot.log && echo "---" && tail -5 dashboard.log'
```

### Controlar Servicios
```bash
# Detener bot
pkill -f 'python run_bot.py'

# Detener dashboard
pkill -f 'python dashboard.py'

# Detener todo
pkill -f 'python'

# Ver procesos activos
ps aux | grep -E 'run_bot|dashboard' | grep -v grep
```

### Reiniciar Servicios
```bash
# Detener todo
pkill -f 'python'

# Esperar un poco
sleep 2

# Reiniciar
cd "/home/yadied/Escritorio/bot descargar contenido"
source .venv/bin/activate
python run_bot.py > /tmp/bot.log 2>&1 &
python dashboard.py > /tmp/dashboard.log 2>&1 &

echo "✅ Servicios reiniciados"
```

### Verificar Estado
```bash
# Verificar dashboard
curl -s http://localhost:5000/health | jq .

# Verificar puerto 5000 en uso
lsof -i :5000

# Ver puertos abiertos
netstat -tlnp | grep python
```

---

## 🔐 VARIABLES DE ENTORNO REQUERIDAS

```bash
# Bot
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_API_ID=tu_api_id
TELEGRAM_API_HASH=tu_api_hash

# Seguridad
ENCRYPTION_KEY=tu_clave_encriptacion
ADMIN_TOKEN=tu_token_admin

# Dashboard
DASHBOARD_SECRET_KEY=tu_clave_secreta
PORT=5000
HOST=0.0.0.0
```

---

## 📊 ESTRUCTURA DE ARCHIVOS

```
bot descargar contenido/
├── run_bot.py              # Ejecutor del bot
├── bot_with_paywall.py     # Lógica principal del bot
├── dashboard.py            # Panel de administración
├── database.py             # Gestor de base de datos
├── messages.py             # Mensajes multiidioma
├── miniapp/                # Aplicación web embebida
│   ├── index.html
│   └── static/
├── templates/              # Plantillas del dashboard
│   ├── dashboard.html
│   ├── login.html
│   ├── users.html
│   └── ...
├── users.db                # Base de datos SQLite
└── requirements.txt        # Dependencias Python
```

---

## 🎯 FLUJO DE USO TÍPICO

1. **Usuario envía mensaje al bot**
   → Bot recibe el mensaje
   → Procesa la descarga
   → Envía el archivo

2. **Usuario abre miniapp**
   → Se abre http://localhost:5000/miniapp
   → Usuario ve planes y referidos
   → Puede realizar compras

3. **Admin accede al dashboard**
   → Va a http://localhost:5000
   → Se autentica con ADMIN_TOKEN
   → Ve estadísticas y gestiona usuarios

---

## ⚠️ SOLUCIÓN DE PROBLEMAS

### Bot no recibe mensajes
```bash
# Verificar logs
tail -f /tmp/bot.log | grep ERROR

# Verificar conflicto 409
# (Normal si hay otra instancia ejecutándose)
```

### Dashboard no accesible
```bash
# Verificar puerto
lsof -i :5000

# Verificar error en logs
tail -f dashboard.log | grep ERROR

# Reiniciar
pkill -f 'python dashboard.py'
sleep 2
python dashboard.py &
```

### Errores de base de datos
```bash
# Resetear BD (⚠️ BORRA TODOS LOS DATOS)
rm users.db

# Reiniciar bot para recrear BD
pkill -f 'python run_bot.py'
sleep 2
python run_bot.py &
```

---

## 📈 MONITOREO

### Ver uso de recursos
```bash
# CPU y memoria del bot
ps aux | grep 'run_bot' | grep -v grep

# Ver todas las conexiones Python
netstat -tlnp | grep python

# Monitor en tiempo real
top -p $(pgrep -f 'python run_bot')
```

### Estadísticas del bot
```bash
# En el dashboard
http://localhost:5000/adminstats

# O enviar comando al bot
/adminstats
```

---

## 🔄 ACTUALIZACIÓN DE CÓDIGO

```bash
# 1. Detener servicios
pkill -f 'python'

# 2. Hacer cambios en el código

# 3. Reiniciar servicios
cd "/home/yadied/Escritorio/bot descargar contenido"
source .venv/bin/activate
python run_bot.py > /tmp/bot.log 2>&1 &
python dashboard.py > /tmp/dashboard.log 2>&1 &
```

---

**Última actualización**: 7 de enero de 2026  
**Versión**: 1.0 - Todas los servicios operativos
