#!/usr/bin/env python3
"""
Script de diagnóstico para problemas de conexión en Railway
Ejecutar con: python3 railway_diagnostic.py
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

def check_environment():
    """Verificar variables de entorno necesarias"""
    print("🔍 Verificando variables de entorno...")

    required_vars = {
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'TELEGRAM_API_ID': os.getenv('TELEGRAM_API_ID'),
        'TELEGRAM_API_HASH': os.getenv('TELEGRAM_API_HASH'),
        'RAILWAY_ENVIRONMENT': os.getenv('RAILWAY_ENVIRONMENT'),
        'RAILWAY_PROJECT_ID': os.getenv('RAILWAY_PROJECT_ID')
    }

    for var, value in required_vars.items():
        status = "✅" if value else "❌"
        print(f"  {status} {var}: {'Configurado' if value else 'NO CONFIGURADO'}")

    return all(required_vars.values())

async def test_telegram_connection():
    """Probar conexión básica a Telegram"""
    print("\n🌐 Probando conexión a Telegram...")

    try:
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')

        if not api_id or not api_hash:
            print("❌ Faltan TELEGRAM_API_ID o TELEGRAM_API_HASH")
            return False

        print("  📡 Intentando conectar...")
        client = TelegramClient(StringSession(), int(api_id), api_hash)

        # Timeout más largo para Railway
        await asyncio.wait_for(client.connect(), timeout=30)
        print("  ✅ Conexión exitosa")

        # Verificar si ya está autorizado
        authorized = await client.is_user_authorized()
        print(f"  {'✅' if authorized else '❌'} Cliente {'autorizado' if authorized else 'no autorizado'}")

        await client.disconnect()
        return True

    except asyncio.TimeoutError:
        print("❌ Timeout conectando a Telegram (posible bloqueo en Railway)")
        return False
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        return False

async def test_bot_connection():
    """Probar conexión del bot"""
    print("\n🤖 Probando conexión del bot...")

    try:
        from telegram import Bot
        token = os.getenv('TELEGRAM_BOT_TOKEN')

        if not token:
            print("❌ Falta TELEGRAM_BOT_TOKEN")
            return False

        print("  📡 Probando bot...")
        bot = Bot(token)

        # Timeout para Railway
        me = await asyncio.wait_for(bot.get_me(), timeout=30)
        print(f"  ✅ Bot conectado: @{me.username}")
        return True

    except Exception as e:
        print(f"❌ Error con bot: {e}")
        return False

async def main():
    """Función principal de diagnóstico"""
    print("🚀 Diagnóstico de Railway - Bot Telegram")
    print("=" * 50)

    # Verificar entorno
    env_ok = check_environment()

    # Probar conexiones
    telegram_ok = await test_telegram_connection()
    bot_ok = await test_bot_connection()

    print("\n" + "=" * 50)
    print("📊 RESULTADO:")

    if env_ok and telegram_ok and bot_ok:
        print("✅ Todo parece estar bien. El problema puede ser temporal.")
        print("💡 Sugerencias:")
        print("   - Espera unos minutos y vuelve a intentar")
        print("   - Verifica que el número de teléfono sea correcto")
        print("   - Asegúrate de que puedas recibir SMS")
    else:
        print("❌ Hay problemas de configuración.")
        print("🔧 Soluciones para Railway:")

        if not env_ok:
            print("   1. Configura todas las variables de entorno en Railway Dashboard")
            print("   2. Variables requeridas: TELEGRAM_BOT_TOKEN, TELEGRAM_API_ID, TELEGRAM_API_HASH")

        if not telegram_ok:
            print("   3. Railway puede bloquear conexiones MTProto (Telethon)")
            print("   4. Considera usar un VPS en lugar de Railway para este bot")
            print("   5. Contacta soporte de Railway sobre restricciones de red")

        if not bot_ok:
            print("   6. Verifica que el token del bot sea válido")
            print("   7. Asegúrate de que el bot no esté bloqueado")

    print("\n📞 Si el problema persiste, contacta: @observer_bots")

if __name__ == "__main__":
    asyncio.run(main())