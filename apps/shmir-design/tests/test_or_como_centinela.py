"""`or` confunde un valor legítimo con la ausencia de valor.

Regla 5: escrito antes.

Sale de la errata nº 16 —`spacer5 or PIECES["espaciador5"]`, donde pedir CERO espaciador
devolvía los 20 nt estándar— y de barrer el paquete entero buscando la misma forma. De
73 usos de `x or defecto`, la mayoría son correctos: rellenar un texto vacío con
«sin fecha» o «SIN REGISTRAR» es exactamente lo que se quiere. Los que muerden son
aquéllos en los que el valor falso **significa algo** y el `or` lo borra.

Este proyecto ya había hecho bien esa distinción dos veces —`divergent_positions=None`
frente a `frozenset()`, y `species_prefix` `None` frente a `""`— así que lo que se
encontró no es un descuido de concepto: es la distinción **hecha en el dato y deshecha
al imprimirlo**.

Los tres que quedaban:

1. `inicio_3utr or window.start` (dos sitios). `inicio_3utr` es `None` cuando la ventana
   **no cae en el 3'UTR** —una del ORF entra con `--cuota-region`— y el `or` la sustituía
   por la coordenada de LO TILADO, que acto seguido se etiquetaba `Frame.UTR3`. Es la
   familia que este proyecto ya ha cazado cuatro veces, por quinta vez.
2. `species_prefix or 'de todas las especies del fichero'` en la TASA BASE. `None` es
   «nadie lo ha declarado» y `""` es «todas, elegido a propósito»: son dos cosas, está
   escrito que lo son, y aquí las dos salían como la segunda.
3. Lo mismo en los controles de la carga de off-targets.
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource


class TestLaPosicionFueraDel3UTR(unittest.TestCase):
    """`None` = fuera del 3'UTR. No es una posición que falte: es que no la hay."""

    def setUp(self):
        # CDS 185..949 sobre 2191 nt: la anatomia del transcrito murino.
        self.anatomia = Anatomy(
            length=2191, utr3=(950, 2191), utr5=(1, 184), cds=(185, 949),
            source=RegionSource.ANOTACION_GENBANK,
        )

    def test_una_posicion_del_ORF_no_tiene_coordenada_de_3UTR(self):
        self.assertIsNone(self.anatomia.utr3_position(500))

    def test_y_la_primera_del_3UTR_es_1_nunca_0(self):
        # Si fuera 0, `or` la borraria tambien. Es 1-based, asi que el unico valor
        # falso posible es None — y None significa «fuera».
        self.assertEqual(self.anatomia.utr3_position(950), 1)


class TestNadieRellenaUnaPosicionAusente(unittest.TestCase):
    """Ni `outputs` ni `selection` sustituyen una posición que NO EXISTE por otra."""

    @staticmethod
    def _lineas(modulo: str) -> list[str]:
        from pathlib import Path

        ruta = Path(__file__).resolve().parents[1] / "shmir_design" / modulo
        return [
            f"{modulo}:{n}  {l.strip()}"
            for n, l in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1)
            if "inicio_3utr or " in l and not l.lstrip().startswith("#")
        ]

    def test_outputs(self):
        self.assertEqual(self._lineas("outputs.py"), [])

    def test_selection(self):
        self.assertEqual(self._lineas("selection.py"), [])


class TestLaTasaBaseDistingueLasDosCosas(unittest.TestCase):
    """`None` y `""` no pueden salir con el mismo texto: son dos corridas distintas."""

    def _tasa(self, prefijo):
        from shmir_design.seed_scan import BaseRate

        return BaseRate(
            matures=1988, distinct=1593, space=16384, window="2-8",
            species_prefix=prefijo,
        ).describe()

    def test_sin_declarar_lo_DICE(self):
        texto = self._tasa(None)
        self.assertIn("SIN DECLARAR", texto)

    def test_todas_a_proposito_dice_otra_cosa(self):
        texto = self._tasa("")
        self.assertIn("todas", texto.lower())
        self.assertNotIn("SIN DECLARAR", texto)

    def test_y_los_dos_textos_NO_son_el_mismo(self):
        self.assertNotEqual(self._tasa(None), self._tasa(""))


class TestLosControlesDeOfftargetIgual(unittest.TestCase):
    def _linea(self, prefijo):
        from shmir_design.offtarget import OfftargetParams

        return "\n".join(
            OfftargetParams(species_prefix=prefijo).describe()
        )

    def test_sin_declarar_lo_dice(self):
        self.assertIn("SIN DECLARAR", self._linea(None))

    def test_y_no_se_confunde_con_todas(self):
        self.assertNotEqual(self._linea(None), self._linea(""))


if __name__ == "__main__":
    unittest.main()
