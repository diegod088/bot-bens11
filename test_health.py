#!/usr/bin/env python3
"""
Test healthcheck endpoint locally
"""

import os
import sys
import time
import requests
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

def run_dashboard():
    """Run dashboard in background"""
    try:
        from dashboard import app
        port = int(os.environ.get('PORT', 8080))
        host = os.environ.get('HOST', '0.0.0.0')
        
        print(f"🌐 Starting dashboard on {host}:{port}")
        try:
            from waitress import serve
            serve(app, host=host, port=port, threads=4)
        except ImportError:
            app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        sys.exit(1)

def test_health():
    """Test healthcheck endpoint"""
    port = int(os.environ.get('PORT', 8080))
    url = f"http://localhost:{port}/health"
    
    # Wait for dashboard to start
    print(f"⏳ Waiting for dashboard to start...")
    for i in range(30):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print(f"✅ Healthcheck PASSED")
                print(f"   Status Code: {response.status_code}")
                print(f"   Response: {response.json()}")
                return True
        except requests.exceptions.RequestException:
            pass
        
        if (i + 1) % 5 == 0:
            print(f"   Attempt {i + 1}/30...")
        time.sleep(1)
    
    print(f"❌ Healthcheck FAILED - timeout after 30s")
    print(f"   Could not reach {url}")
    return False

if __name__ == '__main__':
    # Start dashboard in thread
    dashboard_thread = Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    
    # Test healthcheck
    success = test_health()
    sys.exit(0 if success else 1)
