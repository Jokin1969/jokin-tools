"""El fichero que la propia app manda descargar tiene que poder entrar.

**Reportado el 2026-09-02**, con el mensaje literal de la app:

    RECHAZADO — /data/shmir/reference/.transcriptoma_3utr.fa.subiendo: el identificador
    'mm39_ncbiRefSeqCurated_NR_189043.1_0' aparece dos veces; se aborta en vez de
    quedarse con una de las dos secuencias.

Ese identificador es EXACTAMENTE la forma que produce la ruta que la ficha de obtencion
manda seguir: UCSC Table Browser → «3' UTR Exons» da **un registro POR EXON**, asi que un
3'UTR troceado sale varias veces con el mismo accession y un sufijo `_0`, `_1`. La ficha
ademas dice expresamente que NO se filtren las isoformas a mano.

EL PROYECTO YA LO SABIA Y LO ARREGLO EN UN SOLO LADO. `offtarget.parse_fasta_pairs` lleva
escrito en su docstring que no reutiliza `seed_load.parse_fasta_records` «a proposito,
porque aquel ABORTA con un identificador repetido, y aqui repetirse es un caso legitimo y
esperado». El camino vivo —el panel de subida y `resources`— usaba el otro. Es la familia
de las erratas nº 56 y nº 57: dos implementaciones de lo mismo, y la del camino vivo es
la equivocada.

Y NO BASTABA CON ARREGLAR EL PANEL: `resources._transcriptoma` conecta el fichero con el
MISMO cargador, asi que aceptarlo solo en la subida habria movido el fallo al diseño — y
ahi es peor, porque el fichero ya figuraria como presente.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design import species as sp
from shmir_design.deposito import VALIDATORS
from shmir_design.seed_load import load_utr3_set, seed_load

#: La forma REAL, con el accession que venia en el mensaje: dos exones del mismo 3'UTR
#: —mismo identificador— y otro transcrito.
UCSC = (
    ">mm39_ncbiRefSeqCurated_NR_189043.1_0 range=chr1:1-22\n"
    "ACTAAACTAAACTAAACTAAAC\n"
    ">mm39_ncbiRefSeqCurated_NR_189043.1_0 range=chr1:99-120\n"
    "TTGGCCAATTGGCCAATTGGCC\n"
    ">mm39_ncbiRefSeqCurated_NM_000001.1_0 range=chr2:1-22\n"
    "GGCCTTAAGGCCTTAAGGCCTT\n"
)


def _fichero(texto=UCSC):
    ruta = Path(tempfile.mkdtemp()) / "transcriptoma_3utr.fa"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


class TestElFicheroDeUCSC_ENTRA(unittest.TestCase):

    def test_el_cargador_lo_ACEPTA(self):
        self.assertEqual(len(load_utr3_set(_fichero(), version="x").records), 3)

    def test_y_el_VALIDADOR_del_panel_tambien(self):
        # Es el mismo cargador a proposito —«la validacion la hace el cargador de
        # verdad»—, y por eso arreglar uno solo no habria servido de nada.
        resultado = VALIDATORS["transcriptoma"](
            _fichero(),
            {"species": sp.resolve("mouse"), "filename": "transcriptoma_3utr.fa"},
        )
        self.assertEqual(len(resultado.records), 3)

    def test_NO_se_pierde_ninguna_secuencia(self):
        # El motivo del parser estricto era BUENO: un diccionario se habria quedado con
        # UNA de las dos y el conteo saldria corto sin avisar. Lo que estaba mal era la
        # salida elegida — se conservan las dos.
        secuencias = [s for _, s in load_utr3_set(_fichero(), version="x").records]
        self.assertIn("ACTAAACTAAACTAAACTAAAC", secuencias)
        self.assertIn("TTGGCCAATTGGCCAATTGGCC", secuencias)

    def test_y_el_CONTEO_recorre_los_dos_exones(self):
        # Si se hubiera quedado con uno, la carga saldria mas baja y eso PARECE una buena
        # noticia: es justo el modo de fallo que este proyecto persigue. Se compara
        # contra el MISMO fichero sin el segundo exon — la diferencia es lo que se
        # perdia.
        guia = "TTTAGTTTAGTTTAGTTTAGTT"
        completo = seed_load(guia, load_utr3_set(_fichero(), version="x"))
        sin_el_segundo = seed_load(
            guia,
            load_utr3_set(
                _fichero(
                    ">mm39_ncbiRefSeqCurated_NR_189043.1_0 range=chr1:1-22\n"
                    "ACTAAACTAAACTAAACTAAAC\n"
                    ">mm39_ncbiRefSeqCurated_NM_000001.1_0 range=chr2:1-22\n"
                    "GGCCTTAAGGCCTTAAGGCCTT\n"
                ),
                version="x",
            ),
        )
        self.assertEqual(len(completo.utrs.records), 3)
        self.assertEqual(len(sin_el_segundo.utrs.records), 2)
        self.assertGreaterEqual(
            sum(completo.counts.values()),
            sum(sin_el_segundo.counts.values()),
        )


class TestElCONTEO_INFLADO_se_DICE(unittest.TestCase):
    """Aceptar el repetido y callarlo seria el otro fallo, no el arreglo."""

    def test_la_procedencia_AVISA_de_los_identificadores_repetidos(self):
        self.assertIn(
            "repetid", load_utr3_set(_fichero(), version="x").provenance.lower()
        )

    def test_y_un_fichero_SIN_repetidos_no_avisa(self):
        # Control adversario: un aviso que sale siempre no distingue nada.
        limpio = (
            ">NM_1 range=chr1\nACTAAACTAAACTAAACTAAAC\n"
            ">NM_2 range=chr2\nGGCCTTAAGGCCTTAAGGCCTT\n"
        )
        self.assertNotIn(
            "repetid", load_utr3_set(_fichero(limpio), version="x").provenance.lower()
        )


class TestLoQueElArregloNoRELAJA(unittest.TestCase):

    def test_sin_ninguna_entrada_sigue_ABORTANDO(self):
        # Cero entradas y un conteo de cero no son lo mismo, y ese guardia se queda.
        with self.assertRaises(Exception):
            load_utr3_set(_fichero("\n\n"), version="x")


if __name__ == "__main__":
    unittest.main()
