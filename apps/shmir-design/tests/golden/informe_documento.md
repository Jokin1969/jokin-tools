# Diseño de shmiR — mouse

**Estado del informe: PARCIAL** · generado 2026-08-26

ESTE INFORME ES PARCIAL. No es un borrador ni una version reducida: es el mismo documento con frentes todavia abiertos, y cada uno sale marcado con lo que le falta y donde conseguirlo. Un candidato con cualquier frente en NOT_RUN es INCOMPLETE, nunca aprobado — no haber comprobado algo no es haberlo comprobado y que salga bien.

Frentes abiertos: especificidad, repeticion_polimorfica, repeticiones, seed, seed_colision, transgen, offtarget_seed, empalme_intron.

COMO SE LEE ESTO. Cada filtro emite uno de cuatro estados: PASS (corrio y el candidato lo supera), FAIL (corrio y no lo supera), NOT_RUN (NO LLEGO A CORRER — es una laguna, no un aprobado) y NO_APLICA (esa pregunta no se le hace a ese candidato). Un numero comparativo que no se calculo va VACIO, nunca a cero: no haber contado y contar cero son cosas distintas.

## 1. Que se analizo

Longitud y md5 van JUNTOS a proposito: «referencia 1246 nt» parece razonable a solas, y pegado al md5 no hay forma de leerlo sin ver que lo que se llama referencia no es lo que se cree. Es la contramedida de una errata real.

| campo | valor |
|---|---|
| secuencia analizada | 1242 nt / 19f5fa2a77a87892770e2affdc90e0e4 |
| especie declarada | mouse |
| anatomia | lo tilado ES el 3'UTR (fixture verificado por md5) |
| ventanas tiladas | 1221 |
| tamaño de ventana | 22 nt |
| fecha del informe | 2026-08-26 |

## 2. Estado de los frentes

Un frente es una pregunta que hay que contestar antes de pedir oligo. Los cerrados NO desaparecen del informe: sin ellos, el siguiente lector no sabria si se resolvieron o si nadie los miro.

| frente | estado | que falta | donde se consigue |
|---|---|---|---|
| especificidad | NOT_RUN | refseq_rna (base de BLAST) + el resultado en `-outfmt 6` | La app prepara la consulta; el BLAST lo corres tu. La base es RefSeq RNA del NCBI. (https://ftp.ncbi.nlm.nih.gov/blast/db/) |
| repeticion_polimorfica | NOT_RUN | rmsk_mouse.out, rmsk_mouse.tbl | RepeatMasker Web Server (https://www.repeatmasker.org/) |
| repeticiones | NOT_RUN | rmsk_mouse.out, rmsk_mouse.tbl | RepeatMasker Web Server (https://www.repeatmasker.org/) |
| seed | NOT_RUN | mature.fa | miRBase (el mismo `mature.fa`), o una tabla propia `seed<TAB>familia` (https://www.mirbase.org/) |
| seed_colision | NOT_RUN | mature.fa | miRBase (https://www.mirbase.org/) |
| transgen | NOT_RUN | aav_casete.fa | El laboratorio: el fichero del plasmido del casete AAV (—) |
| offtarget_seed | NOT_RUN | transcriptoma_3utr_mouse.fa | UCSC Table Browser (https://genome.ucsc.edu/cgi-bin/hgTables) |
| empalme_intron | NOT_RUN | no se cierra con ningun fichero (banco) | Banco: RT-PCR, Western y secuenciacion. No hay descarga que valga. (—) |
| fraccion_isoforma_larga | CERRADO | — | — |

> **8 frente(s) en NOT_RUN. No se pide oligo hasta que todos tengan veredicto. Que uno se arregle con un fichero de kilobytes y otro necesite ir al banco no cambia nada: los dos bloquean igual.**

Y hay una categoria aparte: empalme_intron NO se cierra con ningun fichero. Conseguir mas datos no lo resuelve; hay que ir al laboratorio. Se dice aparte para que no parezca que basta con descargar algo.

## 3. Frente por frente

Por cada frente: que mide, por que importa, con que criterio se decide y de donde sale cada umbral, con que datos se ha contestado, y el resultado.

### Filtros biofisicos de ventana (no son un frente)

Los seis filtros biofisicos de ventana NO dependen de ningun fichero ni de ninguna especie: corren siempre. Por eso no son un «frente» — no hay nada que conseguir para cerrarlos. Sus umbrales si necesitan justificarse igual que los demas.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| GC minimo de la ventana | 0,30 | literatura | el rango de GC de las guias funcionales de RNAi es un resultado repetido en los trabajos de diseño de shRNA/siRNA: por debajo el duplex es demasiado inestable para cargar bien |
| GC maximo de la ventana | 0,55 | literatura | por encima el duplex es demasiado estable y la hebra no se separa; mismo cuerpo de trabajo que el minimo |
| homopolimero maximo | 4 nt | convencion | carreras mas largas dan problemas de sintesis y de secuenciacion, y en el casete son sustrato de deslizamiento de la polimerasa  ⚠ SIN BASE MEDIDA: el corte en 4 es un redondeo operativo, no un punto medido: 5 no es cualitativamente distinto de 4 |
| asimetria minima (proxy) | +1,0 kcal/mol | nuestro | la regla de asimetria termodinamica —el extremo 5' de la guia menos estable carga preferentemente— si viene de literatura; el UMBRAL en +1,0 sobre NUESTRO proxy es nuestro. Y el proxy NO es una energia libre de duplex: es una heuristica, con su aviso en `thermo.py`  ⚠ SIN BASE MEDIDA: el proxy no esta calibrado contra energias medidas, asi que el numero ordena candidatos entre si pero no es una magnitud fisica |

### especificidad — NOT_RUN

**Que mide.** ¿Esta guia tiene complementariedad EXTENSA con algun otro transcrito? Es la pregunta de los alineamientos, y la contesta un BLAST contra una base de transcritos.

**Por que importa / resultado.** NOT_RUN en 1221 de 1221 ventanas: falta el recurso. NOT_RUN no es PASS. Y OJO: este frente NO cubre los off-targets mediados por seed. Eso es `offtarget_seed`, un frente APARTE, porque 7 nt contiguos no dan alineamiento y ningun BLAST los devuelve.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

**Criterio.** Este frente no tiene umbral numerico: su veredicto es una comprobacion, no una comparacion contra un corte.

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «especificidad»

  QUE PREGUNTA RESPONDE: ¿Esta guia tiene complementariedad EXTENSA con algun otro transcrito? Es la pregunta de los alineamientos, y la contesta un BLAST contra una base de transcritos.

  FICHERO(S) QUE HACEN FALTA:
    · refseq_rna (base de BLAST) + el resultado en `-outfmt 6`  [OBLIGATORIO]
      La base es contra lo que se alinea; el `-outfmt 6` es lo que se sube. La app no necesita la base: necesita su nombre, su version y su md5 para poder decir contra que se comparo.

  FUENTE: La app prepara la consulta; el BLAST lo corres tu. La base es RefSeq RNA del NCBI.
  URL: https://ftp.ncbi.nlm.nih.gov/blast/db/

  PASOS:
    1. Abre el modal de especificidad en la app y marca los candidatos y las hebras que quieras consultar.
    2. Descarga el FASTA de consulta que genera la app. Lleva su md5: no lo edites.
    3. Copia el comando que la app deja listo. Ya trae los ajustes buenos para una consulta corta: `-task blastn-short`, `-word_size 7`, `-evalue 1000`, `-dust no`, `-outfmt 6`.
    4. Ejecutalo contra una base LOCAL: descarga `refseq_rna` del FTP de BLAST del NCBI y apunta su fecha y su md5. Solo una base local con md5 cierra el frente.
    5. Filtra por organismo con el taxid de la especie: txid10090
    6. Sube el `-outfmt 6` tal cual, sin recortarlo.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · nombre, version y md5 de la base
      Sin ellos el veredicto no es reproducible, y el almacen marca la corrida como «no reproducible» con esas palabras.
    · los ajustes que hayas cambiado
      Cualquier ajuste distinto del estandar viaja con el resultado y se marca en rojo: un veredicto obtenido con parametros no estandar no puede ser indistinguible de uno estandar.

  TAMAÑO APROXIMADO: el resultado (`-outfmt 6`) son unos KB; la base local de RefSeq RNA son varios GB

  COMO SE VALIDA AL SUBIRLO: Al subir el resultado la app comprueba DOS cosas y las dos rechazan: que el md5 del FASTA de consulta que declaras sea el del FASTA que ella genero, y que toda `query` del resultado este en el panel. Es el fallo del CSV de miRarchitect —un fichero de otra corrida que entra, cuadra de forma y produce un analisis entero sobre el dato equivocado— y el mensaje lo nombra. Un `-outfmt 6` VACIO tambien se rechaza: cero hits y «la corrida no llego a correr» son cosas distintas y ese fichero no las distingue.

  AVISOS:
    ⚠ ESTA APP NO LANZA EL BLAST Y NO PUEDE: el navegador no puede llamar a NCBI (CORS) y el backend no tiene red saliente. No es una limitacion escondida: es la arquitectura, y el modal lo dice.
    ⚠ `-remote` es EXPLORACION, NUNCA VEREDICTO. La base de NCBI cambia entre corridas, asi que un resultado remoto no es reproducible. Solo una base LOCAL con md5 cierra el frente.
    ⚠ ESTE FRENTE NO CUBRE LOS OFF-TARGETS POR SEED. Son dos frentes y el otro es `offtarget_seed`: 7 nt contiguos no dan un alineamiento puntuable, asi que ningun BLAST los devuelve. Un «especificidad: PASS» sin esa frase invita a creer que la guia esta comprobada cuando lo comprobado son los alineamientos.
```

### repeticion_polimorfica — NOT_RUN

**Que mide.** ¿La ventana cae dentro de una repeticion POLIMORFICA — un microsatelite, un satelite, un tramo de baja complejidad? Es otra pregunta que la de `repeticiones`, aunque salga del mismo fichero: aquella va de estabilidad del genoma AAV y esta de VIABILIDAD CLINICA. Un microsatelite varia en NUMERO DE REPETICIONES entre individuos, asi que una guia ahi tendria respondedores y no respondedores por variacion de LONGITUD, no de secuencia.

**Por que importa / resultado.** NOT_RUN en 1221 de 1221 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

**Criterio.** Este frente no tiene umbral numerico: su veredicto es una comprobacion, no una comparacion contra un corte.

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «repeticion_polimorfica»

  QUE PREGUNTA RESPONDE: ¿La ventana cae dentro de una repeticion POLIMORFICA — un microsatelite, un satelite, un tramo de baja complejidad? Es otra pregunta que la de `repeticiones`, aunque salga del mismo fichero: aquella va de estabilidad del genoma AAV y esta de VIABILIDAD CLINICA. Un microsatelite varia en NUMERO DE REPETICIONES entre individuos, asi que una guia ahi tendria respondedores y no respondedores por variacion de LONGITUD, no de secuencia.

  FICHERO(S) QUE HACEN FALTA:
    · rmsk_mouse.out  [OBLIGATORIO]
      Las filas con los intervalos enmascarados. Es lo que se aplica a la secuencia.
    · rmsk_mouse.tbl  [OBLIGATORIO]
      El resumen. Es el UNICO sitio donde se declara la especie de la biblioteca y la longitud de la consulta, asi que es lo unico que permite validar la corrida. Sin el, un `.out` sin filas no distingue «no habia repetitivos» de «la corrida no llego a correr».

  FUENTE: RepeatMasker Web Server
  URL: https://www.repeatmasker.org/

  PASOS:
    1. Entra en repeatmasker.org y ve a Services → RepeatMasking.
    2. Sube el FASTA del transcrito que vas a analizar (el mismo que le das a la app).
    3. En «DNA source» elige Mus musculus. NO lo dejes en el valor por defecto: es el unico sitio donde se elige la biblioteca, y con la equivocada el resultado es indistinguible de uno bueno.
    4. En «Return format» elige «tar file».
    5. En «Return method» elige «email».
    6. Del `.tar.gz` que llega por correo saca DOS ficheros: el `.out` y el `.tbl`.
    7. Renombralos a mouse tal y como los pide la app y subelos juntos.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · version de RepeatMasker
      Sale en la cabecera del `.out` y del `.tbl`. Dos versiones dan resultados distintos sobre la misma secuencia.
    · biblioteca Dfam (con su version)
      RepeatMasker con Dfam_3.0 y con otra biblioteca dan resultados distintos, asi que la version del binario a solas NO identifica la corrida. Va en su propia columna del manifiesto.

  TAMAÑO APROXIMADO: unos pocos KB por corrida (el .out y el .tbl juntos no llegan a 10 KB)

  COMO SE VALIDA AL SUBIRLO: La app comprueba que el `.tbl` declare la MISMA especie que se esta diseñando, y que la longitud de la consulta que declara el resumen (`total length:`) coincida con la de la secuencia cargada. Si no cuadran, se rechaza: una mascara de otra secuencia taparia un tramo que ahi no es repetitivo, y el intervalo cabria sin salirse de rango.

  AVISOS:
    ⚠ El `.tbl` NO es opcional. Una corrida valida y una contra la biblioteca equivocada producen un `.out` INDISTINGUIBLE byte a byte cuando lo unico presente es una repeticion simple, porque esas se detectan por composicion y no por biblioteca. Esta demostrado con datos en el propio proyecto (`masking.INDISTINGUISHABLE_OUTS`): dos ficheros con el mismo md5, uno bueno y otro con biblioteca murina sobre una consulta humana. La unica diferencia vive en el `.tbl`.
    ⚠ El `.out` NO declara la especie. Ninguno lo hace. Por eso sin resumen no hay nada que comprobar — y no haber podido comprobar no es «coincide».
    ⚠ ESTE HUECO NO LO CUBRE gnomAD. gnomAD anota SUSTITUCIONES y capta mal la variacion de longitud, asi que un «gnomAD limpio» invita a creer que la ventana esta comprobada y no lo esta. Son dos filtros y ninguno sustituye al otro.
    ⚠ Que familias cuentan como polimorficas va DECLARADO como parametro y no citado: `Simple_repeat`, `Satellite` y `Low_complexity`. Un SINE es repetitivo pero DISPERSO — no varia de longitud — asi que no entra.
```

### repeticiones — NOT_RUN

**Que mide.** ¿La ventana cae dentro de un elemento repetitivo? Importa por dos cosas distintas: un tramo repetitivo dentro del casete AAV es sustrato de recombinacion, y una guia contra un repetitivo tiene miles de sitios perfectos en el genoma.

**Por que importa / resultado.** NOT_RUN en 1221 de 1221 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

**Criterio.** Este frente no tiene umbral numerico: su veredicto es una comprobacion, no una comparacion contra un corte.

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «repeticiones»

  QUE PREGUNTA RESPONDE: ¿La ventana cae dentro de un elemento repetitivo? Importa por dos cosas distintas: un tramo repetitivo dentro del casete AAV es sustrato de recombinacion, y una guia contra un repetitivo tiene miles de sitios perfectos en el genoma.

  FICHERO(S) QUE HACEN FALTA:
    · rmsk_mouse.out  [OBLIGATORIO]
      Las filas con los intervalos enmascarados. Es lo que se aplica a la secuencia.
    · rmsk_mouse.tbl  [OBLIGATORIO]
      El resumen. Es el UNICO sitio donde se declara la especie de la biblioteca y la longitud de la consulta, asi que es lo unico que permite validar la corrida. Sin el, un `.out` sin filas no distingue «no habia repetitivos» de «la corrida no llego a correr».

  FUENTE: RepeatMasker Web Server
  URL: https://www.repeatmasker.org/

  PASOS:
    1. Entra en repeatmasker.org y ve a Services → RepeatMasking.
    2. Sube el FASTA del transcrito que vas a analizar (el mismo que le das a la app).
    3. En «DNA source» elige Mus musculus. NO lo dejes en el valor por defecto: es el unico sitio donde se elige la biblioteca, y con la equivocada el resultado es indistinguible de uno bueno.
    4. En «Return format» elige «tar file».
    5. En «Return method» elige «email».
    6. Del `.tar.gz` que llega por correo saca DOS ficheros: el `.out` y el `.tbl`.
    7. Renombralos a mouse tal y como los pide la app y subelos juntos.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · version de RepeatMasker
      Sale en la cabecera del `.out` y del `.tbl`. Dos versiones dan resultados distintos sobre la misma secuencia.
    · biblioteca Dfam (con su version)
      RepeatMasker con Dfam_3.0 y con otra biblioteca dan resultados distintos, asi que la version del binario a solas NO identifica la corrida. Va en su propia columna del manifiesto.

  TAMAÑO APROXIMADO: unos pocos KB por corrida (el .out y el .tbl juntos no llegan a 10 KB)

  COMO SE VALIDA AL SUBIRLO: La app comprueba que el `.tbl` declare la MISMA especie que se esta diseñando, y que la longitud de la consulta que declara el resumen (`total length:`) coincida con la de la secuencia cargada. Si no cuadran, se rechaza: una mascara de otra secuencia taparia un tramo que ahi no es repetitivo, y el intervalo cabria sin salirse de rango.

  AVISOS:
    ⚠ El `.tbl` NO es opcional. Una corrida valida y una contra la biblioteca equivocada producen un `.out` INDISTINGUIBLE byte a byte cuando lo unico presente es una repeticion simple, porque esas se detectan por composicion y no por biblioteca. Esta demostrado con datos en el propio proyecto (`masking.INDISTINGUISHABLE_OUTS`): dos ficheros con el mismo md5, uno bueno y otro con biblioteca murina sobre una consulta humana. La unica diferencia vive en el `.tbl`.
    ⚠ El `.out` NO declara la especie. Ninguno lo hace. Por eso sin resumen no hay nada que comprobar — y no haber podido comprobar no es «coincide».
```

### seed — NOT_RUN

**Que mide.** ¿La seed de la guia coincide con la de alguna familia de miARN de la tabla de seeds que se le haya pasado al diseño? Es el filtro de ventana, previo y mas grueso que `seed_colision`: aquel compara contra los maduros de miRBase uno a uno.

**Por que importa / resultado.** NOT_RUN en 1221 de 1221 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| ventana de seed | posiciones 2-8 | literatura | la seed 2-8 es la definicion estandar del emparejamiento que dirige la represion mediada por miARN; la alternativa 2-7 tambien esta definida y la app la ofrece, pero cambia el espacio de seeds y la tasa base |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «seed»

  QUE PREGUNTA RESPONDE: ¿La seed de la guia coincide con la de alguna familia de miARN de la tabla de seeds que se le haya pasado al diseño? Es el filtro de ventana, previo y mas grueso que `seed_colision`: aquel compara contra los maduros de miRBase uno a uno.

  FICHERO(S) QUE HACEN FALTA:
    · mature.fa  [OBLIGATORIO]
      La fuente normal de las seeds. Es el mismo fichero que cierra `seed_colision`, asi que subiendolo una vez se cierran los dos.

  FUENTE: miRBase (el mismo `mature.fa`), o una tabla propia `seed<TAB>familia`
  URL: https://www.mirbase.org/

  PASOS:
    1. Lo normal es NO pasar tabla propia: sube `mature.fa` de miRBase (pestaña Downloads) y deja que la app derive las seeds.
    2. Si aun asi quieres una tabla propia, escribela como `seed<TAB>familia`, una por linea, con la seed en ADN.
    3. Apunta de donde sale la tabla y con que criterio se hizo: una lista de seeds sin procedencia no es auditable.
    4. El prefijo de especie que corresponde aqui es mmu-

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · release de miRBase (o procedencia de la tabla propia)
      Igual que en `seed_colision`: sin version, una coincidencia no se puede volver a comprobar.

  TAMAÑO APROXIMADO: unos 5,6 MB si se usa `mature.fa`; unos KB si es una tabla propia

  COMO SE VALIDA AL SUBIRLO: La tabla se lee como `seed<TAB>familia` y una fila mal formada aborta. Con `mature.fa` la app verifica el md5 contra el manifiesto. En los dos casos se normaliza U↔T antes de comparar.

  AVISOS:
    ⚠ La lista de 12 seeds que trae el proyecto (`seeds.BOOTSTRAP_SEEDS`) es un ARRANQUE PARA PROBAR LA MECANICA, no un filtro real. El aviso va en el codigo y en cada informe y no se quita: con ella el frente NO esta cerrado.
```

### seed_colision — NOT_RUN

**Que mide.** ¿La seed de esta hebra es la de un miARN maduro conocido y abundante? Compartir seed con uno del nucleo no da off-targets dispersos: secuestra un programa regulador neuronal entero.

**Por que importa / resultado.** NOT_RUN en 1221 de 1221 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| ventana de seed | posiciones 2-8 | literatura | la seed 2-8 es la definicion estandar del emparejamiento que dirige la represion mediada por miARN; la alternativa 2-7 tambien esta definida y la app la ofrece, pero cambia el espacio de seeds y la tasa base |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «seed_colision»

  QUE PREGUNTA RESPONDE: ¿La seed de esta hebra es la de un miARN maduro conocido y abundante? Compartir seed con uno del nucleo no da off-targets dispersos: secuestra un programa regulador neuronal entero.

  FICHERO(S) QUE HACEN FALTA:
    · mature.fa  [OBLIGATORIO]
      Los maduros de miRBase. De aqui salen las seeds contra las que se compara, y tambien las de los controles biologicos del frente de carga de off-targets — nunca escritas en el codigo.

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
      El fichero NO la trae dentro y miRBase renumera entre versiones. Sin release, una colision no se puede volver a comprobar dentro de un año.

  TAMAÑO APROXIMADO: unos 5,6 MB (todas las especies, ~69.000 maduros)

  COMO SE VALIDA AL SUBIRLO: La app comprueba el md5 del fichero contra el manifiesto y filtra por el prefijo de especie. Ademas normaliza U↔T en los DOS lados antes de comparar: sin eso la comparacion daria CERO colisiones en todas, que es un desajuste de alfabeto disfrazado de resultado limpio.

  AVISOS:
    ⚠ ANOTA EL RELEASE. miRBase RENUMERA entre versiones: un maduro puede cambiar de nombre o de numero entre releases, y una colision anotada sin release no se puede volver a comprobar. El fichero no trae la version dentro, asi que si no la apuntas se pierde.
    ⚠ No recortes el fichero a la especie antes de subirlo: la TASA BASE se deriva del fichero cargado y del filtro que se aplique, y con `hsa-` dentro casi se dobla. Que el filtro lo haga la app es lo que mantiene la tasa comparable entre corridas.
```

### transgen — NOT_RUN

**Que mide.** ¿Esta guia impacta contra el TRANSGEN del casete terapeutico? Es una segunda base de especificidad, y falla duro con cero o un desapareamiento: una guia a un solo desapareamiento apaga la construccion terapeutica casi igual que a su diana, y eso seria un fallo silencioso.

**Por que importa / resultado.** NOT_RUN en 1221 de 1221 ventanas: falta el recurso. NOT_RUN no es PASS.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| desapareamientos que hacen FAIL contra el transgen | 0 o 1 | nuestro | una guia a un solo desapareamiento apaga la construccion terapeutica casi igual que a su diana, y eso seria un fallo silencioso: el experimento no distinguiria «el shmiR no funciona» de «el shmiR apago su propio vector» |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «transgen»

  QUE PREGUNTA RESPONDE: ¿Esta guia impacta contra el TRANSGEN del casete terapeutico? Es una segunda base de especificidad, y falla duro con cero o un desapareamiento: una guia a un solo desapareamiento apaga la construccion terapeutica casi igual que a su diana, y eso seria un fallo silencioso.

  FICHERO(S) QUE HACEN FALTA:
    · aav_casete.fa  [OBLIGATORIO]
      La secuencia del casete terapeutico. Es la segunda base de especificidad y la unica forma de saber si una guia apagaria la propia construccion.

  FUENTE: El laboratorio: el fichero del plasmido del casete AAV
  URL: —

  PASOS:
    1. Pide al laboratorio el FASTA del casete que se va a usar.
    2. Asegurate de que es LO QUE LA CELULA MADURA, no el genoma con el intron dentro.
    3. Comprueba con quien te lo da si lleva ya el modulo del shmiR o es el parental sin modulo: no es lo mismo y la lectura del veredicto cambia.
    4. Subelo y apunta su nombre completo y su md5.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · nombre completo del plasmido y su md5
      Un casete distinto da un veredicto distinto, y el nombre del fichero no identifica la construccion.
    · si lleva el modulo del shmiR o es el parental
      Con modulo dentro, toda guia impacta contra su propia horquilla. El dato cambia como se lee TODO el frente.

  TAMAÑO APROXIMADO: unos KB (un plasmido de ~5 kb en FASTA)

  COMO SE VALIDA AL SUBIRLO: La app comprueba POR SECUENCIA si el casete lleva el modulo del shmiR dentro —busca el loop de los andamios conocidos— y avisa. Si le pasas el GENOMA CON EL INTRON DENTRO en vez del transcrito maduro, toda guia da impacto contra SU PROPIA HORQUILLA y el filtro tumba el panel entero por un artefacto, con un motivo que ademas es literalmente cierto: por eso no se ve si nadie lo comprueba.

  AVISOS:
    ⚠ El casete que hay hoy en el proyecto (`aav_casete.fa`) es el PARENTAL, sin el modulo del shmiR, y esta comprobado por secuencia. Por eso su veredicto se puede leer tal cual. Cuando se sustituya por el terapeutico hay que dar el TRANSCRITO MADURO.
    ⚠ XhoI y EcoRI viajan dentro del modulo, heredadas de los contextos de SGEP, y en el plasmido final NO son unicas. El clonaje va por NheI/SacI o por sintesis.
```

### offtarget_seed — NOT_RUN

**Que mide.** ¿Cuantos mensajeros del transcriptoma llevan un sitio para la seed de esta hebra? Es la CARGA de off-targets, y es otra pregunta que la colision con un miARN conocido. No la contesta ningun alineador: 7 nt contiguos no dan un alineamiento puntuable, asi que ningun BLAST los devuelve por mucho que se le baje el word_size.

**Por que importa / resultado.** NOT_RUN: falta `transcriptoma_3utr.fa`, asi que los sitios de seed no se han contado. NOT_RUN no es PASS. EL OFF-TARGET MEDIADO POR SEED NO SE BUSCA CON BLAST, y no es una preferencia: 7 nt contiguos NO DAN UN ALINEAMIENTO PUNTUABLE, asi que un blastn no los devuelve por mucho que se le baje el word_size. Esto es coincidencia EXACTA del heptamero 2-8 sobre los 3'UTR del transcriptoma murino — busqueda de SUBCADENA, no alineamiento— y necesita `transcriptoma_3utr.fa`. Fundirlo con la especificidad en un solo «PASS» daria por cubierto EL MODO DE OFF-TARGET MAS FRECUENTE DE RNAi con una herramienta que no lo detecta. Por eso son DOS frentes y se cuentan aparte.

**Fuente de datos.** NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero.

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| ventana de seed | posiciones 2-8 | literatura | la seed 2-8 es la definicion estandar del emparejamiento que dirige la represion mediada por miARN; la alternativa 2-7 tambien esta definida y la app la ofrece, pero cambia el espacio de seeds y la tasa base |
| sorteos minimos de la distribucion nula (carga de off-targets) | 10.000 | nuestro | con menos, el percentil de la COLA —que es el unico numero accionable— no tiene resolucion |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «offtarget_seed»

  QUE PREGUNTA RESPONDE: ¿Cuantos mensajeros del transcriptoma llevan un sitio para la seed de esta hebra? Es la CARGA de off-targets, y es otra pregunta que la colision con un miARN conocido. No la contesta ningun alineador: 7 nt contiguos no dan un alineamiento puntuable, asi que ningun BLAST los devuelve por mucho que se le baje el word_size.

  FICHERO(S) QUE HACEN FALTA:
    · transcriptoma_3utr_mouse.fa  [OBLIGATORIO]
      Los 3'UTR sobre los que se cuentan los sitios de seed. Un transcrito representativo por gen; si trae varias isoformas, la app lo detecta y avisa de que el conteo esta inflado.

  FUENTE: UCSC Table Browser
  URL: https://genome.ucsc.edu/cgi-bin/hgTables

  PASOS:
    1. Abre el Table Browser de UCSC.
    2. En «assembly» elige mm39
    3. En «group» elige «Genes and Gene Predictions».
    4. En «track» elige «NCBI RefSeq».
    5. En «table» elige «RefSeq All» o «RefSeq Curated».
    6. En «output format» elige «sequence».
    7. Dale a «get output». Entonces pregunta que region quieres: marca SOLO «3' UTR Exons» y desmarca todo lo demas.
    8. Descarga el fichero y subelo tal cual.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · ensamblaje
      Dos ensamblajes dan coordenadas y contenidos distintos. Va en la procedencia del catalogo y viaja con cada veredicto.
    · fecha de la tabla
      RefSeq cambia. Sin la fecha, el conteo no es reproducible — la misma regla que el release de miRBase y la biblioteca de Dfam.
    · criterio de representante por gen
      «Un transcrito por gen» se puede decidir de varias formas (el mas largo, el curado, el canonico). El numero depende de cual se use, asi que se declara.

  TAMAÑO APROXIMADO: unas decenas de MB

  COMO SE VALIDA AL SUBIRLO: Al subirlo la app comprueba que sea FASTA, que el alfabeto sea de ADN, cuenta secuencias y longitud total, calcula el md5 y AUDITA LAS ISOFORMAS: identificadores repetidos, secuencias identicas y —si le das un mapa transcrito→gen— cuantos genes traen mas de un transcrito. Sin ese mapa, esa tercera pregunta queda NO COMPROBADO, que no es «no las hay».

  AVISOS:
    ⚠ NO FILTRES LAS ISOFORMAS A MANO. Que lo haga la app: ella cuenta cuanto infla el conteo y lo dice al lado del resultado. Un filtrado manual no deja rastro y el numero acaba siendo incomparable entre corridas.
    ⚠ La salida de «3' UTR Exons» da un registro POR EXON, asi que un 3'UTR troceado aparece varias veces. No es un error del fichero: es como es, y por eso la app lo audita en vez de rechazarlo.
    ⚠ El fichero NO va a git — son decenas de MB. En el manifiesto quedan solo nombre, tamaño y md5, igual que con `refseq_rna.fa`.
```

### empalme_intron — NOT_RUN

**Que mide.** ¿Se escinde el intron? Es el UNICO frente BINARIO del proyecto: los otros son graduales —una especificidad regular da off-targets, un techo de APA baja el knockdown— pero aqui, si el intron no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y NO HAY PROTEINA DN EN ABSOLUTO. No hay «un poco de proteina» que optimizar.

**Por que importa / resultado.** RIESGO BINARIO. NO ES UN PARAMETRO DE CALIDAD y no se lee como tal: o el intron se escinde o no. Si no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y no hay proteina DN EN ABSOLUTO — no hay «un poco de proteina» que optimizar. Lo que decide no es un candidato ni una plaza del panel: decide si la ARQUITECTURA INTRONICA sigue viva. Por eso va como frente y no como columna. Y la lectura que se hace por defecto NO lo coge: un small RNA-seq puede salir PERFECTO con el empalme fallando. Drosha procesa el pri-miR COTRANSCRIPCIONALMENTE, o sea ANTES del splicing, asi que la horquilla se corta igual este el intron escindido o no. Un shmiR correcto NO ES EVIDENCIA de que haya proteina: son dos sucesos en orden y esa lectura solo mide el primero. SE CIERRA CON TRES LECTURAS DE BANCO, las tres NOT_RUN y ninguna la corre este software: (1) RT-PCR de empalme con cebadores en los exones que flanquean el intron MVM; (2) Western L42 normalizado por vg-qPCR, que es lo que separa «no empalmo» de «no llego el vector»; (3) parental SIN INTRON en la misma tanda, como techo de expresion. Coordenadas NO emitidas en esta corrida: falta el casete (--transgen). El detalle, en el bloque «Empalme del intron».

**Fuente de datos.** ninguna: este frente no se contesta con datos, sino en el banco

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| criterio de Kozak fuerte | purina en -3 y G en +4 | convencion | es el criterio que este analisis aplica para clasificar los uATG, declarado como parametro y no citado  ⚠ SIN BASE MEDIDA: no se pondera la fuerza del contexto ni se usa ninguna matriz: es un corte binario sobre dos posiciones |
| aceptor de empalme utilizable | tracto de pirimidinas comparado con el aceptor LEGITIMO del mismo intron | nuestro | la comparacion es contra una referencia INTERNA —el aceptor que ya funciona en ese intron— asi que el veredicto no depende de ningun umbral traido de fuera. El legitimo tiene 9 pirimidinas contiguas; el mejor criptico, 3 |

**Como se cierra.** (ficha de obtencion, integra)

```
COMO CERRAR EL FRENTE «empalme_intron»

  QUE PREGUNTA RESPONDE: ¿Se escinde el intron? Es el UNICO frente BINARIO del proyecto: los otros son graduales —una especificidad regular da off-targets, un techo de APA baja el knockdown— pero aqui, si el intron no se escinde, la horquilla se queda en el 5'UTR del mRNA maduro y NO HAY PROTEINA DN EN ABSOLUTO. No hay «un poco de proteina» que optimizar.

  NO SE CIERRA CON NINGUN FICHERO.
  Este frente NO SE CIERRA CON NINGUN FICHERO, y por eso va aparte de los demas: sus cuatro lecturas son de BANCO y este software no corre ninguna. Conseguir mas datos no lo cierra: hay que ir al laboratorio.

  FUENTE: Banco: RT-PCR, Western y secuenciacion. No hay descarga que valga.
  URL: —

  PASOS:
    1. RT-PCR de empalme con cebadores en los exones que flanquean el intron MVM. Banda CORTA = empalmado, banda LARGA = retenido, y la PROPORCION es la eficiencia. La app emite las VENTANAS donde buscar los cebadores, derivadas del casete, no los cebadores: Tm, especificidad y horquillas no se improvisan.
    2. SECUENCIA LA BANDA CORTA. Es la lectura que cierra el frente: el donante criptico `GTGAGCG` del andamio compite por el aceptor legitimo del MVM y produce una banda INTERMEDIA (+97 pb) que en un gel se confunde con la buena.
    3. Western con L42 NORMALIZADO POR vg-qPCR. Sin normalizar, «no hay proteina» no se distingue de «no llego el vector»: los dos dan una membrana vacia y solo uno culpa al empalme.
    4. Corre en la MISMA TANDA el parental SIN INTRON, como techo de expresion. Sin techo, un western flojo no dice si el empalme va mal o si la construccion expresa poco.

  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):
    · que construccion se midio, con su md5
      La eficiencia de empalme es de UNA construccion. Sin identificarla, el numero no se puede volver a comprobar ni comparar con otra.
    · la secuencia de la union exon-exon
      Es lo que cierra el frente. Una banda del tamaño esperado no descarta el donante criptico; su secuencia si.

  TAMAÑO APROXIMADO: —

  COMO SE VALIDA AL SUBIRLO: Lo que cierra el frente es la SECUENCIA DE LA UNION EXON-EXON, no la altura de una banda en un gel. Sin secuenciar, ver una banda corta no descarta el donante criptico.

  AVISOS:
    ⚠ UN small RNA-seq PERFECTO NO ES EVIDENCIA DE QUE HAYA PROTEINA. Drosha procesa el pri-miR COTRANSCRIPCIONALMENTE, o sea ANTES del splicing: la horquilla se corta igual este el intron escindido o no. Son dos sucesos en orden y esa lectura solo mide el primero. Por eso este frente no estaba en la lista.
    ⚠ EL CEBADOR DE AGUAS ABAJO CAE DENTRO DEL ORF DE PrP. La especificidad de vector la da el cebador de aguas ARRIBA, y SOLO ese: un par con los dos cebadores aguas abajo amplificaria tambien el Prnp ENDOGENO del tejido — saldria banda, del tamaño esperado, y no seria del vector. Es el error que arruinaria el ensayo sin dar ninguna señal.
    ⚠ El casete que hay (`aav_casete.fa`) NO sirve como parental sin intron: es el parental sin MODULO pero CON el intron vacio de 82 nt, asi que arrastra el mismo problema que se quiere medir. Y el intron del terapeutico son 296 nt, no 82: la eficiencia de uno no dice nada del otro. La app especifica el control sin intron —donante y aceptor eliminados, todo lo demas conservado base a base— y sale en la hoja de pedido.
```

### fraccion_isoforma_larga — CERRADO

**Que mide.** ¿Que fraccion de los transcritos conserva la diana? Un sitio de poliadenilacion alternativa proximal corta el 3'UTR, asi que un candidato por detras de ese corte solo tiene diana en la isoforma larga. Eso no es un veto: es un TECHO de knockdown.

**Por que importa / resultado.** CERRADO. 6 de 10 candidatos quedan por detras del corte de 3utr:236: comparten UN UNICO MODO DE FALLO. Y el rebalanceo tiene tope: los sitios inmunes por tramo son 16/0/0 —todos en el proximal— y el espaciado deja meter cuatro, que son los 4 que ya estan. POR QUE BLOQUEABA: si la fraccion de isoforma corta es alta, esos 6 candidatos entran al cribado con un TECHO INDISTINGUIBLE DE UN shmiR MALO — un techo de 0,3 y una guia que no funciona dan la misma lectura en la placa, y el experimento se gasta en no poder separarlos. ESTADO: MEDIDO. PolyA_DB v4.1, fraccion larga 0.86 ponderada / 0.65 sin ponderar. El mapeo genomico↔transcrito que bloqueaba esta RESUELTO sin coordenadas genomicas y sobre 4 puntos de apoyo, no sobre una resta. Y el techo no es uno: va POR TRAMOS (0.91, 0.86), porque depende de por detras de cuantos cortes esta cada candidato. Con eso deja de cumplirse lo que hacia bloquear a este frente: un techo de 0.86 NO es indistinguible de un shmiR malo en la placa. RESERVA QUE SE MANTIENE: el dato es de TODOS LOS TEJIDOS, no cerebro, y las neuronas alargan los 3'UTR, asi que estas cifras son un LIMITE INFERIOR conservador para el nuestro. La RT-qPCR de los dos amplicones sigue en pie y puede MEJORARLAS.

**Fuente de datos.** MAPEO GENOMICO↔TRANSCRITO — RESUELTO SIN COORDENADAS GENOMICAS. ·   PolyA_DB publica el sitio de CORTE, NO EL HEXAMERO. Su leyenda: «A[A/U]UAAA motif within 40-nt upstream from the PAS» — el hexamero se busca AGUAS ARRIBA del PAS, luego la coordenada publicada es el corte. Con nuestra convencion el hexamero cae 10-30 nt por delante, dentro de esos 40 nt. ·   Hipotesis «PAS = hexamero»: DESCARTADA. Un hexamero es un punto, no una banda, asi que ·   bajo esa lectura el aterrizaje tiene que ser EXACTO — y no hay ningun desfase que haga ·   aterrizar mas de 1 de las 4 coordenadas. Bajo «PAS = corte» aterrizan las 4, ·   con el MISMO desfase y con la CLASE de hexamero que declara la propia base en cada una. ·   No es una resta: son 4 puntos de apoyo independientes. Desfase 3'UTR→mm10 acotado a 131937185-131937193 (9 valores); se deja como INTERVALO ·   porque la banda de corte mide 20 nt y fijarlo en un entero seria inventarse precision. ·  ·     chr2:+:131937444  Other   → corte 3utr:251-271, hexamero AATATA en 3utr:236  ← proximal mas usado: PSE 21,1 %, AvgRPM 0,55 ·     chr2:+:131937504  AAUAAA  → corte 3utr:303-323, hexamero AATAAA en 3utr:288  ← PSE 23,5 %, AvgRPM 0,34 ·     chr2:+:131938392  Other   → AMBIGUO: 2 hexameros de su clase en la banda (TATAAA en 3utr:1178, TATAAA en 3utr:1189). Ancla, pero NO entra al modelo con banda propia. ·     chr2:+:131938427  AUUAAA  → corte 3utr:1229-1249, hexamero ATTAAA en 3utr:1214  (sin datos de expresion)  ← fuerza 99,9 %, conservado en humano y rata; SIN expresion, asi que no entra en la fraccion — solo ancla ·  ·   TECHO POR TRAMOS. Con tres sitios de corte medidos el techo ya no es UNO: la pregunta ·   de un candidato no es cuanta isoforma larga hay, es que fraccion de transcritos conserva ·   SU diana — y eso depende de por detras de cuantos cortes esta. ·     3utr:1-251  sin techo            por delante de todos los cortes medidos: la diana esta en TODAS las isoformas. INMUNE. ·     3utr:252-271  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937444: no se sabe de que lado cae, asi que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     3utr:272-303  techo 0.91           por detras de chr2:+:131937444 ·     3utr:304-323  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937504: no se sabe de que lado cae, asi que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     3utr:324-1242  techo 0.86           por detras de chr2:+:131937444, chr2:+:131937504

| umbral | valor | origen | de donde sale |
|---|---|---|---|
| banda de corte por detras del hexamero | 10-30 nt aguas abajo | literatura | el corte de poliadenilacion ocurre a esa distancia del hexamero; es un resultado clasico del procesamiento del extremo 3' |
| flanco prohibido alrededor del hexamero (eje esterico) | ±10 nt | convencion | es un umbral OPERATIVO para marcar solapamiento con la señal de poliadenilacion  ⚠ SIN BASE MEDIDA: NO TIENE BASE MEDIDA, y es el caso que obliga a distinguir origenes. La huella real de CPSF/CstF sobre el pre-mRNA es MAYOR que 10 nt, asi que una ventana que el filtro deja pasar por 4 nt esta probablemente dentro de la zona de competencia. El eje esterico es un GRADIENTE, no una frontera: cualquier umbral en nucleotidos le atribuye una precision que la biologia no tiene. Por eso el informe emite ademas la SENSIBILIDAD al flanco |

## 4. Tabla de candidatos

Todas las columnas, con un estado POR FILTRO. No se colapsan ni se omiten los que no corrieron: un filtro ausente de la tabla es indistinguible de uno superado.

| rango | inicio | fin | region | inicio_3utr | fin_3utr | tercio | asimetria_kcal | polyA_hexamero | polyA_clase | polyA_posicion_rel | polyA_hexamero_pos | polyA_dist_extremo3 | polyA_solapa_seed | polyA_veredicto | polyA_estricto | polyA_escalonado | polyA_truncamiento | polyA_truncamiento_propio | polyA_esterico | polyA_dist_corte | polyA_fraccion_isoforma_larga | carga_seed | accesibilidad | GC | homopolimero | G4_diana | G4_guia | asimetria | zona_prohibida_polyA | repeticiones | repeticion_polimorfica | seed | especificidad | transgen | seed_colision | bandera_polyA_debil | biofisicos_ok | riesgo_APA | veredicto | diana | guia |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | 10 | 31 | 3'UTR | 10 | 31 | proximal | 4.33 |  |  |  |  |  | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | TCCTGCTTGTTCCTTCGCATTC | UAAUGCGAAGGAACAAGCAGGA |
| 6 | 60 | 81 | 3'UTR | 60 | 81 | proximal | 5.15 |  |  |  |  |  | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | CCACCTGTAGCTCTTTCAATTG | UAAUUGAAAGAGCUACAGGUGG |
| 7 | 143 | 164 | 3'UTR | 143 | 164 | proximal | 5.08 | AATATA | APA_POSIBLE | aguas abajo, 71 nt | 236 | 1001 | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | GCCCTGGGAAATGTACAGTAGA | UCUACUGUACAUUUCCCAGGGC |
| 10 | 200 | 221 | 3'UTR | 200 | 221 | proximal | 3.8 | AATATA | APA_POSIBLE | aguas abajo, 14 nt | 236 | 1001 | no | PASS | PASS | PASS | NO_APLICA | NO_APLICA | NO_APLICA |  |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:no | INCOMPLETE | TCTGTCATCAGCCAGTGCTAAC | UUUAGCACUGGCUGAUGACAGA |
| 5 | 449 | 470 | 3'UTR | 449 | 470 | medio | 5.32 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 198 |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GTGGAATTCTTTCTTTACTAAC | UUUAGUAAAGAAAGAAUUCCAC |
| 3 | 553 | 574 | 3'UTR | 553 | 574 | medio | 5.86 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 302 |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | AGGGCACTAGAATGATCTTTAG | UUAAAGAUCAUUCUAGUGCCCU |
| 4 | 652 | 673 | 3'UTR | 652 | 673 | medio | 5.8 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 401 |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GAGGGATGGTTAAGGTACAAAG | UUUUGUACCUUAACCAUCCCUC |
| 8 | 735 | 756 | 3'UTR | 735 | 756 | medio | 5.08 |  |  |  |  |  | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 484 |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GCCCTATGTTTCTGTACTTCTA | UAGAAGUACAGAAACAUAGGGC |
| 2 | 819 | 840 | 3'UTR | 819 | 840 | distal | 5.96 | CATAAA | OTRA | aguas abajo, 66 nt | 907 | 330 | no | PASS | PASS | PASS | TECHO | NO_APLICA | NO_APLICA | 568 |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | False | True | prediccion:si | INCOMPLETE | GCTCCATTCCAAAGTGGGAAAG | UUUUCCCACUUUGGAAUGGAGC |
| 1 | 1018 | 1039 | 3'UTR | 1018 | 1039 | distal | 6.65 | ACTAAA | OTRA | dentro | 1034 | 203 | si | PASS | FAIL | PASS | TECHO | NO_APLICA | PENALIZADO | 767 |  |  |  | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | True | True | prediccion:si | INCOMPLETE | GGCCGTTCCATCCAGTACTAAA | UUUAGUACUGGAUGGAACGGCC |

## 5. Fichas de los seleccionados

Una ficha por candidato seleccionado, con el veredicto de CADA frente, su procedencia y su fecha.

### 3utr:200

```
═══ Ficha del candidato — mouse 3utr:200 ═══

  sitio      3utr:200-221
  guia       TTTAGCACTGGCTGATGACAGA
  pasajera   CCTGTCATCAGCCAGTGCTAAA
  veredicto  INCOMPLETE

── Frentes (11) ──
  frente                   estado    fecha        procedencia
  empalme_intron           NOT_RUN   —            frente abierto del informe
  especificidad            NOT_RUN   —            sin corrida en el almacen
  fraccion_isoforma_larga  PASS      —            frente CERRADO del informe
  offtarget_seed:guia      NOT_RUN   —            sin corrida en el almacen
  offtarget_seed:pasajera  NOT_RUN   —            sin corrida en el almacen
  repeticion_polimorfica   NOT_RUN   —            frente abierto del informe
  repeticiones             NOT_RUN   —            frente abierto del informe
  seed                     NOT_RUN   —            frente abierto del informe
  seed_colision:guia       NOT_RUN   —            sin corrida en el almacen
  seed_colision:pasajera   NOT_RUN   —            sin corrida en el almacen
  transgen                 NOT_RUN   —            frente abierto del informe

── Asimetria — las TRES cifras, que son magnitudes distintas ──
  cruda +3.80   penalizacion 0.00   neta +3.80

── Techo de APA ──
  sin techo — 3utr:1-251  sin techo            por delante de todos los cortes medidos: la diana esta en TODAS las isoformas. INMUNE.

── Hexameros cercanos ──
  AATATA  3utr:236  APA_POSIBLE/medida a 15 nt por delante

── Bloques ──
  modulo NheI-SacI (149 nt):
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

── Historial de BLAST ──
  SIN CORRIDAS. El frente de especificidad sigue en NOT_RUN, y NOT_RUN no es PASS.
```

## 6. Limitaciones

Seccion propia y no un pie: una limitacion al pie se lee despues de haber creido el numero.

### Umbrales SIN base medida

Estos no salen de ninguna medida. Se declaran como convenio o como decision de este proyecto, y presentarlos junto a los que si tienen base sin distinguirlos les atribuiria una precision que no tienen.

| umbral | valor | por que no tiene base medida |
|---|---|---|
| homopolimero maximo | 4 nt | el corte en 4 es un redondeo operativo, no un punto medido: 5 no es cualitativamente distinto de 4 |
| asimetria minima (proxy) | +1,0 kcal/mol | el proxy no esta calibrado contra energias medidas, asi que el numero ordena candidatos entre si pero no es una magnitud fisica |
| flanco prohibido alrededor del hexamero (eje esterico) | ±10 nt | NO TIENE BASE MEDIDA, y es el caso que obliga a distinguir origenes. La huella real de CPSF/CstF sobre el pre-mRNA es MAYOR que 10 nt, asi que una ventana que el filtro deja pasar por 4 nt esta probablemente dentro de la zona de competencia. El eje esterico es un GRADIENTE, no una frontera: cualquier umbral en nucleotidos le atribuye una precision que la biologia no tiene. Por eso el informe emite ademas la SENSIBILIDAD al flanco |
| espaciado minimo entre candidatos elegidos | 50 nt | 50 nt no sale de ninguna medida de correlacion espacial de fallos: sale de que sea claramente mayor que una ventana de 22 nt y de que deje sitio para el panel |
| criterio de Kozak fuerte | purina en -3 y G en +4 | no se pondera la fuerza del contexto ni se usa ninguna matriz: es un corte binario sobre dos posiciones |

### La carga de off-targets es un LIMITE SUPERIOR

| limitacion | direccion | detalle |
|---|---|---|
| Sin ponderacion por conservacion | sobrestima | No tenemos alineamientos multiespecie; TargetScan si. Nuestro numero cuenta SITIOS, no sitios probablemente funcionales: un sitio que no esta conservado en ninguna otra especie pesa aqui lo mismo que uno conservado en todas. Sobrestima. |
| Sin ponderacion por APA | sobrestima | Un sitio en la parte DISTAL de un 3'UTR con poliadenilacion alternativa no esta en todos los mensajeros de ese gen: la isoforma corta no lo lleva. Lo sabemos por Prnp, donde la fraccion de isoforma larga esta medida en 0,86, y aplica a los demas genes igual — solo que ahi no lo hemos medido. Sobrestima. |
| Sin ponderacion por expresion | sobrestima | Un sitio en un gen que la neurona no expresa no cuenta como off-target. Si algun dia hay `expresion_cerebro.tsv` con su referencia y su umbral, esto se refina; hoy no lo hay y todos los genes del fichero pesan igual. Sobrestima. |

> **LAS TRES LIMITACIONES EMPUJAN EN LA MISMA DIRECCION, asi que el numero es un LIMITE SUPERIOR: cuenta SITIOS, no sitios probablemente funcionales. No se compensa con un factor ni se corrige a ojo — se dice.**

### La especificidad no cubre los off-targets por seed

EL OFF-TARGET MEDIADO POR SEED NO SE BUSCA CON BLAST, y no es una preferencia: 7 nt contiguos NO DAN UN ALINEAMIENTO PUNTUABLE, asi que un blastn no los devuelve por mucho que se le baje el word_size. Esto es coincidencia EXACTA del heptamero 2-8 sobre los 3'UTR del transcriptoma murino — busqueda de SUBCADENA, no alineamiento— y necesita `transcriptoma_3utr.fa`. Fundirlo con la especificidad en un solo «PASS» daria por cubierto EL MODO DE OFF-TARGET MAS FRECUENTE DE RNAi con una herramienta que no lo detecta. Por eso son DOS frentes y se cuentan aparte.

### La accesibilidad es DESEMPATE, nunca filtro

Es el criterio peor predicho del pipeline. Se calculan dos ventanas de contexto (±80 y ±150) y si discrepan, el numero no sirve ni para desempatar.

### La asimetria usa un PROXY, no una energia libre de duplex

Ordena candidatos entre si; no es una magnitud fisica y no se debe leer como tal. Su especificacion tuvo un error de signo que ningun test de consistencia interna habria detectado, asi que hay dos tests de cordura biologica que fijan los signos.

### Un frente que no se cierra con ningun fichero

El empalme del intron es BINARIO y solo se contesta en el banco. Y la lectura que se hace por defecto NO lo coge: un small RNA-seq puede salir perfecto con el empalme fallando, porque Drosha procesa el pri-miR cotranscripcionalmente — o sea ANTES del splicing. Un shmiR correcto no es evidencia de que haya proteina.

## 7. Procedencia

Todos los ficheros que entraron, con version y md5. Sin esto un veredicto no es auditable dentro de un año — que es la razon por la que el manifiesto se versiona en texto.

| recurso | procedencia |
|---|---|
| mascara de repetitivos | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| maduros de miRBase | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| tabla de seeds | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| base de especificidad | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| casete del transgen | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| 3'UTR del transcriptoma | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
| APA medido | MAPEO GENOMICO↔TRANSCRITO — RESUELTO SIN COORDENADAS GENOMICAS. ·   PolyA_DB publica el sitio de CORTE, NO EL HEXAMERO. Su leyenda: «A[A/U]UAAA motif within 40-nt upstream from the PAS» — el hexamero se busca AGUAS ARRIBA del PAS, luego la coordenada publicada es el corte. Con nuestra convencion el hexamero cae 10-30 nt por delante, dentro de esos 40 nt. ·   Hipotesis «PAS = hexamero»: DESCARTADA. Un hexamero es un punto, no una banda, asi que ·   bajo esa lectura el aterrizaje tiene que ser EXACTO — y no hay ningun desfase que haga ·   aterrizar mas de 1 de las 4 coordenadas. Bajo «PAS = corte» aterrizan las 4, ·   con el MISMO desfase y con la CLASE de hexamero que declara la propia base en cada una. ·   No es una resta: son 4 puntos de apoyo independientes. Desfase 3'UTR→mm10 acotado a 131937185-131937193 (9 valores); se deja como INTERVALO ·   porque la banda de corte mide 20 nt y fijarlo en un entero seria inventarse precision. ·  ·     chr2:+:131937444  Other   → corte 3utr:251-271, hexamero AATATA en 3utr:236  ← proximal mas usado: PSE 21,1 %, AvgRPM 0,55 ·     chr2:+:131937504  AAUAAA  → corte 3utr:303-323, hexamero AATAAA en 3utr:288  ← PSE 23,5 %, AvgRPM 0,34 ·     chr2:+:131938392  Other   → AMBIGUO: 2 hexameros de su clase en la banda (TATAAA en 3utr:1178, TATAAA en 3utr:1189). Ancla, pero NO entra al modelo con banda propia. ·     chr2:+:131938427  AUUAAA  → corte 3utr:1229-1249, hexamero ATTAAA en 3utr:1214  (sin datos de expresion)  ← fuerza 99,9 %, conservado en humano y rata; SIN expresion, asi que no entra en la fraccion — solo ancla ·  ·   TECHO POR TRAMOS. Con tres sitios de corte medidos el techo ya no es UNO: la pregunta ·   de un candidato no es cuanta isoforma larga hay, es que fraccion de transcritos conserva ·   SU diana — y eso depende de por detras de cuantos cortes esta. ·     3utr:1-251  sin techo            por delante de todos los cortes medidos: la diana esta en TODAS las isoformas. INMUNE. ·     3utr:252-271  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937444: no se sabe de que lado cae, asi que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     3utr:272-303  techo 0.91           por detras de chr2:+:131937444 ·     3utr:304-323  TECHO INDETERMINADO  dentro de la banda de corte de chr2:+:131937504: no se sabe de que lado cae, asi que el techo es INDETERMINADO (PENALIZADO, no TECHO) ·     3utr:324-1242  techo 0.86           por detras de chr2:+:131937444, chr2:+:131937504 |
| lista ampliada de abundancia | NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero. |
