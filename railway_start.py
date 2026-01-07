#!/usr/bin/env python3
"""
🚀 RAILWAY DEFINITIVE STARTUP SCRIPT
Ensures the HTTP server (Dashboard + Health) is the main process.
Starts the Telegram Bot in a background thread.
"""

import os
import sys
import threading
import logging
import asyncio
import time
from waitress import serve
from dotenv import load_dotenv

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RailwayStart")

# Load environment variables
load_dotenv()

def run_bot_in_thread():
    """
    Function to run the Telegram bot in a separate event loop and thread.
    This ensures it doesn't block the main Flask/Waitress server.
    """
    logger.info("🤖 [THREAD] Initializing Telegram Bot loop...")
    
    # Each thread needs its own event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Import inside thread to avoid issues
        from bot_with_paywall import async_main
        from database import init_database
        
        logger.info("🤖 [THREAD] Initializing database...")
        init_database()
        
        logger.info("🤖 [THREAD] Running async_main()...")
        # run_until_complete is fine here as it's a dedicated loop for this thread
        loop.run_until_complete(async_main())
        
    except Exception as e:
        logger.error(f"❌ [THREAD] Bot failed with error: {e}", exc_info=True)
    finally:
        logger.info("🤖 [THREAD] Bot loop finishing...")
        loop.close()

def main():
    logger.info("=" * 60)
    logger.info("🚀 STARTING UNIFIED SERVICE (MAIN PROCESS)")
    logger.info("=" * 60)

    # 1. Start the bot in background
    bot_thread = threading.Thread(
        target=run_bot_in_thread, 
        daemon=True, # Allow main process to exit even if bot is stuck
        name="BotBackgroundThread"
    )
    bot_thread.start()
    logger.info("✅ Telegram Bot thread launched (background)")

    # 2. Give the bot a small head start (optional)
    time.sleep(2)

    # 3. Start the Web Server (Dashboard + /health) as the main process
    try:
        from dashboard import app
        
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0' # Required for Railway
        
        logger.info(f"🌐 Starting Dashboard on {host}:{port}")
        logger.info(f"🏥 Health check: http://{host}:{port}/health")
        
        # We use Waitress for production - this is what BLOCKS and keeps process alive
        logger.info("📦 Server: Waitress (8 threads)")
        print(f"\n✅ SERVICE IS READY AND LISTENING ON {host}:{port}\n", flush=True)
        
        serve(app, host=host, port=port, threads=8, _quiet=True)
        
    except KeyboardInterrupt:
        logger.info("🛑 Manually stopped")
    except Exception as e:
        logger.error(f"❌ Web Server failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
