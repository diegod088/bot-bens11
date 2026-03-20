#!/usr/bin/env python3
import sys
import os
import argparse
import asyncio
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Configuración
load_dotenv()

async def activate_affiliate(api_id, api_hash, bot_id_or_username, commission=100, session_str=None):
    """
    Activa el Programa de Afiliados de Telegram Stars para un bot.
    """
    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    
    await client.connect()
    
    if not await client.is_user_authorized():
        print("❌ Error: La sesión no es válida o no está autorizada.")
        if not session_str:
            print("💡 No proporcionaste un StringSession. Por favor, inicia sesión interactivamente:")
            phone = input("Ingresa tu número de teléfono (con +): ")
            await client.start(phone=phone)
            print("✅ Sesión creada con éxito.")
            print(f"🔑 Tu StringSession es: {client.session.save()}")
        else:
            return False

    try:
        # Obtener la entidad del bot
        bot = await client.get_entity(bot_id_or_username)
        print(f"🤖 Bot detectado: {bot.first_name} (@{bot.username})")
        
        # Activar el programa
        # bots.updateStarRefProgram(bot=bot, commission_permille=commission, duration_months=0)
        result = await client(functions.bots.UpdateStarRefProgramRequest(
            bot=bot,
            commission_permille=commission,
            duration_months=0
        ))
        
        print(f"✅ Programa de afiliados activado exitosamente!")
        print(f"📊 Comisión: {commission / 10}% ({commission} permille)")
        return True
        
    except Exception as e:
        print(f"❌ Error al activar el programa: {e}")
        return False
    finally:
        await client.disconnect()

async def main():
    parser = argparse.ArgumentParser(description="Activa el programa de afiliados de Telegram Stars.")
    parser.add_argument("--api-id", help="Telegram API ID", default=os.getenv("TELEGRAM_API_ID"))
    parser.add_argument("--api-hash", help="Telegram API Hash", default=os.getenv("TELEGRAM_API_HASH"))
    parser.add_argument("--bot", help="ID o username del bot", default="8520075728")
    parser.add_argument("--commission", type=int, default=100, help="Comisión en permille (100 = 10%%)")
    parser.add_argument("--session", help="Telethon StringSession", default=os.getenv("TELEGRAM_SESSION_STRING"))
    
    args = parser.parse_args()
    
    if not args.api_id or not args.api_hash:
        print("❌ Error: API_ID y API_HASH son obligatorios.")
        sys.exit(1)
        
    success = await activate_affiliate(
        int(args.api_id), 
        args.api_hash, 
        args.bot, 
        args.commission, 
        args.session
    )
    
    if success:
        print("\n🚀 El programa ya debería estar visible en BotFather y en la interfaz de afiliados del bot.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
