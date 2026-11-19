const canvas = document.getElementById('signatureCanvas');
const ctx = canvas.getContext('2d', { willReadFrequently: true });

let isDrawing = false;
let lastX = 0;
let lastY = 0;
const history = [];

// Redimensionar canvas al tamaño del contenedor
function resizeCanvas() {
  const wrapper = canvas.parentElement;
  const rect = wrapper.getBoundingClientRect();

  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;

  ctx.scale(dpr, dpr);
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = '#1B6CB0';

  redrawCanvas();
}

// Guardar estado del canvas
function saveState() {
  history.push(canvas.toDataURL());
}

// Redibujar canvas desde el histórico
function redrawCanvas() {
  if (history.length > 0) {
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    };
    img.src = history[history.length - 1];
  } else {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
}

// Eventos del canvas
function getCoordinates(e) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  if (e.touches) {
    const touch = e.touches[0];
    return {
      x: (touch.clientX - rect.left) / dpr,
      y: (touch.clientY - rect.top) / dpr
    };
  } else {
    return {
      x: (e.clientX - rect.left) / dpr,
      y: (e.clientY - rect.top) / dpr
    };
  }
}

function startDrawing(e) {
  if (history.length === 0) {
    saveState();
  }
  isDrawing = true;
  const coords = getCoordinates(e);
  lastX = coords.x;
  lastY = coords.y;
  e.preventDefault();
}

function draw(e) {
  if (!isDrawing) return;

  const coords = getCoordinates(e);
  ctx.beginPath();
  ctx.moveTo(lastX, lastY);
  ctx.lineTo(coords.x, coords.y);
  ctx.stroke();

  lastX = coords.x;
  lastY = coords.y;
  e.preventDefault();
}

function stopDrawing(e) {
  if (!isDrawing) return;
  isDrawing = false;
  saveState();
  e.preventDefault();
}

canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseout', stopDrawing);

canvas.addEventListener('touchstart', startDrawing);
canvas.addEventListener('touchmove', draw);
canvas.addEventListener('touchend', stopDrawing);

// Botones
document.getElementById('btn-clear').addEventListener('click', () => {
  history.length = 0;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  showFeedback('Canvas limpiado');
});

document.getElementById('btn-undo').addEventListener('click', () => {
  if (history.length > 0) {
    history.pop();
    redrawCanvas();
    showFeedback('Último trazo deshecho');
  }
});

document.getElementById('btn-copy').addEventListener('click', async () => {
  try {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    await navigator.clipboard.write([
      new ClipboardItem({ 'image/png': blob })
    ]);
    showFeedback('✓ Firma copiada al portapapeles');
  } catch (err) {
    showFeedback('Error al copiar. Intenta descargar en su lugar.');
  }
});

document.getElementById('btn-download-png').addEventListener('click', () => {
  const link = document.createElement('a');
  link.href = canvas.toDataURL('image/png');
  link.download = `firma-${new Date().getTime()}.png`;
  link.click();
  showFeedback('PNG descargado');
});

document.getElementById('btn-download-svg').addEventListener('click', () => {
  const svg = canvasToSVG();
  const blob = new Blob([svg], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `firma-${new Date().getTime()}.svg`;
  link.click();
  URL.revokeObjectURL(url);
  showFeedback('SVG descargado');
});

document.getElementById('btn-download-pdf').addEventListener('click', () => {
  // Usando html2pdf si está disponible, si no, una simple conversión
  const image = canvas.toDataURL('image/png');
  const link = document.createElement('a');

  // Crear PDF simple con jsPDF
  const script = document.createElement('script');
  script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js';
  script.onload = () => {
    const element = document.createElement('div');
    element.style.padding = '20px';
    element.innerHTML = `<img src="${image}" style="max-width: 100%; border: 1px solid #ddd;">`;

    const opt = {
      margin: 10,
      filename: `firma-${new Date().getTime()}.pdf`,
      image: { type: 'png', quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: { orientation: 'landscape', unit: 'mm', format: 'a4' }
    };

    html2pdf().set(opt).from(element).save();
    showFeedback('PDF descargado');
  };
  document.head.appendChild(script);
});

// Convertir canvas a SVG (líneas)
function canvasToSVG() {
  const width = canvas.width / (window.devicePixelRatio || 1);
  const height = canvas.height / (window.devicePixelRatio || 1);

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`;
  svg += `<rect width="${width}" height="${height}" fill="white"/>`;

  // Extraer datos de píxeles y crear caminos aproximados
  // Esto es una versión simplificada que copia la imagen
  const dataUrl = canvas.toDataURL('image/png');
  svg += `<image href="${dataUrl}" width="${width}" height="${height}"/>`;
  svg += `</svg>`;

  return svg;
}

// Mostrar feedback
function showFeedback(message) {
  const feedback = document.getElementById('feedback');
  const text = document.getElementById('feedback-text');
  text.textContent = message;
  feedback.removeAttribute('hidden');

  setTimeout(() => {
    feedback.setAttribute('hidden', '');
  }, 2000);
}

// Inicializar
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// Desabilitar scroll en mobile para que el canvas funcione mejor
document.addEventListener('touchmove', (e) => {
  if (e.target === canvas) {
    e.preventDefault();
  }
}, { passive: false });
