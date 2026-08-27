# Procedencia de `G4_diana` / `G4_guia`

> **Estado: SIN RESOLVER.** Este documento no justifica el filtro. Registra de dónde
> salió y qué NO se ha podido establecer, que es lo que se preguntó. Mientras siga así,
> el filtro no emite veredicto (`UNDECIDED_FILTERS`).

La pregunta fue literal: **en qué commit se introdujo, qué lo motivó y quién lo pidió.**
Van las tres, y la tercera no tiene respuesta buena.

## Corrección previa

En `CLAUDE.md` se dijo que G4 venía «del commit fundacional (`ccb344a`)». **Es falso.**
`ccb344a` es el commit del renombrado de `apps/batchwork/` a `apps/shmir-design/`, y su
propio mensaje dice «G4 **se comprueba ahora** sobre la diana Y sobre la guía
(`G4_diana`, `G4_guia`)»: ya existía, y ese commit lo PARTIÓ en dos variantes. Salió
primero en la búsqueda y se dio por bueno sin mirar qué decía — el principio nº 3
aplicado a la respuesta sobre un incumplimiento del principio nº 3.

## La secuencia real, en 33 minutos del 25 de agosto de 2026

| Hora (UTC) | Commit | Qué pasa con G4 |
|---|---|---|
| 10:02 | `8211734` | Nace `apps/batchwork/` con las seis reglas. **No hay pipeline ni G4.** |
| 10:20 | `61741c4` | Aparece `docs/pipeline.md` con la tabla de 15 pasos. **El paso 8 es «Sin motivo G-cuádruplex», tipo «duro», estado «pendiente».** Aparece también `docs/valores-esperados.md`. |
| 10:35 | `b544dd2` | `hard_filters.py`: «GC 0.30-0.52, homopolímero máx 3, **motivo G4 canónico y guía**». La implementación. |
| 11:02 | `ccb344a` | Se parte en `G4_diana` y `G4_guia` con el renombrado. |

## Qué motivó la implementación

`b544dd2` no lo discute: implementa el paso 8 porque el paso 8 estaba en la tabla. G4
entra **empaquetado** con GC y homopolímero, como si fueran la misma clase de cosa. Y
ahí está la diferencia que importa: en ese mismo fichero, la asimetría lleva
`MIN_ASYMMETRY = 0.5  # kcal/mol` y su commit cita Turner 2004 y reproduce cinco valores
verificados uno a uno. **El G4 no lleva ninguna cita**: sólo un comentario que dice
«Motivo G-cuadruplex canonico» y la expresión regular
`G{3,}[ACGTN]{1,7}G{3,}[ACGTN]{1,7}G{3,}[ACGTN]{1,7}G{3,}`. Ni artículo, ni predictor,
ni umbral, ni criterio de por qué 3 G y por qué 1-7 nt de separación.

## Quién lo pidió — lo que el repositorio SÍ y NO puede decir

Lo que **sí** consta:

- `61741c4` distingue en su propio mensaje entre lo encargado y lo añadido: «Apartados A,
  B y C **del encargo**» (los guardarraíles de poliadenilación) y, aparte, «**Además**:
  docs/pipeline.md, docs/valores-esperados.md…». **G4 está en el «además».** La tabla de
  15 pasos que lo declara «duro» la escribió el agente en ese commit.
- Pero `docs/valores-esperados.md`, creado en ese mismo commit, se titula «**Valores
  esperados (verificados por el responsable del proyecto)**» y lista los criterios así:
  «umbrales GC 0.30–0.52, homopolímero máx 3, asimetría ≥ +0.5 kcal/mol, **sin motivo
  G4**, U forzada en posición 1 de la guía», con el resultado esperado: ratón 1221
  ventanas → **181 PASS** → 93 sitios.
- Ese 181 **no lo pudo calcular este código**: en ese commit los pasos 3–8 estaban
  «pendiente». Vino de fuera.

Lo que **no** consta: si la lista de criterios que acompaña al 181 la dictó el
responsable del proyecto o la redactó el agente alrededor de un número suelto. Los dos
documentos nacen en el mismo commit y no hay nada anterior en el repositorio que los
separe. **El repositorio no lo puede decidir, así que no se decide aquí.**

Y una advertencia sobre ese 181: es a su vez una errata registrada —correspondía al signo
invertido de la asimetría— así que tampoco sirve para reconstruir con qué criterios se
obtuvo.

## Lo medido, que sí es firme

Sobre las **2170 ventanas** del 3'UTR murino, las dos variantes pasan **todas**. G4 no ha
excluido a ningún candidato nunca, en ninguna corrida. Por eso pudo estar tres meses
emitiendo veredictos sin que nadie lo mirara: un filtro que nunca dice que no es
indistinguible de uno que no existe, hasta el día en que dice que no.

## Qué haría falta para cerrarlo

Nada de esto se hace hasta que se decida por escrito:

1. **Si es filtro duro o desempate.** Un motivo G4 en la diana y uno en la guía no son la
   misma pregunta y puede que no merezcan el mismo trato.
2. **Qué predictor.** La expresión regular actual localiza un motivo de secuencia; no
   predice plegado. Si lo que importa es que el cuadruplexo se forme, hace falta un
   predictor de verdad y su procedencia.
3. **Con qué justificación de umbral**, en `justificacion.py`. Y con eso hay que arreglar
   el hueco que lo dejó pasar: **el test que exige justificación recorre los campos de
   `Thresholds`**, así que un criterio que no es un número no lo ve nadie. Cualquier
   criterio futuro que no sea un umbral entra por el mismo agujero.
