# 🤖 Telegram Media Downloader Bot

Bot de Telegram profesional para descargar contenido multimedia de canales privados con sistema de **estrellas interno** para control de acceso.

## 📋 Características

### ⭐ Sistema de Estrellas
- Cada descarga cuesta **1 estrella** ⭐
- Las estrellas son otorgadas por el administrador
- Balance visible en todo momento

### 🆓 Límites Gratuitos
- ✅ 10 fotos diarias (sin usar estrellas)
- ✅ 3 videos totales (sin usar estrellas)
- ❌ Música bloqueada (solo Premium)
- ❌ APK bloqueados (solo Premium)

### 💎 Plan Premium
- ✅ Fotos ilimitadas
- ✅ 50 videos diarios
- ✅ 50 canciones diarias
- ✅ 50 APK diarios
- ⏰ Duración configurable por admin

### 🎯 Funcionalidades
- Descarga de fotos, videos, música y APK de canales privados
- Sistema de límites diarios con reseteo automático cada 24h
- Sistema de estrellas interno (sin pagos externos)
- Comando `/addstars` para que admin otorgue estrellas
- Detección automática de tipo de contenido
- Interfaz profesional con diseño intuitivo
- Estadísticas de uso personal y global
- Guía de uso integrada

---

## 🏗️ Arquitectura del Proyecto

```
.
├── bot_with_paywall.py    # Bot principal de Telegram (ejecutar este)
├── database.py            # Gestión de base de datos SQLite
├── requirements.txt       # Dependencias Python
├── .gitignore            # Archivos ignorados por Git
├── .env.example          # Plantilla de variables de entorno
└── README.md             # Este archivo
```

---

## 🚀 Instalación y Ejecución

### 1. Requisitos Previos
- Python 3.8 o superior
- Cuenta de Telegram
- API credentials de Telegram (Bot Token, API ID, API Hash)

### 2. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/telegram-bot-downloader.git
cd telegram-bot-downloader
```

### 3. Crear Entorno Virtual
```bash
python -m venv .venv

# Linux/Mac
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 4. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 5. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# ==========================================
# TELEGRAM BOT CREDENTIALS
# ==========================================
TELEGRAM_BOT_TOKEN=tu_bot_token_de_@BotFather
TELEGRAM_API_ID=tu_api_id_de_my.telegram.org
TELEGRAM_API_HASH=tu_api_hash_de_my.telegram.org
TELEGRAM_SESSION_STRING=tu_session_string_de_telethon

# ==========================================
# ADMIN CONFIGURATION
# ==========================================
ADMIN_ID=123456789  # Tu user ID de Telegram (para usar /addstars)
```

### 6. Obtener Credenciales de Telegram

#### A. Bot Token
1. Abre [@BotFather](https://t.me/BotFather) en Telegram
2. Envía `/newbot`
3. Sigue las instrucciones
4. Copia el **Bot Token**

#### B. API ID y API Hash
1. Ve a [https://my.telegram.org](https://my.telegram.org)
2. Inicia sesión con tu número de teléfono
3. Ve a "API development tools"
4. Crea una aplicación
5. Copia **API ID** y **API Hash**

#### C. Session String
1. Ejecuta el generador de sesión:
```bash
python -c "from telethon.sync import TelegramClient; from telethon.sessions import StringSession; import os; client = TelegramClient(StringSession(), int(os.getenv('TELEGRAM_API_ID')), os.getenv('TELEGRAM_API_HASH')); client.start(); print('Session String:', client.session.save())"
```
2. Ingresa tu número de teléfono
3. Ingresa el código de verificación
4. Copia el **Session String**

#### D. Admin ID (Tu User ID)
1. Abre [@userinfobot](https://t.me/userinfobot) en Telegram
2. Envía `/start`
3. El bot te mostrará tu **User ID**
4. Usa ese número en `ADMIN_ID`

### 7. Ejecutar el Bot

```bash
python bot_with_paywall.py
```

El bot estará corriendo en modo polling (no necesita servidor web).

---

## 📖 Uso del Bot

### Comandos Disponibles

#### Para Usuarios:
- `/start` - Menú principal y balance de estrellas
- `/premium` - Ver balance de estrellas y información
- `/stats` - Ver estadísticas personales y del bot
- `/help` - Guía de uso completa

#### Para Administradores:
- `/addstars <user_id> <cantidad>` - Agregar estrellas a un usuario
  - Ejemplo: `/addstars 123456789 10`

### Flujo de Uso

1. **Usuarios Nuevos**: Tienen 3 videos gratis y 10 fotos diarias
2. **Después del límite**: Necesitan estrellas para descargar
3. **Obtener Estrellas**: Contactar al admin, quien usa `/addstars`
4. **Descargas**: Cada descarga después del límite consume 1 ⭐

### Ejemplo de Descarga

```
Usuario: https://t.me/canal_privado/123
Bot: 📤 Enviando...
Bot: ✅ Descarga Completada
     💰 Balance: 9 ⭐
```

---

## 🔧 Configuración Avanzada

### Modificar Costos y Límites

Edita `bot_with_paywall.py`:

```python
# Línea ~60-65
STARS_PER_DOWNLOAD = 1  # Costo por descarga
FREE_DOWNLOAD_LIMIT = 3  # Videos gratis
FREE_PHOTO_DAILY_LIMIT = 10  # Fotos diarias gratis
```

### Base de Datos

El bot usa SQLite (`users.db`). Esquema:

```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    downloads INTEGER DEFAULT 0,
    premium INTEGER DEFAULT 0,
    premium_level INTEGER DEFAULT 0,
    premium_until TIMESTAMP DEFAULT NULL,
    daily_photo INTEGER DEFAULT 0,
    daily_video INTEGER DEFAULT 0,
    daily_music INTEGER DEFAULT 0,
    daily_apk INTEGER DEFAULT 0,
    stars INTEGER DEFAULT 0,
    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🐛 Solución de Problemas

### Error: "Missing required environment variables"
- Verifica que `.env` existe y tiene todas las variables
- Asegúrate de que los valores no tengan espacios extras

### Error: Session String inválido
- Regenera el Session String con el script del paso 6C
- Asegúrate de usar el mismo API_ID y API_HASH

### Bot no responde
- Verifica que el bot esté corriendo (`python bot_with_paywall.py`)
- Revisa los logs en consola para ver errores

### Usuario no puede descargar
- Verifica su balance con `/addstars <user_id> 0` (no agrega, solo verifica)
- El admin puede agregar estrellas con `/addstars <user_id> <cantidad>`

---

## 📦 Estructura de Archivos

```
bot-descargar-contenido/
│
├── bot_with_paywall.py      # 🤖 Bot principal (EJECUTAR ESTE)
├── database.py               # 💾 Funciones de base de datos
├── requirements.txt          # 📋 Dependencias Python
├── .env                      # 🔒 Variables de entorno (NO SUBIR A GIT)
├── .env.example              # 📄 Plantilla de variables
├── .gitignore                # 🚫 Archivos ignorados por Git
├── users.db                  # 💾 Base de datos (generado automáticamente)
└── README.md                 # 📖 Esta documentación
```

---

## 🔐 Seguridad

- **NUNCA** subas `.env` a GitHub
- **NUNCA** subas `users.db` a GitHub  
- `.gitignore` ya los protege
- Guarda backups de `users.db` regularmente

---

## 📝 Cambios Respecto a Versión Anterior

### ❌ Eliminado:
- ❌ Sistema de pagos PayPal
- ❌ Sistema de pagos Telegram Stars (nativo)
- ❌ Backend FastAPI (`backend_paypal.py`, `run_backend.py`)
- ❌ Servidor web HTTP
- ❌ Dependencias: `fastapi`, `uvicorn`, `requests`

### ✅ Agregado:
- ✅ Sistema de estrellas interno (SQLite)
- ✅ Comando `/addstars` para administradores
- ✅ Balance de estrellas visible en `/start` y `/premium`
- ✅ Funciones: `get_stars()`, `add_stars()`, `remove_stars()`
- ✅ Bot 100% autónomo (solo polling, sin servidor)

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto es de código abierto bajo licencia MIT.

---

## 💬 Soporte

Si tienes problemas o preguntas:

- 📢 Canal oficial: [@observer_bots](https://t.me/observer_bots)
- 🐛 Reporta bugs en GitHub Issues
- 💡 Sugiere features en GitHub Discussions

---

## ⭐ Roadmap Futuro

- [ ] Comando `/mystars` para usuarios ver su balance
- [ ] Historial de transacciones de estrellas
- [ ] Sistema de referidos (ganar estrellas)
- [ ] Panel web de administración
- [ ] Backup automático de base de datos
- [ ] Soporte multi-idioma

---

**Hecho con ❤️ por la comunidad de Telegram**
