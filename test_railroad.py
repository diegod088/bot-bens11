#!/usr/bin/env python3
"""
Test Railway Configuration
"""
import os
import sys

print("=" * 80)
print("RAILWAY CONFIGURATION TEST")
print("=" * 80)
print()

# Check environment variables
print("1️⃣ ENVIRONMENT VARIABLES:")
print(f"   PORT: {os.environ.get('PORT', 'NOT SET (default: 5000)')}")
print(f"   HOST: {os.environ.get('HOST', 'NOT SET (default: 0.0.0.0)')}")
print(f"   TELEGRAM_TOKEN: {'SET' if os.environ.get('TELEGRAM_TOKEN') else 'NOT SET'}")
print(f"   ENCRYPTION_KEY: {'SET' if os.environ.get('ENCRYPTION_KEY') else 'NOT SET'}")
print()

# Check if files exist
print("2️⃣ FILES CHECK:")
files = ['start.py', 'dashboard.py', 'bot_with_paywall.py', 'requirements.txt']
for f in files:
    exists = "✅" if os.path.exists(f) else "❌"
    print(f"   {exists} {f}")
print()

# Check imports
print("3️⃣ IMPORTS CHECK:")
try:
    from dotenv import load_dotenv
    print("   ✅ dotenv")
except:
    print("   ❌ dotenv")

try:
    import flask
    print("   ✅ flask")
except:
    print("   ❌ flask")

try:
    import waitress
    print("   ✅ waitress")
except:
    print("   ❌ waitress")

try:
    from telethon import TelegramClient
    print("   ✅ telethon")
except:
    print("   ❌ telethon")

try:
    from telegram.ext import Application
    print("   ✅ python-telegram-bot")
except:
    print("   ❌ python-telegram-bot")

print()
print("=" * 80)
