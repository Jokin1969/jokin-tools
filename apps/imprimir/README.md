# Imprimir — hub de impresión

Cola central de impresión. Los trabajos entran por dos vías, se guardan en una
cola (SQLite) y **un único agente local** (junto a la impresora) los recoge e
imprime. Así cualquier app —de **cualquier repo / proyecto de Railway**— puede
imprimir sin tener su propio agente.

```
  Email con adjunto ─┐
                     ├─▶  Cola (jokin-tools)  ◀── pull ──  Agente local  ─▶  Impresora
  Otra app: POST ────┘        (este hub)                   (print-agent/)     \\cicpri042\Color
  /imprimir/api/submit
```

## Vías de entrada
1. **Email**: enviar un adjunto (PDF/JPG/PNG/DOCX/XLSX/PPTX) al buzón configurado.
2. **API de envío** (`POST /imprimir/api/submit`): cualquier app empuja un fichero.

Todo se **normaliza a PDF** en el servidor, así el agente solo imprime PDF.

## API de envío (para tus otras apps)

`POST https://<hub>/imprimir/api/submit` · `multipart/form-data` · cabecera
`X-Api-Key: <IMPRIMIR_SUBMIT_KEY>`.

Campos:
- `file` (obligatorio): el documento (PDF, JPG, PNG, DOCX, XLSX, PPTX).
- `filename` (opcional): nombre a mostrar.
- `printer` (opcional): impresora destino; por defecto `IMPRIMIR_DEFAULT_PRINTER`.
- `source` (opcional): nombre de la app que envía (aparece en el panel).
- `subject` (opcional).

Respuesta: `{ "ok": true, "id": 123, "status": "queued", "printer": "..." }`.

**Recomendado: llamar servidor-a-servidor** (desde el backend de la otra app), para
que la `IMPRIMIR_SUBMIT_KEY` no quede expuesta en el navegador. El botón vive en la
UI de tu app, y esa app reenvía al hub.

### Ejemplos

curl:
```bash
curl -F "file=@documento.pdf" -F "source=research-tools" \
  -H "X-Api-Key: TU_SUBMIT_KEY" \
  https://TU-HUB/imprimir/api/submit
```

Node (backend de otra app):
```js
const fd = new FormData();
fd.append('file', new Blob([pdfBuffer], { type: 'application/pdf' }), 'ficha.pdf');
fd.append('source', 'mi-app');
const r = await fetch(process.env.PRINT_HUB_URL + '/imprimir/api/submit', {
  method: 'POST', headers: { 'X-Api-Key': process.env.PRINT_HUB_KEY }, body: fd,
});
const { id } = await r.json();
```

Python:
```python
import requests
requests.post(f"{HUB}/imprimir/api/submit",
              headers={"X-Api-Key": SUBMIT_KEY},
              files={"file": ("ficha.pdf", pdf_bytes, "application/pdf")},
              data={"source": "mi-app"})
```

### Patrón de botón "Imprimir" en otra app
1. La app genera el PDF (o toma el que ya tiene).
2. Su backend hace el `POST /imprimir/api/submit` al hub con `PRINT_HUB_KEY`.
3. El agente lo imprime en segundos; el estado se ve en `/imprimir/status`.

## Configuración
Ver `.env.example` (`IMPRIMIR_*`). Para el envío por API basta con definir
`IMPRIMIR_SUBMIT_KEY` en el hub y usar ese mismo valor en las apps que envían.
El agente local se documenta en `print-agent/README.md`.
