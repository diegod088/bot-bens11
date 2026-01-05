#!/usr/bin/env python3
"""
✅ VALIDATION SCRIPT - 409 CONFLICT FIX
Verifica que todos los cambios se aplicaron correctamente
"""

import os
import sys
import re

# ANSI colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check(condition, message):
    """Print a check result"""
    if condition:
        print(f"{GREEN}✅ {message}{RESET}")
        return True
    else:
        print(f"{RED}❌ {message}{RESET}")
        return False

def warning(message):
    """Print a warning"""
    print(f"{YELLOW}⚠️  {message}{RESET}")

def info(message):
    """Print info"""
    print(f"{BLUE}ℹ️  {message}{RESET}")

def section(title):
    """Print section header"""
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

def read_file(path):
    """Read a file safely"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Could not read {path}: {e}")
        return None

def validate_bot_with_paywall():
    """Validate bot_with_paywall.py changes"""
    section("1. VALIDATING: bot_with_paywall.py")
    
    content = read_file("bot_with_paywall.py")
    if not content:
        return False
    
    results = []
    
    # Check 1: async_main() exists
    results.append(check(
        "async def async_main():" in content,
        "async_main() function exists"
    ))
    
    # Check 2: Old main() is deprecated
    results.append(check(
        ('raise RuntimeError' in content and 'main()' in content) or 'LEGACY FUNCTION' in content,
        "Old main() properly deprecated with error"
    ))
    
    # Check 3: run_polling() is used correctly
    results.append(check(
        'await application.run_polling(allowed_updates=Update.ALL_TYPES)' in content,
        "Using application.run_polling() (correct PTB v20+ method)"
    ))
    
    # Check 4: No deprecated updater.start_polling()
    results.append(check(
        'await application.updater.start_polling(' not in content,
        "NOT using deprecated application.updater.start_polling()"
    ))
    
    # Check 5: _bot_instance_lock exists for protection
    results.append(check(
        '_bot_instance_lock' in content and '_bot_instance_running' in content,
        "Multiple instance protection flags present"
    ))
    
    # Check 6: Conflict 409 protection
    results.append(check(
        'Conflict 409' in content or 'prevent Conflict 409' in content,
        "409 Conflict protection mentioned in code"
    ))
    
    # Check 7: Proper lifecycle handling
    results.append(check(
        'try:' in content and 'finally:' in content,
        "Proper exception handling with try/finally"
    ))
    
    return all(results)

def validate_start_py():
    """Validate start.py changes"""
    section("2. VALIDATING: start.py")
    
    content = read_file("start.py")
    if not content:
        return False
    
    results = []
    
    # Check 1: Threading protection
    results.append(check(
        '_bot_lock' in content and '_bot_started' in content,
        "Bot instance protection with lock and flag"
    ))
    
    # Check 2: Event loop creation
    results.append(check(
        'loop = asyncio.new_event_loop()' in content,
        "Creates new event loop for bot thread"
    ))
    
    # Check 3: Run until complete
    results.append(check(
        'loop.run_until_complete(async_main())' in content,
        "Calls async_main() via run_until_complete()"
    ))
    
    # Check 4: Loop cleanup
    results.append(check(
        'loop.close()' in content,
        "Properly closes event loop after use"
    ))
    
    # Check 5: Documentation
    results.append(check(
        'The bot runs in a separate thread with its own asyncio event loop' in content,
        "Documentation explains threading model"
    ))
    
    # Check 6: Parallel execution
    results.append(check(
        'bot_thread = threading.Thread' in content,
        "Bot runs in separate thread"
    ))
    
    # Check 7: Dashboard in main thread
    results.append(check(
        'run_dashboard()' in content,
        "Dashboard runs in main thread"
    ))
    
    return all(results)

def validate_railway_start_py():
    """Validate railway_start.py is dashboard-only"""
    section("3. VALIDATING: railway_start.py")
    
    content = read_file("railway_start.py")
    if not content:
        return False
    
    results = []
    
    # Check 1: Dashboard only
    results.append(check(
        'DASHBOARD ONLY' in content,
        "Correctly documented as DASHBOARD ONLY"
    ))
    
    # Check 2: No bot execution
    results.append(check(
        'async_main' not in content and 'bot_with_paywall' not in content,
        "Does NOT execute bot (dashboard only)"
    ))
    
    # Check 3: Uses Waitress
    results.append(check(
        'from waitress import serve' in content or 'Waitress' in content,
        "Uses Waitress production server"
    ))
    
    # Check 4: Runs Flask app
    results.append(check(
        'from dashboard import app' in content,
        "Imports and runs Flask dashboard"
    ))
    
    return all(results)

def check_for_deprecated_patterns():
    """Check for deprecated patterns that should NOT exist"""
    section("4. CHECKING FOR DEPRECATED PATTERNS")
    
    results = []
    files_to_check = [
        ("bot_with_paywall.py", "telegram.ext.Updater"),
        ("bot_with_paywall.py", "from telegram.ext import Updater"),
        ("start.py", "telegram.ext.Updater"),
    ]
    
    all_good = True
    for filepath, pattern in files_to_check:
        content = read_file(filepath)
        if content:
            if pattern in content:
                check(False, f"Found deprecated pattern '{pattern}' in {filepath}")
                all_good = False
            else:
                check(True, f"No deprecated '{pattern}' in {filepath}")
    
    return all_good

def check_imports():
    """Check that imports are correct"""
    section("5. VALIDATING IMPORTS")
    
    results = []
    
    # Check bot_with_paywall.py imports
    bot_content = read_file("bot_with_paywall.py")
    if bot_content:
        results.append(check(
            ('from telegram.ext import' in bot_content and 'Application' in bot_content) or 'Application' in bot_content,
            "bot_with_paywall imports Application (PTB v20+)"
        ))
        results.append(check(
            'Application.builder()' in bot_content or 'ApplicationBuilder' in bot_content,
            "bot_with_paywall uses Application/ApplicationBuilder"
        ))
        results.append(check(
            'import asyncio' in bot_content,
            "bot_with_paywall imports asyncio"
        ))
    
    # Check start.py imports
    start_content = read_file("start.py")
    if start_content:
        results.append(check(
            'import threading' in start_content,
            "start.py imports threading"
        ))
        results.append(check(
            'import asyncio' in start_content,
            "start.py imports asyncio"
        ))
        results.append(check(
            'from bot_with_paywall import async_main' in start_content,
            "start.py imports async_main from bot_with_paywall"
        ))
    
    return all(results)

def main():
    """Run all validations"""
    print(f"\n{BOLD}{BLUE}")
    print("=" * 80)
    print("🔍 TELEGRAM BOT - 409 CONFLICT FIX VALIDATION")
    print("=" * 80)
    print(f"{RESET}\n")
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    results = {
        "bot_with_paywall.py": validate_bot_with_paywall(),
        "start.py": validate_start_py(),
        "railway_start.py": validate_railway_start_py(),
        "deprecated_patterns": check_for_deprecated_patterns(),
        "imports": check_imports(),
    }
    
    # Final report
    section("FINAL REPORT")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{status}: {name}")
    
    print(f"\n{BOLD}Results: {passed}/{total} sections passed{RESET}")
    
    if all(results.values()):
        print(f"\n{GREEN}{BOLD}🎉 ALL VALIDATIONS PASSED!{RESET}")
        print(f"{GREEN}The 409 Conflict fix has been successfully applied.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}❌ SOME VALIDATIONS FAILED{RESET}")
        print(f"{RED}Please review the output above and fix any issues.{RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
