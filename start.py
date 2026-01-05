#!/usr/bin/env python3
"""
🚀 TELEGRAM BOT + DASHBOARD - UNIFIED STARTUP
This script runs BOTH the Telegram bot and the Flask dashboard simultaneously.

⚠️ IMPORTANT NOTES:
1. The bot runs in a separate thread with its own asyncio event loop
2. The dashboard runs in the main thread (blocking)
3. Only ONE polling instance is allowed per token (causes 409 Conflict)
4. Use railway_start.py (dashboard only) for production Railway deployment
"""

import os
import sys
import threading
import signal
import logging
import time
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
    # Continue anyway to start the server

# Global flag to prevent multiple bot instances
_bot_started = False
_bot_lock = threading.Lock()


def run_dashboard():
    """Run the Flask dashboard in the main thread"""
    try:
        # Import here to avoid circular imports
        from dashboard import app
        
        # Get port from environment (Railway provides PORT)
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        logger.info(f"🌐 Starting Dashboard on {host}:{port}")
        
        # Use waitress for production if available, otherwise use Flask's built-in server
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


def run_bot():
    """
    Run the Telegram bot in a separate thread with its own event loop
    
    ⚠️ CRITICAL: Each thread MUST have its own event loop
    """
    global _bot_started
    
    # Prevent multiple bot instances (causes Telegram 409 Conflict error)
    with _bot_lock:
        if _bot_started:
            logger.warning("⚠️ Bot already started, skipping duplicate initialization")
            return
        _bot_started = True
    
    try:
        logger.info("=" * 80)
        logger.info("🤖 TELEGRAM BOT - INITIALIZING IN SEPARATE THREAD")
        logger.info("=" * 80)
        
        # Create a NEW event loop for this thread (CRITICAL!)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Import and run the bot's async main function
            from bot_with_paywall import async_main
            
            logger.info("🤖 Running async_main() in bot thread...")
            loop.run_until_complete(async_main())
            
        except KeyboardInterrupt:
            logger.info("⚠️ Bot interrupted")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}", exc_info=True)
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"❌ Bot thread error: {e}", exc_info=True)
        # Reset flag on error to allow retry
        with _bot_lock:
            _bot_started = False
        raise


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("🛑 Shutdown signal received, stopping services...")
    sys.exit(0)


def main():
    """Main entry point - runs both bot and dashboard"""
    logger.info("=" * 80)
    logger.info("🚀 UNIFIED STARTUP - BOT + DASHBOARD")
    logger.info("=" * 80)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Check required environment variables for the bot
    required_bot_vars = [
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_API_ID', 
        'TELEGRAM_API_HASH',
    ]
    
    # Alternative variable names
    alt_vars = {
        'TELEGRAM_BOT_TOKEN': 'TELEGRAM_TOKEN',
        'TELEGRAM_API_ID': 'API_ID',
        'TELEGRAM_API_HASH': 'API_HASH'
    }
    
    missing_vars = []
    for var in required_bot_vars:
        if not os.environ.get(var):
            # Check alternative name
            alt = alt_vars.get(var)
            if alt and os.environ.get(alt):
                logger.info(f"ℹ️ Using alternative variable name for {var}: {alt}")
                continue
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables for bot: {missing_vars}")
        logger.error("Please set these in your Railway project settings")
        logger.warning("⚠️ Starting dashboard only (bot will NOT be available)")
        logger.info("")
    else:
        logger.info("✅ All required environment variables found")
        logger.info("")
        
        # Start the bot in a SEPARATE THREAD with its own event loop
        logger.info("=" * 80)
        logger.info("📍 Starting Telegram Bot in background thread")
        logger.info("=" * 80)
        
        bot_thread = threading.Thread(
            target=run_bot,
            daemon=True,
            name="TelegramBotThread"
        )
        bot_thread.start()
        logger.info(f"✅ Bot thread started: {bot_thread.name}")
        
        # Give the bot a moment to initialize
        time.sleep(3)
        logger.info("")
    
    # Run the dashboard in the MAIN THREAD (blocking)
    logger.info("=" * 80)
    logger.info("📍 Starting Flask Dashboard in main thread")
    logger.info("=" * 80)
    logger.info("(Press Ctrl+C to stop both services)")
    logger.info("")
    
    run_dashboard()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}", exc_info=True)
        sys.exit(1)

