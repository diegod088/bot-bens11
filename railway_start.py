#!/usr/bin/env python3
"""
Railway Startup Script
Runs both the health server (for Railway healthcheck) and the Telegram bot
"""

import os
import sys
import subprocess
import signal
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Store process references
processes = []

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("🛑 Shutdown signal received, stopping all services...")
    for process in processes:
        try:
            process.terminate()
        except:
            pass
    sys.exit(0)

def main():
    """Main entry point - runs both services"""
    logger.info("=" * 60)
    logger.info("🚀 RAILWAY DEPLOYMENT STARTING")
    logger.info("=" * 60)
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize database
    try:
        from database import init_database
        init_database()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
    
    # Start health server in background
    logger.info("🏥 Starting Health Server...")
    health_process = subprocess.Popen(
        [sys.executable, "health_server.py"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    processes.append(health_process)
    logger.info(f"✅ Health Server started (PID: {health_process.pid})")
    
    # Give health server time to start
    time.sleep(2)
    
    # Start Telegram bot in foreground
    logger.info("🤖 Starting Telegram Bot...")
    bot_process = subprocess.Popen(
        [sys.executable, "bot_with_paywall.py"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    processes.append(bot_process)
    logger.info(f"✅ Telegram Bot started (PID: {bot_process.pid})")
    
    # Wait for bot process (keeps container running)
    try:
        bot_process.wait()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    finally:
        # Clean up all processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()

if __name__ == '__main__':
    main()
