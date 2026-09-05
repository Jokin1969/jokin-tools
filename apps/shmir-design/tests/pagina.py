"""El entorno con el que se PINTA la página en los tests. Declarado, no heredado.

**Por qué existe (2026-09-04).** Desde que la primera pregunta de la app es «¿retomas un
proyecto guardado?», lo que se pinta arriba del todo **depende de si hay proyectos en el
directorio de proyectos**. Y ese directorio, sin declarar, es el del paquete: o sea el de
la máquina donde se corre la suite.

Se vio en el peor sitio posible — corriendo la suite con un proyecto de prueba dentro:
**24 tests en error**, todos de ficheros que no tenían nada que ver, porque
`app.selectbox[0]` había dejado de ser el de la especie y era el del proyecto. Un fallo
así no dice lo que pasa: dice que has roto media app.

La regla es la de siempre en este proyecto: **lo que decide lo que se ve se declara**. Un
test que pinta la página declara con qué proyectos la pinta, igual que `deposito_vacio()`
declara con qué ficheros de referencia.
"""

import contextlib
import os
import tempfile

#: La variable que `trabajo.projects_dir()` lee EN CADA LLAMADA — por eso esto funciona
#: sin tocar la página, igual que `SHMIR_REFERENCE_DIR` en `deposito_vacio()`.
ENV_PROYECTOS = "SHMIR_PROJECT_DIR"


@contextlib.contextmanager
def sin_proyectos():
    """Ningún proyecto guardado: el paso 0 no se pinta y la página empieza por la especie.

    Es el estado de quien abre la app por primera vez, que es el que casi todos estos
    tests quieren mirar. Para el contrario —con proyectos— está `con_proyectos()`.
    """
    with _proyectos_en(vacio=True) as destino:
        yield destino


@contextlib.contextmanager
def con_proyectos(*crear):
    """Un directorio de proyectos con los que se le pasen, ya creados.

    `crear` son `(slug, secuencia, especie, anatomia)` tal cual los quiere
    `presentation.project_create`. Se usa para lo contrario de lo de arriba: comprobar
    que el paso 0 aparece y que la página sigue pintándose con él delante.
    """
    from shmir_design import presentation

    with _proyectos_en(vacio=True) as destino:
        for slug, secuencia, especie, anatomia in crear:
            payload, fuente = presentation.anatomy_payload(anatomia)
            presentation.project_create(
                destino, slug=slug, date="2026-09-04", sequence=secuencia,
                species=especie, anatomy=payload, anatomy_source=fuente,
            )
        yield destino


@contextlib.contextmanager
def _proyectos_en(*, vacio: bool):
    antes = os.environ.get(ENV_PROYECTOS)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ[ENV_PROYECTOS] = tmp
        try:
            yield tmp
        finally:
            if antes is None:
                os.environ.pop(ENV_PROYECTOS, None)
            else:
                os.environ[ENV_PROYECTOS] = antes
