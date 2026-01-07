#!/usr/bin/env python3
"""
Minimal starter - Dashboard ONLY (for Railway debugging)
"""

import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("🚀 DASHBOARD ONLY MODE (debugging)")
logger.info("=" * 80)

# Initialize database
try:
    from database import init_database
    init_database()
    logger.info("✅ Database initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize database: {e}")

# Import and run dashboard
try:
    from dashboard import app
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"🌐 Starting Dashboard on {host}:{port}")
    logger.info(f"   Health check at: http://{host}:{port}/health")
    logger.info(f"   Dashboard at: http://{host}:{port}/")
    
    from waitress import serve
    logger.info("📦 Using Waitress server")
    serve(app, host=host, port=port, threads=4)
    
except Exception as e:
    logger.error(f"❌ Error: {e}", exc_info=True)
    sys.exit(1)
