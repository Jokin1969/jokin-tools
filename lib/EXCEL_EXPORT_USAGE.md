# Sistema de Exportación Excel Reutilizable

Módulo flexible para exportar datos a Excel con estilos profesionales, gestor de columnas y más.

## Uso Básico

```javascript
const { exportarExcel, generarNombreArchivo } = require('../../lib/excel-export');

// Definir columnas
const columnas = [
  { key: 'nombre', header: 'Nombre Completo', width: 25 },
  { key: 'email', header: 'Correo Electrónico', width: 30 },
  { key: 'fecha', header: 'Fecha de Registro', width: 18 },
];

// Datos para exportar
const datos = [
  { nombre: 'Juan García', email: 'juan@example.com', fecha: '2026-10-15' },
  { nombre: 'María López', email: 'maria@example.com', fecha: '2026-10-14' },
];

// Exportar a Excel
const buffer = await exportarExcel(datos, columnas, {
  titulo: 'Reporte de Usuarios',
  hoja: 'Usuarios',
});

// Enviar como descarga
res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
res.setHeader('Content-Disposition', `attachment; filename="${generarNombreArchivo('usuarios')}"`);
res.send(buffer);
```

## Opciones Avanzadas

```javascript
const buffer = await exportarExcel(datos, columnas, {
  titulo: 'Reporte Personalizado',
  hoja: 'Datos',
  empresa: 'Mi Empresa', // Aparece en comentario de celda
  estilos: true,         // Aplica estilos automáticos
});
```

## Columnas Predefinidas

Reutiliza columnas comunes:

```javascript
const { COLUMNAS_PREDEFINIDAS } = require('../../lib/excel-export');

// Firmas básicas
const columnas = COLUMNAS_PREDEFINIDAS.firmas;
// Result: [{key: 'nombre', header: 'Nombre', width: 25}, ...]

// Firmas completas (con IP y User-Agent)
const columnasCompletas = COLUMNAS_PREDEFINIDAS.firmas_completo;
```

## Filtrar Columnas Dinámicamente

```javascript
// Mantener solo columnas seleccionadas
const columnasSeleccionadas = ['nombre', 'email'];
const columnasFilters = columnas.filter(col => columnasSeleccionadas.includes(col.key));

const buffer = await exportarExcel(datos, columnasFilters, {...});
```

## Frontend: Gestor de Columnas

Implementar interfaz para que usuarios seleccionen columnas:

```html
<!-- Modal de selección -->
<div id="columnas-modal" hidden>
  <div id="columnas-list"></div>
  <button onclick="exportarConColumnas()">Exportar</button>
</div>
```

```javascript
// Variable global de columnas seleccionadas
let columnasSeleccionadas = ['nombre', 'email'];

// Renderizar checkboxes
const contenedor = document.getElementById('columnas-list');
COLUMNAS_DISPONIBLES.forEach(col => {
  const label = document.createElement('label');
  label.innerHTML = `
    <input type="checkbox" value="${col.key}" ${columnasSeleccionadas.includes(col.key) ? 'checked' : ''} />
    ${col.label}
  `;
  contenedor.appendChild(label);
});

// Exportar
async function exportarConColumnas() {
  const checkboxes = document.querySelectorAll('#columnas-list input:checked');
  const columnas = Array.from(checkboxes).map(cb => cb.value);

  const resp = await fetch('/api/exportar-excel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ columnas }),
  });

  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'datos.xlsx';
  link.click();
}
```

## Características Automáticas

- ✅ Encabezados con fondo azul (#1B6CB0) y texto blanco
- ✅ Bordes en todas las celdas
- ✅ Alternancia de colores de fila (gris claro)
- ✅ Encabezado congelado para scroll vertical
- ✅ Ancho de columna automático
- ✅ Nombres de archivo con timestamp: `nombre_2026-10-15_14-32-45.xlsx`

## Integrar en Nuevas Apps

1. **Backend (routes.js):**
```javascript
const { exportarExcel, generarNombreArchivo } = require('../../lib/excel-export');

router.post('/api/exportar', async (req, res) => {
  const { columnas } = req.body;
  const datos = obtenerDatos();
  
  const columnasConfig = COLUMNAS_DISPONIBLES
    .filter(col => columnas.includes(col.key));

  const buffer = await exportarExcel(datos, columnasConfig);
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.setHeader('Content-Disposition', `attachment; filename="${generarNombreArchivo('datos')}"`);
  res.send(buffer);
});
```

2. **Frontend (HTML):**
```html
<button id="btn-columnas">⚙️ Columnas</button>
<button id="btn-exportar-excel">📊 Exportar Excel</button>
```

3. **Frontend (JS):**
```javascript
const COLUMNAS_DISPONIBLES = [
  { key: 'campo1', label: 'Campo 1', checked: true },
  { key: 'campo2', label: 'Campo 2', checked: false },
];

let columnasSeleccionadas = ['campo1'];

document.getElementById('btn-columnas').onclick = () => abrirModalColumnas();
document.getElementById('btn-exportar-excel').onclick = () => exportarExcel();
```

## Customización de Estilos

Edita `lib/excel-export.js` para cambiar:
- Color de encabezado: línea `fgColor: { argb: 'FF1B6CB0' }`
- Color alterno de fila: línea `fgColor: { argb: 'FFF9F9F9' }`
- Tamaño de fuente: propiedades en `cell.font`

## Ejemplo Real

Ver implementación completa en `apps/reivindicaciones/` con gestor de columnas funcional.
