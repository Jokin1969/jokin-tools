# Jokin's Tools — notas para agentes

Hub de utilidades. Node.js + Express, SQLite (`better-sqlite3`), frontend vanilla,
deploy en Railway. Detalles de stack y variables de entorno en el `README.md` (ojo: su
sección "Estructura" está desactualizada, la de abajo no).

## Mapa

| Ruta | Qué es | Reglas |
|---|---|---|
| `server.js`, `src/`, `public/`, `lib/`, `test/` | Hub principal (Node/Express) | Las de este fichero |
| `apps/asignacion/`, `apps/auth/`, `apps/bitacora/`, `apps/datamatrix/`, `apps/feep/`, `apps/imprimir/`, `apps/qr-tis/`, `apps/re-memory/` | Micro-apps del hub (Node/Express) | Las de este fichero |
| `apps/batchwork/` | Operaciones por lotes sobre ficheros (Node + scripts Python auxiliares) | Las de este fichero |
| `apps/shmir-design/` | Proyecto Python 3.11+ independiente, CLI + interfaz Streamlit | **`apps/shmir-design/CLAUDE.md`** |

`apps/batchwork/` y `apps/shmir-design/` son cosas distintas y no comparten nada:
el primero es la app de lotes del hub, el segundo es el diseñador de shmiRs.

## `apps/shmir-design/` tiene reglas propias y vinculantes

Antes de tocar cualquier cosa bajo `apps/shmir-design/`, lee entero
[`apps/shmir-design/CLAUDE.md`](./apps/shmir-design/CLAUDE.md). No son orientativas:
prohíben generar secuencias biológicas, prohíben tragarse errores, obligan a estados
`PASS`/`FAIL`/`NOT_RUN` en los filtros, a verificar endpoints y formatos antes de
escribirlos, a escribir los tests primero con datos reales, y a no salir de la librería
estándar sin autorización escrita.

Esas reglas **no** aplican al resto del hub, que es Node y tiene sus dependencias ya
instaladas. Y al revés: los patrones del hub Node no se importan a `apps/shmir-design/`.

## Comprobaciones

```bash
npm test                  # suite del hub Node (node --test)
npm run check:shmir       # regla 2 de shmir-design sobre el AST
npm run test:shmir        # tests de shmir-design (394, sin dependencias externas)
```

La interfaz Streamlit de `apps/shmir-design/` es opcional y se instala aparte
(`pip install -r apps/shmir-design/requirements-ui.txt`); ni el hub ni los CLI la
necesitan.
