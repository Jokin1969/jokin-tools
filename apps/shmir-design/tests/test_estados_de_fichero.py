"""La página pintada con el depósito VACÍO y con el depósito COMPLETO.

Regla 5: escrito antes de bajar el trinquete.

**Qué desbloquea.** Nueve de los diecinueve estados sin pintar del inventario
(`data/estados.toml`) lo estaban por la misma causa: la página resolvía su directorio de
referencia y ninguna corrida de `AppTest` podía cambiarlo, así que el estado de cada rol
lo fijaba lo que hubiera en el repositorio — cuatro roles salían siempre CON y cinco
siempre SIN, y el otro lado de cada uno no lo pintaba nadie.

**Por qué se puede.** `trabajo.reference_dir()` lee `os.environ` **en cada llamada**, y
la página la llama al pintar el panel. Apuntando la variable a un temporal, la misma
página pinta los nueve roles en el estado que se quiera. No hace falta tocar la página:
la indirección ya estaba, la usaba el hub y no la usaba ningún test.

**Lo que NO se puede todavía**, y va escrito para que no se confunda con esto: `AppTest`
no rellena un `file_uploader`, así que la página sigue sin poder llegar a DISEÑADO. Esa
es la otra vía, y es un límite de la herramienta, no de la app.
"""

import os
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from fnmatch import fnmatch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.species import required_files, resolve  # noqa: E402
from shmir_design.trabajo import ENV_VAR  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT = True
except ImportError:  # rule2-ok: ausencia de una dependencia OPCIONAL de la interfaz.
    # Mismo criterio que en `test_streamlit_app.py`: el motivo se enseña en el skip y el
    # núcleo sigue siendo stdlib pura.
    STREAMLIT = False

RAIZ = Path(__file__).resolve().parent.parent
from tests.pagina import sin_proyectos

APP = RAIZ / "ui" / "streamlit_app.py"
REFERENCIA = RAIZ / "data" / "reference"

#: Los roles, DERIVADOS de la especie. Uno nuevo entra solo en los dos estados.
ROLES = tuple(required_files(resolve("raton")))

#: Lo que el depósito COMPLETO tiene que poner y el REPOSITORIO NO VERSIONA, CON EL
#: MOTIVO DE CADA UNO. Aquí no hay un real que usar, así que la excepción del principio
#: nº 18 no aplica: esa regla obliga a justificar el fixture cuando el artefacto real
#: EXISTE — y cuando existe en la máquina de quien corre la suite, `_deposito` lo COPIA.
#:
#: Y los motivos NO son el mismo, que es justo lo que se descubrió al escribir esto: unos
#: son descargas de cientos de MB que no caben en un repositorio; `apa_medido.tsv` no cabe
#: porque TODAVÍA NO EXISTE; y `addgene_111170.gb` no es por tamaño ninguno. Un motivo
#: común habría tapado esas diferencias.
#:
#: Lo que se pinta con un marcador es el ESTADO del panel —presente contra ausente—, no
#: su contenido. La lista no se transcribe: el test de abajo la cruza con lo que
#: `data/reference/.gitignore` DECLARA versionado, y falla si alguien versiona uno y no lo
#: quita de aquí —o al revés—. **Antes se cruzaba con el DISCO**, y eso hacía que la
#: respuesta dependiera de la máquina: en un clon limpio faltan siete y en la máquina de
#: quien ya se bajó `mature.fa` faltan cinco, así que la misma tabla estaba bien y mal a
#: la vez. Lo que el repositorio versiona lo dice el repositorio, no el disco de nadie.
MOTIVO_SIN_VERSIONAR = {
    "refseq_rna.fa": "Descarga de cientos de MB: el RefSeq de la especie entero.",
    "transcriptoma_3utr.fa": "Descarga de cientos de MB: los 3'UTR de todo el transcriptoma.",
    "expresion_cerebro.tsv": "Tabla de expresión por tejido; se descarga, no se versiona.",
    "mirgenedb_cerebro.txt": "La capa ampliada de MirGeneDB; se descarga, no se versiona.",
    "mature.fa": (
        "Los maduros de miRBase, 5,6 MB. Es el ejemplo que la cabecera de "
        "`data/reference/.gitignore` nombra por su nombre al explicar por qué los datos "
        "de referencia no entran en git. Se descarga CON SU RELEASE, que es obligatorio: "
        "miRBase renumera entre versiones."
    ),
    "addgene_111170.gb": (
        "NO es por tamaño, y por eso el motivo no puede ser el del vecino: son ~20 kB de "
        "un depósito PÚBLICO, el mismo orden que `addgene_198131.gb`, que SÍ está "
        "versionado con su excepción escrita. Lo que pasa es que a éste nadie le escribió "
        "la suya, así que en un clon limpio el frente de los contextos sale NOT_RUN para "
        "todo el mundo menos para quien lo subió — que es exactamente lo que la excepción "
        "de #198131 se escribió para evitar. Queda ANOTADO como pendiente de decidir, no "
        "cerrado: versionarlo es una línea en `data/reference/.gitignore` más el fichero, "
        "y el fichero aquí no está. No se reconstruye (regla 1)."
    ),
    "apa_medido.tsv": (
        "No es que no quepa: es que TODAVÍA NO EXISTE. Es el fichero del 3'-end seq de "
        "cerebro, y cuando llegue lo primero es cruzar su techo con el 0,86 de PolyA_DB "
        "—ver `apa.APA_ARE_TWO_FILES`—, no enchufarlo."
    ),
}


def versiona_el_repositorio(nombre: str) -> bool:
    """¿Versiona git este fichero de referencia? Se DERIVA de su `.gitignore`.

    Ese fichero ignora `*` y va declarando excepciones con `!`, así que la lista de lo
    versionado **está escrita ahí** y con su justificación al lado. Transcribirla aquí
    sería la errata nº 28: dos copias del mismo dato, envejeciendo cada una por su lado.

    No se llama a `git`: no es stdlib (regla 6) y además contestaría por el índice de la
    copia de trabajo, que no es la pregunta.
    """
    patrones = [
        linea[1:].strip()
        for linea in (REFERENCIA / ".gitignore").read_text(encoding="utf-8").splitlines()
        if linea.startswith("!")
    ]
    return any(fnmatch(nombre, patron) for patron in patrones)


@contextmanager
def _deposito(poblar: bool):
    """Apunta la página a un depósito de prueba, vacío o completo.

    `poblar` COPIA los ficheros de verdad **siempre que existan**; no los fabrica.
    Fabricar uno que existe sería un fixture sintético donde hay real (principio nº 18) y
    encima inútil: el panel describe el fichero —su tamaño, su ficha—. Los cuatro que el
    repositorio no versiona llevan un marcador de presencia, por
    `MOTIVO_SIN_VERSIONAR`.

    LÍMITE, escrito: con un marcador se pinta el estado CON **del panel**, que es lo que
    este fichero viene a cubrir. No prueba que el frente corra — para eso haría falta el
    fichero de verdad, y ésos no caben en el repositorio.
    """
    antes = os.environ.get(ENV_VAR)
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp)
        if poblar:
            for fila in ROLES:
                for nombre in fila.filenames:
                    origen = REFERENCIA / nombre
                    if origen.is_file():
                        shutil.copy(origen, destino / nombre)
                    elif nombre in MOTIVO_SIN_VERSIONAR:
                        # Ver MOTIVO_SIN_VERSIONAR: no hay real que copiar. Y NO vale
                        # vacío: el panel no usa `is_file()` —un fichero de 0 bytes
                        # existe y no tiene nada dentro, errata nº 15— así que uno vacío
                        # se sigue pintando como ausente.
                        (destino / nombre).write_text(
                            f"# marcador de presencia — {MOTIVO_SIN_VERSIONAR[nombre]}\n",
                            encoding="utf-8",
                        )
                    else:
                        # Ni está ni tiene motivo declarado, así que este depósito NO es
                        # completo y lo que se midiera sobre él diría otra cosa. Se SALTA
                        # nombrando el fichero: un `KeyError` aquí —que es lo que había—
                        # sale como una traza de diccionario sobre un test de la página, o
                        # sea un rojo que no dice ni qué falta ni dónde se declara. Quien
                        # va rojo, y es lo correcto, es el cruce de abajo: ése es el que
                        # dice que la tabla y el repositorio ya no coinciden.
                        raise unittest.SkipTest(
                            f"NOT_RUN: no se puede montar un depósito COMPLETO — falta "
                            f"data/reference/{nombre} y no tiene motivo en "
                            f"MOTIVO_SIN_VERSIONAR ({__name__})."
                        )
        os.environ[ENV_VAR] = str(destino)
        try:
            yield destino
        finally:
            if antes is None:
                os.environ.pop(ENV_VAR, None)
            else:
                os.environ[ENV_VAR] = antes


def deposito_vacio():
    """Todos los roles en SIN. El marcador que lee `tools/auditar_estados.py`."""
    return _deposito(poblar=False)


def deposito_completo():
    """Todos los roles en CON. El marcador que lee `tools/auditar_estados.py`."""
    return _deposito(poblar=True)


def _pintar(especie="Mus musculus"):
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.selectbox[0].set_value(especie).run()
    return app


def _acciones(app):
    """Lo que se puede HACER sobre una fila. «Ver» es un botón; «Reemplazar» y «Borrar»
    son toggles. Mirar sólo una de las dos listas da una respuesta en verde y falsa."""
    return [b.label for b in app.button] + [t.label for t in app.get("toggle")]


def _texto(app):
    partes = [m.value for m in app.get("markdown")]
    partes += [e.label for e in app.get("expander")]
    partes += [w.label for w in app.get("file_uploader")]
    partes += [b.label for b in app.button]
    return " ".join(partes)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
class TestLaPaginaSePINTAconElDepositoVACIO(unittest.TestCase):
    """Los nueve roles en SIN, a la vez. Es la primera vez que alguien la pinta así."""

    def setUp(self):
        with deposito_vacio():
            self.app = _pintar()
            self.texto = _texto(self.app)

    def test_no_revienta(self):
        self.assertEqual(list(self.app.exception), [])

    def test_TODOS_los_roles_piden_su_fichero(self):
        etiquetas = [w.label for w in self.app.get("file_uploader")]
        for fila in ROLES:
            with self.subTest(fila.role):
                self.assertTrue(
                    any(fila.filenames[0] in e for e in etiquetas),
                    f"{fila.role} no ofrece dónde subir {fila.filenames[0]}",
                )

    def test_y_NINGUNO_ofrece_las_acciones_de_lo_que_ya_esta(self):
        """Sin fichero no hay nada que ver, reemplazar, borrar ni descargar. Ofrecerlo
        sería un botón que no puede funcionar."""
        for accion in ("Ver", "Reemplazar", "Borrar"):
            with self.subTest(accion):
                self.assertNotIn(accion, _acciones(self.app))
        self.assertEqual([b.label for b in self.app.get("download_button")], [])


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
class TestYconElDepositoCOMPLETO(unittest.TestCase):
    """Los nueve en CON. Es el estado al que llega quien ha subido todo — y hasta hoy
    tampoco lo pintaba nadie: en el repositorio faltan cinco de los nueve."""

    def setUp(self):
        with deposito_completo():
            self.app = _pintar()
            self.texto = _texto(self.app)

    def test_no_revienta(self):
        self.assertEqual(list(self.app.exception), [])

    def test_NADIE_pide_ya_ningun_fichero(self):
        pendientes = [
            w.label for w in self.app.get("file_uploader")
            if w.label.startswith("Subir ")
        ]
        self.assertEqual(pendientes, [])

    def test_y_todos_ofrecen_sus_CUATRO_acciones(self):
        """«Reemplazar» y «Borrar» son `toggle`, no `button`: mirando sólo los botones
        este test pasaba en verde afirmando lo contrario de lo que comprobaba."""
        acciones = _acciones(self.app)
        for accion in ("Ver", "Reemplazar", "Borrar"):
            with self.subTest(accion):
                self.assertIn(accion, acciones)
        self.assertTrue([b.label for b in self.app.get("download_button")])

    def test_no_queda_NINGUN_frente_abierto_por_falta_de_fichero(self):
        """El otro lado del mismo panel: con todo puesto, el recuento de lo que falta
        tiene que ser cero. Es la afirmación que el depósito del repositorio no permitía
        hacer, porque en él siempre faltan cinco."""
        self.assertNotIn("Subir ", self.texto)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
class TestLosDosDEPOSITOSpintanCosasDISTINTAS(unittest.TestCase):
    """Si pintaran lo mismo, los dieciocho estados serían nueve y la tabla sobra.

    Es la comprobación que convierte «hay dos estados» en un hecho medido en vez de una
    afirmación: los otros tests miran cada lado por separado y ninguno compara.
    """

    def test_el_panel_NO_es_el_mismo(self):
        with deposito_vacio():
            vacio = _texto(_pintar())
        with deposito_completo():
            completo = _texto(_pintar())
        self.assertNotEqual(vacio, completo)


class TestElDepositoDePRUEBAnoTOCAelDelREPOSITORIO(unittest.TestCase):
    """Un test que escribiera en `data/reference/` contaminaría a todos los demás. Y la
    variable tiene que quedar como estaba: si se fuga, el siguiente test de la suite
    pinta contra un temporal ya borrado."""

    def test_el_temporal_desaparece_y_la_variable_vuelve_a_lo_que_estaba(self):
        antes = os.environ.get(ENV_VAR)
        with deposito_completo() as destino:
            self.assertTrue(destino.is_dir())
            self.assertNotEqual(destino, REFERENCIA)
            self.assertEqual(os.environ[ENV_VAR], str(destino))
        self.assertFalse(destino.exists())
        self.assertEqual(os.environ.get(ENV_VAR), antes)

    def test_el_completo_COPIA_los_reales_y_no_los_fabrica(self):
        """La regla del principio nº 18 aplicada aquí mismo: donde existe el real, se usa
        el real."""
        with deposito_completo() as destino:
            for fila in ROLES:
                for nombre in fila.filenames:
                    origen = REFERENCIA / nombre
                    if not origen.is_file():
                        continue
                    with self.subTest(nombre):
                        self.assertEqual(
                            (destino / nombre).read_bytes(), origen.read_bytes()
                        )


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
class TestLaFilaColapsadaYAUSENTE(unittest.TestCase):
    """El estado que nadie había pintado, y que estaba ROTO en producción.

    `apa_medido.tsv` está en «NO USADO»: su frente ya lo cierra `polya_db_mouse.tsv`, así
    que no es trabajo pendiente y la fila sale colapsada. Pero el fichero NO ESTÁ. La
    página elegía qué pintar con `if fila["acciones"]:` — y para una fila ausente esa
    lista es `["subir"]`, que es **verdadera**. Resultado, hoy, al abrir la app:

    - un recuadro rojo diciendo que el fichero «no está, así que no hay nada que
      descargar», sobre una fila que la propia página acaba de describir como algo que no
      hace falta conseguir;
    - y al pulsar «Ver», la página ENTERA se cae con una excepción sin capturar.

    Ninguna suite lo veía porque ninguna pintaba la página con ese depósito, y el
    inventario de estados decía exactamente eso.
    """

    def setUp(self):
        # El depósito del REPOSITORIO, que es el que tiene la combinación: PolyA_DB está
        # y `apa_medido.tsv` no. No se monta un temporal: aquí el estado interesante es
        # el real.
        self.app = _pintar()

    def test_el_panel_no_saca_un_ERROR_por_algo_que_no_hace_falta(self):
        rojos = [e.value for e in self.app.error]
        self.assertEqual(
            rojos, [], "el panel sale con un error sobre un fichero que no hace falta"
        )

    def test_y_pulsar_VER_no_tira_la_pagina(self):
        for boton in self.app.button:
            if boton.key == "g_ver_apa_medido.tsv":
                self.fail(
                    "una fila AUSENTE ofrece «Ver»: pulsarlo tira la página entera."
                )


class TestLaFilaDICEsiEstaOnO(unittest.TestCase):
    """El otro lado del mismo arreglo, sin pintar: la decisión vive en el núcleo.

    Regla 6. Mientras la página la deducía de `acciones`, la deducía mal y no había dónde
    escribir un test que lo cazara.
    """

    def _filas(self, directorio):
        from shmir_design.presentation import refinement_panel

        return {f["nombre"]: f for f in refinement_panel("raton", directory=directorio)["filas"]}

    def test_con_el_deposito_VACIO_ninguna_dice_que_esta(self):
        with deposito_vacio() as destino:
            filas = self._filas(destino)
        self.assertTrue(filas)
        self.assertEqual([n for n, f in filas.items() if f["presente"]], [])

    def test_con_el_COMPLETO_lo_dicen_todas(self):
        with deposito_completo() as destino:
            filas = self._filas(destino)
        self.assertEqual([n for n, f in filas.items() if not f["presente"]], [])

    def test_una_fila_COLAPSADA_puede_estar_AUSENTE(self):
        """La combinación del fallo, fijada como lo que es: colapsar significa «no ocupa
        sitio», no «está». Si alguien vuelve a juntar las dos cosas, esto lo dice."""
        with deposito_vacio() as destino:
            # Con PolyA_DB puesto y `apa_medido.tsv` no, la fila de APA queda NO USADO.
            shutil.copy(REFERENCIA / "polya_db_mouse.tsv", destino / "polya_db_mouse.tsv")
            fila = self._filas(destino)["apa_medido.tsv"]
        self.assertTrue(fila["colapsada"])
        self.assertFalse(fila["presente"])
        self.assertEqual(fila["estado"], "NO USADO")

    def test_una_fila_NO_colapsada_nunca_esta_PRESENTE(self):
        """La otra rama de la página se apoya en esto, y conviene que se apoye en algo
        comprobado y no en leer `_estado_de` con cuidado.

        Se sostiene por construcción —presente ⇒ CERRADO ⇒ colapsada— y por eso la página
        no lleva una rama para «no colapsada y presente»: sería código inalcanzable, que
        es justo lo que este proyecto persigue. Lo que hace falta es que si alguien rompe
        la implicación, se entere AQUÍ y no en la página.
        """
        for poblar in (deposito_vacio, deposito_completo):
            with poblar() as destino:
                for fila in self._filas(destino).values():
                    if not fila["colapsada"]:
                        with self.subTest(fila["nombre"]):
                            self.assertFalse(fila["presente"])

    def test_y_las_ACCIONES_nunca_estan_vacias_que_es_lo_que_engañaba(self):
        """Se fija el hecho que hacía falsa la comprobación anterior, para que nadie
        vuelva a apoyarse en ella: `acciones` es siempre verdadera."""
        with deposito_vacio() as destino:
            for fila in self._filas(destino).values():
                with self.subTest(fila["nombre"]):
                    self.assertTrue(fila["acciones"])


class TestLoQueElREPOSITORIOnoVERSIONA(unittest.TestCase):
    """La lista de marcadores de presencia no se transcribe: se DERIVA del `.gitignore`.

    Si alguien versiona uno, el depósito completo pasa a copiar el real y aquí hay que
    quitarlo. Lo que no puede pasar es que la tabla crezca —ni encoja— en silencio.

    **Se cruzaba con el DISCO y eso era una pregunta distinta.** «Qué versiona el
    repositorio» no depende de qué haya bajado quien corre la suite: en un clon limpio
    faltan siete ficheros y en la máquina de quien ya tiene `mature.fa` faltan cinco, así
    que la misma tabla salía correcta en un sitio y rota en el otro — y el rojo no decía
    «la tabla está mal», decía «tú no tienes esto». Un rojo que depende de la máquina es
    un rojo que se acaba leyendo como ruido.
    """

    def test_la_lista_declarada_es_EXACTAMENTE_lo_que_el_repositorio_NO_versiona(self):
        sin_versionar = sorted(
            n for fila in ROLES for n in fila.filenames
            if not versiona_el_repositorio(n)
        )
        self.assertEqual(
            sin_versionar,
            sorted(MOTIVO_SIN_VERSIONAR),
            f"Cambió lo que el repositorio versiona: {sin_versionar}. Si es deliberado, "
            f"`MOTIVO_SIN_VERSIONAR` se actualiza a la vez — con SU motivo, no con el "
            f"del vecino.",
        )

    def test_y_la_DERIVACION_distingue_de_verdad(self):
        """Prueba de vida (principio nº 51). Sin esto, un lector de `.gitignore` que
        devolviera `False` siempre haría que la tabla tuviera que listarlo TODO y el
        cruce de arriba seguiría en verde diciendo que ha comprobado algo."""
        self.assertTrue(versiona_el_repositorio("NM_011170.3.fa"))
        self.assertTrue(versiona_el_repositorio("rmsk_mouse.tbl"))
        self.assertTrue(versiona_el_repositorio("polya_db_mouse.tsv"), "el patrón `*`")
        self.assertFalse(versiona_el_repositorio("refseq_rna.fa"))

    def test_cada_uno_dice_el_SUYO(self):
        for nombre, motivo in MOTIVO_SIN_VERSIONAR.items():
            with self.subTest(nombre):
                self.assertGreater(len(motivo), 40, nombre)

    def test_y_el_de_apa_medido_NO_es_el_de_los_demas(self):
        """Lo que un motivo común habría tapado: éste no falta por tamaño."""
        self.assertNotIn("cientos de MB", MOTIVO_SIN_VERSIONAR["apa_medido.tsv"])
        self.assertIn("NO EXISTE", MOTIVO_SIN_VERSIONAR["apa_medido.tsv"])

    def test_y_el_del_PLASMIDO_tampoco(self):
        """El segundo que un motivo común habría tapado, y el que más importa: tiene el
        tamaño de los que SÍ se versionan, así que su ausencia no es una consecuencia del
        criterio de este repositorio — es que nadie escribió su excepción."""
        motivo = MOTIVO_SIN_VERSIONAR["addgene_111170.gb"]
        self.assertIn("NO es por tamaño", motivo)
        self.assertIn("addgene_198131.gb", motivo)


# EL DIRECTORIO DE PROYECTOS SE DECLARA, no se hereda de la máquina. Desde que la primera
# pregunta de la app es «¿retomas un proyecto guardado?», lo que se pinta arriba del todo
# depende de si hay proyectos guardados — y sin declararlo, ése es el del paquete. Con un
# proyecto de prueba dentro, `app.selectbox[0]` deja de ser el de la especie y saltan 24
# tests de ficheros que no tienen nada que ver: un fallo así no dice lo que pasa, dice que
# has roto media app. Ver `tests/pagina.py`.
#
# Va como `setUpModule` y no como gestor de contexto porque tiene que estar puesto durante
# TODOS los `.run()`: cada `set_value(...).run()` vuelve a ejecutar el script de la página.
_ENTORNO_DE_PAGINA = None


def setUpModule():
    global _ENTORNO_DE_PAGINA
    _ENTORNO_DE_PAGINA = sin_proyectos()
    _ENTORNO_DE_PAGINA.__enter__()


def tearDownModule():
    if _ENTORNO_DE_PAGINA is not None:
        _ENTORNO_DE_PAGINA.__exit__(None, None, None)
