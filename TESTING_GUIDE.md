# 📱 Guía de Testing - Dashboard Mobile-First

## 🎯 Objetivo
Validar que el dashboard optimizado para móvil funciona correctamente en dispositivos reales antes de ir a producción.

---

## 🚀 Configuración de Testing

### Paso 1: Acceso Remoto
```bash
# Opción A: En red local (recomendado para testing)
1. Abre http://<tu-ip-local>:5000/login en tu teléfono
2. Debe estar en la misma red WiFi

# Opción B: Tunnel público (ngrok)
ngrok http 5000
# Usa la URL pública en tu teléfono
```

### Paso 2: Credenciales
- **Usuario**: Tu contraseña admin configurada
- **Contraseña**: La que uses en el dashboard

---

## 📋 Checklist de Testing - MÓVIL

### 1️⃣ Login Page (`/login`)

#### Diseño y Layout
- [ ] Tarjeta de login centrada en pantalla
- [ ] No requiere scroll horizontal
- [ ] Brand logo visible y centrado
- [ ] Fade-in animation al cargar (suave)

#### Inputs y Buttons
- [ ] Campo de contraseña tiene 44px+ altura (fácil de tocar)
- [ ] Placeholder visible y descriptivo
- [ ] Focus state visible (border color cambia)
- [ ] Botón tiene 44px+ altura
- [ ] Al hacer tap en botón, animación visual (scale 0.98)

#### Validación
- [ ] Muestra error si contraseña está vacía
- [ ] Error tiene animación shake
- [ ] Error es legible (color rojo sobre fondo claro)

---

### 2️⃣ Dashboard (`/`)

#### Navegación
- [ ] Hamburger menu (☰) visible en top-right
- [ ] Clicking en hamburger abre menú lateral
- [ ] Menú tiene opciones: Dashboard, Usuarios, Analytics, Settings
- [ ] Clicking fuera del menú lo cierra
- [ ] Las transiciones son smooth (no saltos)

#### Stat Cards
- [ ] Tarjetas de estadísticas ocupan todo el ancho (menos padding)
- [ ] Aparecen con animación fade-in progresiva
- [ ] Números visibles y legibles
- [ ] No hay overlap con otros elementos

#### Activity & Broadcast
- [ ] Sección de actividad NO está visible en móvil (debe estar oculta)
- [ ] Sección de broadcast visible y funcional
- [ ] Inputs de broadcast tienen 44px+ altura
- [ ] Botón "Enviar" visible y tapeable

#### Responsividad
- [ ] En landscape, layout se ajusta correctamente
- [ ] Contenido no se corta
- [ ] Texto sigue siendo legible

---

### 3️⃣ Usuarios (`/users`)

#### Vista de Tarjetas (Mobile)
- [ ] **Layout**: Tarjetas en single column (no multiple columns)
- [ ] Cada tarjeta muestra:
  - ID de usuario
  - Nombre/Username
  - Badge (Premium/Gratis) con color diferente
  - Stats: "Descargas: XX", "Desde: fecha"
  - Botón "Ver" (full-width)
  
#### Selección Múltiple
- [ ] Checkbox visible en cada tarjeta
- [ ] Clicking checkbox marca/desmarca el usuario
- [ ] Cuando hay items seleccionados:
  - Aparece banner en top con "X seleccionados"
  - Botón "Acción en Masa" en el banner
  - Banner puede cerrarse

#### Búsqueda y Filtros
- [ ] Search box visible (full-width)
- [ ] Filtro de estado (Premium/Gratis) como dropdown
- [ ] Botón de exportar visible
- [ ] Todos apilados verticalmente (no lado a lado)

#### Paginación
- [ ] Números de página: 1, 2, 3, etc.
- [ ] Botones ← y → para navegación
- [ ] Centered en la pantalla
- [ ] Fácil de tocar (44px+ tap area)

---

### 4️⃣ Detalle de Usuario (`/users/<id>`)

#### Premium Status (Top)
- [ ] Tarjeta prominente con status Premium/Gratis
- [ ] Color diferente según estado (Gold = Premium, Gray = Free)
- [ ] Si Premium: muestra fecha de vencimiento
- [ ] Avatar visible (letras iniciales)
- [ ] Nombre y username visibles

#### Stats Grid
- [ ] Grid de 1 columna en móvil
- [ ] Mostrar:
  - Total Descargas
  - Última Actividad
  - Fecha de Registro
  - Estado General

#### Accordion Sections
**Gestión Premium** (abierto por defecto):
- [ ] Sección expandida por defecto
- [ ] Input para "Añadir días" visible
- [ ] Botón "Añadir Premium" (full-width, 44px+)
- [ ] Si Premium: botón "Remover" también visible
- [ ] Clicking en header minimiza la sección

**Zona de Peligro** (cerrado por defecto):
- [ ] Sección colapsada
- [ ] Click en header la expande (con animación)
- [ ] Aviso en color rojo visible
- [ ] Botones: "Resetear Estadísticas" y "Eliminar Usuario"
- [ ] Ambos botones full-width

#### Interactividad
- [ ] Clicking "Añadir Premium" muestra toast de confirmación
- [ ] Página se recarga con éxito
- [ ] Errores se muestran en toast rojo
- [ ] Confirmaciones dobles para acciones peligrosas (Eliminar)

---

## 📋 Checklist de Testing - DESKTOP (Validación Rápida)

### Punto de Quiebre: 768px+

#### Base Layout
- [ ] Menú horizontal visible (NOT hamburger)
- [ ] Main content centrado con max-width 1200px
- [ ] Padding aumentado a 2rem

#### Dashboard
- [ ] Stat cards en grid (2 o 4 columnas)
- [ ] Activity section visible
- [ ] Broadcast inputs lado a lado

#### Usuarios
- [ ] **Tabla tradicional visible** (NO tarjetas)
- [ ] Columnas: ID, Nombre, Status, Días, Descargas, Acciones
- [ ] Toolbar en grid horizontal (search, filters, export)
- [ ] Checkboxes NO visibles en desktop
- [ ] Bulk actions banner NO visible

#### Usuario Detail
- [ ] Ambas secciones lado a lado (grid 2 cols)
- [ ] NO son accordions (siempre visibles)
- [ ] Botones no son full-width
- [ ] Stats en grid 2 columnas

---

## 🔍 Casos de Uso Críticos

### Caso 1: Agregar Premium a Usuario
1. Ve a `/users`
2. Clickea en un usuario
3. En móvil: sección "Gestión Premium" está expandida
4. Ingresa días (ej: 30)
5. Click en "Añadir Premium"
6. Toast verde de confirmación
7. Página se recarga
8. Status cambia a "Premium ✓"

**En Desktop**: Mismo flujo, pero sección visible sin accordion

### Caso 2: Búsqueda de Usuarios
1. Ve a `/users`
2. En search box, escribe nombre
3. Lista de tarjetas se filtra en tiempo real
4. Resultados se muestran en single column (móvil)
5. En desktop: tabla se filtra

### Caso 3: Selección Múltiple (Solo Móvil)
1. Ve a `/users`
2. Marca 2-3 checkboxes
3. Banner "2 seleccionados" aparece en top
4. Click en "Acción en Masa" (si está disponible)
5. Operación se ejecuta para todos

### Caso 4: Responsividad Landscape
1. Abre en iPhone portrait
2. Gira a landscape (horizontal)
3. Layout se ajusta (puede expandirse a 2 cols si hay espacio)
4. Todo sigue siendo legible
5. Sin scroll horizontal

---

## ⚠️ Red Flags - Que NO debería pasar

### Problemas de Layout
- ❌ Elementos cortados o overflow horizontal
- ❌ Texto demasiado pequeño (< 14px)
- ❌ Botones < 44px de altura
- ❌ Overlap de elementos
- ❌ Hamburger menu visible en desktop

### Problemas de Interacción
- ❌ Botones difíciles de tocar (< 44px)
- ❌ Menú no se cierra al hacer click en link
- ❌ Accordion no abre/cierra
- ❌ Checkbox no se selecciona
- ❌ Inputs sin focus visual claro

### Problemas de Performance
- ❌ Animaciones laggy/stuttering
- ❌ Scroll lento o scroll horizontal involuntario
- ❌ Página tarda > 3s en cargar
- ❌ Toast notifications se superponen
- ❌ Página se congela al hacer búsqueda

---

## 📊 Métricas a Monitorear

```
LCP (Largest Contentful Paint): < 2.5s
FID (First Input Delay): < 100ms
CLS (Cumulative Layout Shift): < 0.1
TTI (Time to Interactive): < 3.5s
```

### Herramientas
- Chrome DevTools → Lighthouse
- PageSpeed Insights
- WebPageTest

---

## 🐛 Si Encuentras un Bug

1. **Documenta**: Screenshot + navegador + resolución
2. **Reproduce**: En Chrome DevTools (Responsive Design Mode)
3. **Aísla**: ¿Afecta solo móvil? ¿Solo desktop? ¿Ambos?
4. **Inspecciona**: F12 → Console → ¿Hay errores?
5. **Reporta**: Con pasos para reproducir

### Formato de Reporte
```
🐛 BUG: [Título breve]

Dispositivo: [iPhone 12 / Samsung S21 / Desktop]
Navegador: [Safari / Chrome / Firefox]
URL: [Página donde ocurre]
Pasos:
1. ...
2. ...
3. ...

Resultado esperado: ...
Resultado actual: ...

Screenshot: [adjuntar]
```

---

## ✅ Checklist Final Antes de Deploy

- [ ] Todos los casos de uso funcionan en móvil
- [ ] Todos los casos de uso funcionan en desktop
- [ ] Sin red flags de problemas
- [ ] Animations smooth (60fps)
- [ ] Touch targets tapeable
- [ ] Texto legible
- [ ] Responsive en landscape
- [ ] Sin errores en console (F12)
- [ ] Toast notifications visible
- [ ] Links navegan correctamente
- [ ] Formularios submiteable
- [ ] Validaciones funcionan

---

## 🎉 Conclusión

Si todos los checkboxes están marcados ✅, **¡el dashboard está listo para producción!**

### Siguientes Pasos
1. Deploy a producción
2. Monitorear en primeras 24h
3. Recopilar feedback de usuarios
4. Iterar basado en feedback real

---

**Testing completado**: Fecha: ___________
**Testeador**: ___________
**Status**: ⭕ Pendiente | 🟡 En Progreso | ✅ Completado
