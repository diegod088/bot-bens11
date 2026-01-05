#!/usr/bin/env python3
"""
Minimal HTTP Health Server for Railway
Runs a simple Flask server that only responds to /health endpoint
This ensures Railway's healthcheck always passes
"""

import os
import logging
from flask import Flask, jsonify
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create minimal Flask app
app = Flask(__name__)

@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'service': 'telegram-bot',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/')
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'Telegram Bot Health Server',
        'status': 'running',
        'endpoints': {
            'health': '/health'
        }
    }), 200

def run_health_server():
    """Run the health check server"""
    port = int(os.environ.get('PORT', 8000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"🏥 Starting Health Server on {host}:{port}")
    
    try:
        # Use gunicorn if available, otherwise use Flask's built-in server
        try:
            from waitress import serve
            logger.info("Using Waitress server")
            serve(app, host=host, port=port, threads=2)
        except ImportError:
            logger.info("Using Flask development server")
            app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ Health server error: {e}")
        raise

if __name__ == '__main__':
    run_health_server()
