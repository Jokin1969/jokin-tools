"""El espacio de coordenadas no tiene valor por defecto. En ningun sitio.

**La via que se le escapaba a los tres guardias que ya habia** (2026-09-07). `coords.
Position` impide imprimir un entero desnudo; `tools/auditar_marcos.py` impide teclear el
prefijo; los 37 literales estan corregidos. Y aun asi la pagina saco `3utr:1768` por
`tx:1768`, porque la etiqueta se fabrico **bien** —con `coords.label` y un miembro de
`coords.Frame`— y lo que estaba mal era el MARCO. Ninguno de los tres guardias mira eso.

De donde salia el marco equivocado, medido: de un **valor por defecto**. Veinte sitios lo
tenian —campos de dataclass, firmas de funcion y un `.get(clave, Frame.UTR3.value)` al
releer el log— y todos decian lo mismo: `3utr`. Asi que olvidarse de pasar el marco no
daba ningun error; daba una posicion de otro sitio, bien formada, dentro de rango y
callada. El caso real: `save_offtarget_run` no guardaba el campo, `LoadResult` lo reponia
por defecto, y una corrida del TRANSCRITO volvia del log con las once posiciones en el
espacio del 3'UTR.

**La regla, y es la misma doctrina que la del prefijo**: si el marco no se puede omitir,
no puede haber un decimo sitio que lo omita. Omitirlo pasa a ser un `TypeError` al
construir el objeto —ruidoso, inmediato y en el sitio del fallo— en vez de una etiqueta
equivocada tres pantallas mas abajo.

**Que NO prohibe**, declarado: escribir `Frame.UTR3` como ARGUMENTO donde el valor esta
de verdad en el 3'UTR (`label(window.inicio_3utr, Frame.UTR3)`). Eso es una afirmacion
sobre ese valor, no un defecto que rellena lo que nadie dijo. Lo que se prohibe es que el
marco lo ponga la AUSENCIA de una decision.

Regla 5: escrito antes.
"""

import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tools import auditar_marcos  # noqa: E402


class TestElGuardiaEstaACero(unittest.TestCase):

    def test_ningun_marco_por_defecto_fuera_de_coords(self):
        informe = auditar_marcos.auditar()
        culpables = [
            f"{f['fichero']}:{f['linea']}  {f['simbolo']}  ({f['donde']})"
            for f in informe.por_defecto
        ]
        self.assertEqual(
            culpables, [],
            "El marco no se pone por defecto: quien construye la posición lo declara.\n"
            + "\n".join(culpables),
        )

    def test_y_el_guardia_dice_CUANTOS_ficheros_ha_mirado(self):
        # Principio nº 51: «no falló» y «no miró» dan el mismo verde.
        self.assertGreater(auditar_marcos.auditar().ficheros, 50)


class TestCazariaLasTresFormas(unittest.TestCase):
    """Un guardia que no se prueba contra el caso que persigue es una lista de deseos.

    Las tres son las que habia de verdad en el codigo el 2026-09-07, copiadas tal cual.
    """

    def _por_defecto(self, fuente: str):
        informe = auditar_marcos.analizar_fuentes(
            {"sonda.py": fuente}, auditar_marcos.declaraciones()
        )
        return informe.por_defecto

    def test_un_CAMPO_de_dataclass(self):
        hallado = self._por_defecto(
            "from dataclasses import dataclass\n"
            "from .coords import Frame\n"
            "@dataclass\n"
            "class LoadResult:\n"
            "    start: int\n"
            "    frame: Frame = Frame.UTR3\n"
        )
        self.assertEqual([f["donde"] for f in hallado], ["campo"])
        self.assertEqual(hallado[0]["simbolo"], "LoadResult")

    def test_una_FIRMA_de_funcion(self):
        hallado = self._por_defecto(
            "from .coords import Frame\n"
            "def self_sites(strand, *, target, frame: Frame = Frame.UTR3):\n"
            "    return frame\n"
        )
        self.assertEqual([f["donde"] for f in hallado], ["firma"])
        self.assertEqual(hallado[0]["simbolo"], "self_sites")

    def test_y_un_DEFECTO_AL_RELEER_el_log(self):
        # `Frame(p.get("candidate_frame", Frame.UTR3.value))`: el mismo defecto, escrito
        # en el sitio donde mas daño hace — la reconstruccion de lo guardado.
        hallado = self._por_defecto(
            "from .coords import Frame\n"
            "def cargar(p):\n"
            "    return Frame(p.get('candidate_frame', Frame.UTR3.value))\n"
        )
        self.assertEqual([f["donde"] for f in hallado], ["al releer"])

    def test_un_marco_como_ARGUMENTO_no_se_toca(self):
        # El control adversario: sin esto, el guardia prohibiria las ~47 etiquetas
        # legitimas del paquete y lo primero que se haria seria apagarlo.
        self.assertEqual(
            self._por_defecto(
                "from .coords import Frame, label\n"
                "def fila(window):\n"
                "    return label(window.inicio_3utr, Frame.UTR3)\n"
            ),
            [],
        )


class TestElMarcoSeEXIGEalConstruir(unittest.TestCase):
    """Y la otra mitad: que omitirlo REVIENTE, no que se quede sin declarar.

    El guardia mira el fuente; esto mira el objeto. Los dos hacen falta: un campo sin
    defecto que nadie construya nunca no prueba que construir sin marco falle.
    """

    def test_un_LoadResult_sin_marco_es_un_TypeError(self):
        from shmir_design.offtarget import Counts, LoadResult, SITE_CLASSES, site_patterns

        with self.assertRaises(TypeError):
            LoadResult(
                start=1, strand="guia", query="q", sequence="ACGTACGTACGTACGTACGTAC",
                patterns=site_patterns("ACGTACGTACGTACGTACGTAC"),
                counts=Counts(
                    sites={c: 0 for c in SITE_CLASSES},
                    transcripts={c: 0 for c in SITE_CLASSES},
                ),
                percentiles={c: 0.0 for c in SITE_CLASSES},
            )

    def test_y_un_SeedResult_tambien(self):
        from shmir_design.seed_scan import SeedResult

        with self.assertRaises(TypeError):
            SeedResult(
                start=1, strand="guia", query="q", sequence="ACGT", heptamer="ACGTACG",
                window="2-8", collisions=(), level="LIMPIO",
            )


class TestNingunaFuncionQueRECIBEunStartEscribeElMarco(unittest.TestCase):
    """La otra forma de la misma familia: escribirlo donde llega una posicion del panel.

    `seed_load_highlights(stores, species, starts)` no tenia de donde derivar el marco
    —recibia enteros pelados— asi que se lo escribio. Un `starts` que viaja sin su marco
    obliga a quien lo imprime a inventarselo: la regla es que ahi el marco se recibe o se
    saca de la corrida, nunca se declara.
    """

    def test_a_cero(self):
        informe = auditar_marcos.auditar()
        culpables = [
            f"{f['fichero']}:{f['linea']}  {f['simbolo']}"
            for f in informe.escrito_sobre_un_start
        ]
        self.assertEqual(culpables, [], "\n".join(culpables))

    def test_y_cazaria_el_caso_real(self):
        hallado = auditar_marcos.analizar_fuentes(
            {
                "sonda.py":
                    "from . import coords\n"
                    "def seed_load_highlights(*, stores, species, starts):\n"
                    "    def _etiqueta(inicio):\n"
                    "        return coords.label(int(inicio), coords.Frame.UTR3)\n"
                    "    return [_etiqueta(i) for i in starts]\n"
            },
            auditar_marcos.declaraciones(),
        ).escrito_sobre_un_start
        self.assertEqual(len(hallado), 1, hallado)
        self.assertEqual(hallado[0]["simbolo"], "seed_load_highlights")


class TestElAuditorNoSeInventaElAST(unittest.TestCase):
    """Que lo que lee sea Python de verdad y no una cadena que casualmente casa."""

    def test_las_sondas_de_arriba_son_codigo_valido(self):
        for fuente in (
            "from dataclasses import dataclass\nclass A:\n    frame: int = 1\n",
        ):
            ast.parse(fuente)


if __name__ == "__main__":
    unittest.main()
