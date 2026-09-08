"""El nombre de cada construcción etiquetaba como 3'UTR una coordenada del transcrito.

Regla 5: escritos antes.

**EL CASO, y es de los que sólo se ven cuando alguien decide con el dato delante.** El
nombre se montaba con `f"{intron}__3utr{start}"`, con el prefijo TECLEADO, y `start` va
en el marco de LO TILADO — que en la página y en el CLI es el TRANSCRITO. Así que la
construcción del candidato `3utr:10` salía del FASTA llamándose `mvm_actual__3utr959`, y
`tx:959` es `3utr:10`: el número es válido en los dos marcos y en uno de ellos es OTRA
ventana. El invariante de rango no puede cazarlo — caza lo imposible, no lo equivocado.

**Y NO ES COSMÉTICO**: el 2026-09-07 se retiró un candidato del panel nombrándolo
«3utr:959». El candidato retirado era el `3utr:10` —el más proximal de los cuatro inmunes
al APA— y `3utr:959` es una ventana distal, con otro veredicto, otro techo de APA y
ninguna inmunidad. Las demás cifras de la decisión (asimetría +4,33, novena de once,
inmune) sólo cuadran con `3utr:10`, y son las que permitieron verlo.

**LO QUE MÁS ENSEÑA es que el guardia tenía este caso EXENTO POR ESCRITO**
(`tools/auditar_marcos.py`): decía que un `3utr` sin dos puntos «es un identificador y no
una etiqueta de posición… no se lee como una coordenada». Se leyó como una coordenada la
primera vez que salió de la app. **Una excepción declarada es una hipótesis**, y ésta
quedó refutada por el uso.

**Y el fichero que ya está fuera no se invalida.** La identidad de una construcción es su
**md5**, no su nombre: un resultado con el nombre viejo se acepta si el md5 cuadra, y se
DICE que el nombre es heredado. Rechazarlo obligaría a repetir una corrida de SpliceAI
por un cambio de etiqueta nuestro.
"""

import unittest

from shmir_design import coords, presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import (
    REFERENCES, fixture_available, load_3utr, load_reference,
)
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.selection import SelectionConfig, select_from_report
from shmir_design.spliceai import RESULT_COLUMNS, build_panel, parse_result
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _panel_del_transcrito():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia),
        source=RegionSource.FIXTURE_VERIFICADO,
    )
    corrida = presentation.page_run(
        species="raton", sequence=secuencia, anatomy=anatomia
    )
    return corrida.selection, anatomia, build_panel(
        corrida.selection, scaffold=SGEP_SCAFFOLD,
    )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElMarcoSE_RECIBE_no_se_teclea(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.seleccion, cls.anatomia, cls.panel = _panel_del_transcrito()

    def test_tilando_el_TRANSCRITO_el_nombre_dice_tx(self):
        # Si esto deja de ser `tx`, el resto de la clase no prueba nada.
        self.assertIs(coords.frame_of(self.anatomia), coords.Frame.TX)
        for construccion in self.panel.constructions:
            self.assertIn("tx:", construccion.name, construccion.name)
            self.assertNotIn("3utr", construccion.name, construccion.name)

    def test_y_la_etiqueta_se_puede_LEER_DE_VUELTA(self):
        """No es texto parecido a una coordenada: es una coordenada."""
        for construccion in self.panel.constructions:
            etiqueta = construccion.name.split("__")[-1]
            posicion = coords.parse(etiqueta)
            self.assertEqual(posicion.value, construccion.candidate_start)
            self.assertIs(posicion.frame, coords.Frame.TX)

    def test_el_candidato_que_se_llamaba_3utr959_es_3utr10(self):
        """La cuenta que hace legible la decisión del 2026-09-07.

        `tx:959` menos el inicio del 3'UTR más uno. No se transcribe: se deriva de la
        anatomía, que es de donde sale todo lo demás.
        """
        inicio_utr3 = self.anatomia.utr3[0]
        self.assertEqual(959 - inicio_utr3 + 1, 10)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestTilandoElUTR3ElNombreDice3utr(unittest.TestCase):
    """El control adversario: con otro marco, otra etiqueta. Se RECIBE."""

    def test_el_nombre_dice_3utr_cuando_lo_tilado_ES_el_3utr(self):
        utr3 = load_3utr(RATON)
        seleccion = select_from_report(
            tile_utr(utr3), SelectionConfig(n_candidates=3)
        )
        panel = build_panel(seleccion, scaffold=SGEP_SCAFFOLD)
        for construccion in panel.constructions:
            self.assertIn("3utr:", construccion.name, construccion.name)
            self.assertNotIn("tx:", construccion.name, construccion.name)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElNOMBRE_VIEJO_sigue_valiendo(unittest.TestCase):
    """La identidad es el md5. Un cambio de etiqueta NUESTRO no invalida un fichero suyo."""

    @classmethod
    def setUpClass(cls):
        cls.seleccion, cls.anatomia, cls.panel = _panel_del_transcrito()
        cls.construccion = cls.panel.constructions[0]

    def _tsv(self, nombre, md5=None):
        cabecera = "\t".join(RESULT_COLUMNS)
        c = self.construccion
        return (
            f"{cabecera}\n"
            f"{nombre}\t{md5 or c.md5}\t{c.donor_position}\tdonante\t0.8\n"
        )

    def test_con_el_nombre_viejo_y_el_md5_bueno_SE_ACEPTA(self):
        viejo = f"{self.construccion.intron}__3utr{self.construccion.candidate_start}"
        sitios = parse_result(
            self._tsv(viejo), constructions=self.panel.constructions
        )
        self.assertEqual(len(sitios), 1)
        self.assertEqual(sitios[0].construction, self.construccion.name)

    def test_y_SE_DICE_que_el_nombre_es_heredado(self):
        """Aceptarlo en silencio sería aceptar cualquier cosa que cuadre de md5."""
        viejo = f"{self.construccion.intron}__3utr{self.construccion.candidate_start}"
        aviso = presentation.splice_legacy_name_note(
            self._tsv(viejo), constructions=self.panel.constructions
        )
        self.assertIn(viejo, aviso)
        self.assertIn(self.construccion.name, aviso)

    def test_sin_nombre_heredado_NO_hay_aviso(self):
        aviso = presentation.splice_legacy_name_note(
            self._tsv(self.construccion.name),
            constructions=self.panel.constructions,
        )
        self.assertEqual(aviso, "")

    def test_un_md5_que_NO_cuadra_se_sigue_rechazando(self):
        """El guardia no se afloja: lo que identifica es el md5, y sin él no entra."""
        viejo = f"{self.construccion.intron}__3utr{self.construccion.candidate_start}"
        with self.assertRaises(ShmirDesignError) as cm:
            parse_result(
                self._tsv(viejo, md5="0" * 32),
                constructions=self.panel.constructions,
            )
        self.assertIn("md5", str(cm.exception))

    def test_y_un_nombre_de_OTRA_corrida_tambien(self):
        with self.assertRaises(ShmirDesignError) as cm:
            parse_result(
                self._tsv("otra_cosa__tx:1", md5="0" * 32),
                constructions=self.panel.constructions,
            )
        self.assertIn("otra_cosa", str(cm.exception))


class TestElGuardiaYA_MIRA_el_prefijo_SIN_dos_puntos(unittest.TestCase):
    """La exención estaba declarada por escrito, y el uso la refutó."""

    def test_caza_la_forma_EXACTA_del_fallo(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("tools").resolve().parent))
        from tools.auditar_marcos import analizar_fuentes

        fuente = 'def f(nombre, elegido):\n    return f"{nombre}__3utr{elegido.start}"\n'
        informe = analizar_fuentes({"falso.py": fuente}, [])
        self.assertEqual(len(informe.fabrican), 1, informe.fabrican)

    def test_y_NO_muerde_una_palabra_que_acaba_en_tx(self):
        """Un guardia con falsos positivos se acaba apagando."""
        from tools.auditar_marcos import analizar_fuentes

        fuente = 'def f(n):\n    return f"ctx{n}" + f"latex{n}"\n'
        informe = analizar_fuentes({"falso.py": fuente}, [])
        self.assertEqual(informe.fabrican, [])


if __name__ == "__main__":
    unittest.main()
