#!/usr/bin/env python3
"""
Generador de Variables de Entorno para Railway
Genera las claves de seguridad necesarias
"""

import secrets
from cryptography.fernet import Fernet

print("=" * 70)
print("🔐 GENERADOR DE CLAVES DE SEGURIDAD PARA RAILWAY")
print("=" * 70)
print()

# Generar ENCRYPTION_KEY
encryption_key = Fernet.generate_key().decode()
print("📝 ENCRYPTION_KEY:")
print(f"   {encryption_key}")
print()

# Generar DASHBOARD_SECRET_KEY
dashboard_key = secrets.token_hex(32)
print("📝 DASHBOARD_SECRET_KEY:")
print(f"   {dashboard_key}")
print()

# Generar un ADMIN_TOKEN sugerido
admin_token = secrets.token_urlsafe(16)
print("📝 ADMIN_TOKEN (sugerido - puedes cambiarlo):")
print(f"   {admin_token}")
print()

print("=" * 70)
print("✅ CLAVES GENERADAS EXITOSAMENTE")
print("=" * 70)
print()
print("📋 COPIA Y PEGA EN RAILWAY:")
print()
print(f"ENCRYPTION_KEY={encryption_key}")
print(f"DASHBOARD_SECRET_KEY={dashboard_key}")
print(f"ADMIN_TOKEN={admin_token}")
print()
print("⚠️  IMPORTANTE:")
print("   - Estas claves son secretas, no las compartas")
print("   - Guárdalas en un lugar seguro")
print("   - Configúralas en Railway en la sección Variables")
print()
print("📚 Para más información, consulta: RAILWAY_VARIABLES.md")
print()
