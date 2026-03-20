import asyncio
import os
import argparse
from dotenv import load_dotenv
from telegram import Bot
from database import get_db_connection

load_dotenv()

async def broadcast_message(test_mode=True):
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("Error: No TELEGRAM_BOT_TOKEN found in environment")
        return

    bot = Bot(token=bot_token)
    
    # Message outlining the new Paywall / System
    message_text = (
        "🚀 **Actualización en DownloadBot** 🚀\n\n"
        "Hemos renovado nuestra interfaz y sistema de recompensas. Estas son las novedades:\n\n"
        "⛔️ **Fin de las descargas gratuitas**\n"
        "Para mantener nuestros servidores rápidos, ahora requerimos que los usuarios participen en el bot.\n\n"
        "🔥 **Misiones de Referidos**\n"
        "¡Trae a 15 amigos y obtén **10 descargas extra** totalmente gratis para descargar lo que quieras!\n\n"
        "🚀 **Nuevos Planes Premium**\n"
        "¿Necesitas tus descargas ya? Adquiere el plan **Básico (333 ⭐)** o el **Pro (777 ⭐)**.\n\n"
        "Escribe /start para ver el nuevo diseño y planes de la MiniApp."
    )
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if test_mode:
            admin_id = os.getenv('ADMIN_ID')
            if not admin_id:
                print("No ADMIN_ID found for test broadcast")
                return
            users = [{'user_id': int(admin_id)}]
            print(f"Test mode: Broadcasting to admin {admin_id}")
        else:
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            print(f"Production mode: Broadcasting to {len(users)} users.")
            
    success_count = 0
    fail_count = 0
    
    for user in users:
        user_id = user['user_id']
        try:
            await bot.send_message(chat_id=user_id, text=message_text, parse_mode='Markdown')
            success_count += 1
            if not test_mode:
                await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            
    print(f"\nBroadcast terminado. Éxitos: {success_count}, Fallos: {fail_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Broadcast new paywall messages")
    parser.add_argument("--all", action="store_true", help="Send to all users instead of just testing on the admin")
    args = parser.parse_args()
    asyncio.run(broadcast_message(test_mode=not args.all))
