# Batchwork

Proyecto Python del hub. Vive dentro de `jokin-tools` pero es independiente del
backend Node/Express: Python 3.11+, solo librería estándar, interfaz CLI (regla 6).

## Estado

Solo hay reglas y su verificador. **No hay código funcional todavía**, y hay dos
bloqueantes declarados:

- **Sin datos reales.** La regla 5 exige tests con datos reales; los datos no llegaron
  con el encargo. `tests/data/` está vacío a propósito y no se rellena con secuencias
  sintéticas — eso sería la regla 1 por otra puerta.
- **Sin endpoints verificados.** `docs/endpoints-verificados.md` está vacío, así que no
  se escribe ninguna llamada de red (regla 4).

## Ficheros

| Ruta | Qué es |
|---|---|
| `CLAUDE.md` | Las seis reglas innegociables y sus contratos concretos. Vinculante. |
| `AGENTS.md` | Resumen de las reglas para agentes que no leen `CLAUDE.md`. |
| `docs/endpoints-verificados.md` | Registro de URLs externas verificadas (vacío). |
| `docs/dependencias-autorizadas.md` | Registro de dependencias autorizadas (vacío). |
| `tools/check_rules.py` | Verificador de la regla 2 sobre el AST. |
| `tests/test_check_rules.py` | Tests del verificador (escritos antes que él). |
| `tests/data/PROCEDENCIA.md` | Procedencia de los datos de test (vacío). |

## Comprobaciones

```bash
# Regla 2: manejo de errores que se traga fallos
npm run check:batchwork
# o: python3 apps/batchwork/tools/check_rules.py [ruta ...]

# Tests
npm run test:batchwork
# o: cd apps/batchwork && python3 -m unittest discover -s tests -t .
```

`check_rules.py` sale con 0 si está limpio, 1 si hay violaciones y 2 si algún fichero no
se pudo analizar — un fichero no analizable nunca cuenta como limpio.

## Qué hace falta para empezar a escribir código

1. Los datos reales para los tests, con su procedencia (fuente, accession, fecha).
2. Los endpoints externos que deba usar Batchwork, para verificarlos antes de escribir
   ninguna URL.
3. La descripción del pipeline: qué candidatos entran, qué filtros se aplican y qué
   recurso externo necesita cada uno (para el contrato `PASS`/`FAIL`/`NOT_RUN`).
