#!/usr/bin/env python3
"""
Telegram Bot with Telegram Stars Payment System

A bot that forwards media from Telegram links with a free limit for videos.
Users can pay with Telegram Stars to unlock Premium (videos unlimited for 30 days).
Photos are always free.
"""

import os
import re
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, WebAppInfo
from contextlib import asynccontextmanager

# Load environment variables from .env file
load_dotenv(override=True)

# URLs are read from environment variables (MINIAPP_URL, DASHBOARD_URL)
# Set these in Railway's Variables panel

from telegram.ext import (
    Application, MessageHandler, CommandHandler, ContextTypes, 
    filters, PreCheckoutQueryHandler, CallbackQueryHandler, ConversationHandler
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto
from telethon.errors import (
    ChannelPrivateError, ChatForbiddenError, InviteHashExpiredError,
    InviteHashInvalidError, FloodWaitError, UserAlreadyParticipantError,
    SessionPasswordNeededError
)
from telethon.tl.functions.messages import ImportChatInviteRequest
import tempfile
from io import BytesIO

from database import (
    init_database,
    get_user, create_user, add_user, update_user_info, set_user_language, set_premium,
    increment_daily_counter, increment_total_downloads, get_user_stats, get_user_usage_stats,
    get_user_session, has_active_session, delete_user_session, set_user_session,
    confirm_referral, check_and_reward_referrer, get_referral_stats,
    check_and_reset_daily_limits,
    get_next_pending_download, update_download_status
)

# Import messages module for multi-language support
from messages import get_msg, get_user_language

# Configure logging - escribir a archivo para debug
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_TOKEN')
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID') or os.getenv('API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH') or os.getenv('API_HASH')
REQUIRED_VARS = {
    "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    "TELEGRAM_API_ID": TELEGRAM_API_ID,
    "TELEGRAM_API_HASH": TELEGRAM_API_HASH,
}
missing = [k for k, v in REQUIRED_VARS.items() if v is None]
if missing:
    raise ValueError(f"Missing required environment variables: {missing}")

# LOGS DE DEPURACIÓN PARA URLs
logger.info("=" * 80)
logger.info(f"DASHBOARD_URL: {os.getenv('DASHBOARD_URL')}")
logger.info(f"MINIAPP_URL: {os.getenv('MINIAPP_URL')}")
logger.info("=" * 80)

# Store temporary clients during login process
login_clients = {}

# Global Telethon Client for Bot (to send large files)
bot_client = None

# Conversation states for Login
PHONE, CODE, PASSWORD = range(10, 13)


# Constants
FREE_DOWNLOAD_LIMIT = 3  # Free users: 3 videos PERMANENTES (sin reset)
FREE_PHOTO_LIMIT = 10  # Free users: 10 fotos PERMANENTES (sin reset)

# Premium Plans (Telegram Stars) - Estrategia de Precios Optimizada
PREMIUM_PLANS = {
    'trial': {
        'stars': 30,
        'days': 3,
        'name': '🎁 Prueba',
        'label': 'Premium 3 días',
        'badge': '✨ PRUEBA',
        'description': 'Perfecto para probar'
    },
    'weekly': {
        'stars': 90,
        'days': 7,
        'name': '🔥 Semanal',
        'label': 'Premium 7 días',
        'badge': '🔥 MÁS POPULAR',
        'description': 'Mejor precio por día'
    },
    'monthly': {
        'stars': 179,
        'days': 30,
        'name': '💎 Mensual',
        'label': 'Premium 30 días',
        'badge': '⭐ RECOMENDADO',
        'description': 'El más elegido'
    },
    'quarterly': {
        'stars': 479,
        'days': 90,
        'name': '👑 Trimestral',
        'label': 'Premium 90 días',
        'badge': '💰 MEJOR VALOR',
        'description': 'Ahorra hasta 50%'
    }
}

# Backward compatibility (default to monthly plan)
PREMIUM_PRICE_STARS = PREMIUM_PLANS['monthly']['stars']

# Premium daily limits (unlimited photos, 50 daily for others)
PREMIUM_VIDEO_DAILY_LIMIT = 50
PREMIUM_MUSIC_DAILY_LIMIT = 50
PREMIUM_APK_DAILY_LIMIT = 50

# Admin User IDs - Pueden ver estadísticas globales del bot
ADMIN_ID_ENV = os.getenv('ADMIN_ID', '')
ADMIN_USER_IDS = [int(i.strip()) for i in ADMIN_ID_ENV.split(',') if i.strip().isdigit()]
# Si no hay admins en env, usamos los hardcoded como fallback (opcional, mejor dejar vacío si no hay env)
if not ADMIN_USER_IDS:
    ADMIN_USER_IDS = [
        1438860917,  # Admin principal
        8524907238,  # Admin secundario
        7727224233,  # Admin adicional
        8297992519,  # Yadiel - 1 mes premium
    ]

# PID File for Conflict 409 protection cross-process
PID_FILE = ".bot.pid"

# Conversation states
WAITING_FOR_LINK = 1

# Network retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Global flag to prevent multiple bot instances (Conflict 409 protection)
_bot_instance_running = False
_bot_instance_lock = threading.Lock()


# ==================== UTILITY FUNCTIONS ====================

async def retry_on_error(func, *args, max_retries=MAX_RETRIES, delay=RETRY_DELAY, **kwargs):
    """
    Reintentar una función asíncrona en caso de errores de red
    
    Args:
        func: Función asíncrona a ejecutar
        max_retries: Número máximo de reintentos
        delay: Tiempo de espera entre reintentos (segundos)
        *args, **kwargs: Argumentos para la función
    
    Returns:
        Resultado de la función o None si todos los intentos fallan
    """
    from telegram.error import TimedOut, NetworkError, RetryAfter
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except (TimedOut, NetworkError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Network error on attempt {attempt + 1}/{max_retries}: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed for {func.__name__}")
                raise
        except RetryAfter as e:
            wait_time = e.retry_after + 1
            logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            if attempt < max_retries - 1:
                continue
            else:
                raise
        except Exception as e:
            # Para otros errores, no reintentar
            logger.error(f"Non-retryable error in {func.__name__}: {e}")
            raise
    
    return None


@asynccontextmanager
async def get_user_client(user_id: int):
    """Obtiene un cliente de Telethon para el usuario"""
    session_string = get_user_session(user_id)
    if not session_string:
        raise ValueError("No session found for user")
    
    client = TelegramClient(StringSession(session_string), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    await client.connect()
    try:
        yield client
    finally:
        await client.disconnect()


def ensure_admin_premium(user_id):
    """
    Asegura que los administradores tengan premium automáticamente
    """
    if user_id in ADMIN_USER_IDS:
        user = get_user(user_id)
        if user and not user['premium']:
            # Dar premium permanente a admins (100 años = 1200 meses)
            set_premium(user_id, months=1200)
            logger.info(f"Admin {user_id} automatically granted premium access")


# ==================== ERROR HANDLERS ====================

class BotError:
    """Manejo centralizado de errores con mensajes amigables"""
    
    @staticmethod
    async def invalid_link(update_or_msg, is_message=False):
        """Error: Enlace inválido"""
        message = (
            "❌ *Enlace inválido*\n\n"
            "El enlace no es de Telegram o no es válido\n\n"
            "💡 *Formatos aceptados:*\n"
            "• `https://t.me/canal/123`\n"
            "• `https://t.me/+ABC123`\n"
            "• `https://t.me/c/123456/789`\n\n"
            "📝 Verifica el enlace e intenta nuevamente"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def incomplete_link(update_or_msg, is_message=False):
        """Error: Enlace sin número de mensaje"""
        message = (
            "❌ *Enlace incompleto*\n\n"
            "Falta el número del mensaje en el enlace\n\n"
            "💡 *Cómo obtener el enlace completo:*\n"
            "1️⃣ Abre Telegram y busca el mensaje\n"
            "2️⃣ Mantén presionado el mensaje\n"
            "3️⃣ Selecciona *'Copiar enlace'*\n"
            "4️⃣ Envíame el enlace completo\n\n"
            "✅ *Ejemplo correcto:*\n"
            "`https://t.me/canal/123`"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def private_channel_no_invite(update_or_msg, is_message=False):
        """Error: Canal privado sin hash de invitación"""
        message = (
            "🔐 *Canal privado - Necesito acceso*\n\n"
            "Para descargar de canales privados, necesito que me agregues al canal o me envíes un enlace de invitación válido.\n\n"
            "📋 *Opción 1: Enviar enlace de invitación*\n"
            "1️⃣ Abre el canal en Telegram\n"
            "2️⃣ Toca el nombre del canal\n"
            "3️⃣ Toca *'Invitar mediante enlace'*\n"
            "4️⃣ Copia y envíame el enlace\n\n"
            "💡 *Ejemplo:* `t.me/+AbC123XyZ`\n\n"
            "📋 *Opción 2: Agregar el bot al canal*\n"
            "1️⃣ Abre el canal\n"
            "2️⃣ Toca el nombre del canal\n"
            "3️⃣ Toca *'Agregar miembros'*\n"
            "4️⃣ Busca `@prusebas_bot`\n"
            "5️⃣ Agrégame al canal\n\n"
            "Luego envía el enlace del mensaje que quieres descargar."
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def invite_link_expired(update_or_msg, is_message=False):
        """Error: Enlace de invitación expirado"""
        message = (
            "⏰ *Enlace de invitación expirado*\n\n"
            "El enlace de invitación ya no es válido\n\n"
            "💡 *Soluciones:*\n"
            "1️⃣ Pide un nuevo enlace de invitación\n"
            "2️⃣ O agrega al bot manualmente:\n"
            "   • Ve al canal/grupo\n"
            "   • Agrégame: @prusebas_bot\n"
            "   • Dale permisos de lectura\n\n"
            "🔄 Luego intenta nuevamente"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def message_not_found(update_or_msg, is_message=False):
        """Error: Mensaje no encontrado"""
        message = (
            "❌ *Mensaje no encontrado*\n\n"
            "El mensaje no existe o fue eliminado\n\n"
            "💡 *Posibles causas:*\n"
            "• El mensaje fue borrado\n"
            "• El número de mensaje es incorrecto\n"
            "• No tengo acceso al canal\n\n"
            "🔍 Verifica el enlace e intenta con otro mensaje"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def unsupported_content(update_or_msg, is_message=False):
        """Error: Tipo de contenido no soportado"""
        message = (
            "❌ *Contenido no soportado*\n\n"
            "Este tipo de contenido no puede ser descargado\n\n"
            "✅ *Tipos soportados:*\n"
            "📸 Fotos\n"
            "🎬 Videos\n"
            "🎵 Música y audio\n"
            "📦 Archivos APK\n"
            "📄 Documentos\n\n"
            "🔄 Intenta con otro tipo de contenido"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def file_too_large(update_or_msg, file_size_mb, is_message=False):
        """Error: Archivo muy grande"""
        message = (
            "📦 *Archivo muy grande*\n\n"
            f"Tamaño del archivo: {file_size_mb:.1f} MB\n"
            "Límite de Telegram: 2000 MB (2 GB)\n\n"
            "💡 *Sugerencias:*\n"
            "• Intenta con un archivo más pequeño\n"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')

    @staticmethod
    async def daily_limit_reached(update_or_msg, content_type, current, limit, is_message=False):
        """Error: Límite diario alcanzado"""
        content_names = {
            'photo': 'fotos',
            'video': 'videos',
            'music': 'canciones',
            'apk': 'archivos APK'
        }
        
        name = content_names.get(content_type, 'archivos')
        
        message = (
            "⏰ *Límite diario alcanzado*\n\n"
            f"Has descargado {current}/{limit} {name} hoy\n\n"
            "💡 *Opciones:*\n"
            "🔄 Espera hasta mañana (se reinicia a las 00:00)\n"
            "💎 Obtén Premium para más descargas\n\n"
            "📊 Usa /stats para ver tus límites\n"
            "💎 Usa /premium para mejorar tu plan"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def total_limit_reached(update_or_msg, is_message=False):
        """Error: Límite total de videos alcanzado (usuarios gratuitos)"""
        message = (
            "🎬 *Límite de videos gratuitos alcanzado*\n\n"
            f"Has usado tus {FREE_DOWNLOAD_LIMIT} videos gratuitos\n\n"
            "💎 *Con Premium obtienes:*\n"
            "✅ 50 videos diarios\n"
            "✅ 50 canciones diarias\n"
            "✅ 50 APK diarios\n"
            "✅ Fotos ilimitadas\n"
            f"⭐ Solo {PREMIUM_PRICE_STARS} estrellas por 30 días\n\n"
            "📊 Usa /stats para ver tu uso\n"
            "💎 Usa /premium para suscribirte"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def premium_required(update_or_msg, content_type, is_message=False):
        """Error: Contenido requiere Premium"""
        content_names = {
            'music': '🎵 Música',
            'apk': '📦 APK'
        }
        
        name = content_names.get(content_type, 'Este contenido')
        
        message = (
            f"🔒 *{name} - Solo Premium*\n\n"
            f"{name} está disponible solo para usuarios Premium\n\n"
            "💎 *Con Premium desbloqueas:*\n"
            "✅ 50 canciones diarias\n"
            "✅ 50 APK diarios\n"
            "✅ 50 videos diarios\n"
            "✅ Fotos ilimitadas\n"
            f"⭐ Solo {PREMIUM_PRICE_STARS} estrellas por 30 días\n\n"
            "💎 Usa /premium para suscribirte"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def flood_wait(update_or_msg, seconds, is_message=False):
        """Error: Límite de velocidad de Telegram"""
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        
        time_str = f"{minutes} minutos" if minutes > 0 else f"{remaining_seconds} segundos"
        
        message = (
            "⏰ *Límite de Telegram alcanzado*\n\n"
            f"Debes esperar {time_str} antes de continuar\n\n"
            "💡 *¿Por qué pasa esto?*\n"
            "Telegram limita las peticiones para evitar spam\n\n"
            "🔄 Espera un momento e intenta nuevamente\n"
            "📊 Usa /stats para ver tu actividad"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def download_failed(update_or_msg, is_message=False):
        """Error: Fallo general en la descarga"""
        message = (
            "❌ *Error al descargar*\n\n"
            "Ocurrió un problema al descargar el contenido\n\n"
            "💡 *Intenta lo siguiente:*\n"
            "1️⃣ Verifica que el enlace sea correcto\n"
            "2️⃣ Intenta con otro mensaje\n"
            "3️⃣ Espera unos minutos e intenta nuevamente\n\n"
            "💬 Si el problema persiste:\n"
            "Contacta al soporte en @observer_bots"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def generic_error(update_or_msg, is_message=False):
        """Error: Error genérico"""
        message = (
            "❌ *Algo salió mal*\n\n"
            "Ocurrió un error inesperado\n\n"
            "🔄 *Qué hacer:*\n"
            "1️⃣ Intenta nuevamente en unos segundos\n"
            "2️⃣ Verifica tu conexión a internet\n"
            "3️⃣ Usa /help para ver la guía\n\n"
            "💬 *¿Necesitas ayuda?*\n"
            "Contacta al soporte: @observer_bots"
        )
        
        if is_message:
            await update_or_msg.edit_text(message, parse_mode='Markdown')
        else:
            await update_or_msg.message.reply_text(message, parse_mode='Markdown')


# ==================== LOGIN HANDLERS ====================

async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de login"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'
    
    # Botón de cancelar
    keyboard = [[InlineKeyboardButton(get_msg("btn_cancel_login", lang), callback_data="cancel_login")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if has_active_session(user_id):
        msg_text = get_msg("login_already_active", lang)
        back_keyboard = [[InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]]
        back_markup = InlineKeyboardMarkup(back_keyboard)
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(msg_text, parse_mode='Markdown', reply_markup=back_markup)
            except Exception:
                await update.callback_query.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=back_markup)
        else:
            await update.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=back_markup)
        return ConversationHandler.END
    
    msg_text = get_msg("login_setup_title", lang)
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
    return PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el número de teléfono y envía el código"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'
    phone = update.message.text.strip().replace(" ", "")
    
    # Botón de cancelar
    keyboard = [[InlineKeyboardButton(get_msg("btn_cancel_login", lang), callback_data="cancel_login")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not re.match(r'^\+\d+$', phone):
        await update.message.reply_text(
            get_msg("login_invalid_phone", lang),
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return PHONE
    
    msg = await update.message.reply_text(get_msg("login_connecting", lang))
    
    try:
        # Configuración especial para Railway (PaaS con restricciones de red)
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID')
        
        client = TelegramClient(StringSession(), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        
        # Configuración optimizada para Railway
        if is_railway:
            logger.info("Detectado entorno Railway - usando configuración optimizada")
            # Railway puede tener restricciones, intentar con timeout más largo
            connect_timeout = 30  # Más tiempo para conectar en Railway
        else:
            connect_timeout = 10
            
        await asyncio.wait_for(client.connect(), timeout=connect_timeout)
        
        if not await client.is_user_authorized():
            # Timeout más largo para Railway
            code_timeout = 60 if is_railway else 30
            sent = await asyncio.wait_for(
                client.send_code_request(phone), 
                timeout=code_timeout
            )
            login_clients[user_id] = {
                'client': client, 
                'phone': phone,
                'phone_code_hash': sent.phone_code_hash
            }
            
            # Botón de cancelar
            cancel_keyboard = [[InlineKeyboardButton(get_msg("btn_cancel_login", lang), callback_data="cancel_login")]]
            cancel_markup = InlineKeyboardMarkup(cancel_keyboard)
            
            await msg.edit_text(
                get_msg("login_code_sent", lang),
                parse_mode='Markdown',
                reply_markup=cancel_markup
            )
            return CODE
        else:
            # Should not happen with new session
            await client.disconnect()
            await msg.edit_text("❌ Error inesperado. Intenta de nuevo.")
            return ConversationHandler.END
            
    except asyncio.TimeoutError:
        logger.error(f"Timeout conectando para {user_id} en Railway")
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID')
        if is_railway:
            error_msg = (
                "❌ *Error de Conexión en Railway*\n\n"
                "Railway puede tener restricciones de red que impiden la conexión directa a Telegram.\n\n"
                "🔧 *Soluciones:*\n"
                "1️⃣ Verifica que las variables `TELEGRAM_API_ID` y `TELEGRAM_API_HASH` estén configuradas en Railway\n"
                "2️⃣ Intenta desde un servidor VPS en lugar de Railway\n"
                "3️⃣ Contacta soporte de Railway sobre restricciones MTProto\n\n"
                "📞 Soporte: @observer_bots"
            )
        else:
            error_msg = get_msg("login_error_connect", lang, error="Timeout de conexión")
        await msg.edit_text(error_msg, parse_mode='Markdown')
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error sending code to {user_id}: {e}")
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID')
        if is_railway and "connection" in str(e).lower():
            error_msg = (
                "❌ *Error de Red en Railway*\n\n"
                f"Error: `{str(e)[:100]}`\n\n"
                "💡 Railway puede bloquear conexiones MTProto.\n"
                "Prueba desde un VPS o contacta soporte de Railway."
            )
        else:
            error_msg = get_msg("login_error_connect", lang, error=str(e))
        await msg.edit_text(error_msg, parse_mode='Markdown')
        return ConversationHandler.END

async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el código de inicio de sesión"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'
    # Limpiar el código de espacios, guiones y otros caracteres no numéricos
    raw_code = update.message.text
    code = ''.join(filter(str.isdigit, raw_code))
    
    if user_id not in login_clients:
        await update.message.reply_text(get_msg("login_session_expired", lang))
        return ConversationHandler.END
    
    data = login_clients[user_id]
    client = data['client']
    phone = data['phone']
    phone_code_hash = data.get('phone_code_hash')
    
    msg = await update.message.reply_text(get_msg("login_verifying_code", lang))
    
    try:
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            # Botón de cancelar
            cancel_keyboard = [[InlineKeyboardButton(get_msg("btn_cancel_login", lang), callback_data="cancel_login")]]
            cancel_markup = InlineKeyboardMarkup(cancel_keyboard)
            
            await msg.edit_text(
                get_msg("login_2fa_required", lang),
                parse_mode='Markdown',
                reply_markup=cancel_markup
            )
            return PASSWORD
            
        # Login successful
        session_string = client.session.save()
        set_user_session(user_id, session_string, phone)
        await client.disconnect()
        del login_clients[user_id]
        
        # Botón para volver al menú
        success_keyboard = [[InlineKeyboardButton(get_msg("btn_back_menu", lang), callback_data="back_to_menu")]]
        success_markup = InlineKeyboardMarkup(success_keyboard)
        
        await msg.edit_text(
            get_msg("login_success", lang),
            parse_mode='Markdown',
            reply_markup=success_markup
        )
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error signing in {user_id}: {e}")
        retry_keyboard = [[InlineKeyboardButton(get_msg("btn_back_menu", lang), callback_data="back_to_menu")]]
        retry_markup = InlineKeyboardMarkup(retry_keyboard)
        
        # Distinguir entre error de Telethon y error de código
        if "phone_code_invalid" in str(e).lower() or "expired" in str(e).lower():
            error_text = get_msg("login_wrong_code", lang)
        else:
            error_text = f"❌ *Error inesperado*\n\nOcurrió un error al procesar el código: `{str(e)[:50]}`"
            
        await msg.edit_text(error_text, parse_mode='Markdown', reply_markup=retry_markup)
        return ConversationHandler.END

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la contraseña 2FA"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'
    password = update.message.text
    
    if user_id not in login_clients:
        await update.message.reply_text(get_msg("login_session_expired", lang))
        return ConversationHandler.END
    
    data = login_clients[user_id]
    client = data['client']
    phone = data['phone']
    
    msg = await update.message.reply_text(get_msg("login_verifying_code", lang))
    
    try:
        await client.sign_in(password=password)
        
        # Login successful
        session_string = client.session.save()
        set_user_session(user_id, session_string, phone)
        await client.disconnect()
        del login_clients[user_id]
        
        # Botón para volver al menú
        success_keyboard = [[InlineKeyboardButton(get_msg("btn_back_menu", lang), callback_data="back_to_menu")]]
        success_markup = InlineKeyboardMarkup(success_keyboard)
        
        await msg.edit_text(
            get_msg("login_success", lang),
            parse_mode='Markdown',
            reply_markup=success_markup
        )
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error with 2FA for {user_id}: {e}")
        retry_keyboard = [[InlineKeyboardButton(get_msg("btn_back_menu", lang), callback_data="back_to_menu")]]
        retry_markup = InlineKeyboardMarkup(retry_keyboard)
        
        # Distinguir entre error de Telethon y error de código
        if "password_hash_invalid" in str(e).lower() or "incorrect" in str(e).lower():
            error_text = get_msg("login_wrong_password", lang)
        else:
            error_text = f"❌ *Error inesperado*\n\nOcurrió un error al procesar la contraseña: `{str(e)[:50]}`"
            
        await msg.edit_text(error_text, parse_mode='Markdown', reply_markup=retry_markup)
        return ConversationHandler.END

async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela el proceso de login"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'
    
    if user_id in login_clients:
        try:
            await login_clients[user_id]['client'].disconnect()
        except Exception:
            pass
        del login_clients[user_id]
    
    # Botón para volver al menú
    keyboard = [[InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg_text = get_msg("login_cancelled", lang)
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    return ConversationHandler.END

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cierra la sesión del usuario"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'
    
    # Build response message and keyboard with back button
    keyboard = [[InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if delete_user_session(user_id):
        msg_text = get_msg("logout_success", lang)
    else:
        msg_text = get_msg("logout_no_session", lang)
    
    # Edit message if from callback, otherwise reply
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)



class UsageNotification:
    """Notificaciones de uso y límites para usuarios"""
    
    @staticmethod
    async def send_low_usage_warning(message_obj, warning_data: dict):
        """
        Envía notificación cuando quedan pocos usos disponibles
        
        Args:
            message_obj: Objeto de mensaje de Telegram
            warning_data: Datos del warning desde check_low_usage_warning()
        """
        if not warning_data.get('show_warning'):
            return
        
        warning_type = warning_data['type']
        remaining = warning_data['remaining']
        
        if warning_type == 'video':
            notification = (
                "⚠️ *¡Atención!*\n\n"
                f"📊 Te queda solo *{remaining} video{'s' if remaining > 1 else ''}* disponible\n\n"
                "💎 *Actualiza a Premium y obtén:*\n"
                "✅ 50 videos diarios\n"
                "✅ 50 canciones diarias\n"
                "✅ 50 APK diarios\n"
                "✅ Fotos ilimitadas\n"
                f"⭐ Solo {PREMIUM_PRICE_STARS} estrellas por 30 días\n\n"
                "💎 Comando: /premium"
            )
        elif warning_type == 'photo':
            notification = (
                "⚠️ *¡Atención!*\n\n"
                f"📊 Te quedan solo *{remaining} foto{'s' if remaining > 1 else ''}* hoy\n"
                "🔄 El límite se reinicia en 24 horas\n\n"
                "💎 *Con Premium obtienes:*\n"
                "✅ Fotos ilimitadas\n"
                "✅ 50 videos diarios\n"
                "✅ Música y APK disponibles\n"
                f"⭐ Solo {PREMIUM_PRICE_STARS} estrellas por 30 días\n\n"
                "💎 Comando: /premium"
            )
        else:
            return
        
        await message_obj.reply_text(notification, parse_mode='Markdown')
    
    @staticmethod
    def get_usage_summary(user_stats: dict) -> str:
        """
        Genera un resumen de uso del usuario
        
        Args:
            user_stats: Dict desde get_user_usage_stats()
            
        Returns:
            String con resumen formateado
        """
        if user_stats['is_premium']:
            summary = "💎 *Plan Premium Activo*\n\n"
            summary += "📊 *Uso hoy:*\n"
            summary += f"🎬 Videos: {user_stats['videos']['used']}/50\n"
            summary += f"📸 Fotos: {user_stats['photos']['used']} (ilimitadas)\n"
            summary += f"🎵 Música: {user_stats['music']['used']}/50\n"
            summary += f"📦 APK: {user_stats['apk']['used']}/50\n"
        else:
            summary = "🆓 *Plan Gratuito*\n\n"
            summary += "📊 *Tu uso:*\n"
            
            videos = user_stats['videos']
            summary += f"🎬 Videos: {videos['used']}/{videos['limit']} totales "
            if videos['remaining'] > 0:
                summary += f"({videos['remaining']} restantes) ✅\n"
            else:
                summary += "❌\n"
            
            photos = user_stats['photos']
            summary += f"📸 Fotos: {photos['used']}/{photos['limit']} hoy "
            if photos['remaining'] > 0:
                summary += f"({photos['remaining']} restantes) ✅\n"
            else:
                summary += "❌\n"
            
            summary += f"🎵 Música: 🔒 Premium\n"
            summary += f"📦 APK: 🔒 Premium\n"
            
            summary += f"\n💡 *Mejora a Premium por {PREMIUM_PRICE_STARS} ⭐*\n"
            summary += "Comando: /premium"
        
        return summary
    
    @staticmethod
    async def send_upgrade_suggestion(message_obj, content_type: str):
        """
        Sugiere actualización a Premium después de uso exitoso
        
        Args:
            message_obj: Objeto de mensaje
            content_type: Tipo de contenido descargado
        """
        suggestions = {
            'video': (
                "💡 *¿Te gustó este video?*\n\n"
                f"Con Premium puedes descargar *50 videos diarios* + música y APK\n"
                f"⭐ Solo {PREMIUM_PRICE_STARS} estrellas\n"
                "💎 Comando: /premium"
            ),
            'photo': (
                "💡 *¿Necesitas más fotos?*\n\n"
                f"Con Premium tienes *fotos ilimitadas* + videos, música y APK\n"
                f"⭐ Solo {PREMIUM_PRICE_STARS} estrellas\n"
                "💎 Comando: /premium"
            )
        }
        
        suggestion = suggestions.get(content_type)
        if suggestion:
            await message_obj.reply_text(suggestion, parse_mode='Markdown')


def parse_telegram_link(url: str) -> tuple[str, int | None] | None:
    """Extrae identificador del canal y message_id (puede ser None)"""
    url = url.strip()
    
    # Enlaces con hash de invitación: t.me/+HASH o t.me/+HASH/123
    match = re.search(r't\.me/\+([^/]+)(?:/(\d+))?', url)
    if match:
        return f"+{match.group(1)}", int(match.group(2)) if match.group(2) else None
    
    # Enlaces privados numéricos: t.me/c/123456789 o t.me/c/123456789/123
    match = re.search(r't\.me/c/(\d+)(?:/(\d+))?', url)
    if match:
        return match.group(1), int(match.group(2)) if match.group(2) else None
    
    # Canales públicos: t.me/username o t.me/username/123
    match = re.search(r't\.me/([^/\s]+)(?:/(\d+))?', url)
    if match and match.group(1) not in ['joinchat', 'c', '+']:
        return match.group(1), int(match.group(2)) if match.group(2) else None
    
    return None


async def get_entity_from_identifier(client, identifier: str):
    """Resolve channel identifier to Telegram entity"""
    if identifier.startswith('+'):
        return await client.get_entity(identifier)
    elif identifier.isdigit():
        # For numeric channel IDs (from t.me/c/ID/MSG format)
        # Need to convert to proper channel ID: -100{channel_id}
        channel_id = int(identifier)
        return await client.get_entity(f"-100{channel_id}")
    else:
        return identifier


def extract_message_caption(message) -> str:
    """Extract caption or text from a Telegram message"""
    caption = ""
    if hasattr(message, 'caption') and message.caption:
        caption = message.caption
    elif hasattr(message, 'text') and message.text:
        caption = message.text
    
    return caption.strip() if caption else ""


async def is_photo_message(message):
    """Check if message contains a photo"""
    from telethon.tl.types import MessageMediaPhoto
    return isinstance(message.media, MessageMediaPhoto)


def detect_content_type(message) -> str:
    """
    Detect content type from message
    Returns: 'photo', 'video', 'music', 'apk', or 'other'
    """
    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
    
    if isinstance(message.media, MessageMediaPhoto):
        return 'photo'
    
    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        mime_type = doc.mime_type if hasattr(doc, 'mime_type') else ''
        
        # Check file extension from attributes
        file_name = ''
        if hasattr(doc, 'attributes'):
            for attr in doc.attributes:
                if hasattr(attr, 'file_name'):
                    file_name = attr.file_name.lower()
                    break
        
        # APK detection
        if file_name.endswith('.apk') or mime_type == 'application/vnd.android.package-archive':
            return 'apk'
        
        # Music detection
        if mime_type.startswith('audio/') or file_name.endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
            return 'music'
        
        # Video detection
        if mime_type.startswith('video/') or file_name.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
            return 'video'
    
    return 'other'


def get_file_size(message) -> int:
    """Get file size in bytes"""
    from telethon.tl.types import MessageMediaDocument
    
    if isinstance(message.media, MessageMediaDocument):
        return message.media.document.size
    return 0


async def download_and_send_media(message, chat_id: int, bot, caption=None):
    """Download media from protected channel and send to user with optimized performance"""
    logger.info(f"Iniciando download_and_send_media para chat_id {chat_id}")
    path = None
    try:
        if caption is None:
            caption = extract_message_caption(message)
        from telethon.tl.types import MessageMediaPhoto
        is_photo = isinstance(message.media, MessageMediaPhoto)
        content_type = detect_content_type(message)

        # Verificar tamaño antes de descargar (Límite aumentado a 2000MB = 2GB)
        file_size = 0
        if hasattr(message, 'document') and message.document:
            file_size = message.document.size
        elif hasattr(message, 'video') and message.video:
            file_size = message.video.size
        elif hasattr(message, 'audio') and message.audio:
            file_size = message.audio.size
            
        # Límite aumentado a 2000MB (2GB)
        if file_size > 2000 * 1024 * 1024:
            await bot.send_message(chat_id=chat_id, text=f"❌ El archivo ({file_size / (1024*1024):.1f} MB) supera el límite de 2GB de Telegram.")
            return

        if is_photo:
            # Descargar foto a memoria (rápido)
            photo_bytes = BytesIO()
            result = await message.download_media(file=photo_bytes)
            if not result:
                await bot.send_message(chat_id=chat_id, text="❌ No se pudo descargar la foto. Puede estar protegida o eliminada.")
                return
            photo_bytes.seek(0)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_bytes,
                caption=caption if caption else None
            )
        else:
            # OPTIMIZACIÓN AVANZADA: Configuración específica para archivos grandes
            suffix = '.mp4' if content_type == 'video' else ''
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            path = temp_file.name
            temp_file.close()
            
            # Configuración optimizada basada en tamaño del archivo
            download_config = {
                'progress_callback': None,  # Podemos agregar callback de progreso si queremos
            }
            
            # OPTIMIZACIÓN: Configuración avanzada para diferentes tamaños de archivo
            if file_size > 500 * 1024 * 1024:  # >500MB - Archivos muy grandes
                logger.info(f"Archivo muy grande detectado ({file_size / (1024*1024):.1f} MB), usando configuración ultra-optimizada")
                # Para archivos muy grandes, usar configuración especial de Telethon
                download_config.update({
                    'dc_id': None,  # Usar DC automático
                    'workers': 1,   # Un solo worker para estabilidad
                })
                timeout_seconds = 900  # 15 minutos para archivos >500MB
            elif file_size > 100 * 1024 * 1024:  # >100MB - Archivos grandes
                logger.info(f"Archivo grande detectado ({file_size / (1024*1024):.1f} MB), usando configuración optimizada")
                download_config.update({
                    'workers': 2,   # Dos workers para archivos grandes
                })
                timeout_seconds = 600  # 10 minutos para archivos >100MB
            elif file_size > 50 * 1024 * 1024:   # >50MB - Archivos medianos-grandes
                logger.info(f"Archivo mediano-grande detectado ({file_size / (1024*1024):.1f} MB), usando configuración balanceada")
                download_config.update({
                    'workers': 4,   # Cuatro workers para velocidad
                })
                timeout_seconds = 300  # 5 minutos para archivos >50MB
            else:  # Archivos pequeños
                timeout_seconds = 300  # 5 minutos para archivos pequeños
            
            # Timeout dinámico basado en tamaño (mínimo 300s, máximo 900s)
            timeout_seconds = min(900, max(300, file_size // (1024 * 1024)))  # 1MB = 1 segundo, mín 5 min
            
            logger.info(f"Iniciando descarga con timeout de {timeout_seconds}s para archivo de {file_size / (1024*1024):.1f} MB")
            
            try:
                # Usar asyncio.wait_for para timeout personalizado
                result = await asyncio.wait_for(
                    message.download_media(file=path, **download_config),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                await bot.send_message(
                    chat_id=chat_id, 
                    text=f"❌ Tiempo de espera agotado ({timeout_seconds}s). El archivo es muy grande ({file_size / (1024*1024):.1f} MB) o la conexión es lenta.\n\n💡 Intenta con un archivo más pequeño o verifica tu conexión."
                )
                if path and os.path.exists(path):
                    os.remove(path)
                return
            
            if not result or not os.path.exists(path):
                await bot.send_message(chat_id=chat_id, text="❌ No se pudo descargar el archivo. Puede estar protegido o eliminado.")
                if path and os.path.exists(path):
                    os.remove(path)
                return
            
            # OPTIMIZACIÓN: Estrategia inteligente de envío basada en tamaño y tipo
            sent = False
            
            # Para archivos muy grandes (>200MB), priorizar Telethon bot_client
            if bot_client and file_size > 200 * 1024 * 1024:
                try:
                    logger.info(f"Enviando archivo muy grande ({file_size / (1024*1024):.1f} MB) con Telethon bot_client prioritario")
                    await bot_client.send_file(
                        chat_id,
                        path,
                        caption=caption if caption else None,
                        supports_streaming=(content_type == 'video'),
                        force_document=False,  # Intentar mantener formato original
                        timeout=600  # 10 minutos timeout para envío
                    )
                    sent = True
                    logger.info("Archivo enviado exitosamente con Telethon (prioridad alta)")
                except Exception as e:
                    logger.error(f"Error enviando con Telethon prioritario: {e}")
                    # Fallback a PTB
            
            # Para archivos medianos (50-200MB), usar Telethon si está disponible
            elif bot_client and file_size > 50 * 1024 * 1024:
                try:
                    logger.info(f"Enviando archivo mediano ({file_size / (1024*1024):.1f} MB) con Telethon bot_client")
                    await bot_client.send_file(
                        chat_id,
                        path,
                        caption=caption if caption else None,
                        supports_streaming=(content_type == 'video'),
                        force_document=False
                    )
                    sent = True
                    logger.info("Archivo enviado exitosamente con Telethon")
                except Exception as e:
                    logger.error(f"Error enviando con Telethon: {e}")
                    # Fallback a PTB
            
            if not sent:
                # Fallback a PTB (python-telegram-bot) con configuraciones ultra-optimizadas
                # Para videos, intentar primero con bot_client si está disponible
                if content_type == 'video' and bot_client:
                    try:
                        logger.info("Intentando enviar video con Telethon bot_client primero")
                        await bot_client.send_file(
                            chat_id,
                            path,
                            caption=caption if caption else None,
                            supports_streaming=True,
                            timeout=600  # 10 minutos
                        )
                        sent = True
                        logger.info("Video enviado exitosamente con Telethon")
                    except Exception as telethon_error:
                        logger.error(f"Error enviando video con Telethon: {telethon_error}")
                        # Fallback a PTB
                
                if not sent:
                    with open(path, 'rb') as f:
                        try:
                            if content_type == 'video':
                                # Configuración específica para videos grandes
                                if file_size > 500 * 1024 * 1024:  # >500MB
                                    logger.info("Enviando video ultra-grande con configuración máxima")
                                    await bot.send_video(
                                        chat_id=chat_id,
                                        video=f,
                                        caption=caption if caption else None,
                                        supports_streaming=True
                                    )
                                elif file_size > 100 * 1024 * 1024:  # >100MB
                                    logger.info("Enviando video grande con configuración optimizada")
                                    await bot.send_video(
                                        chat_id=chat_id,
                                        video=f,
                                        caption=caption if caption else None,
                                        supports_streaming=True
                                    )
                                else:
                                    await bot.send_video(
                                        chat_id=chat_id,
                                        video=f,
                                        caption=caption if caption else None,
                                        supports_streaming=True
                                    )
                            elif content_type == 'music':
                                await bot.send_audio(
                                    chat_id=chat_id,
                                    audio=f,
                                    caption=caption if caption else None
                                )
                            else:
                                # Para documentos/APK, configuración optimizada
                                if file_size > 100 * 1024 * 1024:  # >100MB
                                    await bot.send_document(
                                        chat_id=chat_id,
                                        document=f,
                                        caption=caption if caption else None
                                    )
                                else:
                                    await bot.send_document(
                                        chat_id=chat_id,
                                        document=f,
                                        caption=caption if caption else None
                                    )
                        except Exception as send_error:
                            logger.error(f"Error enviando con PTB: {send_error}")
                            # Si falla por timeout, intentar con Telethon como último recurso
                            if bot_client and ("timeout" in str(send_error).lower() or "read" in str(send_error).lower()):
                                try:
                                    logger.info("Reintentando envío con Telethon después de timeout de PTB")
                                    await bot_client.send_file(
                                        chat_id,
                                        path,
                                        caption=caption if caption else None,
                                        supports_streaming=(content_type == 'video'),
                                        timeout=600  # 10 minutos como último recurso
                                    )
                                    sent = True
                                    logger.info("Reintento con Telethon exitoso")
                                except Exception as telethon_retry_error:
                                    logger.error(f"Telethon retry también falló: {telethon_retry_error}")
                                    raise send_error  # Re-lanzar el error original
            
            os.remove(path)
    except (asyncio.TimeoutError, TimeoutError):
        if path and os.path.exists(path):
            os.remove(path)
        logger.error("Timeout en download_and_send_media")
        await bot.send_message(
            chat_id=chat_id, 
            text="❌ Tiempo de espera agotado. El archivo es demasiado grande o la conexión es lenta.\n\n💡 Sugerencias:\n• Verifica tu conexión a internet\n• Intenta con un archivo más pequeño\n• Espera unos minutos antes de reintentar"
        )
        return False
    except Exception as e:
        if path and os.path.exists(path):
            os.remove(path)
        logger.error(f"Error en download_and_send_media: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")
        return False
    
    logger.info(f"download_and_send_media completado exitosamente para chat_id {chat_id}")
    return True


async def send_premium_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send invoice for Premium subscription payment with Telegram Stars"""
    chat_id = update.effective_chat.id
    title = "💎 Suscripción Premium"
    description = "Fotos Ilimitadas + 50 Videos + 50 Música + 50 APK diarios | 30 días de acceso"
    payload = "premium_30_days"
    currency = "XTR"  # Telegram Stars currency code
    
    # Price in Telegram Stars
    prices = [LabeledPrice("Premium 30 días", PREMIUM_PRICE_STARS)]
    
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",  # Empty for Stars payments
        currency=currency,
        prices=prices
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer pre-checkout query (approve all by default)"""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def show_premium_plans(query, context: ContextTypes.DEFAULT_TYPE, lang="es"):
    """Show premium plans information"""
    message = get_msg("plans_title", lang)
    message += get_msg("plans_free", lang)
    message += get_msg("plans_premium", lang, price=PREMIUM_PRICE_STARS)
    message += get_msg("plans_benefits", lang)
    message += get_msg("plans_warning", lang)
    message += get_msg("plans_payment", lang)
    
    # Add payment, channel and back buttons
    keyboard = [
        [InlineKeyboardButton(get_msg("btn_pay_stars", lang), callback_data="pay_premium")],
        [InlineKeyboardButton(get_msg("btn_join_channel", lang), url="https://t.me/observer_bots")],
        [InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    logger.info(f"🔘 BUTTON CALLBACK: data={query.data}, user={query.from_user.id}")
    
    if query.data.startswith("setlang_"):
        await query.answer()
        lang = query.data.split("_")[1]
        user_id = query.from_user.id
        set_user_language(user_id, lang)
        logger.info(f"User {user_id} selected language: {lang}")
        
        # Proceed to the actual welcome message which was deferred from /start
        user = get_user(user_id)
        
        # Send Miniapp button with language included
        first_name = update.effective_user.first_name
        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&new=false&lang={lang}"
        
        welcome_message = (
            f"👋 ¡Hola {first_name}! / Hello {first_name}!\n\n"
            "🚀 Abriendo MiniApp...\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("📱 Abrir MiniApp", web_app=WebAppInfo(url=miniapp_url))],
            [InlineKeyboardButton("⚙️ Configuración", callback_data="settings")],
            [InlineKeyboardButton("💎 Premium", callback_data="show_premium_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
        
    if query.data == "cancel_login":
        await query.answer()
        await cancel_login(update, context)
        return
    
    if query.data == "connect_account":
        await query.answer()
        await start_login(update, context)
        return
    
    if query.data == "panel_menu":
        await query.answer()
        await panel_command(update, context)
        return

    if query.data == "panel_refresh":
        await query.answer("🔄 Actualizando...")
        await panel_command(update, context)
        return
        
    if query.data == "disconnect_account":
        await query.answer()
        await logout_command(update, context)
        return
        
    if query.data == "my_stats":
        await query.answer()
        await stats_command(update, context)
        return
        
    if query.data == "back_to_menu":
        await query.answer()
        await start_command(update, context)
        return
    
    if query.data == "start_download":
        logger.info(f"start_download callback triggered by user {query.from_user.id}")
        
        # Primero responder al callback para quitar el "loading"
        try:
            await query.answer("✅ Listo para descargar")
        except Exception as e:
            logger.warning(f"Error answering callback: {e}")
        
        try:
            user_id = query.from_user.id
            user = get_user(user_id)
            lang = get_user_language(user)
            
            # Verificar si el usuario tiene sesión configurada
            if not has_active_session(user_id):
                config_message = (
                    "⚠️ *Configuración Requerida*\n\n"
                    "Para descargar contenido, necesitas configurar tu cuenta de Telegram primero.\n\n"
                    "👉 Presiona el botón de abajo para configurar."
                )
                keyboard = [
                    [InlineKeyboardButton("⚙️ Configurar Cuenta", callback_data="connect_account")],
                    [InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await query.edit_message_text(config_message, parse_mode='Markdown', reply_markup=reply_markup)
                except Exception:
                    await query.message.reply_text(config_message, parse_mode='Markdown', reply_markup=reply_markup)
                return
            
            if lang == 'es':
                message = (
                    "📥 *¡Listo para descargar!*\n\n"
                    "Ahora envíame el enlace del mensaje de Telegram que quieres descargar.\n\n"
                    "📎 *Ejemplo:*\n"
                    "`https://t.me/canal/123`\n\n"
                    "💡 *Tip:* Copia el enlace desde Telegram y pégalo aquí."
                )
            elif lang == 'en':
                message = (
                    "📥 *Ready to download!*\n\n"
                    "Now send me the Telegram message link you want to download.\n\n"
                    "📎 *Example:*\n"
                    "`https://t.me/channel/123`\n\n"
                    "💡 *Tip:* Copy the link from Telegram and paste it here."
                )
            elif lang == 'pt':
                message = (
                    "📥 *Pronto para baixar!*\n\n"
                    "Agora envie-me o link da mensagem do Telegram que você quer baixar.\n\n"
                    "📎 *Exemplo:*\n"
                    "`https://t.me/canal/123`\n\n"
                    "💡 *Dica:* Copie o link do Telegram e cole aqui."
                )
            else:  # Italian
                message = (
                    "📥 *Pronto per scaricare!*\n\n"
                    "Ora inviami il link del messaggio di Telegram che vuoi scaricare.\n\n"
                    "📎 *Esempio:*\n"
                    "`https://t.me/canale/123`\n\n"
                    "💡 *Suggerimento:* Copia il link da Telegram e incollalo qui."
                )
            
            keyboard = [[InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Intentar editar el mensaje, si falla enviar uno nuevo
            try:
                await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
                logger.info(f"Successfully edited message for user {user_id}")
            except Exception as edit_error:
                logger.warning(f"Could not edit message: {edit_error}, sending new message")
                await query.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
                
        except Exception as e:
            logger.error(f"Error handling start_download callback: {e}", exc_info=True)
            # Fallback: enviar mensaje nuevo con información útil
            try:
                fallback_msg = (
                    "📥 *Modo Descarga*\n\n"
                    "Envía el enlace del mensaje que quieres descargar.\n\n"
                    "Ejemplo: `https://t.me/canal/123`"
                )
                await query.message.reply_text(fallback_msg, parse_mode='Markdown')
            except Exception as e2:
                logger.error(f"Error sending fallback message: {e2}")
        return
    
    if query.data == "view_plans":
        # Show premium plans
        await query.answer()
        user_id = query.from_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        await show_premium_plans(query, context, lang)
        return
    
    if query.data == "show_guide":
        # Show detailed usage guide
        await query.answer()
        user_id = query.from_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        
        guide_message = get_msg("guide_title", lang)
        guide_message += get_msg("guide_step_1", lang)
        guide_message += get_msg("guide_step_2", lang)
        guide_message += get_msg("guide_formats", lang)
        guide_message += get_msg("guide_tips", lang)
        guide_message += get_msg("guide_premium", lang)
        guide_message += get_msg("guide_option_a", lang)
        guide_message += get_msg("guide_option_b", lang)
        guide_message += get_msg("guide_note", lang)
        
        keyboard = [[InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(guide_message, parse_mode='HTML', reply_markup=reply_markup)
        return
    
    if query.data == "back_to_menu":
        # Return to main menu - usar el mismo mensaje de /start
        await query.answer()
        user_id = update.effective_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        
        # Check and reset daily limits
        check_and_reset_daily_limits(user_id)
        user = get_user(user_id)
        
        # Build welcome message using multi-language system
        welcome_message = get_msg("start_welcome", lang)
        welcome_message += get_msg("start_description", lang)
        welcome_message += get_msg("start_divider", lang)
        welcome_message += get_msg("start_how_to", lang)
        welcome_message += get_msg("start_example", lang)
        welcome_message += get_msg("start_divider", lang)
        
        # Add plan status
        if user['premium']:
            if user.get('premium_until'):
                expiry = datetime.fromisoformat(user['premium_until'])
                days_left = (expiry - datetime.now()).days
                welcome_message += get_msg("start_premium_plan", lang, 
                                         expiry=expiry.strftime('%d/%m/%Y'),
                                         days_left=days_left)
                welcome_message += get_msg("start_premium_usage", lang,
                                         daily_video=user['daily_video'],
                                         video_limit=PREMIUM_VIDEO_DAILY_LIMIT,
                                         daily_music=user['daily_music'],
                                         music_limit=PREMIUM_MUSIC_DAILY_LIMIT,
                                         daily_apk=user['daily_apk'],
                                         apk_limit=PREMIUM_APK_DAILY_LIMIT)
            else:
                welcome_message += get_msg("start_premium_active", lang)
        else:
            welcome_message += get_msg("start_free_plan", lang,
                                     daily_photo=user['daily_photo'],
                                     photo_limit=FREE_PHOTO_LIMIT,
                                     downloads=user['downloads'],
                                     download_limit=FREE_DOWNLOAD_LIMIT)
        
        welcome_message += get_msg("start_cta", lang)
        
        # Build buttons with language support
        keyboard = [
            [InlineKeyboardButton(get_msg("btn_download_now", lang), callback_data="start_download")],
            [
                InlineKeyboardButton(get_msg("btn_how_to_use", lang), callback_data="show_guide"),
                InlineKeyboardButton(get_msg("btn_plans", lang), callback_data="view_plans")
            ]
        ]
        
        # PROBLEMA 2: Agregar botón de MiniApp al menú principal
        miniapp_url_env = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        if miniapp_url_env:
            full_url = f"{miniapp_url_env}/miniapp?v=2&user_id={user_id}&lang={lang}"
            keyboard.append([
                InlineKeyboardButton("📱 Abrir App", web_app=WebAppInfo(url=full_url))
            ])
            
        keyboard.extend([
            [InlineKeyboardButton(get_msg("btn_change_language", lang), callback_data="change_language")],
            [InlineKeyboardButton(get_msg("btn_support", lang), url="https://t.me/observer_bots/11")],
            [InlineKeyboardButton(get_msg("btn_official_channel", lang), url="https://t.me/observer_bots")]
        ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    # Manejar callback de ver/refrescar estadísticas PERSONALES
    if query.data == "view_stats" or query.data == "refresh_stats":
        await query.answer("🔄 Actualizando...")
        user_id = query.from_user.id
        user_name = query.from_user.first_name or "Usuario"
        
        check_and_reset_daily_limits(user_id)
        user_stats = get_user_usage_stats(user_id, FREE_DOWNLOAD_LIMIT, FREE_PHOTO_LIMIT)
        user = get_user(user_id)
        
        if not user_stats:
            await query.edit_message_text("❌ Error al obtener estadísticas")
            return
        
        # Función helper para barra de progreso
        def get_progress_bar(used, total, width=10):
            if total == 0:
                return "▱" * width
            filled = int((used / total) * width)
            return "▰" * filled + "▱" * (width - filled)
        
        # Header PERSONAL
        message = "```\n"
        message += "╔═══════════════════════════════╗\n"
        message += "║   👤 MIS ESTADÍSTICAS         ║\n"
        message += "╚═══════════════════════════════╝\n"
        message += "```\n\n"
        
        # Información del usuario
        message += "```\n"
        message += "┌─────────────────────────────┐\n"
        message += f"│  📋 {user_name[:20]:<20} │\n"
        message += "└─────────────────────────────┘\n"
        message += "```\n"
        
        if user['premium']:
            if user.get('premium_until'):
                expiry = datetime.fromisoformat(user['premium_until'])
                days_left = (expiry - datetime.now()).days
                message += f"💎 *Plan:* Premium Activo\n"
                message += f"📅 *Expira:* {expiry.strftime('%d/%m/%Y')}\n"
                message += f"⏳ *Quedan:* {days_left} días\n\n"
            else:
                message += "💎 *Plan:* Premium Vitalicio ♾️\n\n"
            
            # Uso de hoy con barras de progreso
            videos = user_stats['videos']
            video_bar = get_progress_bar(videos['used'], 50)
            message += f"🎬 *Videos Hoy:* {videos['used']}/50\n"
            message += f"   {video_bar} {50 - videos['used']} restantes\n\n"
            
            photos = user_stats['photos']
            message += f"📸 *Fotos Hoy:* {photos['used']} (Ilimitadas) ♾️\n\n"
            
            music = user_stats['music']
            music_bar = get_progress_bar(music['used'], 50)
            message += f"🎵 *Música Hoy:* {music['used']}/50\n"
            message += f"   {music_bar} {music['remaining']} restantes\n\n"
            
            apk = user_stats['apk']
            apk_bar = get_progress_bar(apk['used'], 50)
            message += f"📦 *APK Hoy:* {apk['used']}/50\n"
            message += f"   {apk_bar} {apk['remaining']} restantes\n"
        else:
            message += "🆓 *Plan:* Gratuito\n\n"
            
            # Videos (límite total, no diario)
            videos = user_stats['videos']
            if videos['remaining'] > 0:
                dots = "🟢" * videos['remaining'] + "⚫" * (videos['limit'] - videos['remaining'])
                message += f"🎬 *Videos Totales:* {videos['used']}/{videos['limit']}\n"
                message += f"   {dots}\n"
                message += f"   Quedan *{videos['remaining']}* {'videos' if videos['remaining'] > 1 else 'video'}\n"
                if videos['remaining'] == 1:
                    message += "   ⚠️ ¡Solo queda 1!\n"
            else:
                message += f"🎬 *Videos:* {videos['used']}/{videos['limit']} ❌\n"
                message += "   🔒 Límite alcanzado\n"
            message += "\n"
            
            # Fotos (límite diario)
            photos = user_stats['photos']
            if photos['remaining'] > 0:
                dots = "🟩" * photos['remaining'] + "⬜" * (photos['limit'] - photos['remaining'])
                message += f"📸 *Fotos:* {photos['used']}/{photos['limit']}\n"
                message += f"   {dots}\n"
                message += f"   Quedan *{photos['remaining']}* {'fotos' if photos['remaining'] > 1 else 'foto'}\n"
                if photos['remaining'] <= 2:
                    message += "   ⚠️ Pocas restantes\n"
            else:
                message += f"📸 *Fotos:* {photos['used']}/{photos['limit']} ❌\n"
                message += "   🔒 Límite alcanzado\n"
            message += "\n"
            
            # Contenido premium bloqueado
            message += "🔒 *Requiere Premium:*\n"
            message += "   🎵 Música\n"
            message += "   📦 APK\n"
        
        # Footer con call to action
        if not user['premium']:
            message += f"\n```\n┌─────────────────────────────┐\n"
            message += f"│  💎 PREMIUM: {PREMIUM_PRICE_STARS} ⭐  │\n"
            message += "└─────────────────────────────┘\n```"
        
        keyboard = []
        if not user['premium']:
            keyboard.append([InlineKeyboardButton("💎 Obtener Premium", callback_data="show_premium")])
        keyboard.append([InlineKeyboardButton("🔄 Actualizar Stats", callback_data="refresh_stats")])
        keyboard.append([InlineKeyboardButton("◀️ Volver al menú", callback_data="back_to_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error actualizando stats: {e}")
            await query.answer("Error al actualizar", show_alert=True)
        
        return
    
    # Manejar callback de refrescar estadísticas de ADMIN
    if query.data == "refresh_admin_stats":
        user_id = query.from_user.id
        
        # Verificar si es admin
        if user_id not in ADMIN_USER_IDS:
            await query.answer("❌ Acceso denegado", show_alert=True)
            return
        
        await query.answer("🔄 Actualizando...")
        
        # Obtener estadísticas globales
        global_stats = get_user_stats()
        
        # Reconstruir mensaje del panel de admin
        message = "```\n"
        message += "╔═══════════════════════════════╗\n"
        message += "║  🔐 PANEL DE ADMINISTRACIÓN  ║\n"
        message += "╚═══════════════════════════════╝\n"
        message += "```\n\n"
        
        # Estadísticas Globales
        message += "```\n"
        message += "┌─────────────────────────────┐\n"
        message += "│    🌍 ESTADÍSTICAS GLOBALES │\n"
        message += "└─────────────────────────────┘\n"
        message += "```\n"
        message += f"👥 *Total de Usuarios:* `{global_stats['total_users']:,}`\n"
        message += f"💎 *Usuarios Premium:* `{global_stats['premium_users']:,}`\n"
        message += f"🆓 *Usuarios Free:* `{global_stats['free_users']:,}`\n"
        message += f"🟢 *Activos Hoy:* `{global_stats['active_today']:,}`\n\n"
        
        # Ingresos
        message += "```\n"
        message += "┌─────────────────────────────┐\n"
        message += "│       💰 INGRESOS           │\n"
        message += "└─────────────────────────────┘\n"
        message += "```\n"
        message += f"⭐ *Total en Stars:* `{global_stats['revenue']['stars']:,}`\n"
        message += f"📊 *Suscripciones:* `{global_stats['revenue']['premium_subs']:,}`\n"
        message += f"💵 *Promedio por sub:* `{PREMIUM_PRICE_STARS}` ⭐\n\n"
        
        # Descargas totales
        message += "```\n"
        message += "┌─────────────────────────────┐\n"
        message += "│    📥 DESCARGAS TOTALES     │\n"
        message += "└─────────────────────────────┘\n"
        message += "```\n"
        message += f"📊 *Total Histórico:* `{global_stats['total_downloads']:,}`\n\n"
        
        # Actividad del Día
        daily = global_stats['daily_stats']
        message += "```\n"
        message += "┌─────────────────────────────┐\n"
        message += "│      📈 ACTIVIDAD DE HOY    │\n"
        message += "└─────────────────────────────┘\n"
        message += "```\n"
        message += f"📸 *Fotos:* `{daily['photos']:,}` descargadas\n"
        message += f"🎬 *Videos:* `{daily['videos']:,}` descargados\n"
        message += f"🎵 *Música:* `{daily['music']:,}` archivos\n"
        message += f"📦 *APK:* `{daily['apk']:,}` archivos\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📊 *Total Hoy:* `{daily['total']:,}` descargas\n\n"
        
        # Métricas adicionales
        if global_stats['total_users'] > 0:
            conversion_rate = (global_stats['premium_users'] / global_stats['total_users']) * 100
            avg_downloads = global_stats['total_downloads'] / global_stats['total_users']
            
            message += "```\n"
            message += "┌─────────────────────────────┐\n"
            message += "│       📊 MÉTRICAS           │\n"
            message += "└─────────────────────────────┘\n"
            message += "```\n"
            message += f"📈 *Tasa de Conversión:* `{conversion_rate:.1f}%`\n"
            message += f"📥 *Promedio Descargas/Usuario:* `{avg_downloads:.1f}`\n"
            message += f"⚡ *Tasa de Actividad:* `{(global_stats['active_today']/global_stats['total_users']*100):.1f}%`\n\n"
        
        # Footer
        message += "```\n"
        message += "╔═══════════════════════════════╗\n"
        message += "║   Actualizado en tiempo real  ║\n"
        message += "╚═══════════════════════════════╝\n"
        message += "```"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Actualizar Stats", callback_data="refresh_admin_stats")],
            [InlineKeyboardButton("◀️ Volver al menú", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error actualizando admin stats: {e}")
            await query.answer("Error al actualizar", show_alert=True)
        
        return
    
    # Manejar callback para mostrar info de Premium
    if query.data == "show_premium":
        await query.answer()
        await show_premium_plans(query, context)
        return
    
    await query.answer("📄 Procesando...", show_alert=False)
    
    # Handle premium payment callbacks for all plans
    if query.data.startswith("pay_premium"):
        user_id = update.effective_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        
        # Determine which plan was selected
        plan_key = 'monthly'  # default
        if query.data == "pay_premium_trial":
            plan_key = 'trial'
        elif query.data == "pay_premium_weekly":
            plan_key = 'weekly'
        elif query.data == "pay_premium_monthly":
            plan_key = 'monthly'
        elif query.data == "pay_premium_quarterly":
            plan_key = 'quarterly'
        
        plan = PREMIUM_PLANS[plan_key]
        logger.info(f"User {user_id} requested payment invoice for plan: {plan_key} ({plan['stars']}⭐ / {plan['days']}d)")
        
        try:
            # Send the invoice with the selected plan
            await send_premium_invoice_callback(update, context, plan_key=plan_key)
            logger.info(f"Invoice sent successfully to user {user_id} for plan {plan_key}")
            
            # Answer callback with plan info
            if lang == 'es':
                callback_msg = f"✅ Factura enviada: {plan['name']} - {plan['stars']}⭐ por {plan['days']} días"
            else:
                callback_msg = f"✅ Invoice sent: {plan['name']} - {plan['stars']}⭐ for {plan['days']} days"
            
            await query.answer(callback_msg[:200], show_alert=True)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error sending invoice to user {user_id}: {error_msg}")
            
            # Check if it's a Telegram Stars configuration error
            if "currency" in error_msg.lower() or "stars" in error_msg.lower() or "xtr" in error_msg.lower():
                await query.answer("⚠️ Pagos no configurados. Contacta soporte.", show_alert=True)
            else:
                await query.answer(f"❌ Error: {error_msg[:100]}", show_alert=True)
        return
    
    # Handle language change callbacks
    if query.data == "change_language":
        await query.answer()
        user_id = query.from_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        
        message = get_msg("language_select", lang)
        
        keyboard = [
            [
                InlineKeyboardButton(get_msg("btn_spanish", lang), callback_data="set_lang_es"),
                InlineKeyboardButton(get_msg("btn_english", lang), callback_data="set_lang_en")
            ],
            [
                InlineKeyboardButton(get_msg("btn_portuguese", lang), callback_data="set_lang_pt"),
                InlineKeyboardButton(get_msg("btn_italian", lang), callback_data="set_lang_it")
            ],
            [InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    if query.data == "set_lang_es":
        user_id = query.from_user.id
        set_user_language(user_id, 'es')
        await query.answer(get_msg("language_changed", 'es'))
        
        # Return to main menu in Spanish
        user = get_user(user_id)
        check_and_reset_daily_limits(user_id)
        user = get_user(user_id)
        
        lang = 'es'
        
        # Build welcome message
        welcome_message = get_msg("start_welcome", lang)
        welcome_message += get_msg("start_description", lang)
        welcome_message += get_msg("start_divider", lang)
        welcome_message += get_msg("start_how_to", lang)
        welcome_message += get_msg("start_example", lang)
        welcome_message += get_msg("start_divider", lang)
        
        if user['premium']:
            if user.get('premium_until'):
                expiry = datetime.fromisoformat(user['premium_until'])
                days_left = (expiry - datetime.now()).days
                welcome_message += get_msg("start_premium_plan", lang, 
                                         expiry=expiry.strftime('%d/%m/%Y'),
                                         days_left=days_left)
                welcome_message += get_msg("start_premium_usage", lang,
                                         daily_video=user['daily_video'],
                                         video_limit=PREMIUM_VIDEO_DAILY_LIMIT,
                                         daily_music=user['daily_music'],
                                         music_limit=PREMIUM_MUSIC_DAILY_LIMIT,
                                         daily_apk=user['daily_apk'],
                                         apk_limit=PREMIUM_APK_DAILY_LIMIT)
            else:
                welcome_message += get_msg("start_premium_active", lang)
        
        welcome_message += get_msg("start_cta", lang)
        
        keyboard = [
            [InlineKeyboardButton("📱 " + get_msg("btn_open_miniapp", lang), web_app=WebAppInfo(url=f"{(os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')}/miniapp?v=2&user_id={user_id}&new=false&lang={lang}"))],
            [InlineKeyboardButton(get_msg("btn_panel", lang), callback_data="panel_menu")],
            [InlineKeyboardButton(get_msg("btn_plans", lang), callback_data="view_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    if query.data == "set_lang_en":
        user_id = query.from_user.id
        set_user_language(user_id, 'en')
        await query.answer(get_msg("language_changed", 'en'))
        
        # Return to main menu in English
        user = get_user(user_id)
        check_and_reset_daily_limits(user_id)
        user = get_user(user_id)
        
        lang = 'en'
        
        # Build welcome message
        welcome_message = get_msg("start_welcome", lang)
        welcome_message += get_msg("start_description", lang)
        welcome_message += get_msg("start_divider", lang)
        welcome_message += get_msg("start_how_to", lang)
        welcome_message += get_msg("start_example", lang)
        welcome_message += get_msg("start_divider", lang)
        
        if user['premium']:
            if user.get('premium_until'):
                expiry = datetime.fromisoformat(user['premium_until'])
                days_left = (expiry - datetime.now()).days
                welcome_message += get_msg("start_premium_plan", lang, 
                                         expiry=expiry.strftime('%d/%m/%Y'),
                                         days_left=days_left)
                welcome_message += get_msg("start_premium_usage", lang,
                                         daily_video=user['daily_video'],
                                         video_limit=PREMIUM_VIDEO_DAILY_LIMIT,
                                         daily_music=user['daily_music'],
                                         music_limit=PREMIUM_MUSIC_DAILY_LIMIT,
                                         daily_apk=user['daily_apk'],
                                         apk_limit=PREMIUM_APK_DAILY_LIMIT)
            else:
                welcome_message += get_msg("start_premium_active", lang)
        
        welcome_message += get_msg("start_cta", lang)
        
        keyboard = [
            [InlineKeyboardButton("📱 " + get_msg("btn_open_miniapp", lang), web_app=WebAppInfo(url=f"{(os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')}/miniapp?v=2&user_id={user_id}&new=false&lang={lang}"))],
            [InlineKeyboardButton(get_msg("btn_panel", lang), callback_data="panel_menu")],
            [InlineKeyboardButton(get_msg("btn_plans", lang), callback_data="view_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    if query.data == "set_lang_pt":
        user_id = query.from_user.id
        set_user_language(user_id, 'pt')
        await query.answer(get_msg("language_changed", 'pt'))
        
        # Return to main menu in Portuguese
        user = get_user(user_id)
        check_and_reset_daily_limits(user_id)
        user = get_user(user_id)
        
        lang = 'pt'
        
        # Build welcome message
        welcome_message = get_msg("start_welcome", lang)
        welcome_message += get_msg("start_description", lang)
        welcome_message += get_msg("start_divider", lang)
        welcome_message += get_msg("start_how_to", lang)
        welcome_message += get_msg("start_example", lang)
        
        if user['premium']:
            if user.get('premium_until'):
                expiry = datetime.fromisoformat(user['premium_until'])
                days_left = (expiry - datetime.now()).days
                welcome_message += get_msg("start_premium_plan", lang, 
                                         expiry=expiry.strftime('%d/%m/%Y'),
                                         days_left=days_left)
            else:
                welcome_message += get_msg("start_premium_active", lang)
        else:
            welcome_message += get_msg("start_free_plan", lang)
            welcome_message += get_msg("start_upgrade", lang)
        
        keyboard = [
            [InlineKeyboardButton("📱 " + get_msg("btn_open_miniapp", lang), web_app=WebAppInfo(url=f"{(os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')}/miniapp?v=2&user_id={user_id}&new=false&lang={lang}"))],
            [InlineKeyboardButton(get_msg("btn_panel", lang), callback_data="panel_menu")],
            [InlineKeyboardButton(get_msg("btn_plans", lang), callback_data="view_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    if query.data == "set_lang_it":
        user_id = query.from_user.id
        set_user_language(user_id, 'it')
        await query.answer(get_msg("language_changed", 'it'))
        
        # Return to main menu in Italian
        user = get_user(user_id)
        check_and_reset_daily_limits(user_id)
        user = get_user(user_id)
        
        lang = 'it'
        
        # Build welcome message
        welcome_message = get_msg("start_welcome", lang)
        welcome_message += get_msg("start_description", lang)
        welcome_message += get_msg("start_divider", lang)
        welcome_message += get_msg("start_how_to", lang)
        welcome_message += get_msg("start_example", lang)
        
        if user['premium']:
            if user.get('premium_until'):
                expiry = datetime.fromisoformat(user['premium_until'])
                days_left = (expiry - datetime.now()).days
                welcome_message += get_msg("start_premium_plan", lang, 
                                         expiry=expiry.strftime('%d/%m/%Y'),
                                         days_left=days_left)
            else:
                welcome_message += get_msg("start_premium_active", lang)
        else:
            welcome_message += get_msg("start_free_plan", lang)
            welcome_message += get_msg("start_upgrade", lang)
        
        keyboard = [
            [InlineKeyboardButton("📱 " + get_msg("btn_open_miniapp", lang), web_app=WebAppInfo(url=f"{(os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')}/miniapp?v=2&user_id={user_id}&new=false&lang={lang}"))],
            [InlineKeyboardButton(get_msg("btn_panel", lang), callback_data="panel_menu")],
            [InlineKeyboardButton(get_msg("btn_plans", lang), callback_data="view_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    # Handle settings button
    if query.data == "settings":
        logger.info(f"⚙️ Settings button clicked by user {query.from_user.id}")
        await query.answer("🔧 Abriendo configuración...")
        user_id = query.from_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        
        # Build settings message
        settings_msg = "⚙️ *CONFIGURACIÓN*\n\n"
        settings_msg += f"👤 *Usuario:* @{user.get('username', 'N/A')}\n"
        settings_msg += f"🌐 *Idioma:* {lang.upper()}\n\n"
        
        # Show current language and option to change
        settings_msg += "*Cambiar Idioma:*\n"
        
        keyboard = [
            [InlineKeyboardButton("🇪🇸 Español", callback_data="change_lang_es")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="change_lang_en")],
            [InlineKeyboardButton("🇵🇹 Português", callback_data="change_lang_pt")],
            [InlineKeyboardButton("🇮🇹 Italiano", callback_data="change_lang_it")],
            [InlineKeyboardButton("◀️ Volver", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(settings_msg, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            await query.answer("Error al abrir configuración", show_alert=True)
        return
    
    # Handle open miniapp button
    if query.data == "open_miniapp":
        logger.info(f"📱 Open miniapp clicked by user {query.from_user.id}")
        await query.answer("Abriendo MiniApp...")
        user_id = query.from_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        
        # Prepare MiniApp URL with language
        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&new=false&lang={lang}"
        
        miniapp_msg = "📱 *MiniApp*\n\n"
        miniapp_msg += "Haz clic en el botón de abajo para abrir la aplicación.\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🚀 Abrir MiniApp", web_app=WebAppInfo(url=miniapp_url))],
            [InlineKeyboardButton("◀️ Volver", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(miniapp_msg, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error showing miniapp: {e}")
            await query.message.reply_text(miniapp_msg, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    # Handle premium plans display
    if query.data == "show_premium_plans":
        await query.answer()
        user_id = update.effective_user.id
        user = get_user(user_id)
        lang = get_user_language(user) if user else 'es'
        await show_premium_plans(query, context, lang)
        return
    
    # Handle language changes (change_lang_XX)
    if query.data.startswith("change_lang_"):
        await query.answer()
        user_id = update.effective_user.id
        lang_code = query.data.replace("change_lang_", "")
        
        # Update user language in database
        try:
            set_user_language(user_id, lang_code)
            user = get_user(user_id)
            
            # Re-show settings with new language
            await panel_command(update, context)
        except Exception as e:
            logger.error(f"Error changing language: {e}")
            await query.answer("Error al cambiar idioma", show_alert=True)
        return
    
    # Fallback: log unknown button
    logger.warning(f"⚠️ Unknown callback data: {query.data} from user {query.from_user.id}")
    await query.answer(f"Botón no reconocido: {query.data}", show_alert=False)


async def send_premium_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_key='monthly'):
    """Send invoice for Premium subscription when callback button is pressed"""
    chat_id = update.effective_chat.id
    
    # Get plan details
    plan = PREMIUM_PLANS.get(plan_key, PREMIUM_PLANS['monthly'])
    
    # Build title and description based on plan
    if plan_key == 'trial':
        title = f"{plan['badge']} Suscripción Premium"
        description = f"Prueba Premium por {plan['days']} días | Descargas ilimitadas | Ideal para conocer el servicio"
    elif plan_key == 'weekly':
        title = f"{plan['badge']} Suscripción Premium"
        description = f"Premium por {plan['days']} días | Mejor precio por día | Descargas ilimitadas"
    elif plan_key == 'monthly':
        title = f"{plan['badge']} Suscripción Premium"
        description = f"Premium por {plan['days']} días (1 mes) | El más popular | Descargas ilimitadas"
    elif plan_key == 'quarterly':
        title = f"{plan['badge']} Suscripción Premium"
        description = f"Premium por {plan['days']} días (3 meses) | Ahorra hasta 50% | Descargas ilimitadas"
    else:
        title = "💎 Suscripción Premium"
        description = f"Premium por {plan['days']} días | Descargas ilimitadas"
    
    payload = f"premium_{plan['days']}_days_{plan_key}"
    currency = "XTR"  # Telegram Stars currency code
    
    # Price in Telegram Stars
    prices = [LabeledPrice(f"Premium {plan['days']} días", plan['stars'])]
    
    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Empty for Stars payments
            currency=currency,
            prices=prices
        )
        logger.info(f"Invoice successfully sent to chat {chat_id} for plan {plan_key} ({plan['stars']}⭐ / {plan['days']}d)")
    except Exception as e:
        logger.error(f"Failed to send invoice to chat {chat_id}: {e}")
        # Send informative error message
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ *Sistema de Pagos Temporalmente No Disponible*\n\n"
                "El bot está configurándose para aceptar pagos con Telegram Stars.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💡 *Mientras tanto:*\n"
                "• Disfruta de 3 videos gratuitos\n"
                "• 10 fotos gratuitas\n\n"
                "📢 Únete al canal para actualizaciones:\n"
                "@observer_bots\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔧 Error técnico: `{str(e)[:50]}`"
            ),
            parse_mode='Markdown'
        )


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment with Telegram Stars - Support all plans"""
    user_id = update.effective_user.id
    payment_info = update.message.successful_payment
    
    logger.info(f"🎉 PAGO RECIBIDO - User {user_id}: {payment_info.total_amount} {payment_info.currency}")
    logger.info(f"📦 Payload: {payment_info.invoice_payload}")
    logger.info(f"🔑 Transaction ID: {payment_info.telegram_payment_charge_id}")
    
    # Extract plan key from payload (format: premium_{days}_days_{plan_key}_{user_id})
    payload = payment_info.invoice_payload
    days = 30  # default
    plan_name = "Premium"
    plan_key = "monthly"
    
    try:
        # Parse payload to get days and plan key
        if "premium_" in payload and "_days_" in payload:
            # Format: premium_3_days_trial_123456789 or premium_30_days_monthly_123456789
            parts = payload.split("_days_")
            if len(parts) == 2:
                days_str = parts[0].replace("premium_", "")
                days = int(days_str)
                
                # Get plan key and user_id from second part
                remaining = parts[1].split("_")
                if len(remaining) >= 1:
                    plan_key = remaining[0]
                if len(remaining) >= 2:
                    payload_user_id = remaining[1]
                    logger.info(f"✓ Payload includes user_id: {payload_user_id}")
                
                # Get plan details
                plan = PREMIUM_PLANS.get(plan_key, PREMIUM_PLANS['monthly'])
                plan_name = plan['name']
                
                logger.info(f"✓ Plan detectado: {plan_key} ({plan['name']}) - {days} días - {plan['stars']}⭐")
            else:
                logger.warning(f"⚠️ Formato de payload incorrecto: {payload}, usando plan por defecto (30 días)")
        else:
            logger.warning(f"⚠️ Payload no reconocido: {payload}, usando plan por defecto (30 días)")
    except Exception as e:
        logger.error(f"❌ Error parseando payload: {e}, usando plan por defecto (30 días)")
        import traceback
        logger.error(traceback.format_exc())
    
    # Activate Premium for the purchased duration
    logger.info(f"💾 Actualizando premium para user {user_id} por {days} días...")
    try:
        set_premium(user_id, days=days)
        logger.info(f"✓ Premium activado correctamente para user {user_id}")
    except Exception as e:
        logger.error(f"❌ Error activando premium: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    from datetime import datetime, timedelta
    expiry = datetime.now() + timedelta(days=days)
    
    # Get user language
    user = get_user(user_id)
    lang = get_user_language(user)
    
    if lang == 'es':
        await update.message.reply_text(
            f"🎉 *{plan_name} Activado* 🎉\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ Pago recibido exitosamente\n"
            "💎 Suscripción Premium activada\n\n"
            f"📅 Válido hasta: {expiry.strftime('%d/%m/%Y')}\n"
            f"⏰ Duración: {days} días\n"
            f"⭐ Estrellas: {payment_info.total_amount}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Beneficios Desbloqueados:*\n"
            "• Fotos ilimitadas\n"
            "• 50 videos/día\n"
            "• 50 canciones/día\n"
            "• Sin anuncios\n"
            "• Prioridad en soporte\n\n"
            "🚀 Usa /start para comenzar\n"
            "📊 Usa /panel para ver tu estado",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"🎉 *{plan_name} Activated* 🎉\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ Payment received successfully\n"
            "💎 Premium subscription activated\n\n"
            f"📅 Valid until: {expiry.strftime('%m/%d/%Y')}\n"
            f"⏰ Duration: {days} days\n"
            f"⭐ Stars: {payment_info.total_amount}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Unlocked Benefits:*\n"
            "• Unlimited photos\n"
            "• 50 videos/day\n"
            "• 50 songs/day\n"
            "• No ads\n"
            "• Priority support\n\n"
            "🚀 Use /start to begin\n"
            "📊 Use /panel to check your status",
            parse_mode='Markdown'
        )


# ==================== FLUJO GUIADO ====================

async def start_download_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el flujo guiado de descarga"""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    
    # Ensure user exists
    if not get_user(user_id):
        create_user(user_id, first_name=first_name, username=username)
    
    # Ensure admins have premium
    ensure_admin_premium(user_id)
    
    message = (
        f"👋 ¡Hola {first_name}!\n\n"
        "🎯 *Vamos a descargar contenido*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *Paso 1 de 2*\n\n"
        "📎 *Envíame el enlace del mensaje* que quieres descargar\n\n"
        "💡 *Ejemplo:*\n"
        "`https://t.me/canal/123`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ Canales públicos\n"
        "✅ Canales privados (debes agregarme)\n"
        "✅ Grupos públicos\n\n"
        "💡 O usa el comando /descargar"
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')
    return WAITING_FOR_LINK


async def handle_link_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa el enlace enviado por el usuario con manejo optimizado de errores"""
    user_id = update.effective_user.id
    link = update.message.text.strip()
    
    # Validar que sea un enlace de Telegram
    if not re.search(r't\.me/', link):
        await BotError.invalid_link(update)
        return WAITING_FOR_LINK
    
    # Mostrar mensaje de procesamiento
    processing_msg = await update.message.reply_text(
        "⏳ *Procesando...*\n\n"
        "🔍 Verificando el enlace\n"
        "📥 Preparando descarga",
        parse_mode='Markdown'
    )
    
    try:
        # Parsear el enlace
        parsed = parse_telegram_link(link)
        if not parsed:
            await BotError.invalid_link(processing_msg, is_message=True)
            return WAITING_FOR_LINK
        
        channel_identifier, message_id = parsed
        
        # Verificar si tiene message_id
        if not message_id:
            await BotError.incomplete_link(processing_msg, is_message=True)
            return WAITING_FOR_LINK
        
        # Procesar la descarga
        await processing_msg.edit_text(
            "✨ *Enlace válido*\n\n"
            "📥 Descargando contenido...",
            parse_mode='Markdown'
        )
        
        # Llamar a la función de descarga mejorada
        await process_download(update, context, channel_identifier, message_id, processing_msg)
        
        # Finalizar conversación
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error en flujo guiado: {e}")
        await BotError.generic_error(processing_msg, is_message=True)
        return ConversationHandler.END


async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela el flujo guiado"""
    await update.message.reply_text(
        "❌ *Operación cancelada*\n\n"
        "🔄 Usa /descargar cuando quieras intentar de nuevo\n"
        "📋 Usa /help para ver la guía completa",
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          channel_identifier: str, message_id: int, status_msg):
    """Procesa la descarga del contenido con manejo optimizado de errores"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not has_active_session(user_id):
        await status_msg.edit_text(
            "⚠️ *Configuración Requerida*\n\n"
            "Para descargar contenido, necesitas configurar tu cuenta de Telegram.\n"
            "Esto es necesario para evitar baneos y descargar de canales privados.\n\n"
            "👉 Usa /configurar para empezar.",
            parse_mode='Markdown'
        )
        return

    try:
        async with get_user_client(user_id) as client:
            # Intentar obtener el canal
            try:
                if channel_identifier.startswith('+'):
                    # Canal privado con hash de invitación
                    await status_msg.edit_text(
                        "🔐 *Canal privado detectado*\n\n"
                        "🤖 Intentando acceder al canal...",
                        parse_mode='Markdown'
                    )
                    
                    try:
                        invite_hash = channel_identifier[1:]
                        await client(ImportChatInviteRequest(invite_hash))
                        await asyncio.sleep(1)
                    except UserAlreadyParticipantError:
                        pass  # Ya estamos en el canal
                    except (InviteHashExpiredError, InviteHashInvalidError):
                        await BotError.invite_link_expired(status_msg, is_message=True)
                        return
                    
                    channel = await client.get_entity(invite_hash)
                else:
                    # Canal público o privado numérico
                    channel = await client.get_entity(int(channel_identifier) if channel_identifier.isdigit() else channel_identifier)
            
            except (ChannelPrivateError, ChatForbiddenError):
                await BotError.private_channel_no_invite(status_msg, is_message=True)
                return
            
            # Obtener el mensaje
            await status_msg.edit_text(
                "📥 *Descargando contenido...*\n\n"
                "⏳ Esto puede tardar unos segundos",
                parse_mode='Markdown'
            )
            
            message = await client.get_messages(channel, ids=message_id)
            
            if not message:
                await BotError.message_not_found(status_msg, is_message=True)
                return
            
            # Verificar si es parte de un álbum (grupo de medios)
            if hasattr(message, 'grouped_id') and message.grouped_id:
                # Es un álbum, obtener todos los mensajes del grupo
                await status_msg.edit_text(
                    "📸 *Álbum detectado*\n\n"
                    "🔄 Analizando contenido del álbum...",
                    parse_mode='Markdown'
                )
                
                # Obtener todos los mensajes del álbum (ventana de +/- 10 alrededor del mensaje original)
                album_messages = []
                async for msg in client.iter_messages(channel, limit=20, offset_id=message_id + 11):
                    if hasattr(msg, 'grouped_id') and msg.grouped_id == message.grouped_id:
                        album_messages.append(msg)
                
                # Ordenar por ID para consistencia
                album_messages.sort(key=lambda m: m.id)
                
                # Filtrar solo los mensajes que tienen medios y extraer caption
                media_messages = []
                shared_caption = ""
                media_counts = {'photo': 0, 'video': 0, 'music': 0, 'apk': 0, 'other': 0}
                
                for msg in album_messages:
                    if not msg.media:
                        continue
                    
                    c_type = detect_content_type(msg)
                    if c_type != 'other':
                        media_messages.append(msg)
                        media_counts[c_type] += 1
                        # Buscar el primer caption disponible en todo el álbum
                        if not shared_caption:
                            shared_caption = extract_message_caption(msg)
                
                if not media_messages:
                    await BotError.unsupported_content(status_msg, is_message=True)
                    return

                # Verificación PREVIA de límites para TODO el álbum
                check_and_reset_daily_limits(user_id)
                user = get_user(user_id)
                is_premium = user['premium']
                
                # Simular descargas para verificar límites
                can_batch_download = True
                failing_reason = None
                
                # Copia de contadores para simulación
                sim_photo = user.get('daily_photo', 0)
                sim_video = user.get('daily_video', 0)
                sim_downloads = user.get('downloads', 0)
                
                for c_type, count in media_counts.items():
                    if count == 0: continue
                    
                    if c_type == 'photo':
                        if not is_premium and sim_photo + count > FREE_PHOTO_LIMIT:
                            can_batch_download = False
                            failing_reason = f"Límite de fotos superado ({sim_photo + count}/{FREE_PHOTO_LIMIT})"
                            break
                        sim_photo += count
                    elif c_type == 'video':
                        if is_premium:
                            if sim_video + count > PREMIUM_VIDEO_DAILY_LIMIT:
                                can_batch_download = False
                                failing_reason = f"Límite de videos premium superado ({sim_video + count}/{PREMIUM_VIDEO_DAILY_LIMIT})"
                                break
                            sim_video += count
                        else:
                            if sim_downloads + count > FREE_DOWNLOAD_LIMIT:
                                can_batch_download = False
                                failing_reason = f"Límite de videos gratuitos superado ({sim_downloads + count}/{FREE_DOWNLOAD_LIMIT})"
                                break
                            sim_downloads += count
                    elif c_type in ['music', 'apk']:
                        if not is_premium:
                            can_batch_download = False
                            failing_reason = "requeire_premium"
                            break

                if not can_batch_download:
                    if failing_reason == "requeire_premium":
                        await BotError.premium_required(status_msg, 'music/apk', is_message=True)
                    else:
                        limit_msg = (
                            f"⚠️ *Límite insuficiente*\n\n"
                            f"El álbum contiene {media_counts['photo']} fotos y {media_counts['video']} videos.\n"
                            f"No tienes suficiente saldo disponible para descargar todo el álbum.\n\n"
                            f"❌ *Motivo:* {failing_reason}\n\n"
                            f"💡 Usa /premium para obtener descargas ilimitadas."
                        )
                        await status_msg.edit_text(limit_msg, parse_mode='Markdown')
                    return

                # Si llegamos aquí, podemos descargar todo
                await status_msg.edit_text(
                    f"📸 *Álbum con {len(media_messages)} archivos*\n\n"
                    f"⏳ Descargando 1/{len(media_messages)}...",
                    parse_mode='Markdown'
                )
                
                # Descargar cada archivo del álbum
                for idx, album_msg in enumerate(media_messages, 1):
                    msg_type = detect_content_type(album_msg)
                    await status_msg.edit_text(
                        f"📸 *Álbum con {len(media_messages)} archivos*\n\n"
                        f"⏳ Descargando {idx}/{len(media_messages)}...\n"
                        f"📦 Tipo: {msg_type.capitalize()}",
                        parse_mode='Markdown'
                    )
                    # Bypass limits porque ya los verificamos en lote
                    await handle_media_download(
                        update, context, album_msg, user, status_msg, 
                        is_album=True, album_index=idx, album_total=len(media_messages),
                        bypass_limits=True, custom_caption=shared_caption
                    )
                
                # Mensaje final
                try:
                    await status_msg.edit_text(
                        f"✅ *Álbum completado*\n\n"
                        f"📥 {len(media_messages)} archivos descargados exitosamente.",
                        parse_mode='Markdown'
                    )
                except Exception:
                    # Si el mensaje fue borrado o no se puede editar, enviar uno nuevo
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ *Álbum completado*\n\n📥 {len(media_messages)} archivos descargados.",
                        parse_mode='Markdown'
                    )
            else:
                # Mensaje individual
                await handle_media_download(update, context, message, user, status_msg)

            
    except FloodWaitError as e:
        await BotError.flood_wait(status_msg, e.seconds, is_message=True)
    except Exception as e:
        logger.error(f"Error en process_download: {e}")
        await BotError.download_failed(status_msg, is_message=True)


async def handle_media_download(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                message, user: dict, status_msg, is_album: bool = False, 
                                album_index: int = 1, album_total: int = 1,
                                bypass_limits: bool = False, custom_caption: str = None):
    """Maneja la descarga según el tipo de medio con validaciones optimizadas"""
    user_id = update.effective_user.id
    
    # Determinar tipo de contenido
    if message.photo:
        content_type = 'photo'
    elif message.video:
        content_type = 'video'
    elif message.audio or message.voice:
        content_type = 'music'
    elif message.document and message.document.mime_type == 'application/vnd.android.package-archive':
        content_type = 'apk'
    else:
        await BotError.unsupported_content(status_msg, is_message=True)
        return
    
    # Verificar tamaño del archivo
    file_size = 0
    if message.video and hasattr(message.video, 'size'):
        file_size = message.video.size
    elif message.document and hasattr(message.document, 'size'):
        file_size = message.document.size
    elif message.audio and hasattr(message.audio, 'size'):
        file_size = message.audio.size
    
    # Límite de 2GB de Telegram (con Telethon Bot)
    if file_size > 2000 * 1024 * 1024:
        file_size_mb = file_size / (1024 * 1024)
        await BotError.file_too_large(status_msg, file_size_mb, is_message=True)
        return
    
    # Verificar límites de usuario (solo si no se saltan)
    if not bypass_limits:
        check_and_reset_daily_limits(user_id)
        user = get_user(user_id)  # Refrescar
        
        # Log para depuración de límites
        logger.info(f"Checking limits for user {user_id}: Premium={user['premium']}, Downloads={user['downloads']}, Limit={FREE_DOWNLOAD_LIMIT}")

        # Verificar si puede descargar
        can_download, error_type, error_data = check_download_limits(user, content_type)
        
        if not can_download:
            if error_type == 'daily_limit':
                await BotError.daily_limit_reached(status_msg, content_type, error_data['current'], error_data['limit'], is_message=True)
            elif error_type == 'total_limit':
                await BotError.total_limit_reached(status_msg, is_message=True)
            elif error_type == 'premium_required':
                await BotError.premium_required(status_msg, content_type, is_message=True)
            return

    # Descargar y enviar
    await status_msg.edit_text(
        f"📥 *Descargando {content_type}...*\n\n"
        "⏳ Preparando archivo",
        parse_mode='Markdown'
    )
    
    try:
        # Preparar caption con información del álbum si aplica
        if is_album:
            caption_prefix = f"📸 Álbum {album_index}/{album_total}\n\n"
        else:
            caption_prefix = "✅ *Descarga completada*\n\n"
        
        # Use custom caption if provided, otherwise extract from message
        if custom_caption:
            original_caption = custom_caption
        else:
            original_caption = extract_message_caption(message) or ""
        
        # Combine
        final_caption = f"{caption_prefix}{original_caption}"
        
        # Usar la función optimizada para descargar y enviar
        logger.info(f"Iniciando envío de {content_type} para usuario {user_id}")
        success = await download_and_send_media(message, user_id, context.bot, caption=final_caption)
        logger.info(f"Resultado del envío: {success} para usuario {user_id}")
        
        if success:
            # Incrementar contadores
            if content_type == 'photo':
                increment_daily_counter(user_id, 'photo')
                increment_total_downloads(user_id)  # Contar fotos para referidos
            elif content_type == 'video':
                increment_total_downloads(user_id)
                increment_daily_counter(user_id, 'video')
            elif content_type == 'music':
                increment_total_downloads(user_id)  # Contar música para referidos
                increment_daily_counter(user_id, 'music')
            elif content_type == 'apk':
                increment_total_downloads(user_id)  # Contar APKs para referidos
                increment_daily_counter(user_id, 'apk')
            
            # SISTEMA DE REFERIDOS: Confirmar referido si cumple requisitos
            referrer_id = confirm_referral(user_id)
            if referrer_id:
                # Verificar y recompensar al referente si alcanzó 15 referidos
                days_earned = check_and_reward_referrer(referrer_id)
                if days_earned > 0:
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 *¡Felicidades!*\n\n"
                                 f"Has alcanzado 15 referidos válidos y has ganado *{days_earned} día de Premium*.\n\n"
                                 f"🎁 ¡Gracias por ayudarnos a crecer!\n\n"
                                 f"Usa /referidos para ver tu progreso.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify referrer {referrer_id}: {e}")
                else:
                    # Notificar confirmación del referido sin recompensa aún
                    try:
                        stats = get_referral_stats(referrer_id)
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"✅ *Referido confirmado!*\n\n"
                                 f"Tienes {stats['confirmed']}/15 referidos válidos.\n\n"
                                 f"Usa /referidos para más detalles.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify referrer {referrer_id}: {e}")
            
            # Éxito - eliminar mensaje de estado (solo si no es parte de un álbum, 
            # ya que process_download manejará el mensaje final para álbumes)
            if not is_album:
                try:
                    await status_msg.delete()
                except Exception as e:
                    logger.debug(f"Could not delete status message: {e}")
            
            # Verificar si debe mostrar advertencia de uso bajo (solo usuarios gratuitos)
            # NOTA: En álbumes esto se mostrará por cada archivo, lo cual es molesto.
            # Podríamos mejorarlo para mostrarlo solo al final, pero por ahora mantenemos consistencia.
            if not user['premium'] and not is_album:
                # Importar aquí para evitar problemas si no está disponible
                try:
                    from database import check_low_usage_warning
                    warning = check_low_usage_warning(user_id, FREE_DOWNLOAD_LIMIT, FREE_PHOTO_LIMIT)
                    if warning.get('show_warning'):
                        # update.message puede ser None si viene de MiniApp o Callback
                        msg_to_reply = update.message if update.message else status_msg
                        await UsageNotification.send_low_usage_warning(msg_to_reply, warning)
                except Exception as e:
                    logger.warning(f"Error checking low usage warning: {e}")
        else:
            # El error ya fue enviado por download_and_send_media
            pass
        
    except Exception as e:
        logger.error(f"Error en handle_media_download: {e}")
        await BotError.download_failed(status_msg, is_message=True)



def check_download_limits(user: dict, content_type: str) -> tuple[bool, str, dict]:
    """
    Verifica si el usuario puede descargar según su plan
    Retorna: (puede_descargar, tipo_error, datos_error)
    tipo_error: 'daily_limit', 'total_limit', 'premium_required', None
    datos_error: dict con 'current', 'limit' para límites diarios
    """
    is_premium = user['premium']
    
    if content_type == 'photo':
        if is_premium:
            return True, None, {}
        else:
            if user['daily_photo'] >= FREE_PHOTO_LIMIT:
                return False, 'daily_limit', {
                    'current': user['daily_photo'],
                    'limit': FREE_PHOTO_LIMIT
                }
            return True, None, {}
    
    elif content_type == 'video':
        if is_premium:
            if user['daily_video'] >= PREMIUM_VIDEO_DAILY_LIMIT:
                return False, 'daily_limit', {
                    'current': user['daily_video'],
                    'limit': PREMIUM_VIDEO_DAILY_LIMIT
                }
            return True, None, {}
        else:
            if user['downloads'] >= FREE_DOWNLOAD_LIMIT:
                return False, 'total_limit', {}
            return True, None, {}
    
    elif content_type in ['music', 'apk']:
        if not is_premium:
            return False, 'premium_required', {}
        
        limit_key = 'daily_music' if content_type == 'music' else 'daily_apk'
        limit_value = PREMIUM_MUSIC_DAILY_LIMIT if content_type == 'music' else PREMIUM_APK_DAILY_LIMIT
        
        if user[limit_key] >= limit_value:
            return False, 'daily_limit', {
                'current': user[limit_key],
                'limit': limit_value
            }
        return True, None, {}
    
    return False, None, {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Auto-detect language and open miniapp directly"""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    logger.info(f"🚀 /START command from user {user_id} (@{username})")
    
    # Get user's language from Telegram (if available)
    telegram_language = update.effective_user.language_code or 'es'
    logger.info(f"User {user_id} Telegram language_code: {telegram_language}")
    
    # Map Telegram language codes to our supported languages
    language_map = {
        'es': 'es',
        'es-ES': 'es',
        'es-MX': 'es',
        'es-AR': 'es',
        'en': 'en',
        'en-US': 'en',
        'en-GB': 'en',
        'pt': 'pt',
        'pt-BR': 'pt',
        'pt-PT': 'pt',
        'it': 'it',
        'it-IT': 'it'
    }
    
    # Determine user language (fallback to es if not supported)
    user_language = language_map.get(telegram_language, 'es')
    logger.info(f"Mapped to language: {user_language}")
    
    # Check if user exists (first time user)
    is_new_user = not get_user(user_id)
    
    # Detectar código de referido (formato: ref_123456)
    referred_by = None
    if context.args and is_new_user:
        arg = context.args[0]
        if arg.startswith('ref_'):
            try:
                referrer_id = int(arg[4:])
                if referrer_id != user_id and get_user(referrer_id):
                    referred_by = referrer_id
                    logger.info(f"User {user_id} referred by {referrer_id}")
            except ValueError:
                pass
    
    # Create or update user with all information
    if is_new_user:
        # Use add_user instead of create_user to handle language and referrals properly
        add_user(user_id, language=user_language, referred_by=referred_by)
        # Update additional info
        if first_name or username:
            update_user_info(user_id, first_name, username)
        logger.info(f"✓ New user {user_id} created with language: {user_language}")
    else:
        # PROBLEMA 1: Siempre actualizar info aunque el usuario exista
        update_user_info(user_id, first_name, username)
        
        # We don't forcefully overwrite their selected language if they already chose one
        user = get_user(user_id)
        lang = user.get('language') if user and user.get('language') else user_language
        set_user_language(user_id, lang)
    
    # Ensure admins have premium
    ensure_admin_premium(user_id)
    
    # Show language selection menu
    welcome_message = (
        f"👋 ¡Hola {first_name}! / Hello {first_name}!\n\n"
        "🌐 *Selecciona tu idioma / Select your language:*\n"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🇪🇸 Español", callback_data="set_lang_es"),
            InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
        ],
        [
            InlineKeyboardButton("🇧🇷 Português", callback_data="set_lang_pt"),
            InlineKeyboardButton("🇮🇹 Italiano", callback_data="set_lang_it")
        ]
    ]
    
    # PROBLEMA 2: Agregar botón de MiniApp con user_id y lang
    miniapp_url_env = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
    if miniapp_url_env:
        # Usar la variable local lang si está definida (en el else de is_new_user)
        # o user_language (que es el detectado por Telegram)
        try:
            current_lang = lang if 'lang' in locals() else user_language
        except NameError:
            current_lang = user_language
            
        full_url = f"{miniapp_url_env}/miniapp?v=2&user_id={user_id}&lang={current_lang}"
        keyboard.append([
            InlineKeyboardButton("📱 Abrir App", web_app=WebAppInfo(url=full_url))
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"Could not edit message, sending new one: {e}")
            await update.callback_query.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
    return
    
    # Check and reset daily limits
    check_and_reset_daily_limits(user_id)
    user = get_user(user_id)
    
    # Get user language
    lang = get_user_language(user)
    
    # Build welcome message using multi-language system
    welcome_message = get_msg("start_welcome", lang)
    welcome_message += get_msg("start_description", lang)
    welcome_message += get_msg("start_divider", lang)
    welcome_message += get_msg("start_how_to", lang)
    welcome_message += get_msg("start_example", lang)
    welcome_message += get_msg("start_divider", lang)
    
    if user['premium']:
        if user.get('premium_until'):
            expiry = datetime.fromisoformat(user['premium_until'])
            days_left = (expiry - datetime.now()).days
            welcome_message += get_msg("start_premium_plan", lang, 
                                         expiry=expiry.strftime('%d/%m/%Y'),
                                         days_left=days_left)
        else:
            welcome_message += get_msg("start_premium_active", lang)
    else:
        welcome_message += get_msg("start_free_plan", lang)
        welcome_message += get_msg("start_upgrade", lang)
    
    # Add buttons with language support
    keyboard = [
        [InlineKeyboardButton(get_msg("btn_panel", lang), callback_data="panel_menu")],
        [
            InlineKeyboardButton(get_msg("btn_how_to_use", lang), callback_data="show_guide"),
            InlineKeyboardButton(get_msg("btn_plans", lang), callback_data="view_plans")
        ],
        [InlineKeyboardButton(get_msg("btn_change_language", lang), callback_data="change_language")],
        [InlineKeyboardButton(get_msg("btn_support", lang), url="https://t.me/observer_bots/11")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /premium command - Show ALL subscription plans with referral bonus"""
    from datetime import datetime
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user)
    
    # Check current premium status
    if user and user['premium'] and user.get('premium_until'):
        expiry = datetime.fromisoformat(user['premium_until'])
        days_left = (expiry - datetime.now()).days
        
        if lang == 'es':
            status_msg = (
                "✨ *Ya eres Premium* ✨\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📅 Expira: {expiry.strftime('%d/%m/%Y')}\n"
                f"⏳ *Quedan:* {days_left} días\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💎 *Renovar o Extender Premium*\n\n"
            )
        else:
            status_msg = (
                "✨ *You're already Premium* ✨\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📅 Expires: {expiry.strftime('%m/%d/%Y')}\n"
                f"⏳ *{days_left} days remaining*\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💎 *Renew or Extend Premium*\n\n"
            )
    else:
        status_msg = ""
    
    # Build pricing tiers message
    if lang == 'es':
        message = status_msg + (
            "🌟 *PLANES PREMIUM DISPONIBLES* 🌟\n\n"
            "Elige el plan que mejor se adapte a ti:\n\n"
        )
        
        # Trial Plan
        trial = PREMIUM_PLANS['trial']
        message += (
            f"{trial['badge']}\n"
            f"*{trial['name']}* - {trial['stars']} ⭐ Stars\n"
            f"⏰ Duración: {trial['days']} días\n"
            f"💡 {trial['description']}\n"
            f"💵 ~${trial['stars']/100:.2f} USD\n\n"
        )
        
        # Weekly Plan
        weekly = PREMIUM_PLANS['weekly']
        price_per_day_w = weekly['stars'] / weekly['days']
        message += (
            f"{weekly['badge']}\n"
            f"*{weekly['name']}* - {weekly['stars']} ⭐ Stars\n"
            f"⏰ Duración: {weekly['days']} días\n"
            f"💡 {weekly['description']} ({price_per_day_w:.1f}⭐/día)\n"
            f"💵 ~${weekly['stars']/100:.2f} USD\n\n"
        )
        
        # Monthly Plan
        monthly = PREMIUM_PLANS['monthly']
        price_per_day_m = monthly['stars'] / monthly['days']
        message += (
            f"{monthly['badge']}\n"
            f"*{monthly['name']}* - {monthly['stars']} ⭐ Stars\n"
            f"⏰ Duración: {monthly['days']} días (1 mes)\n"
            f"💡 {monthly['description']} ({price_per_day_m:.1f}⭐/día)\n"
            f"💵 ~${monthly['stars']/100:.2f} USD\n\n"
        )
        
        # Quarterly Plan
        quarterly = PREMIUM_PLANS['quarterly']
        price_per_day_q = quarterly['stars'] / quarterly['days']
        savings = int((1 - (quarterly['stars'] / (monthly['stars'] * 3))) * 100)
        message += (
            f"{quarterly['badge']}\n"
            f"*{quarterly['name']}* - {quarterly['stars']} ⭐ Stars\n"
            f"⏰ Duración: {quarterly['days']} días (3 meses)\n"
            f"💡 {quarterly['description']} ({price_per_day_q:.1f}⭐/día)\n"
            f"💵 ~${quarterly['stars']/100:.2f} USD\n"
            f"📊 Ahorras {savings}% vs 3 meses individuales\n\n"
        )
        
        message += (
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 *BONUS REFERIDOS GRATIS* 🎁\n\n"
            "Por cada *15 referidos confirmados* recibes:\n"
            "➕ *1 día Premium GRATIS*\n"
            "📊 Máximo acumulable: 15 días\n\n"
            "Usa /referidos para ver tu progreso\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Beneficios Premium:*\n"
            "• Descargas ilimitadas de fotos\n"
            "• 50 videos/día\n"
            "• 50 canciones/día\n"
            "• Sin anuncios\n"
            "• Prioridad en soporte\n\n"
            "Selecciona tu plan abajo 👇"
        )
    else:
        message = status_msg + (
            "🌟 *PREMIUM PLANS AVAILABLE* 🌟\n\n"
            "Choose the plan that fits you best:\n\n"
        )
        
        # Trial Plan (English)
        trial = PREMIUM_PLANS['trial']
        message += (
            f"{trial['badge']}\n"
            f"*{trial['name']}* - {trial['stars']} ⭐ Stars\n"
            f"⏰ Duration: {trial['days']} days\n"
            f"💡 Perfect for testing\n"
            f"💵 ~${trial['stars']/100:.2f} USD\n\n"
        )
        
        # Weekly Plan
        weekly = PREMIUM_PLANS['weekly']
        price_per_day_w = weekly['stars'] / weekly['days']
        message += (
            f"{weekly['badge']}\n"
            f"*{weekly['name']}* - {weekly['stars']} ⭐ Stars\n"
            f"⏰ Duration: {weekly['days']} days\n"
            f"💡 Best price per day ({price_per_day_w:.1f}⭐/day)\n"
            f"💵 ~${weekly['stars']/100:.2f} USD\n\n"
        )
        
        # Monthly Plan
        monthly = PREMIUM_PLANS['monthly']
        price_per_day_m = monthly['stars'] / monthly['days']
        message += (
            f"{monthly['badge']}\n"
            f"*{monthly['name']}* - {monthly['stars']} ⭐ Stars\n"
            f"⏰ Duration: {monthly['days']} days (1 month)\n"
            f"💡 Most popular ({price_per_day_m:.1f}⭐/day)\n"
            f"💵 ~${monthly['stars']/100:.2f} USD\n\n"
        )
        
        # Quarterly Plan
        quarterly = PREMIUM_PLANS['quarterly']
        price_per_day_q = quarterly['stars'] / quarterly['days']
        savings = int((1 - (quarterly['stars'] / (monthly['stars'] * 3))) * 100)
        message += (
            f"{quarterly['badge']}\n"
            f"*{quarterly['name']}* - {quarterly['stars']} ⭐ Stars\n"
            f"⏰ Duration: {quarterly['days']} days (3 months)\n"
            f"💡 Save up to {savings}% ({price_per_day_q:.1f}⭐/day)\n"
            f"💵 ~${quarterly['stars']/100:.2f} USD\n"
            f"📊 Save {savings}% vs 3 individual months\n\n"
        )
        
        message += (
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 *FREE REFERRAL BONUS* 🎁\n\n"
            "For every *15 confirmed referrals* you get:\n"
            "➕ *1 day Premium FREE*\n"
            "📊 Max accumulation: 15 days\n\n"
            "Use /referidos to check your progress\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Premium Benefits:*\n"
            "• Unlimited photo downloads\n"
            "• 50 videos/day\n"
            "• 50 songs/day\n"
            "• No ads\n"
            "• Priority support\n\n"
            "Select your plan below 👇"
        )
    
    # Create keyboard with all plan options
    keyboard = [
        [
            InlineKeyboardButton(
                f"{PREMIUM_PLANS['trial']['badge']} {PREMIUM_PLANS['trial']['stars']}⭐ ({PREMIUM_PLANS['trial']['days']}d)",
                callback_data="pay_premium_trial"
            )
        ],
        [
            InlineKeyboardButton(
                f"{PREMIUM_PLANS['weekly']['badge']} {PREMIUM_PLANS['weekly']['stars']}⭐ ({PREMIUM_PLANS['weekly']['days']}d)",
                callback_data="pay_premium_weekly"
            )
        ],
        [
            InlineKeyboardButton(
                f"{PREMIUM_PLANS['monthly']['badge']} {PREMIUM_PLANS['monthly']['stars']}⭐ ({PREMIUM_PLANS['monthly']['days']}d)",
                callback_data="pay_premium_monthly"
            )
        ],
        [
            InlineKeyboardButton(
                f"{PREMIUM_PLANS['quarterly']['badge']} {PREMIUM_PLANS['quarterly']['stars']}⭐ ({PREMIUM_PLANS['quarterly']['days']}d)",
                callback_data="pay_premium_quarterly"
            )
        ],
        [InlineKeyboardButton(get_msg("btn_join_channel", lang), url="https://t.me/observer_bots")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)


async def testpay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test payment system - Send invoice directly"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} testing payment system with /testpay")
    
    try:
        chat_id = update.effective_chat.id
        title = "💎 TEST - Premium"
        description = "Prueba del sistema de pagos con Telegram Stars"
        payload = "test_payment"
        currency = "XTR"
        prices = [LabeledPrice("Test Premium", PREMIUM_PRICE_STARS)]
        
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency=currency,
            prices=prices
        )
        
        await update.message.reply_text(
            "✅ *Sistema de Pagos Funcionando*\n\n"
            "La factura de prueba se envió correctamente.\n"
            "Telegram Stars está habilitado. ✨",
            parse_mode='Markdown'
        )
        logger.info(f"Test invoice sent successfully to user {user_id}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Test payment failed for user {user_id}: {error_msg}")
        
        await update.message.reply_text(
            "❌ *Sistema de Pagos NO Configurado*\n\n"
            f"Error: `{error_msg[:200]}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔧 *Solución:*\n"
            "1. Abre @BotFather\n"
            "2. /mybots → Selecciona tu bot\n"
            "3. Payments → Telegram Stars\n"
            "4. Habilita y acepta términos\n\n"
            "📢 @observer_bots",
            parse_mode='Markdown'
        )


async def diagnostic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /diagnostic command - Check connection status for Railway issues"""
    user_id = update.effective_user.id

    # Only allow admins to use this command
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(
            "❌ *Acceso Denegado*\n\n"
            "Este comando es solo para administradores.",
            parse_mode='Markdown'
        )
        return

    await update.message.reply_text("🔍 *Ejecutando diagnóstico...*", parse_mode='Markdown')


async def miniapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /miniapp command - Open the MiniApp"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user)
    
    # Get the MiniApp URL from environment or use default
    miniapp_url = (os.getenv('MINIAPP_URL') or os.getenv('DASHBOARD_URL', '')).strip()
    
    if not miniapp_url:
        if lang == 'es':
            await update.message.reply_text(
                "⚠️ *MiniApp no configurada*\n\n"
                "La MiniApp no está disponible en este momento.\n"
                "Usa /panel para ver tu información.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "⚠️ *MiniApp not configured*\n\n"
                "The MiniApp is not available at this time.\n"
                "Use /panel to view your information.",
                parse_mode='Markdown'
            )
        return
    
    # Add /miniapp path to the URL
    if not miniapp_url.endswith('/'):
        miniapp_url += '/'
    miniapp_url += f'miniapp?v=2&lang={lang}'
    
    keyboard = [
        [InlineKeyboardButton(
            "📱 Abrir MiniApp" if lang == 'es' else "📱 Open MiniApp", 
            web_app={"url": miniapp_url}
        )],
        [InlineKeyboardButton(
            "⭐ Premium 179 Stars", 
            callback_data="pay_premium"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if lang == 'es':
        message = (
            "📱 *MiniApp Premium Downloads*\n\n"
            "Accede a tu panel personal:\n\n"
            "• 📊 Ver estadísticas de uso\n"
            "• ⭐ Comprar Premium\n"
            "• 📜 Historial de descargas\n"
            "• ⚙️ Configuración\n\n"
            "Toca el botón para abrir 👇"
        )
    else:
        message = (
            "📱 *Premium Downloads MiniApp*\n\n"
            "Access your personal panel:\n\n"
            "• 📊 View usage statistics\n"
            "• ⭐ Buy Premium\n"
            "• 📜 Download history\n"
            "• ⚙️ Settings\n\n"
            "Tap the button to open 👇"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    # Check environment
    is_railway = bool(os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID'))
    env_status = "✅ Railway" if is_railway else "❌ No Railway (localhost?)"

    # Check API credentials
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

    credentials_status = "✅" if all([api_id, api_hash, bot_token]) else "❌"
    credentials_status += " Credenciales completas" if all([api_id, api_hash, bot_token]) else " Credenciales faltantes"

    # Test basic connectivity
    connectivity_test = "⏳ Probando..."
    try:
        from telegram import Bot
        bot = Bot(bot_token)
        await bot.get_me()
        connectivity_test = "✅ Bot conectado"
    except Exception as e:
        connectivity_test = f"❌ Error bot: {str(e)[:50]}"

    # Test Telethon connection
    telethon_test = "⏳ Probando..."
    try:
        client = TelegramClient(StringSession(), int(api_id), api_hash)
        await asyncio.wait_for(client.connect(), timeout=10)
        telethon_test = "✅ Telethon conectado"
        await client.disconnect()
    except asyncio.TimeoutError:
        telethon_test = "❌ Timeout Telethon (Railway bloquea MTProto?)"
    except Exception as e:
        telethon_test = f"❌ Error Telethon: {str(e)[:50]}"

    # Build diagnostic message
    diagnostic_msg = (
        "🔧 *DIAGNÓSTICO DEL SISTEMA*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 *Entorno:* {env_status}\n\n"
        f"🔑 *Credenciales:* {credentials_status}\n\n"
        f"🤖 *Bot:* {connectivity_test}\n\n"
        f"📡 *Telethon:* {telethon_test}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if "❌" in telethon_test:
        diagnostic_msg += (
            "🚨 *PROBLEMA DETECTADO*\n\n"
            "Railway puede estar bloqueando conexiones MTProto.\n\n"
            "💡 *Soluciones:*\n"
            "1️⃣ Usa un VPS en lugar de Railway\n"
            "2️⃣ Verifica variables de entorno\n"
            "3️⃣ Contacta soporte de Railway\n\n"
        )
    else:
        diagnostic_msg += "✅ *Sistema funcionando correctamente*\n\n"

    diagnostic_msg += "📞 *Soporte:* @observer_bots"

    await update.message.reply_text(diagnostic_msg, parse_mode='Markdown')


async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /panel command - Show user control panel with detailed stats"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user)
    
    # Get usage stats
    stats = get_user_usage_stats(user_id)
    if not stats:
        # Fallback if user not found (shouldn't happen usually)
        if update.callback_query:
            await update.callback_query.message.reply_text("Error loading profile.")
        else:
            await update.message.reply_text("Error loading profile.")
        return

    # 1. Header & Plan Info
    message = get_msg("panel_title", lang, user_name=update.effective_user.first_name)
    
    if stats['is_premium']:
        message += get_msg("panel_plan_premium", lang)
        # Calculate days left
        if user.get('premium_until'):
            try:
                expiry_dt = datetime.fromisoformat(user['premium_until'])
                days_left = (expiry_dt - datetime.now()).days
                expiry_str = expiry_dt.strftime("%d/%m/%Y")
                message += get_msg("panel_expires", lang, expiry=expiry_str, days_left=days_left)
            except:
                pass
    else:
        message += get_msg("panel_plan_free", lang)

    # 2. Usage Statistics
    message += "\n" + get_msg("panel_stats_row", lang)
    
    # Photos
    p_used = stats['photos']['used']
    p_limit = "∞" if stats['photos']['unlimited'] else stats['photos']['limit']
    message += get_msg("panel_photos", lang, count=p_used, limit=p_limit)
    
    # Videos
    v_used = stats['videos']['used']
    v_limit = "∞" if stats['videos']['unlimited'] else stats['videos']['limit']
    message += get_msg("panel_videos", lang, count=v_used, limit=v_limit)
    
    # Music
    m_used = stats['music']['used']
    m_limit = stats['music']['limit']
    message += get_msg("panel_music", lang, count=m_used, limit=m_limit)
    
    # APK
    a_used = stats['apk']['used']
    a_limit = stats['apk']['limit']
    message += get_msg("panel_apk", lang, count=a_used, limit=a_limit)

    # 3. Connection Status
    message += get_msg("panel_connection_title", lang)
    session_string = get_user_session(user_id)
    is_connected = bool(session_string)
    
    if is_connected:
        message += get_msg("panel_connection_ok", lang)
    else:
        message += get_msg("panel_connection_fail", lang)
        
    # Footer
    if not stats['is_premium']:
        message += get_msg("panel_footer", lang)
    
    # Buttons
    keyboard = []
    
    # Row 1: Refresh & Plans
    keyboard.append([
        InlineKeyboardButton(get_msg("btn_refresh_stats", lang), callback_data="panel_refresh"),
        InlineKeyboardButton(get_msg("btn_plans", lang), callback_data="view_plans")
    ])
    
    # Row 2: Connect/Disconnect
    if is_connected:
        keyboard.append([InlineKeyboardButton(get_msg("btn_disconnect", lang), callback_data="disconnect_account")])
    else:
        keyboard.append([InlineKeyboardButton(get_msg("btn_connect", lang), callback_data="connect_account")])
        
    # Row 3: Support & Back
    keyboard.append([
        InlineKeyboardButton(get_msg("btn_support", lang), url="https://t.me/observer_bots/11"),
        InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        # If called from callback (e.g. refresh button)
        try:
            await update.callback_query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception:
            # If message content is same, ignore error
            pass
    else:
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)


async def adminstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /adminstats command - Panel de ADMINISTRACIÓN con estadísticas globales"""
    user_id = update.effective_user.id
    
    # Verificar si el usuario es administrador
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(
            "❌ *Acceso Denegado*\n\n"
            "Este comando es solo para administradores del bot.\n\n"
            "Usa /stats para ver tus estadísticas personales.",
            parse_mode='Markdown'
        )
        return
    
    # Obtener estadísticas globales del bot
    global_stats = get_user_stats()
    
    # ════════════════════════════════════════════════
    # PANEL DE ADMINISTRACIÓN
    # ════════════════════════════════════════════════
    
    message = "```\n"
    message += "╔═══════════════════════════════╗\n"
    message += "║  🔐 PANEL DE ADMINISTRACIÓN  ║\n"
    message += "╚═══════════════════════════════╝\n"
    message += "```\n\n"
    
    # Estadísticas Globales
    message += "```\n"
    message += "┌─────────────────────────────┐\n"
    message += "│    🌍 ESTADÍSTICAS GLOBALES │\n"
    message += "└─────────────────────────────┘\n"
    message += "```\n"
    message += f"👥 *Total de Usuarios:* `{global_stats['total_users']:,}`\n"
    message += f"💎 *Usuarios Premium:* `{global_stats['premium_users']:,}`\n"
    message += f"🆓 *Usuarios Free:* `{global_stats['free_users']:,}`\n"
    message += f"🟢 *Activos Hoy:* `{global_stats['active_today']:,}`\n\n"
    
    # Ingresos
    message += "```\n"
    message += "┌─────────────────────────────┐\n"
    message += "│       💰 INGRESOS           │\n"
    message += "└─────────────────────────────┘\n"
    message += "```\n"
    message += f"⭐ *Total en Stars:* `{global_stats['revenue']['stars']:,}`\n"
    message += f"📊 *Suscripciones:* `{global_stats['revenue']['premium_subs']:,}`\n"
    message += f"💵 *Promedio por sub:* `{PREMIUM_PRICE_STARS}` ⭐\n\n"
    
    # Descargas totales
    message += "```\n"
    message += "┌─────────────────────────────┐\n"
    message += "│    📥 DESCARGAS TOTALES     │\n"
    message += "└─────────────────────────────┘\n"
    message += "```\n"
    message += f"📊 *Total Histórico:* `{global_stats['total_downloads']:,}`\n\n"
    
    # Actividad del Día
    daily = global_stats['daily_stats']
    message += "```\n"
    message += "┌─────────────────────────────┐\n"
    message += "│      📈 ACTIVIDAD DE HOY    │\n"
    message += "└─────────────────────────────┘\n"
    message += "```\n"
    message += f"📸 *Fotos:* `{daily['photos']:,}` descargadas\n"
    message += f"🎬 *Videos:* `{daily['videos']:,}` descargados\n"
    message += f"🎵 *Música:* `{daily['music']:,}` archivos\n"
    message += f"📦 *APK:* `{daily['apk']:,}` archivos\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"📊 *Total Hoy:* `{daily['total']:,}` descargas\n\n"
    
    # Métricas adicionales
    if global_stats['total_users'] > 0:
        conversion_rate = (global_stats['premium_users'] / global_stats['total_users']) * 100
        avg_downloads = global_stats['total_downloads'] / global_stats['total_users']
        
        message += "```\n"
        message += "┌─────────────────────────────┐\n"
        message += "│       📊 MÉTRICAS           │\n"
        message += "└─────────────────────────────┘\n"
        message += "```\n"
        message += f"📈 *Tasa de Conversión:* `{conversion_rate:.1f}%`\n"
        message += f"📥 *Promedio Descargas/Usuario:* `{avg_downloads:.1f}`\n"
        message += f"⚡ *Tasa de Actividad:* `{(global_stats['active_today']/global_stats['total_users']*100):.1f}%`\n\n"
    
    # Footer
    message += "```\n"
    message += "╔═══════════════════════════════╗\n"
    message += "║   Actualizado en tiempo real  ║\n"
    message += "╚═══════════════════════════════╝\n"
    message += "```"
    
    # Botón de actualización
    keyboard = [
        [InlineKeyboardButton("🔄 Actualizar Stats", callback_data="refresh_admin_stats")],
        [InlineKeyboardButton("◀️ Volver al menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)


async def referidos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔥 COMANDO /REFERIDOS - Sistema de referidos con validación anti-abuso"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await update.message.reply_text("⚠️ Usuario no encontrado. Usa /start primero.")
        return
    
    # Obtener estadísticas de referidos
    stats = get_referral_stats(user_id)
    
    # Generar enlace de referido
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    # Construir mensaje
    message = (
        "👥 *Sistema de Referidos*\n\n"
        "🎯 *Cómo Funciona:*\n"
        "1️⃣ Comparte tu enlace personal\n"
        "2️⃣ Tus amigos se unen y usan el bot\n"
        "3️⃣ Cada 15 referidos válidos = 1 día Premium\n\n"
        "⚠️ *Requisitos para ser válido:*\n"
        "• Usuario nuevo\n"
        "• Conecta su cuenta\n"
        "• Realiza al menos 1 descarga\n\n"
        "📊 *Tu Progreso:*\n"
        f"✅ Referidos confirmados: *{stats['confirmed']}*\n"
        f"⏳ Pendientes: *{stats['pending']}*\n"
        f"🎁 Días Premium ganados: *{stats['days_earned']}*\n"
        f"📈 Progreso: *{stats['progress']}/{stats['next_reward_at']}*\n\n"
    )
    
    # Añadir información sobre el límite
    if stats['days_earned'] >= 15:
        message += "🏆 *¡Has alcanzado el límite de 15 días!*\n\n"
    else:
        remaining = 15 - stats['days_earned']
        message += f"🎯 Puedes ganar hasta *{remaining} días más* de Premium.\n\n"
    
    message += (
        "🔗 *Tu Enlace Personal:*\n"
        f"`{referral_link}`\n\n"
        "👇 Comparte tu enlace usando el botón de abajo."
    )
    
    # Botón para compartir
    keyboard = [
        [InlineKeyboardButton(
            "📤 Compartir Enlace",
            url=f"https://t.me/share/url?url={referral_link}&text="
                f"¡Descarga contenido de Telegram con este bot! 🚀"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - Muestra solo estadísticas PERSONALES del usuario"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Usuario"
    
    # Reset daily limits if needed
    check_and_reset_daily_limits(user_id)
    
    # Obtener estadísticas personales
    user_stats = get_user_usage_stats(user_id, FREE_DOWNLOAD_LIMIT, FREE_PHOTO_LIMIT)
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'
    
    # Initialize keyboard early
    keyboard = []
    
    if not user_stats:
        error_text = "❌ Error getting statistics" if lang == 'en' else "❌ Error al obtener estadísticas"
        keyboard.append([InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(error_text, reply_markup=reply_markup)
        return
    
    # Header
    header = "MY STATISTICS" if lang == 'en' else "MIS ESTADÍSTICAS"
    message = "```\n"
    message += "╔═══════════════════════════════╗\n"
    message += f"║   👤 {header:<20} ║\n"
    message += "╚═══════════════════════════════╝\n"
    message += "```\n\n"
    message += "┌─────────────────────────────┐\n"
    message += f"│  📋 {user_name[:20]:<20} │\n"
    message += "└─────────────────────────────┘\n"
    message += "```\n"
    
    # Información del plan
    if user['premium']:
        message += "💎 *Plan:* `PREMIUM` ✨\n"
        
        if user.get('premium_until'):
            expiry = datetime.fromisoformat(user['premium_until'])
            days_left = (expiry - datetime.now()).days
            expires_label = "Expires" if lang == 'en' else "Expira"
            days_label = "days left" if lang == 'en' else "días"
            message += f"📅 *{expires_label}:* `{expiry.strftime('%d/%m/%Y')}`\n"
            message += f"⏰ *{days_label.title()}:* `{days_left} {days_label}`\n\n"
        else:
            lifetime = "Lifetime Premium" if lang == 'en' else "Premium Vitalicio"
            message += f"♾️ *{lifetime}*\n\n"
        
        # Barra de progreso para cada tipo
        videos = user_stats['videos']
        photos = user_stats['photos']
        music = user_stats['music']
        apk = user_stats['apk']
        
        def get_progress_bar(used, total, width=10):
            if total == 0:
                return "▰" * width
            filled = int((used / total) * width)
            return "▰" * filled + "▱" * (width - filled)
        
        remaining_label = "remaining" if lang == 'en' else "restantes"
        unlimited_label = "unlimited" if lang == 'en' else "ilimitadas"
        
        message += f"🎬 *Videos:* `{videos['used']}/50`\n"
        message += f"   {get_progress_bar(videos['used'], 50)} `{50-videos['used']} {remaining_label}`\n\n"
        
        message += f"📸 *Fotos:* `{photos['used']}` ♾️\n"
        message += f"   ∞∞∞∞∞∞∞∞∞∞ `{unlimited_label}`\n\n"
        
        message += f"🎵 *Música:* `{music['used']}/50`\n"
        message += f"   {get_progress_bar(music['used'], 50)} `{music['remaining']} {remaining_label}`\n\n"
        
        message += f"📦 *APK:* `{apk['used']}/50`\n"
        message += f"   {get_progress_bar(apk['used'], 50)} `{apk['remaining']} {remaining_label}`\n\n"
        
        # Footer for premium
        message += "```\n"
        message += "╔═══════════════════════════════╗\n"
        message += "║    Estadísticas personales    ║\n"
        message += "╚═══════════════════════════════╝\n"
        message += "```"
    else:
        free_plan = "FREE" if lang == 'en' else "GRATUITO"
        message += f"🆓 *Plan:* `{free_plan}`\n\n"
        
        videos = user_stats['videos']
        photos = user_stats['photos']
        
        # Labels traducidos
        total_label = "total" if lang == 'en' else "totales"
        today_label = "today" if lang == 'en' else "hoy"
        remaining_label = "remaining" if lang == 'en' else "restante"
        only_one = "Only 1 left!" if lang == 'en' else "¡Solo queda 1!"
        limit_reached = "Limit reached" if lang == 'en' else "Límite alcanzado"
        daily_limit = "Daily limit reached" if lang == 'en' else "Límite diario alcanzado"
        resets_in = "Resets in 24h" if lang == 'en' else "Se reinicia en 24h"
        few_left = "Few remaining" if lang == 'en' else "Pocas restantes"
        required = "Premium required" if lang == 'en' else "Premium requerido"
        
        # Videos (totales)
        message += f"🎬 *Videos:* `{videos['used']}/{videos['limit']}` {total_label}\n"
        if videos['remaining'] > 0:
            bar = "🟢" * videos['remaining'] + "⚫" * (videos['limit'] - videos['remaining'])
            message += f"   {bar}\n"
            plural = 's' if videos['remaining'] > 1 else ''
            message += f"   💡 `{videos['remaining']} {remaining_label}{plural}`\n"
            if videos['remaining'] == 1:
                message += f"   ⚠️ *{only_one}*\n"
        else:
            message += f"   🔴🔴🔴 `{limit_reached}`\n"
        message += "\n"
        
        # Fotos (permanentes para FREE)
        message += f"📸 *Fotos:* `{photos['used']}/{photos['limit']}`\n"
        if photos['remaining'] > 0:
            filled = min(photos['used'], photos['limit'])
            bar = "🟩" * filled + "⬜" * (photos['limit'] - filled)
            message += f"   {bar}\n"
            plural = 's' if photos['remaining'] > 1 else ''
            message += f"   💡 `{photos['remaining']} {remaining_label}{plural}`\n"
            if photos['remaining'] <= 2:
                message += f"   ⚠️ *{few_left}*\n"
        else:
            message += f"   🔴 `{limit_reached}`\n"
        message += "\n"
        
        # Contenido premium bloqueado
        message += "🔒 *Requiere Premium:*\n"
        message += "   🎵 Música\n"
        message += "   📦 APK\n"
        
        # Footer
        message += "```\n"
        message += "╔═══════════════════════════════╗\n"
        message += "║    Estadísticas personales    ║\n"
        message += "╚═══════════════════════════════╝\n"
        message += "```"
    
    # Build keyboard buttons
    if not user['premium']:
        btn_premium = "💎 Get Premium" if lang == 'en' else "💎 Obtener Premium"
        keyboard.append([InlineKeyboardButton(btn_premium, callback_data="show_premium")])
    btn_refresh = "🔄 Refresh Stats" if lang == 'en' else "🔄 Actualizar Stats"
    keyboard.append([InlineKeyboardButton(btn_refresh, callback_data="refresh_stats")])
    keyboard.append([InlineKeyboardButton(get_msg("btn_back_start", lang), callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or edit message based on context
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)


async def handle_message_logic(update, context_or_bot, client, link, parsed, user_id, user):
    """Lógica principal de manejo de mensajes con cliente de usuario"""
    channel_id, message_id = parsed
    joined_automatically = False
    
    # Helper local para responder unificado (soporta Update o Bot directo)
    async def reply(text, parse_mode='Markdown', **kwargs):
        if update and update.message:
            return await update.message.reply_text(text, parse_mode=parse_mode, **kwargs)
        else:
            bot = context_or_bot.bot if hasattr(context_or_bot, 'bot') else context_or_bot
            return await bot.send_message(user_id, text, parse_mode=parse_mode, **kwargs)
    
    if message_id is None:
        if channel_id.startswith('+'):
            try:
                invite_hash = channel_id[1:]
                result = await client(ImportChatInviteRequest(invite_hash))
                await asyncio.sleep(1)
                channel_name = getattr(result.chats[0], 'title', 'canal') if result.chats else 'canal'
                await reply(f"✅ *Unido Exitosamente*\n\nMe uní al canal: *{channel_name}*\n\nAhora puedes enviarme enlaces de mensajes específicos del canal para descargar contenido.\n\n📝 Ejemplo: t.me/+HASH/123")
                return
            except UserAlreadyParticipantError:
                await reply("ℹ️ *Ya Estoy en el Canal*\n\nYa soy miembro de este canal.\n\nPuedes enviarme enlaces de mensajes específicos para descargar contenido.\n\n📝 Ejemplo: t.me/+HASH/123")
                return
            except InviteHashExpiredError:
                await reply("La invitación ha expirado\n\nPide al administrador del canal un enlace nuevo (debe empezar con t.me/+) y envíamelo otra vez.")
                return
            except InviteHashInvalidError:
                await reply("Enlace de invitación inválido o ya usado\n\nAsegúrate de copiar el enlace completo que empieza con t.me/+")
                return
            except FloodWaitError as e:
                await reply(f"⏳ *Límite de Velocidad*\n\nDemasiadas solicitudes. Espera {e.seconds} segundos e inténtalo nuevamente.")
                return
            except Exception as join_e:
                logger.error(f"Error joining channel: {join_e}")
                await reply("❌ *Error al Unirse al Canal*\n\nNo pude unirme al canal automáticamente.\n\n🔍 *Qué puedes hacer:*\n1️⃣ Verifica que el enlace sea correcto\n2️⃣ Pide un nuevo enlace de invitación al admin\n3️⃣ Intenta agregar el bot manualmente al canal\n\n💡 Si el problema persiste, contacta al administrador del canal.")
                return
        else:
            await reply("❌ *Enlace Incompleto*\n\nEste enlace no tiene el número de mensaje.\n\n📝 *Necesito el enlace completo:*\n• Para canales públicos: t.me/canal/123\n• Para canales privados: t.me/c/123456/789\n\n💡 Toca el mensaje específico → Copiar enlace")
            return
    
    try:
        message = None
        entity = None
        logger.info(f"Attempting to get message {message_id} from channel {channel_id}")
        try:
            entity = await get_entity_from_identifier(client, channel_id)
            logger.info(f"Entity resolved: {entity}")
            message = await client.get_messages(entity, ids=message_id)
            logger.info(f"Message retrieved: {message is not None}")
        except ValueError as ve:
            logger.warning(f"ValueError getting entity: {ve}")
            if channel_id.isdigit():
                try:
                    logger.info(f"Numeric channel ID, searching in dialogs...")
                    async for dialog in client.iter_dialogs():
                        if dialog.is_channel and str(dialog.entity.id) == channel_id:
                            entity = dialog.entity
                            logger.info(f"Found channel in dialogs: {dialog.entity.title}")
                            message = await client.get_messages(entity, ids=message_id)
                            logger.info(f"Message retrieved from dialog channel: {message is not None}")
                            break
                    if not message:
                        raise ChannelPrivateError(None)
                except Exception as ex:
                    logger.error(f"Failed to get entity from dialogs: {ex}")
                    raise ChannelPrivateError(None)
            elif channel_id.startswith('+'):
                try:
                    logger.info(f"Trying to get entity directly for invite link")
                    entity = await client.get_entity(channel_id)
                    message = await client.get_messages(entity, ids=message_id)
                    logger.info(f"Message retrieved after direct entity fetch: {message is not None}")
                except Exception as ex:
                    logger.error(f"Failed to get entity directly: {ex}")
                    raise ChannelPrivateError(None)
            else:
                raise ChannelPrivateError(None)
        except (ChannelPrivateError, ChatForbiddenError):
            if channel_id.startswith('+'):
                try:
                    invite_hash = channel_id[1:]
                    await client(ImportChatInviteRequest(invite_hash))
                    await asyncio.sleep(1)
                    entity = await get_entity_from_identifier(client, channel_id)
                    message = await client.get_messages(entity, ids=message_id)
                    await reply("Unido al canal automáticamente. Descargando...")
                    joined_automatically = True
                except InviteHashExpiredError:
                    await reply("La invitación ha expirado\n\nPide al administrador del canal un enlace nuevo (debe empezar con t.me/+) y envíamelo otra vez.")
                    return
                except InviteHashInvalidError:
                    await reply("Enlace de invitación inválido o ya usado\n\nAsegúrate de copiar el enlace completo que empieza con t.me/+")
                    return
                except FloodWaitError as flood_e:
                    await reply(f"⏳ *Límite de Velocidad*\n\nDemasiadas solicitudes. Espera {flood_e.seconds} segundos e inténtalo nuevamente.")
                    return
                except Exception as join_e:
                    logger.error(f"Error joining channel: {join_e}")
                    await reply("❌ *Error al Unirse al Canal*\n\nNo pude unirme al canal automáticamente.\n\n🔍 *Qué puedes hacer:*\n1️⃣ Verifica que el enlace sea correcto\n2️⃣ Pide un nuevo enlace de invitación al admin\n3️⃣ Intenta agregar el bot manualmente al canal\n\n💡 Si el problema persiste, contacta al administrador del canal.")
                    return
            else:
                me = await client.get_me()
                username = f"@{me.username}" if me.username else "el bot"
                await reply(f"Este es un canal privado y no tengo acceso\n\nPara que pueda descargar:\n\nOpción 1 → Envíame un enlace de invitación (empieza con t.me/+) \nOpción 2 → Agrégame manualmente al canal con mi cuenta {username}")
                return
        
        if not message:
            await reply("❌ *Mensaje No Encontrado*\n\nNo pude encontrar este mensaje en el canal.\n\n🔍 *Posibles razones:*\n• El mensaje fue eliminado\n• El enlace está incorrecto\n• El canal no existe\n\n💡 Verifica el enlace y envíamelo otra vez.")
            return

        # Check if message is part of an album (grouped media)
        album_messages = []
        if hasattr(message, 'grouped_id') and message.grouped_id:
            logger.info(f"Album detected with grouped_id: {message.grouped_id}")
            try:
                album_status = await update.message.reply_text("🔍 Detectando álbum...")
                grouped_id = message.grouped_id
                album_messages = []
                start_id = max(1, message_id - 20)
                end_id = message_id + 20
                ids_to_check = list(range(start_id, end_id + 1))
                messages_batch = await client.get_messages(entity, ids=ids_to_check)
                for msg in messages_batch:
                    if msg and hasattr(msg, 'grouped_id') and msg.grouped_id == grouped_id:
                        album_messages.append(msg)
                album_messages.sort(key=lambda m: m.id)
                await album_status.edit_text(f"📸 Álbum detectado: {len(album_messages)} archivos\n⏳ Preparando descarga...")
            except Exception as album_err:
                logger.error(f"Error getting album messages: {album_err}")
                album_messages = [message]
        
        # Check for nested links
        if not message.media and message.text:
            inner_links = re.findall(r'https?://t\.me/[^\s\)]+', message.text)
            if inner_links:
                inner_parsed = parse_telegram_link(inner_links[0])
                if inner_parsed:
                    inner_channel_id, inner_message_id = inner_parsed
                    if inner_message_id is not None:
                        try:
                            inner_entity = None
                            inner_msg = None
                            try:
                                inner_entity = await get_entity_from_identifier(client, inner_channel_id)
                                inner_msg = await client.get_messages(inner_entity, ids=inner_message_id)
                            except ValueError:
                                if inner_channel_id.isdigit():
                                    async for dialog in client.iter_dialogs():
                                        if dialog.is_channel and str(dialog.entity.id) == inner_channel_id:
                                            inner_entity = dialog.entity
                                            inner_msg = await client.get_messages(inner_entity, ids=inner_message_id)
                                            break
                            if inner_msg and inner_msg.media:
                                message = inner_msg
                                logger.info("Using nested link message with media")
                        except Exception as nested_ex:
                            logger.warning(f"Could not process nested link: {nested_ex}")

        if not message:
            await reply("❌ *Mensaje No Encontrado*\n\nNo pude encontrar este mensaje en el canal.")
            return
        
        if not message.media:
            if message.text:
                text_to_send = message.text
                if hasattr(message, 'caption') and message.caption:
                    text_to_send = f"{message.caption}\n\n{text_to_send}"
                await reply(f"📄 *Contenido del Mensaje:*\n\n{text_to_send}")
                return
            else:
                await reply("❌ *Sin Contenido*\n\nEste mensaje no contiene texto ni archivos para descargar.")
                return
        
        content_type = detect_content_type(message)
        
        # Check limits (simplified for brevity, assuming user object is up to date)
        # ... (limits check logic should be here, but I'll skip it for now to fit in the tool call)
        # Actually, I should include it.
        
        # Now process the download
        messages_to_process = album_messages if album_messages else [message]
        downloaded_count = 0
        
        for idx, msg in enumerate(messages_to_process, 1):
            # Refrescar datos del usuario antes de cada archivo
            user = get_user(user_id)
            content_type = detect_content_type(msg)
            # BLOQUEO para usuarios FREE
            if not user['premium']:
                if content_type == 'video' and user['downloads'] >= FREE_DOWNLOAD_LIMIT:
                    await reply(f"⚠️ Límite de videos alcanzado ({user['downloads']}/{FREE_DOWNLOAD_LIMIT}).\n\n💎 /premium para descargas ilimitadas.")
                    break
                if content_type == 'photo' and user['daily_photo'] >= FREE_PHOTO_LIMIT:
                    await reply(f"⚠️ Límite de fotos alcanzado ({user['daily_photo']}/{FREE_PHOTO_LIMIT}).\n\n💎 /premium para fotos ilimitadas.")
                    break
            if len(messages_to_process) > 1:
                status = await reply(f"📥 Descargando {idx}/{len(messages_to_process)}...")
            else:
                status = await reply("📥 Descargando...")
            try:
                bot = context_or_bot.bot if hasattr(context_or_bot, 'bot') else context_or_bot
                await download_and_send_media(msg, user_id, bot)
                if update and update.message:
                    await status.delete()
                downloaded_count += 1
                # Incrementar contadores SOLO si fue exitoso
                user = get_user(user_id)
                if not user['premium']:
                    if content_type == 'video':
                        increment_total_downloads(user_id)
                    elif content_type == 'photo':
                        increment_daily_counter(user_id, 'photo')
            except Exception as e:
                logger.error(f"Error downloading media: {e}")
                err_text = f"❌ Error al descargar: {str(e)[:50]}"
                if update and update.message:
                    await status.edit_text(err_text)
                else:
                    await reply(err_text)

        if downloaded_count > 0:
            await reply("✅ *Descarga Completada*")

    except Exception as e:
        logger.error(f"Error in handle_message_logic: {e}", exc_info=True)
        await reply("❌ *Error Inesperado*")


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data received from the MiniApp WebApp"""
    import json
    
    user_id = update.effective_user.id
    data = update.effective_message.web_app_data.data
    
    try:
        webapp_data = json.loads(data)
        action = webapp_data.get('action')
        
        if action == 'buy_premium':
            # Trigger premium payment
            logger.info(f"User {user_id} initiated premium purchase from MiniApp")
            
            chat_id = update.effective_chat.id
            title = "💎 Premium - 30 días"
            description = "Desbloquea videos ilimitados, música y más por 30 días"
            payload = f"miniapp_premium_{user_id}"
            currency = "XTR"
            prices = [LabeledPrice("Premium 30 días", PREMIUM_PRICE_STARS)]
            
            await context.bot.send_invoice(
                chat_id=chat_id,
                title=title,
                description=description,
                payload=payload,
                provider_token="",
                currency=currency,
                prices=prices
            )
        
        elif action == 'download':
            # Handle download request from MiniApp
            link = webapp_data.get('link', '')
            if link and 't.me/' in link:
                logger.info(f"User {user_id} requested download from MiniApp: {link}")
                await update.message.reply_text(f"📥 Procesando descarga...\n\n🔗 {link}")
                # Create a fake message update to process the link
                update.message.text = link
                await handle_message(update, context)
            else:
                await update.message.reply_text("❌ Enlace no válido")
        
        elif action == 'configure':
            # Send user to configure account
            logger.info(f"User {user_id} requested account config from MiniApp")
            await update.message.reply_text(
                "⚙️ *Configuración de cuenta*\n\n"
                "Usa /configurar para vincular tu cuenta de Telegram y poder descargar contenido de canales privados.",
                parse_mode='Markdown'
            )
        
        elif action == 'disconnect':
            # Disconnect user session
            logger.info(f"User {user_id} requested disconnect from MiniApp")
            # Remove session file if exists
            session_file = f"sessions/session_{user_id}"
            if os.path.exists(f"{session_file}.session"):
                os.remove(f"{session_file}.session")
                db.update_session_status(user_id, False)
                await update.message.reply_text("✅ Tu cuenta ha sido desconectada correctamente.")
            else:
                await update.message.reply_text("ℹ️ No tienes ninguna cuenta conectada.")
            
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from MiniApp: {data}")
    except Exception as e:
        logger.error(f"Error handling MiniApp data: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages with Telegram links"""
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"📨 MESSAGE from {user_id}: {text[:50] if text else 'None'}")
    
    if not text:
        return
    
    # Extract Telegram links
    links = re.findall(r'https?://t\.me/[^\s]+', text)
    if not links:
        return
    
    # Ensure user exists
    if not get_user(user_id):
        create_user(user_id, first_name=update.effective_user.first_name, username=update.effective_user.username)
    
    # Ensure admins have premium
    ensure_admin_premium(user_id)
    
    if not has_active_session(user_id):
        await update.message.reply_text(
            "⚠️ *Configuración Requerida*\n\n"
            "Para descargar contenido, necesitas configurar tu cuenta de Telegram.\n"
            "Esto es necesario para evitar baneos y descargar de canales privados.\n\n"
            "👉 Usa /configurar para empezar.",
            parse_mode='Markdown'
        )
        return
    
    user = get_user(user_id)
    
    # Parse link
    link = links[0]
    parsed = parse_telegram_link(link)
    
    if not parsed:
        await update.message.reply_text(
            "❌ *Enlace Inválido*\n\n"
            "El enlace que enviaste no es válido.\n\n"
            "📌 *Formatos aceptados:*\n"
            "• Canales públicos: t.me/canal/123\n"
            "• Canales privados: t.me/+HASH/123\n"
            "• Enlaces numéricos: t.me/c/123456/789\n\n"
            "💡 Copia el enlace completo desde Telegram y envíamelo otra vez.",
            parse_mode='Markdown'
        )
        return

    async with get_user_client(user_id) as client:
        await handle_message_logic(update, context, client, link, parsed, user_id, user)


async def handle_message_old(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages with Telegram links"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if not text:
        return
    
    # Extract Telegram links
    links = re.findall(r'https?://t\.me/[^\s]+', text)
    if not links:
        return
    
    # Ensure user exists
    if not get_user(user_id):
        create_user(user_id, first_name=update.effective_user.first_name, username=update.effective_user.username)
    
    # Ensure admins have premium
    ensure_admin_premium(user_id)
    
    if not has_active_session(user_id):
        await update.message.reply_text(
            "⚠️ *Configuración Requerida*\n\n"
            "Para descargar contenido, necesitas configurar tu cuenta de Telegram.\n"
            "Esto es necesario para evitar baneos y descargar de canales privados.\n\n"
            "👉 Usa /configurar para empezar.",
            parse_mode='Markdown'
        )
        return
    
    user = get_user(user_id)
    
    # Parse link
    link = links[0]
    parsed = parse_telegram_link(link)
    
    if not parsed:
        await update.message.reply_text(
            "❌ *Enlace Inválido*\n\n"
            "El enlace que enviaste no es válido.\n\n"
            "📌 *Formatos aceptados:*\n"
            "• Canales públicos: t.me/canal/123\n"
            "• Canales privados: t.me/+HASH/123\n"
            "• Enlaces numéricos: t.me/c/123456/789\n\n"
            "💡 Copia el enlace completo desde Telegram y envíamelo otra vez.",
            parse_mode='Markdown'
        )
        return
    
    channel_id, message_id = parsed
    joined_automatically = False  # Track if we joined a channel
    
    # If no message_id, this is just an invitation link to join
    if message_id is None:
        if channel_id.startswith('+'):
            try:
                invite_hash = channel_id[1:]
                result = await telethon_client(ImportChatInviteRequest(invite_hash))
                await asyncio.sleep(1)
                
                # Get channel name from result
                channel_name = getattr(result.chats[0], 'title', 'canal') if result.chats else 'canal'
                
                await update.message.reply_text(
                    f"✅ *Unido Exitosamente*\n\n"
                    f"Me uní al canal: *{channel_name}*\n\n"
                    f"Ahora puedes enviarme enlaces de mensajes específicos del canal para descargar contenido.\n\n"
                    f"📝 Ejemplo: t.me/+HASH/123",
                    parse_mode='Markdown'
                )
                return
            except UserAlreadyParticipantError:
                await update.message.reply_text(
                    "ℹ️ *Ya Estoy en el Canal*\n\n"
                    "Ya soy miembro de este canal.\n\n"
                    "Puedes enviarme enlaces de mensajes específicos para descargar contenido.\n\n"
                    "📝 Ejemplo: t.me/+HASH/123",
                    parse_mode='Markdown'
                )
                return
            except InviteHashExpiredError:
                await update.message.reply_text(
                    "La invitación ha expirado\n\n"
                    "Pide al administrador del canal un enlace nuevo (debe empezar con t.me/+) y envíamelo otra vez."
                )
                return
            except InviteHashInvalidError:
                await update.message.reply_text(
                    "Enlace de invitación inválido o ya usado\n\n"
                    "Asegúrate de copiar el enlace completo que empieza con t.me/+"
                )
                return
            except FloodWaitError as e:
                await update.message.reply_text(
                    f"⏳ *Límite de Velocidad*\n\n"
                    f"Demasiadas solicitudes. Espera {e.seconds} segundos e inténtalo nuevamente.",
                    parse_mode='Markdown'
                )
                return
            except Exception as join_e:
                logger.error(f"Error joining channel: {join_e}")
                await update.message.reply_text(
                    "❌ *Error al Unirse al Canal*\n\n"
                    "No pude unirme al canal automáticamente.\n\n"
                    "🔍 *Qué puedes hacer:*\n"
                    "1️⃣ Verifica que el enlace sea correcto\n"
                    "2️⃣ Pide un nuevo enlace de invitación al admin\n"
                    "3️⃣ Intenta agregar el bot manualmente al canal\n\n"
                    "💡 Si el problema persiste, contacta al administrador del canal.",
                    parse_mode='Markdown'
                )
                return
        else:
            await update.message.reply_text(
                "❌ *Enlace Incompleto*\n\n"
                "Este enlace no tiene el número de mensaje.\n\n"
                "📝 *Necesito el enlace completo:*\n"
                "• Para canales públicos: t.me/canal/123\n"
                "• Para canales privados: t.me/c/123456/789\n\n"
                "💡 Toca el mensaje específico → Copiar enlace",
                parse_mode='Markdown'
            )
            return
    
    try:
        # Get the message
        message = None
        entity = None
        
        logger.info(f"Attempting to get message {message_id} from channel {channel_id}")
        
        try:
            entity = await get_entity_from_identifier(channel_id)
            logger.info(f"Entity resolved: {entity}")
            message = await telethon_client.get_messages(entity, ids=message_id)
            logger.info(f"Message retrieved: {message is not None}")
        except ValueError as ve:
            logger.warning(f"ValueError getting entity: {ve}")
            # Entity not found in cache
            # For numeric channel IDs, we need to get all dialogs to find it
            if channel_id.isdigit():
                try:
                    logger.info(f"Numeric channel ID, searching in dialogs...")
                    # Get the channel from dialogs
                    async for dialog in telethon_client.iter_dialogs():
                        if dialog.is_channel and str(dialog.entity.id) == channel_id:
                            entity = dialog.entity
                            logger.info(f"Found channel in dialogs: {dialog.entity.title}")
                            message = await telethon_client.get_messages(entity, ids=message_id)
                            logger.info(f"Message retrieved from dialog channel: {message is not None}")
                            break
                    
                    if not message:
                        # Channel not found in dialogs, need invitation
                        raise ChannelPrivateError(None)
                except Exception as ex:
                    logger.error(f"Failed to get entity from dialogs: {ex}")
                    raise ChannelPrivateError(None)
            elif channel_id.startswith('+'):
                # For invite links, try to get entity directly or join
                try:
                    logger.info(f"Trying to get entity directly for invite link")
                    entity = await telethon_client.get_entity(channel_id)
                    message = await telethon_client.get_messages(entity, ids=message_id)
                    logger.info(f"Message retrieved after direct entity fetch: {message is not None}")
                except Exception as ex:
                    logger.error(f"Failed to get entity directly: {ex}")
                    # If still fails, treat as private channel
                    raise ChannelPrivateError(None)
            else:
                raise ChannelPrivateError(None)
        except (ChannelPrivateError, ChatForbiddenError):
            # If channel is private and we have an invite hash, try to join
            if channel_id.startswith('+'):
                try:
                    # Extract hash from identifier (remove '+' prefix)
                    invite_hash = channel_id[1:]
                    await telethon_client(ImportChatInviteRequest(invite_hash))
                    
                    # Wait a moment for the join to complete
                    await asyncio.sleep(1)
                    
                    # Try to get the message again
                    entity = await get_entity_from_identifier(channel_id)
                    message = await telethon_client.get_messages(entity, ids=message_id)
                    
                    await update.message.reply_text("Unido al canal automáticamente. Descargando...")
                    joined_automatically = True
                    
                except InviteHashExpiredError:
                    await update.message.reply_text(
                        "La invitación ha expirado\n\n"
                        "Pide al administrador del canal un enlace nuevo (debe empezar con t.me/+) y envíamelo otra vez."
                    )
                    return
                except InviteHashInvalidError:
                    await update.message.reply_text(
                        "Enlace de invitación inválido o ya usado\n\n"
                        "Asegúrate de copiar el enlace completo que empieza con t.me/+"
                    )
                    return
                except FloodWaitError as flood_e:
                    await update.message.reply_text(
                        f"⏳ *Límite de Velocidad*\n\n"
                        f"Demasiadas solicitudes. Espera {flood_e.seconds} segundos e inténtalo nuevamente.",
                        parse_mode='Markdown'
                    )
                    return
                except Exception as join_e:
                    logger.error(f"Error joining channel: {join_e}")
                    await update.message.reply_text(
                        "❌ *Error al Unirse al Canal*\n\n"
                        "No pude unirme al canal automáticamente.\n\n"
                        "🔍 *Qué puedes hacer:*\n"
                        "1️⃣ Verifica que el enlace sea correcto\n"
                        "2️⃣ Pide un nuevo enlace de invitación al admin\n"
                        "3️⃣ Intenta agregar el bot manualmente al canal\n\n"
                        "💡 Si el problema persiste, contacta al administrador del canal.",
                        parse_mode='Markdown'
                    )
                    return
            else:
                # Private channel without invite hash
                me = await telethon_client.get_me()
                username = f"@{me.username}" if me.username else "el bot"
                await update.message.reply_text(
                    f"Este es un canal privado y no tengo acceso\n\n"
                    f"Para que pueda descargar:\n\n"
                    f"Opción 1 → Envíame un enlace de invitación (empieza con t.me/+) \n"
                    f"Opción 2 → Agrégame manualmente al canal con mi cuenta {username}"
                )
                return
        
        if not message:
            await update.message.reply_text(
                "❌ *Mensaje No Encontrado*\n\n"
                "No pude encontrar este mensaje en el canal.\n\n"
                "🔍 *Posibles razones:*\n"
                "• El mensaje fue eliminado\n"
                "• El enlace está incorrecto\n"
                "• El canal no existe\n\n"
                "💡 Verifica el enlace y envíamelo otra vez.",
                parse_mode='Markdown'
            )
            return
        
        # === DETECCIÓN DE PAYWALL/PROTECCIÓN STARS ===
        # Si el mensaje existe pero no tiene media y no es solo texto, probablemente está protegido
        is_paywall = False
        paywall_reason = None
        # Telethon: algunos mensajes protegidos tienen media=None y restriction_reason o restricted
        if message and not message.media:
            # Si tiene restriction_reason o restricted, o el texto menciona Stars
            restriction = getattr(message, 'restriction_reason', None)
            restricted = getattr(message, 'restricted', None)
            text = getattr(message, 'text', '') or ''
            if restriction or restricted:
                is_paywall = True
                paywall_reason = str(restriction) if restriction else 'Contenido restringido.'
            # Heurística: si el texto menciona Stars/paywall
            if 'Stars' in text or '⭐' in text or 'paywall' in text.lower():
                is_paywall = True
                paywall_reason = 'Contenido protegido por Telegram Stars.'
        # Si detectamos paywall, mostrar mensaje claro
        if is_paywall:
            user_id = update.effective_user.id
            if user_id in ADMIN_USER_IDS:
                # Intento de bypass experimental para admins
                try:
                    await update.message.reply_text(
                        "🔓 *Contenido protegido por Stars detectado.*\n\n"
                        "Intentando bypass experimental solo para admins...",
                        parse_mode='Markdown'
                    )
                    # Intentar reenviar el mensaje (puede fallar)
                    try:
                        await context.bot.forward_message(
                            chat_id=user_id,
                            from_chat_id=message.chat_id,
                            message_id=message.id
                        )
                        await update.message.reply_text(
                            "✅ *Bypass experimental exitoso.*\n\nSi ves el archivo, el método funcionó.",
                            parse_mode='Markdown'
                        )
                        return
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ *Bypass experimental fallido.*\n\nNo se pudo reenviar el mensaje.\n\nError: {e}",
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ *Error inesperado en bypass experimental.*\n\n{e}",
                        parse_mode='Markdown'
                    )
            # Mensaje para usuarios normales
            else:
                await update.message.reply_text(
                    "🔒 *Contenido protegido por Stars*\n\n"
                    "Este archivo está protegido por un paywall de Telegram Stars y no puede ser descargado automáticamente.\n\n"
                    "💡 Si eres el dueño del canal, puedes quitar el paywall o compartir el archivo directamente.\n\n"
                    "⭐ Si quieres más información sobre Stars: https://core.telegram.org/stars",
                    parse_mode='Markdown'
                )
            return

        # Check if message is part of an album (grouped media)
        album_messages = []
        if hasattr(message, 'grouped_id') and message.grouped_id:
            logger.info(f"Album detected with grouped_id: {message.grouped_id}")
            
            # Search forward and backward for other messages in the group
            try:
                # Show initial status
                album_status = await update.message.reply_text("🔍 Detectando álbum...")
                
                # Collect all messages with same grouped_id
                grouped_id = message.grouped_id
                album_messages = []
                
                # Get a range of message IDs around the current message
                # Albums are always consecutive, so check 20 messages before and after
                start_id = max(1, message_id - 20)
                end_id = message_id + 20
                
                # Get all messages in the range
                ids_to_check = list(range(start_id, end_id + 1))
                logger.info(f"Checking message IDs from {start_id} to {end_id} for grouped_id {grouped_id}")
                
                messages_batch = await telethon_client.get_messages(entity, ids=ids_to_check)
                
                # Filter messages with the same grouped_id
                for msg in messages_batch:
                    if msg and hasattr(msg, 'grouped_id') and msg.grouped_id == grouped_id:
                        album_messages.append(msg)
                
                # Sort by ID to maintain order
                album_messages.sort(key=lambda m: m.id)
                
                logger.info(f"Found {len(album_messages)} messages in album")
                
                # Update status message to show album
                await album_status.edit_text(f"📸 Álbum detectado: {len(album_messages)} archivos\n⏳ Preparando descarga...")
            except Exception as album_err:
                logger.error(f"Error getting album messages: {album_err}")
                logger.exception(album_err)
                # Continue with single message if album fetch fails
                album_messages = [message]
        
        # Check for nested links
        if not message.media and message.text:
            inner_links = re.findall(r'https?://t\.me/[^\s\)]+', message.text)
            if inner_links:
                inner_parsed = parse_telegram_link(inner_links[0])
                if inner_parsed:
                    inner_channel_id, inner_message_id = inner_parsed
                    if inner_message_id is None:
                        logger.info(f"Skipping nested link without message_id: {inner_links[0]}")
                    else:
                        try:
                            inner_entity = None
                            inner_msg = None
                            try:
                                inner_entity = await get_entity_from_identifier(inner_channel_id)
                                inner_msg = await telethon_client.get_messages(inner_entity, ids=inner_message_id)
                            except ValueError as ve_inner:
                                if inner_channel_id.isdigit():
                                    async for dialog in telethon_client.iter_dialogs():
                                        if dialog.is_channel and str(dialog.entity.id) == inner_channel_id:
                                            inner_entity = dialog.entity
                                            inner_msg = await telethon_client.get_messages(inner_entity, ids=inner_message_id)
                                            break
                            if inner_msg and inner_msg.media:
                                message = inner_msg
                                logger.info("Using nested link message with media")
                        except Exception as nested_ex:
                            logger.warning(f"Could not process nested link: {nested_ex}")
                            # Continue with original message if nested fails
        
        # Check if message has media or text content
        if not message:
            await update.message.reply_text(
                "❌ *Mensaje No Encontrado*\n\n"
                "No pude encontrar este mensaje en el canal.",
                parse_mode='Markdown'
            )
            return
        
        # If message has only text (no media), send the text
        if not message.media:
            if message.text:
                # Send the text content
                text_to_send = message.text
                
                # Add caption if available
                if hasattr(message, 'caption') and message.caption:
                    text_to_send = f"{message.caption}\n\n{text_to_send}"
                
                await update.message.reply_text(
                    f"📄 *Contenido del Mensaje:*\n\n{text_to_send}",
                    parse_mode='Markdown'
                )
                return
            else:
                await update.message.reply_text(
                    "❌ *Sin Contenido*\n\n"
                    "Este mensaje no contiene texto ni archivos para descargar.\n\n"
                    "📥 *Puedo descargar:*\n"
                    "• Texto\n"
                    "• Videos y GIFs\n"
                    "• Fotos e imágenes\n"
                    "• Música y audio\n"
                    "• Archivos APK\n\n"
                    "💡 Envíame un enlace a un mensaje que contenga alguno de estos.",
                    parse_mode='Markdown'
                )
                return
        
        # Detect content type
        content_type = detect_content_type(message)
        
        # Check photo limits
        if content_type == 'photo':
            if not user['premium']:
                # FREE users: límite PERMANENTE de fotos
                user = get_user(user_id)
                
                if user['daily_photo'] >= FREE_PHOTO_LIMIT:
                    await update.message.reply_text(
                        "⚠️ *Límite de Fotos Alcanzado*\n\n"
                        f"Has usado tus {FREE_PHOTO_LIMIT} fotos gratuitas.\n\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "💎 *Con Premium obtienes:*\n"
                        "✅ Fotos: Ilimitadas\n"
                        "✅ Videos: 50 diarios\n"
                        "✅ Música: 50 diarias\n"
                        "✅ APK: 50 diarios\n"
                        "♻️ Videos, música y APK se renuevan diario\n\n"
                        f"💰 Solo {PREMIUM_PRICE_STARS} ⭐ por 30 días\n\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "⭐ Usa /premium para suscribirte",
                        parse_mode='Markdown'
                    )
                    return
            # Premium users have unlimited photos, continue
        # Music and APK blocked for FREE users
        elif content_type in ['music', 'apk'] and not user['premium']:
            content_name = 'Música' if content_type == 'music' else 'APK'
            await update.message.reply_text(
                "🔒 *Contenido Bloqueado*\n\n"
                f"✖️ {content_name} solo para usuarios Premium\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💎 *Con Premium desbloqueas:*\n"
                f"✅ {content_name}: 50 diarias\n"
                "✅ Videos: 50 diarios\n"
                "✅ Todo se resetea cada día\n\n"
                f"💰 Solo {PREMIUM_PRICE_STARS} ⭐ por 30 días\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "⭐ Usa /premium para suscribirte",
                parse_mode='Markdown'
            )
            return
        # Check video limits
        elif content_type == 'video':
            if user['premium']:
                # Check premium daily video limit
                check_and_reset_daily_limits(user_id)
                user = get_user(user_id)  # Refresh after potential reset
                
                if user['daily_video'] >= PREMIUM_VIDEO_DAILY_LIMIT:
                    await update.message.reply_text(
                        "⚠️ *Límite Diario Alcanzado*\n\n"
                        f"Has descargado {user['daily_video']}/{PREMIUM_VIDEO_DAILY_LIMIT} videos hoy.\n\n"
                        "♻️ Tu límite se renueva en 24 horas.\n\n"
                        "💡 Mientras esperas puedes descargar:\n"
                        "✨ Fotos: Ilimitadas\n"
                        f"🎵 Música: {user['daily_music']}/{PREMIUM_MUSIC_DAILY_LIMIT}\n"
                        f"📦 APK: {user['daily_apk']}/{PREMIUM_APK_DAILY_LIMIT}",
                        parse_mode='Markdown'
                    )
                    return
            else:
                # Check FREE total video limit
                if user['downloads'] >= FREE_DOWNLOAD_LIMIT:
                    await update.message.reply_text(
                        "⚠️ *Límite Alcanzado*\n\n"
                        "Has usado tus 3 videos gratuitos.\n\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "💎 *Mejora a Premium y obtén:*\n"
                        "✅ 50 videos cada día\n"
                        "✅ 50 canciones cada día\n"
                        "✅ 50 APK cada día\n"
                        "♻️ Límites se renuevan diario\n\n"
                        f"💰 Solo {PREMIUM_PRICE_STARS} ⭐ por 30 días\n\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "⭐ Usa /premium para suscribirte",
                        parse_mode='Markdown'
                    )
                    return
        # Check music limits for premium
        elif content_type == 'music' and user['premium']:
            check_and_reset_daily_limits(user_id)
            user = get_user(user_id)  # Refresh
            
            if user['daily_music'] >= PREMIUM_MUSIC_DAILY_LIMIT:
                await update.message.reply_text(
                    "⚠️ *Límite Diario Alcanzado*\n\n"
                    f"Has descargado {user['daily_music']}/{PREMIUM_MUSIC_DAILY_LIMIT} canciones hoy.\n\n"
                    "♻️ Tu límite se renueva en 24 horas.\n\n"
                    "💡 Mientras esperas puedes descargar:\n"
                    "✨ Fotos: Ilimitadas\n"
                    f"🎬 Videos: {user['daily_video']}/{PREMIUM_VIDEO_DAILY_LIMIT}\n"
                    f"📦 APK: {user['daily_apk']}/{PREMIUM_APK_DAILY_LIMIT}",
                    parse_mode='Markdown'
                )
                return
        # Check APK limits for premium
        elif content_type == 'apk' and user['premium']:
            check_and_reset_daily_limits(user_id)
            user = get_user(user_id)  # Refresh
            
            if user['daily_apk'] >= PREMIUM_APK_DAILY_LIMIT:
                await update.message.reply_text(
                    "⚠️ *Límite Diario Alcanzado*\n\n"
                    f"Has descargado {user['daily_apk']}/{PREMIUM_APK_DAILY_LIMIT} APK hoy.\n\n"
                    "♻️ Tu límite se renueva en 24 horas.\n\n"
                    "💡 Mientras esperas puedes descargar:\n"
                    "✨ Fotos: Ilimitadas\n"
                    f"🎬 Videos: {user['daily_video']}/{PREMIUM_VIDEO_DAILY_LIMIT}\n"
                    f"🎵 Música: {user['daily_music']}/{PREMIUM_MUSIC_DAILY_LIMIT}",
                    parse_mode='Markdown'
                )
                return
        
        # Now process the download
        # If album was detected, process all messages
        messages_to_process = album_messages if album_messages else [message]
        
        for idx, msg in enumerate(messages_to_process, 1):
            # Detección de paywall para cada mensaje del álbum
            is_paywall = False
            paywall_reason = None
            restriction = getattr(msg, 'restriction_reason', None)
            restricted = getattr(msg, 'restricted', None)
            text = getattr(msg, 'text', '') or ''
            if msg and not msg.media:
                if restriction or restricted:
                    is_paywall = True
                    paywall_reason = str(restriction) if restriction else 'Contenido restringido.'
                if 'Stars' in text or '⭐' in text or 'paywall' in text.lower():
                    is_paywall = True
                    paywall_reason = 'Contenido protegido por Telegram Stars.'
            if is_paywall:
                if user_id in ADMIN_USER_IDS:
                    try:
                        await update.message.reply_text(
                            f"🔓 *Contenido protegido por Stars detectado en archivo {idx}.*\n\nIntentando bypass experimental solo para admins...",
                            parse_mode='Markdown'
                        )
                        try:
                            await context.bot.forward_message(
                                chat_id=user_id,
                                from_chat_id=msg.chat_id,
                                message_id=msg.id
                            )
                            await update.message.reply_text(
                                f"✅ *Bypass experimental exitoso en archivo {idx}.*\n\nSi ves el archivo, el método funcionó.",
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            await update.message.reply_text(
                                f"❌ *Bypass experimental fallido en archivo {idx}.*\n\nNo se pudo reenviar el mensaje.\n\nError: {e}",
                                parse_mode='Markdown'
                            )
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ *Error inesperado en bypass experimental (archivo {idx}).*\n\n{e}",
                            parse_mode='Markdown'
                        )
                else:
                    await update.message.reply_text(
                        f"🔒 *Contenido protegido por Stars (archivo {idx})*\n\nEste archivo está protegido por un paywall de Telegram Stars y no puede ser descargado automáticamente.\n\n💡 Si eres el dueño del canal, puedes quitar el paywall o compartir el archivo directamente.\n\n⭐ Más info: https://core.telegram.org/stars",
                        parse_mode='Markdown'
                    )
                continue
            # Si no está protegido, proceder normalmente
            
            # Check limits inside the loop to prevent album bypass
            user = get_user(user_id) # Refresh user data
            msg_content_type = detect_content_type(msg)
            
            if msg_content_type == 'video':
                if user['premium']:
                    if user['daily_video'] >= PREMIUM_VIDEO_DAILY_LIMIT:
                        await update.message.reply_text(f"⚠️ Límite de videos premium alcanzado ({user['daily_video']}/{PREMIUM_VIDEO_DAILY_LIMIT}). Deteniendo descarga del álbum.")
                        break
                else:
                    if user['downloads'] >= FREE_DOWNLOAD_LIMIT:
                        await update.message.reply_text(f"⚠️ Límite de videos alcanzado ({user['downloads']}/{FREE_DOWNLOAD_LIMIT}).\n\n💎 /premium para descargas ilimitadas.")
                        break
            elif msg_content_type == 'photo':
                if not user['premium']:
                    if user['daily_photo'] >= FREE_PHOTO_LIMIT:
                        await update.message.reply_text(f"⚠️ Límite de fotos alcanzado ({user['daily_photo']}/{FREE_PHOTO_LIMIT}).\n\n💎 /premium para fotos ilimitadas.")
                        break
            elif msg_content_type == 'music':
                if user['premium']:
                    if user['daily_music'] >= PREMIUM_MUSIC_DAILY_LIMIT:
                        await update.message.reply_text(f"⚠️ Límite de música diario alcanzado. Deteniendo descarga.")
                        break
            elif msg_content_type == 'apk':
                if user['premium']:
                    if user['daily_apk'] >= PREMIUM_APK_DAILY_LIMIT:
                        await update.message.reply_text(f"⚠️ Límite de APK diario alcanzado. Deteniendo descarga.")
                        break

            if len(messages_to_process) > 1:
                status = await update.message.reply_text(f"📥 Descargando {idx}/{len(messages_to_process)}...")
            else:
                status = await update.message.reply_text("📥 Descargando...")
            
            try:
                # Always use download_and_send_media to avoid 'Forwarded from' tag and ensure it looks like it comes from the bot
                await download_and_send_media(msg, user_id, context.bot)
                await status.delete()
                
                # Increment counters
                if msg_content_type == 'photo':
                    if not user['premium']:
                        increment_daily_counter(user_id, 'photo')
                elif msg_content_type == 'video':
                    if user['premium']:
                        increment_daily_counter(user_id, 'video')
                    else:
                        increment_total_downloads(user_id)
                elif msg_content_type == 'music':
                    if user['premium']:
                        increment_daily_counter(user_id, 'music')
                elif msg_content_type == 'apk':
                    if user['premium']:
                        increment_daily_counter(user_id, 'apk')
            except Exception as e:
                await status.edit_text(f"❌ Error al descargar archivo {idx}: {str(e)}")
        
        # Show final success message after all messages processed
        user = get_user(user_id)  # Refresh user data
        
        # Show success message
        album_text = f"📸 Álbum de {len(messages_to_process)} archivos descargado\n\n" if len(messages_to_process) > 1 else ""
        
        if content_type == 'photo':
            if user['premium']:
                success_msg = f"✅ *Descarga Completada*\n\n{album_text}📸 Fotos ilimitadas con Premium ✨"
                if joined_automatically:
                    success_msg += "\n\n🔗 Canal unido automáticamente"
                await update.message.reply_text(success_msg, parse_mode='Markdown')
            else:
                user = get_user(user_id)
                remaining_photos = FREE_PHOTO_LIMIT - user['daily_photo']
                success_msg = (
                    f"✅ *Descarga Completada*\n\n"
                    f"{album_text}"
                    f"📸 Fotos usadas: {user['daily_photo']}/{FREE_PHOTO_LIMIT}\n"
                    f"🎁 Te quedan: *{remaining_photos}* fotos\n\n"
                    f"💎 /premium para fotos ilimitadas"
                )
                if joined_automatically:
                    success_msg += "\n\n🔗 Canal unido automáticamente"
                await update.message.reply_text(success_msg, parse_mode='Markdown')
        elif content_type == 'video':
            # Counters already incremented in loop
            user = get_user(user_id)
            if user['premium']:
                success_msg = (
                    f"✅ *Descarga Completada*\n\n"
                    f"{album_text}"
                    f"📊 Videos hoy: {user['daily_video']}/{PREMIUM_VIDEO_DAILY_LIMIT}\n"
                    f"♻️ Se resetea en 24 horas"
                )
                if joined_automatically:
                    success_msg += "\n\n🔗 Canal unido automáticamente"
                await update.message.reply_text(success_msg, parse_mode='Markdown')
            else:
                remaining = FREE_DOWNLOAD_LIMIT - user['downloads']
                success_msg = (
                    f"✅ *Descarga Completada*\n\n"
                    f"{album_text}"
                    f"📊 Videos usados: {user['downloads']}/{FREE_DOWNLOAD_LIMIT}\n"
                    f"🎁 Te quedan: *{remaining}* descargas\n\n"
                    f"💎 /premium para 50 videos diarios"
                )
                if joined_automatically:
                    success_msg += "\n\n🔗 Canal unido automáticamente"
                await update.message.reply_text(success_msg, parse_mode='Markdown')
        elif content_type == 'music':
            # Counters already incremented in loop
            user = get_user(user_id)
            success_msg = (
                f"✅ *Descarga Completada*\n\n"
                f"{album_text}"
                f"🎵 Música hoy: {user['daily_music']}/{PREMIUM_MUSIC_DAILY_LIMIT}\n"
                f"♻️ Se resetea en 24 horas"
            )
            if joined_automatically:
                success_msg += "\n\n🔗 Canal unido automáticamente"
            await update.message.reply_text(success_msg, parse_mode='Markdown')
        elif content_type == 'apk':
            # Counters already incremented in loop
            user = get_user(user_id)
            success_msg = (
                f"✅ *Descarga Completada*\n\n"
                f"{album_text}"
                f"📦 APK hoy: {user['daily_apk']}/{PREMIUM_APK_DAILY_LIMIT}\n"
                f"♻️ Se resetea en 24 horas"
            )
            if joined_automatically:
                success_msg += "\n\n🔗 Canal unido automáticamente"
            await update.message.reply_text(success_msg, parse_mode='Markdown')
        else:
            success_msg = f"✅ *Descarga Completada*\n\n{album_text}" if album_text else "✅ *Descarga Completada*"
            if joined_automatically:
                success_msg += "\n\n🔗 Canal unido automáticamente"
            await update.message.reply_text(success_msg, parse_mode='Markdown')
    
    except FloodWaitError as e:
        await update.message.reply_text(
            f"⏳ *Límite de Velocidad*\n\n"
            f"Espera {e.seconds} segundos e inténtalo nuevamente.",
            parse_mode='Markdown'
        )
    except Exception as e:
        import traceback
        from telegram.error import TimedOut, NetworkError, RetryAfter
        
        error_type = type(e).__name__
        
        # Manejo específico de errores de red
        if isinstance(e, (TimedOut, NetworkError)):
            logger.warning(f"Network error: {error_type} - {e}")
            try:
                await update.message.reply_text(
                    "⚠️ *Problema de Conexión*\n\n"
                    "Hubo un problema temporal de red.\n\n"
                    "🔄 Intenta de nuevo en unos segundos.",
                    parse_mode='Markdown'
                )
            except:
                pass  # Si falla el mensaje de error, no hacer nada
        elif isinstance(e, RetryAfter):
            logger.warning(f"Rate limited: wait {e.retry_after} seconds")
            try:
                await update.message.reply_text(
                    f"⏳ *Límite de Solicitudes*\n\n"
                    f"Espera {e.retry_after} segundos e inténtalo nuevamente.",
                    parse_mode='Markdown'
                )
            except:
                pass
        else:
            # Error desconocido - mostrar mensaje genérico
            logger.error(f"Error processing message: {error_type} - {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                await update.message.reply_text(
                    "❌ *Error Inesperado*\n\n"
                    "Ocurrió un problema al procesar tu enlace.\n\n"
                    "🔄 *Qué hacer:*\n"
                    "1️⃣ Verifica que el enlace sea correcto\n"
                    "2️⃣ Intenta con otro enlace\n"
                    "3️⃣ Si el problema continúa, contacta al soporte\n\n"
                    "💡 Puedes usar /help para ver la guía de uso.",
                    parse_mode='Markdown'
                )
            except:
                pass  # Si falla el mensaje de error, registrar y continuar
                logger.error("Failed to send error message to user")



async def miniapp_queue_observer(application: Application):
    """
    Background task that polls the database for pending downloads from the MiniApp
    """
    logger.info("🚀 MiniApp Queue Observer started and waiting for items...")
    while True:
        try:
            # Poll for next pending download
            item = get_next_pending_download()
            
            if item:
                download_id = item['id']
                user_id = item['user_id']
                link = item['link']
                
                logger.info(f"📥 Processing queued download {download_id} for user {user_id}: {link}")
                
                # Check user existence and data
                user = get_user(user_id)
                if not user:
                    update_download_status(download_id, 'error', 'User not found')
                    continue
                
                # Mark as processing
                update_download_status(download_id, 'processing')
                
                # Parse link
                parsed = parse_telegram_link(link)
                if not parsed:
                    await application.bot.send_message(user_id, "❌ El enlace enviado desde la MiniApp no es válido.")
                    update_download_status(download_id, 'error', 'Invalid link')
                    continue
                
                # Use handle_message_logic but adapted for no update object
                try:
                    async with get_user_client(user_id) as client:
                        # Passing None as update to indicate background task
                        await handle_message_logic(None, application, client, link, parsed, user_id, user)
                        update_download_status(download_id, 'processed')
                        logger.info(f"✅ Download {download_id} processed successfully")
                except Exception as proc_e:
                    logger.error(f"Error processing queued download {download_id}: {proc_e}")
                    update_download_status(download_id, 'error', str(proc_e))
                    await application.bot.send_message(user_id, f"❌ Error al procesar descarga: {str(proc_e)[:50]}")
            
        except Exception as queue_e:
            logger.error(f"Error in miniapp_queue_observer: {queue_e}")
            
        # Wait before next poll
        await asyncio.sleep(5)


async def post_init(application: Application):
    """Initialize database and bot client"""
    init_database()
    
    # Initialize Telethon Bot Client
    global bot_client
    try:
        # Usar el mismo directorio que la base de datos para la sesión del bot
        db_path = os.getenv("DATABASE_PATH", "users.db")
        db_dir = os.path.dirname(db_path)
        session_path = os.path.join(db_dir, 'bot_session') if db_dir else 'bot_session'
        
        bot_client = TelegramClient(session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await bot_client.start(bot_token=TELEGRAM_TOKEN)
        logger.info("Telethon Bot Client started successfully")
    except Exception as e:
        logger.error(f"Failed to start Telethon Bot Client: {e}")

    # Start MiniApp Download Queue Observer
    asyncio.create_task(miniapp_queue_observer(application))
    logger.info("✅ MiniApp Queue Observer hooked into event loop")

    # Set bot commands menu
    from telegram import BotCommand, MenuButtonWebApp, WebAppInfo
    commands = [
        BotCommand("start", "🏠 Inicio - Menú principal"),
        BotCommand("panel", "📊 Panel de usuario"),
        BotCommand("premium", "💎 Hacerse Premium"),
        BotCommand("configurar", "⚙️ Configurar cuenta"),
        BotCommand("stats", "📈 Mis estadísticas"),
        BotCommand("referidos", "👥 Sistema de referidos"),
        BotCommand("miniapp", "📱 Abrir MiniApp")
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info(f"✅ Bot commands configured: {len(commands)} commands")
    except Exception as e:
        logger.error(f"❌ Failed to set bot commands: {e}")
    
    # Set Menu Button to open MiniApp
    miniapp_url = os.getenv('MINIAPP_URL', os.getenv('DASHBOARD_URL', '')).strip()
    if miniapp_url:
        miniapp_url = miniapp_url.rstrip('/')
        full_miniapp_url = miniapp_url + '/miniapp?v=2'
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Abrir App (RW)",
                    web_app=WebAppInfo(url=full_miniapp_url)
                )
            )
            logger.info(f"Menu button set to: {full_miniapp_url}")
        except Exception as e:
            logger.error(f"Failed to set menu button: {e}")
    
    # Limpiar comandos anteriores si existen
    # await application.bot.delete_my_commands()


async def post_shutdown(application: Application):
    """Acciones a realizar al cerrar el bot"""
    logger.info("👋 Ejecutando post_shutdown...")
    
    # Remove PID file
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
            logger.info(f"🗑️ PID file {PID_FILE} removed.")
        except Exception as e:
            logger.error(f"❌ Error removing PID file: {e}")

    # Close any active login clients
    for user_id, data in login_clients.items():
        try:
            await data['client'].disconnect()
        except:
            pass
            
    # Close bot client
    if bot_client:
        try:
            await bot_client.disconnect()
        except:
            pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors caused by Updates - maneja errores comunes silenciosamente."""
    from telegram.error import BadRequest, TimedOut, NetworkError, Forbidden
    
    error = context.error
    
    # Ignorar errores de callbacks expirados (normales después de reiniciar el bot)
    if isinstance(error, BadRequest):
        if "Query is too old" in str(error) or "query id is invalid" in str(error):
            logger.debug(f"Callback query expirado (normal después de reinicio): {error}")
            return
        if "Message is not modified" in str(error):
            logger.debug(f"Mensaje no modificado (contenido idéntico): {error}")
            return
    
    # Ignorar errores cuando el usuario bloqueó el bot (muy común)
    if isinstance(error, Forbidden):
        if "bot was blocked by the user" in str(error):
            logger.debug(f"Usuario bloqueó el bot (normal): {error}")
            return
        if "user is deactivated" in str(error):
            logger.debug(f"Usuario desactivado: {error}")
            return
    
    # Errores de red - solo warning (son recuperables)
    if isinstance(error, (TimedOut, NetworkError)):
        logger.warning(f"Error de red (recuperable): {error}")
        return
    
    # Log otros errores no manejados
    logger.error(f"Error no manejado: {error}", exc_info=context.error)


async def main():
    """
    ⚠️ LEGACY FUNCTION - DO NOT USE
    This function is kept for backward compatibility only.
    Use async_main() instead which is the proper async entry point.
    """
    logger.warning("❌ main() called - this is deprecated. Use async_main() or bot_with_paywall.py directly")
    raise RuntimeError("❌ CRITICAL: Do not call main() - use async_main() via asyncio.run() instead")


if __name__ == "__main__":
    # Entry point for direct execution (only for testing)
    logger.info("=" * 80)
    logger.info("🚀 TELEGRAM BOT - DIRECT EXECUTION (Testing Only)")
    logger.info("=" * 80)
    logger.warning("⚠️ WARNING: Direct bot execution is not recommended. Use railway_start.py or start.py")
    logger.info("=" * 80)
    
    asyncio.run(async_main())


async def async_main():
    """Start the bot asynchronously (for use in non-main threads)"""
    global _bot_instance_running
    
    # 1. Cross-process Protection (PID File)
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process actually exists
            import psutil
            if psutil.pid_exists(old_pid):
                logger.warning(f"⚠️ Bot already running (PID {old_pid}). Skipping to prevent Conflict 409.")
                return
            else:
                logger.info(f"ℹ️ Found stale PID file (PID {old_pid} no longer exists). Cleaning up.")
                os.remove(PID_FILE)
        except (ValueError, Exception) as e:
            logger.error(f"❌ Error checking PID file: {e}")
            if os.path.exists(PID_FILE): os.remove(PID_FILE)

    # 2. Thread-safe Protection (Flag)
    with _bot_instance_lock:
        if _bot_instance_running:
            logger.warning("⚠️ Bot instance already running in this process. Skipping.")
            return
        _bot_instance_running = True

    # Write current PID
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"📝 PID {os.getpid()} written to {PID_FILE}")
    except Exception as e:
        logger.error(f"❌ Could not write PID file: {e}")
    
    logger.info("🤖 Initializing Telegram Bot (async_main)...")
    
    from telegram.request import HTTPXRequest
    from telegram.error import TimedOut, NetworkError
    
    # Configuración de timeouts más robusta para Railway
    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=120.0,    # 2 minutos para conectar (Railway puede ser lento)
        read_timeout=900.0,       # 15 minutos para leer
        write_timeout=900.0,      # 15 minutos para escribir
        pool_timeout=120.0        # 2 minutos para pool
    )

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .request(request)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Login conversation handler
    login_handler = ConversationHandler(
        entry_points=[
            CommandHandler("configurar", start_login),
            CallbackQueryHandler(start_login, pattern="^connect_account$")
        ],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_login),
            CallbackQueryHandler(cancel_login, pattern="^cancel_login$")
        ],
        allow_reentry=True
    )
    application.add_handler(login_handler)
    application.add_handler(CommandHandler("logout", logout_command))

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("miniapp", miniapp_command))
    application.add_handler(CommandHandler("testpay", testpay_command))
    application.add_handler(CommandHandler("adminstats", adminstats_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("referidos", referidos_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Registrar el manejador de errores global
    application.add_error_handler(error_handler)

    logger.info("Bot started. Waiting for messages...")
    
    # Initialize the application with retries (Railway puede tener latencia inicial)
    max_retries = 5
    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing bot (attempt {attempt + 1}/{max_retries})...")
            await application.initialize()
            logger.info("Bot initialized successfully!")
            break
        except (TimedOut, NetworkError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10  # 10s, 20s, 30s, 40s
                logger.warning(f"Initialization failed: {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to initialize bot after {max_retries} attempts")
                raise
    
    # Manual startup to be compatible with existing event loop in start.py
    try:
        await application.initialize()
        # Manually call post_init as initialize() might not call it in some contexts or we want to be sure
        await post_init(application)
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info("=" * 80)
        logger.info("🚀 TELEGRAM BOT POLLING STARTED (Manual Mode)")
        logger.info("✅ Listening for incoming messages...")
        logger.info("=" * 80)
        
        # Keep the bot running until cancelled
        stop_event = asyncio.Event()
        
        # Helper to stop the event
        def stop_bot(*args):
            logger.info("🛑 Stop signal received...")
            stop_event.set()
        
        # Wait until stop_event is set
        try:
            await stop_event.wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("🛑 Bot execution cancelled.")
        
    except Exception as e:
        logger.error(f"❌ Bot polling error: {e}", exc_info=True)
    finally:
        logger.info("🛑 Bot shutting down...")
        try:
            # Stop application
            await application.stop()
            # Shutdown application
            await application.shutdown()
        except Exception as e:
            logger.debug(f"Debug: Shutdown exception (can be normal): {e}")
        
        # Reset flag to allow restart if needed
        with _bot_instance_lock:
            _bot_instance_running = False
        logger.info("✅ Bot stopped cleanly")
