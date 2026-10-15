let reivindicacionesActual = [];
let reivindicacionEnEdicion = null;

// ========== Inicialización ==========
document.addEventListener('DOMContentLoaded', () => {
  cargarReivindicaciones();
  setupEventListeners();
});

function setupEventListeners() {
  document.getElementById('btn-nueva-reivindicacion').addEventListener('click', abrirModalNueva);
  document.getElementById('btn-cancelar').addEventListener('click', cerrarModal);
  document.getElementById('modal-close').addEventListener('click', cerrarModal);
  document.getElementById('form-reivindicacion').addEventListener('submit', guardarReivindicacion);
  document.getElementById('modal-firmas-close').addEventListener('click', cerrarModalFirmas);
  document.getElementById('modal-compartir-close').addEventListener('click', cerrarModalCompartir);
  document.getElementById('btn-copiar-enlace').addEventListener('click', copiarEnlace);
  document.getElementById('scrim').addEventListener('click', cerrarModal);
}

// ========== Cargar reivindicaciones ==========
async function cargarReivindicaciones() {
  try {
    const resp = await fetch('/reivindicaciones/api/reivindicaciones');
    if (!resp.ok) throw new Error('Error al cargar');
    reivindicacionesActual = await resp.json();
    renderizarReivindicaciones();
  } catch (error) {
    console.error('Error:', error);
  }
}

function renderizarReivindicaciones() {
  const main = document.getElementById('rv-main');
  if (reivindicacionesActual.length === 0) {
    main.innerHTML = '<div class="rv-empty"><p>No hay reivindicaciones. ¡Crea la primera!</p></div>';
    return;
  }

  main.innerHTML = reivindicacionesActual.map(r => `
    <div class="rv-card">
      <div class="rv-card-header">
        <h3>${escapeHtml(r.titulo)}</h3>
        <span class="rv-estado rv-estado-${r.estado}">${r.estado}</span>
      </div>
      <div class="rv-card-body">
        <div class="rv-card-stats">
          <div class="rv-stat">
            <span class="rv-stat-label">Firmas</span>
            <span class="rv-stat-value">${r.contador_firmas || 0}${r.objetivo_firmas ? '/' + r.objetivo_firmas : ''}</span>
          </div>
          <div class="rv-stat">
            <span class="rv-stat-label">Inicio</span>
            <span class="rv-stat-value">${formatearFecha(r.fecha_inicio)}</span>
          </div>
          ${r.fecha_fin ? `<div class="rv-stat">
            <span class="rv-stat-label">Fin</span>
            <span class="rv-stat-value">${formatearFecha(r.fecha_fin)}</span>
          </div>` : ''}
        </div>
      </div>
      <div class="rv-card-actions">
        <button class="rv-btn rv-btn-secondary" onclick="verFirmas(${r.id})">Ver firmas</button>
        <button class="rv-btn rv-btn-secondary" onclick="abrirCompartir(${r.id})">Compartir</button>
        <button class="rv-btn rv-btn-secondary" onclick="abrirEditar(${r.id})">Editar</button>
        <button class="rv-btn rv-btn-danger" onclick="eliminar(${r.id})">Eliminar</button>
      </div>
    </div>
  `).join('');
}

// ========== Modales ==========
function abrirModalNueva() {
  reivindicacionEnEdicion = null;
  document.getElementById('modal-titulo').textContent = 'Nueva reivindicación';
  document.getElementById('form-reivindicacion').reset();
  document.getElementById('rv-fecha-inicio').value = new Date().toISOString().split('T')[0];
  abrirModal('modal-reivindicacion');
}

function abrirEditar(id) {
  const r = reivindicacionesActual.find(x => x.id == id);
  if (!r) return;
  reivindicacionEnEdicion = r;
  document.getElementById('modal-titulo').textContent = 'Editar reivindicación';
  document.getElementById('rv-titulo').value = r.titulo;
  document.getElementById('rv-fecha-inicio').value = r.fecha_inicio;
  document.getElementById('rv-fecha-fin').value = r.fecha_fin || '';
  document.getElementById('rv-objetivo').value = r.objetivo_firmas || '';

  // Modal para editar bloques de contenido
  abrirModalContenido(r);
}

function abrirModalContenido(reivindicacion) {
  const html = `
    <div class="rv-modal-contenido">
      <div class="rv-modal-h">
        <h3>Editar contenido</h3>
        <button class="rv-x" onclick="cerrarModal()">×</button>
      </div>
      <div class="rv-bloques-editor" id="bloques-editor">
        <!-- Cargado dinámicamente -->
      </div>
      <div class="rv-modal-actions">
        <button class="rv-btn rv-btn-secondary" onclick="anadirBloque()">+ Añadir bloque</button>
        <button class="rv-btn rv-btn-primary" onclick="guardarBloques(${reivindicacion.id})">Guardar bloques</button>
      </div>
    </div>
  `;

  // Mostrar en modal aparte - por ahora lo simplificamos
  console.log('Editar contenido para:', reivindicacion.titulo);
  // Aquí se abre un editor más complejo
  abrirModal('modal-reivindicacion');
}

function abrirModal(id) {
  document.getElementById(id).hidden = false;
  document.getElementById('scrim').hidden = false;
}

function cerrarModal() {
  document.getElementById('modal-reivindicacion').hidden = true;
  document.getElementById('scrim').hidden = true;
}

function cerrarModalFirmas() {
  document.getElementById('modal-firmas').hidden = true;
  document.getElementById('scrim').hidden = true;
}

function cerrarModalCompartir() {
  document.getElementById('modal-compartir').hidden = true;
  document.getElementById('scrim').hidden = true;
}

// ========== Guardar reivindicación ==========
async function guardarReivindicacion(e) {
  e.preventDefault();

  const titulo = document.getElementById('rv-titulo').value;
  const fecha_inicio = document.getElementById('rv-fecha-inicio').value;
  const fecha_fin = document.getElementById('rv-fecha-fin').value;
  const objetivo_firmas = parseInt(document.getElementById('rv-objetivo').value) || 0;

  if (!titulo || !fecha_inicio) {
    alert('Faltan campos requeridos');
    return;
  }

  const datos = {
    titulo,
    fecha_inicio,
    fecha_fin: fecha_fin || null,
    objetivo_firmas,
    contenido: reivindicacionEnEdicion?.contenido || [],
  };

  try {
    const url = reivindicacionEnEdicion
      ? `/reivindicaciones/api/reivindicaciones/${reivindicacionEnEdicion.id}`
      : '/reivindicaciones/api/reivindicaciones';

    const metodo = reivindicacionEnEdicion ? 'PUT' : 'POST';

    const resp = await fetch(url, {
      method: metodo,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    });

    if (!resp.ok) throw new Error('Error al guardar');
    cerrarModal();
    cargarReivindicaciones();
  } catch (error) {
    alert('Error: ' + error.message);
  }
}

// ========== Firmas ==========
async function verFirmas(id) {
  try {
    const resp = await fetch(`/reivindicaciones/api/reivindicaciones/${id}/firmas`);
    if (!resp.ok) throw new Error('Error');
    const firmas = await resp.json();

    const r = reivindicacionesActual.find(x => x.id == id);
    document.getElementById('firmas-titulo').textContent = `Firmas - ${r.titulo}`;
    document.getElementById('stat-total').textContent = firmas.length;

    const tbody = document.querySelector('#tabla-firmas tbody');
    tbody.innerHTML = firmas.map(f => `
      <tr>
        <td>${escapeHtml(f.nombre)}</td>
        <td>${escapeHtml(f.dni)}</td>
        <td>${formatearFecha(f.creado_en)}</td>
      </tr>
    `).join('');

    document.getElementById('btn-descargar-csv').onclick = () => descargarCSV(id, firmas);
    abrirModal('modal-firmas');
  } catch (error) {
    alert('Error: ' + error.message);
  }
}

function descargarCSV(id, firmas) {
  const r = reivindicacionesActual.find(x => x.id == id);
  let csv = 'Nombre,DNI,Fecha\n';
  firmas.forEach(f => {
    csv += `"${f.nombre.replace(/"/g, '""')}","${f.dni}","${f.creado_en}"\n`;
  });

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `firmas-${r.id}.csv`);
  link.click();
}

// ========== Compartir ==========
async function abrirCompartir(id) {
  const r = reivindicacionesActual.find(x => x.id == id);
  if (!r) return;

  try {
    const resp = await fetch(`/reivindicaciones/api/reivindicaciones/${id}`);
    if (!resp.ok) throw new Error('Error');
    const datos = await resp.json();

    // Si no tiene token, generar uno
    const token = datos.token || await generarToken(id);
    const enlace = `${window.location.origin}/reivindicaciones/firma/${token}`;

    document.getElementById('input-enlace').value = enlace;
    abrirModal('modal-compartir');
  } catch (error) {
    alert('Error: ' + error.message);
  }
}

async function generarToken(id) {
  const resp = await fetch(`/reivindicaciones/api/reivindicaciones/${id}/token`, {
    method: 'POST',
  });
  if (!resp.ok) throw new Error('Error');
  const { token } = await resp.json();
  return token;
}

function copiarEnlace() {
  const input = document.getElementById('input-enlace');
  input.select();
  document.execCommand('copy');
  alert('¡Enlace copiado al portapapeles!');
}

// ========== Eliminar ==========
async function eliminar(id) {
  if (!confirm('¿Estás seguro de que quieres eliminar esta reivindicación? Se perderán todas las firmas.')) {
    return;
  }

  try {
    const resp = await fetch(`/reivindicaciones/api/reivindicaciones/${id}`, {
      method: 'DELETE',
    });
    if (!resp.ok) throw new Error('Error');
    cargarReivindicaciones();
  } catch (error) {
    alert('Error: ' + error.message);
  }
}

// ========== Utilidades ==========
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatearFecha(fecha) {
  return new Date(fecha).toLocaleDateString('es-ES');
}

function anadirBloque() {
  // Simplificado por ahora
  console.log('Añadir bloque');
}

function guardarBloques(id) {
  // Simplificado por ahora
  console.log('Guardar bloques para:', id);
}
