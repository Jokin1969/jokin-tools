const path = require('path');
const ExcelJS = require('exceljs');

async function run(session, params) {
  const { fileList = [] } = params;

  session.progress = { current: 0, total: 1, message: 'Generando inventario...' };

  // Detect whether files carry a folder prefix (webkitdirectory / webkitGetAsEntry)
  // or were dragged as flat files (no '/' in relativePath).
  const hasFolderPrefix = fileList.some(f => f.relativePath.includes('/'));
  const rootName = hasFolderPrefix
    ? (fileList[0]?.relativePath?.split('/')[0] || 'carpeta')
    : 'ficheros';

  // Build first-level structure: files directly in root + immediate subdirs
  const firstLevel = new Map();

  for (const entry of fileList) {
    const parts = entry.relativePath.split('/');

    // Flat file (no folder prefix): treat as a root-level file
    if (!hasFolderPrefix) {
      const itemName = parts[0];
      if (!itemName || firstLevel.has(itemName)) continue;
      const ext = path.extname(itemName);
      firstLevel.set(itemName, {
        tipo: 'Fichero',
        nombre: ext ? path.basename(itemName, ext) : itemName,
        extension: ext ? ext.slice(1).toUpperCase() : '',
        tamano: (entry.size / 1024).toFixed(2) + ' KB',
        rutaRelativa: entry.relativePath,
      });
      continue;
    }

    // Folder mode: parts[0] = root folder, parts[1] = first-level item
    if (parts.length < 2 || !parts[1]) continue;

    const itemName = parts[1];
    if (firstLevel.has(itemName)) continue;

    if (parts.length === 2) {
      const ext = path.extname(itemName);
      firstLevel.set(itemName, {
        tipo: 'Fichero',
        nombre: ext ? path.basename(itemName, ext) : itemName,
        extension: ext ? ext.slice(1).toUpperCase() : '',
        tamano: (entry.size / 1024).toFixed(2) + ' KB',
        rutaRelativa: entry.relativePath,
      });
    } else {
      firstLevel.set(itemName, {
        tipo: 'Carpeta',
        nombre: itemName,
        extension: '',
        tamano: '',
        rutaRelativa: rootName + '/' + itemName,
      });
    }
  }

  const entries = [...firstLevel.values()].sort((a, b) => {
    if (a.tipo !== b.tipo) return a.tipo === 'Carpeta' ? -1 : 1;
    return a.nombre.localeCompare(b.nombre, 'es');
  });

  const workbook = new ExcelJS.Workbook();
  workbook.creator = "Batchwork — Jokin's Tools";
  const sheet = workbook.addWorksheet('Inventario');

  sheet.columns = [
    { header: 'Tipo', key: 'tipo', width: 12 },
    { header: 'Nombre', key: 'nombre', width: 42 },
    { header: 'Extensión', key: 'extension', width: 13 },
    { header: 'Tamaño', key: 'tamano', width: 16 },
    { header: 'Ruta relativa', key: 'rutaRelativa', width: 64 },
  ];

  const headerRow = sheet.getRow(1);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1B6CB0' } };
  headerRow.alignment = { vertical: 'middle' };

  for (const entry of entries) {
    const row = sheet.addRow(entry);
    if (entry.tipo === 'Carpeta') {
      row.font = { bold: true };
      row.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF0F4FA' } };
    }
  }

  const outPath = path.join(session.outputDir, 'inventario.xlsx');
  await workbook.xlsx.writeFile(outPath);

  session.resultFile = outPath;
  session.resultMime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  session.resultFilename = 'inventario.xlsx';
  session.progress = { current: 1, total: 1, message: `${entries.length} entradas en el inventario` };
  session.status = 'done';
}

module.exports = { run };
