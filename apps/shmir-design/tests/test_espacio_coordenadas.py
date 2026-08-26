"""Toda posicion impresa lleva su espacio de coordenadas PEGADO.

Regla 5: escritos antes de `coords.py`.

El fallo que lo motiva no dio ningun error: la linea de inmunes elegibles imprimio un
«1018» que era el 69 del 3'UTR, justo al lado de un candidato elegido que se llama 1018.
Nadie lo habria visto. Es el mismo fallo que la longitud sin md5 —«referencia 1246 nt»
parece razonable— y se cierra igual: la etiqueta va PEGADA al numero, inline, no en la
cabecera de la tabla ni en una nota al pie.

Un entero desnudo no identifica nada. `tx:1018` y `3utr:1018` son dos sitios distintos.
"""

import re
import unittest
from pathlib import Path

from shmir_design.coords import (
    Frame,
    Position,
    frame_of,
    label,
    parse,
    span,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"
GENBANK = DIR / "NM_011170.3.gb"

#: Un numero pegado a su espacio. Lo que NO vale es el entero suelto.
ETIQUETADA = re.compile(r"(?:3utr|tx):\d+")


class TestLaPosicionNoSePuedeEmitirDesnuda(unittest.TestCase):

    def test_se_formatea_con_el_espacio_delante(self):
        self.assertEqual(str(Position(1018, Frame.UTR3)), "3utr:1018")

    def test_en_un_f_string_tambien(self):
        p = Position(1967, Frame.TX)
        self.assertEqual(f"{p}", "tx:1967")

    def test_el_mismo_entero_en_dos_espacios_no_se_confunde(self):
        # El caso real: el 1018 del transcrito es el 69 del 3'UTR, y el 1018 del 3'UTR
        # es otro sitio. Impresos, tienen que verse distintos.
        self.assertNotEqual(
            str(Position(1018, Frame.TX)), str(Position(1018, Frame.UTR3))
        )

    def test_el_espacio_es_obligatorio(self):
        with self.assertRaises(TypeError):
            Position(1018)

    def test_un_espacio_inventado_aborta(self):
        with self.assertRaises(ValueError):
            Position(1018, "cromosoma")

    def test_una_posicion_menor_que_1_aborta(self):
        # Las coordenadas del proyecto son 1-based: un 0 es un error de conversion.
        with self.assertRaises(ValueError):
            Position(0, Frame.UTR3)

    def test_el_valor_sigue_disponible_para_calcular(self):
        self.assertEqual(Position(1018, Frame.UTR3).value + 21, 1039)

    def test_label_es_el_atajo_de_una_posicion_suelta(self):
        self.assertEqual(label(288, Frame.UTR3), "3utr:288")

    def test_span_etiqueta_el_intervalo_UNA_vez(self):
        # `3utr:158-277`, no `3utr:158-3utr:277`: se lee peor y ocupa el doble.
        self.assertEqual(span(158, 277, Frame.UTR3), "3utr:158-277")

    def test_span_al_reves_aborta(self):
        with self.assertRaises(ValueError):
            span(277, 158, Frame.UTR3)

    def test_vacio_sigue_siendo_vacio(self):
        # Una posicion que no existe va vacia, nunca "3utr:" ni "3utr:0".
        self.assertEqual(label(None, Frame.UTR3), "")


class TestSePuedeLeerDeVuelta(unittest.TestCase):
    """La etiqueta no es decoracion: una celda etiquetada se vuelve a leer sin adivinar."""

    def test_ida_y_vuelta(self):
        self.assertEqual(parse("3utr:449"), Position(449, Frame.UTR3))

    def test_un_entero_desnudo_no_se_acepta(self):
        with self.assertRaises(ValueError):
            parse("449")

    def test_un_espacio_desconocido_aborta(self):
        with self.assertRaises(ValueError):
            parse("cromosoma:449")


class TestElEspacioSaleDeLaAnatomia(unittest.TestCase):
    """No se elige a mano: si lo tilado empieza antes del 3'UTR, el marco es el del
    transcrito. Es la misma cuenta del desfase, en un solo sitio."""

    def test_si_todo_es_3utr_el_marco_es_3utr(self):
        from shmir_design.anatomy import Anatomy, RegionSource

        anat = Anatomy.whole_is_utr3(1242, source=RegionSource.TODO_3UTR_DECLARADO)
        self.assertIs(frame_of(anat), Frame.UTR3)

    def test_con_un_mRNA_entero_el_marco_es_el_del_transcrito(self):
        from shmir_design.resolve import resolve_anatomy

        if not (RATON.is_file() and GENBANK.is_file()):
            self.skipTest("NOT_RUN: faltan los ficheros de NM_011170.3")
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
        secuencia = normalize_sequence(bruta, name="NM_011170.3")
        anat = resolve_anatomy(name="raton", sequence=secuencia, genbank=GENBANK)
        self.assertIs(frame_of(anat), Frame.TX)

    def test_sin_anatomia_no_se_adivina(self):
        with self.assertRaises(ValueError):
            frame_of(None)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLasSalidasDeVerdadLlevanElEspacio(unittest.TestCase):
    """Sobre la corrida murina, no sobre un ejemplo."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.outputs import text_report, tsv_selected
        from shmir_design.polya import normalize_sequence
        from shmir_design.comparative import comparative_tsv
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
        cls.utr3 = normalize_sequence(bruta, name="NM_011170.3")[949:]
        cls.tiling = tile_utr(cls.utr3)
        cls.seleccion = select_from_report(
            cls.tiling, SelectionConfig(n_candidates=6)
        )
        cls.informe = text_report(
            species="raton", tiling=cls.tiling, selection=cls.seleccion,
            scaffold=SGEP_SCAFFOLD,
        )
        cls.comparativa = comparative_tsv(cls.seleccion, SGEP_SCAFFOLD, anatomy=cls.tiling.anatomy)
        cls.seleccionados = tsv_selected(cls.seleccion, species="raton")

    def _columna(self, tsv: str, nombre: str) -> list[str]:
        filas = [l for l in tsv.splitlines() if l and not l.startswith("#")]
        cabecera = filas[0].split("\t")
        i = cabecera.index(nombre)
        return [f.split("\t")[i] for f in filas[1:]]

    def test_la_columna_inicio_3utr_va_etiquetada(self):
        for celda in self._columna(self.comparativa, "inicio_3utr"):
            with self.subTest(celda):
                self.assertRegex(celda, r"^3utr:\d+$")

    def test_la_columna_inicio_transcrito_va_etiquetada(self):
        for celda in self._columna(self.comparativa, "inicio_transcrito"):
            with self.subTest(celda):
                self.assertRegex(celda, r"^(3utr|tx):\d+$")

    def test_el_hexamero_de_polya_va_en_el_marco_de_lo_tilado_y_lo_dice(self):
        for celda in self._columna(self.comparativa, "polyA_hexamero_pos"):
            if celda:
                with self.subTest(celda):
                    self.assertRegex(celda, r"^(3utr|tx):\d+$")

    def test_el_tsv_de_seleccionados_tambien(self):
        for celda in self._columna(self.seleccionados, "inicio"):
            with self.subTest(celda):
                self.assertRegex(celda, r"^(3utr|tx):\d+$")

    def test_el_bloque_de_polya_del_informe_no_deja_enteros_sueltos(self):
        bloque = self.informe.split("── Riesgo de polyA")[1].split("── Que se ha")[0]
        for linea in bloque.splitlines():
            if "inmunes tambien" in linea or "con TECHO" in linea:
                with self.subTest(linea.strip()[:50]):
                    self.assertTrue(
                        ETIQUETADA.search(linea),
                        f"posiciones sin espacio de coordenadas: {linea!r}",
                    )

    def test_el_experimento_da_los_amplicones_etiquetados(self):
        bloque = self.informe.split("EXPERIMENTO QUE RESUELVE")[1]
        for linea in bloque.splitlines():
            if linea.strip().startswith(("proximal:", "distal:")):
                with self.subTest(linea.strip()[:40]):
                    self.assertRegex(linea, r"(3utr|tx):\d+-\d+")


if __name__ == "__main__":
    unittest.main()
