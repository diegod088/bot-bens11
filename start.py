#!/usr/bin/env python3
"""
🚀 TELEGRAM BOT + DASHBOARD - UNIFIED STARTUP (FIXED)

ARQUITECTURA CORRECTA:
- Bot ejecuta en MAIN THREAD (evita set_wakeup_fd error)
- Dashboard ejecuta en thread SECUNDARIO
- Sin asyncio.run() en threads secundarios
"""

import os
import sys
import threading
import signal
import logging
import asyncio
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize database
try:
    from database import init_database
    init_database()
    logger.info("✅ Database initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize database: {e}")

# Flag to prevent multiple instances
_bot_started = False
_bot_lock = threading.Lock()


def run_dashboard():
    """Run Flask dashboard in a SEPARATE THREAD (non-blocking)"""
    try:
        from dashboard import app
        
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        logger.info(f"🌐 Starting Dashboard on {host}:{port}")
        
        try:
            from waitress import serve
            logger.info("📦 Using Waitress production server (8 threads)")
            serve(app, host=host, port=port, threads=8)
        except ImportError:
            logger.info("Using Flask development server (not recommended for production)")
            app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
            
    except Exception as e:
        logger.error(f"❌ Dashboard error: {e}", exc_info=True)
        raise


async def run_bot_async():
    """
    Bot execution (ASYNC ONLY - NO THREADING)
    This runs in the MAIN thread's event loop
    """
    global _bot_started
    
    # Prevent duplicate instances
    with _bot_lock:
        if _bot_started:
            logger.warning("⚠️ Bot already started, skipping")
            return
        _bot_started = True
    
    try:
        logger.info("=" * 80)
        logger.info("🤖 TELEGRAM BOT - MAIN THREAD EXECUTION")
        logger.info("=" * 80)
        
        from bot_with_paywall import async_main
        await async_main()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Bot interrupted")
    except Exception as e:
        logger.error(f"❌ Bot error: {e}", exc_info=True)
    finally:
        with _bot_lock:
            _bot_started = False


def main():
    """
    MAIN ENTRY POINT - CORRECT ARCHITECTURE
    
    1. Bot runs in MAIN THREAD (asyncio.run)
    2. Dashboard runs in SEPARATE THREAD
    """
    logger.info("=" * 80)
    logger.info("🚀 UNIFIED STARTUP - BOT (MAIN) + DASHBOARD (THREAD)")
    logger.info("=" * 80)
    
    # Signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    
    # Check bot requirements
    telegram_token = os.environ.get('TELEGRAM_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not telegram_token:
        logger.error(f"❌ Missing TELEGRAM_TOKEN")
        logger.warning("⚠️ Starting dashboard only (no bot)")
        
        # Run only dashboard in main thread
        try:
            run_dashboard()
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down...")
        return
    
    logger.info("✅ Bot token found")
    logger.info("")
    
    # Start dashboard in SEPARATE THREAD (non-daemon so it keeps running)
    logger.info("=" * 80)
    logger.info("📍 Starting Dashboard in background thread")
    logger.info("=" * 80)
    
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        daemon=False,  # Non-daemon to ensure it keeps running
        name="DashboardThread"
    )
    dashboard_thread.start()
    logger.info(f"✅ Dashboard thread started: {dashboard_thread.name}")
    
    # Give dashboard time to start before healthcheck
    import time
    time.sleep(2)
    logger.info("")
    
    # Run bot in MAIN THREAD (prevents set_wakeup_fd error)
    logger.info("=" * 80)
    logger.info("📍 Running Bot in MAIN THREAD")
    logger.info("=" * 80)
    logger.info("(This is the correct way - no async.run() in threads)")
    logger.info("")
    
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
