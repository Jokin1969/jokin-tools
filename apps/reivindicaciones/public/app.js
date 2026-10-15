let reivindicacionesActual = [];
let reivindicacionEnEdicion = null;
let contenidoEnEdicion = [];

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
  document.getElementById('modal-contenido-close').addEventListener('click', cerrarModalContenido);
  document.getElementById('modal-estadisticas-close').addEventListener('click', cerrarModalEstadisticas);
  document.getElementById('btn-copiar-enlace').addEventListener('click', copiarEnlace);
  document.getElementById('btn-anadir-titulo').addEventListener('click', () => anadirBloque('titulo'));
  document.getElementById('btn-anadir-parrafo').addEventListener('click', () => anadirBloque('parrafo'));
  document.getElementById('btn-anadir-lista').addEventListener('click', () => anadirBloque('lista'));
  document.getElementById('btn-anadir-imagen').addEventListener('click', () => anadirBloque('imagen'));
  document.getElementById('btn-guardar-contenido').addEventListener('click', guardarContenido);
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
        <button class="rv-btn rv-btn-secondary" onclick="verEstadisticas(${r.id})">Estadísticas</button>
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
  contenidoEnEdicion = [];
  document.getElementById('modal-titulo').textContent = 'Nueva reivindicación';
  document.getElementById('form-reivindicacion').reset();
  document.getElementById('rv-fecha-inicio').value = new Date().toISOString().split('T')[0];
  abrirModal('modal-reivindicacion');
}

function abrirEditar(id) {
  const r = reivindicacionesActual.find(x => x.id == id);
  if (!r) return;
  reivindicacionEnEdicion = r;
  contenidoEnEdicion = JSON.parse(JSON.stringify(r.contenido || []));
  document.getElementById('modal-titulo').textContent = 'Editar reivindicación';
  document.getElementById('rv-titulo').value = r.titulo;
  document.getElementById('rv-fecha-inicio').value = r.fecha_inicio;
  document.getElementById('rv-fecha-fin').value = r.fecha_fin || '';
  document.getElementById('rv-objetivo').value = r.objetivo_firmas || '';
  abrirModal('modal-reivindicacion');
}

function abrirModal(id) {
  document.getElementById(id).hidden = false;
  document.getElementById('scrim').hidden = false;
  // Si es el modal de contenido, renderizar editor
  if (id === 'modal-contenido') {
    renderizarEditorContenido();
  }
}

function cerrarModal() {
  document.getElementById('modal-reivindicacion').hidden = true;
  document.getElementById('modal-contenido').hidden = true;
  document.getElementById('scrim').hidden = true;
}

function cerrarModalContenido() {
  document.getElementById('modal-contenido').hidden = true;
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

function cerrarModalEstadisticas() {
  document.getElementById('modal-estadisticas').hidden = true;
  document.getElementById('scrim').hidden = true;
}

// ========== Editor de contenido ==========
function renderizarEditorContenido() {
  const editor = document.getElementById('contenido-editor');
  if (!editor) return;

  editor.innerHTML = contenidoEnEdicion.map((bloque, idx) => `
    <div class="rv-bloque-editor" id="bloque-${idx}">
      <div class="rv-bloque-header">
        <span class="rv-bloque-tipo">${bloque.tipo.toUpperCase()}</span>
        <button class="rv-btn rv-btn-danger" style="padding:5px 10px;font-size:12px;" onclick="eliminarBloque(${idx})">×</button>
      </div>
      ${bloque.tipo === 'titulo' ? `
        <input type="text" value="${escapeHtml(bloque.texto)}" onchange="contenidoEnEdicion[${idx}].texto = this.value" placeholder="Título" style="width:100%;padding:8px;margin:8px 0;border:1px solid #ddd;border-radius:4px;" />
      ` : bloque.tipo === 'parrafo' ? `
        <textarea onchange="contenidoEnEdicion[${idx}].texto = this.value" placeholder="Párrafo de texto..." style="width:100%;padding:8px;margin:8px 0;border:1px solid #ddd;border-radius:4px;font-family:Inter,sans-serif;min-height:80px;">${escapeHtml(bloque.texto)}</textarea>
      ` : bloque.tipo === 'lista' ? `
        <div style="margin:8px 0;">
          <textarea placeholder="Items de la lista (uno por línea)" onchange="contenidoEnEdicion[${idx}].items = this.value.split('\\n').filter(x=>x.trim())" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;font-family:Inter,sans-serif;min-height:80px;">${(bloque.items || []).join('\n')}</textarea>
        </div>
      ` : bloque.tipo === 'imagen' ? `
        <div style="margin:8px 0;">
          <label style="display:block;margin-bottom:8px;">Selecciona imagen:</label>
          <input type="file" accept="image/*" onchange="subirImagenBloque(${idx}, this)" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;" />
          ${bloque.imagen_url ? `<div style="margin-top:10px;"><img src="${bloque.imagen_url}" style="max-width:200px;max-height:200px;border-radius:4px;" /><br/><small style="color:#666;">Imagen cargada</small></div>` : ''}
        </div>
      ` : ''}
    </div>
  `).join('');
}

function anadirBloque(tipo) {
  const bloques = {
    titulo: { tipo: 'titulo', texto: '' },
    parrafo: { tipo: 'parrafo', texto: '' },
    lista: { tipo: 'lista', items: [] },
    imagen: { tipo: 'imagen', imagen_url: null },
  };
  contenidoEnEdicion.push(bloques[tipo]);
  renderizarEditorContenido();
}

function subirImagenBloque(idx, input) {
  const file = input.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    contenidoEnEdicion[idx].imagen_url = e.target.result;
    renderizarEditorContenido();
  };
  reader.readAsDataURL(file);
}

function eliminarBloque(idx) {
  contenidoEnEdicion.splice(idx, 1);
  renderizarEditorContenido();
}

function guardarContenido() {
  // El contenido ya está actualizado en el array contenidoEnEdicion por los onchange
  // Cerramos el modal de contenido y continuamos con el formulario principal
  cerrarModalContenido();
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

  // Abrir editor de contenido antes de guardar
  if (!document.getElementById('modal-contenido').hidden === false) {
    abrirModal('modal-contenido');
    return; // El usuario editará el contenido y luego guardará
  }

  const datos = {
    titulo,
    fecha_inicio,
    fecha_fin: fecha_fin || null,
    objetivo_firmas,
    contenido: contenidoEnEdicion,
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

// ========== Estadísticas ==========
async function verEstadisticas(id) {
  try {
    const resp = await fetch(`/reivindicaciones/api/reivindicaciones/${id}/firmas`);
    if (!resp.ok) throw new Error('Error');
    const firmas = await resp.json();

    const r = reivindicacionesActual.find(x => x.id == id);
    document.getElementById('estadisticas-titulo').textContent = `Estadísticas - ${r.titulo}`;

    document.getElementById('stat-es-total').textContent = firmas.length;
    document.getElementById('stat-es-objetivo').textContent = r.objetivo_firmas ? r.objetivo_firmas + ' firmas' : '-';

    if (r.objetivo_firmas) {
      const porcentaje = Math.round((firmas.length / r.objetivo_firmas) * 100);
      document.getElementById('stat-es-progreso').textContent = porcentaje + '%';
    } else {
      document.getElementById('stat-es-progreso').textContent = '-';
    }

    // Calcular días activa
    if (firmas.length > 0) {
      const fechaInicio = new Date(r.fecha_inicio);
      const ahora = new Date();
      const dias = Math.floor((ahora - fechaInicio) / (1000 * 60 * 60 * 24)) + 1;
      document.getElementById('stat-es-dias').textContent = dias;
    }

    // Generar gráfica de firmas por día
    generarGrafica(firmas, r.fecha_inicio);
    abrirModal('modal-estadisticas');
  } catch (error) {
    alert('Error: ' + error.message);
  }
}

function generarGrafica(firmas, fechaInicio) {
  const container = document.getElementById('grafica-container');

  // Agrupar firmas por día
  const porDia = {};
  firmas.forEach(f => {
    const fecha = new Date(f.creado_en).toLocaleDateString();
    porDia[fecha] = (porDia[fecha] || 0) + 1;
  });

  const fechas = Object.keys(porDia).sort();
  const maxFirmas = Math.max(...Object.values(porDia));

  const html = `
    <div style="border-bottom: 2px solid #ddd; padding-bottom: 10px; margin-bottom: 10px;">
      <h4 style="margin: 0 0 20px 0;">Firmas por día</h4>
      <div style="display: flex; align-items: flex-end; justify-content: space-around; height: 200px; gap: 8px;">
        ${fechas.map(fecha => `
          <div style="display: flex; flex-direction: column; align-items: center; flex: 1;">
            <div style="background: linear-gradient(to top, #1B6CB0, #0097B2); width: 100%; border-radius: 4px 4px 0 0; height: ${(porDia[fecha] / maxFirmas) * 180}px; min-height: 20px;"></div>
            <span style="font-size: 12px; color: #666; margin-top: 8px; text-align: center; word-break: break-word;">${porDia[fecha]}</span>
            <span style="font-size: 10px; color: #999; margin-top: 4px;">${fecha}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  container.innerHTML = html;
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
