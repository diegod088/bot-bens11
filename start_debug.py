#!/usr/bin/env python3
"""
Debug Startup Script - More verbose logging for Railway
"""
import os
import sys
import logging
from pathlib import Path

# Ensure we have good logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/startup.log')
    ]
)
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("🚀 STARTING BOT + DASHBOARD (DEBUG MODE)")
print("="*80 + "\n", flush=True)

logger.info("Starting startup sequence...")

# Step 1: Check environment
logger.info("Step 1: Checking environment variables")
token = os.environ.get('TELEGRAM_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
if token:
    logger.info(f"✅ TELEGRAM_TOKEN found (length: {len(token)})")
else:
    logger.error("❌ TELEGRAM_TOKEN not found!")

encryption_key = os.environ.get('ENCRYPTION_KEY')
if encryption_key:
    logger.info(f"✅ ENCRYPTION_KEY found")
else:
    logger.warning("⚠️  ENCRYPTION_KEY not found (may use default)")

port = os.environ.get('PORT', 5000)
logger.info(f"📍 PORT: {port}")

# Step 2: Initialize database
logger.info("Step 2: Initializing database...")
try:
    from database import init_database
    init_database()
    logger.info("✅ Database initialized successfully")
except Exception as e:
    logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
    sys.exit(1)

# Step 3: Start dashboard thread
logger.info("Step 3: Starting dashboard in background thread...")
import threading

def start_dashboard():
    try:
        logger.info("Dashboard thread: Importing Flask app...")
        from dashboard import app
        
        host = '0.0.0.0'
        logger.info(f"Dashboard thread: Starting Flask on {host}:{port}")
        
        from waitress import serve
        logger.info("Dashboard thread: Using Waitress server")
        
        # Log that we're about to serve
        logger.info(f"Dashboard thread: SERVING on http://{host}:{port}")
        print(f"\n✅ DASHBOARD READY at http://{host}:{port}\n", flush=True)
        
        serve(app, host=host, port=port, threads=4, _quiet=False)
        
    except Exception as e:
        logger.error(f"❌ Dashboard error: {e}", exc_info=True)
        raise

dashboard_thread = threading.Thread(target=start_dashboard, daemon=False, name="Dashboard")
dashboard_thread.start()
logger.info("✅ Dashboard thread started")

# Step 4: Wait for dashboard to initialize
logger.info("Step 4: Waiting for dashboard to initialize...")
import time
time.sleep(4)
logger.info("✅ Dashboard initialization wait complete")

# Step 5: Start bot
logger.info("Step 5: Starting Telegram bot...")
try:
    logger.info("Importing bot module...")
    from bot_with_paywall import async_main
    
    logger.info("Starting async bot...")
    import asyncio
    logger.info("🤖 BOT STARTING - Polling messages...")
    print("\n✅ BOT READY - Listening for messages\n", flush=True)
    
    asyncio.run(async_main())
    
except KeyboardInterrupt:
    logger.info("Interrupted by user")
    sys.exit(0)
except Exception as e:
    logger.error(f"❌ Bot error: {e}", exc_info=True)
    sys.exit(1)
