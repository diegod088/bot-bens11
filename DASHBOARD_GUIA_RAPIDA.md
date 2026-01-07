# 🚀 GUÍA RÁPIDA - NUEVAS MEJORAS DEL DASHBOARD

**Última actualización:** 7 de Enero de 2026  
**Estado:** ✅ En línea y funcionando

---

## 📊 ACCESO RÁPIDO

### Dashboard Principal con Gráficos
```
URL: http://localhost:5000/
```

**Lo que verás:**
- 4 tarjetas grandes de métricas
- Gráfico de ingresos (línea)
- Gráfico de usuarios nuevos (barras)
- Gráfico de distribución (pie)
- Gráfico de descargas por tipo (pie)
- Actualización automática cada 5 minutos

### Gestión de Usuarios Avanzada
```
URL: http://localhost:5000/users
```

**Nuevas características:**
- Búsqueda en tiempo real
- Filtros por estado (Free, Premium, Premium Expirado)
- Ordenamiento múltiple (Recientes, Descargas, Activos, etc)
- Paginación flexible (10, 20, 50, 100 por página)
- Selección múltiple de usuarios

---

## 📈 GRÁFICOS DISPONIBLES

### 1. Gráfico de Ingresos
```
Endpoint: /api/charts/revenue
Tipo: Línea
Período: Últimos 7 días
Actualización: Automática cada 5 min
Datos: Ingresos diarios estimados
```

**Ejemplo de respuesta:**
```json
{
  "labels": ["2026-01-01", "2026-01-02", ..., "2026-01-07"],
  "data": [0, 0, 0, 0, 0, 0, 0]
}
```

### 2. Gráfico de Usuarios Nuevos
```
Endpoint: /api/charts/users
Tipo: Barras
Período: Últimos 7 días
Actualización: Automática cada 5 min
Datos: Cantidad de usuarios nuevos por día
```

**Ejemplo de respuesta:**
```json
{
  "labels": ["2026-01-01", "2026-01-02", ..., "2026-01-07"],
  "data": [8, 0, 0, 13, 7, 0, 0]
}
```

### 3. Gráfico de Distribución
```
Endpoint: /api/charts/distribution
Tipo: Doughnut (Pastel)
Datos: Free vs Premium
Actualización: Automática cada 5 min
Colores: Azul (Gratuitos), Verde (Premium)
```

**Ejemplo de respuesta:**
```json
{
  "labels": ["Gratuitos", "Premium"],
  "data": [81, 5],
  "colors": ["#3b82f6", "#10b981"]
}
```

### 4. Gráfico de Descargas
```
Endpoint: /api/charts/downloads
Tipo: Doughnut (Pastel)
Datos: Videos, Fotos, Música, APK
Actualización: Automática cada 5 min
Colores: Rojo, Ámbar, Púrpura, Cian
```

**Ejemplo de respuesta:**
```json
{
  "labels": ["Videos", "Fotos", "Música", "APK"],
  "data": [5, 0, 0, 0],
  "colors": ["#ef4444", "#f59e0b", "#8b5cf6", "#06b6d4"]
}
```

---

## 🔍 CÓMO USAR LOS FILTROS

### Filtro de Estado
```
Opciones:
- Todos los usuarios (86 total)
- ⭐ Premium activo (5 usuarios)
- ⭐ Premium expirado (0 usuarios)
- Gratuito (81 usuarios)
```

### Filtro de Ordenamiento
```
Opciones:
- 📅 Más recientes (creados recientemente)
- 📅 Más antiguos (creados hace tiempo)
- 📥 Más descargas (usuarios con más descargas)
- ⏱️ Más activos (actualizados recientemente)
- ⭐ Próximo vencimiento (premium próximo a expirar)
```

### Registros por Página
```
Opciones:
- 10 registros por página
- 20 registros por página (default)
- 50 registros por página
- 100 registros por página
```

### Búsqueda
```
Busca por:
- ID del usuario (ej: 123456789)
- Nombre (ej: Juan)
- Username (ej: @juanperez)

Características:
- En tiempo real (mientras escribes)
- Presiona Enter para buscar manual
- Combina con otros filtros
```

---

## 👥 GESTIÓN MASIVA DE USUARIOS

### Seleccionar Usuarios (Mobile)
1. Abre la página de usuarios
2. Aparecerán checkboxes a la izquierda
3. Selecciona los usuarios que quieras

### Banner de Acciones
Cuando selecciones usuarios, aparecerá un banner con:
```
┌─────────────────────────────────┐
│ X seleccionados                 │
│ [Cancelar] [Añadir Premium]     │
└─────────────────────────────────┘
```

### Acciones Disponibles
- ✅ Añadir Premium a Seleccionados
  - Ingresa cuántos días quieres
  - Se aplica a todos los seleccionados

---

## 📊 DATOS EN TIEMPO REAL

### Estadísticas Actuales
```
Total usuarios:     86
Premium activos:    5
Usuarios gratuitos: 81
Usuarios activos hoy: 1
Ingresos totales:   1,500 ⭐
Descargas totales:  5
Premium expirados:  0
```

### Actualización de Datos
```
Dashboard: Cada 30 segundos
Gráficos:  Cada 5 minutos
Usuarios:  Bajo demanda (al filtrar/buscar)
```

---

## 🛠️ ENDPOINTS API

### Para Desarrolladores

```bash
# Estadísticas generales
curl http://localhost:5000/api/stats

# Gráfico de ingresos
curl http://localhost:5000/api/charts/revenue

# Gráfico de usuarios
curl http://localhost:5000/api/charts/users

# Gráfico de distribución
curl http://localhost:5000/api/charts/distribution

# Gráfico de descargas
curl http://localhost:5000/api/charts/downloads

# Lista de usuarios con filtros
curl "http://localhost:5000/api/users?page=1&per_page=20&status=premium"

# Exportar a CSV
curl "http://localhost:5000/api/export/users?format=csv" -o usuarios.csv
```

---

## 💡 TIPS Y TRUCOS

### En el Dashboard
```
✓ Los gráficos se actualizan automáticamente
✓ Puedes hacer click en los gráficos (si lo requieres)
✓ Visibles en móvil, tablet y desktop
✓ Datos siempre sincronizados con la BD
```

### En Gestión de Usuarios
```
✓ Combina filtros para resultados más precisos
✓ La búsqueda es en tiempo real
✓ Puedes cambiar la página mientras buscas
✓ Selecciona múltiples usuarios para acciones en lote
✓ Exporta a CSV sin perder filtros
```

### Performance
```
✓ Paginación evita cargar todos los usuarios
✓ Búsqueda en tiempo real sin demoras
✓ Gráficos se cargan de forma asincrónica
✓ Base de datos optimizada para consultas
```

---

## 🎯 CASOS DE USO COMUNES

### Caso 1: Encontrar usuarios premium próximos a expirar
```
1. Ir a /users
2. Filtro Estado → "⭐ Premium activo"
3. Filtro Ordenar → "⭐ Próximo vencimiento"
4. Ver primeros usuarios en la lista
```

### Caso 2: Ver todos los usuarios que descargaron videos
```
1. Ir a /users
2. Filtro Ordenar → "📥 Más descargas"
3. Los usuarios con más descargas aparecen primero
```

### Caso 3: Agregar premium a 10 usuarios gratuitos
```
1. Ir a /users
2. Filtro Estado → "Gratuito"
3. Seleccionar 10 usuarios
4. Click "Añadir Premium a Seleccionados"
5. Ingresar días (ej: 30)
6. Listo! ✅
```

### Caso 4: Analizar tendencias de ingresos
```
1. Ir a / (Dashboard)
2. Ver gráfico de ingresos
3. Observar tendencias últimos 7 días
4. Correlacionar con eventos
```

### Caso 5: Buscar un usuario específico
```
1. Ir a /users
2. En búsqueda escribir: nombre, @usuario o ID
3. Resultados en tiempo real
4. Click "Ver Detalle" para información completa
```

---

## 🔔 NOTIFICACIONES Y ALERTAS

Pronto se agregará:
- ⏳ Alertas de premium próximo a expirar
- ⏳ Notificaciones de usuarios inactivos
- ⏳ Cambios anormales en descargas
- ⏳ Límites de cuota por usuario

---

## 📞 SOPORTE

### Si algo no funciona:

**Los gráficos no cargan**
```
1. Verifica conexión a internet
2. Recarga la página (F5)
3. Abre DevTools (F12) y revisa la consola
4. Verifica que /api/stats responde
```

**La búsqueda es lenta**
```
1. Usa términos más específicos
2. Combina con filtros
3. Cambia "Por página" a un número menor
4. Contacta al admin si persiste
```

**Los filtros no funcionan**
```
1. Limpiar cache (Ctrl+Shift+Delete)
2. Cerrar y abrir la página
3. Verificar que estés en la URL correcta
4. Revisar consola del navegador
```

---

## 📈 MÉTRICAS A OBSERVAR

### Diarias
- Usuarios nuevos registrados
- Descargas totales
- Usuarios activos

### Semanales
- Crecimiento de usuarios
- Tendencia de ingresos
- Proporción free/premium

### Mensuales
- Retención de usuarios
- Churn rate
- ARR (Annual Recurring Revenue)

---

## 🎉 ¡LISTO PARA USAR!

Todo está configurado y funcionando. 

**Accede ahora:**
- Dashboard: http://localhost:5000/
- Usuarios: http://localhost:5000/users

**¡Disfruta del dashboard mejorado! 🚀**

---

*Generado automáticamente - 7 de Enero de 2026*
