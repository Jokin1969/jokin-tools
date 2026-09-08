# Resultados medidos — base factual para un informe

**Qué es este documento.** El inventario de lo que el proyecto ha COMPUTADO, con los valores
que salieron, las comprobaciones que se pasaron y las decisiones que quedaron fijadas como
salida. No explica código: recoge resultados.

**Cómo leer cada cifra.** Cada bloque marca su procedencia:

- **`[DERIVADO 2026-09-08]`** — vuelto a calcular al escribir este documento, corriendo el
  pipeline sobre los ficheros versionados. Es el estado de hoy.
- **`[REGISTRO <fecha>]`** — medido en su día y anotado en `docs/erratas.md` o en `CLAUDE.md`.
  No se ha vuelto a derivar aquí; la fecha dice cuándo se midió.
- **`[DECLARADO]`** — un parámetro o un criterio que alguien fijó, no una medida.
- **`[NOT_RUN]`** — no se ha computado, y por qué.

**Advertencia de uso.** Ninguna cifra de aquí es un veredicto biológico: son salidas de un
pipeline computacional con limitaciones declaradas (§17). Los estados `NOT_RUN` no son `PASS`,
y **ningún candidato de este documento está aprobado** — el panel es **provisional** mientras
queden frentes abiertos (§15).

---

## 1. Entradas y procedencia

`[DERIVADO 2026-09-08]`

| entrada | longitud | md5 de la secuencia canónica | CDS |
|---|---|---|---|
| `NM_011170.3` — *Mus musculus* Prnp | **2191 nt** | `44fb8cd80883844cde5e53bbc367b176` | 185..949 |
| 3'UTR murino (derivado del CDS) | **1242 nt** | `19f5fa2a77a87892770e2affdc90e0e4` | — |
| `NM_000311.5` — *Homo sapiens* PRNP | **2435 nt** | `e28a945d24ce53e0d1d93ba5b55a532a` | 68..829 |
| 3'UTR humano | **1606 nt** | — | — |

Desfase de marcos en ratón: **`tx = 3utr + 949`**. Toda posición de este documento lleva su
marco (`3utr:` o `tx:`).

Otras entradas versionadas y usadas:

- `aav_casete.fa` — pAAV_G130E_W144Y_mouse_PrP_4xmiR-183T, **5.282 pb**. Es el parental **sin
  módulo** pero **con el intrón vacío de 82 nt**. `[REGISTRO 2026-09-05]`
- `addgene_198131.gb` — pCI_mini-mAgrin-AviTag, 22.810 B, md5
  `108ad0c1d1861e28cf5830eda9254dfd`. De su feature `intron` 1216-1348 sale el intrón
  quimérico. `[DERIVADO 2026-09-08]`
- `#111170` (SGEP) — 8.968 pb, md5 `b15d8091…`. Ancla los contextos de miR-E. `[REGISTRO 2026-08-30]`
- `polya_db_mouse.tsv` — PolyA_DB v4.1 (2025-09-15), mm10, Prnp (Gene ID 19122).
- `mature.fa` — miRBase, release 23.
- `rmsk_mouse.out` + `.tbl`, `rmsk_human.out` + `.tbl` — RepeatMasker 4.0.9 · rmblastn 2.17.1+ ·
  Dfam_3.0.

**Comprobación pasada:** todo fichero se carga verificando checksum; el manifiesto guarda tres
checksums distintos por fila (fichero, secuencia canónica, 3'UTR) y hay test de que no se
confunden. Una longitud anunciada se cuenta sobre la cadena **entregada** — la errata nº 5 fue
un 3'UTR anunciado como «1242 nt verificados» que traía 1246.

---

## 2. Tilado y filtros de ventana

`[DERIVADO 2026-09-08]`, sobre el transcrito entero con su anatomía:

| magnitud | valor |
|---|---|
| ventanas de 22 nt tiladas | **2170** |
| sitios elegibles (agrupados por espaciado de 50 nt) | **95** |
| candidatos elegidos | **11** |

`[REGISTRO 2026-09-07]` Descomposición completa de las 2170: **949** caen fuera del 3'UTR y
**1221** dentro; superan los filtros biofísicos **407**, de los que **287** son del 3'UTR y 120
de fuera.

### Filtros que corren siempre (sin recurso externo)

GC (30-55 %), homopolímero de la **ventana** (≤3), homopolímero de la **molécula**, asimetría
(≥0,5 kcal/mol), G4 y polyA.

**Comprobación pasada:** `G4_diana` **no emite veredicto** — sale `NOT_RUN` y no cuenta para el
veredicto del candidato. `[REGISTRO 2026-08-27]` Su criterio es una expresión regular sin
justificación registrada, y **medido: pasa las 2170 ventanas; nunca ha excluido a nadie**.
Queda pendiente decidir por escrito si es filtro duro o desempate.

### El homopolímero se mide sobre la molécula, no sobre la diana

`[REGISTRO 2026-09-07]` Dos filtros distintos y los dos se conservan: `homopolimero` sobre la
**ventana diana**, `homopolimero_molecula` sobre la **guía y la pasajera**, que es lo que se
sintetiza.

**Resultado:** de las ventanas que superan todo lo demás, **cuatro del panel** fallan el nuevo
y **ninguna** falla el de la ventana:

| candidato | hebra | tramo | origen del tramo |
|---|---|---|---|
| `3utr:143` | pasajera | 4 × C | desapareamiento de la posición 1 |
| `3utr:652` | guía | 4 × T | U forzada de la posición 1 |
| `3utr:735` | pasajera | 4 × C | desapareamiento de la posición 1 |
| `3utr:819` | guía | 4 × T | U forzada de la posición 1 |

Los cuatro tramos los crea una **posición de convenio**, no la diana: por eso el filtro de la
ventana no podía verlos.

**Coste computacional medido:** sólo hace falta plegar el **9,4 %** de las ventanas; la corrida
cuesta **+0,43 s**. El atajo está cruzado contra el camino lento sobre las 2170, con el mismo
veredicto.

---

## 3. Panel confirmado — 11 candidatos

`[DERIVADO 2026-09-08]`

| # | 3'UTR | transcrito | asimetría (cruda) | tercio | riesgo APA | guía (5'→3') |
|---|---|---|---|---|---|---|
| 1 | `3utr:60` | `tx:1009` | **+5,15** | proximal | inmune | `UAAUUGAAAGAGCUACAGGUGG` |
| 2 | `3utr:144` | `tx:1093` | +3,69 | proximal | inmune | `UUCUACUGUACAUUUCCCAGGG` |
| 3 | `3utr:200` | `tx:1149` | +3,80 | proximal | inmune | `UUUAGCACUGGCUGAUGACAGA` |
| 4 | `3utr:359` | `tx:1308` | +4,82 | proximal | techo | `UUUGGUUGUAGAACCCUUUGCC` |
| 5 | `3utr:449` | `tx:1398` | +5,32 | medio | techo | `UUUAGUAAAGAAAGAAUUCCAC` |
| 6 | `3utr:553` | `tx:1502` | +5,86 | medio | techo | `UUAAAGAUCAUUCUAGUGCCCU` |
| 7 | `3utr:673` | `tx:1622` | +4,42 | medio | techo | `UAAGAAACUCAAGUUUCUAGCC` |
| 8 | `3utr:736` | `tx:1685` | +4,26 | medio | techo | `UUAGAAGUACAGAAACAUAGGG` |
| 9 | `3utr:818` | `tx:1767` | +4,55 | medio | techo | `UUUCCCACUUUGGAAUGGAGCC` |
| 10 | `3utr:1018` | `tx:1967` | **+7,65** | distal | techo + estérico penalizado | `UUUAGUACUGGAUGGAACGGCC` |
| 11 | `3utr:1071` | `tx:2020` | +4,28 | distal | techo | `UAAUCCUACGGAACUGAGUGCA` |

**Asimetría total: dos cantidades, las dos ciertas.** Suma **cruda +53,80**; suma **neta
+52,80**, porque `3utr:1018` lleva **−1,00** por solapar el hexámero variante `ACTAAA` (clase
`OTRA`). No se colapsan: una columna que mezcle cruda y neta hace parecer un error de cálculo
lo que es una penalización.

**La posición 1 de la guía es CONVENIO**, no dato: se fuerza una U para que AGO2 cargue esa
hebra. Por eso todas empiezan por U, y esa base no entra en ninguna comparación de identidad.

### Cuota de inmunes al APA: tres, y es un requisito

`[DERIVADO 2026-09-08]` `3utr:60`, `3utr:144` y `3utr:200`.

**Decisión fijada:** el orden voraz por asimetría sacaba **2 de 3** —el mejor de cada paso deja
a los siguientes por debajo del espaciado de 50 nt—, así que la selección busca el **conjunto**
que sí cumple la cuota y lo usa **sólo si mejora**. La cuota es un requisito: los inmunes son la
única reserva si el APA resulta funcional.

`[REGISTRO 2026-09-07]` La cuota bajó de cuatro a tres **por geometría**, no por criterio: al
retirarse `3utr:10` su plaza **no la puede ocupar otro inmune** — los 16 sitios inmunes se
apelotonan entre `3utr:10` y `3utr:200`, y con `60/143/200` puestos ninguno queda a ≥50 nt.

### Retirada declarada

`[REGISTRO 2026-09-07]` **`3utr:10` retirado por el frente `empalme_sitios`.** Es el único de
los once que introducía sitios crípticos que sus hermanas no tienen —un aceptor al **12 %** y un
donante al **6 %** del donante legítimo, sólo con `mvm_actual`—. Sigue siendo un sitio elegible
con sus veredictos; lo que se retiró es su plaza, y no se vuelve a proponer como «el siguiente
que cabe».

**Es el primer candidato que el frente de empalme quita.** El otro caído por un motivo real fue
`tx:1746`, por especificidad (§10), y no estaba en el panel.

### Cobertura por tercios

`[REGISTRO 2026-09-07]`, sobre el 3'UTR:

| tramo | sitios elegibles | panel | caben más | el siguiente |
|---|---|---|---|---|
| proximal `3utr:1-414` | 29 | 4 | 1 | `3utr:309-330` (+2,73) |
| medio `3utr:415-828` | 48 | 5 | **0** | — |
| distal `3utr:829-1242` | 18 | 2 | 4 | `3utr:900-921` (+4,15) |

El tercio medio está **saturado**. El distal no lo limita la geometría sino la cuota.

---

## 4. Poliadenilación alternativa (APA)

### Señales murinas, ancladas a PolyA_DB

`[REGISTRO 2026-08-26]` El mapeo genómico↔transcrito se resolvió **sin coordenadas genómicas**,
exigiendo que las **cuatro** coordenadas publicadas aterricen con el **mismo desfase** sobre un
hexámero de la clase que la propia base declara:

| PAS (mm10) | corte | hexámero | clase | evidencia |
|---|---|---|---|---|
| 131937444 | `3utr:251-271` | `AATATA` en `3utr:236` | variante rara | PSE 21,1 %, AvgRPM 0,55 |
| 131937504 | `3utr:303-323` | `AATAAA` en `3utr:288` | canónica | PSE 23,5 %, AvgRPM 0,34 |
| 131938427 | `3utr:1229-1249` | `ATTAAA` en `3utr:1214` | canónica (terminal) | — |
| 131938392 | banda `3utr:1199-1207` | **AMBIGUO** | — | PSE 70,5 %, AvgRPM 1,65 |

Desfase 3'UTR→mm10 acotado a **131937185-131937193**, dejado como **intervalo**: la banda de
corte mide 20 nt y fijarlo en un entero inventaría precisión.

**Comprobación pasada:** bajo la lectura «PAS = hexámero» **no hay ningún desfase que haga
aterrizar más de una** de las cuatro; bajo «PAS = sitio de corte» aterrizan las cuatro. Lo
desempata la propia leyenda de la base («A[A/U]UAAA motif within 40-nt upstream from the PAS»).

### Fracción de isoforma larga

`[REGISTRO 2026-08-26]` PolyA_DB v4.1, 15 PAS, 5 con expresión:

- **ponderada** `Σ(AvgRPM × PSE) distal / Σ total` = **0,86** ← valor de trabajo
- sin ponderar `Σ(AvgRPM) distal / Σ total` = 0,65

Manda la ponderada porque `AvgRPM` está condicionado a muestras **con** expresión.

**Reserva declarada:** el dato es de **todos los tejidos**. Las neuronas alargan los 3'UTR, así
que **0,86 es un límite inferior** para el modelo.

### Techo de knockdown POR TRAMOS

`[REGISTRO 2026-08-26]`

| tramo (3'UTR) | techo | motivo |
|---|---|---|
| `1-251` | — | inmune: por delante de todos los cortes |
| `252-271` | INDETERMINADO | dentro de la banda de `131937444` |
| `272-303` | **0,91** | por detrás de un corte |
| `304-323` | INDETERMINADO | dentro de la banda de `131937504` |
| `324-1242` | **0,86** | por detrás de los dos proximales |

Los ocho candidatos con techo del panel están todos en el último tramo: **0,86**.

**Decisión fijada:** el truncamiento por APA es un **TECHO**, no un `FAIL` — el APA produce una
mezcla de isoformas. `FAIL` queda reservado a la señal terminal.

### Coste de la promoción por medida

`[REGISTRO 2026-09-07]` Aplicar la medida (que sube el `AATATA` de `3utr:236` a `APA_POSIBLE`):

| | sin la medida | con la medida | diferencia |
|---|---|---|---|
| ventanas elegibles | 271 | 254 | **−17** |
| sitios | 99 | 95 | **−4** |
| sitios inmunes | 21 | 17 | −4 |

**Comprobación que da valor a la cifra:** cuando la piscina encogió por el homopolímero de la
molécula (287→271), **lo que la promoción cuesta no se movió** — las mismas 17 ventanas y los
mismos 4 sitios. Eso demuestra que sólo se cobran las que caen **por esto**.

### Conservación de la señal en humano

`[REGISTRO 2026-08-26]` **El 3'UTR humano (1606 nt) no contiene `AATAAA` ni una sola vez**, así
que la señal murina de `3utr:288` no tiene homólogo posible. No se alinea entre especies —daría
un alineamiento sin sentido con pinta de resultado—: se cuenta.

**Lectura fijada, con las dos cláusulas juntas:** que el gen humano haya prescindido del
hexámero canónico **REBAJA** la probabilidad a priori de que la murina se use, y **NO LA
DESCARTA**.

**Matiz que no se omite:** el 3'UTR humano tiene dos `ATTAAA` (`3utr:955` y `3utr:1167`), las dos
`APA_POSIBLE` **por canonicidad y sin un solo dato de uso**. Condicionan, sobre 311 ventanas
elegibles humanas:

- `3utr:955` → **100 de 311 = 32,2 %** con techo
- `3utr:1167` → **74 de 311 = 23,8 %**, subconjunto de la anterior (74 llevarían **dos** techos)

---

## 5. RT-qPCR de amplicones

`[REGISTRO 2026-08-27, coordenadas revisadas 2026-09-07]`

**Coordenadas declaradas** (contra el corte más temprano, el del `AATATA` de `3utr:236`), 120 nt
cada uno con holgura de 10 nt:

| | 3'UTR | transcrito |
|---|---|---|
| proximal | **`3utr:106-225`** | `tx:1055-1174` |
| distal | **`3utr:282-401`** | `tx:1231-1350` |

**Discrepancia abierta y declarada:** el informe de una corrida con panel emite otro distal
—`3utr:850-969`— porque le pasa las ventanas diana como zonas a evitar. Los dos salen del mismo
generador con distinto argumento, **los dos correctos para su pregunta**, y **ninguno elegido**:
*«son coordenadas de banco y una decisión tomada de paso es una decisión sin contexto»*.

### Limitación permanente del ensayo (no condicional)

**NINGÚN par de amplicones de esta arquitectura puede aislar el evento de `3utr:236`.** La razón
distal/proximal mide **la fracción que sobrevive a los DOS cortes** —el tramo de **0,86**— y **no
confirma el 0,91 del tramo intermedio**. Es geometría: entre las dos bandas quedan **11 nt** para
un amplicón de 120.

Y hay **dos formas** de estar ausente de la isoforma corta, con la misma lectura:

| distal | respecto de la banda de `3utr:288` | ¿aísla 236? |
|---|---|---|
| `3utr:282-401` | la **atraviesa** | no |
| `3utr:850-969` | entero **por detrás** | no |

**Condiciones fijadas:** tejido **sin tratar** (en tratado un amplicón que solape una diana mide
corte por RNAi, no isoformas); RT con **hexámeros aleatorios, nunca oligo-dT** (su sesgo va en la
dirección del resultado buscado); RIN documentado; curva estándar común.

**Control positivo de ensayo obligatorio y hoy `[NOT_RUN]`**: un gen con APA caracterizado en
cerebro murino, en las mismas muestras y con la misma arquitectura. Sin él, «casi todo isoforma
larga» no se distingue de un ensayo **ciego** a las isoformas cortas.

**Salida si alguna vez hace falta el tramo intermedio:** 3'RACE o secuenciación de extremos. Es
línea abierta, no tarea: hoy no hay ningún candidato ahí.

---

## 6. Conservación ratón/humano y la vía del ORF

### El 3'UTR no da un shmiR único

`[REGISTRO 2026-08-26]` Único bloque de identidad exacta ≥22 nt entre los dos 3'UTR: **26 nt**,
`TTTTCTATATTTGTAACTTTGCATGT`, ratón `3utr:1138-1163` / humano `3utr:1507-1532`.

**De las 5 ventanas de 22 nt que caben DENTRO, ninguna** supera los filtros de secuencia, y **con
los mismos motivos en las dos especies**: GC en las cinco, asimetría en cuatro, homopolímero en
una.

> **CONSECUENCIA FIJADA: no existe un shmiR único válido para ratón, Tg650 y clínica por la vía
> del 3'UTR.** Eso cambia la arquitectura del programa, no dos plazas del panel.

**Comprobación de método:** se miran las ventanas **CONTENIDAS**, no las que solapan. Contar las
que solapan dio un «sí hay ventanas elegibles» **falso** en el informe del ratón mientras el del
humano decía lo contrario.

### La vía ORF

`[REGISTRO 2026-08-26]` Identidad exacta ≥22 nt entre los dos ORF: **4 bloques**, 16 ventanas
contenidas, **2 superan los filtros de secuencia** — ORF ratón 523/524 (`tx:707`/`tx:708`), ORF
humano 526/527, misma diana `GTGCACGACTGCGTCAATATCA`.

**Verificado traduciendo los ORF del repositorio:** la ventana empieza en el **codón 175**
(ratón) / **176** (humano), en marco, y codifica **`VHDCVNIT`** — el mismo péptido. Su posición 4
es una cisteína: **C178** (ratón) / **C179** (humano).

**Comprobación sin estructura:** PrP tiene **un solo** puente disulfuro (C178-C213 murino); en el
ORF murino sólo hay tres cisteínas (22, 178, 213) y la 22 está en el péptido señal, así que **no
hay un segundo par posible**. Dos anotaciones previas quedaron corregidas: la numeración «codón
143» era contaminación con el W144Y del plásmido, y el «segundo puente disulfuro» no existe.

**Propiedad de alcance fijada:** una guía contra esa ventana **alcanza PRNP humano** —y por tanto
Tg650 y líneas humanizadas— **y no alcanza el transgén** del casete, que está codón-optimizado.
Es el reparto que hace falta.

**Estado:** esas dos ventanas **no están aprobadas, están preseleccionadas** — seed, repetitivos
y especificidad siguen `[NOT_RUN]`, y **gnomAD sobre esa ventana es obligatorio** y no se ha
hecho: la selección purificadora restringe los cambios **no sinónimos**, y son los **sinónimos**
los que rompen el apareamiento sin tocar la proteína.

---

## 7. Los dos intrones

`[DERIVADO 2026-09-08]`

### `mvm_actual` — se ensambla de piezas versionadas del plásmido receptor

| pieza | nt | secuencia |
|---|---|---|
| `exon5` | 5 | `AAGAG` |
| `MVM5` | 40 | `GTAAGGGTTTAAGGGATGGTTGGTTGGTGGGGTATTAATG` |
| `MVM3` | 42 | `TTTAATTACCTGGAGCACCTGCCTGAAATCACTTTTTTTCAG` |
| `exon3` | 5 | `GTTGG` |

Intrón **vacío = 82 nt**; **montado = 284 nt** (296 con los sitios de restricción dentro).

### `intron_quimerico` — 133 pb

Extraído de `addgene_198131.gb`, feature `intron` 1216-1348, md5 de la feature
`5cd85dcf763f8e7df6f4e84ada503be0`:

```
GTAAGTATCAAGGTTACAAGACAGGTTTAAGGAGACCAATAGAAACTGGGCTTGTCGAGA
CAGAGAAGACTCTTGCGTTTCTGATAGGCACCTATTGGTCTTACTGACATCCACTTTGCC
TTTCTCTCCACAG
```

Quimera de **β-globina humana** (donante `GTAAGT`, consenso perfecto) e **inmunoglobulina de
cadena pesada** (aceptor). Sus cuatro elementos, derivados:

| elemento | posición | secuencia |
|---|---|---|
| donante | 1-2 | `GT` |
| punto de ramificación | 100-104 **y** 104-108 | `CTTAC` y `CTGAC` — **dos candidatos, AMBIGUO** |
| tracto de polipirimidinas | 119-129 | `CCTTTCTCTCC` (11 nt, frente a 9 del MVM) |
| aceptor | 132-133 | `AG` |

**Corrección registrada:** se llamaba `quimerico_cmv_globina` y se describía como «CMV /
β-globina». Las dos cosas estaban mal: CMV es el **promotor** del plásmido (497-1080), no parte
del intrón.

**Punto de inserción del módulo: posición 49** `[REGISTRO 2026-08-30]`, de la ventana admisible
3-99. **Criterio medido:** sólo **15 de 97** posiciones conservan la horquilla, y **las que
ganaban por separación pura (52 y 53) no están entre ellas**. Entre las dos finalistas decidió la
separación al elemento más frágil: la 69 deja el punto de ramificación a 34 nt y la 49 a 54. La
**69 queda registrada como descartada**. Montado: 133 + 149 = **282 nt**, con los cuatro elementos
intactos a los dos lados.

### El tercero, retirado

**`mvm_sin_criptico`** — diseñado para romper el donante críptico `GTGAGCG`. **Retirado de la
matriz** `[REGISTRO 2026-09-05]`: ese sitio puntúa **0,0000** en las veinte construcciones con las
dos arquitecturas. *«Un intrón que arregla un problema que no existe.»* Sigue en el registro con
su motivo y su condición de vuelta.

### El donante críptico `GTGAGCG`

`[REGISTRO 2026-08-30]` Está en el **flanco 5' del andamio** miR-E, así que **viaja con cualquier
guía**: intrón +98 en el MVM, +87 en el quimérico.

- **Por criterio de secuencia** empata con el donante legítimo: score **5 contra 5**.
- **Por SpliceAI** puntúa entre **4e-08 y 3e-07** en las diez construcciones.

**Consecuencia de método fijada:** *el consenso posicional **sobrestima** porque cuenta
coincidencias sin contexto*. No jubila el criterio de secuencia —sigue enumerando candidatos sin
nada instalado— pero **no puede afirmar que un sitio es un donante**.

**Lo que la secuencia SÍ cierra:** entre ese donante y el aceptor legítimo hay **13 `AG`** y
**ninguno es utilizable** — el legítimo tiene **9 pirimidinas contiguas** y el mejor críptico llega
a **3**. Eso cierra los empalmes que cortarían **por dentro de la horquilla**, y **NO cierra** el
riesgo del donante críptico: ése no necesita aceptor críptico, el legítimo está aguas abajo. Un
empalme `+98 → +295` dejaría **97 nt** de intrón dentro: la banda intermedia, la confundible en un
gel.

### Matriz intrón × andamio

`[REGISTRO 2026-08-30]` Sobre `mvm_actual` × `mir_e`, el único par evaluable: **un** donante
críptico en los 149 nt del módulo (el conocido), **ningún** aceptor utilizable, y un `YTNAY`
(`TTGAC` en +32) que **no define ningún intrón** — va aguas arriba del donante. Se comprueba el
**orden**, no sólo la presencia.

Geometría donante→punto de ramificación: **256 nt** (MVM) y **249-253** (quimérico) — este eje
**no discrimina**, y los dos quedan muy por encima del rango típico de mamífero (18-100).

**Retirado por su autor** `[2026-09-05]`: la afirmación previa de que el quimérico estaba en
314-318 salía de aplicarle a un intrón que se monta con 149 los 214 nt que se intercalan en el MVM.

---

## 8. SpliceAI — corrida de veinte construcciones

`[REGISTRO 2026-09-05]`, `data/medido/spliceai_dos_intrones_2026-09-05.tsv`, validada al entrar por
md5 y por nombre una a una. Panel de diez × dos arquitecturas.

| | donante legítimo | rango | **dispersión** | aceptor legítimo | rango | dispersión |
|---|---|---|---|---|---|---|
| `mvm_actual` | 0,873 | 0,783–0,925 | **18,1 %** | 0,831 | 0,778–0,858 | 10,3 % |
| `intron_quimerico` | 0,966 | 0,956–0,973 | **1,8 %** | 0,990 | 0,985–0,994 | 0,9 % |

**El hallazgo no es la media, es la dispersión.** La media compara dos moléculas; la dispersión
dice qué pasa al cambiar de guía. **La guía modula el empalme del MVM (18 %, con el módulo a más
de 100 nt) y no modula el del quimérico.** Para una matriz de diez guías eso elimina una variable
entera.

### Crípticos por encima del 5 % del donante legítimo

- `mvm_actual`: un **aceptor** en `construccion:3261` (**11,9 %**, en 1 de 10, `3utr:959`) y un
  **donante** en `construccion:3353` (6,1 %, en 1 de 10).
- `intron_quimerico`: **ninguno**.
- Siete en el **contexto 5'** salen en las **veinte**: vienen con el plásmido, no los introduce
  ninguna guía.

**Decisión de denominador fijada:** se normaliza contra el donante legítimo **de su propia
construcción**, no contra la media. Contra la media el peor caso baja a 10,7 %, y ese peor caso es
justo la construcción con el legítimo más bajo: dividir por la media **suaviza precisamente el
caso que importa**.

### Un sitio que DEPENDE de la guía

Es lo que este frente existe para encontrar, y **el `GTGAGCG` no lo es**. El que sí: el aceptor de
`construccion:3261`, dentro del módulo de 149 nt y sobre un `AG` real. **El valor no es la
alarma** —queda muy por debajo del 50 % que dispara el aviso—: lo que vale es que **existe un eje
por el que el módulo modula el empalme y ahora está medido**. Criterio `[DECLARADO]`: **una razón,
no un corte absoluto** (`GUIDE_DEPENDENT_RATIO = 2`).

### Limitaciones de uso fijadas

**SpliceAI no fue entrenado para esto** —secuencia genómica humana, ventana de 10.000 nt, para
predecir el efecto de **variantes**—. Por tanto: las puntuaciones **absolutas no son
interpretables**, **no hay umbral que aplicar**, y sólo vale la comparación **relativa contra un
referente interno** (el donante legítimo del mismo intrón, en la misma corrida). Un legítimo de
cero **aborta** en vez de dividir.

**Errata de convención registrada (nº 99):** la app apunta a la **G de `GT`** y SpliceAI a la
**última base exónica** (`donante − 1`). El desfase normalizó 107.680 filas contra un referente
inexistente (`2e-07`). Cerrado con la convención declarada en la cabecera del FASTA, traducción en
la frontera, y un guardia que compara con el **vecindario** (±3) en vez de con un umbral —
calibrado: con el marco bueno la base declarada vale 0,66-0,87 y ninguna vecina pasa de 1,1e-05.

---

## 9. Accesibilidad estructural del intrón (ViennaRNA)

`[REGISTRO 2026-09-06]` Plegadas las **22 construcciones** (panel de once × dos arquitecturas),
por **función de partición** — no por la estructura de MFE, que da 0 o 1 disfrazado de
probabilidad. Fracción media sin aparear:

| elemento | `mvm_actual` | `intron_quimerico` | gana |
|---|---|---|---|
| donante | **0,889** | 0,533 | mvm_actual |
| **punto de ramificación** | **0,257** | **0,355** | quimérico |
| tracto de polipirimidinas | 0,594 | 0,547 | mvm_actual |
| aceptor | 0,836 | **0,994** | quimérico |

**Hallazgo:** el **punto de ramificación es el elemento menos accesible en las DOS
arquitecturas**, y por bastante. Es una propiedad del **elemento**, no del intrón.

**El contraste queda 2-2 y no se redondea a un ganador.** El quimérico deja el punto de
ramificación más libre; su **donante** queda bastante más secuestrado. Las dos frases van juntas o
mienten las dos.

**La guía no mueve ninguno de los cuatro:** dispersión **0,82 %** en el peor caso (punto de
ramificación del MVM) y **0,00 %** en el quimérico. Este eje **no discrimina entre candidatos** —
compara arquitecturas.

**Control adversario que impide leerlo como ceguera:** un módulo complementario al extremo 5'
lleva el donante de **0,89 a 0,00**. El análisis cazaría una guía que secuestrara un elemento; lo
que dice la medida es que ninguna de las once lo hace.

### Contradicción registrada, no reconciliada

Del **mismo** donante legítimo, SpliceAI da mejor al quimérico (0,966 vs 0,873) y el plegado al
MVM (0,533 vs 0,889).

> **No se promedian y no se reconcilian: la secuencia dice que el sitio EXISTE, el plegado dice si
> se puede USAR. Son dos preguntas, y que discrepen es INFORMACIÓN.**

SpliceAI sólo puntúa dos de los cuatro elementos, y **su silencio en los otros dos no es
acuerdo** — sale nombrado.

### Riesgo compartido

Que el punto de ramificación sea el menos accesible **en las dos** y que la geometría
donante→punto esté **fuera del rango típico en las dos** apuntan al mismo sitio por dos caminos:
es el **candidato a causa común si el empalme falla en las dos**, y no lo arregla cambiar de
arquitectura — lo movería acortar lo que se intercala.

### Decisión de arquitectura fijada

`[REGISTRO 2026-09-07]` **Van las dos a síntesis.** *«Dos arquitecturas que hay que probar las
dos, porque ninguna medida las separa de forma unánime y el gel es quien decide.»* Cada eje manda
a un lado y **ninguno de esos números predice el empalme**. Lo que se retira es la conclusión
agregada, no las medidas.

### Lecturas de banco que cierran este frente — las cuatro `[NOT_RUN]`

1. **RT-PCR de empalme**, con cuatro condiciones y ninguna opcional: RNA **citoplásmico**,
   selección por polyA, DNasa y control **sin RT**, y lectura de **PROPORCIÓN** corta/larga con
   dos referencias en la misma tanda. **Corrección registrada (2026-09-02):** «banda larga =
   retenido» es **falso** — el pre-mRNA sin empalmar existe siempre.
2. **Western L42 normalizado por vg-qPCR.**
3. **Parental SIN INTRÓN** en la misma tanda, como techo de expresión. `aav_casete.fa` **no
   vale**: lleva el intrón vacío de 82 nt.
4. **Secuenciar la banda corta** — es **la que cierra el frente**: la lectura de éxito es la
   **secuencia de la unión exón-exón**, no la altura de la banda.

**Coordenadas derivadas** `[REGISTRO 2026-08-26]`: donante `casete:3134`, aceptor `casete:3215`;
ventanas donde **buscar** cebadores `casete:3064-3123` y `casete:3226-3285`, comprobadas como
únicas en el plásmido. **No se emiten cebadores.** **La especificidad de vector la da el cebador
de aguas ARRIBA, y sólo ése**: la ventana de aguas abajo entra en el ORF de PrP y amplificaría
también el Prnp endógeno. La cifra que no depende de la longitud de los cebadores es la
**DIFERENCIA**: 296 pb en el terapéutico, 82 en el parental.

### uAUG del intrón retenido

`[REGISTRO 2026-08-26]` Si el intrón se retiene hay **dos** modos de fallo: la horquilla queda en
el 5'UTR **y** el ribosoma encuentra AUG antes del legítimo. Con la horquilla de referencia son
**ocho** uATG, en tres categorías:

- **`EXTENSION_N_TERMINAL`** (el peor: PrP con cola, confundible en un Western) — **ninguno**,
  comprobado. El único en marco es `+16` (`TAAGGGATG`, Kozak fuerte) y **para a los 10 codones**.
- **`uORF_SOLAPANTE`** — `+210` y `+237`.
- **`uORF`** — el resto.

**Comprobado por traducción, no por el nombre del fichero:** el ATG está en `casete:3253`, a 37 nt
del aceptor, y el ORF da **254 aa** que empiezan por `MANLGYWLLALFVTMW` con **G130E** y **W144Y**.

---

## 10. Especificidad, colisión de seed y carga de off-targets

### Especificidad (BLAST) — el único candidato caído por un motivo real

`[REGISTRO 2026-09-05]` Corrida sobre 88 candidatos, **176 consultas**. **Cae uno**, con las dos
hebras: **`tx:1746`**, con ocho aciertos que son **21 de 22 con un hueco** (`identity 95.455`,
`mismatches 0`, `gapopen 1`). Los ocho son **variantes de transcrito de Adar**.

**Lo que decide, y va escrito:** ADAR es maquinaria del propio sistema de ARN de doble cadena
—lo que el vector produce—, es esencial en neurona (edita GluA2 en Q/R) y su pérdida daría
**neurodegeneración**, que en un experimento de priones **se leería como toxicidad del shmiR o
como la enfermedad progresando**.

> **Las dos frases van juntas o mienten las dos: «descarta 1 de 88» suena a filtro inútil y
> «atrapó un shmiR anti-ADAR» suena a filtro decisivo — es las dos cosas.**

`tx:1746` **no está en el panel**: los once siguen limpios en este eje.

**Erratas de criterio registradas:** `mismatches = 0` **no** dice que el acierto sea perfecto
(nº 57); un parcial de 13 nt no es un off-target y el mínimo se **deriva** de la sonda; y
`ANTISENSE` significa cosas distintas en el escáner propio y en `-outfmt 6`, por lo que la
orientación dejó de decidir el veredicto y pasó a ser un **invariante de montaje** (guía →
antisentido, pasajera → sentido, contra su propia diana).

### Colisión de seed

`[REGISTRO 2026-08-26]` Dos capas: **núcleo** (`FAIL` duro, diez miARN de cerebro murino, en
código y con autorización escrita — compartir seed con uno de ellos **no da off-targets
dispersos, secuestra un programa regulador neuronal completo**) y **capa ampliada** (`AVISO`, de
fichero, con referencia y umbral o queda `NOT_RUN`).

**Tasas base derivadas del fichero cargado** (no tecleadas):

| filtro | maduros | seeds distintas | espacio | tasa |
|---|---|---|---|---|
| `mmu-`, ventana **2-8** | 1988 | 1593 | 16384 | **9,7 %** |
| `mmu-`, ventana **2-7** | 1988 | 1274 | 4096 | **31,1 %** |
| `mmu-` + `hsa-`, 2-8 | 4777 | 3127 | 16384 | 19,1 % |

**Resultado de la corrida de referencia** (20 consultas): **cero FAIL de núcleo, cero miR-30**, y
**tres AVISO** — `3utr:143` (`mmu-miR-7653-3p`), `3utr:359` (`mmu-miR-5615-5p`) y la pasajera de
`3utr:819` (`mmu-miR-136-5p`). **Tres de veinte es el 15 % contra una tasa base del 10 %: es lo
que predice el azar**, y por eso la cifra va al lado.

**La familia miR-30 se señala aparte**: el andamio es miR-E, derivado de miR-30a, así que una
colisión ahí es lectura distinta y peor.

### Carga de off-targets por seed

**Cuatro clases y NUNCA un total** `[DECLARADO]`: `8mer`, `7mer-m8`, `7mer-A1`, `6mer`. La
represión esperada de un 8mer y la de un 6mer no se parecen. Las cuatro comparten un núcleo de
6 nt y son **excluyentes por construcción** (test: la suma de las cuatro es exactamente el número
de apariciones del núcleo).

**Cada conteo va con tres referencias:** percentil contra una **nula por permutación del propio
heptámero** (≥10.000 sorteos, semilla declarada), **controles biológicos** (`miR-124-3p`,
`miR-9-5p`, `let-7a-5p`, que dan **magnitud** y no llevan percentil) y **autoconteo** sobre la
propia diana (esperado 1).

**Hallazgo del autoconteo** `[REGISTRO 2026-09-06, re-medido]`: **4 del panel** tienen un **segundo
sitio de seed en el propio 3'UTR de Prnp** — `3utr:449` (núcleos en `3utr:464` y `1033`), `553`
(`460`, `568`), `819` (`148`, `834`) y `1018` (`464`, `1033`). Y **`449` y `1018` comparten
núcleo**: en este eje **no son dos apuestas independientes**.

**Las tres limitaciones, todas en la misma dirección** `[DECLARADO]`: sin ponderar por
conservación, por APA ni por expresión. **Conclusión pegada: el número es un LÍMITE SUPERIOR.**

**Uso fijado: DESEMPATE, NUNCA FILTRO.** `verdict_for` **no puede** devolver `FAIL`.

**Segundo aviso rojo de la selección:** dos candidatos que comparten núcleo de 6 nt no son
independientes **aunque el espaciado los dé por buenos** — el espaciado mide nucleótidos, no
seeds. Caso real: `tx:1398` y `tx:1967` comparten el núcleo `TACTAA` con heptámeros distintos.

---

## 11. Elementos repetitivos

`[REGISTRO 2026-08-26]`

- **Ratón**: **una** repetición, `(CTC)n` en `tx:892-936`, **dentro del CDS**. O sea: **el 3'UTR
  murino no tiene ni un elemento repetitivo**, con los ceros explícitos por familia en el `.tbl`
  (SINEs 0, Alu/B1 0, B2-B4 0, LINEs 0, LTR 0).
- **Humano**: **una**, `(TA)n` en `tx:2097-2130` = `3utr:1268-1301`, que **solapa 5 ventanas
  elegibles** (`3utr:1247`, `1249`, `1250`, `1251`, `1252`).

**Caso con triple motivo:** esas cinco caen por los **tres** ejes a la vez — repetitivo,
polimórfico y con **techo** por quedar por detrás de las dos `ATTAAA` humanas. Tres razones
independientes: no se recuperan arreglando una.

**Mordida de la máscara, tres cifras** (elementos totales / dentro del 3'UTR / ventanas elegibles
solapadas): ratón **1 / 0 / 0**, humano **1 / 1 / 5**. Es una propiedad de los **transcritos**, no
del pipeline.

**Y `repeticion_polimorfica` es OTRO motivo, no una etiqueta del mismo:** el primero apunta a
estabilidad del genoma AAV y a una guía con miles de sitios; el segundo a **viabilidad clínica** —
un microsatélite varía en número de repeticiones entre individuos, así que habría respondedores y
no respondedores **por variación de LONGITUD**. **gnomAD anota sustituciones y capta mal la
variación de longitud**, así que el filtro de variación **no cubre este riesgo**.

**Predicción refutada y anotada con su nombre** `[2026-08-26, Joaquín Castilla]`: se predijo que
los 45 pb serían la carrera de A de `3utr:480-500`. **No lo es** — es un `(CTC)n` en el CDS, y la
carrera más larga del 3'UTR murino son 10 A que acaban en `3utr:507`, donde RepeatMasker no marcó
nada. **No hay convergencia.**

**Demostración registrada con md5 como evidencia:** `rmsk_human.out` y
`rmsk_human_WRONG_SPECIES_mouse_lib.out` son **el mismo fichero byte a byte**
(`bcc33dbc7a65e74690f5f9d1fb270035`). Una corrida válida y una contra la biblioteca equivocada
producen `.out` **indistinguibles**; la diferencia vive **sólo** en el `.tbl`. Por eso el resumen
es un **requisito**, no una precaución.

---

## 12. Convergencia con un método externo

`[REGISTRO 2026-08-26]` Dos métodos independientes sobre el mismo 3'UTR verificado (nuestra
cascada y miRarchitect), 24 sitios externos contra los 90 elegibles de entonces:

- **0 sitios exclusivos** de la fuente externa que superen nuestros filtros duros
- **4 coincidencias exactas** (`3utr:221`, `735`, `810`, `1018`) — la de 735 es la misma ventana
  base a base
- **6 a 1 nt** (`337↔338`, `516↔517`, `552↔553`, `1017↔1018`, `1024↔1025`, `1075↔1076`)
- el único externo sin choque es `3utr:1200`, que **falla nuestro propio filtro de polyA**

> **Lectura fijada: NO es una validación cruzada.** Donde sólo cabe coincidir, coincidir no
> demuestra nada. La convergencia externa **no discrimina entre candidatos y no puede usarse para
> elegir**. Es un dato de **calibración de nuestra cascada**, y va al suplementario.

**Contraste que da sentido a la cifra:** contra los **6 elegidos** de entonces salían 9 filas sin
choque = **7 plazas**; contra los **90 sitios elegibles**, **ninguna**. La referencia del
espaciado son los sitios elegibles, no el panel.

**Sesgo de baja complejidad descartado** como explicación del score externo: correlación carrera
máxima/score `r = +0,154`, y homopolímeros de ≥4 repartidos 5/15 entre los mejores y 3/9 entre los
peores — el mismo 33 %.

**El PUESTO no se transfiere:** 20 de los 21 sitios compartidos entre dos corridas de miRarchitect
cambian de puesto con el score **idéntico**, sólo porque una lista tiene 26 filas y la otra 24. El
puesto es propiedad de la LISTA, no del sitio.

---

## 13. Construcciones y fragmento de síntesis

### Andamio y regla de la pasajera

`[REGISTRO 2026-08-30]` miR-E completo en los cuatro ejes: secuencia verificada, contextos
anclados contra **#111170** (`contexto5` en 1739-1758, `contexto3` en 1856-1875, **97 nt exactos**
de andamio en 1759-1855), regla de pasajera y plásmido con md5.

**La regla de la pasajera es ESTRUCTURAL, no una tabla:** se pliegan las cuatro bases posibles
para la posición 1 y se elige una cuyo 97-mero reproduzca la notación punto-paréntesis de SGEP;
`C > A > G > T` sólo desempata. **La tabla por terminación está descartada por escrito** — le
faltaba el apareamiento tambaleante `G:U`.

**Consecuencia operativa:** sin ViennaRNA **no se emite ADN**. El núcleo degrada a `NOT_RUN`, pero
la regla de la pasajera degradaría a la tabla descartada, y esa pasajera va **dentro del módulo de
149 nt**. Un `NOT_RUN` que produce ADN sintetizable no es un `NOT_RUN`.

### Las cinco longitudes, cada una con su etiqueta

`[REGISTRO 2026-09-06]`, sobre el MVM:

| etiqueta | nt | qué es |
|---|---|---|
| intrón vacío | **82** | de `GT` a `AG`, sin módulo — el que se compara con el rango típico |
| intrón montado | **284** (296 con sitios) | con el módulo dentro — el que se compara entre arquitecturas |
| feature anotada | **92** | lo que se **selecciona** en SnapGene (incluye 5+5 nt de exón) |
| fragmento de síntesis | **294** (306 con sitios) | lo que se manda a sintetizar |
| crecimiento del plásmido | **202** (214 con sitios) | lo que crece al pegar |

**Los diez nucleótidos de la feature, medidos antes de emitir nada:** la feature son 92 nt y el
intrón vacío 82; los diez de más son `exon5` (`AAGAG`) y `exon3` (`GTTGG`). **Pegar 82 sobre una
selección de 92 borraría 10 nt de exón.**

### Decisiones sobre el fragmento

`[REGISTRO 2026-09-05]` Lo que se sintetiza deja de ser el módulo NheI–SacI y pasa a ser el
**intrón completo con su contexto exónico**, y **los sitios de restricción salen por defecto**:
con el fragmento sintetizado entero no cortan nada. Siguen disponibles con
`--fragmento-con-sitios`: **retirar algo por defecto es una decisión; quitarlo del código es
perder la opción.**

**Los 15 nt de cada extremo están CALIBRADOS** `[REGISTRO 2026-09-06]`: los dos donantes empiezan
por `GTAAG` y el contexto exónico aporta otros 5, así que los primeros 10 nt son idénticos en las
dos arquitecturas — **divergen en el 11** por un extremo y **en el 9** por el otro. Con 5 o con 10
el guardia seguiría aprobando las cuatro casillas de la matriz.

### Piezas del vector, auditadas

`[REGISTRO 2026-09-02]` `MluI`, `MVM5`, `MVM3`, `AgeI`: **únicas** en `aav_casete.fa`, confirmadas.
`exon5`/`exon3` miden 5 nt y aparecen 3 y 8 veces: se exige que estén **pegadas a su MVM**.
**Hallazgo: `NheI` y `SacI` NO están en el receptor depositado** — coherente, porque el parental
lleva el intrón vacío sin sitio de clonaje. Lo que estaba mal era la frase que les atribuía ese
origen; se corrigió y **se las sigue buscando**.

**XhoI y EcoRI viajan dentro del módulo**, heredadas de los contextos de SGEP, y en el plásmido
final **no son únicas**: la hoja de pedido lo dice siempre.

### El casete que se pasa tiene que ser el que la célula MADURA

`[REGISTRO 2026-08-26]` Si el casete llevara el módulo y se pasara el genoma con el intrón dentro,
**toda guía daría impacto contra su propia horquilla** y el filtro tumbaría el panel entero por un
artefacto, con un motivo además literalmente cierto. Se detecta **por secuencia**. El casete de hoy
es el **parental sin módulo**, comprobado.

---

## 14. Controles del experimento

`[REGISTRO 2026-08-31]` Dos construcciones de primera clase, con autorización escrita y acotada
(permutar posiciones 2-22; sustituir 2-3 bases en 2-8; **nunca** andamio, loop, contextos,
espaciadores, intrón ni guías nuevas).

### Scrambled

**Hallazgo que fija el criterio: pasar el filtro NO es ser equivalente.** Las cinco primeras
permutaciones pasaban todo y tenían asimetría **+0,8 a +3,9 frente a los +7,65 del original**.
Sobre 2000 permutaciones la asimetría tiene **mediana 0,67** y rango **−6,45 a 8,05**.

Por eso hay un **segundo umbral con frente propio** (`equivalencia_asimetria`, tolerancia
**1,5 kcal/mol**): aquí se busca **parecerse**, no maximizar.

**Medidas de «sin diana», dos preguntas y no una:** tramo contiguo máximo (moda **6**, sólo 1 de
2000 llega a 12; **la guía original da 22**, que es el control de la medida) y **sitios de seed** —
**451 de 2000** sí los tienen, o sea que ese filtro muerde.

**`3utr:449` NO admite scrambled, y se demuestra en un paso:** el GC es **invariante bajo
permutación**. La causa: los umbrales biofísicos están definidos sobre la **diana**, y la guía
difiere en la posición 1 (convenio) — su GC baja de **0,318 a 0,273** y cruza el mínimo de 0,30. El
candidato es legítimo; lo que no admite es esa vía.

### Seed-mismatch

Enumerado entero (no sorteado): **189** variantes con 2 cambios, **945** con 3. Medido sobre
`3utr:1018`:

| | k=2 | k=3 |
|---|---|---|
| variantes | 189 | 945 |
| limpias | 62 | 198 |
| **racha de seed intacta mínima** | **2** | **1** |
| limpias con esa racha | **1** | **7** |
| chocan con el núcleo de abundantes | **0** | **8** |

**Lo que la medida añade a la intuición:** el residuo de reconocimiento no lo decide cuántas bases
se tocan, sino **dónde caen**. Y el riesgo que se temía de k=3 está **medido y filtrado**: 8 de 945
chocan con el núcleo y ninguna de ésas se emite. **No se elige aquí.**

### Un criterio que resultó no discriminar

**El plegado del 97-mero no discrimina nada**, y va dicho en la salida: **0 de 2000** permutaciones
y **0 de 1134** variantes lo rompen. `passenger_from_guide` ya **elige** la base de la posición 1
para que el 97-mero reproduzca SGEP, así que preguntarlo después vuelve a preguntar lo que era
condición para montarlo. Se conserva como guardia; **un `PASS` ahí no es evidencia**.

### Los seis brazos: aviso, no impedimento

**Scrambled y seed-mismatch no son intercambiables:** el primero controla «tener UN shmiR»
(saturación de la maquinaria, respuesta a dsRNA, carga viral); el segundo, «tener ESTA guía».
Quedarse con uno deja viva una explicación alternativa.

---

## 15. Estado de los frentes

**Un frente es un filtro que se cierra CONSIGUIENDO algo.** Hoy son **diez**. Un frente sólo se
considera cerrado si **cubre todo el panel**; un `FAIL` cierra igual que un `PASS` — se cierra
consiguiendo *la respuesta*, no una buena.

| frente | estado | qué lo cierra |
|---|---|---|
| `fraccion_isoforma_larga` | **CERRADO** | PolyA_DB v4.1 (0,86, límite inferior) |
| `repeticiones` / `repeticion_polimorfica` | **CERRADO** | `rmsk_mouse.out` + `.tbl` |
| `seed` (colisión) | **CERRADO** | `mature.fa` release 23 |
| `transgen` | **CERRADO** | `aav_casete.fa` |
| `empalme_sitios` | **PARCIAL** | corrida de SpliceAI 2026-09-05: cubre **9 de 11** |
| `seed_colision` | **PARCIAL** | corrida del panel viejo: `3utr:144`, `736`, `818` en `SIN_CONSULTAR` |
| `especificidad` | **ABIERTO** | base de RefSeq local con md5 `[NOT_RUN]` |
| `offtarget_seed` | **ABIERTO** | `transcriptoma_3utr.fa` `[NOT_RUN]` |
| `empalme_intron` | **ABIERTO — no lo cierra ningún fichero** | las cuatro lecturas de banco (§9) |

**Consecuencia fijada:** mientras queden frentes abiertos, **los candidatos salen `INCOMPLETE` y la
selección es PROVISIONAL**. No se pide oligo hasta que tengan veredicto.

**Distinción de estados que un informe no debe colapsar:**

| estado | significa | cómo se arregla |
|---|---|---|
| `PASS` / `FAIL` | corrió con todos sus recursos | — |
| `NOT_RUN` | no llegó a ejecutarse: falta un recurso | consiguiéndolo |
| `SIN_CONSULTAR` | hay corrida y a este candidato no se le preguntó | repitiendo con otro alcance |
| `NO_CIERRA` | la corrida se hizo y no cierra el frente | repitiendo, no empezando |
| `NO_PEDIDO` | no se midió por coste, y es una decisión | nada que conseguir |
| `NO_APLICA` | la pregunta no va con ese candidato | — |
| `OBSOLETO` | el fichero de la corrida ya no es el del depósito | revalidando |

---

## 16. Decisiones de diseño fijadas (salidas, no procesos)

1. **Panel de once**, `3utr:` 60, 144, 200, 359, 449, 553, 673, 736, 818, 1018, 1071.
2. **Cuota de tres inmunes al APA** como **requisito**, no como preferencia.
3. **Espaciado mínimo de 50 nt**, y **no se baja** para meter un inmune más: compra independencia
   entre apuestas, no número de apuestas.
4. **`3utr:10` retirado** por el frente de empalme, con motivo, fecha y autor, aplicado por md5 del
   3'UTR.
5. **Filtro de polyA escalonado**; el APA es **TECHO**, no veto.
6. **La medida entra siempre que haya medida**: `measured_apa=None` **aborta**; excluirla exige un
   motivo escrito que viaja al informe.
7. **Homopolímero medido sobre la MOLÉCULA**, conservando el de la ventana: dos medidas distintas y
   la comparación tiene valor.
8. **Las dos arquitecturas de intrón van a síntesis**; se retira la conclusión agregada, no las
   medidas.
9. **`mvm_sin_criptico` retirado** de la matriz, conservado con su condición de vuelta.
10. **Punto de inserción del quimérico: 49**, con la 69 registrada como descartada.
11. **El fragmento de síntesis es el intrón completo**, con los sitios de restricción **fuera** por
    defecto.
12. **El ensayo de RT-qPCR se queda con ALCANCE DECLARADO**: mide el 0,86 y dice, con dos frases,
    qué mide y qué no.
13. **No existe shmiR único ratón/humano por la vía del 3'UTR**; la vía ORF queda preseleccionada y
    sin cerrar.
14. **La carga de off-targets es desempate, nunca filtro**; la convergencia externa no ordena.
15. **No se generan los `.dna` montados: se genera su comprobación**, por secuencia.

---

## 17. Limitaciones declaradas y trabajo pendiente

### Limitaciones que van pegadas a los resultados, no al pie

- **La asimetría usa un proxy heurístico**, no una energía libre de dúplex.
- **El flanco de ±10 nt del eje estérico no tiene base medida**: es un umbral operativo, y la huella
  real de CPSF/CstF es mayor. Por eso `3utr:200` sale **en los dos ejes** —
  `inmune_truncamiento = SI` / `esterico = PENALIZADO`— con la sensibilidad pegada: queda **4 nt**
  por delante de la zona prohibida, y **con un flanco de 15 también caería**.
- **La accesibilidad es desempate, nunca filtro**: es el criterio peor predicho del pipeline, y si
  las dos ventanas de contexto (±80 y ±150) discrepan, el número no sirve.
- **El andamio miR-E está verificado en el 97-mero y sólo ahí**; los flancos extendidos del pri-miR
  siguen sin decidir.
- **`3utr:236` y `3utr:288` son `APA_POSIBLE` por vías distintas** —medida y canonicidad— y la
  salida nunca las confunde: `APA_POSIBLE (medido, PolyA_DB v4.1)` frente a
  `APA_POSIBLE (canónico, asumido)`.
- **El humano está en MODO ASUMIDO**: la tabla murina se aplica por md5 del 3'UTR, así que sobre el
  humano no promueve nada y sus dos `ATTAAA` siguen clasificadas por canonicidad.

### Cabo suelto explícitamente NO cerrado

**`131938392`** es el PAS con **más expresión** (PSE 70,5 %, AvgRPM 1,65) y es el **numerador** de
la fracción larga. Dos lecturas: racimo del terminal, o **corte propio** en `3utr:1199-1207`. El
anclaje de cuatro puntos **estrecha** la banda y **no desempata** — caben dos `TATAAA`
(`3utr:1178` y `3utr:1189`).

**Por qué el frente sigue cerrado igual, y no por conveniencia:** bajo **las dos** lecturas el techo
del panel es **≥ 0,86**. La ambigüedad movería el número de cualquier candidato por detrás de
`3utr:1207`, **y hoy no hay ninguno**. **Ratificado, y el cabo queda abierto.**

### Ficheros que faltan y qué desbloquea cada uno

| fichero | desbloquea |
|---|---|
| RefSeq RNA local con md5 | `especificidad` con veredicto reproducible |
| `transcriptoma_3utr.fa` (UCSC, «3' UTR Exons») | `offtarget_seed` — el tercer modal |
| 3'-end seq de cerebro murino (`apa_medido.tsv`) | la fracción larga **en nuestro tejido** |
| `apa_medido_human.tsv` | sacar al humano del **modo asumido** |
| parental **sin intrón** | techo de expresión para el empalme |
| `hairpin.fa` de miRBase | los tres cálculos de miR-451 |
| lista ampliada de abundancia con referencia y umbral | la capa `AVISO` de colisión de seed |
| tabla de expresión en cerebro | ponderar la carga de off-targets |

**Cuando llegue el 3'-end seq, lo primero es CRUZAR los dos techos, no enchufarlo:** hoy
`apa_assessment` y `resolve_measured` producen un techo por caminos **independientes** y nada obliga
a que coincidan.

**Y la dirección esperada va escrita:** PolyA_DB promedia todos los tejidos y las neuronas alargan
los 3'UTR, así que lo esperable es **cerebro > 0,86**. Si sale **cerebro < PolyA_DB**, eso
**contradice la dirección conocida del sesgo: hay que PARAR y buscar la causa**, no promediar.

---

## 18. Verificación del propio pipeline

Lo que respalda que las cifras de arriba sean reproducibles:

- **5.201 pruebas** (Python) y **368** (hub) en verde `[DERIVADO 2026-09-08]`.
- **Goldens** que comparan el informe, la ficha, el documento y la instantánea de la página
  **enteros**, generados **con la configuración por defecto, sin excepciones**.
- **Un guardia de calendario** que vuelve a correr la suite entera con el reloj 400 días por
  delante: un valor esperado que dependa de la fecha falla hoy, no dentro de un año.
- **Auditorías que abortan la suite**: regla 2 sobre el AST, alcanzabilidad, datos de una especie en
  el código, banderas de CLI sin recorrido (trinquete, sólo baja), estados de la interfaz, fixtures
  sintéticos declarados, condiciones imposibles, secuencias emparejadas, homónimos, umbrales con
  supuesto, marcos de coordenadas, truncamiento de secuencias en tablas, claves derivadas y
  magnitudes calculadas por duplicado.
- **Cada intervalo se DERIVA de la secuencia que describe** y aborta si no cuadra; **cada posición
  impresa lleva su marco**; **cada salida que nombra una referencia imprime longitud y md5 juntos**.
- **Registro de erratas propias** (154 entradas) con las predicciones refutadas anotadas con su
  nombre — *«si sólo se anotan las predicciones que salen bien, el registro deja de ser un registro
  y pasa a ser un argumento»*.
