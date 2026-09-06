<!-- GOLDEN — se genera con: el MISMO documento sobre el TRANSCRITO ENTERO, que es lo que tilan la pagina y el CLI: sin ella, esta salida no se leia nunca en el marco de uso. -->

# Diseño de shmiR — mouse

**Estado del informe: PARCIAL** · generado 2026-08-26

ESTE INFORME ES PARCIAL. No es un borrador ni una versión reducida: es el mismo documento con frentes todavia abiertos, y cada uno sale marcado con lo que le falta y donde conseguirlo. Un candidato con cualquier frente en NOT_RUN es INCOMPLETE, nunca aprobado — no haber comprobado algo no es haberlo comprobado y que salga bien.

Frentes abiertos: especificidad, repeticion_polimorfica, repeticiones, seed, seed_colision, transgen, offtarget_seed, empalme_intron, empalme_sitios.

COMO SE LEE ESTO. Cada filtro emite uno de cuatro estados: PASS (corrió y el candidato lo supera), FAIL (corrió y no lo supera), NOT_RUN (NO LLEGO A CORRER — es una laguna, no un aprobado) y NO_APLICA (esa pregunta no se le hace a ese candidato). Un número comparativo que no se calculo va VACÍO, nunca a cero: no haber contado y contar cero son cosas distintas.

## 1. Que se analizo

Longitud y md5 van JUNTOS a propósito: «referencia 1246 nt» parece razonable a solas, y pegado al md5 no hay forma de leerlo sin ver que lo que se llama referencia no es lo que se cree. Es la contramedida de una errata real.

| campo | valor |
|---|---|
| secuencia analizada | 2191 nt / 44fb8cd80883844cde5e53bbc367b176 |
| especie declarada | mouse |
| anatomia | CDS del fixture verificado por md5 (transcrito entero) |
| ventanas tiladas | 2170 |
| tamaño de ventana | 22 nt |
| fecha del informe | 2026-08-26 |
| estado del registro | d41d8cd98f00b204e9800998ecf8427e · 0 corrida(s) |

## 2. Estado de los frentes

Un frente es una pregunta que hay que contestar antes de pedir oligo. Los cerrados NO desaparecen del informe: sin ellos, el siguiente lector no sabria si se resolvieron o si nadie los miro.

| frente | estado | que falta | donde se consigue |
|---|---|---|---|
| especificidad | NOT_RUN | refseq_rna.fa, el resultado del BLAST en `-outfmt 6` | La app prepara la consulta; el BLAST lo corres tu. La base la construyes por una de DOS vias: el Table Browser de UCSC (recomendada, la especie del diseño, decenas de MB) o el FTP de BLAST del NCBI (exhaustiva, todos los organismos, decenas de GB). (https://genome.ucsc.edu/cgi-bin/hgTables) |
| repeticion_polimorfica | NOT_RUN | rmsk_mouse.out, rmsk_mouse.tbl | RepeatMasker Web Server (https://www.repeatmasker.org/) |
| repeticiones | NOT_RUN | rmsk_mouse.out, rmsk_mouse.tbl | RepeatMasker Web Server (https://www.repeatmasker.org/) |
| seed | NOT_RUN | mature.fa | miRBase (el mismo `mature.fa`), o una tabla propia `seed<TAB>familia` (https://www.mirbase.org/) |
| seed_colision | NOT_RUN | mature.fa | miRBase (https://www.mirbase.org/) |
| transgen | NOT_RUN | aav_casete.fa | El laboratorio: el fichero del plásmido del casete AAV (—) |
| offtarget_seed | NOT_RUN | transcriptoma_3utr.fa | UCSC Table Browser (https://genome.ucsc.edu/cgi-bin/hgTables) |
| empalme_intron | NOT_RUN | no se cierra con ningún fichero (banco) | Banco: RT-PCR, Western y secuenciacion. No hay descarga que valga. (—) |
| empalme_sitios | NOT_RUN | resultado de SpliceAI sobre las construcciones (TSV) | SpliceAI, ejecutado por ti. La app prepara las construcciones y recoge el resultado. (—) |
| fraccion_isoforma_larga | CERRADO | — | — |

> **9 frente(s) en NOT_RUN. No se pide oligo hasta que todos tengan veredicto. Que uno se arregle con un fichero de kilobytes y otro necesite ir al banco no cambia nada: los dos bloquean igual.**

Y hay una categoría aparte: empalme_intron NO se cierra con ningún fichero. Conseguir más datos no lo resuelve; hay que ir al laboratorio. Se dice aparte para que no parezca que basta con descargar algo.

## 3. Frente por frente

Por cada frente: que mide, por que importa, con que criterio se decide y de donde sale cada umbral, con que datos se ha contestado, y el resultado.

### Filtros biofísicos de ventana (no son un frente)

Los seis filtros biofísicos de ventana NO dependen de ningún fichero ni de ninguna especie: corren siempre. Por eso no son un «frente» — no hay nada que conseguir para cerrarlos. Sus umbrales si necesitan justificarse igual que los demas.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| GC mínimo de la ventana | 0,30 | literatura | el rango de GC de las guías funcionales de RNAi es un resultado repetido en los trabajos de diseño de shRNA/siRNA: por debajo el duplex es demasiado inestable para cargar bien |
| GC máximo de la ventana | 0,55 | literatura | por encima el duplex es demasiado estable y la hebra no se separa; mismo cuerpo de trabajo que el mínimo |
| homopolimero máximo | 4 nt | convencion | carreras más largas dan problemas de síntesis y de secuenciacion, y en el casete son sustrato de deslizamiento de la polimerasa  ⚠ SIN BASE MEDIDA: el corte en 4 es un redondeo operativo, no un punto medido: 5 no es cualitativamente distinto de 4 |
| asimetría mínima (proxy) | +1,0 kcal/mol | nuestro | la regla de asimetría termodinamica —el extremo 5' de la guía menos estable carga preferentemente— si viene de literatura; el UMBRAL en +1,0 sobre NUESTRO proxy es nuestro. Y el proxy NO es una energía libre de duplex: es una heurística, con su aviso en `thermo.py`  ⚠ SIN BASE MEDIDA: el proxy no está calibrado contra energias medidas, así que el número ordena candidatos entre si pero no es una magnitud fisica |

### especificidad — NOT_RUN

**Que mide.** ¿Esta guía tiene complementariedad EXTENSA con algun otro transcrito? Es la pregunta de los alineamientos, y la contesta un BLAST contra una base de transcritos.

**Por que importa / resultado.** NOT_RUN en 2170 de 2170 ventanas: falta el recurso. NOT_RUN no es PASS. Y OJO: este frente NO cubre los off-targets mediados por seed. Eso es `offtarget_seed`, un frente APARTE, porque 7 nt contiguos no dan alineamiento y ningún BLAST los devuelve.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

**Criterio.** Un acierto cuenta como GRAVE si alinea casi la sonda ENTERA —el mínimo se deriva de la propia sonda, un extremo recortado— tiene 0 o 1 desapareamiento, y su transcrito NO es una de las variantes declaradas de la diana. Un solo acierto grave da FAIL. Las variantes de la diana se declaran en `data/diana/variantes.toml` con su procedencia, y una especie que no las declare NO recibe veredicto: sale `NO_CIERRA`, nunca un PASS por una lista vacía. El criterio NO es «más de un acierto»: ese umbral escondía el supuesto de que la diana produce exactamente UN acierto, y con dos variantes del mismo gen contaba la segunda como off-target. La diana se declara y el umbral es «ningún acierto grave fuera de ella». Un acierto cuenta si alinea casi la sonda ENTERA: `mismatch` de `-outfmt 6` sólo cuenta desapareamientos dentro del segmento alineado, así que un parcial de 13 nt clavado trae 0 y no es un off-target. La ORIENTACIÓN no filtra: dice qué hebra es —la guía es antisentido a su diana y la pasajera lleva su misma secuencia— y se usa como comprobación de montaje, no como descarte.

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «especificidad»

  ¿Se pega también a otros genes?
  Tu shmiR está pensado para apagar un gen y sólo uno. Esta comprobación busca si su secuencia se parece lo bastante a la de otros mensajeros de la célula como para apagarlos también. Se contesta comparándola contra un catálogo de los mensajeros conocidos de tu especie.

  QUE PREGUNTA RESPONDE: ¿Esta guía tiene complementariedad EXTENSA con algun otro transcrito? Es la pregunta de los alineamientos, y la contesta un BLAST contra una base de transcritos.

  FICHERO(S) QUE HACEN FALTA:
    · refseq_rna.fa  [OBLIGATORIO]
      El FASTA de transcritos del que sale la base. Es lo que se DECLARA: la app no necesita el fichero entero para dar el veredicto —el BLAST lo corres tu— pero si su nombre, su versión y su md5, que es lo único que permite decir contra que se comparo. Las dos vias acaban en este mismo fichero, y por eso el md5 significa lo mismo por las dos.
    · el resultado del BLAST en `-outfmt 6`  [OBLIGATORIO]
      Lo que se SUBE. No es un fichero con nombre fijo: sale de la orden que da la app, y por eso aquí se describe en vez de nombrarse. Un `-outfmt 6` VACÍO se rechaza — cero hits y «no llego a correr» son cosas distintas y ese fichero no las distingue.

  FUENTE: La app prepara la consulta; el BLAST lo corres tu. La base la construyes por una de DOS vias: el Table Browser de UCSC (recomendada, la especie del diseño, decenas de MB) o el FTP de BLAST del NCBI (exhaustiva, todos los organismos, decenas de GB).
  URL: https://genome.ucsc.edu/cgi-bin/hgTables

  PASOS:
    1. Abre el modal de especificidad en la app y marca los candidatos y las hebras que quieras consultar.
    2. Descarga el FASTA de consulta que genera la app. Lleva su md5: no lo edites.
    3. Instala BLAST+ del NCBI. Trae `blastn`, `makeblastdb` y `blastdbcmd`, y los necesitas por las DOS vias.
    4. ELIGE VÍA, y la elección es de TAMAÑO: la A son decenas de MB, sólo de Mus musculus; la B son decenas de GB de todos los organismos. Lo único que la B da y la A no son los transcritos PREDICHOS (`XM_`/`XR_`) — lee el aviso antes de elegir.
    5. [VÍA A · UCSC — RECOMENDADA] Abre el Table Browser (la URL de arriba) y pide los transcritos de Mus musculus: «assembly» mm39, «group» Genes and Gene Predictions, «track» NCBI RefSeq, «table» «RefSeq Curated», «output format» sequence. Cuando pregunte el tipo de secuencia, elige el TRANSCRITO (mRNA), NO «genomic»: una guía se alinea contra mensajeros, y el genomico traeria intrones que no existen en ningún transcrito.
    6. [VÍA A · UCSC] Es la MISMA sesion de la que sale transcriptoma_3utr.fa: alli se marca la región «3' UTR Exons» y aquí se pide el transcrito entero. Dos descargas, una navegacion.
    7. [VÍA A · UCSC] Guarda el FASTA como refseq_rna.fa y MIRA LAS CABECERAS antes de seguir: con «RefSeq Curated» todas empiezan por `NM_` o `NR_` y no puede haber ni un `XM_`/`XR_`. Es la comprobación que no depende de que los menus se sigan llamando como aquí.
    8. [VÍA A · UCSC] Construye la base — un FASTA no es una base de BLAST: `makeblastdb -in refseq_rna.fa -dbtype nucl -out refseq_rna_mouse`
    9. [VÍA B · NCBI — EXHAUSTIVA] Descarga la base ya formateada desde https://ftp.ncbi.nlm.nih.gov/blast/db/ con `update_blastdb.pl --decompress refseq_rna`. Llega en volumenes numerados (`refseq_rna.00.*`, `refseq_rna.01.*`…) que son UNA sola base: no falta ninguno porque los ficheros se llamen distinto. Son decenas de GB de TODOS los organismos.
    10. [VÍA B · NCBI] Filtra a Mus musculus y vuelve a un FASTA: `blastdbcmd -db refseq_rna -taxids 10090 -out refseq_rna.fa`. Hace falta por DOS razones: `-entrez_query` no funciona contra una base local, así que sin filtrar la corrida no queda restringida a la especie; y la base preformateada no deja ningún FASTA que registrar, así que sin este paso el manifiesto se queda sin el md5 que es toda la procedencia del veredicto.
    11. [VÍA B · NCBI] Construye la base filtrada — un FASTA no es una base de BLAST: `makeblastdb -in refseq_rna.fa -dbtype nucl -out refseq_rna_mouse`
    12. Comprueba que la base se lee ANTES de lanzar nada: `blastdbcmd -db refseq_rna_mouse -info`. Da el número de secuencias y la fecha, que son dos de los tres metadatos que hay que anotar. Si esto falla, el BLAST también — y falla después de horas.
    13. En el modal, cambia `-db` al nombre de la base que acabas de construir. Se marcara como ajuste modificado y viajara con el resultado, y eso es lo CORRECTO: la base no es la estándar y el veredicto no puede parecer que si.
    14. Copia el comando que la app deja listo, TAL CUAL. Trae los ajustes de una consulta corta (`-task blastn-short`, `-word_size 7`, `-evalue 1000`, `-dust no`) y `-outfmt 6` a secas. Cambiar cualquier otro no es un detalle: viaja con el resultado y se marca en rojo.
    15. Ejecutalo desde el directorio donde esta la base, o pasale la ruta completa en `-db`, o declara `BLASTDB`. Con el nombre a secas desde otro sitio, `blastn` no la encuentra.
    16. Sube el `-outfmt 6` tal cual, sin recortarlo.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · nombre, versión y md5 de la base
      Sin ellos el veredicto no es reproducible, y el almacen marca la corrida como «no reproducible» con esas palabras. Con la via de UCSC van además el ensamblaje y la tabla («RefSeq Curated» o «RefSeq All»), que es lo que dice si los predichos estaban dentro.
    · los ajustes que hayas cambiado
      Cualquier ajuste distinto del estándar viaja con el resultado y se marca en rojo: un veredicto obtenido con parámetros no estándar no puede ser indistinguible de uno estándar. El `-db` de una base que te has construido tu ENTRA aquí, y tiene que entrar.

  TAMAÑO APROXIMADO: por la via de UCSC, unas decenas de MB; por la del NCBI, decenas de GB — una descarga real de este proyecto se fue a 80 GB. El resultado (`-outfmt 6`) son unos KB por las dos

  COMO SE VALIDA AL SUBIRLO: Al subir el resultado la app comprueba DOS cosas y las dos rechazan: que el md5 del FASTA de consulta que declaras sea el del FASTA que ella genero, y que toda `query` del resultado este en el panel. Es el fallo del CSV de miRarchitect —un fichero de otra corrida que entra, cuadra de forma y produce un análisis entero sobre el dato equivocado— y el mensaje lo nombra. Un `-outfmt 6` VACÍO también se rechaza: cero hits y «la corrida no llego a correr» son cosas distintas y ese fichero no las distingue.

  AVISOS:
    ⚠ «RefSeq Curated» NO TRAE LOS PREDICHOS (`XM_`/`XR_`), y eso cambia como se LEE el resultado: cero aciertos contra predichos NO ES «no hay off-targets contra predichos» — es que no habia ninguno en la base contra el que acertar. Es el «Alu 0 %» obtenido sin buscar Alu. Si los quieres dentro, o eliges «RefSeq All» en el mismo menu (si tu ensamblaje lo ofrece) o te vas a la VÍA B. Lo que no vale es dar por comprobado lo que no se miro.
    ⚠ EL FILTRO POR ORGANISMO NO VA EN LA ORDEN LOCAL. `-entrez_query` lo aplica el servicio de NCBI, así que sólo funciona con `-remote` — y `-remote` no da veredicto. En una corrida local la restricción a la especie tiene que venir de la BASE, y por eso las dos vias acaban en `makeblastdb`: la A porque UCSC ya te da una sola especie, la B porque hay que filtrarla. El organismo (txid10090) viaja igual con la corrida: es su identidad, no un ajuste.
    ⚠ ESTOS COMANDOS NO SE HAN PODIDO EJECUTAR DESDE ESTE PROYECTO: aquí no hay BLAST+ instalado ni red saliente. Son la ruta, no una corrida comprobada — y el paso de `blastdbcmd -info` está puesto justo para eso: que un fallo salga antes de la corrida y no después de ella.
    ⚠ ESTA APP NO LANZA EL BLAST Y NO PUEDE: el navegador no puede llamar a NCBI (CORS) y el backend no tiene red saliente. No es una limitacion escondida: es la arquitectura, y el modal lo dice.
    ⚠ `-remote` es EXPLORACION, NUNCA VEREDICTO. La base de NCBI cambia entre corridas, así que un resultado remoto no es reproducible. Solo una base LOCAL con md5 cierra el frente.
    ⚠ ESTE FRENTE NO CUBRE LOS OFF-TARGETS POR SEED. Son dos frentes y el otro es `offtarget_seed`: 7 nt contiguos no dan un alineamiento puntuable, así que ningún BLAST los devuelve. Un «especificidad: PASS» sin esa frase invita a creer que la guía está comprobada cuando lo comprobado son los alineamientos.
```

### repeticion_polimorfica — NOT_RUN

**Que mide.** ¿La ventana cae dentro de una repetición POLIMÓRFICA — un microsatelite, un satelite, un tramo de baja complejidad? Es otra pregunta que la de `repeticiones`, aunque salga del mismo fichero: aquella va de estabilidad del genoma AAV y esta de VIABILIDAD CLINICA. Un microsatelite varia en NÚMERO DE REPETICIONES entre individuos, así que una guía ahi tendría respondedores y no respondedores por variación de LONGITUD, no de secuencia.

**Por que importa / resultado.** NOT_RUN en 2170 de 2170 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

**Criterio.** Este frente no tiene umbral numérico: su veredicto es una comprobación, no una comparación contra un corte.

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «repeticion_polimorfica»

  ¿Cae en un tramo que mide distinto en cada individuo?
  Algunos tramos repetidos tienen distinto número de repeticiones en cada persona. Un shmiR dirigido ahí funcionaría en unos y en otros no — y no por un cambio de letras, sino de longitud, que es algo que los catálogos de variantes captan mal.

  QUE PREGUNTA RESPONDE: ¿La ventana cae dentro de una repetición POLIMÓRFICA — un microsatelite, un satelite, un tramo de baja complejidad? Es otra pregunta que la de `repeticiones`, aunque salga del mismo fichero: aquella va de estabilidad del genoma AAV y esta de VIABILIDAD CLINICA. Un microsatelite varia en NÚMERO DE REPETICIONES entre individuos, así que una guía ahi tendría respondedores y no respondedores por variación de LONGITUD, no de secuencia.

  FICHERO(S) QUE HACEN FALTA:
    · rmsk_mouse.out  [OBLIGATORIO]
      Las filas con los intervalos enmascarados. Es lo que se aplica a la secuencia.
    · rmsk_mouse.tbl  [OBLIGATORIO]
      El resumen. Es el ÚNICO sitio donde se declara la especie de la biblioteca y la longitud de la consulta, así que es lo único que permite validar la corrida. Sin el, un `.out` sin filas no distingue «no habia repetitivos» de «la corrida no llego a correr».

  FUENTE: RepeatMasker Web Server
  URL: https://www.repeatmasker.org/

  PASOS:
    1. Entra en repeatmasker.org y ve a Services → RepeatMasking.
    2. Sube el FASTA del transcrito que vas a analizar (el mismo que le das a la app).
    3. En «DNA source» elige Mus musculus. NO lo dejes en el valor por defecto: es el único sitio donde se elige la biblioteca, y con la equivocada el resultado es indistinguible de uno bueno.
    4. En «Return format» elige «tar file».
    5. En «Return method» elige «email».
    6. Del `.tar.gz` que llega por correo saca DOS ficheros: el `.out` y el `.tbl`.
    7. Renombralos a mouse tal y como los pide la app y subelos juntos.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · versión de RepeatMasker
      Sale en la cabecera del `.out` y del `.tbl`. Dos versiones dan resultados distintos sobre la misma secuencia.
    · biblioteca Dfam (con su versión)
      RepeatMasker con Dfam_3.0 y con otra biblioteca dan resultados distintos, así que la versión del binario a solas NO identifica la corrida. Va en su propia columna del manifiesto.

  TAMAÑO APROXIMADO: unos pocos KB por corrida (el .out y el .tbl juntos no llegan a 10 KB)

  COMO SE VALIDA AL SUBIRLO: La app comprueba que el `.tbl` declare la MISMA especie que se esta diseñando, y que la longitud de la consulta que declara el resumen (`total length:`) coincida con la de la secuencia cargada. Si no cuadran, se rechaza: una máscara de otra secuencia taparia un tramo que ahi no es repetitivo, y el intervalo cabria sin salirse de rango.

  AVISOS:
    ⚠ El `.tbl` NO es opcional. Una corrida valida y una contra la biblioteca equivocada producen un `.out` INDISTINGUIBLE byte a byte cuando lo único presente es una repetición simple, porque esas se detectan por composición y no por biblioteca. Esta demostrado con datos en el propio proyecto (`masking.INDISTINGUISHABLE_OUTS`): dos ficheros con el mismo md5, uno bueno y otro con biblioteca murina sobre una consulta humana. La única diferencia vive en el `.tbl`.
    ⚠ El `.out` NO declara la especie. Ninguno lo hace. Por eso sin resumen no hay nada que comprobar — y no haber podido comprobar no es «coincide».
    ⚠ ESTE HUECO NO LO CUBRE gnomAD. gnomAD anota SUSTITUCIONES y capta mal la variación de longitud, así que un «gnomAD limpio» invita a creer que la ventana está comprobada y no lo esta. Son dos filtros y ninguno sustituye al otro.
    ⚠ Que familias cuentan como polimórficas va DECLARADO como parámetro y no citado: `Simple_repeat`, `Satellite` y `Low_complexity`. Un SINE es repetitivo pero DISPERSO — no varia de longitud — así que no entra.
```

### repeticiones — NOT_RUN

**Que mide.** ¿La ventana cae dentro de un elemento repetitivo? Importa por dos cosas distintas: un tramo repetitivo dentro del casete AAV es sustrato de recombinación, y una guía contra un repetitivo tiene miles de sitios perfectos en el genoma.

**Por que importa / resultado.** NOT_RUN en 2170 de 2170 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

**Criterio.** Este frente no tiene umbral numérico: su veredicto es una comprobación, no una comparación contra un corte.

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «repeticiones»

  ¿Cae en un tramo repetido del genoma?
  Hay tramos que aparecen miles de veces repartidos por el genoma. Un shmiR dirigido a uno de ellos tendría miles de sitios donde pegarse. Y además, un tramo repetido dentro del virus con el que se administra el tratamiento lo vuelve inestable.

  QUE PREGUNTA RESPONDE: ¿La ventana cae dentro de un elemento repetitivo? Importa por dos cosas distintas: un tramo repetitivo dentro del casete AAV es sustrato de recombinación, y una guía contra un repetitivo tiene miles de sitios perfectos en el genoma.

  FICHERO(S) QUE HACEN FALTA:
    · rmsk_mouse.out  [OBLIGATORIO]
      Las filas con los intervalos enmascarados. Es lo que se aplica a la secuencia.
    · rmsk_mouse.tbl  [OBLIGATORIO]
      El resumen. Es el ÚNICO sitio donde se declara la especie de la biblioteca y la longitud de la consulta, así que es lo único que permite validar la corrida. Sin el, un `.out` sin filas no distingue «no habia repetitivos» de «la corrida no llego a correr».

  FUENTE: RepeatMasker Web Server
  URL: https://www.repeatmasker.org/

  PASOS:
    1. Entra en repeatmasker.org y ve a Services → RepeatMasking.
    2. Sube el FASTA del transcrito que vas a analizar (el mismo que le das a la app).
    3. En «DNA source» elige Mus musculus. NO lo dejes en el valor por defecto: es el único sitio donde se elige la biblioteca, y con la equivocada el resultado es indistinguible de uno bueno.
    4. En «Return format» elige «tar file».
    5. En «Return method» elige «email».
    6. Del `.tar.gz` que llega por correo saca DOS ficheros: el `.out` y el `.tbl`.
    7. Renombralos a mouse tal y como los pide la app y subelos juntos.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · versión de RepeatMasker
      Sale en la cabecera del `.out` y del `.tbl`. Dos versiones dan resultados distintos sobre la misma secuencia.
    · biblioteca Dfam (con su versión)
      RepeatMasker con Dfam_3.0 y con otra biblioteca dan resultados distintos, así que la versión del binario a solas NO identifica la corrida. Va en su propia columna del manifiesto.

  TAMAÑO APROXIMADO: unos pocos KB por corrida (el .out y el .tbl juntos no llegan a 10 KB)

  COMO SE VALIDA AL SUBIRLO: La app comprueba que el `.tbl` declare la MISMA especie que se esta diseñando, y que la longitud de la consulta que declara el resumen (`total length:`) coincida con la de la secuencia cargada. Si no cuadran, se rechaza: una máscara de otra secuencia taparia un tramo que ahi no es repetitivo, y el intervalo cabria sin salirse de rango.

  AVISOS:
    ⚠ El `.tbl` NO es opcional. Una corrida valida y una contra la biblioteca equivocada producen un `.out` INDISTINGUIBLE byte a byte cuando lo único presente es una repetición simple, porque esas se detectan por composición y no por biblioteca. Esta demostrado con datos en el propio proyecto (`masking.INDISTINGUISHABLE_OUTS`): dos ficheros con el mismo md5, uno bueno y otro con biblioteca murina sobre una consulta humana. La única diferencia vive en el `.tbl`.
    ⚠ El `.out` NO declara la especie. Ninguno lo hace. Por eso sin resumen no hay nada que comprobar — y no haber podido comprobar no es «coincide».
```

### seed — NOT_RUN

**Que mide.** ¿La seed de la guía coincide con la de alguna familia de miARN de la tabla de seeds que se le haya pasado al diseño? Es el filtro de ventana, previo y más grueso que `seed_colision`: aquel compara contra los maduros de miRBase uno a uno.

**Por que importa / resultado.** NOT_RUN en 2170 de 2170 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| ventana de seed | posiciones 2-8 | literatura | la seed 2-8 es la definicion estándar del emparejamiento que dirige la represion mediada por miARN; la alternativa 2-7 también está definida y la app la ofrece, pero cambia el espacio de seeds y la tasa base |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «seed»

  ¿Empieza igual que una familia de microARN conocida?
  Es la versión rápida de la comprobación anterior: mira las primeras letras contra una lista corta de familias, antes de compararlas una a una con el catálogo completo.

  QUE PREGUNTA RESPONDE: ¿La seed de la guía coincide con la de alguna familia de miARN de la tabla de seeds que se le haya pasado al diseño? Es el filtro de ventana, previo y más grueso que `seed_colision`: aquel compara contra los maduros de miRBase uno a uno.

  FICHERO(S) QUE HACEN FALTA:
    · mature.fa  [OBLIGATORIO]
      La fuente normal de las seeds. Es el mismo fichero que cierra `seed_colision`, así que subiendolo una vez se cierran los dos.

  FUENTE: miRBase (el mismo `mature.fa`), o una tabla propia `seed<TAB>familia`
  URL: https://www.mirbase.org/

  PASOS:
    1. Lo normal es NO pasar tabla propia: sube `mature.fa` de miRBase (pestaña Downloads) y deja que la app derive las seeds.
    2. Si aun así quieres una tabla propia, escribela como `seed<TAB>familia`, una por línea, con la seed en ADN.
    3. Apunta de donde sale la tabla y con que criterio se hizo: una lista de seeds sin procedencia no es auditable.
    4. El prefijo de especie que corresponde aquí es mmu-

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · release de miRBase (o procedencia de la tabla propia)
      Igual que en `seed_colision`: sin versión, una coincidencia no se puede volver a comprobar.

  TAMAÑO APROXIMADO: unos 5,6 MB si se usa `mature.fa`; unos KB si es una tabla propia

  COMO SE VALIDA AL SUBIRLO: La tabla se lee como `seed<TAB>familia` y una fila mal formada aborta. Con `mature.fa` la app verifica el md5 contra el manifiesto. En los dos casos se normaliza U↔T antes de comparar.

  AVISOS:
    ⚠ La lista de 12 seeds que trae el proyecto (`seeds.BOOTSTRAP_SEEDS`) es un ARRANQUE PARA PROBAR LA MECANICA, no un filtro real. El aviso va en el código y en cada informe y no se quita: con ella el frente NO está cerrado.
```

### seed_colision — NOT_RUN

**Que mide.** ¿La seed de esta hebra es la de un miARN maduro conocido y abundante? Compartir seed con uno del núcleo no da off-targets dispersos: secuestra un programa regulador neuronal entero.

**Por que importa / resultado.** NOT_RUN en 2170 de 2170 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| ventana de seed | posiciones 2-8 | literatura | la seed 2-8 es la definicion estándar del emparejamiento que dirige la represion mediada por miARN; la alternativa 2-7 también está definida y la app la ofrece, pero cambia el espacio de seeds y la tasa base |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «seed_colision»

  ¿Se confunde con un microARN de la propia célula?
  La célula fabrica sus propios microARN, y en el cerebro algunos son muy abundantes. Si tu shmiR empieza con las mismas letras que uno de ellos competirá con él, y de paso alterará todos los genes que ese microARN controla.

  QUE PREGUNTA RESPONDE: ¿La seed de esta hebra es la de un miARN maduro conocido y abundante? Compartir seed con uno del núcleo no da off-targets dispersos: secuestra un programa regulador neuronal entero.

  FICHERO(S) QUE HACEN FALTA:
    · mature.fa  [OBLIGATORIO]
      Los maduros de miRBase. De aquí salen las seeds contra las que se compara, y también las de los controles biologicos del frente de carga de off-targets — nunca escritas en el código.
    · mirgenedb_cerebro.txt  [opcional]
      OPCIONAL y solo para el nivel AVISO: la capa AMPLIADA de abundancia en cerebro. El nivel de FAIL duro no lo necesita —corre siempre, con la lista del código y su autorización escrita—. El fichero tiene que traer en cabecera la REFERENCIA y el UMBRAL: sin ellos la capa queda NOT_RUN y no avisa de nada, porque un aviso sin umbral parece un veredicto y no lo es.

  FUENTE: miRBase
  URL: https://www.mirbase.org/

  PASOS:
    1. Entra en mirbase.org y abre la pestaña «Downloads».
    2. Descarga `mature.fa` — el de TODAS las especies vale: el filtro por especie lo hace la app.
    3. Apunta el RELEASE de miRBase que aparece en la pagina de descargas; el fichero no lo lleva dentro.
    4. Subelo tal cual, sin recortarlo ni filtrarlo a mano.
    5. Al configurar el modal, el prefijo de especie que hay que usar es mmu-

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · release de miRBase
      El fichero NO la trae dentro y miRBase renumera entre versiones. Sin release, una colisión no se puede volver a comprobar dentro de un año.

  TAMAÑO APROXIMADO: unos 5,6 MB (todas las especies, ~69.000 maduros)

  COMO SE VALIDA AL SUBIRLO: La app comprueba el md5 del fichero contra el manifiesto y filtra por el prefijo de especie. Además normaliza U↔T en los DOS lados antes de comparar: sin eso la comparación daria CERO colisiones en todas, que es un desajuste de alfabeto disfrazado de resultado limpio.

  AVISOS:
    ⚠ ANOTA EL RELEASE. miRBase RENUMERA entre versiones: un maduro puede cambiar de nombre o de número entre releases, y una colisión anotada sin release no se puede volver a comprobar. El fichero no trae la versión dentro, así que si no la apuntas se pierde.
    ⚠ No recortes el fichero a la especie antes de subirlo: la TASA BASE se deriva del fichero cargado y del filtro que se aplique, y con `hsa-` dentro casi se dobla. Que el filtro lo haga la app es lo que mantiene la tasa comparable entre corridas.
```

### transgen — NOT_RUN

**Que mide.** ¿Esta guía impacta contra el TRANSGÉN del casete terapeutico? Es una segunda base de especificidad, y falla duro con cero o un desapareamiento: una guía a un solo desapareamiento apaga la construcción terapeutica casi igual que a su diana, y eso sería un fallo silencioso.

**Por que importa / resultado.** NOT_RUN en 2170 de 2170 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| desapareamientos que hacen FAIL contra el transgén | 0 o 1 | nuestro | una guía a un solo desapareamiento apaga la construcción terapeutica casi igual que a su diana, y eso sería un fallo silencioso: el experimento no distinguiria «el shmiR no funciona» de «el shmiR apago su propio vector» |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «transgen»

  ¿Apagaría también el propio tratamiento?
  El tratamiento se administra dentro de un virus que lleva su propia copia del gen. Si el shmiR se pega también a esa copia, apaga la terapia a la vez que la diana. No se notaría: parecería sencillamente que el tratamiento no funciona.

  QUE PREGUNTA RESPONDE: ¿Esta guía impacta contra el TRANSGÉN del casete terapeutico? Es una segunda base de especificidad, y falla duro con cero o un desapareamiento: una guía a un solo desapareamiento apaga la construcción terapeutica casi igual que a su diana, y eso sería un fallo silencioso.

  FICHERO(S) QUE HACEN FALTA:
    · aav_casete.fa  [OBLIGATORIO]
      La secuencia del casete terapeutico. Es la segunda base de especificidad y la única forma de saber si una guía apagaria la propia construcción.

  FUENTE: El laboratorio: el fichero del plásmido del casete AAV
  URL: —

  PASOS:
    1. Pide al laboratorio el FASTA del casete que se va a usar.
    2. Asegurate de que es LO QUE LA CELULA MADURA, no el genoma con el intrón dentro.
    3. Comprueba con quien te lo da si lleva ya el módulo del shmiR o es el parental sin módulo: no es lo mismo y la lectura del veredicto cambia.
    4. Subelo y apunta su nombre completo y su md5.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · nombre completo del plásmido y su md5
      Un casete distinto da un veredicto distinto, y el nombre del fichero no identifica la construcción.
    · si lleva el módulo del shmiR o es el parental
      Con módulo dentro, toda guía impacta contra su propia horquilla. El dato cambia como se lee TODO el frente.

  TAMAÑO APROXIMADO: unos KB (un plásmido de ~5 kb en FASTA)

  COMO SE VALIDA AL SUBIRLO: La app comprueba POR SECUENCIA si el casete lleva el módulo del shmiR dentro —busca el loop de los andamios conocidos— y avisa. Si le pasas el GENOMA CON EL INTRÓN DENTRO en vez del transcrito maduro, toda guía da impacto contra SU PROPIA HORQUILLA y el filtro tumba el panel entero por un artefacto, con un motivo que además es literalmente cierto: por eso no se ve si nadie lo comprueba.

  AVISOS:
    ⚠ El casete que hay hoy en el proyecto (`aav_casete.fa`) es el PARENTAL, sin el módulo del shmiR, y está comprobado por secuencia. Por eso su veredicto se puede leer tal cual. Cuando se sustituya por el terapeutico hay que dar el TRANSCRITO MADURO.
    ⚠ XhoI y EcoRI viajan dentro del módulo, heredadas de los contextos de SGEP, y en el plásmido final NO son únicas. El clonaje va por NheI/SacI o por síntesis.
```

### offtarget_seed — NOT_RUN

**Que mide.** ¿Cuántos mensajeros del transcriptoma llevan un sitio para la seed de esta hebra? Es la CARGA de off-targets, y es otra pregunta que la colisión con un miARN conocido. No la contesta ningún alineador: 7 nt contiguos no dan un alineamiento puntuable, así que ningún BLAST los devuelve por mucho que se le baje el word_size.

**Por que importa / resultado.** NOT_RUN: falta `transcriptoma_3utr.fa`, así que los sitios de seed no se han contado. NOT_RUN no es PASS. EL OFF-TARGET MEDIADO POR SEED NO SE BUSCA CON BLAST, y no es una preferencia: 7 nt contiguos NO DAN UN ALINEAMIENTO PUNTUABLE, así que un blastn no los devuelve por mucho que se le baje el word_size. Esto es coincidencia EXACTA del heptamero 2-8 sobre los 3'UTR del transcriptoma murino — busqueda de SUBCADENA, no alineamiento— y necesita `transcriptoma_3utr.fa`. Fundirlo con la especificidad en un solo «PASS» daria por cubierto EL MODO DE OFF-TARGET MÁS FRECUENTE DE RNAi con una herramienta que no lo detecta. Por eso son DOS frentes y se cuentan aparte.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| ventana de seed | posiciones 2-8 | literatura | la seed 2-8 es la definicion estándar del emparejamiento que dirige la represion mediada por miARN; la alternativa 2-7 también está definida y la app la ofrece, pero cambia el espacio de seeds y la tasa base |
| sorteos minimos de la distribución nula (carga de off-targets) | 10.000 | nuestro | con menos, el percentil de la COLA —que es el único número accionable— no tiene resolución |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «offtarget_seed»

  ¿A cuántos genes puede afectar de rebote?
  A un shmiR le bastan siete letras del principio para frenar un mensajero, aunque el resto no encaje. Esto cuenta cuántos mensajeros de tu especie llevan esas siete letras. No es un aprobado ni un suspenso: es una cifra para comparar unos candidatos con otros.

  QUE PREGUNTA RESPONDE: ¿Cuántos mensajeros del transcriptoma llevan un sitio para la seed de esta hebra? Es la CARGA de off-targets, y es otra pregunta que la colisión con un miARN conocido. No la contesta ningún alineador: 7 nt contiguos no dan un alineamiento puntuable, así que ningún BLAST los devuelve por mucho que se le baje el word_size.

  FICHERO(S) QUE HACEN FALTA:
    · transcriptoma_3utr.fa  [OBLIGATORIO]
      Los 3'UTR sobre los que se cuentan los sitios de seed. Un transcrito representativo por gen; si trae varias isoformas, la app lo detecta y avisa de que el conteo está inflado.
    · expresion_cerebro.tsv  [opcional]
      OPCIONAL y REFINA, no cierra: una tabla `transcrito<TAB>valor` de expresión en el tejido. Sin ella el conteo sigue saliendo, pero sin ponderar — un sitio en un gen que la neurona no expresa cuenta igual que uno en un gen abundante. Es una de las tres limitaciones que hacen del número un LÍMITE SUPERIOR, y la única de las tres que un fichero puede quitar.

  FUENTE: UCSC Table Browser
  URL: https://genome.ucsc.edu/cgi-bin/hgTables

  PASOS:
    1. Abre el Table Browser de UCSC.
    2. En «assembly» elige mm39
    3. En «group» elige «Genes and Gene Predictions».
    4. En «track» elige «NCBI RefSeq».
    5. En «table» elige «RefSeq All» o «RefSeq Curated».
    6. En «output format» elige «sequence».
    7. Dale a «get output». Entonces pregunta que región quieres: marca SOLO «3' UTR Exons» y desmarca todo lo demas.
    8. Descarga el fichero y subelo tal cual.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · ensamblaje
      Dos ensamblajes dan coordenadas y contenidos distintos. Va en la procedencia del catalogo y viaja con cada veredicto.
    · fecha de la tabla
      RefSeq cambia. Sin la fecha, el conteo no es reproducible — la misma regla que el release de miRBase y la biblioteca de Dfam.
    · criterio de representante por gen
      «Un transcrito por gen» se puede decidir de varias formas (el más largo, el curado, el canónico). El número depende de cual se use, así que se declara.

  TAMAÑO APROXIMADO: unas decenas de MB

  COMO SE VALIDA AL SUBIRLO: Al subirlo la app comprueba que sea FASTA, que el alfabeto sea de ADN, cuenta secuencias y longitud total, calcula el md5 y AUDITA LAS ISOFORMAS: identificadores repetidos, secuencias idénticas y —si le das un mapa transcrito→gen— cuántos genes traen más de un transcrito. Sin ese mapa, esa tercera pregunta queda NO COMPROBADO, que no es «no las hay».

  AVISOS:
    ⚠ NO FILTRES LAS ISOFORMAS A MANO. Que lo haga la app: ella cuenta cuanto infla el conteo y lo dice al lado del resultado. Un filtrado manual no deja rastro y el número acaba siendo incomparable entre corridas.
    ⚠ La salida de «3' UTR Exons» da un registro POR EXON, así que un 3'UTR troceado aparece varias veces. No es un error del fichero: es como es, y por eso la app lo audita en vez de rechazarlo.
    ⚠ El fichero NO va a git — son decenas de MB. En el manifiesto quedan solo nombre, tamaño y md5, igual que con `refseq_rna.fa`.
```

### empalme_intron — NOT_RUN

**Que mide.** ¿Se escinde el intrón? Es el ÚNICO frente BINARIO del proyecto: los otros son graduales —una especificidad regular da off-targets, un techo de APA baja el knockdown— pero aquí, si el intrón no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y NO HAY PROTEINA DN EN ABSOLUTO. No hay «un poco de proteina» que optimizar.

**Por que importa / resultado.** RIESGO BINARIO. NO ES UN PARÁMETRO DE CALIDAD y no se lee como tal: o el intrón se escinde o no. Si no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y no hay proteina DN EN ABSOLUTO — no hay «un poco de proteina» que optimizar. Lo que decide no es un candidato ni una plaza del panel: decide si la ARQUITECTURA INTRÓNICA sigue viva. Por eso va como frente y no como columna. Y la lectura que se hace por defecto NO lo coge: un small RNA-seq puede salir PERFECTO con el empalme fallando. Drosha procesa el pri-miR COTRANSCRIPCIONALMENTE, o sea ANTES del splicing, así que la horquilla se corta igual este el intrón escindido o no. Un shmiR correcto NO ES EVIDENCIA de que haya proteina: son dos sucesos en orden y esa lectura solo mide el primero. SE CIERRA CON TRES LECTURAS DE BANCO, las tres NOT_RUN y ninguna la corre este software: (1) RT-PCR de empalme con cebadores en los exones que flanquean el intrón MVM; (2) Western L42 normalizado por vg-qPCR, que es lo que separa «no empalmo» de «no llego el vector»; (3) parental SIN INTRÓN en la misma tanda, como techo de expresión. Coordenadas NO emitidas en esta corrida: falta el casete (--transgen). El detalle, en el bloque «Empalme del intrón».

**Fuente de datos.** ninguna: este frente no se contesta con datos, sino en el banco

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| criterio de Kozak fuerte | purina en -3 y G en +4 | convencion | es el criterio que este análisis aplica para clasificar los uATG, declarado como parámetro y no citado  ⚠ SIN BASE MEDIDA: no se pondera la fuerza del contexto ni se usa ninguna matriz: es un corte binario sobre dos posiciones |
| aceptor de empalme utilizable | tracto de pirimidinas comparado con el aceptor LEGÍTIMO del mismo intrón | nuestro | la comparación es contra una referencia INTERNA —el aceptor que ya funciona en ese intrón— así que el veredicto no depende de ningún umbral traido de fuera. El legítimo tiene 9 pirimidinas contiguas; el mejor críptico, 3 |

**Como se cierra.** (ficha de obtencion, integra)

```
QUÉ HAY QUE MEDIR EN EL BANCO PARA CERRAR «empalme_intron»

  ¿La célula recorta bien la pieza que lleva el shmiR?
  El shmiR viaja dentro de una pieza —un intrón— que la célula tiene que recortar y tirar para poder fabricar la proteína del tratamiento. Si no la recorta, no hay proteína. Es la única comprobación de todo o nada: aquí no hay resultado a medias.

  QUE PREGUNTA RESPONDE: ¿Se escinde el intrón? Es el ÚNICO frente BINARIO del proyecto: los otros son graduales —una especificidad regular da off-targets, un techo de APA baja el knockdown— pero aquí, si el intrón no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y NO HAY PROTEINA DN EN ABSOLUTO. No hay «un poco de proteina» que optimizar.

  NO SE CIERRA CON NINGÚN FICHERO.
  Este frente NO SE CIERRA CON NINGÚN FICHERO, y por eso va aparte de los demas: sus cuatro lecturas son de BANCO y este software no corre ninguna. Conseguir más datos no lo cierra: hay que ir al laboratorio. Y es además el único frente BINARIO del proyecto —los otros son graduales y este no: o el intrón se escinde o no hay proteína DN en absoluto—, así que tampoco se lee como los demás: NINGUNO de los otros ocho lo detecta.

  FUENTE: Banco: RT-PCR, Western y secuenciacion. No hay descarga que valga.
  URL: —

  PASOS:
    1. RT-PCR de empalme con cebadores en los exones que flanquean el intrón MVM. La app emite las VENTANAS donde buscar los cebadores, derivadas del casete, no los cebadores: Tm, especificidad y horquillas no se improvisan.
    2. PARTE DE RNA CITOPLÁSMICO, NO TOTAL. El pre-mRNA sin empalmar es NUCLEAR: en RNA total sale siempre y no dice nada. Lo que sí es un fallo de empalme es encontrar el intrón retenido en el CITOPLASMA, que es donde se traduce.
    3. SELECCIONA POR polyA. Excluye la mayor parte del transcrito naciente, que es la otra fuente de banda larga que no es retención.
    4. TRATA CON DNasa Y CORRE UN CONTROL SIN RETROTRANSCRIPTASA (−RT). El genoma del AAV LLEVA el intrón dentro, así que una traza de ADN del vector amplifica y da una banda larga INDISTINGUIBLE de la retención. El control −RT tiene que salir vacío; si sale banda, lo que se está midiendo es ADN.
    5. LEE LA PROPORCIÓN corta/larga, NO la presencia de la larga. Y no se lee sola: hacen falta DOS referencias en la MISMA TANDA — el control sin intrón, que es el 100 % corta y fija dónde está el cero, y el terapéutico. Sin las dos, una proporción no se puede interpretar.
    6. SECUENCIA LA BANDA CORTA. Es la lectura que cierra el frente: el donante críptico `GTGAGCG` del andamio compite por el aceptor legítimo del MVM y produce una banda INTERMEDIA (+97 pb) que en un gel se confunde con la buena.
    7. Western con L42 NORMALIZADO POR vg-qPCR. Sin normalizar, «no hay proteina» no se distingue de «no llego el vector»: los dos dan una membrana vacía y solo uno culpa al empalme.
    8. Corre en la MISMA TANDA el parental SIN INTRÓN, como techo de expresión. Sin techo, un western flojo no dice si el empalme va mal o si la construcción expresa poco.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · que construcción se midio, con su md5
      La eficiencia de empalme es de UNA construcción. Sin identificarla, el número no se puede volver a comprobar ni comparar con otra.
    · la secuencia de la union exon-exon
      Es lo que cierra el frente. Una banda del tamaño esperado no descarta el donante críptico; su secuencia si.

  TAMAÑO APROXIMADO: —

  COMO SE VALIDA AL SUBIRLO: Lo que cierra el frente es la SECUENCIA DE LA UNION EXON-EXON, no la altura de una banda en un gel. Sin secuenciar, ver una banda corta no descarta el donante críptico. Y la banda LARGA no cierra nada en ninguna dirección: sale con el empalme perfecto.

  AVISOS:
    ⚠ LA PRESENCIA DE BANDA LARGA NO ES EVIDENCIA DE RETENCIÓN, y esto invalida la lectura ingenua del gel. El pre-mRNA sin empalmar EXISTE SIEMPRE: el splicing es cotranscripcional pero NO instantáneo, así que en cualquier población de transcritos hay nacientes a medio procesar y dan banda larga aunque el empalme sea PERFECTO. Aquí estuvo escrito «banda CORTA = empalmado, banda LARGA = retenido» y es FALSO. Por eso el ensayo lleva las cuatro condiciones de los pasos —citoplasma, polyA, DNasa con control −RT, y proporción con dos referencias— y no una de ellas: las tres primeras quitan del medio lo que no es retención, y la cuarta cambia lo que se lee.
    ⚠ UN small RNA-seq PERFECTO NO ES EVIDENCIA DE QUE HAYA PROTEINA. Drosha procesa el pri-miR COTRANSCRIPCIONALMENTE, o sea ANTES del splicing: la horquilla se corta igual este el intrón escindido o no. Son dos sucesos en orden y esa lectura solo mide el primero. Por eso este frente no estaba en la lista.
    ⚠ EL CEBADOR DE AGUAS ABAJO CAE DENTRO DEL ORF DE PrP. La especificidad de vector la da el cebador de aguas ARRIBA, y SOLO ese: un par con los dos cebadores aguas abajo amplificaria también el Prnp ENDOGENO del tejido — saldria banda, del tamaño esperado, y no sería del vector. Es el error que arruinaria el ensayo sin dar ninguna señal.
    ⚠ El casete que hay (`aav_casete.fa`) NO sirve como parental sin intrón: es el parental sin MÓDULO pero CON el intrón vacío de 82 nt, así que arrastra el mismo problema que se quiere medir. Y el intrón del terapeutico son 296 nt, no 82: la eficiencia de uno no dice nada del otro. La app específica el control sin intrón —donante y aceptor eliminados, todo lo demas conservado base a base— y sale en la hoja de pedido.
```

### empalme_sitios — NOT_RUN

**Que mide.** ¿El módulo de esta guía introduce un sitio de splicing críptico dentro del intrón? La unidad no es la guía: es el CASSETTE MONTADO —intrón completo, módulo dentro, guía y pasajera de ese candidato, y contexto exonico a los dos lados—. Un críptico que compita con el donante legítimo produce una banda intermedia que en un gel se confunde con la buena.

**Por que importa / resultado.** NOT_RUN: no se ha consultado la predicción de sitios de splicing sobre ningún cassette montado. La unidad de este frente es el PAR candidato x intrón, no el candidato. Es DESEMPATE Y ALERTA, nunca filtro: no puede excluir a nadie, y por eso su veredicto solo puede ser NOT_RUN o PASS. Lo accionable es que guías introducen crípticos que las otras no.

**Fuente de datos.** el resultado de SpliceAI sobre las construcciones, subido por su modal. No sale del informe de tilado porque la unidad de ese frente es el par candidato x intrón, no la ventana

**Criterio.** Este frente NO tiene umbral ABSOLUTO, y no se puede inventar uno: SpliceAI se entreno sobre secuencia genomica humana con ventana de 10.000 nt para predecir el efecto de variantes, y un cassette de AAV no se le parece. Lo que si tiene es un umbral RELATIVO declarado: solo se listan los sitios que llegan al 5 % de la puntuación del DONANTE LEGÍTIMO del mismo intrón en la MISMA corrida. Ese referente interno es lo único que hace interpretable el número — el mismo criterio con el que ya se descartaron los aceptores crípticos, comparando su tracto de pirimidinas contra las nueve del legítimo.

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «empalme_sitios»

  ¿La guía crea un corte donde no debería?
  Al meter tu guía dentro de esa pieza puede aparecer por casualidad una señal de corte nueva. Si la célula la usa, corta por donde no toca y el tratamiento sale mal montado.

  QUE PREGUNTA RESPONDE: ¿El módulo de esta guía introduce un sitio de splicing críptico dentro del intrón? La unidad no es la guía: es el CASSETTE MONTADO —intrón completo, módulo dentro, guía y pasajera de ese candidato, y contexto exonico a los dos lados—. Un críptico que compita con el donante legítimo produce una banda intermedia que en un gel se confunde con la buena.

  FICHERO(S) QUE HACEN FALTA:
    · resultado de SpliceAI sobre las construcciones (TSV)  [OBLIGATORIO]
      Las puntuaciones por posición de cada cassette montado. La app no las calcula: no tiene red y la invocación no esta verificada.

  FUENTE: SpliceAI, ejecutado por ti. La app prepara las construcciones y recoge el resultado.
  URL: —

  PASOS:
    1. Abre el cuarto modal y elige los candidatos y los intrones que quieras consultar. Recuerda que la unidad es el PAR: diez candidatos por tres intrones son treinta consultas.
    2. LEE LOS AVISOS DE ARRIBA ANTES DE NADA. SpliceAI no fue entrenado para esto y sus puntuaciones absolutas no son interpretables sobre un cassette de AAV.
    3. Descarga el FASTA de construcciones. Cada cabecera lleva su md5, la ventana de contexto y las posiciones del donante y el aceptor legítimos: no la edites.
    4. Pasa el FASTA por SpliceAI en tu máquina. La app NO da la orden: esa invocación no se ha verificado desde este proyecto y no se inventa (regla 4). Si nos dices cual usas, se añade.
    5. Pasa su salida al formato que la app acepta: un TSV con las columnas `construccion`, `md5`, `posicion`, `tipo` (donante o aceptor) y `puntuacion`. La posición es 1-based DENTRO de la construcción.
    6. Sube el TSV. La app compara cada sitio contra el DONANTE LEGÍTIMO del mismo intrón en la misma corrida, que es el único referente que vale.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · versión de SpliceAI y del modelo
      Dos versiones dan números distintos, y como aquí todo es comparación relativa dentro de una corrida, mezclar versiones entre corridas invalidaria la comparación.
    · la ventana de contexto con la que se corrió
      Cambia el resultado. La app declara la que puso en la construcción; si tu herramienta añade o recorta contexto, hay que saberlo.

  TAMAÑO APROXIMADO: el FASTA de construcciones son unos KB; el resultado, unos KB

  COMO SE VALIDA AL SUBIRLO: Al subir el resultado la app comprueba que CADA construcción sea una de las que ella genero y que su md5 CUADRE. Un resultado de otra corrida NO puede entrar, aunque encaje de forma: es el fallo del CSV de miRarchitect, un fichero de otra corrida pegado por error que produce un análisis entero sobre el dato equivocado. Un resultado con solo cabecera también se rechaza: cero sitios y «la corrida no llego a correr» son cosas distintas y ese fichero no las distingue.

  AVISOS:
    ⚠ SpliceAI NO FUE ENTRENADO PARA ESTO. Se entreno sobre secuencia genomica humana con ventana de 10.000 nt para predecir el efecto de VARIANTES. Un cassette de AAV no se le parece: no hay contexto genomico, las longitudes son atipicas y la composición también.
    ⚠ NO HAY UMBRAL ABSOLUTO Y NO SE PUEDE INVENTAR UNO. Un 0,8 aquí no significa lo que significa un 0,8 en el genoma humano. Lo único que vale es la comparación RELATIVA contra el donante legítimo del mismo intrón en la MISMA corrida — el mismo criterio con el que ya se descartaron los aceptores crípticos, comparando su tracto de pirimidinas contra las nueve del legítimo.
    ⚠ LA VENTANA DE CONTEXTO CAMBIA EL RESULTADO. Va declarada y viaja con cada consulta: dos corridas con contextos distintos no son comparables.
    ⚠ DESEMPATE Y ALERTA, NUNCA FILTRO. Este frente no puede excluir a ningún candidato: su veredicto solo puede ser NOT_RUN o PASS. Lo accionable es que guías introducen crípticos que las otras NO — si nueve dan un perfil limpio y una no, esa se cambia.
    ⚠ LA ACCESIBILIDAD ESTRUCTURAL VA EN EL MISMO MODAL Y APARTE EN EL RESULTADO. Esa si corre entera aquí (ViennaRNA) y da un número PROPIO, no prestado de un modelo entrenado para otra cosa. Son dos preguntas y no se mezclan.
```

### fraccion_isoforma_larga — CERRADO

**Que mide.** ¿Que fracción de los transcritos conserva la diana? Un sitio de poliadenilación alternativa proximal corta el 3'UTR, así que un candidato por detrás de ese corte solo tiene diana en la isoforma larga. Eso no es un veto: es un TECHO de knockdown.

**Por que importa / resultado.** CERRADO. 7 de 11 candidatos quedan por detrás del corte de tx:1185: comparten UN ÚNICO MODO DE FALLO. Y el rebalanceo tiene tope: los sitios inmunes por tramo son 16/0/0 —todos en el proximal— y el espaciado deja meter cuatro, que son los 4 que ya están. POR QUE BLOQUEABA: si la fracción de isoforma corta es alta, esos 7 candidatos entran al cribado con un TECHO INDISTINGUIBLE DE UN shmiR MALO — un techo de 0,3 y una guía que no funciona dan la misma lectura en la placa, y el experimento se gasta en no poder separarlos. ESTADO: MEDIDO. PolyA_DB v4.1, fracción larga 0.86 ponderada / 0.65 sin ponderar. El mapeo genomico↔transcrito que bloqueaba está RESUELTO sin coordenadas genomicas y sobre 4 puntos de apoyo, no sobre una resta. Y el techo no es uno: va POR TRAMOS (0.91, 0.86), porque depende de por detrás de cuántos cortes está cada candidato. Con eso deja de cumplirse lo que hacia bloquear a este frente: un techo de 0.86 NO es indistinguible de un shmiR malo en la placa. RESERVA QUE SE MANTIENE: el dato es de TODOS LOS TEJIDOS, no cerebro, y las neuronas alargan los 3'UTR, así que estas cifras son un LÍMITE INFERIOR conservador para el nuestro. La RT-qPCR de los dos amplicones sigue en pie y puede MEJORARLAS.

**Fuente de datos.** MAPEO GENOMICO↔TRANSCRITO — RESUELTO SIN COORDENADAS GENOMICAS. ·   PolyA_DB pública el sitio de CORTE, NO EL HEXÁMERO. Su leyenda: «A[A/U]UAAA motif within 40-nt upstream from the PAS» — el hexámero se busca AGUAS ARRIBA del PAS, luego la coordenada publicada es el corte. Con nuestra convención el hexámero cae 10-30 nt por delante, dentro de esos 40 nt. ·   Hipotesis «PAS = hexámero»: DESCARTADA. Un hexámero es un punto, no una banda, así que ·   bajo esa lectura el aterrizaje tiene que ser EXACTO — y no hay ningún desfase que haga ·   aterrizar más de 1 de las 4 coordenadas. Bajo «PAS = corte» aterrizan las 4, ·   con el MISMO desfase y con la CLASE de hexámero que declara la propia base en cada una. ·   No es una resta: son 4 puntos de apoyo independientes. Desfase 3'UTR→mm10 acotado a 131937185-131937193 (9 valores); se deja como INTERVALO ·   porque la banda de corte mide 20 nt y fijarlo en un entero sería inventarse precisión. ·  ·     chr2:+:131937444  Other   → corte 3utr:251-271, hexámero AATATA en 3utr:236  PSE 21.1%, AvgRPM 0.55  ← TERCER sitio de corte, el proximal MÁS USADO de los tres ·     chr2:+:131937504  AAUAAA  → corte 3utr:303-323, hexámero AATAAA en 3utr:288  PSE 23.5%, AvgRPM 0.34  ← nuestro AATAAA de 3utr:288 ·     chr2:+:131938392  Other   → AMBIGUO: 2 hexámeros de su clase en la banda (TATAAA en 3utr:1178, TATAAA en 3utr:1189). Ancla, pero NO entra al modelo con banda propia. ·     chr2:+:131938427  AUUAAA  → corte 3utr:1229-1249, hexámero ATTAAA en 3utr:1214  (sin datos de expresión)  ← fuerza 99,9 %, conservado en humano y rata; SIN expresión, así que no entra en la fracción — solo ancla ·  ·   TECHO POR TRAMOS. Con tres sitios de corte medidos el techo ya no es UNO: la pregunta ·   de un candidato no es cuanta isoforma larga hay, es que fracción de transcritos conserva ·   SU diana — y eso depende de por detrás de cuántos cortes esta. ·     tx:1-1200  sin techo            por delante de todos los cortes medidos: la diana está en TODAS las isoformas. INMUNE. ·     tx:1201-1220  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937444: no se sabe de que lado cae, así que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     tx:1221-1252  techo 0.91           por detrás de chr2:+:131937444 ·     tx:1253-1272  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937504: no se sabe de que lado cae, así que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     tx:1273-2191  techo 0.86           por detrás de chr2:+:131937444, chr2:+:131937504

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| banda de corte por detrás del hexámero | 10-30 nt aguas abajo | literatura | el corte de poliadenilación ocurre a esa distancia del hexámero; es un resultado clasico del procesamiento del extremo 3' |
| flanco prohibido alrededor del hexámero (eje esterico) | ±10 nt | convencion | es un umbral OPERATIVO para marcar solapamiento con la señal de poliadenilacion  ⚠ SIN BASE MEDIDA: NO TIENE BASE MEDIDA, y es el caso que obliga a distinguir origenes. La huella real de CPSF/CstF sobre el pre-mRNA es MAYOR que 10 nt, así que una ventana que el filtro deja pasar por 4 nt está probablemente dentro de la zona de competencia. El eje esterico es un GRADIENTE, no una frontera: cualquier umbral en nucleótidos le atribuye una precisión que la biologia no tiene. Por eso el informe emite además la SENSIBILIDAD al flanco |

## 4. Anatomía del transcrito

De dónde sale cada frontera. La procedencia de la anotación importa tanto como el número: una frontera declarada y una anotada no sostienen lo mismo.

| tramo | inicio | fin | longitud | origen |
|---|---|---|---|---|
| 5'UTR | 1 | 184 | 184 | coordenadas del transcrito de referencia, comprobadas por checksum |
| CDS | 185 | 949 | 765 | coordenadas del transcrito de referencia, comprobadas por checksum |
| 3'UTR | 950 | 2191 | 1242 | coordenadas del transcrito de referencia, comprobadas por checksum |

## 5. Mapa del 3'UTR

Todo a la misma escala: los candidatos numerados por su puesto en el panel, las señales de poliadenilación con su banda de corte, los tercios y —cuando la hay— la conservación. El mapa del informe es de CARACTERES y no el SVG de la página: el PDF de este proyecto se escribe con las fuentes base-14 y no incrusta imágenes, así que un mapa dibujado saldría en un formato y no en los otros. En caracteres se dibuja una vez y sale igual en los tres — todo a la misma escala, y la misma escala en markdown, en `.docx` y en `.pdf`.

```
  nt      1         125       249       374       498       622       746       870       995       1119
          |         |         |         |         |         |         |         |         |         |
  tercios -------------proximal------------|--------------medio-------------|-------------distal--------------
  conserv NOT_RUN: no se ha dado informe de conservación para esta especie.
  polyA                      M   M                                                A   A     A           AA T
  corte                       === ===                                              === ===    ==         =====
  cand     1   2     3    4                   5       6       7      8     9               10  11

  3'UTR de 1242 nt en 100 columnas — 12.4 nt por columna (marco de lo tilado: tx).
  M = señal polyA con uso MEDIDO · A = señal polyA por canonicidad, sin dato de uso · T = terminal probable
  · = banda de corte (10-30 nt aguas abajo del hexámero) · # = bloque conservado · ~ = repetición
  enmascarada · dígito = candidato, por su puesto en el panel.
  2 banda(s) de corte se salen del transcrito anotado: el corte de una terminal cae aguas abajo del final.
  Van recortadas.
  1=tx:959  2=tx:1009  3=tx:1092  4=tx:1149  5=tx:1398  6=tx:1502  7=tx:1601  8=tx:1684  9=tx:1768
  10=tx:1967  11=tx:2020
```

Cobertura por tercios: cuántos sitios elegibles hay en cada tramo, cuántos candidatos del panel caen ahí con cada una de las dos definiciones de tercio, y cuál sería el siguiente sin romper el espaciado. Un tramo que se ve vacío en el mapa puede estarlo porque no hay sitios elegibles o porque no caben: no es lo mismo.

```
  proximal — 3utr:1-414, 414 nt: 28 sitios elegibles por inicio (28 por punto medio).
    Panel: 4 candidato(s) por PUNTO MEDIO —la definición que usa la cuota— y 4 por inicio. Cuota 1:
      cumplida.
    Margen: 18 sitio(s) del tramo quedan a 50 nt o más de 3utr:200, y 12 lo cumplen con TODO el panel. El
      que manda es el segundo: añadir uno exige espaciado con todos.
    Los mejores del tramo a 50 nt o más de 3utr:200, por el mismo orden con que se eligió el panel
      (asimetría): 3utr:359-380 (asimetría +4.82); 3utr:329-350 (asimetría +4.39); 3utr:69-90 (asimetría
      +3.80).
    Los que además caben con TODO el panel NO son los mismos: 3utr:359-380 (asimetría +4.82); 3utr:329-350
      (asimetría +4.39); 3utr:338-359 (asimetría +3.79).
  medio — 3utr:415-828, 414 nt: 42 sitios elegibles por inicio (41 por punto medio).
    Panel: 4 candidato(s) por PUNTO MEDIO —la definición que usa la cuota— y 5 por inicio. Cuota 1:
      cumplida.
    Margen: 27 sitio(s) del tramo quedan a 50 nt o más de 3utr:735, y 0 lo cumplen con TODO el panel. El que
      manda es el segundo: añadir uno exige espaciado con todos.
    Los mejores del tramo a 50 nt o más de 3utr:735, por el mismo orden con que se eligió el panel
      (asimetría): 3utr:573-594 (asimetría +4.42); 3utr:673-694 (asimetría +4.42); 3utr:517-538 (asimetría
      +4.33).
    No queda ninguno: o no hay más sitios elegibles en el tramo o todos caen a menos de 50 nt de un
      candidato ya elegido.
  distal — 3utr:829-1242, 414 nt: 16 sitios elegibles por inicio (17 por punto medio).
    Panel: 3 candidato(s) por PUNTO MEDIO —la definición que usa la cuota— y 2 por inicio. Cuota 1:
      cumplida.
    OJO, borde: 3utr:819 cuenta(n) en este tercio por punto medio y empieza(n) en el anterior. Cubre(n) el
      primer nucleótido del tramo, no el tramo.
    Margen: 8 sitio(s) del tramo quedan a 50 nt o más de 3utr:1071, y 4 lo cumplen con TODO el panel. El que
      manda es el segundo: añadir uno exige espaciado con todos.
    Los mejores del tramo a 50 nt o más de 3utr:1071, por el mismo orden con que se eligió el panel
      (asimetría): 3utr:900-921 (asimetría +4.15); 3utr:851-872 (asimetría +3.19); 3utr:846-867 (asimetría
      +3.12).
    Los que además caben con TODO el panel NO son los mismos: 3utr:900-921 (asimetría +4.15); 3utr:922-943
      (asimetría +1.90); 3utr:904-925 (asimetría +1.33).
```

## 6. Tabla de candidatos

Todas las columnas, con un estado POR FILTRO. No se colapsan ni se omiten los que no corrieron: un filtro ausente de la tabla es indistinguible de uno superado.

| rango | inicio | fin | region | inicio_3utr | fin_3utr | tercio | asimetria_kcal | polyA_hexamero | polyA_clase | polyA_posicion_rel | polyA_hexamero_pos | polyA_dist_extremo3 | polyA_solapa_seed | polyA_veredicto | polyA_estricto | polyA_escalonado | polyA_truncamiento | polyA_truncamiento_propio | polyA_esterico | polyA_dist_corte | polyA_fraccion_isoforma_larga | tilado_8mer | tilado_7mer-m8 | tilado_7mer-A1 | carga_8mer | carga_7mer-m8 | carga_7mer-A1 | carga_6mer | accesibilidad | GC | homopolimero | asimetria | zona_prohibida_polyA | repeticiones | repeticion_polimorfica | seed | especificidad | transgen | seed_colision | bandera_polyA_debil | biofisicos_ok | riesgo_APA | veredicto | diana | guia |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | 959 | 980 | 3'UTR | 10 | 31 | proximal | 4.33 |  |  |  |  |  | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | TCCTGCTTGTTCCTTCGCATTC | UAAUGCGAAGGAACAAGCAGGA |
| 6 | 1009 | 1030 | 3'UTR | 60 | 81 | proximal | 5.15 |  |  |  |  |  | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | CCACCTGTAGCTCTTTCAATTG | UAAUUGAAAGAGCUACAGGUGG |
| 7 | 1092 | 1113 | 3'UTR | 143 | 164 | proximal | 5.08 | AATATA | APA_POSIBLE | aguas abajo, 71 nt | tx:1185 | 1001 nt | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | GCCCTGGGAAATGTACAGTAGA | UCUACUGUACAUUUCCCAGGGC |
| 11 | 1149 | 1170 | 3'UTR | 200 | 221 | proximal | 3.8 | AATATA | APA_POSIBLE | aguas abajo, 14 nt | tx:1185 | 1001 nt | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | TCTGTCATCAGCCAGTGCTAAC | UUUAGCACUGGCUGAUGACAGA |
| 5 | 1398 | 1419 | 3'UTR | 449 | 470 | medio | 5.32 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 198 |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GTGGAATTCTTTCTTTACTAAC | UUUAGUAAAGAAAGAAUUCCAC |
| 3 | 1502 | 1523 | 3'UTR | 553 | 574 | medio | 5.86 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 302 |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | AGGGCACTAGAATGATCTTTAG | UUAAAGAUCAUUCUAGUGCCCU |
| 4 | 1601 | 1622 | 3'UTR | 652 | 673 | medio | 5.8 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 401 |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GAGGGATGGTTAAGGTACAAAG | UUUUGUACCUUAACCAUCCCUC |
| 8 | 1684 | 1705 | 3'UTR | 735 | 756 | medio | 5.08 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 484 |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GCCCTATGTTTCTGTACTTCTA | UAGAAGUACAGAAACAUAGGGC |
| 2 | 1768 | 1789 | 3'UTR | 819 | 840 | distal | 5.96 | CATAAA | OTRA | aguas abajo, 66 nt | tx:1856 | 330 nt | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 568 |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GCTCCATTCCAAAGTGGGAAAG | UUUUCCCACUUUGGAAUGGAGC |
| 1 | 1967 | 1988 | 3'UTR | 1018 | 1039 | distal | 6.65 | ACTAAA | OTRA | dentro | tx:1983 | 203 nt | si | PASS | FAIL | PASS | TECHO | NO_APLICA | PENALIZADO | 767 |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | True | True | prediccion:si | INCOMPLETE | GGCCGTTCCATCCAGTACTAAA | UUUAGUACUGGAUGGAACGGCC |
| 10 | 2020 | 2041 | 3'UTR | 1071 | 1092 | distal | 4.28 | ACTAAA | OTRA | aguas arriba, 31 nt | tx:1983 | 203 nt | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 820 |  |  |  |  |  |  |  |  | NO_PEDIDO | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | TGCACTCAGTTCCGTAGGATTC | UAAUCCUACGGAACUGAGUGCA |

> **MULTIPLEXADO: hay candidatos que comparten núcleo.**

- tx:1398 y tx:1967 comparten el núcleo TACTAA con heptameros DISTINTOS (TTAGTAA y TTAGTAC): difieren solo en la posición 8, así que la colisión de seed no los empareja y este eje si.

CONSECUENCIA PARA EL MULTIPLEXADO. Dos candidatos que comparten el NÚCLEO de 6 nt no son dos apuestas independientes en el eje de off-targets, aunque su heptamero difiera y aunque el espaciado los de por buenos: las cuatro clases de sitio se construyen sobre ese núcleo, así que casi toda su red de dianas accesorias es la misma. Y el espaciado no lo ve — mide DISTANCIA en el 3'UTR, no parecido de seed. El caso murino es exactamente ese: `3utr:449` y `3utr:1018` son la pareja que el espaciado sugeriria —extremos opuestos del 3'UTR y los dos con buena asimetría— y en este eje serían la PEOR elección posible.

CARGA DE SEED SIN REFERENCIA — NOT_RUN. Los conteos por clase del tilado (`tilado_<clase>`) están, y solos no se pueden leer: falta el PERCENTIL contra la nula por permutación, falta el `6mer` y faltan los controles biológicos (miR-124-3p, miR-9-5p, let-7a-5p). Los dos los calcula el modal de carga de off-targets, que necesita `transcriptoma_3utr.fa` y una corrida guardada en el proyecto. Son DOS referencias y ninguna sustituye a la otra: el percentil contra la nula por permutación dice si el número es raro PARA ESA COMPOSICIÓN de heptámero, y los controles biológicos dan la MAGNITUD — qué es «muchos sitios» en un cerebro de verdad. Los controles no llevan percentil a propósito: se calcularía contra la nula de su propia composición, así que no sería comparable con el nuestro. Las clases no se suman: la represión esperada de un 8mer y la de un 6mer no se parecen en nada. Por eso no hay —ni puede haber— un percentil de un total: el percentil va POR CLASE, pegado a su conteo, y es lo que sale en las columnas `carga_<clase>`.

## 7. Todos los sitios elegibles, con una columna por frente — mouse

Todos, no sólo los seleccionados: la selección es una propuesta y esta tabla es el conjunto sobre el que se hizo. Una columna por frente, derivada de los frentes que el informe conoce.

| elegido | sitio | inicio | tercio | asimetria | rango | empalme_intron | empalme_sitios | especificidad | fraccion_isoforma_larga | offtarget_seed:guia | offtarget_seed:pasajera | repeticion_polimorfica | repeticiones | seed | seed_colision:guia | seed_colision:pasajera | transgen | veredicto | guia |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| True | 3utr:1018 | 1967 | distal | 7.65 | 1 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUAGUACUGGAUGGAACGGCC |
| True | 3utr:819 | 1768 | distal | 5.96 | 2 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUCCCACUUUGGAAUGGAGC |
| True | 3utr:553 | 1502 | medio | 5.86 | 3 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAAAGAUCAUUCUAGUGCCCU |
| True | 3utr:652 | 1601 | medio | 5.8 | 4 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUGUACCUUAACCAUCCCUC |
| True | 3utr:449 | 1398 | medio | 5.32 | 5 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUAGUAAAGAAAGAAUUCCAC |
| True | 3utr:60 | 1009 | proximal | 5.15 | 6 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUUGAAAGAGCUACAGGUGG |
| True | 3utr:143 | 1092 | proximal | 5.08 | 7 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUACUGUACAUUUCCCAGGGC |
| True | 3utr:735 | 1684 | medio | 5.08 | 8 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAGUACAGAAACAUAGGGC |
| True | 3utr:10 | 959 | proximal | 4.33 | 9 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUGCGAAGGAACAAGCAGGA |
| True | 3utr:1071 | 2020 | distal | 4.28 | 10 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUCCUACGGAACUGAGUGCA |
| True | 3utr:200 | 1149 | proximal | 3.8 | 11 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUAGCACUGGCUGAUGACAGA |
| False | 3utr:9 | 958 | proximal | 2.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUGCGAAGGAACAAGCAGGAA |
| False | 3utr:11 | 960 | proximal | 2.96 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAUGCGAAGGAACAAGCAGG |
| False | 3utr:12 | 961 | proximal | 2.75 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAUGCGAAGGAACAAGCAG |
| False | 3utr:13 | 962 | proximal | 0.62 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAGAAUGCGAAGGAACAAGCA |
| False | 3utr:20 | 969 | proximal | 1.93 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGACCACGAGAAUGCGAAGGA |
| False | 3utr:53 | 1002 | proximal | 3.45 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAGCUACAGGUGGAUAACCC |
| False | 3utr:54 | 1003 | proximal | 2.09 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGAGCUACAGGUGGAUAACC |
| False | 3utr:55 | 1004 | proximal | 1.76 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAGAGCUACAGGUGGAUAAC |
| False | 3utr:58 | 1007 | proximal | 2.74 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGAAAGAGCUACAGGUGGAU |
| False | 3utr:59 | 1008 | proximal | 4.36 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUGAAAGAGCUACAGGUGGA |
| False | 3utr:61 | 1010 | proximal | 3.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAAUUGAAAGAGCUACAGGUG |
| False | 3utr:62 | 1011 | proximal | 2.19 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCAAUUGAAAGAGCUACAGGU |
| False | 3utr:63 | 1012 | proximal | 1.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUCAAUUGAAAGAGCUACAGG |
| False | 3utr:69 | 1018 | proximal | 3.8 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAACCACCUCAAUUGAAAGAGC |
| False | 3utr:70 | 1019 | proximal | 1.57 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAACCACCUCAAUUGAAAGAG |
| False | 3utr:75 | 1024 | proximal | 2.03 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUGAGAACCACCUCAAUUGA |
| False | 3utr:81 | 1030 | proximal | 1.31 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGCAAGAAUGAGAACCACCUC |
| False | 3utr:82 | 1031 | proximal | 2.79 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGCAAGAAUGAGAACCACCU |
| False | 3utr:83 | 1032 | proximal | 3.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAGCAAGAAUGAGAACCACC |
| False | 3utr:84 | 1033 | proximal | 2.75 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAGCAAGAAUGAGAACCAC |
| False | 3utr:85 | 1034 | proximal | 0.62 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAGAAGCAAGAAUGAGAACCA |
| False | 3utr:86 | 1035 | proximal | 1.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAGAAGCAAGAAUGAGAACC |
| False | 3utr:90 | 1039 | proximal | 1.31 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UACACAGAGAAGCAAGAAUGAG |
| False | 3utr:144 | 1093 | proximal | 3.69 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUACUGUACAUUUCCCAGGG |
| False | 3utr:145 | 1094 | proximal | 1.2 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUCUACUGUACAUUUCCCAGG |
| False | 3utr:146 | 1095 | proximal | 0.74 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGGUCUACUGUACAUUUCCCAG |
| False | 3utr:147 | 1096 | proximal | 2.33 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGGUCUACUGUACAUUUCCCA |
| False | 3utr:148 | 1097 | proximal | 2.33 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUGGUCUACUGUACAUUUCCC |
| False | 3utr:149 | 1098 | proximal | 1.34 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UACUGGUCUACUGUACAUUUCC |
| False | 3utr:155 | 1104 | proximal | 0.95 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAGCAACUGGUCUACUGUAC |
| False | 3utr:156 | 1105 | proximal | 0.89 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGAGCAACUGGUCUACUGUA |
| False | 3utr:157 | 1106 | proximal | 3.69 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAGAGCAACUGGUCUACUGU |
| False | 3utr:158 | 1107 | proximal | 1.49 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAAAGAGCAACUGGUCUACUG |
| False | 3utr:161 | 1110 | proximal | 0.97 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGCAAAGAGCAACUGGUCUA |
| False | 3utr:162 | 1111 | proximal | 1.73 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAGCAAAGAGCAACUGGUCU |
| False | 3utr:163 | 1112 | proximal | 3.36 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGAAGCAAAGAGCAACUGGUC |
| False | 3utr:164 | 1113 | proximal | 0.62 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUGAAGCAAAGAGCAACUGGU |
| False | 3utr:165 | 1114 | proximal | 0.66 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCCUGAAGCAAAGAGCAACUGG |
| False | 3utr:171 | 1120 | proximal | 3.96 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGGGACCUGAAGCAAAGAGC |
| False | 3utr:172 | 1121 | proximal | 3.77 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAGGGACCUGAAGCAAAGAG |
| False | 3utr:176 | 1125 | proximal | 1.35 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAUCAAAGGGACCUGAAGCAA |
| False | 3utr:183 | 1132 | proximal | 0.59 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAGACUCCAUCAAAGGGACCU |
| False | 3utr:185 | 1134 | proximal | 1.6 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGACAGACUCCAUCAAAGGGAC |
| False | 3utr:186 | 1135 | proximal | 3.93 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGACAGACUCCAUCAAAGGGA |
| False | 3utr:187 | 1136 | proximal | 4.06 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUGACAGACUCCAUCAAAGGG |
| False | 3utr:188 | 1137 | proximal | 1.16 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAUGACAGACUCCAUCAAAGG |
| False | 3utr:199 | 1148 | proximal | 2.33 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGCACUGGCUGAUGACAGAC |
| False | 3utr:201 | 1150 | proximal | 1.6 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUUAGCACUGGCUGAUGACAG |
| False | 3utr:202 | 1151 | proximal | 1.87 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUUAGCACUGGCUGAUGACA |
| False | 3utr:307 | 1256 | proximal | 2.67 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUACUCUGGGUACAAGUCAGG |
| False | 3utr:308 | 1257 | proximal | 1.71 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUACUCUGGGUACAAGUCAG |
| False | 3utr:309 | 1258 | proximal | 2.73 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGUACUCUGGGUACAAGUCA |
| False | 3utr:310 | 1259 | proximal | 1.76 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUUGUACUCUGGGUACAAGUC |
| False | 3utr:316 | 1265 | proximal | 2.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUCACCUUGUACUCUGGGUA |
| False | 3utr:317 | 1266 | proximal | 2.22 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUGUCACCUUGUACUCUGGGU |
| False | 3utr:319 | 1268 | proximal | 1.2 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCACUGUCACCUUGUACUCUGG |
| False | 3utr:320 | 1269 | proximal | 1.6 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCACUGUCACCUUGUACUCUG |
| False | 3utr:322 | 1271 | proximal | 1.84 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUCACUGUCACCUUGUACUC |
| False | 3utr:324 | 1273 | proximal | 1.43 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUGUCACUGUCACCUUGUAC |
| False | 3utr:325 | 1274 | proximal | 0.69 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUGUGUCACUGUCACCUUGUA |
| False | 3utr:328 | 1277 | proximal | 1.77 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUACAUGUGUCACUGUCACCUU |
| False | 3utr:329 | 1278 | proximal | 4.39 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUACAUGUGUCACUGUCACCU |
| False | 3utr:330 | 1279 | proximal | 3.23 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUUACAUGUGUCACUGUCACC |
| False | 3utr:331 | 1280 | proximal | 1.5 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGUUACAUGUGUCACUGUCAC |
| False | 3utr:332 | 1281 | proximal | 2.36 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGUUACAUGUGUCACUGUCA |
| False | 3utr:333 | 1282 | proximal | 3.96 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAAGUUACAUGUGUCACUGUC |
| False | 3utr:334 | 1283 | proximal | 1.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUAAGUUACAUGUGUCACUGU |
| False | 3utr:337 | 1286 | proximal | 2.16 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUGCUAAGUUACAUGUGUCAC |
| False | 3utr:338 | 1287 | proximal | 3.79 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAUGCUAAGUUACAUGUGUCA |
| False | 3utr:339 | 1288 | proximal | 1.39 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUAUGCUAAGUUACAUGUGUC |
| False | 3utr:343 | 1292 | proximal | 1.8 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGCCUAUGCUAAGUUACAUG |
| False | 3utr:344 | 1293 | proximal | 2.66 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUGCCUAUGCUAAGUUACAU |
| False | 3utr:352 | 1301 | proximal | 2.49 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGAACCCUUUGCCUAUGCUA |
| False | 3utr:353 | 1302 | proximal | 1.93 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUAGAACCCUUUGCCUAUGCU |
| False | 3utr:354 | 1303 | proximal | 1.8 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUAGAACCCUUUGCCUAUGC |
| False | 3utr:355 | 1304 | proximal | 0.57 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGUAGAACCCUUUGCCUAUG |
| False | 3utr:358 | 1307 | proximal | 2.46 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGGUUGUAGAACCCUUUGCCU |
| False | 3utr:359 | 1308 | proximal | 4.82 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGGUUGUAGAACCCUUUGCC |
| False | 3utr:360 | 1309 | proximal | 4.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUGGUUGUAGAACCCUUUGC |
| False | 3utr:363 | 1312 | proximal | 2.06 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUCUUUGGUUGUAGAACCCUU |
| False | 3utr:364 | 1313 | proximal | 3.69 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUUCUUUGGUUGUAGAACCCU |
| False | 3utr:365 | 1314 | proximal | 1.6 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGCUUCUUUGGUUGUAGAACCC |
| False | 3utr:373 | 1322 | proximal | 2.99 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAACAGUGGCUUCUUUGGUUG |
| False | 3utr:374 | 1323 | proximal | 1.49 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAAACAGUGGCUUCUUUGGUU |
| False | 3utr:426 | 1375 | medio | 2.17 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUGGAUGCUCUAGCUAUCCCA |
| False | 3utr:434 | 1383 | medio | 1.73 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUCCACGUGUGGAUGCUCUAG |
| False | 3utr:435 | 1384 | medio | 2.4 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUCCACGUGUGGAUGCUCUA |
| False | 3utr:436 | 1385 | medio | 3.6 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUUCCACGUGUGGAUGCUCU |
| False | 3utr:437 | 1386 | medio | 3.36 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAUUCCACGUGUGGAUGCUC |
| False | 3utr:438 | 1387 | medio | 1.85 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAUUCCACGUGUGGAUGCU |
| False | 3utr:439 | 1388 | medio | 2.29 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGAAUUCCACGUGUGGAUGC |
| False | 3utr:440 | 1389 | medio | 3.27 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAGAAUUCCACGUGUGGAUG |
| False | 3utr:441 | 1390 | medio | 1.77 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAAGAAUUCCACGUGUGGAU |
| False | 3utr:442 | 1391 | medio | 1.96 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAAGAAUUCCACGUGUGGA |
| False | 3utr:443 | 1392 | medio | 3.72 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGAAAGAAUUCCACGUGUGG |
| False | 3utr:444 | 1393 | medio | 3.72 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAGAAAGAAUUCCACGUGUG |
| False | 3utr:445 | 1394 | medio | 3.85 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAAAGAAAGAAUUCCACGUGU |
| False | 3utr:446 | 1395 | medio | 1.93 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUAAAGAAAGAAUUCCACGUG |
| False | 3utr:447 | 1396 | medio | 1.19 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGUAAAGAAAGAAUUCCACGU |
| False | 3utr:448 | 1397 | medio | 2.82 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGUAAAGAAAGAAUUCCACG |
| False | 3utr:465 | 1414 | medio | 2.29 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUCAGCUAUCGUUUGUUAGU |
| False | 3utr:468 | 1417 | medio | 0.62 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUCAAUCAGCUAUCGUUUGUU |
| False | 3utr:473 | 1422 | medio | 2.53 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGCCUUCAAUCAGCUAUCGU |
| False | 3utr:474 | 1423 | medio | 0.98 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUUGCCUUCAAUCAGCUAUCG |
| False | 3utr:478 | 1427 | medio | 0.59 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCCUGUUGCCUUCAAUCAGCU |
| False | 3utr:479 | 1428 | medio | 3.85 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUCCUGUUGCCUUCAAUCAGC |
| False | 3utr:512 | 1461 | medio | 1.8 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUCAACGUCAGUAGGACAAU |
| False | 3utr:515 | 1464 | medio | 1.84 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGCUUUCAACGUCAGUAGGAC |
| False | 3utr:516 | 1465 | medio | 3.27 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGCUUUCAACGUCAGUAGGA |
| False | 3utr:517 | 1466 | medio | 4.33 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUGCUUUCAACGUCAGUAGG |
| False | 3utr:518 | 1467 | medio | 1.27 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUUUGCUUUCAACGUCAGUAG |
| False | 3utr:521 | 1470 | medio | 2.2 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGGUUUGCUUUCAACGUCAG |
| False | 3utr:522 | 1471 | medio | 3.96 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAGGUUUGCUUUCAACGUCA |
| False | 3utr:523 | 1472 | medio | 2.46 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAAAGGUUUGCUUUCAACGUC |
| False | 3utr:524 | 1473 | medio | 1.16 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UACAAAGGUUUGCUUUCAACGU |
| False | 3utr:525 | 1474 | medio | 1.03 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAACAAAGGUUUGCUUUCAACG |
| False | 3utr:526 | 1475 | medio | 0.79 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAACAAAGGUUUGCUUUCAAC |
| False | 3utr:529 | 1478 | medio | 1.3 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUGAACAAAGGUUUGCUUUC |
| False | 3utr:543 | 1492 | medio | 1.06 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUAGUGCCCUGGGAAUGAAC |
| False | 3utr:544 | 1493 | medio | 0.73 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUCUAGUGCCCUGGGAAUGAA |
| False | 3utr:545 | 1494 | medio | 2.2 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUCUAGUGCCCUGGGAAUGA |
| False | 3utr:548 | 1497 | medio | 1.76 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUCAUUCUAGUGCCCUGGGAA |
| False | 3utr:549 | 1498 | medio | 3.76 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAUCAUUCUAGUGCCCUGGGA |
| False | 3utr:550 | 1499 | medio | 3.32 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAUCAUUCUAGUGCCCUGGG |
| False | 3utr:551 | 1500 | medio | 3.56 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGAUCAUUCUAGUGCCCUGG |
| False | 3utr:552 | 1501 | medio | 5.16 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAGAUCAUUCUAGUGCCCUG |
| False | 3utr:554 | 1503 | medio | 5.08 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUAAAGAUCAUUCUAGUGCCC |
| False | 3utr:555 | 1504 | medio | 1.63 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGCUAAAGAUCAUUCUAGUGCC |
| False | 3utr:558 | 1507 | medio | 0.86 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGGCUAAAGAUCAUUCUAGU |
| False | 3utr:559 | 1508 | medio | 1.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAAGGCUAAAGAUCAUUCUAG |
| False | 3utr:566 | 1515 | medio | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUCCAAGCAAGGCUAAAGAUC |
| False | 3utr:567 | 1516 | medio | 2.17 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUCCAAGCAAGGCUAAAGAU |
| False | 3utr:572 | 1521 | medio | 1.63 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGUUCAAUCCAAGCAAGGCUA |
| False | 3utr:573 | 1522 | medio | 4.42 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGUUCAAUCCAAGCAAGGCU |
| False | 3utr:574 | 1523 | medio | 3.45 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUAGUUCAAUCCAAGCAAGGC |
| False | 3utr:578 | 1527 | medio | 2.25 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUCCUAGUUCAAUCCAAGCA |
| False | 3utr:579 | 1528 | medio | 1.65 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUCUCCUAGUUCAAUCCAAGC |
| False | 3utr:581 | 1530 | medio | 0.99 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAUCUCCUAGUUCAAUCCAA |
| False | 3utr:582 | 1531 | medio | 2.93 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGAUCUCCUAGUUCAAUCCA |
| False | 3utr:583 | 1532 | medio | 1.77 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAAGAUCUCCUAGUUCAAUCC |
| False | 3utr:588 | 1537 | medio | 0.66 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAGUCAAGAUCUCCUAGUUC |
| False | 3utr:593 | 1542 | medio | 0.7 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCCUCAGAGUCAAGAUCUCCU |
| False | 3utr:594 | 1543 | medio | 1.36 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUCCUCAGAGUCAAGAUCUCC |
| False | 3utr:595 | 1544 | medio | 1.87 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUCCUCAGAGUCAAGAUCUC |
| False | 3utr:650 | 1599 | medio | 4.04 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUACCUUAACCAUCCCUCCC |
| False | 3utr:651 | 1600 | medio | 4.17 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGUACCUUAACCAUCCCUCC |
| False | 3utr:653 | 1602 | medio | 3.69 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUUUGUACCUUAACCAUCCCU |
| False | 3utr:654 | 1603 | medio | 1.63 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCCUUUGUACCUUAACCAUCCC |
| False | 3utr:657 | 1606 | medio | 2.13 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGCCUUUGUACCUUAACCAU |
| False | 3utr:658 | 1607 | medio | 1.85 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUAGCCUUUGUACCUUAACCA |
| False | 3utr:659 | 1608 | medio | 1.52 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUAGCCUUUGUACCUUAACC |
| False | 3utr:663 | 1612 | medio | 1.07 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGUUUCUAGCCUUUGUACCUU |
| False | 3utr:664 | 1613 | medio | 2.79 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGUUUCUAGCCUUUGUACCU |
| False | 3utr:665 | 1614 | medio | 1.89 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAAGUUUCUAGCCUUUGUACC |
| False | 3utr:666 | 1615 | medio | 1.32 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCAAGUUUCUAGCCUUUGUAC |
| False | 3utr:670 | 1619 | medio | 1.2 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAACUCAAGUUUCUAGCCUUU |
| False | 3utr:671 | 1620 | medio | 1.33 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAACUCAAGUUUCUAGCCUU |
| False | 3utr:672 | 1621 | medio | 3.45 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAACUCAAGUUUCUAGCCU |
| False | 3utr:673 | 1622 | medio | 4.42 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGAAACUCAAGUUUCUAGCC |
| False | 3utr:674 | 1623 | medio | 1.89 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAGAAACUCAAGUUUCUAGC |
| False | 3utr:675 | 1624 | medio | 1.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGAAGAAACUCAAGUUUCUAG |
| False | 3utr:678 | 1627 | medio | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAAUGAAGAAACUCAAGUUUC |
| False | 3utr:684 | 1633 | medio | 1.23 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGACAGAAAUGAAGAAACUCA |
| False | 3utr:689 | 1638 | medio | 0.94 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGUGAGACAGAAAUGAAGAA |
| False | 3utr:690 | 1639 | medio | 2.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUGUGAGACAGAAAUGAAGA |
| False | 3utr:691 | 1640 | medio | 2.9 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUUGUGAGACAGAAAUGAAG |
| False | 3utr:693 | 1642 | medio | 1.8 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUAAUUGUGAGACAGAAAUGA |
| False | 3utr:720 | 1669 | medio | 1.6 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGGGCAGAAGCUAAUUCUAG |
| False | 3utr:721 | 1670 | medio | 2.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUAGGGCAGAAGCUAAUUCUA |
| False | 3utr:727 | 1676 | medio | 1.52 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAACAUAGGGCAGAAGCUA |
| False | 3utr:728 | 1677 | medio | 0.59 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAGAAACAUAGGGCAGAAGCU |
| False | 3utr:729 | 1678 | medio | 1.2 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UACAGAAACAUAGGGCAGAAGC |
| False | 3utr:730 | 1679 | medio | 1.31 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUACAGAAACAUAGGGCAGAAG |
| False | 3utr:732 | 1681 | medio | 1.34 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGUACAGAAACAUAGGGCAGA |
| False | 3utr:733 | 1682 | medio | 3.72 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGUACAGAAACAUAGGGCAG |
| False | 3utr:734 | 1683 | medio | 3.85 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAGUACAGAAACAUAGGGCA |
| False | 3utr:736 | 1685 | medio | 4.26 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGAAGUACAGAAACAUAGGG |
| False | 3utr:737 | 1686 | medio | 3.36 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUAGAAGUACAGAAACAUAGG |
| False | 3utr:748 | 1697 | medio | 1.48 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUCCAGUUCAAAUAGAAGUAC |
| False | 3utr:750 | 1699 | medio | 2.06 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUAUCCAGUUCAAAUAGAAGU |
| False | 3utr:751 | 1700 | medio | 0.98 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUUAUCCAGUUCAAAUAGAAG |
| False | 3utr:760 | 1709 | medio | 1.14 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGUCUCUCUGUUAUCCAGUUC |
| False | 3utr:761 | 1710 | medio | 0.83 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGUCUCUCUGUUAUCCAGUU |
| False | 3utr:762 | 1711 | medio | 3.52 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUGUCUCUCUGUUAUCCAGU |
| False | 3utr:763 | 1712 | medio | 2.79 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAUUGUCUCUCUGUUAUCCAG |
| False | 3utr:764 | 1713 | medio | 1.96 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAUUGUCUCUCUGUUAUCCA |
| False | 3utr:765 | 1714 | medio | 2.37 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGAUUGUCUCUCUGUUAUCC |
| False | 3utr:766 | 1715 | medio | 2.04 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUAGAUUGUCUCUCUGUUAUC |
| False | 3utr:767 | 1716 | medio | 0.57 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUAGAUUGUCUCUCUGUUAU |
| False | 3utr:770 | 1719 | medio | 1.89 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUGUUUAGAUUGUCUCUCUGU |
| False | 3utr:771 | 1720 | medio | 3.63 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUGUUUAGAUUGUCUCUCUG |
| False | 3utr:772 | 1721 | medio | 1.57 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAUGUUUAGAUUGUCUCUCU |
| False | 3utr:773 | 1722 | medio | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAUGUUUAGAUUGUCUCUC |
| False | 3utr:775 | 1724 | medio | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAGAAUGUUUAGAUUGUCUC |
| False | 3utr:777 | 1726 | medio | 3.96 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAAGAGAAUGUUUAGAUUGUC |
| False | 3utr:788 | 1737 | medio | 1.23 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAUCUGCAGCCUAAGAGAAUG |
| False | 3utr:789 | 1738 | medio | 1.64 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUAUCUGCAGCCUAAGAGAAU |
| False | 3utr:791 | 1740 | medio | 1.87 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUUAUCUGCAGCCUAAGAGA |
| False | 3utr:796 | 1745 | medio | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UACUUCUCUUAUCUGCAGCCUA |
| False | 3utr:797 | 1746 | medio | 4.26 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUACUUCUCUUAUCUGCAGCCU |
| False | 3utr:798 | 1747 | medio | 3.45 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUACUUCUCUUAUCUGCAGCC |
| False | 3utr:799 | 1748 | medio | 0.82 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCCUACUUCUCUUAUCUGCAGC |
| False | 3utr:802 | 1751 | medio | 1.52 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAGCCUACUUCUCUUAUCUGC |
| False | 3utr:810 | 1759 | medio | 2.81 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGGAAUGGAGCCUACUUCUC |
| False | 3utr:811 | 1760 | medio | 2.57 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUGGAAUGGAGCCUACUUCU |
| False | 3utr:812 | 1761 | medio | 0.9 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUUUGGAAUGGAGCCUACUUC |
| False | 3utr:817 | 1766 | medio | 2.22 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCCCACUUUGGAAUGGAGCCU |
| False | 3utr:818 | 1767 | medio | 4.55 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUCCCACUUUGGAAUGGAGCC |
| False | 3utr:820 | 1769 | distal | 3.23 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUUUCCCACUUUGGAAUGGAG |
| False | 3utr:821 | 1770 | distal | 2.36 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUUUCCCACUUUGGAAUGGA |
| False | 3utr:822 | 1771 | distal | 2.26 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUCUUUCCCACUUUGGAAUGG |
| False | 3utr:823 | 1772 | distal | 1.8 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUCUUUCCCACUUUGGAAUG |
| False | 3utr:824 | 1773 | distal | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUUCUUUCCCACUUUGGAAU |
| False | 3utr:825 | 1774 | distal | 3.63 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUUUCUUUCCCACUUUGGAA |
| False | 3utr:826 | 1775 | distal | 2.33 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAUUUCUUUCCCACUUUGGA |
| False | 3utr:827 | 1776 | distal | 0.99 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAAUUUCUUUCCCACUUUGG |
| False | 3utr:831 | 1780 | distal | 2.09 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGCAGAAUUUCUUUCCCACU |
| False | 3utr:832 | 1781 | distal | 2.75 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUAGCAGAAUUUCUUUCCCAC |
| False | 3utr:833 | 1782 | distal | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGCUAGCAGAAUUUCUUUCCCA |
| False | 3utr:834 | 1783 | distal | 2.41 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGCUAGCAGAAUUUCUUUCCC |
| False | 3utr:835 | 1784 | distal | 2.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUGCUAGCAGAAUUUCUUUCC |
| False | 3utr:836 | 1785 | distal | 1.3 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUGCUAGCAGAAUUUCUUUC |
| False | 3utr:840 | 1789 | distal | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAACAAUGCUAGCAGAAUUUC |
| False | 3utr:844 | 1793 | distal | 2.0 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUUAAACAAUGCUAGCAGAA |
| False | 3utr:845 | 1794 | distal | 1.43 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAUUUAAACAAUGCUAGCAGA |
| False | 3utr:846 | 1795 | distal | 3.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUGAUUUAAACAAUGCUAGCAG |
| False | 3utr:847 | 1796 | distal | 0.62 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUGAUUUAAACAAUGCUAGCA |
| False | 3utr:851 | 1800 | distal | 3.19 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGCCUGAUUUAAACAAUGCU |
| False | 3utr:898 | 1847 | distal | 2.99 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCGCAGUUUAUGUCUGCUGGG |
| False | 3utr:899 | 1848 | distal | 3.12 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUCGCAGUUUAUGUCUGCUGG |
| False | 3utr:900 | 1849 | distal | 5.15 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAUCGCAGUUUAUGUCUGCUG |
| False | 3utr:901 | 1850 | distal | 1.85 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUAUCGCAGUUUAUGUCUGCU |
| False | 3utr:902 | 1851 | distal | 0.9 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGCUAUCGCAGUUUAUGUCUGC |
| False | 3utr:904 | 1853 | distal | 2.33 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGCUAUCGCAGUUUAUGUCU |
| False | 3utr:905 | 1854 | distal | 1.76 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGAAGCUAUCGCAGUUUAUGUC |
| False | 3utr:914 | 1863 | distal | 1.43 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUGCAAGCUGAAGCUAUCGCA |
| False | 3utr:920 | 1869 | distal | 0.59 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCCACAGUGCAAGCUGAAGCU |
| False | 3utr:921 | 1870 | distal | 1.65 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUCCACAGUGCAAGCUGAAGC |
| False | 3utr:922 | 1871 | distal | 2.9 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAUCCACAGUGCAAGCUGAAG |
| False | 3utr:1017 | 1966 | distal | 4.45 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAGUACUGGAUGGAACGGCCA |
| False | 3utr:1019 | 1968 | distal | 7.15 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUAGUACUGGAUGGAACGGC |
| False | 3utr:1020 | 1969 | distal | 4.95 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUUUAGUACUGGAUGGAACGG |
| False | 3utr:1024 | 1973 | distal | 2.93 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGCAUUUAGUACUGGAUGGA |
| False | 3utr:1025 | 1974 | distal | 3.73 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUAAGCAUUUAGUACUGGAUGG |
| False | 3utr:1026 | 1975 | distal | 0.78 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUAAGCAUUUAGUACUGGAUG |
| False | 3utr:1029 | 1978 | distal | 1.97 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UACGGUAAGCAUUUAGUACUGG |
| False | 3utr:1070 | 2019 | distal | 3.44 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUCCUACGGAACUGAGUGCAC |
| False | 3utr:1075 | 2024 | distal | 2.57 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUGGAAUCCUACGGAACUGAG |
| False | 3utr:1076 | 2025 | distal | 4.2 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUUUGGAAUCCUACGGAACUGA |
| False | 3utr:1077 | 2026 | distal | 1.52 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCUUUGGAAUCCUACGGAACUG |
| False | 3utr:1081 | 2030 | distal | 3.06 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUCUGCUUUGGAAUCCUACGGA |
| False | 3utr:1103 | 2052 | distal | 3.29 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGAUUCAAAGACCAGCUAGGG |
| False | 3utr:1107 | 2056 | distal | 2.59 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAUGCAGAUUCAAAGACCAGCU |
| False | 3utr:1108 | 2057 | distal | 2.95 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UCAUGCAGAUUCAAAGACCAGC |
| False | 3utr:1109 | 2058 | distal | 2.67 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UACAUGCAGAUUCAAAGACCAG |
| False | 3utr:1110 | 2059 | distal | 2.66 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UUACAUGCAGAUUCAAAGACCA |
| False | 3utr:1111 | 2060 | distal | 3.07 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UGUACAUGCAGAUUCAAAGACC |
| False | 3utr:1112 | 2061 | distal | 1.47 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAGUACAUGCAGAUUCAAAGAC |
| False | 3utr:1113 | 2062 | distal | 0.57 |  | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | INCOMPLETE | UAAGUACAUGCAGAUUCAAAGA |

## 8. Controles del experimento

Un control sin veredictos no es un control, es una secuencia. Los dos que diseña la app pasan por los mismos filtros que un candidato y salen INCOMPLETE mientras les quede un frente sin correr.

SCRAMBLED Y SEED-MISMATCH NO SON INTERCAMBIABLES, y quedarse con uno deja viva una explicación alternativa. El scrambled controla «tener un shmiR» —saturación de la maquinaria, respuesta a ARN de doble cadena, carga viral— con una guía que no se parece a la nuestra. El seed-mismatch controla «tener ESTA guía»: misma composición, misma estructura, mismo sitio del andamio y la seed rota, así que lo único que cambia es el reconocimiento de la diana.

| brazo | qué aísla |
|---|---|
| vehículo | el procedimiento: inyección, cirugía y formulación, sin vector. Es la línea de base contra la que se lee todo lo demás. |
| shmiR scrambled | tener UN shmiR: saturación de la maquinaria de miARN, respuesta a ARN de doble cadena y carga viral, con una guía sin diana. Lo que quede de efecto aquí no es del silenciamiento. |
| shmiR con la seed rota | tener ESTA guía: misma composición, misma estructura y mismo sitio, con el reconocimiento de la diana roto. Lo que quede de efecto aquí es off-target de esta secuencia, no del knockdown. |
| sólo shmiR | la contribución del knockdown sin la proteína dominante negativa. |
| sólo DN | la contribución de la dominante negativa sin knockdown. Es además el techo de expresión con el que se lee la construcción completa. |
| construcción completa | el efecto terapéutico que se quiere demostrar. Sin los otros cinco no se puede atribuir a nada en concreto. |

PASAR EL FILTRO DE ASIMETRÍA NO ES SER EQUIVALENTE. El umbral del pipeline dice si una hebra se carga; un control necesita además cargarse IGUAL que la guía que controla, y eso es una distancia, no un mínimo. Medido sobre `3utr:1018`: la mediana de las permutaciones es 0,67 frente a 7,65 del original, así que casi todas pasan el filtro y ninguna sería comparable.

EL PLEGADO DEL 97-MERO NO DISCRIMINA, y por eso un PASS aquí no es evidencia de que el control se procese como el original. `passenger_from_guide` ELIGE la base de la posición 1 de la pasajera para que el 97-mero reproduzca la estructura de SGEP, y ABORTA si ninguna de las cuatro lo consigue: la comprobación posterior vuelve a preguntar algo que ya era condición para haber montado la horquilla. Medido el 2026-08-31: 0 de 2000 permutaciones y 0 de 1134 variantes de seed dan una notación distinta, y tampoco la da una guía derivada del propio andamio para que compita con el loop. Lo que SÍ discrimina es la ASIMETRÍA —falla el 47 % de las permutaciones—, que además es la propiedad que decide qué hebra carga AGO2: un tallo más débil se procesa peor y entonces la comparación no mide la diana, mide el procesamiento.

2 o 3 cambios en la seed, medido sobre la guía de 3utr:959 —el primero del panel—. La «racha intacta» es el tramo contiguo de seed que queda sin tocar, y es lo que mide el residuo de reconocimiento: importa más DÓNDE caen los cambios que cuántos son.

| cambios | variantes | limpias | racha mínima | con esa racha | chocan con el núcleo |
|---|---|---|---|---|---|
| 2 | 189 | 112 | 2 | 14 | no comprobado |
| 3 | 945 | 453 | 1 | 12 | no comprobado |

2 o 3 CAMBIOS: no se elige aquí. Se emiten las dos versiones con sus métricas y lo decide quien lee, con la tabla delante. Lo que la medida añade a la intuición es que el número de cambios importa MENOS que dónde caen: lo que deja residuo de reconocimiento es la RACHA de seed que queda intacta, no cuántas bases se tocaron.

## 9. Arquitecturas de intrón

Los diez candidatos del panel se han consultado con LAS DOS arquitecturas de intrón —20 construcciones— y estos son los ejes en los que se diferencian. Las puntuaciones salen de la corrida de SpliceAI del 2026-09-05, guardada con su procedencia; la geometria la deriva esta app.

| eje | mvm_actual | intron_quimerico | gana |
|---|---|---|---|
| dispersión del donante legítimo entre las 10 guías | 18,1 % (0,783-0,925) | 1,8 % (0,956-0,973) | quimérico |
| dispersión del aceptor legítimo | 10,3 % (0,778-0,858) | 0,9 % (0,985-0,994) | quimérico |
| crípticos intrónicos por encima del 5 % del legítimo | 2 (11,9 % y 6,1 %, en 1 de 10) | ninguno | quimérico |
| tracto de polipirimidinas | 9 pirimidinas | 11 pirimidinas | quimérico |
| donante→punto de ramificación, MONTADO | 256 nt | 249-253 nt | ninguno: no discrimina |

Retirado por Joaquín Castilla (2026-09-05), que fue quien lo propuso. Se dio como contrapeso del quimérico que su donante→punto de ramificación es de 314-318 nt frente a los 256 del MVM, y con sus palabras: «apliqué al quimérico los 214 nt del MVM sin comprobar que el quimérico se monta sin espaciadores. La diferencia era exactamente 65 = 20 + 45 — la errata nº 35, cometida por mí esta vez». Medido sobre el intrón que de verdad se monta, el quimérico está en 249-253 nt: no es peor en geometría, empata y queda marginalmente por debajo. CONSECUENCIA, y va escrita porque decide qué se sintetiza: el quimérico GANA EN TODO LO MEDIDO, SIN CONTRAPESO CONOCIDO. Lo que sí se sostiene del contrapeso es que LOS DOS quedan muy por encima del rango típico de mamífero, y eso no lo arregla cambiar de intrón.

En el intrón VACÍO el quimérico tiene el punto de ramificación mucho más lejos del donante (100-104 nt frente a 42), pero MONTADOS empatan: el MVM lleva además los dos espaciadores, así que intercala 214 nt frente a 149 y acaba en 256 nt frente a los 249-253 del quimérico. Los dos quedan fuera del rango típico de mamífero y la diferencia entre ellos es de unos pocos nucleótidos, así que ESTE EJE NO DISCRIMINA — era el único contrapeso que se le conocía al quimérico y queda retirado. Lo que sí separa a los dos es lo demás —el quimérico tiene mejor donante, mejor tracto y 97 posiciones de inserción frente a 39—, y ninguno de esos números predice el empalme. Las opciones van a síntesis; el gel decide.

## 10. Fichas de los seleccionados

Una ficha por candidato seleccionado, con el veredicto de CADA frente, su procedencia y su fecha.

### 3utr:1149

```
═══ Ficha del candidato — mouse tx:1149 ═══

  sitio      tx:1149-1170
  guía       TTTAGCACTGGCTGATGACAGA
  pasajera   CCTGTCATCAGCCAGTGCTAAA
  veredicto  INCOMPLETE

── Frentes (14) ──
  frente                          estado    fecha        procedencia
  empalme_intron                  NOT_RUN   —            frente abierto del informe
  empalme_sitios:intron_quimerico NOT_RUN   —            sin corrida en el almacen
  empalme_sitios:mvm_actual       NOT_RUN   —            sin corrida en el almacen
  empalme_sitios:mvm_sin_criptico NOT_RUN   —            sin corrida en el almacen
  especificidad                   NOT_RUN   —            sin corrida en el almacen
  fraccion_isoforma_larga         PASS      —            frente CERRADO del informe
  offtarget_seed:guia             NOT_RUN   —            sin corrida en el almacen
  offtarget_seed:pasajera         NOT_RUN   —            sin corrida en el almacen
  repeticion_polimorfica          NOT_RUN   —            frente abierto del informe
  repeticiones                    NOT_RUN   —            frente abierto del informe
  seed                            NOT_RUN   —            frente abierto del informe
  seed_colision:guia              NOT_RUN   —            sin corrida en el almacen
  seed_colision:pasajera          NOT_RUN   —            sin corrida en el almacen
  transgen                        NOT_RUN   —            frente abierto del informe

── Asimetría — las TRES cifras, que son magnitudes distintas ──
  cruda +3.80   penalizacion 0.00   neta +3.80

── Techo de APA ──
  sin techo — tx:1-1200  sin techo            por delante de todos los cortes medidos: la diana está en TODAS las isoformas. INMUNE.

── Sitios de esta seed en la PROPIA diana (esperado: 1) ──
  tx:1164 7mer-m8 (el suyo)

── Multiplexado: núcleo de seed compartido ──
  Con ningún otro candidato del panel. En este eje es independiente.

── Hexámeros cercanos ──
  AATATA  tx:1185  APA_POSIBLE/medida a 15 nt por delante

── Bloques ──
  módulo NheI-SacI (149 nt):
    GCTAGCGAAGGCTCGAGAAGGTATATTGCTGTTGACAGTGAGCGCCTGTCATCAGCCAGT
    GCTAAATAGTGAAGCCACAGATGTATTTAGCACTGGCTGATGACAGATGCCTACTGCCTC
    GGACTTCAAGGGGCTAGAATTCGGAGCTC
  cassette MluI-AgeI (318 pb):
    ACGCGTAAGAGGTAAGGGTTTAAGGGATGGTTGGTTGGTGGGGTATTAATGTACAATGAT
    CCAAATCAAGAGCTAGCGAAGGCTCGAGAAGGTATATTGCTGTTGACAGTGAGCGCCTGT
    CATCAGCCAGTGCTAAATAGTGAAGCCACAGATGTATTTAGCACTGGCTGATGACAGATG
    CCTACTGCCTCGGACTTCAAGGGGCTAGAATTCGGAGCTCATGGATTTGTGTAAAGATCC
    AGTGCCTATGTATTGTTGGAAAGTATTTAATTACCTGGAGCACCTGCCTGAAATCACTTT
    TTTTCAGGTTGGACCGGT
  ⚠  No está el plásmido SGEP depositado, así que los contextos del módulo (5' GAAGGCTCGAGAAGGTATAT en 1739-1758, 3' CTTCAAGGGGCTAGAATTCG en 1856-1875) NO se han contrastado con el vector real. NO pidas el gBlock con esto sin resolver.

── Historial de BLAST ──
  SIN CORRIDAS. El frente de especificidad sigue en NOT_RUN, y NOT_RUN no es PASS.
```

## 11. Limitaciones

Seccion propia y no un pie: una limitacion al pie se lee después de haber creido el número.

### Umbrales SIN base medida

Estos no salen de ninguna medida. Se declaran como convenio o como decisión de este proyecto, y presentarlos junto a los que si tienen base sin distinguirlos les atribuiria una precisión que no tienen.

| umbral | valor | por que no tiene base medida |
|---|---|---|
| homopolimero máximo | 4 nt | el corte en 4 es un redondeo operativo, no un punto medido: 5 no es cualitativamente distinto de 4 |
| asimetría mínima (proxy) | +1,0 kcal/mol | el proxy no está calibrado contra energias medidas, así que el número ordena candidatos entre si pero no es una magnitud fisica |
| flanco prohibido alrededor del hexámero (eje esterico) | ±10 nt | NO TIENE BASE MEDIDA, y es el caso que obliga a distinguir origenes. La huella real de CPSF/CstF sobre el pre-mRNA es MAYOR que 10 nt, así que una ventana que el filtro deja pasar por 4 nt está probablemente dentro de la zona de competencia. El eje esterico es un GRADIENTE, no una frontera: cualquier umbral en nucleótidos le atribuye una precisión que la biologia no tiene. Por eso el informe emite además la SENSIBILIDAD al flanco |
| longitud de los espaciadores del intrón (5' y 3') | 20 nt en 5' y 45 nt en 3' | NO HAY NÚMERO QUE JUSTIFICAR, y no por no haberlo buscado: el barrido se hizo (`tools/barrer_espaciadores.py`, 0-45 nt en los dos lados, 5 réplicas por longitud) y en LOS DOS LADOS el único largo admisible es el punto de partida — ninguna longitud más corta queda no peor en los tres elementos frágiles. Lo que el barrido NO da es un número que justifique 20 y 45 en vez de otros: en el lado 5' el criterio ni siquiera discrimina (recorrido entre longitudes por debajo de la dispersión entre secuencias de la misma longitud, en los tres elementos), y en el 3' discrimina por un margen del 7-11 %, que no sostiene una optimización fina. Optimizar por un criterio que apenas distingue es elegir ruido, y elegir el ruido favorable es peor que no elegir. Misma categoría que el flanco de ±10 nt: nuestro, sin base medida |
| espaciado mínimo entre candidatos elegidos | 50 nt | 50 nt no sale de ninguna medida de correlación espacial de fallos: sale de que sea claramente mayor que una ventana de 22 nt y de que deje sitio para el panel |
| criterio de Kozak fuerte | purina en -3 y G en +4 | no se pondera la fuerza del contexto ni se usa ninguna matriz: es un corte binario sobre dos posiciones |

### La carga de off-targets es un LÍMITE SUPERIOR

| limitacion | direccion | detalle |
|---|---|---|
| Sin ponderación por conservación | sobrestima | No tenemos alineamientos multiespecie; TargetScan si. Nuestro número cuenta SITIOS, no sitios probablemente funcionales: un sitio que no está conservado en ninguna otra especie pesa aquí lo mismo que uno conservado en todas. Sobrestima. |
| Sin ponderación por APA | sobrestima | Un sitio en la parte DISTAL de un 3'UTR con poliadenilación alternativa no está en todos los mensajeros de ese gen: la isoforma corta no lo lleva. Lo sabemos por Prnp, donde la fracción de isoforma larga está medida en 0,86, y aplica a los demas genes igual — solo que ahi no lo hemos medido. Sobrestima. |
| Sin ponderación por expresión | sobrestima | Un sitio en un gen que la neurona no expresa no cuenta como off-target. Si algun día hay `expresion_cerebro.tsv` con su referencia y su umbral, esto se refina; hoy no lo hay y todos los genes del fichero pesan igual. Sobrestima. |

> **LAS TRES LIMITACIONES EMPUJAN EN LA MISMA DIRECCIÓN, así que el número es un LÍMITE SUPERIOR: cuenta SITIOS, no sitios probablemente funcionales. No se compensa con un factor ni se corrige a ojo — se dice.**

### La especificidad no cubre los off-targets por seed

EL OFF-TARGET MEDIADO POR SEED NO SE BUSCA CON BLAST, y no es una preferencia: 7 nt contiguos NO DAN UN ALINEAMIENTO PUNTUABLE, así que un blastn no los devuelve por mucho que se le baje el word_size. Esto es coincidencia EXACTA del heptamero 2-8 sobre los 3'UTR del transcriptoma murino — busqueda de SUBCADENA, no alineamiento— y necesita `transcriptoma_3utr.fa`. Fundirlo con la especificidad en un solo «PASS» daria por cubierto EL MODO DE OFF-TARGET MÁS FRECUENTE DE RNAi con una herramienta que no lo detecta. Por eso son DOS frentes y se cuentan aparte.

### La accesibilidad es DESEMPATE, nunca filtro

Es el criterio peor predicho del pipeline. Se calculan dos ventanas de contexto (±80 y ±150) y si discrepan, el número no sirve ni para desempatar.

### La asimetría usa un PROXY, no una energía libre de duplex

Ordena candidatos entre si; no es una magnitud fisica y no se debe leer como tal. Su especificación tuvo un error de signo que ningún test de consistencia interna habría detectado, así que hay dos tests de cordura biologica que fijan los signos.

### Un frente que no se cierra con ningún fichero

El empalme del intrón es BINARIO y solo se contesta en el banco. Y la lectura que se hace por defecto NO lo coge: un small RNA-seq puede salir perfecto con el empalme fallando, porque Drosha procesa el pri-miR cotranscripcionalmente — o sea ANTES del splicing. Un shmiR correcto no es evidencia de que haya proteina.

### Las herramientas externas: por qué NO son la fuente principal

ESTAS HERRAMIENTAS SE CONOCÍAN Y SE DECIDIÓ NO USARLAS COMO FUENTE PRINCIPAL, sino como CONTRASTE independiente. Dos motivos, y ninguno es que sean malas: (a) devuelven una lista de candidatos y NO DECLARAN qué no han comprobado, así que un sitio que no sale no se distingue de uno que no miraron —que es la misma razón por la que aquí todo filtro emite `NOT_RUN` con su motivo—; y (b) ninguna considera la POLIADENILACIÓN ALTERNATIVA, que en este 3'UTR condiciona a seis de los diez candidatos con un techo de knockdown. Lo que sí aportan es convergencia de sitio: que otro método señale la misma región es información, y por eso están en la lista en vez de fuera de ella.

| herramienta | longitud de guía | alimenta score_externo |
|---|---|---|
| miRarchitect | 22 nt | sí |
| SplashRNA | 22 nt | no |
| GPP Web Portal | SIN DECLARAR | no |
| siDirect | 19 nt | sí |
| BLOCK-iT RNAi Designer | SIN DECLARAR | sí |

La longitud NO es un detalle de ficha: es lo que decide cómo se cruza su salida con la nuestra. siDirect diseña 19-mers y nuestras ventanas miden 22, así que sus candidatos son OTRAS ventanas sobre el mismo sitio — se cruzan por solapamiento sobre la referencia, y el importador ABORTA si le llegan longitudes distintas de las declaradas, en vez de cruzar cero y dejar que eso se lea como «no hay convergencia».

## 12. Procedencia

Todos los ficheros que entraron, con versión y md5. Sin esto un veredicto no es auditable dentro de un año — que es la razón por la que el manifiesto se versiona en texto.

| recurso | procedencia |
|---|---|
| máscara de repetitivos | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| maduros de miRBase | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| tabla de seeds | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| base de especificidad | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| casete del transgén | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| 3'UTR del transcriptoma | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| APA medido | MAPEO GENOMICO↔TRANSCRITO — RESUELTO SIN COORDENADAS GENOMICAS. ·   PolyA_DB pública el sitio de CORTE, NO EL HEXÁMERO. Su leyenda: «A[A/U]UAAA motif within 40-nt upstream from the PAS» — el hexámero se busca AGUAS ARRIBA del PAS, luego la coordenada publicada es el corte. Con nuestra convención el hexámero cae 10-30 nt por delante, dentro de esos 40 nt. ·   Hipotesis «PAS = hexámero»: DESCARTADA. Un hexámero es un punto, no una banda, así que ·   bajo esa lectura el aterrizaje tiene que ser EXACTO — y no hay ningún desfase que haga ·   aterrizar más de 1 de las 4 coordenadas. Bajo «PAS = corte» aterrizan las 4, ·   con el MISMO desfase y con la CLASE de hexámero que declara la propia base en cada una. ·   No es una resta: son 4 puntos de apoyo independientes. Desfase 3'UTR→mm10 acotado a 131937185-131937193 (9 valores); se deja como INTERVALO ·   porque la banda de corte mide 20 nt y fijarlo en un entero sería inventarse precisión. ·  ·     chr2:+:131937444  Other   → corte 3utr:251-271, hexámero AATATA en 3utr:236  PSE 21.1%, AvgRPM 0.55  ← TERCER sitio de corte, el proximal MÁS USADO de los tres ·     chr2:+:131937504  AAUAAA  → corte 3utr:303-323, hexámero AATAAA en 3utr:288  PSE 23.5%, AvgRPM 0.34  ← nuestro AATAAA de 3utr:288 ·     chr2:+:131938392  Other   → AMBIGUO: 2 hexámeros de su clase en la banda (TATAAA en 3utr:1178, TATAAA en 3utr:1189). Ancla, pero NO entra al modelo con banda propia. ·     chr2:+:131938427  AUUAAA  → corte 3utr:1229-1249, hexámero ATTAAA en 3utr:1214  (sin datos de expresión)  ← fuerza 99,9 %, conservado en humano y rata; SIN expresión, así que no entra en la fracción — solo ancla ·  ·   TECHO POR TRAMOS. Con tres sitios de corte medidos el techo ya no es UNO: la pregunta ·   de un candidato no es cuanta isoforma larga hay, es que fracción de transcritos conserva ·   SU diana — y eso depende de por detrás de cuántos cortes esta. ·     tx:1-1200  sin techo            por delante de todos los cortes medidos: la diana está en TODAS las isoformas. INMUNE. ·     tx:1201-1220  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937444: no se sabe de que lado cae, así que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     tx:1221-1252  techo 0.91           por detrás de chr2:+:131937444 ·     tx:1253-1272  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937504: no se sabe de que lado cae, así que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     tx:1273-2191  techo 0.86           por detrás de chr2:+:131937444, chr2:+:131937504 |
| lista ampliada de abundancia | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
