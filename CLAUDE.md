# Jokin's Tools — notas para agentes

Hub de utilidades. Node.js + Express, SQLite (`better-sqlite3`), frontend vanilla,
deploy en Railway. Detalles de stack, variables de entorno y rutas en el `README.md`.

## Mapa

| Ruta | Qué es | Reglas |
|---|---|---|
| `server.js`, `src/`, `public/` | Hub principal (Node/Express) | Las de este fichero |
| `apps/re-memory/` | Micro-app Re-memory (Node/Express) | Las de este fichero |
| `apps/batchwork/` | Proyecto Python 3.11+, CLI | **`apps/batchwork/CLAUDE.md`** |

## `apps/batchwork/` tiene reglas propias y vinculantes

Antes de tocar cualquier cosa bajo `apps/batchwork/`, lee entero
[`apps/batchwork/CLAUDE.md`](./apps/batchwork/CLAUDE.md). No son orientativas: prohíben
generar secuencias biológicas, prohíben tragarse errores, obligan a estados
`PASS`/`FAIL`/`NOT_RUN` en los filtros, a verificar endpoints antes de escribirlos, a
escribir los tests primero con datos reales, y a no salir de la librería estándar sin
autorización escrita.

Esas reglas **no** aplican al resto del hub, que es Node y tiene sus dependencias ya
instaladas. Y al revés: los patrones del hub Node no se importan a `apps/batchwork/`.

## Comprobaciones

```bash
npm run check:batchwork   # regla 2 de Batchwork sobre el AST
npm run test:batchwork    # tests de Batchwork
```

El hub Node no tiene tests todavía.
