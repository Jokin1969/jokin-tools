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
| `apps/asignacion/`, `apps/auth/`, `apps/bitacora/`, `apps/datamatrix/`, `apps/feep/`, `apps/imprimir/`, `apps/qr-tis/`, `apps/re-memory/` | Micro-apps del hub (Node/Express) | Las de este fichero |
| `apps/batchwork/` | Operaciones por lotes sobre ficheros (Node + scripts Python auxiliares) | Las de este fichero |
| `apps/shmir-design/` | Proyecto Python 3.11+ independiente: CLI, interfaz Streamlit y una operación en el sidebar de Batchwork | **`apps/shmir-design/CLAUDE.md`** |
| `apps/shmir/` | El hub sirviendo esa interfaz Streamlit en `/shmir` (proceso hijo + proxy) | Las de este fichero |

`apps/batchwork/` y `apps/shmir-design/` son cosas distintas: el primero es la app de
lotes del hub, el segundo el diseñador de shmiRs. Lo único que comparten es un puente:
`apps/batchwork/python/shmir_design_run.py` llama al CLI de shmir-design para la
operación «Diseñar shmiRs» del sidebar. Ese puente no debe contener lógica.

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
npm run check:shmir       # regla 2 de shmir-design sobre el AST
npm run test:shmir        # tests de shmir-design (394, sin dependencias externas)
```

La interfaz Streamlit de `apps/shmir-design/` es opcional y se instala aparte
(`pip install -r apps/shmir-design/requirements-ui.txt`); ni el hub ni los CLI la
necesitan.
