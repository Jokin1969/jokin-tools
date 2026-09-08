"""Los avisos de la seleccion etiquetaban `3utr:` una coordenada del TRANSCRITO.

Sexta vez de la familia del marco (`3utr:1784`, `3utr:1185`, `3utr:1398`, `3utr:1856`,
`selection.report.frame`), y la primera EN UN AVISO que se lee justo antes de decidir
que se sintetiza. El invariante de rango de `coords` NO puede cazarla y no por descuido:
`3utr:1398` sobre un 3'UTR murino de 1242 nt es una posicion IMPOSIBLE, pero el techo se
deriva del 3'UTR mas largo que conoce el proyecto —1606, que lo pone el humano— asi que
1398 cabe y no aborta. Es literalmente el corolario escrito del principio nº 9: el
invariante caza lo imposible, no lo equivocado.

Lo que se leia: «3utr:1398 y 3utr:1967 comparten el nucleo TACTAA». Ninguno de los dos
esta en el panel — son `tx:1398` y `tx:1967`, o sea `3utr:449` y `3utr:1018`. Quien lo
lee busca dos candidatos que no existen, y el aviso trata justo del eje que el espaciado
NO ve, o sea el que nadie puede recalcular de cabeza.
"""

import unittest
from pathlib import Path

from shmir_design import coords, presentation, reference, resolve
from shmir_design.coords import Frame

RAIZ = Path(__file__).resolve().parents[1]
FASTA = RAIZ / "data" / "reference" / "NM_011170.3.fa"
GB = RAIZ / "data" / "reference" / "NM_011170.3.gb"


def _corrida():
    _, secuencia = reference.parse_fasta_payload(
        FASTA.read_text(encoding="utf-8"), source=FASTA.name
    )
    anatomia = resolve.resolve_anatomy(name="raton", sequence=secuencia, genbank=GB)
    return presentation.page_run(
        species="raton", sequence=secuencia, anatomy=anatomia
    )


@unittest.skipUnless(FASTA.is_file() and GB.is_file(), "faltan los fixtures del raton")
class TestElAvisoLlevaElMarcoDeLoTILADO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.avisos = presentation.selection_warnings(
            cls.corrida.tiling, cls.corrida.selection
        )

    def test_hay_al_menos_un_aviso_que_mirar(self):
        """Sin esto, «ninguno etiqueta mal» y «no hay ninguno» dan el mismo verde."""
        self.assertTrue(self.avisos)

    def test_ninguno_etiqueta_3utr_una_coordenada_del_transcrito(self):
        # Lo tilado es el transcrito entero, asi que el marco es `tx`. Una etiqueta
        # `3utr:` aqui no es una posicion mal escrita: es OTRA posicion.
        self.assertEqual(coords.frame_of(self.corrida.selection.anatomy), Frame.TX)
        for aviso in self.avisos:
            self.assertNotIn("3utr:1", aviso["texto"].split("CONSECUENCIA")[0])

    def test_las_etiquetas_son_las_que_derivaria_coords(self):
        elegidos = sorted(c.start for c in self.corrida.selection.selection.chosen)
        marco = coords.frame_of(self.corrida.selection.anatomy)
        texto = " ".join(a["texto"] for a in self.avisos)
        nombrados = [e for e in elegidos if coords.label(e, marco) in texto]
        self.assertTrue(nombrados, "ningun candidato del panel sale nombrado")
        for inicio in nombrados:
            self.assertIn(coords.label(inicio, marco), texto)

    def test_y_el_par_que_denuncia_es_el_del_nucleo_compartido(self):
        """`3utr:449` y `3utr:1018` comparten el nucleo TACTAA — el caso que la propia
        nota del multiplexado pone de ejemplo. Se comprueba el HECHO, no la redaccion."""
        marco = coords.frame_of(self.corrida.selection.anatomy)
        texto = " ".join(a["texto"] for a in self.avisos)
        for utr3 in (449, 1018):
            self.assertIn(coords.label(utr3 + 949, marco), texto)


@unittest.skipUnless(FASTA.is_file() and GB.is_file(), "faltan los fixtures del raton")
class TestConUnTiladoDEL_3UTR_el_marco_es_el_otro(unittest.TestCase):
    """El control por el otro lado: tilando el 3'UTR pelado, `3utr:` SI es lo correcto.

    Sin esto, un arreglo que escribiera `tx:` a pelo pasaria el test de arriba y estaria
    igual de mal — seria el mismo fallo con la otra etiqueta.
    """

    def test_ahi_las_etiquetas_son_del_3utr(self):
        _, secuencia = reference.parse_fasta_payload(
            FASTA.read_text(encoding="utf-8"), source=FASTA.name
        )
        anatomia = resolve.resolve_anatomy(name="raton", sequence=secuencia, genbank=GB)
        utr3 = secuencia[anatomia.cds[1] :]  # el 3'UTR empieza justo tras el CDS
        corrida = presentation.page_run(
            species="raton",
            sequence=utr3,
            anatomy=resolve.resolve_anatomy(
                name="raton", sequence=utr3, whole_is_utr3=True,
                hint="el 3'UTR recortado del propio transcrito, para este control",
            ),
        )
        self.assertEqual(coords.frame_of(corrida.selection.anatomy), Frame.UTR3)
        avisos = presentation.selection_warnings(corrida.tiling, corrida.selection)
        self.assertTrue(avisos)
        texto = " ".join(a["texto"] for a in avisos)
        self.assertIn("3utr:", texto)
        self.assertNotIn("tx:", texto)


if __name__ == "__main__":
    unittest.main()
