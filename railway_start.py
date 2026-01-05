#!/usr/bin/env python3
"""
🚂 Railway Startup Script - BOT + DASHBOARD (SINGLE EVENT LOOP)
"""

import os
import sys
import logging
import threading
import asyncio
from dotenv import load_dotenv

# Necesario para threads con asyncio
try:
    import nest_asyncio
    nest_asyncio.apply()
    logger_temp = logging.getLogger(__name__)
    logger_temp.info("✅ nest_asyncio applied")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

load_dotenv()

def init_database():
    """Inicializar base de datos"""
    try:
        from database import init_database as db_init
        db_init()
        logger.info("✅ Database initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return False

def run_dashboard():
    """Ejecutar Dashboard Flask (en thread secundario)"""
    try:
        from dashboard import app
        port = int(os.environ.get('PORT', 8080))
        host = os.environ.get('HOST', '0.0.0.0')
        
        logger.info(f"🌐 Dashboard on {host}:{port}")
        
        try:
            from waitress import serve
            logger.info("📦 Using Waitress production server")
            serve(app, host=host, port=port, threads=8)
        except ImportError:
            logger.info("Using Flask development server")
            app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
            
    except Exception as e:
        logger.error(f"❌ Dashboard error: {e}")

async def run_bot_async():
    """Ejecutar el bot Telegram"""
    try:
        logger.info("🤖 Starting Telegram Bot...")
        from bot_with_paywall import async_main
        await async_main()
    except Exception as e:
        logger.error(f"❌ Bot error: {e}", exc_info=True)
        raise

def main():
    """Ejecutar BOT (priority) o DASHBOARD (fallback)"""
    
    logger.info("=" * 70)
    logger.info("🚂 RAILWAY DEPLOYMENT")
    logger.info("=" * 70)
    logger.info("")
    
    # Initialize database
    if not init_database():
        logger.error("Failed to initialize database")
        sys.exit(1)
    
    # Check for bot token
    telegram_token = os.environ.get('TELEGRAM_TOKEN')
    if telegram_token:
        logger.info("✅ TELEGRAM_TOKEN found - starting BOT")
        logger.info("")
        logger.info("📍 Running Bot in MAIN THREAD...")
        try:
            asyncio.run(run_bot_async())
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"❌ Fatal bot error: {e}", exc_info=True)
            sys.exit(1)
    else:
        logger.error("❌ TELEGRAM_TOKEN not found")
        logger.info("Starting DASHBOARD only...")
        logger.info("")
        run_dashboard()

if __name__ == '__main__':
    main()

