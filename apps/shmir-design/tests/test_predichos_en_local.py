"""En una corrida LOCAL, «predichos: sí» no es una afirmación que se pueda sostener.

**La opcion fuerte, decidida por el responsable del proyecto**: en local sale `NOT_RUN`
con el motivo escrito. Una nota derivada dejaria el campo AFIRMANDO algo que la corrida no
puede cumplir, y eso es un `PASS` falso de la misma familia que un `provided=True` con
secuencia vacia.

**El riesgo concreto, con sus palabras**: dos corridas, una remota y otra local, las dos
registradas como «predichos: sí», comparadas dentro de un año como si fueran equivalentes.

**Por que pasa.** `include_predicted` solo tiene efecto dentro de `-entrez_query`, y desde
la errata nº 40 ese filtro va SOLO con `-remote`. En local el ajuste no aparece en la
orden: no filtra nada, ni a favor ni en contra. Lo que decide si hay predichos en el
resultado es LA BASE — y eso no lo sabe este campo.

**Y el veredicto declara el universo contra el que se comprobo**, porque es lo que hace
interpretable un cero: «0 aciertos» contra 59.078 transcritos curados sin predichos no
dice lo mismo que «0 aciertos» contra RefSeq entera.
"""

import unittest

from shmir_design import blast
from shmir_design.filters import FilterState


class TestEnLOCALelCAMPOnoAFIRMA(unittest.TestCase):

    def test_en_local_el_estado_de_los_predichos_es_NOT_RUN(self):
        params = blast.BlastParams.for_species("raton")
        self.assertIs(params.predicted_state(), FilterState.NOT_RUN)

    def test_y_el_motivo_dice_POR_QUE_no_por_que_falte_un_fichero(self):
        motivo = blast.BlastParams.for_species("raton").predicted_reason()
        self.assertIn("-entrez_query", motivo)
        self.assertIn("base", motivo.lower())

    def test_en_REMOTA_si_afirma(self):
        params = blast.BlastParams.for_species("raton", remote=True)
        self.assertIs(params.predicted_state(), FilterState.PASS)

    def test_y_da_igual_lo_que_marque_la_casilla_en_local(self):
        """Es lo que hace falso el campo: en local NO cambia nada de la orden."""
        con = blast.BlastParams.for_species("raton", include_predicted=True)
        sin = blast.BlastParams.for_species("raton", include_predicted=False)
        ruta = "q.fa"
        self.assertEqual(con.command(query_path=ruta), sin.command(query_path=ruta))
        self.assertIs(con.predicted_state(), FilterState.NOT_RUN)
        self.assertIs(sin.predicted_state(), FilterState.NOT_RUN)


class TestElVEREDICTOdeclaraElUNIVERSO(unittest.TestCase):
    """«0 aciertos» no significa lo mismo contra dos catalogos distintos."""

    def test_el_veredicto_nombra_la_base_y_su_version(self):
        from shmir_design.blast_store import BlastDatabase, BlastRun
        from shmir_design.presentation import query_name

        consulta = query_name("raton", 200, "guia")
        corrida = BlastRun.create(
            run_id="r1", date="2026-09-01", uploaded_by="responsable",
            params=blast.BlastParams.for_species("raton"),
            database=BlastDatabase(
                name="refseq_mouse_curated", version="2026-09-01", md5="a" * 32,
                remote=False,
            ),
            query=blast.QueryFasta.from_records(((consulta, "TTATATTCTTATTGGCCCGGTG"),)),
            raw=f"{consulta}\tNM_1\t100.000\t22\t0\t0\t1\t22\t1\t22\t1e-05\t44.1\n",
        )
        motivo = corrida.verdict(consulta).reason
        self.assertIn("refseq_mouse_curated", motivo)

    def test_y_dice_que_los_PREDICHOS_dependen_de_la_base(self):
        # Sin esta frase, un cero contra un catalogo curado se lee como «no hay
        # off-targets contra predichos», que es el «Alu 0 %» otra vez.
        self.assertIn("predich", blast.UNIVERSE_NOTE.lower())


if __name__ == "__main__":
    unittest.main()
