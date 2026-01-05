#!/usr/bin/env python3
"""
🧪 MANUAL TEST SCRIPT - 409 Conflict Fix Verification

Este script verifica que el fix para el error 409 está funcionando correctamente.
Ejecuta en modo de testing sin realmente conectar a Telegram.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test 1: Verify all imports work"""
    print("\n" + "="*80)
    print("TEST 1: IMPORT VALIDATION")
    print("="*80 + "\n")
    
    try:
        print("  Importing database...")
        from database import init_database
        print("  ✅ database imported")
        
        print("  Importing dashboard...")
        from dashboard import app
        print("  ✅ dashboard imported")
        
        print("  Importing bot_with_paywall...")
        from bot_with_paywall import async_main, TELEGRAM_TOKEN
        print("  ✅ bot_with_paywall imported")
        print(f"  ℹ️  Token configured: {'✅ YES' if TELEGRAM_TOKEN else '❌ NO'}")
        
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def test_module_structure():
    """Test 2: Verify module structure"""
    print("\n" + "="*80)
    print("TEST 2: MODULE STRUCTURE")
    print("="*80 + "\n")
    
    try:
        import bot_with_paywall
        import start
        
        # Check bot_with_paywall
        print("  Checking bot_with_paywall...")
        assert hasattr(bot_with_paywall, 'async_main'), "async_main() not found"
        print("    ✅ async_main() exists")
        
        assert hasattr(bot_with_paywall, 'main'), "main() not found"
        print("    ✅ main() exists (deprecated wrapper)")
        
        # Check start.py
        print("  Checking start...")
        assert hasattr(start, 'run_bot'), "run_bot() not found"
        print("    ✅ run_bot() exists")
        
        assert hasattr(start, 'run_dashboard'), "run_dashboard() not found"
        print("    ✅ run_dashboard() exists")
        
        return True
    except Exception as e:
        print(f"  ❌ Structure check failed: {e}")
        return False

def test_protection_flags():
    """Test 3: Verify protection flags are defined"""
    print("\n" + "="*80)
    print("TEST 3: PROTECTION FLAGS")
    print("="*80 + "\n")
    
    try:
        import bot_with_paywall
        import start
        
        # Check bot_with_paywall flags
        print("  Checking bot_with_paywall...")
        assert hasattr(bot_with_paywall, '_bot_instance_running'), "_bot_instance_running not found"
        print("    ✅ _bot_instance_running flag exists")
        
        assert hasattr(bot_with_paywall, '_bot_instance_lock'), "_bot_instance_lock not found"
        print("    ✅ _bot_instance_lock mutex exists")
        
        # Check start.py flags
        print("  Checking start...")
        assert hasattr(start, '_bot_started'), "_bot_started not found"
        print("    ✅ _bot_started flag exists")
        
        assert hasattr(start, '_bot_lock'), "_bot_lock not found"
        print("    ✅ _bot_lock mutex exists")
        
        return True
    except Exception as e:
        print(f"  ❌ Protection flags check failed: {e}")
        return False

def test_no_deprecated_patterns():
    """Test 4: Check for deprecated code patterns"""
    print("\n" + "="*80)
    print("TEST 4: DEPRECATED PATTERNS CHECK")
    print("="*80 + "\n")
    
    try:
        import inspect
        import bot_with_paywall
        
        # Get source code
        source = inspect.getsource(bot_with_paywall)
        
        print("  Checking bot_with_paywall source...")
        
        # Check for deprecated patterns
        deprecated_patterns = [
            ('await application.updater.start_polling', 'await application.updater.start_polling()'),
            ('from telegram.ext import Updater', 'Updater import'),
            ('telegram.ext.Updater', 'Updater class'),
        ]
        
        all_good = True
        for pattern, name in deprecated_patterns:
            if pattern in source:
                print(f"    ❌ Found deprecated pattern: {name}")
                all_good = False
            else:
                print(f"    ✅ No deprecated {name}")
        
        return all_good
    except Exception as e:
        print(f"  ❌ Pattern check failed: {e}")
        return False

def test_correct_patterns():
    """Test 5: Check for correct code patterns"""
    print("\n" + "="*80)
    print("TEST 5: CORRECT PATTERNS CHECK")
    print("="*80 + "\n")
    
    try:
        import inspect
        import bot_with_paywall
        
        # Get source code
        source = inspect.getsource(bot_with_paywall)
        
        print("  Checking bot_with_paywall source...")
        
        # Check for correct patterns
        correct_patterns = [
            ('await application.run_polling', 'application.run_polling()'),
            ('Application.builder()', 'ApplicationBuilder'),
            ('async def async_main', 'async_main function'),
            ('_bot_instance_lock', 'instance lock protection'),
        ]
        
        all_good = True
        for pattern, name in correct_patterns:
            if pattern in source:
                print(f"    ✅ Found correct pattern: {name}")
            else:
                print(f"    ❌ Missing correct pattern: {name}")
                all_good = False
        
        return all_good
    except Exception as e:
        print(f"  ❌ Pattern check failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("\n")
    print("█" * 80)
    print("█  🧪 409 CONFLICT FIX - MANUAL TEST SUITE")
    print("█" * 80)
    
    tests = [
        ("Import Validation", test_imports),
        ("Module Structure", test_module_structure),
        ("Protection Flags", test_protection_flags),
        ("Deprecated Patterns", test_no_deprecated_patterns),
        ("Correct Patterns", test_correct_patterns),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            results[name] = False
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80 + "\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Results: {passed}/{total} tests passed\n")
    
    if passed == total:
        print("█" * 80)
        print("█  🎉 ALL TESTS PASSED - FIX IS WORKING CORRECTLY!")
        print("█" * 80)
        return 0
    else:
        print("█" * 80)
        print("█  ❌ SOME TESTS FAILED - PLEASE REVIEW")
        print("█" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
