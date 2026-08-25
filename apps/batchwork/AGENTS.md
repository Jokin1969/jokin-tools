# Batchwork — reglas del proyecto

Las reglas vinculantes de este directorio están en [`CLAUDE.md`](./CLAUDE.md).
Léelas enteras antes de tocar nada bajo `apps/batchwork/`. No son orientativas.

Resumen (el detalle y los contratos concretos están en `CLAUDE.md`):

1. Nunca generar, completar ni reconstruir secuencias biológicas: si falta, se aborta.
2. Prohibido `except: pass` y `except Exception: return None`; todo fallo se propaga
   diciendo QUÉ falló y QUÉ paso queda sin ejecutar.
3. Filtros con tres estados `PASS` / `FAIL` / `NOT_RUN`; nada se reporta como aprobado
   si un filtro no llegó a correr.
4. Ningún endpoint o URL externa sin verificar antes; si no está verificado, se pregunta.
5. Tests antes que la funcionalidad, con datos reales y su procedencia.
6. Python 3.11+, solo stdlib salvo autorización explícita. Sin frameworks web en la v1.
