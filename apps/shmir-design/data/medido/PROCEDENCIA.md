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
