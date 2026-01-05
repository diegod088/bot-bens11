# Railway Healthcheck Fix - Resumen Técnico

## Problema
Railway se queda en "Starting Healthcheck" porque:
1. El servicio no responde rápidamente al endpoint `/health`
2. El timeout (10s) era insuficiente
3. Posibles inconsistencias entre Dockerfile, Procfile y railway.json

## Soluciones Implementadas

### 1. ✅ Healthcheck Timeout en Dockerfile
**Archivo**: `Dockerfile`
**Cambio**: Aumentar timeouts para dar más tiempo al servicio
```dockerfile
# Antes:
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3

# Después:
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=5
```

**Impacto**:
- `start-period`: 60s → 90s (más tiempo antes de empezar checks)
- `timeout`: 10s → 15s (más tiempo para responder cada request)
- `retries`: 3 → 5 (más tolerancia a fallos transitorios)

### 2. ✅ Puerto ENV en railway_start.py
**Archivo**: `railway_start.py`
**Cambio**: Usar variable de entorno PORT con fallback consistente
```python
# Antes:
port = int(os.environ.get('PORT', 5000))
host = '0.0.0.0'

# Después:
port = int(os.environ.get('PORT', 8080))
host = os.environ.get('HOST', '0.0.0.0')
```

**Impacto**:
- Fallback a 8080 (más consistente con Railway defaults)
- Lee HOST desde ENV (flexible para testing)
- Garantiza que escucha en 0.0.0.0 (accesible desde cualquier interfaz)

### 3. ✅ Consistencia en railway.json
**Archivo**: `railway.json`
**Cambio**: Usar mismo comando que Procfile y Dockerfile
```json
// Antes:
"startCommand": "python start.py",

// Después:
"startCommand": "python railway_start.py",
```

**Impacto**:
- Alineación: Procfile, Dockerfile, railway.json usan `railway_start.py`
- Evita conflictos si Railway reinterpreta configuración

### 4. ✅ Endpoint /health ya existe en dashboard.py
**Archivo**: `dashboard.py` (líneas 61-67)
```python
@app.route('/health')
def health_check():
    """Health check endpoint for Railway and Docker"""
    return jsonify({
        'status': 'healthy',
        'service': 'dashboard',
        'timestamp': datetime.now().isoformat()
    }), 200
```

**Características**:
- ✅ Sin autenticación requerida
- ✅ No accede a base de datos
- ✅ Responde instantáneamente
- ✅ Status HTTP 200

## Verificación

### Ruta registrada en Flask
```
Routes en app:
  ✅ /health -> health_check
  - /login -> login
  - / -> dashboard
```

### Comportamiento esperado
```
GET http://localhost:8080/health
Response:
{
  "status": "healthy",
  "service": "dashboard",
  "timestamp": "2026-01-06T00:08:54.123456"
}
Status: 200 OK
```

## Flujo de Healthcheck en Railway

1. **Container inicia** (`docker run`)
   - ENV vars aplicadas (PORT, etc.)
   - Dockerfile's `CMD` ejecuta `python railway_start.py`

2. **railway_start.py inicia**
   - Inicializa BD
   - Lee PORT desde ENV (default 8080)
   - Inicia Flask con Waitress en 0.0.0.0:PORT

3. **Espera start-period (90s)**
   - Railway NO hace healthcheck durante este tiempo
   - Dashboard tiene tiempo para inicializar

4. **Healthcheck cada 30s**
   - Railway hace `curl http://localhost:PORT/health`
   - timeout 15s por request
   - Si falla, reintenta (máx 5 veces)

5. **Container marcado HEALTHY**
   - Si cualquier healthcheck pasa → HEALTHY
   - Tráfico se enruta correctamente

## Archivos Modificados

1. `Dockerfile` - Timeouts aumentados
2. `railway_start.py` - Puerto desde ENV
3. `railway.json` - Comando consistente

## Notas de Seguridad

- ✅ `/health` sin auth (necesario para Railway)
- ✅ Sin cambios en endpoints de autenticación
- ✅ No acceso a datos sensibles
- ✅ No modifica lógica del bot
- ✅ No nuevas dependencias

## Rollback si es necesario

Si algo falla, revertir commits:
```bash
git revert HEAD~0  # Revert railway.json
git revert HEAD~1  # Revert railway_start.py
git revert HEAD~2  # Revert Dockerfile
```

## Testing Local

Para probar localmente:
```bash
PORT=8080 HOST=0.0.0.0 python railway_start.py

# En otra terminal:
curl http://localhost:8080/health
```

Esperado:
```
{"status":"healthy","service":"dashboard","timestamp":"2026-01-06T..."}
```
