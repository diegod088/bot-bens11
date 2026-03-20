#!/usr/bin/env python3
"""
Test script para verificar que el bot funciona correctamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_database, create_user, add_user, update_user_info, 
    set_user_language, get_user
)
from messages import get_user_language

def test_database_functions():
    """Probar las funciones de la base de datos"""
    print("🧪 Iniciando pruebas de base de datos...")
    
    # Inicializar base de datos
    init_database()
    print("✅ Base de datos inicializada")
    
    # Test 1: Crear usuario con create_user
    print("\n📝 Test 1: create_user() con language")
    try:
        result = create_user(12345, first_name="Test User", username="testuser", language="es")
        print(f"✅ create_user() funcionó: {result}")
    except Exception as e:
        print(f"❌ Error en create_user(): {e}")
        return False
    
    # Test 2: Crear usuario con add_user
    print("\n📝 Test 2: add_user() con language y referred_by")
    try:
        add_user(12346, language="en", referred_by=12345)
        print("✅ add_user() funcionó")
    except Exception as e:
        print(f"❌ Error en add_user(): {e}")
        return False
    
    # Test 3: Actualizar info de usuario
    print("\n📝 Test 3: update_user_info()")
    try:
        result = update_user_info(12345, first_name="Updated Name", username="updateduser")
        print(f"✅ update_user_info() funcionó: {result}")
    except Exception as e:
        print(f"❌ Error en update_user_info(): {e}")
        return False
    
    # Test 4: Obtener usuario
    print("\n📝 Test 4: get_user()")
    try:
        user = get_user(12345)
        if user:
            print(f"✅ get_user() funcionó: {user.get('first_name', 'N/A')}")
        else:
            print("❌ get_user() no encontró usuario")
    except Exception as e:
        print(f"❌ Error en get_user(): {e}")
        return False
    
    # Test 5: Establecer lenguaje
    print("\n📝 Test 5: set_user_language()")
    try:
        set_user_language(12345, "pt")
        print("✅ set_user_language() funcionó")
    except Exception as e:
        print(f"❌ Error en set_user_language(): {e}")
        return False
    
    # Test 6: Obtener lenguaje
    print("\n📝 Test 6: get_user_language()")
    try:
        lang = get_user_language({"user_id": 12345, "language_code": "pt"})
        print(f"✅ get_user_language() funcionó: {lang}")
    except Exception as e:
        print(f"❌ Error en get_user_language(): {e}")
        return False
    
    print("\n🎉 Todas las pruebas de base de datos pasaron!")
    return True

def test_bot_imports():
    """Probar que los imports del bot funcionan"""
    print("\n🧪 Probando imports del bot...")
    
    try:
        from bot_with_paywall import start_command
        print("✅ Import de start_command funcionó")
        return True
    except Exception as e:
        print(f"❌ Error importando start_command: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando tests del bot...")
    
    # Test database functions
    if not test_database_functions():
        print("❌ Las pruebas de base de datos fallaron")
        sys.exit(1)
    
    # Test bot imports
    if not test_bot_imports():
        print("❌ Las pruebas de imports fallaron")
        sys.exit(1)
    
    print("\n✅ Todos los tests pasaron correctamente!")
    print("🎯 El bot debería funcionar sin errores de TypeError")
    print("📝 Los errores de 'unexpected keyword argument' están resueltos")
