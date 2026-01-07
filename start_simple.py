#!/usr/bin/env python3
"""
Simple startup - Bot + Dashboard without complex threading
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("🚀 SIMPLE STARTUP - Bot + Dashboard")
logger.info("=" * 80)

# Initialize database
try:
    from database import init_database
    init_database()
    logger.info("✅ Database initialized")
except Exception as e:
    logger.error(f"❌ Database error: {e}")
    sys.exit(1)

# Start dashboard in background
import threading
def start_dashboard():
    try:
        from dashboard import app
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0'
        
        logger.info(f"🌐 Dashboard: http://{host}:{port}")
        
        from waitress import serve
        serve(app, host=host, port=port, threads=4, _quiet=True)
    except Exception as e:
        logger.error(f"❌ Dashboard error: {e}", exc_info=True)

dashboard_thread = threading.Thread(target=start_dashboard, daemon=False)
dashboard_thread.start()
logger.info("✅ Dashboard thread started")

# Wait for dashboard to start
import time
time.sleep(3)

# Start bot
try:
    logger.info("🤖 Starting Bot...")
    from bot_with_paywall import async_main
    import asyncio
    asyncio.run(async_main())
except KeyboardInterrupt:
    logger.info("🛑 Shutting down...")
    sys.exit(0)
except Exception as e:
    logger.error(f"❌ Bot error: {e}", exc_info=True)
    sys.exit(1)
