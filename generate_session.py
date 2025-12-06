#!/usr/bin/env python3
"""
Script para generar Session String de Telethon
Ejecuta: python generate_session.py
"""
import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Cargar variables de entorno
load_dotenv()

# Obtener credenciales de .env
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

def main():
    print("=" * 70)
    print("GENERADOR DE SESSION STRING DE TELETHON")
    print("=" * 70)
    print("")
    print("Se te pedirá:")
    print("  1. Número de teléfono (con código de país, ej: +1234567890)")
    print("  2. Código de verificación que recibirás en Telegram")
    print("  3. Contraseña de 2FA (si la tienes configurada)")
    print("")
    
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_string = client.session.save()
        
        print("")
        print("=" * 70)
        print("✅ SESSION STRING GENERADO EXITOSAMENTE")
        print("=" * 70)
        print("")
        print(session_string)
        print("")
        print("=" * 70)
        print("")
        print("Copia este string y úsalo como TELEGRAM_SESSION_STRING")
        print("en tus variables de entorno de Railway.")
        print("")

if __name__ == "__main__":
    main()
