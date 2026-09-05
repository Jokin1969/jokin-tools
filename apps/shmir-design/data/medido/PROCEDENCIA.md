# `data/medido/` — resultados REALES de herramientas externas

Lo que hay aquí no lo ha calculado este proyecto: son salidas de herramientas que corren
fuera, guardadas para que las afirmaciones escritas en `docs/` tengan detrás el dato con
el que se hicieron y para que la siguiente corrida se pueda comparar con ésta.

**No se editan.** Ni una puntuación, ni un redondeo, ni un reordenado.

---

## `spliceai_mvm_actual_2026-09-05.tsv`

**Qué es.** Las predicciones de SpliceAI sobre las diez construcciones
`mvm_actual × candidato` del panel murino, en la primera corrida real de este frente.

**Cómo se obtuvo** (declarado por quien la corrió, 2026-09-05):

| | |
|---|---|
| versión | SpliceAI 1.3 |
| entorno | conda, entorno «spliceai», en WSL/Ubuntu |
| forma de llamada | **la librería desde Python**, NO el ejecutable `spliceai` — ése anota VARIANTES sobre un genoma con un VCF y no aplica a una construcción suelta |
| modelos | los cinco del reparto, **promediados** |
| ventana | 10.000 nt, la del entrenamiento, con relleno de `N` hasta 5.000 por lado |
| convención de posiciones | la de **SpliceAI**: última base exónica el donante, primera base exónica el aceptor |

El relleno de `N` **no es contexto**: el contexto declarado de cada construcción es el que
va en su cabecera del FASTA (3.133 nt por el 5' y 1.955 por el 3' en aquella corrida).

**Qué se conserva y qué no.** El fichero original trae **107.680 filas** —todas las
posiciones de las diez construcciones, las dos clases—. Aquí se guarda un **recorte por
posición**, sin tocar ningún valor:

- todas las posiciones de **3120 a 3440**, que es el intrón entero con margen a los dos
  lados (el donante legítimo, el aceptor, el críptico conocido y el 3352);
- y las posiciones **429, 1131, 1156, 1516 y 3231**, que son las que el análisis nombra.

Son 6.500 filas. Lo que se descarta es el resto del plásmido, donde no hay nada por encima
de 0,11 y ninguna afirmación escrita depende de ello.

**Un aviso, y no es menor.** Los `md5` de este fichero son los de **aquella** corrida, y
las construcciones de hoy **no los reproducen**: el casete con el que se montaron daba un
flanco 3' de 1.955 nt y el versionado hoy da 2.067 —112 nt más—, así que las
construcciones miden 5.384 y no 5.496. Todo lo demás coincide (contexto 5' de 3.133,
donante en 3134, aceptor en 3428), por lo que las **posiciones** son las mismas. El casete
`aav_casete.fa` no se versiona en git (material de laboratorio), así que la discrepancia
**no se ha podido explicar desde aquí** y no se le asigna causa. Los tests que usan este
fichero reescriben la columna `md5` a la de la construcción de hoy, y lo dicen.

---

## `spliceai_dos_intrones_2026-09-05.tsv`

**Qué es.** La segunda corrida real de este frente, y la primera con **LAS DOS
ARQUITECTURAS**: las **20** construcciones `candidato × intrón` del panel murino —los diez
candidatos con `mvm_actual` y los diez con `intron_quimerico`—, sobre el FASTA que emitió
la app el 2026-09-05 con el quimérico ya montable.

**Cómo se obtuvo.** Igual que la anterior y por quien la corrió: SpliceAI 1.3 como
**librería desde Python**, los cinco modelos promediados, ventana de 10.000 nt con relleno
de `N` hasta 5.000 por lado, y las posiciones en **la convención de SpliceAI**.

**Validada al entrar, y las dos comprobaciones rechazan.** Las 20 construcciones del
resultado son exactamente las 20 del FASTA —mismos nombres— y **los 20 md5 cuadran uno a
uno** con los que declara cada cabecera. Un resultado de otra corrida no entra aunque
encaje de forma: es el fallo del CSV de miRarchitect.

**En qué se diferencia de la corrida del 2026-09-05 sobre diez.** No es sólo que haya el
doble: **las construcciones de `mvm_actual` no son las mismas**. Aquéllas medían 5.384 nt y
éstas 5.496 — los 112 nt del flanco 3' que quedaron sin causa asignada (ver
`docs/preguntas-abiertas.md`). Así que **las dos corridas no son comparables sitio a sitio**
y las cifras del donante legítimo se mueven: iba de 0,664 a 0,871 y ahora de 0,783 a 0,925.
Las dos están guardadas, y ninguna sustituye a la otra.

**Qué se conserva y qué no.** El fichero original trae **219.560 filas**. Aquí se guarda un
**recorte por posición**, sin tocar ningún valor: todas las de **3120 a 3449** —que cubre
los dos intrones enteros, los dos aceptores legítimos (3428 y 3414 en nuestra convención) y
los dos crípticos intrónicos— más las posiciones sueltas que el análisis nombra en el
contexto 5' (255, 430, 1132, 1157, 1517, 1749, 2032) y las dos del `GTGAGCG`. Son **13.480
filas**. Lo que se descarta es el resto del plásmido, común a las veinte, del que no depende
ninguna afirmación escrita.
