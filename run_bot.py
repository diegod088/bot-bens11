#!/usr/bin/env python3
"""
🚀 TELEGRAM BOT - SOLO BOT (para Railway)
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv
import nest_asyncio

# Apply nest_asyncio to allow nested event loops (CRITICAL for python-telegram-bot)
nest_asyncio.apply()

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
    sys.exit(1)

def main():
    """Run only the Telegram bot"""
    
    # Check required variables
    required_vars = ['TELEGRAM_TOKEN', 'ENCRYPTION_KEY']
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        logger.error(f"❌ Missing required variables: {missing}")
        sys.exit(1)
    
    logger.info("✅ All requirements satisfied")
    logger.info("")
    logger.info("=" * 80)
    logger.info("🤖 STARTING TELEGRAM BOT")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        from bot_with_paywall import async_main
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
