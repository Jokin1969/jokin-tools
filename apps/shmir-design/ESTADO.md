# Estado del proyecto — resumen para quien continúe

Documento de traspaso. Dice **qué está hecho, qué está medido con datos reales, qué está
abierto y qué no se puede romper**. Si vas a tocar código, lee además
[`CLAUDE.md`](./CLAUDE.md), que es **vinculante** y gana sobre cualquier cosa que digan
estas páginas.

**Reescrito entero el 2026-09-11.** La versión anterior estaba congelada en el
2026-08-25 y equivocada en casi todas sus cifras: decía 1162 tests (hay 5343), 88
ficheros Python (hay 455), «selección voraz N=6» (el panel son once), y que los dos `.fa`
de referencia no estaban en el repositorio (están los dos desde entonces). No era un
documento con una errata: era un documento caducado, y eso es peor que ninguno — se lee
como vigente. **Todas las cifras de aquí están medidas hoy, y cada una dice sobre qué
depósito** (ver §3), porque este proyecto tiene una entrada de registro entera sobre
números que se copian en vez de derivarse (principio nº 13).

---

## 1. Qué es

Diseñador de shmiRs. De uno o dos transcritos a un panel corto de candidatos con sus
veredictos por frente, sus oligos y el fragmento de síntesis listo para pegar sobre el
vector. **Python 3.11+, stdlib pura** en todo `shmir_design/` y en los `tools/`.

Dos dependencias autorizadas, las dos **opcionales** y ninguna en el núcleo
([`docs/dependencias-autorizadas.md`](./docs/dependencias-autorizadas.md)):

- **ViennaRNA** (≥2.6, probado con 2.7.2) — plegado. Sin ella el núcleo corre igual,
  **pero no se emite ADN**: la regla de la pasajera es estructural y sin plegado cae a
  una tabla por terminación que este proyecto tiene **descartada por escrito**, así que
  `check_can_emit_dna()` bloquea la emisión del módulo y de la hoja de pedido (errata
  nº 43). En la imagen de producción se instala en el build.
- **Streamlit** — la interfaz, y sólo la interfaz. No contiene lógica (regla 6).

### Tres puertas, el mismo núcleo

```bash
# 1. La INTERACTIVA: el hub sirve la interfaz Streamlit en /shmir
#    (proceso hijo en 127.0.0.1 + proxy inverso; arranca perezoso, en la primera
#    petición). Desplegables de especie, gestor de ficheros, los cuatro modales,
#    persistencia por proyecto e informe descargable.

# 2. El CLI
python3 apps/shmir-design/tools/design.py \
    --fasta data/reference/NM_011170.3.fa --genbank data/reference/NM_011170.3.gb \
    --name raton --usar-manifiesto --out salida/

# 3. Por LOTES: Batchwork → «Diseñar shmiRs». Subes uno o dos FASTA, sale un ZIP.
#    Llama al MISMO CLI por un puente sin lógica
#    (apps/batchwork/python/shmir_design_run.py). Se desmantelará cuando /shmir
#    cubra lo que hace; hasta entonces NO se le añade nada.
```

`--usar-manifiesto` es la forma normal de correr: conecta cada fichero del depósito con
el filtro que su rol declara, **para la especie que se diseña**, y con la versión y el
md5 del propio manifiesto. Va con **una sola especie** a propósito.

---

## 2. Cómo se comprueba

```bash
npm test                  # suite del hub (Node). HOY: 378 pruebas, 0 rojos
npm run test:shmir        # suite de shmir-design. HOY: 5343 pruebas, 0 rojos, 200 saltos
npm run check:shmir       # regla 2 sobre el AST + catorce auditorías (ver §10)
npm run check:tildes      # el castellano de los mensajes que ve el usuario
```

**Los 200 saltos son visibles y dicen su motivo**, uno por uno: cada uno nombra el
fichero de `data/reference/` que le falta, o la dependencia opcional que no está. Ésa es
la regla 3 aplicada a la suite — «no se pudo comprobar» y «no lo supera» son cosas
distintas. Un rojo que depende de la máquina es peor que ninguno: una suite con un rojo
fijo no dice «hay un fallo», dice «hay un rojo», y a partir de ahí ningún rojo se
atiende.

`npm test` incluye `test/calendario.test.js`, que **vuelve a correr la suite entera con
el reloj 400 días por delante**. Existe porque una prueba se puso roja sola el 1 de
septiembre de 2026: nadie la rompió, caducó. Un test que necesita tiempo lo **recibe por
parámetro**.

### Si te salen rojos nada más clonar, mira antes el entorno

Dos causas conocidas, las dos del contenedor y ninguna del repositorio:

- **`npm test` con 21 rojos y `Cannot find module`** (`pdfkit`, `qrcode`, `sharp`,
  `mailparser`): `node_modules` a medio instalar. `npm ci` y vuelven los 378.
- **decenas de rojos en `npm run test:shmir` a la vez, en zonas que tu cambio no toca**:
  mira el DISCO antes de atribuirlos al cambio. En este entorno el disco escribible es
  un cupo por sesión, así que `df` engaña —`Avail` a cero con `Used` bajo es el cupo
  agotado— y una escritura truncada no se parece a un fallo de disco: se parece a un
  test roto. Errata nº 143.

---

## 3. EL DEPÓSITO: lo que el repositorio versiona y lo que no

**Esto va antes que cualquier cifra, porque decide cuáles se pueden reproducir.**

`data/reference/.gitignore` ignora todo y va declarando excepciones con su
justificación: el criterio es el **tamaño** —«un RefSeq RNA completo no entra en el
repositorio»— y lo que sí entra es el **manifiesto**, que dice cuál era cada fichero y
cómo comprobarlo. Lo que entra hoy: los dos transcritos del ratón y del humano (`.fa` y
`.gb`), el casete de AAV, las tres corridas de RepeatMasker (dos de ellas el **fixture
negativo** de la biblioteca equivocada), las dos tablas de PolyA_DB, el plásmido
`addgene_198131.gb`, los exports de miRarchitect y el 3'UTR **fabricado** de 1246 nt, que
es evidencia de la errata nº 5 y no se borra.

**Lo que NO está, y por tanto no lo tiene quien clone:**

| Fichero | Qué cierra | Por qué no está |
|---|---|---|
| `refseq_rna.fa` | especificidad | descarga de cientos de MB |
| `transcriptoma_3utr.fa` | carga de off-targets por seed | ídem |
| `mature.fa` | colisión de seed (nivel aviso) | 5,6 MB de miRBase; se descarga **con su release** |
| `mirgenedb_cerebro.txt` | colisión de seed (nivel FAIL ampliado) | se descarga |
| `expresion_cerebro.tsv` | pondera la carga (opcional, no bloquea) | se descarga |
| `apa_medido.tsv` | el techo de APA **en cerebro** | **todavía no existe**: es el 3'-end seq |
| `addgene_111170.gb` | contextos del andamio (SGEP) | **ninguna: ver abajo** |
| `addgene_20670.gb` | el andamio miR-30 original | no aportado |
| `addgene_78126.gb` | el andamio miR-155 (**descartado con motivo medido**) | no aportado |

**`addgene_111170.gb` es el que chirría, y queda ANOTADO como pendiente de decidir.** No
falta por tamaño: son ~20 kB de un depósito público, el mismo orden que
`addgene_198131.gb`, que sí está versionado con su excepción escrita y con el argumento
exacto que aplica aquí — «sin él dentro, quien clone el repositorio se encuentra la
entrada vacía». A éste nadie le escribió la suya, así que en un clon el frente de los
contextos sale `NOT_RUN` para todo el mundo menos para quien lo subió. Versionarlo es
**una línea en el `.gitignore` más el fichero**, y el fichero aquí no está. No se
reconstruye (regla 1).

**Consecuencia de método, y es la que más cuesta aprender**: una derivación que mira al
DISCO contesta «qué hay en esta máquina», que casi nunca es la pregunta. El 2026-09-11
había tres guardias haciéndolo —la tabla de marcadores de presencia, el auditor de
fixtures sintéticos y los goldens con `--usar-manifiesto`— y los tres se arreglaron
apuntando a lo **versionado**: el `.gitignore`, el manifiesto y el bloque de procedencia
que el propio informe escribe dentro. El de fixtures, además, **dejaba de ver** seis
fabricaciones reales en un clon limpio: el fallo hacia el silencio que su propia cabecera
declara.

---

## 4. Estado por paso del pipeline

El orden de operaciones es **no negociable** y está en
[`docs/pipeline.md`](./docs/pipeline.md) — **que tiene cifras y estados caducados**: dice
que la accesibilidad está «pendiente» (está, con ViennaRNA) y que falta el fichero de
`rmsk` (están las tres corridas). Manda lo de aquí y lo de `CLAUDE.md`.

| # | Paso | Estado |
|---:|---|---|
| 0 | Carga de referencias + checksum | hecho. Tres checksums distintos por fila y un test de que no se confunden |
| 1 | Anatomía (ORF, UTRs) | hecho, **tres vías** y ninguna adivina. `resolve.py` la resuelve para los DOS frontales |
| 2 | Enmascarado → **RETILAR** | hecho, con las corridas reales de RepeatMasker. El `.tbl` es **obligatorio** |
| 3 | Tiling de 22-meros | hecho |
| 4-8 | GC, homopolímero, U forzada, asimetría, G4 | hechos. **G4 no emite veredicto** hasta que se decida su criterio (sale `NOT_RUN` y no cuenta) |
| — | **homopolímero de la MOLÉCULA** | hecho (2026-09-07). Mide guía y pasajera, que es lo que se sintetiza; el de la ventana se queda al lado |
| 9 | polyA como anotación + APA escalonado | hecho. Techo **por tramos**, promoción **por medida** |
| 10a | Colisión de seed | hecho; falta `mature.fa` para el nivel de aviso |
| 10b | Carga de off-targets por seed | hecho; falta el catálogo. **Eje de transcriptoma** desde 2026-09-09 |
| 11 | Variantes (gnomAD) | **el único paso sin empezar**. Obligatorio sobre la ventana del ORF conservado |
| 12 | Especificidad + transgén | hecho; falta la base. El BLAST se prepara y se recoge, **no se lanza** |
| 13 | Accesibilidad | hecho con ViennaRNA. **Desempate, nunca filtro** |
| 14 | Bloques conservados | hecho, y con el veredicto que cambia el programa (§6) |
| 15 | Sitios + selección voraz | hecho: espaciado 50 nt, cuota por tercio y **cuota de inmunes como requisito** |
| — | Horquilla, módulo de 149 nt, cassette, **fragmento de síntesis** | hechos |
| — | Informe de texto + documento (`md`/`docx`/`pdf`) | hechos, escritos con stdlib |
| — | Los cuatro modales y la persistencia por proyecto | hechos |

---

## 5. Los diez frentes

Un **frente** es un filtro que se cierra **consiguiendo algo**. Lo demás se cuenta en el
semáforo. Hoy hay **diez** declarados: `especificidad`, `repeticiones`,
`repeticion_polimorfica`, `seed`, `seed_colision`, `transgen`, `offtarget_seed`,
`empalme_intron`, `empalme_sitios` y `fraccion_isoforma_larga`.

- **Ocho se cierran con un FICHERO.** Con el depósito de un clon limpio, en ratón cierran
  **4 de 8** (biofísicos, repetitivos, la fracción de isoforma larga y el transgén) y en
  humano **3 de 8** — el humano necesita además su propio casete.
- **Uno NO se cierra con ningún fichero, sólo en el banco**: el **empalme del intrón**,
  con sus cuatro lecturas, las cuatro `NOT_RUN`. El informe lo dice aparte para que no
  parezca que basta con conseguir datos.
- **Un frente sólo se cierra si cubre TODO el panel**, y un `FAIL` cierra igual que un
  `PASS`: se cierra consiguiendo *la respuesta*, no una buena.
- **Un frente CERRADO no desaparece del informe**: sale como `FRENTE CERRADO` con su
  motivo. Borrarlo dejaría al siguiente lector sin saber si se resolvió o si nadie lo
  miró. Hoy está cerrado el del **APA**, con el techo cuantificado en 0,86.

**Mientras haya frentes abiertos, todo candidato sale `INCOMPLETE` y eso es lo
correcto.** `NOT_RUN` no es `PASS`, y no se pide oligo con filtros sin correr.

---

## 6. El panel de once, medido

Medido hoy sobre `NM_011170.3` (2191 nt, CDS 185..949, 3'UTR 1242 nt), tilando el
**transcrito entero** como hacen la página y el CLI, con el depósito de un clon limpio:

```
  ventanas tiladas   2170
  elegibles           254        (253 con mature.fa conectado: quita una)
  sitios               95        (96 con mature.fa)
  panel                11        inmunes al APA: 3
```

```
  3utr:   60  144  200  359  449  553  673  736  818  1018  1071
  tx:   1009 1093 1149 1308 1398 1502 1622 1685 1767 1967  2020
```

**El panel NO se mueve por el depósito**: es el mismo con `mature.fa` y sin él, y eso es
lo que permite reproducirlo clonando. Lo que cambia con ese fichero es el recuento de
elegibles y el bloque de seed, nada más — comprobado leyendo el diff de los dos goldens
con `--usar-manifiesto`.

**Y el panel no está escrito en ningún test**: se declara UNA vez en
`tests/panel_confirmado.py` y de ahí sale todo lo demás. Antes estaba transcrito en una
docena de ficheros, que es la errata nº 28 dentro de la suite.

Qué hay detrás de estas once plazas, con su fecha, está en `CLAUDE.md`: los diez primeros
del panel original coincidieron con los que el responsable ya tenía —o sea que la app
reprodujo lo que se sabía antes de construirla, y esa validación quedó cerrada—, la plaza
once es el segundo distal, `3utr:10` se **retiró por el frente de empalme** el 2026-09-07
(el primer candidato que ese frente quita) y cuatro plazas se corrieron entre 1 y 21 nt
el mismo día al medir el homopolímero sobre la molécula, **sin que cambiara ninguna
decisión anterior**.

### El hallazgo que ordena el programa, y no es del panel

De las cinco ventanas de 22 nt que caben **dentro** del único bloque conservado de ≥22 nt
entre los dos 3'UTR, **ninguna** supera los filtros, y con los mismos motivos en las dos
especies. O sea: **no existe un shmiR único válido para ratón, Tg650 y clínica por la vía
del 3'UTR.** Eso cambia la arquitectura del programa, no dos plazas del panel. La otra
vía —el **ORF conservado**— da dos ventanas preseleccionadas (ratón `tx:707`/`tx:708`,
misma diana en humano), que **no están aprobadas**: seed, repetitivos y especificidad
siguen en `NOT_RUN`, y gnomAD sobre esa ventana es obligatorio y no existe.

---

## 7. Lo que está DECIDIDO y no se reabre de paso

Cada una con su fecha y su motivo en `CLAUDE.md`. Aquí sólo la lista, para que nadie las
deshaga sin darse cuenta:

- **El criterio de polyA es ESCALONADO**, decidido con la tabla de candidatos delante. Y
  ese mismo criterio tumbó después a `3utr:221`, que era uno de los inmunes que su autor
  quería conservar: un criterio que sólo aprueba no demuestra nada.
- **La medida entra SIEMPRE que haya medida.** No es una preferencia de ordenación: son
  dos veredictos. `measured_apa=None` **aborta**; excluirla exige motivo escrito.
- **El truncamiento por APA es un TECHO, no un FAIL.** `FAIL` queda para la señal
  terminal, donde no hay isoforma que conserve la diana.
- **El espaciado NO se baja** para meter un inmune más: compra independencia entre
  apuestas, no número de apuestas.
- **El ensayo de RT-qPCR no se rediseña: se queda con ALCANCE DECLARADO**, y el plan lo
  dice con dos frases —qué mide y qué no— que van juntas o mienten las dos.
- **Van las DOS arquitecturas de intrón a síntesis** (`mvm_actual` e
  `intron_quimerico`). No es un empate ni una indecisión: ninguna medida las separa de
  forma unánime y el gel es quien decide.
- **`mvm_sin_criptico` sale de la matriz** — arregla un problema que no existe — y
  **retirar no es borrar**: sigue en el registro con su motivo y su condición de vuelta.
- **El fragmento de síntesis es el intrón ENTERO con su contexto exónico**, y los sitios
  de restricción salen por defecto (siguen disponibles con una bandera).
- **Los `.dna` completos NO se generan: se genera su COMPROBACIÓN** (`montaje.py`).
- **Los off-targets humanos se cuentan contra los DOS transcriptomas**, en un eje y sin
  veredicto fundido: el murino mide el experimento y el humano el paciente.
- **La persistencia es JSONL append-only por proyecto, no SQLite**: un veredicto tiene
  que sobrevivir a la app que lo escribió, y un `.db` binario no se lee con `cat`.

---

## 8. Lo que está ABIERTO

Por orden de lo que desbloquea:

1. **`mature.fa` de miRBase** — cierra el nivel de aviso de la colisión de seed, y es con
   diferencia el fichero del que más cuelga: **159 de los 200 saltos de la suite lo
   nombran**, solos o junto a un fixture. Hace falta **con su release declarada**;
   miRBase renumera entre versiones.
2. **`addgene_111170.gb` en git** — decisión de una línea (§3).
3. **`transcriptoma_3utr.fa`** (y el del fondo, para el humano) — cierra
   `offtarget_seed`, que es el modo de off-target más frecuente de RNAi y el que el BLAST
   **no puede** detectar.
4. **`refseq_rna.fa`** — cierra especificidad. Ojo: `scanner_budget` **impide** conectar
   una base grande al escáner por ventana, y con razón (17 min por repintado con 100 MB).
   Ese frente se cierra por el **modal**, no por el filtro de ventana.
5. **El paso 11 (gnomAD)** — el único sin empezar, y obligatorio sobre la ventana del ORF
   conservado: la selección purificadora restringe los **no sinónimos**, y son los
   **sinónimos** los que rompen el apareamiento sin tocar la proteína.
6. **El 3'-end seq de cerebro murino** (`apa_medido.tsv`). Cuando llegue, **lo primero es
   cruzar su techo con el 0,86 de PolyA_DB**, no enchufarlo: hoy los dos caminos son
   independientes y nada obliga a que coincidan. Y la **dirección esperada va escrita**:
   si el de cerebro sale MENOR, se PARA — no se promedia.
7. **El control positivo del ensayo de APA**, con su cita. Sin él, «casi todo isoforma
   larga» no se distingue de un ensayo **ciego** a las isoformas cortas.
8. **`hairpin.fa` de miRBase** — los tres cálculos de miR-451. Del maduro no se deriva.
9. **`aav_casete_human.fa`** y `polya_db_human.tsv` ya está: el humano sigue en **modo
   asumido** para su APA hasta que llegue su tabla medida.
10. **La columna `knockdown_medido`**, que vuelve rellena del laboratorio. Hasta
    entonces, el orden por asimetría es una convención, no un resultado.

**Cabos abiertos que se dejan abiertos a propósito** (no son tareas): el racimo
`131938392` de PolyA_DB —ratificado que su ambigüedad no mueve el techo del panel— y el
criterio de G4, que no emite veredicto hasta que alguien decida con qué justificación.

### Y un guardia que lleva tiempo sin morder, ENCONTRADO el 2026-09-11 y NO arreglado

`tests/test_rmsk_especie.TestElFixtureNegativo` —el test que reproduce la errata
fundacional del proyecto, el «Alu 0 %»— se salta siempre, y su motivo dice que **falta el
fixture negativo**. El fixture negativo **está en el repositorio**: es
`rmsk_human_WRONG_SPECIES_mouse_lib.out`, versionado con su `.tbl`. Lo que el test busca
es otro nombre, `rmsk_humano_contra_biblioteca_murina.out`, y sobre todo **otra cosa**:
espera un `.out` que declare `mus musculus` y traiga un elemento `Alu`.

**Ese fichero no puede existir, y este proyecto lo demostró después con md5**: los dos
`.out` de la corrida buena y de la mala son **idénticos byte a byte**
(`bcc33dbc…`), ninguno declara la especie —ninguno lo hace— y lo único que los distingue
vive en el `.tbl`. O sea que el test está escrito contra un artefacto que la propia
demostración descartó, y su skip dice «falta un fichero» cuando lo que pasa es que el
test pide una forma que no se produce.

**No se toca de paso**, y por eso queda aquí: reescribirlo contra la pareja `.out`+`.tbl`
—que es lo que la contramedida real comprueba— o retirarlo con su motivo escrito es una
decisión, no un renombrado. Mientras tanto, la contramedida SÍ está viva por otro camino:
`expected_species` es obligatorio, el resumen es obligatorio, y hay tests del parser con
sondas que cubren las dos ramas.

---

## 9. Invariantes que no se pueden romper

1. **Nunca generar, completar ni reconstruir una secuencia.** Si falta, se aborta. Las
   tres autorizaciones escritas y acotadas —espaciadores, una base del `GTGAGCG` y los
   controles del experimento— cubren **sólo** eso, y lo que sale de ellas va **marcado**
   en toda la salida.
2. **Ningún `except` se traga un fallo.** `check:shmir` lo comprueba sobre el AST.
3. **`NOT_RUN` no es `PASS`**, y `NO_APLICA` no es una cuarta forma de `NOT_RUN`.
4. **Un número comparativo que no se calculó va VACÍO, nunca a cero.** Y hay tres celdas
   distinguibles, no una: vacía, `NOT_RUN` (faltó un recurso) y `NO_PEDIDO` (se decidió
   no calcularlo).
5. **Toda posición impresa lleva su ESPACIO DE COORDENADAS pegado** (`3utr:1018`,
   `tx:1967`), en la celda y no en la cabecera. El marco **se recibe**, nunca se pone por
   defecto, y el prefijo **no se puede teclear** fuera de `coords`.
6. **Longitud y md5 van JUNTOS** en toda salida que nombre una referencia.
7. **Toda cifra comparativa sale con su referencia**: la tasa base junto a las colisiones
   de seed, el percentil junto a la carga de off-targets.
8. **Los avisos no se pueden silenciar**: `ANDAMIO_NO_VERIFICADO` no tiene parámetro para
   apagarlo, en ninguna función ni CLI.
9. **La interfaz no decide**: lo que decide vive en `presentation.py` con tests, y hay
   guardias mecánicos que leen el fuente de la página.
10. **El orden del paso 15 no se cambia**: enmascarar y RETILAR, filtros duros, ordenar
    por asimetría, agrupar en sitios, selección voraz.
11. **Los tests van antes que la funcionalidad**, y con datos reales.
12. **La anatomía no se adivina**, y sin `.gb` lo que cuelga de la frontera sale
    `NO_FIABLE` con los afectados nombrados uno a uno.
13. **Un dato que cita un fichero se DERIVA de él, nunca se transcribe** (principio
    nº 13). Es la regla que más veces se ha roto en este proyecto.
14. **La accesibilidad y la carga de off-targets son DESEMPATE, nunca filtro.**

---

## 10. Los guardias: qué vigila la suite además de los tests

Hay **diecisiete auditorías declaradas** en `data/auditorias.toml`, cada una diciendo
**sobre qué evidencia opina y cómo la reconoce** — dos que compartan evidencia tienen que
declarar un cruce, porque ya hubo dos con reglas opuestas sobre lo mismo (errata nº 52).
`npm run check:shmir` corre la regla 2 sobre el AST y **catorce** de ellas; las dos que
no —`auditar_geometria` y `auditar_navegacion`— corren desde sus tests, que es dónde se
comprueban.

Tres instrumentos, y la distinción importa:

- **GUARDIA — el número correcto es CERO** y cualquier hallazgo aborta: condiciones que
  no pueden ser falsas, secuencias emparejadas sin `strict`, claves que un test escribe y
  luego busca, marcos tecleados, tablas que truncan una secuencia, umbrales que esconden
  un supuesto, homónimos sin declarar, una magnitud calculada en dos sitios.
- **TRINQUETE — un techo que SÓLO puede bajar**, y falla en las dos direcciones. Hoy:
  **41** banderas `VEREDICTO` de los CLI sin recorrer de punta a punta, **11** estados de
  la interfaz sin pintar, y tres grupos de fórmula repetida (el prioritario: **23** sitios
  que calculan a mano la longitud de un intervalo).
- **INFORME — no falla nunca**: alcanzabilidad (qué función pública no tiene llamador),
  datos de una especie escritos en el código, piezas contra los plásmidos.

**Y hay un guardia sobre los guardias**: `tests/test_un_GUARDIA_demuestra_que_ha_mirado.py`.
`hallazgos == 0` contesta «¿falló?», y la pregunta es «¿lo comprobó?» — las dos dan el
mismo cero. Cada auditoría publica un inventario de lo que ha leído, y ese campo **no
puede ser el de hallazgos**.

**Nueve goldens** (`tests/golden/`) comparan salidas ENTERAS, cada uno declarando en su
cabecera sobre qué entrada se genera. Se regeneran a mano y **el diff entra en la
revisión**: es lo que caza lo que los tests de presencia no ven —127 líneas borradas en
silencio, un `3utr:1149` en la cabecera de una ficha, dos textos inventados.

El registro completo de por qué existe cada uno está en
[`docs/erratas.md`](./docs/erratas.md) —**157** entradas, numeradas hasta la nº 160— y
[`docs/principios.md`](./docs/principios.md), con **63** principios.

---

## 11. Mapa de ficheros

455 ficheros Python: **79** módulos en `shmir_design/`, **34** CLI y auditorías en
`tools/`, **338** ficheros de test, 1 de interfaz.

| Ruta | Qué |
|---|---|
| `shmir_design/errors.py`, `filters.py` | excepciones; `PASS`/`FAIL`/`NOT_RUN`/`NO_APLICA` y su agregación |
| `shmir_design/coords.py` | posiciones con marco. No se puede imprimir un entero desnudo |
| `shmir_design/reference.py`, `manifest.py`, `presencia.py` | referencias, checksums, manifiesto, «¿está Y tiene contenido?» |
| `shmir_design/anatomy.py`, `genbank.py`, `orf.py`, `resolve.py` | anatomía por tres vías, para los DOS frontales |
| `shmir_design/tiling.py`, `hard_filters.py`, `thermo.py`, `folding.py` | tilado, filtros de ventana, asimetría, plegado |
| `shmir_design/polya.py`, `apa.py` | señales, techo por tramos, promoción por medida, amplicones |
| `shmir_design/mirna.py`, `seed_scan.py`, `seed_load.py`, `offtarget.py` | las dos preguntas de la seed y la carga de off-targets |
| `shmir_design/specificity.py`, `blast.py` | especificidad y transgén; el BLAST se prepara y se recoge |
| `shmir_design/masking.py`, `conservation.py`, `orf_sweep.py` | repetitivos, bloques conservados, la vía del ORF |
| `shmir_design/selection.py`, `spacing.py`, `retirados.py` | selección voraz, cuotas, comparación de sitios, retiradas |
| `shmir_design/scaffold.py`, `scaffold_registry.py`, `spacers.py` | andamio, registro de los cuatro, espaciadores de novo |
| `shmir_design/introns.py`, `splicing.py`, `spliceai.py`, `intron_design.py` | el intrón: registro, empalme, predicción, propuesta |
| `shmir_design/blocks.py`, `gblock.py`, `fragmento.py`, `montaje.py` | módulo, cassette, fragmento de síntesis y su comprobación |
| `shmir_design/controles.py` | scrambled y seed-mismatch, con veredictos y ficha |
| `shmir_design/store.py`, `*_store.py`, `trabajo.py` | persistencia append-only, almacenes por modal, directorios |
| `shmir_design/outputs.py`, `comparative.py`, `informe_doc.py`, `docx_writer.py`, `pdf_writer.py` | las salidas y el documento |
| `shmir_design/presentation.py`, `dossier.py`, `obtencion.py` | lo que decide la interfaz, la ficha y las fichas de obtención |
| `tools/` | `design`, `informe`, `blocks`, `oligo`, `comprobar_montaje`, `regenerar_golden`, `check_rules`, `check_tildes` y **dieciséis auditorías** (quince `auditar_*` más `check_alcance`) |
| `ui/streamlit_app.py` | la interfaz, sin lógica |
| `data/reference/` | el depósito y su manifiesto (§3) |
| `data/*.toml` | las tablas que las auditorías cruzan contra el código |
| `docs/` | pipeline, fixtures, principios, erratas, endpoints, dependencias, resultados |

---

## 12. Lo que este documento NO es

- **No es vinculante.** Lo vinculante es [`CLAUDE.md`](./CLAUDE.md), y sus seis reglas
  ganan sobre cualquier petición.
- **No es el registro.** Por qué se decidió cada cosa, con su fecha y con las palabras de
  quien la decidió, está en `CLAUDE.md`; lo que salió mal y qué lo enseña, en
  `docs/erratas.md`.
- **No es una fuente de números.** Las cifras de aquí se midieron el 2026-09-11 sobre el
  depósito de un clon limpio y **envejecen**. Si una cuenta, sácala corriendo el CLI: es
  lo mismo que este proyecto exige de su propio código.
