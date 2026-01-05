#!/usr/bin/env python3
"""
🚂 Railway Startup Script - DASHBOARD ONLY
"""

import os
import sys
import signal
import logging
from dotenv import load_dotenv

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
    """Ejecutar Dashboard Flask (PRODUCCIÓN)"""
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
        sys.exit(1)

def signal_handler(signum, frame):
    """Manejo de señales"""
    logger.info("🛑 Shutdown signal received")
    sys.exit(0)

def main():
    """Entrada principal"""
    logger.info("=" * 70)
    logger.info("🚂 RAILWAY DEPLOYMENT - DASHBOARD ONLY")
    logger.info("=" * 70)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    if not init_database():
        logger.error("Failed to init database")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("🌐 Starting Dashboard...")
    logger.info("=" * 70)
    run_dashboard()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
