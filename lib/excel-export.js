const ExcelJS = require('exceljs');
const path = require('path');

/**
 * Exporta datos a Excel con estilos profesionales
 * @param {Array} datos - Array de objetos a exportar
 * @param {Array} columnas - Array de {key, header, width} para especificar qué exportar
 * @param {Object} opciones - {titulo, hoja, estilos}
 * @returns {Promise<Buffer>}
 */
async function exportarExcel(datos, columnas, opciones = {}) {
  const {
    titulo = 'Reporte',
    hoja = 'Datos',
    empresa = 'Jokin\'s Tools',
    estilos = true,
  } = opciones;

  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet(hoja);

  // Configurar encabezados
  const headers = columnas.map(col => col.header);
  worksheet.addRow(headers);

  // Aplicar estilos a encabezados
  if (estilos) {
    worksheet.getRow(1).forEach(cell => {
      cell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FF1B6CB0' },
      };
      cell.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 11 };
      cell.alignment = { horizontal: 'center', vertical: 'center', wrapText: true };
      cell.border = {
        top: { style: 'thin' },
        left: { style: 'thin' },
        bottom: { style: 'thin' },
        right: { style: 'thin' },
      };
    });
  }

  // Configurar ancho de columnas
  columnas.forEach((col, idx) => {
    worksheet.getColumn(idx + 1).width = col.width || 15;
  });

  // Agregar datos
  datos.forEach((fila, filaIdx) => {
    const valores = columnas.map(col => fila[col.key]);
    const row = worksheet.addRow(valores);

    // Estilos para datos
    if (estilos) {
      row.forEach((cell, cellIdx) => {
        cell.alignment = { horizontal: 'left', vertical: 'center', wrapText: true };
        cell.border = {
          top: { style: 'thin', color: { argb: 'FFDDDDDD' } },
          left: { style: 'thin', color: { argb: 'FFDDDDDD' } },
          bottom: { style: 'thin', color: { argb: 'FFDDDDDD' } },
          right: { style: 'thin', color: { argb: 'FFDDDDDD' } },
        };

        // Alternancia de colores de fila
        if (filaIdx % 2 === 1) {
          cell.fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFF9F9F9' },
          };
        }
      });
    }
  });

  // Congelar encabezado
  worksheet.views = [{ state: 'frozen', ySplit: 1 }];

  // Obtener buffer
  const buffer = await workbook.xlsx.writeBuffer();
  return buffer;
}

/**
 * Genera nombre de archivo con timestamp
 * @param {String} prefijo
 * @returns {String}
 */
function generarNombreArchivo(prefijo) {
  const fecha = new Date().toISOString().split('T')[0];
  const hora = new Date().toTimeString().split(' ')[0].replace(/:/g, '-');
  return `${prefijo}_${fecha}_${hora}.xlsx`;
}

/**
 * Columnas predefinidas para diferentes exportaciones
 */
const COLUMNAS_PREDEFINIDAS = {
  firmas: [
    { key: 'nombre', header: 'Nombre', width: 25 },
    { key: 'dni', header: 'DNI/NIE', width: 15 },
    { key: 'creado_en', header: 'Fecha y Hora', width: 20 },
    { key: 'ip_address', header: 'Dirección IP', width: 18 },
  ],
  firmas_completo: [
    { key: 'nombre', header: 'Nombre', width: 25 },
    { key: 'dni', header: 'DNI/NIE', width: 15 },
    { key: 'creado_en', header: 'Fecha y Hora', width: 20 },
    { key: 'ip_address', header: 'Dirección IP', width: 18 },
    { key: 'user_agent', header: 'Dispositivo/Navegador', width: 30 },
  ],
};

module.exports = {
  exportarExcel,
  generarNombreArchivo,
  COLUMNAS_PREDEFINIDAS,
};
