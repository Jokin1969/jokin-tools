# Jokin's Tools — notas para agentes

Hub de utilidades. Node.js + Express, SQLite (`better-sqlite3`), frontend vanilla,
deploy en Railway. Detalles de stack y variables de entorno en el `README.md` (ojo: su
sección "Estructura" está desactualizada, la de abajo no).

## Puede haber otro agente trabajando en este repo a la vez

Este repo tiene varias sesiones/agentes trabajando en paralelo, normalmente en zonas
distintas del Mapa de abajo. Para que las fusiones a `main` sigan siendo automáticas:

- **Sincroniza con `origin/main` a menudo durante una rama larga**, no solo justo antes
  de fusionar (`git fetch origin main && git merge origin/main` en tu rama de trabajo).
  Cuanto más tiempo pase una rama sin tocar `main`, más grande es el diff a reconciliar
  y más probable un choque de verdad. Si `git merge --ff-only` falla porque `main` avanzó,
  NO es necesariamente un conflicto: mergea `origin/main` en tu rama, corre los tests, y
  si no hay marcas `<<<<<<<` vuelve a intentar el fast-forward — no fuerces nada.
- Los ficheros "columna vertebral" que cualquier app nueva toca —`server.js` (el mount) y
  `apps/auth/apps-registry.js` (el array `APPS`)— son el único punto real de choque entre
  agentes distintos. Añade tu entrada **al final del bloque que corresponda, sin reordenar
  ni tocar entradas ajenas**: eso es lo que permite que Git fusione solo aunque otra
  sesión edite el mismo fichero en paralelo.

## Mapa

| Ruta | Qué es | Reglas |
|---|---|---|
| `server.js`, `src/`, `public/`, `lib/`, `test/` | Hub principal (Node/Express) | Las de este fichero |
| `apps/asignacion/`, `apps/auth/`, `apps/bitacora/`, `apps/datamatrix/`, `apps/feep/`, `apps/galenica/`, `apps/imprimir/`, `apps/pastillero/`, `apps/qr-tis/`, `apps/re-memory/` | Micro-apps del hub (Node/Express) | Las de este fichero |
| `apps/batchwork/` | Operaciones por lotes sobre ficheros (Node + scripts Python auxiliares) | Las de este fichero |
| `apps/shmir-design/` | Proyecto Python 3.11+ independiente: CLI, interfaz Streamlit y una operación en el sidebar de Batchwork | **`apps/shmir-design/CLAUDE.md`** |
| `apps/shmir/` | El hub sirviendo esa interfaz Streamlit en `/shmir` (proceso hijo + proxy) | Las de este fichero |

`apps/batchwork/` y `apps/shmir-design/` son cosas distintas: el primero es la app de
lotes del hub, el segundo el diseñador de shmiRs. Lo único que comparten es un puente:
`apps/batchwork/python/shmir_design_run.py` llama al CLI de shmir-design para la
operación «Diseñar shmiRs» del sidebar. Ese puente no debe contener lógica.

`apps/pastillero/pill-images/` (fotos de pastilla por Código Nacional, `<CN>.png`)
vive **dentro del repo a propósito**, no en un volumen: se sube por GitHub, no por
acceso al servidor. Lo que se SIRVE de verdad es otra cosa: al arrancar,
`pill-images.js` copia esa carpeta al volumen (`PASTILLERO_PILL_IMAGES_DIR`, por
defecto `/data/pastillero/pills` en producción) — mismo motivo que
`SHMIR_REFERENCE_DIR` (filesystem del contenedor efímero), pero el mecanismo es el
opuesto: aquí Git es la ÚNICA fuente (nadie sube nada desde un panel en marcha), así
que la sincronización es un espejo completo en cada arranque —copia lo nuevo,
borra del volumen lo que ya no esté en el repo—, no una siembra de una sola vez.
Servida en `GET /pastillero/assets/pill/<CN>.png`, compartida tal cual por
Pastillero, Data Matrix, Asignación y Galénica.

`apps/galenica/ingest.js` alimenta el catálogo de Galénica con los Código Nacional
que van entrando por Data Matrix y Asignación — DE UN SOLO SENTIDO: esas dos apps
llaman a `ingestCn(cn)` justo tras crear el registro (caja escaneada, medicamento
añadido a un plan…) y no esperan ni necesitan respuesta; Galénica nunca escribe en
sus bases de datos. Es best-effort y no bloqueante (nunca hace fallar la petición que
lo dispara), y sólo actúa si el CN es NUEVO para Galénica — uno ya existente no se
vuelve a tocar, ni con datos de CIMA más frescos, para no pisar una ficha ya editada
a mano (sobre todo el color, que Galénica siempre lleva manual). Al arrancar,
`backfillAll()` (llamado desde `runStartupMigrations` en `server.js`, en segundo
plano) hace el mismo catch-up con lo que ya hubiera en esas dos apps antes de que
este feed existiera — Asignación primero, que tiene más.

## `apps/shmir-design/` tiene reglas propias y vinculantes

Antes de tocar cualquier cosa bajo `apps/shmir-design/`, lee entero
[`apps/shmir-design/CLAUDE.md`](./apps/shmir-design/CLAUDE.md). No son orientativas:
prohíben generar secuencias biológicas, prohíben tragarse errores, obligan a estados
`PASS`/`FAIL`/`NOT_RUN` en los filtros, a verificar endpoints y formatos antes de
escribirlos, a escribir los tests primero con datos reales, y a no salir de la librería
estándar sin autorización escrita.

Esas reglas **no** aplican al resto del hub, que es Node y tiene sus dependencias ya
instaladas. Y al revés: los patrones del hub Node no se importan a `apps/shmir-design/`.

## `apps/shmir/` sirve la interfaz de shmir-design dentro del hub

Son **dos frentes distintos** para el mismo diseñador y conviene no confundirlos:

- **`apps/batchwork/` → «Diseñar shmiRs»** llama al **CLI** (`tools/design.py`) por el
  puente `apps/batchwork/python/shmir_design_run.py`. Es por lotes: subes uno o dos
  FASTA, sale un ZIP. La especie sale del **nombre del fichero**, no hay ficheros de
  referencia y no hay modales.
- **`apps/shmir/` → `/shmir`** arranca la **interfaz Streamlit** como proceso hijo en
  `127.0.0.1` y la sirve por un proxy inverso. Es la interactiva: desplegable de
  especies, panel de ficheros de referencia con subida, los tres modales e informe.

Lo que hay que saber para tocarlo:

- **El proceso arranca PEREZOSO**, en la primera petición a `/shmir`, no al bootear el
  hub: Streamlit tarda segundos, ocupa memoria y la mayoría de quien entra al hub no
  abre esta app. Si no arranca, la respuesta es un **503 con el motivo** —la salida del
  proceso— y no un 502 mudo: «no disponible» a secas no distingue «falta Streamlit» de
  «el puerto está cogido».
- **Escucha SÓLO en `127.0.0.1`.** En `0.0.0.0` quedaría accesible por su puerto
  saltándose el login del hub. La única puerta es el proxy.
- **El `upgrade` a WebSocket NO pasa por los middlewares de Express**, así que
  `app.use('/shmir', requireApp(…))` protege la página y **no** protege el socket — y
  Streamlit hace todo por él (`/_stcore/stream`). La sesión y el permiso se comprueban a
  mano en `proxy.upgradeAllowed`, enganchada en `server.on('upgrade')`, y tiene tests
  propios. Si alguien mueve ese handler, la app queda abierta sin login.
- **El `Origin` se REESCRIBE al del upstream.** El navegador manda el del hub y Streamlit
  sólo admite localhost (`server.enableCORS`), así que rechaza el WebSocket con un 403 y
  la página se queda con el **esqueleto sin rellenar** — sin ningún error visible. Se
  reescribe en vez de apagarle el CORS: así lo único con un Origin aceptable es lo que
  pasa por el proxy, que ya comprueba sesión y permiso.
- **`/shmir` lleva su propia CSP.** La del hub bloquea la fuente `data:` de Streamlit y
  sus workers `blob:`. Se le da una política a esa ruta en vez de relajar la del hub; no
  lleva `'unsafe-eval'`, comprobado con un navegador de verdad.
- **Streamlit se apaga el modo desarrollo a mano** (`--global.developmentMode=false`): lo
  decide con `"site-packages" not in __file__`, y `pip install --target=` deja la ruta sin
  él, así que `--server.port` pasa a ser un conflicto y el proceso aborta. En local vive
  en site-packages: esto pasa en desarrollo y revienta en producción.
- **El mensaje de fallo NO interpreta.** Enseña las últimas líneas de la salida del
  proceso **tal cual**, y una pista sólo cuando la propia salida la nombra
  (`process.diagnose`). Antes se pegaba «comprueba que Streamlit está instalado» a TODO
  fallo, y el primero de producción fue un conflicto de configuración con Streamlit ya
  importado y corriendo: la página mandaba a mirar el sitio equivocado. Un diagnóstico
  **equivocado** cuesta más que ninguno — la misma lección que el «Alu 0 %» obtenido sin
  buscar Alu.
- **Hay un TEST DE HUMO que levanta la interfaz de verdad** (`test/shmir.smoke.test.js`):
  arranca el proceso, pide la página por el proxy y **abre el WebSocket CON cabecera
  `Origin`**. Existe porque hubo 2.767 tests en verde y la app no abría: se miraban los
  argumentos y las funciones del proxy, no el resultado. Y la cabecera no es un detalle —
  la comprobación anterior usaba una petición cruda, que NO manda `Origin`, así que pasaba
  mientras el navegador recibía un 403. **Un cliente que no se parece al real no prueba
  nada.** Comprobado que el test falla si se quita la reescritura del Origin.
- **Express QUITA el prefijo del montaje**: dentro del router, `/shmir/` llega como `/`.
  Streamlit sirve bajo `--server.baseUrlPath=/shmir`, así que reenviar `req.url` da un
  404 **sin ningún error en ningún log**: la app simplemente no aparece. Se reenvía
  `req.originalUrl`. Lo cazó una prueba de punta a punta, no un test unitario; hay
  regresión escrita.
- **Los ficheros de referencia viven en el VOLUMEN, no en la imagen**
  (`SHMIR_REFERENCE_DIR`, por defecto `/data/shmir/reference` en producción). El sistema
  de ficheros de la imagen es efímero: dentro de ella, todo lo subido por el panel
  desaparecería en el siguiente redespliegue y el único síntoma sería un frente que
  vuelve a salir NOT_RUN. Lo versionado se **siembra** ahí la primera vez y **no se
  vuelve a pisar** — ni los ficheros ni el `manifest.tsv`, que es el que lleva los md5 de
  lo subido. Sin la variable, todo apunta al directorio del paquete y en local no cambia
  nada.
- **Los PROYECTOS también viven en el volumen y en OTRO directorio**
  (`SHMIR_PROJECT_DIR`, por defecto `/data/shmir/proyectos` en producción). Ahí va el
  registro append-only de lo que se decidió —corridas, selecciones, veredictos— y el
  motivo pesa más que en la referencia: un veredicto tiene que sobrevivir **a la app que
  lo escribió**. Va aparte de la referencia porque la referencia **se siembra** desde lo
  versionado y los proyectos no tienen semilla ninguna: en un solo directorio, la siembra
  tendría que distinguir qué pisa y qué no, que es justo lo que no sabe hacer. Si la
  variable no llega al proceso hijo, la persistencia funciona entera en local y en
  producción se pierde en el siguiente redespliegue, sin ningún síntoma hasta que alguien
  busca lo que guardó ayer.
- **Streamlit se instala en el build** (`nixpacks.toml`) y se arranca como
  `python3 -m streamlit`, no por el ejecutable de la consola: `pip install --target` lo
  deja en un `bin` que no está en el PATH. La comprobación de importación va en el build
  a propósito, para que un fallo se vea al desplegar y no al abrir la app. Se lleva por
  delante pandas, pyarrow, numpy, altair y tornado: un par de cientos de MB. Si eso
  llegara a pesar demasiado, la salida **no** es quitarle dependencias a Streamlit, es
  desplegar esa interfaz como servicio aparte.
- **Sin dependencias nuevas en el hub**: el proxy son ~130 líneas sobre `node:http`
  porque hay un único upstream, es nuestro y está en `127.0.0.1`.

## Comprobaciones

```bash
npm test                  # suite del hub Node (node --test)
npm run check:shmir       # regla 2 de shmir-design sobre el AST + alcanzabilidad
npm run check:tildes      # el castellano de los mensajes que ve el usuario
npm run test:shmir        # tests de shmir-design (sin dependencias externas)
```

`check:shmir` imprime además el **informe de alcanzabilidad**: qué función pública de
`apps/shmir-design/` no tiene ningún llamador fuera de su propio módulo y de sus tests.
No es un fallo automático —hay casos legítimos— pero aparecer ahí obliga a decidir: o se
cablea, o se justifica por escrito en `apps/shmir-design/data/alcanzabilidad.toml`, o se
borra. Existe porque el proyecto llegó **tres veces** a lo mismo: código con tests en
verde y sin caller. El golden lee lo que se emite; esto detecta lo que nunca llega a
emitirse.

La interfaz Streamlit de `apps/shmir-design/` es opcional y se instala aparte
(`pip install -r apps/shmir-design/requirements-ui.txt`); ni el hub ni los CLI la
necesitan.
