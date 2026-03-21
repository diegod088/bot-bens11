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
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, WebAppInfo
from contextlib import asynccontextmanager
import uuid
import time

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
    SessionPasswordNeededError, AuthKeyUnregisteredError, UserDeactivatedError
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
    get_next_pending_download, update_download_status,
    try_acquire_bot_leadership
)

# Unique ID for this instance
INSTANCE_ID = str(uuid.uuid4())[:8]
PID_FILE = "bot.pid"
_bot_instance_lock = threading.Lock()
_bot_instance_running = False

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
FREE_DOWNLOAD_LIMIT = 0  # Free users: 0 videos
FREE_PHOTO_LIMIT = 0  # Free users: 0 fotos

# Premium Plans (Telegram Stars) - Estrategia de Precios Optimizada
PREMIUM_PLANS = {
    'flash': {
        'stars': 75,
        'days': 3,
        'name': '⚡ Venta Flash',
        'label': 'Premium 3 días',
        'badge': '💥 50% DESCUENTO',
        'description': 'Solo por hoy'
    },
    'basic': {
        'stars': 333,
        'days': 7,
        'name': '🚀 Básico',
        'label': 'Premium 7 días',
        'badge': '✨ ESTRATEGIA',
        'description': 'Ideal para empezar'
    },
    'pro': {
        'stars': 777,
        'days': 30,
        'name': '🔥 Pro',
        'label': 'Premium 30 días',
        'badge': '⭐ RECOMENDADO',
        'description': 'El más popular'
    },
    'elite': {
        'stars': 1499,
        'days': 90,
        'name': '💎 Elite',
        'label': 'Premium 90 días',
        'badge': '👑 MÁXIMO VALOR',
        'description': 'Máximo ahorro'
    }
}

# Backward compatibility (default to pro plan)
PREMIUM_PRICE_STARS = PREMIUM_PLANS['pro']['stars']

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
    """Obtiene un cliente de Telethon para el usuario y verifica su sesión"""
    session_string = get_user_session(user_id)
    if not session_string:
        raise ValueError("No session found for user")
    
    client = TelegramClient(StringSession(session_string), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    await client.connect()
    
    try:
        # Verificación activa de la sesión
        await client.get_me()
        yield client
    except (AuthKeyUnregisteredError, UserDeactivatedError, SessionPasswordNeededError):
        logger.error(f"❌ Sesión inválida detectada para usuario {user_id}. Limpiando...")
        delete_user_session(user_id)
        # Intentar borrar el archivo físico .session si existe (opcional pero recomendado)
        try:
            session_file = f"sessions/session_{user_id}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
        except: pass
        raise ValueError("Invalid session")
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
    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
    
    if not message or not message.media:
        return 'other'
        
    # Handle direct photos
    if isinstance(message.media, MessageMediaPhoto) or hasattr(message, 'photo') and message.photo:
        return 'photo'
    
    # Identify the document object if it exists
    doc = None
    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
    elif isinstance(message.media, MessageMediaWebPage) and message.media.webpage:
        wp = message.media.webpage
        if hasattr(wp, 'photo') and wp.photo:
            return 'photo'
        if hasattr(wp, 'document') and wp.document:
            doc = wp.document
    elif hasattr(message, 'document') and message.document:
        doc = message.document

    if doc:
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
        
        # Music detection (including voice notes)
        if mime_type.startswith('audio/') or file_name.endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')) or hasattr(message, 'voice') and message.voice:
            return 'music'
        
        # Video detection
        if mime_type.startswith('video/') or file_name.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')) or hasattr(message, 'video') and message.video:
            return 'video'
            
        # Photo detection in documents
        if mime_type.startswith('image/') or file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
            return 'photo'
    
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
        user_id = query.from_user.id
        lang = query.data.split("_")[1]
        set_user_language(user_id, lang)
        first_name = update.effective_user.first_name
        logger.info(f"User {user_id} selected language: {lang}")

        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')

        if lang == 'es':
            welcome_message = f"👋 ¡Hola de nuevo, {first_name}!\n\n👇 *Abre la app para continuar:*"
        else:
            welcome_message = f"👋 Welcome back, {first_name}!\n\n👇 *Open the app to continue:*"

        keyboard = []
        if base_url:
            miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}"
            keyboard.append([
                InlineKeyboardButton(
                    "📱 Abrir App" if lang == 'es' else "📱 Open App",
                    web_app=WebAppInfo(url=miniapp_url)
                )
            ])

        has_session = has_active_session(user_id)
        if not has_session:
            keyboard.append([
                InlineKeyboardButton(
                    "⚙️ Configurar cuenta" if lang == 'es' else "⚙️ Configure account",
                    callback_data="connect_account"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "💬 Soporte" if lang == 'es' else "💬 Support",
                url="https://t.me/observer_bots/11"
            )
        ])

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
        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        if base_url:
            miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}#premium"
            keyboard = [[InlineKeyboardButton("⭐ Ver Planes" if lang == 'es' else "⭐ View Plans", web_app=WebAppInfo(url=miniapp_url))]]
            await query.edit_message_text(
                "💎 Elige tu plan en la app:" if lang == 'es' else "💎 Choose your plan in the app:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
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
        await query.answer()
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name
        user = get_user(user_id)
        lang = get_user_language(user)
        check_and_reset_daily_limits(user_id)

        if lang == 'es':
            welcome_message = f"👋 ¡Hola {first_name}!\n\n👇 *Abre la app para continuar:*"
        else:
            welcome_message = f"👋 Hello {first_name}!\n\n👇 *Open the app to continue:*"

        keyboard = []
        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        if base_url:
            miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}"
            keyboard.append([
                InlineKeyboardButton(
                    "📱 Abrir App" if lang == 'es' else "📱 Open App",
                    web_app=WebAppInfo(url=miniapp_url)
                )
            ])

        has_session = has_active_session(user_id)
        if not has_session:
            keyboard.append([
                InlineKeyboardButton(
                    "⚙️ Configurar cuenta" if lang == 'es' else "⚙️ Configure account",
                    callback_data="connect_account"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "💬 Soporte" if lang == 'es' else "💬 Support",
                url="https://t.me/observer_bots/11"
            )
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    # Manejar callback de ver/refrescar estadísticas PERSONALES
    if query.data in ["view_stats", "refresh_stats"]:
        await query.answer()
        user_id = update.effective_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        if base_url:
            miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}"
            keyboard = [[InlineKeyboardButton("📱 Ver Stats" if lang == 'es' else "📱 View Stats", web_app=WebAppInfo(url=miniapp_url))]]
            await query.edit_message_text(
                "📊 Tus stats completos están en la app:" if lang == 'es' else "📊 Your full stats are in the app:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
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
        user_id = update.effective_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        if base_url:
            miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}#premium"
            keyboard = [[InlineKeyboardButton("⭐ Ver Planes" if lang == 'es' else "⭐ View Plans", web_app=WebAppInfo(url=miniapp_url))]]
            await query.edit_message_text(
                "💎 Elige tu plan en la app:" if lang == 'es' else "💎 Choose your plan in the app:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    await query.answer("📄 Procesando...", show_alert=False)
    
    # Handle premium payment callbacks for all plans
    if query.data.startswith("pay_premium"):
        user_id = update.effective_user.id
        user = get_user(user_id)
        lang = get_user_language(user)
        
        # Determine which plan was selected
        plan_key = data.get('plan_key', 'pro')  # Default to pro plan
        if query.data == "pay_premium_basic":
            plan_key = 'basic'
        elif query.data == "pay_premium_pro":
            plan_key = 'pro'
        elif query.data == "pay_premium_elite":
            plan_key = 'elite'
        elif query.data == "pay_premium_flash":
            plan_key = 'flash'
        
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
            [InlineKeyboardButton("📱 " + get_msg("btn_open_miniapp", lang), web_app=WebAppInfo(url=miniapp_url))],
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
        base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
        if base_url:
            miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}#premium"
            keyboard = [[
                InlineKeyboardButton(
                    "⭐ Ver Planes Premium" if lang == 'es' else "⭐ View Premium Plans",
                    web_app=WebAppInfo(url=miniapp_url)
                )
            ]]
            msg = "💎 Elige tu plan en la app:" if lang == 'es' else "💎 Choose your plan in the app:"
            try:
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
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
    plan = PREMIUM_PLANS.get(plan_key, PREMIUM_PLANS['pro'])
    
    # Build title and description based on plan
    if plan_key == 'basic':
        title = f"{plan['badge']} Suscripción Premium"
        description = f"Premium por {plan['days']} días | Ideal para empezar | Descargas ilimitadas"
    elif plan_key == 'pro':
        title = f"{plan['badge']} Suscripción Premium"
        description = f"Premium por {plan['days']} días (1 mes) | El más popular | Descargas ilimitadas"
    elif plan_key == 'elite':
        title = f"{plan['badge']} Suscripción Premium"
        description = f"Premium por {plan['days']} días (3 meses) | Máximo ahorro | Descargas ilimitadas"
    elif plan_key == 'flash':
        title = f"{plan['badge']} VIP"
        description = f"¡Venta Flash! Premium por {plan['days']} días al 50% de descuento"
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
            # Format: premium_7_days_basic_123456789 or premium_30_days_pro_123456789
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
    
    # FIX 2: Agregar botón para abrir la MiniApp con el nuevo estado premium
    miniapp_base = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
    if miniapp_base:
        full_miniapp_url = f"{miniapp_base}/miniapp?v=2&user_id={user_id}&lang={lang}"
        try:
            keyboard = [[
                InlineKeyboardButton(
                    "📱 Ver mi Premium" if lang == 'es' else "📱 View my Premium",
                    web_app=WebAppInfo(url=full_miniapp_url)
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "👇 *Abre la app para ver tu plan activo*" if lang == 'es' else "👇 *Open the app to see your active plan*",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending miniapp button after payment: {e}")


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
    lang = get_user_language(user)
    
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
            # 1. Resolver entidad (canal/grupo)
            try:
                if channel_identifier.startswith('+'):
                    invite_hash = channel_identifier[1:]
                    try:
                        await client(ImportChatInviteRequest(invite_hash))
                        await asyncio.sleep(1)
                    except UserAlreadyParticipantError:
                        pass
                    except (InviteHashExpiredError, InviteHashInvalidError):
                        await BotError.invite_link_expired(status_msg, is_message=True)
                        return
                    channel = await client.get_entity(invite_hash)
                else:
                    channel = await client.get_entity(int(channel_identifier) if channel_identifier.isdigit() else channel_identifier)
            except (ChannelPrivateError, ChatForbiddenError, ValueError):
                await BotError.private_channel_no_invite(status_msg, is_message=True)
                return
            
            # 2. Obtener mensaje(s)
            original_message = await client.get_messages(channel, ids=message_id)
            if not original_message:
                await BotError.message_not_found(status_msg, is_message=True)
                return
            
            # Detectar si es álbum o mensaje único
            is_album = hasattr(original_message, 'grouped_id') and original_message.grouped_id
            media_messages = []
            
            if is_album:
                # Buscar mensajes del mismo álbum
                grouped_id = original_message.grouped_id
                start_id = max(1, message_id - 10)
                end_id = message_id + 10
                ids_to_check = list(range(start_id, end_id + 1))
                
                try:
                    messages_batch = await client.get_messages(channel, ids=ids_to_check)
                    if messages_batch:
                        for msg in messages_batch:
                            if msg and hasattr(msg, 'grouped_id') and msg.grouped_id == grouped_id:
                                if msg.media:
                                    media_messages.append(msg)
                    if not media_messages:
                        media_messages = [original_message]
                    media_messages.sort(key=lambda m: m.id)
                except Exception as album_err:
                    logger.error(f"Error fetching album: {album_err}")
                    media_messages = [original_message]
            else:
                if not original_message.media:
                    await BotError.unsupported_content(status_msg, is_message=True)
                    return
                media_messages = [original_message]

            # 3. Analizar contenido y verificar límites
            check_and_reset_daily_limits(user_id)
            user = get_user(user_id)
            is_premium = user['premium']
            
            # Contadores para el resumen
            counts = {'photo': 0, 'video': 0, 'music': 0, 'apk': 0}
            messages_to_download = []
            limit_exceeded = False
            
            # Simulación de consumo de límites
            sim_usage = {
                'photo': user.get('daily_photo', 0),
                'video': user.get('daily_video', 0) if is_premium else user.get('downloads', 0),
                'music': user.get('daily_music', 0),
                'apk': user.get('daily_apk', 0)
            }
            
            shared_caption = ""
            
            for msg in media_messages:
                c_type = detect_content_type(msg)
                if c_type == 'other': continue
                
                # Buscar caption compartido en el álbum
                if not shared_caption:
                    shared_caption = extract_message_caption(msg)
                
                # Verificar si este ítem específico entra en el límite
                can_item_download = True
                if c_type == 'photo':
                    if not is_premium and sim_usage['photo'] >= FREE_PHOTO_LIMIT:
                        can_item_download = False
                    else:
                        sim_usage['photo'] += 1
                elif c_type == 'video':
                    video_limit = PREMIUM_VIDEO_DAILY_LIMIT if is_premium else FREE_DOWNLOAD_LIMIT
                    if sim_usage['video'] >= video_limit:
                        can_item_download = False
                    else:
                        sim_usage['video'] += 1
                elif c_type in ['music', 'apk']:
                    if not is_premium:
                        can_item_download = False
                    else:
                        limit_key = 'music' if c_type == 'music' else 'apk'
                        limit_val = PREMIUM_MUSIC_DAILY_LIMIT if c_type == 'music' else PREMIUM_APK_DAILY_LIMIT
                        if sim_usage[limit_key] >= limit_val:
                            can_item_download = False
                        else:
                            sim_usage[limit_key] += 1
                
                counts[c_type] += 1
                if can_item_download:
                    messages_to_download.append(msg)
                else:
                    limit_exceeded = True

            if not counts['photo'] and not counts['video'] and not counts['music'] and not counts['apk']:
                await BotError.unsupported_content(status_msg, is_message=True)
                return

            # 4. Construir y enviar mensaje de REPORTE "Se detectó"
            report_lines = [f"*{get_msg('status_detected_title', lang)}*"]
            if is_album:
                report_lines.append(get_msg('status_detected_album', lang))
            
            if counts['photo'] > 0:
                report_lines.append(get_msg('status_detected_photos', lang, count=counts['photo']))
            if counts['video'] > 0:
                report_lines.append(get_msg('status_detected_videos', lang, count=counts['video']))
            # (Opcional: agregar música/apk si el bot los detecta frecuentemente)
            
            if limit_exceeded:
                report_lines.append(f"\n{get_msg('status_limit_warning', lang)}")
            
            report_lines.append(f"\n{get_msg('status_starting_download', lang)}")
            
            await status_msg.edit_text("\n".join(report_lines), parse_mode='Markdown')
            await asyncio.sleep(1) # Breve pausa para que el usuario lea

            # 5. Ejecutar descargas
            if not messages_to_download:
                # No se pudo descargar nada por límites
                return # El mensaje ya tiene la advertencia

            total_to_download = len(messages_to_download)
            for idx, msg in enumerate(messages_to_download, 1):
                msg_type = detect_content_type(msg)
                
                # Actualizar estado de descarga
                if total_to_download > 1:
                    status_text = (
                        f"📥 *{get_msg('status_downloading', lang)}* ({idx}/{total_to_download})\n"
                        f"📦 {msg_type.capitalize()}"
                    )
                    await status_msg.edit_text(status_text, parse_mode='Markdown')
                
                # Descargar - pasamos bypass_limits=True porque ya los verificamos nosotros
                await handle_media_download(
                    update, context, msg, user, status_msg,
                    is_album=(total_to_download > 1),
                    album_index=idx, album_total=total_to_download,
                    bypass_limits=True, custom_caption=shared_caption
                )

            # 6. Mensaje Final
            if total_to_download > 1:
                try:
                    await status_msg.edit_text(
                        f"✅ *{get_msg('success_download', lang).strip()}*\n\n"
                        f"📥 {total_to_download} {get_msg('success_album', lang).split(' ')[-2]}",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
            elif not limit_exceeded:
                # Para un solo archivo que se descargó con éxito, handle_media_download borra el status_msg
                pass

    except FloodWaitError as e:
        await BotError.flood_wait(status_msg, e.seconds, is_message=True)
    except Exception as e:
        logger.error(f"Error en process_download: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await BotError.download_failed(status_msg, is_message=True)



async def handle_media_download(update: Update, context_or_bot,
                                message, user: dict, status_msg, is_album: bool = False, 
                                album_index: int = 1, album_total: int = 1,
                                bypass_limits: bool = False, custom_caption: str = None):
    """Maneja la descarga según el tipo de medio con validaciones optimizadas"""
    user_id = user.get('user_id', user.get('id'))
    bot = context_or_bot.bot if hasattr(context_or_bot, 'bot') else context_or_bot
    
    # Determinar tipo de contenido usando la función unificada
    content_type = detect_content_type(message)
    
    if content_type == 'other':
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
        success = await download_and_send_media(message, user_id, bot, caption=final_caption)
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
                rewards_count = check_and_reward_referrer(referrer_id)
                if rewards_count > 0:
                    try:
                        downloads_earned = rewards_count * 10
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 *¡Felicidades!*\n\n"
                                 f"Has alcanzado 15 referidos válidos y has ganado *{downloads_earned} descargas extra*.\n\n"
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
    Verifica si el usuario puede descargar según su plan.
    Free users: descargas basadas en referidos (15 refs = 10 descargas).
    Retorna: (puede_descargar, tipo_error, datos_error)
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
            # Free users: limit = referrals_rewarded * 10 (0 if no referrals)
            referrals_rewarded = user.get('referrals_rewarded', 0) or 0
            earned_downloads = referrals_rewarded * 10
            if user['downloads'] >= earned_downloads:
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
    
    # Obtener idioma del usuario
    user = get_user(user_id)
    lang = user.get('language') if user and user.get('language') else user_language

    # Mensaje de bienvenida corto
    if lang == 'es':
        if is_new_user:
            welcome_message = (
                f"👋 ¡Hola {first_name}! Bienvenido a *DownloadBot*.\n\n"
                "🚀 Tu portal premium para descargar contenido de Telegram:\n"
                "✨ Videos, Fotos, Música y APKs de canales privados.\n\n"
                "👇 *Presiona el botón para empezar:*"
            )
        else:
            welcome_message = (
                f"👋 ¡Hola de nuevo, {first_name}!\n\n"
                "🚀 *DownloadBot* está listo. ¿Qué quieres descargar hoy?\n\n"
                "👇 *Abre la app para continuar:*"
            )
    else:
        if is_new_user:
            welcome_message = (
                f"👋 Hello {first_name}! Welcome to *DownloadBot*.\n\n"
                "🚀 Your premium portal for Telegram downloads:\n"
                "✨ Videos, Photos, Music and APKs from private channels.\n\n"
                "👇 *Press the button to get started:*"
            )
        else:
            welcome_message = (
                f"👋 Welcome back, {first_name}!\n\n"
                "🚀 *DownloadBot* is ready. What do you want to download today?\n\n"
                "👇 *Open the app to continue:*"
            )

    # Construir teclado minimalista
    keyboard = []

    # Botón principal: MiniApp
    base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')
    if base_url:
        new_flag = "true" if is_new_user else "false"
        miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&new={new_flag}&lang={lang}"
        keyboard.append([
            InlineKeyboardButton(
                "📱 Abrir App" if lang == 'es' else "📱 Open App",
                web_app=WebAppInfo(url=miniapp_url)
            )
        ])

    # Solo si NO tiene cuenta configurada, mostrar botón de configurar
    has_session = has_active_session(user_id)
    if not has_session:
        keyboard.append([
            InlineKeyboardButton(
                "⚙️ Configurar cuenta" if lang == 'es' else "⚙️ Configure account",
                callback_data="connect_account"
            )
        ])

    # Soporte siempre disponible
    keyboard.append([
        InlineKeyboardButton(
            "💬 Soporte" if lang == 'es' else "💬 Support",
            url="https://t.me/observer_bots/11"
        )
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                welcome_message, parse_mode='Markdown', reply_markup=reply_markup
            )
        except Exception:
            await update.callback_query.message.reply_text(
                welcome_message, parse_mode='Markdown', reply_markup=reply_markup
            )
    elif update.message:
        await update.message.reply_text(
            welcome_message, parse_mode='Markdown', reply_markup=reply_markup
        )
    return


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /premium command - Redirect to MiniApp premium tab"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user)

    base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')

    if not base_url:
        msg = "⚠️ MiniApp no disponible. Usa /start." if lang == 'es' else "⚠️ MiniApp not available. Use /start."
        await update.message.reply_text(msg)
        return

    # Abrir directo en tab premium
    miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}#premium"

    msg = "💎 Elige tu plan Premium en la app:" if lang == 'es' else "💎 Choose your Premium plan in the app:"
    keyboard = [[
        InlineKeyboardButton(
            "⭐ Ver Planes Premium" if lang == 'es' else "⭐ View Premium Plans",
            web_app=WebAppInfo(url=miniapp_url)
        )
    ]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


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

    status_msg = await update.message.reply_text("🔍 *Ejecutando diagnóstico...*", parse_mode='Markdown')
    
    results = []
    
    # 1. Database Check
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        results.append("✅ *Base de datos:* Conectada")
    except Exception as e:
        results.append(f"❌ *Base de datos:* Error - `{str(e)}`")
        
    # 2. API Config
    if TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_TOKEN:
        results.append("✅ *Configuración API:* Presente")
    else:
        results.append("❌ *Configuración API:* Faltan variables (.env)")

    # 3. Telethon Bot Client
    if bot_client and bot_client.is_connected():
        results.append("✅ *Cliente Telethon (Bot):* Conectado")
    else:
        results.append("⚠️ *Cliente Telethon (Bot):* Desconectado o no iniciado")
        
    # 4. OS / Runtime
    import platform
    results.append(f"ℹ️ *Sistema:* `{platform.system()} {platform.release()}`")
    
    # 5. MiniApp URL
    miniapp_url = os.getenv('MINIAPP_URL', os.getenv('DASHBOARD_URL', ''))
    if miniapp_url:
        results.append(f"🔗 *MiniApp URL:* `{miniapp_url}`")
    else:
        results.append("⚠️ *MiniApp URL:* No definida")

    diagnostic_text = "📊 *Resultado del Diagnóstico:*\n\n" + "\n".join(results)
    diagnostic_text += "\n\n━━━━━━━━━━━━━━━\n📢 @observer_bots"
    
    await status_msg.edit_text(diagnostic_text, parse_mode='Markdown')


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
    miniapp_url += f'miniapp?v=2&user_id={user_id}&lang={lang}'
    
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
    """Handle /panel command - Redirect to MiniApp"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user)

    base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')

    if not base_url:
        msg = "⚠️ MiniApp no disponible. Usa /start." if lang == 'es' else "⚠️ MiniApp not available. Use /start."
        await update.message.reply_text(msg)
        return

    miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}"

    msg = "📊 Tu panel completo está en la app:" if lang == 'es' else "📊 Your full panel is in the app:"
    keyboard = [[
        InlineKeyboardButton(
            "📱 Abrir App" if lang == 'es' else "📱 Open App",
            web_app=WebAppInfo(url=miniapp_url)
        )
    ]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


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
    """Handle /referidos command - Redirect to MiniApp referrals tab"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user) if user else 'es'

    base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')

    if not base_url:
        msg = "⚠️ MiniApp no disponible. Usa /start." if lang == 'es' else "⚠️ MiniApp not available. Use /start."
        await update.message.reply_text(msg)
        return

    miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}"

    msg = "👥 Tu sistema de referidos está en la app:" if lang == 'es' else "👥 Your referral system is in the app:"
    keyboard = [[
        InlineKeyboardButton(
            "👥 Ver Mis Referidos" if lang == 'es' else "👥 View My Referrals",
            web_app=WebAppInfo(url=miniapp_url)
        )
    ]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - Redirect to MiniApp account tab"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = get_user_language(user)

    base_url = (os.getenv('MINIAPP_URL', '') or '').strip().rstrip('/')

    if not base_url:
        msg = "⚠️ MiniApp no disponible. Usa /start." if lang == 'es' else "⚠️ MiniApp not available. Use /start."
        await update.message.reply_text(msg)
        return

    miniapp_url = f"{base_url}/miniapp?v=2&user_id={user_id}&lang={lang}"

    msg = "📈 Tus estadísticas completas están en la app:" if lang == 'es' else "📈 Your full stats are in the app:"
    keyboard = [[
        InlineKeyboardButton(
            "📱 Ver Mis Stats" if lang == 'es' else "📱 View My Stats",
            web_app=WebAppInfo(url=miniapp_url)
        )
    ]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


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
                # Use local reply helper
                album_status = await reply("🔍 Detectando álbum...")
                grouped_id = message.grouped_id
                
                start_id = max(1, message_id - 10)
                end_id = message_id + 10
                ids_to_check = list(range(start_id, end_id + 1))
                
                try:
                    messages_batch = await client.get_messages(entity, ids=ids_to_check)
                    if messages_batch:
                        for msg in messages_batch:
                            if msg and hasattr(msg, 'grouped_id') and msg.grouped_id == grouped_id and msg.media:
                                album_messages.append(msg)
                    
                    if not album_messages:
                        album_messages = [message]
                    
                    album_messages.sort(key=lambda m: m.id)
                except Exception as batch_err:
                    logger.error(f"Error batch fetching album: {batch_err}")
                    album_messages = [message]

                lang = get_user_language(user)
                await album_status.edit_text(f"📸 {get_msg('status_album_detected', lang).format(count=len(album_messages))}")
            except Exception as album_err:
                logger.error(f"Error getting album messages: {album_err}")
                album_messages = [message]

        # 3. Analizar contenido y verificar límites
        check_and_reset_daily_limits(user_id)
        user = get_user(user_id)
        is_premium = user['premium']
        lang = get_user_language(user)
        
        media_messages = album_messages if album_messages else [message]
        messages_to_download = []
        counts = {'photo': 0, 'video': 0, 'music': 0, 'apk': 0}
        limit_exceeded = False
        
        sim_usage = {
            'photo': user.get('daily_photo', 0),
            'video': user.get('daily_video', 0) if is_premium else user.get('downloads', 0),
            'music': user.get('daily_music', 0),
            'apk': user.get('daily_apk', 0)
        }
        
        shared_caption = ""
        for msg in media_messages:
            if not msg.media: continue
            
            c_type = detect_content_type(msg)
            if c_type == 'other': continue
            
            if not shared_caption:
                shared_caption = extract_message_caption(msg)
            
            can_item_download = True
            if c_type == 'photo':
                if not is_premium and sim_usage['photo'] >= FREE_PHOTO_LIMIT:
                    can_item_download = False
                else:
                    sim_usage['photo'] += 1
            elif c_type == 'video':
                video_limit = PREMIUM_VIDEO_DAILY_LIMIT if is_premium else FREE_DOWNLOAD_LIMIT
                if sim_usage['video'] >= video_limit:
                    can_item_download = False
                else:
                    sim_usage['video'] += 1
            elif c_type in ['music', 'apk']:
                if not is_premium:
                    can_item_download = False
                else:
                    limit_key = 'music' if c_type == 'music' else 'apk'
                    limit_val = PREMIUM_MUSIC_DAILY_LIMIT if c_type == 'music' else PREMIUM_APK_DAILY_LIMIT
                    if sim_usage[limit_key] >= limit_val:
                        can_item_download = False
                    else:
                        sim_usage[limit_key] += 1
            
            counts[c_type] += 1
            if can_item_download:
                messages_to_download.append(msg)
            else:
                limit_exceeded = True

        # Fallback para enlaces anidados si no se encontró nada directo
        if not messages_to_download and not limit_exceeded:
            if not message.media and message.text:
                inner_links = re.findall(r'https?://t\.me/[^\s\)]+', message.text)
                if inner_links:
                    inner_parsed = parse_telegram_link(inner_links[0])
                    if inner_parsed:
                        inner_ch, inner_msg_id = inner_parsed
                        if inner_msg_id:
                            try:
                                inner_ent = await get_entity_from_identifier(client, inner_ch)
                                inner_msg = await client.get_messages(inner_ent, ids=inner_msg_id)
                                if inner_msg and inner_msg.media:
                                    # Reiniciar lógica con el nuevo mensaje anidado
                                    # Para simplificar, llamamos recursivamente o simplemente procesamos este
                                    return await handle_message_logic(update, context_or_bot, client, inner_links[0], inner_parsed, user_id, user)
                            except Exception: pass

        if not counts['photo'] and not counts['video'] and not counts['music'] and not counts['apk']:
            if not message.media and message.text:
                await reply(f"📄 *Contenido del Mensaje:*\n\n{message.text}")
            else:
                await reply("❌ *Sin Contenido soportado*")
            return

        # 4. Reporte "Se detectó"
        report_lines = [f"*{get_msg('status_detected_title', lang)}*"]
        if album_messages:
            report_lines.append(get_msg('status_detected_album', lang))
        
        if counts['photo'] > 0:
            report_lines.append(get_msg('status_detected_photos', lang, count=counts['photo']))
        if counts['video'] > 0:
            report_lines.append(get_msg('status_detected_videos', lang, count=counts['video']))
        
        if limit_exceeded:
            report_lines.append(f"\n{get_msg('status_limit_warning', lang)}")
        
        report_lines.append(f"\n{get_msg('status_starting_download', lang)}")
        
        status_msg = await reply("\n".join(report_lines))
        await asyncio.sleep(1)

        # 5. Descargar
        if not messages_to_download: return

        total = len(messages_to_download)
        for idx, msg in enumerate(messages_to_download, 1):
            if total > 1:
                try:
                    await status_msg.edit_text(f"📥 *{get_msg('status_downloading', lang)}* ({idx}/{total})")
                except Exception: pass
            
            await handle_media_download(
                update, context_or_bot, msg, user, status_msg,
                is_album=(total > 1), album_index=idx, album_total=total,
                bypass_limits=True, custom_caption=shared_caption
            )

        # Mensaje Final
        if total > 1:
            try:
                await status_msg.edit_text(f"✅ *{get_msg('success_download', lang).strip()}*\n\n📥 {total} {get_msg('success_album', lang).split(' ')[-2]}")
            except Exception: pass

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

    try:
        async with get_user_client(user_id) as client:
            await handle_message_logic(update, context, client, link, parsed, user_id, user)
    except ValueError as ve:
        if "Invalid session" in str(ve):
            await update.message.reply_text(
                "⚠️ *Sesión Caducada*\n\nTu sesión de Telegram ya no es válida o ha sido cerrada desde otro dispositivo.\n\n"
                "👉 Por seguridad, he desconectado tu cuenta. **Usa /configurar** para volver a vincularla.",
                parse_mode='Markdown'
            )
        else:
            logger.error(f"Error en handle_message para usuario {user_id}: {ve}")
            await update.message.reply_text("❌ Ocurrió un error al procesar tu solicitud.")
    except Exception as e:
        logger.error(f"Error inesperado en handle_message para usuario {user_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ Ocurrió un error inesperado.")


# Configuración de concurrencia para descargas
MAX_CONCURRENT_DOWNLOADS = 5
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

async def process_one_queued_download(application: Application, item: Dict):
    """Procesa una única descarga de la cola con protección de tiempo y concurrencia"""
    download_id = item['id']
    user_id = item['user_id']
    link = item['link']
    
    async with download_semaphore:
        try:
            logger.info(f"📥 Processing queued download {download_id} for user {user_id}: {link}")
            
            # Check user existence and data
            user = get_user(user_id)
            if not user:
                update_download_status(download_id, 'error', 'User not found')
                return
            
            # Parse link
            parsed = parse_telegram_link(link)
            if not parsed:
                await application.bot.send_message(user_id, "❌ El enlace enviado desde la MiniApp no es válido.")
                update_download_status(download_id, 'error', 'Invalid link')
                return
            
            # Use handle_message_logic with timeout (15 minutes max per download)
            try:
                async with asyncio.timeout(900): # 15 min timeout
                    async with get_user_client(user_id) as client:
                        await handle_message_logic(None, application, client, link, parsed, user_id, user)
                        update_download_status(download_id, 'processed')
                        logger.info(f"✅ Download {download_id} processed successfully")
            except TimeoutError:
                logger.error(f"⏱️ Timeout processing download {download_id}")
                update_download_status(download_id, 'error', 'Timeout - processing took too long')
                await application.bot.send_message(user_id, "❌ La descarga ha tardado demasiado y ha sido cancelada.")
            except ValueError as ve:
                if "Invalid session" in str(ve):
                    update_download_status(download_id, 'error', 'Invalid session - user disconnected')
                    await application.bot.send_message(
                        user_id, 
                        "⚠️ *Sesión Caducada*\n\nTu sesión de Telegram ya no es válida. Por seguridad, he desconectado tu cuenta.\n\n👉 Por favor, abre la MiniApp y vuelve a configurarla en la pestaña 'Cuenta'.",
                        parse_mode='Markdown'
                    )
                else:
                    update_download_status(download_id, 'error', str(ve))
            except Exception as proc_e:
                logger.error(f"Error processing queued download {download_id}: {proc_e}")
                update_download_status(download_id, 'error', str(proc_e))
                await application.bot.send_message(user_id, f"❌ Error al procesar descarga: {str(proc_e)[:50]}")
                
        except Exception as e:
            logger.error(f"Fatal error in process_one_queued_download {download_id}: {e}")
            update_download_status(download_id, 'error', f"Fatal: {str(e)}")


async def miniapp_queue_observer(application: Application):
    """
    Background task that polls the database for pending downloads from the MiniApp
    """
    logger.info(f"🚀 MiniApp Queue Observer started (Concurrency: {MAX_CONCURRENT_DOWNLOADS})")
    while True:
        try:
            # Poll for next pending download
            item = get_next_pending_download()
            
            if item:
                # Mark as processing IMMEDIATELY to avoid other threads/tasks picking it up
                update_download_status(item['id'], 'processing')
                
                # Start processing in background without blocking the loop
                asyncio.create_task(process_one_queued_download(application, item))
                
                # Don't sleep if we found an item, try to pick next one immediately
                # to fill up the concurrency slots
                continue
            
        except Exception as queue_e:
            logger.error(f"Error in miniapp_queue_observer: {queue_e}")
            
        # Wait before next poll if queue was empty
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
        BotCommand("start", "🏠 Inicio"),
        BotCommand("configurar", "⚙️ Configurar cuenta de Telegram"),
        BotCommand("miniapp", "📱 Abrir App")
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
                    text="📱 Abrir App",
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
        except Exception as e:
            logger.debug(f"Error disconnecting login client {user_id}: {e}")
            pass
            
    # Close bot client
    if bot_client:
        try:
            await bot_client.disconnect()
        except Exception as e:
            logger.debug(f"Error disconnecting bot client: {e}")
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
        
    # 3. Distributed Protection (Database Leader Election)
    # Give it a few tries in case of DB contention
    acquired = False
    for i in range(3):
        if try_acquire_bot_leadership(INSTANCE_ID):
            acquired = True
            break
        await asyncio.sleep(2)
        
    if not acquired:
        logger.warning(f"⚠️ Instance {INSTANCE_ID} could not acquire leadership. Another instance is likely running. Skipping.")
        return

    _bot_instance_running = True
    logger.info(f"👑 Instance {INSTANCE_ID} acquired leadership.")

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
    
    # Start heartbeat task
    async def leadership_heartbeat():
        while _bot_instance_running:
            try:
                if not try_acquire_bot_leadership(INSTANCE_ID):
                    logger.error("❌ Lost leadership! Shutting down this instance...")
                    os._exit(1) # Radical shutdown to prevent Conflict 409
                await asyncio.sleep(30) # Update leadership every 30s
            except Exception as e:
                logger.error(f"Error in heartbeat: {e}")
                await asyncio.sleep(10)

    asyncio.create_task(leadership_heartbeat())
    
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
        # application.initialize() is handled in the retry loop above
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
