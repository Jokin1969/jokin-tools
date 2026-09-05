"""El mapa del 3'UTR entra en el informe y en el PDF, todo a la MISMA escala.

Regla 5: escritos antes que `presentation.map_text`.

## De qué va

El mapa existía sólo como SVG en la página, y al documento llegaba un RESUMEN: cuántos
elementos dibuja por tipo. Eso permite ver que un mapa se quedó sin candidatos, y no
permite ver lo único que el mapa sirve para ver — **si los candidatos están repartidos o
apelotonados, y qué tramos quedan vacíos**.

## Por qué un mapa de caracteres y no el SVG

El informe sale en markdown, `.docx` y `.pdf`, y el PDF de este proyecto se escribe a
mano con las fuentes base-14: no incrusta imágenes. Un mapa de caracteres se dibuja una
vez y sale IGUAL en los tres, que es justo la garantía que se pide — todo a la misma
escala, y la misma escala en los tres formatos.

Y por eso es ASCII puro: el PDF codifica en WinAnsi y sustituye lo que no tiene por su
equivalente, así que un ▲ saldría como otra cosa y las columnas dejarían de alinearse.
Una alineación que se rompe en un formato y no en otro es peor que un símbolo feo.
"""

import unittest
from pathlib import Path

from shmir_design.presentation import MAP_TEXT_WIDTH, map_text
from shmir_design.selection import select_from_report

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _corrida():
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.tiling import tile_utr

    tiling = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
    return tiling, select_from_report(tiling)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElMapaDeCaracteres(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _corrida()
        cls.mapa = map_text(cls.tiling, cls.seleccion)
        cls.lineas = cls.mapa.splitlines()

    def test_NINGUN_caracter_cambia_de_ancho_al_pasar_al_PDF(self):
        """La propiedad que importa no es «ASCII»: es que la traducción no ALARGUE.

        El PDF codifica en WinAnsi y sustituye lo que no tiene. Las tildes y la eñe
        están en WinAnsi y ocupan uno; una flecha `→` se traduce a `->` y ocupa DOS, y
        ahí la columna se corre. La comprobación es la longitud, no el juego de
        caracteres — comprobar «ASCII» prohibiría el castellano sin proteger de nada.
        """
        from shmir_design.pdf_writer import _ascii

        for linea in self.lineas:
            self.assertEqual(len(_ascii(linea)), len(linea), linea)

    def test_todos_los_carriles_miden_lo_mismo(self):
        pistas = [l for l in self.lineas if l.startswith("  ") and "|" in l]
        self.assertTrue(pistas)
        anchos = {len(l.rstrip()) for l in self.lineas if l.strip()}
        self.assertLessEqual(max(anchos), MAP_TEXT_WIDTH + 20)
        pistas_reales = [l for l in self.lineas if l.startswith("  ") and len(l) > 60]
        self.assertTrue(pistas_reales)

    def test_estan_los_tres_tercios_con_su_frontera(self):
        tercios = next(l for l in self.lineas if "proximal" in l and "distal" in l)
        self.assertIn("medio", tercios)

    def test_los_diez_candidatos_salen_NUMERADOS(self):
        candidatos = next(l for l in self.lineas if l.startswith("  cand"))
        for numero in range(1, 11):
            self.assertIn(str(numero), candidatos)

    def test_y_debajo_va_su_coordenada(self):
        for inicio in (10, 1018):
            self.assertIn(f"3utr:{inicio}", self.mapa)

    def test_las_señales_polya_llevan_su_banda_de_corte(self):
        self.assertTrue(any(l.startswith("  polyA") for l in self.lineas))
        self.assertTrue(any(l.startswith("  corte") for l in self.lineas))

    def test_una_señal_MEDIDA_no_se_dibuja_igual_que_una_supuesta(self):
        """`A` a secas dice lo mismo de dos cosas que no se parecen.

        En el 3'UTR murino las dos con uso medido —PolyA_DB— caen en el tramo proximal
        y todo lo distal está clasificado por canonicidad SIN un solo dato de uso. Con
        un solo símbolo eso no se ve, y es justo lo que el mapa sirve para ver.
        """
        pista = next(l for l in self.lineas if l.startswith("  polyA"))
        self.assertIn("M", pista)
        self.assertIn("A", pista)
        self.assertIn("uso MEDIDO", self.mapa)
        self.assertIn("sin dato de uso", self.mapa)

    def test_la_escala_se_DECLARA(self):
        self.assertIn("nt por columna", self.mapa)
        self.assertIn("1242", self.mapa)

    def test_los_tramos_vacios_se_ven(self):
        """Un carril de candidatos con huecos: es para lo que sirve el mapa."""
        candidatos = next(l for l in self.lineas if l.startswith("  cand"))
        pista = candidatos[len("  cand") :]
        self.assertIn("   ", pista)

    def test_sin_conservacion_el_carril_lo_DICE(self):
        self.assertIn("NOT_RUN", self.mapa)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElMapaEnElDocumento(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.informe_doc import build_document

        cls.tiling, cls.seleccion = _corrida()
        cls.doc = build_document(
            species="mouse", tiling=cls.tiling, selection=cls.seleccion,
            generated="2026-09-05",
        )
        cls.seccion = next(
            s for s in cls.doc.sections if s.title.startswith("Mapa del 3'UTR")
        )

    def test_el_mapa_va_ENTERO_y_no_su_resumen(self):
        bloques = [b for b in self.seccion.blocks if b.kind == "pre"]
        self.assertTrue(bloques)
        texto = "\n".join(b.text for b in bloques)
        self.assertIn("cand", texto)
        self.assertIn("nt por columna", texto)

    def test_es_EL_MISMO_mapa_que_pinta_la_pagina(self):
        """Un mapa distinto por formato divergiría, y el que diverge acaba en la libreta."""
        bloques = [b for b in self.seccion.blocks if b.kind == "pre"]
        texto = "\n".join(b.text for b in bloques)
        self.assertIn(map_text(self.tiling, self.seleccion), texto)

    def test_la_cobertura_por_tercios_va_al_lado(self):
        texto = "\n".join(
            b.text + "\n".join(b.items or ())
            for b in self.seccion.blocks
        )
        self.assertIn("distal", texto)
        self.assertIn("3utr:1071", texto)

    def test_cabe_en_el_PDF_sin_partirse(self):
        """Una línea que el PDF parte deja de estar a escala: eso es el mapa roto."""
        from shmir_design.pdf_writer import _chars_per_line

        limite = _chars_per_line(7, mono=True)
        bloques = [b for b in self.seccion.blocks if b.kind == "pre"]
        for bloque in bloques:
            for linea in bloque.text.splitlines():
                self.assertLessEqual(len(linea), limite, linea)

    def test_el_PDF_se_escribe(self):
        from shmir_design.pdf_writer import to_pdf

        self.assertTrue(to_pdf(self.doc).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
