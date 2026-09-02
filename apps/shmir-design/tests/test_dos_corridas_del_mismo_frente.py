"""Dos corridas del mismo frente: cual MANDA, y por que no es «la ultima» ni «la mejor».

**El caso**, planteado por el responsable del proyecto antes de que pasara: se sube una
corrida buena y despues, por probar, una marcada `-remote`. «Nada se sobrescribe» y la
ficha enseña la ULTIMA, asi que una corrida mala posterior degradaria un frente cerrado.

**Ninguna de las tres opciones obvias vale**:

  - *la ultima manda* — una exploracion posterior tumba un veredicto ganado con una base
    local de decenas de GB;
  - *la mejor manda* — esconde una FAIL posterior, que es justo la que hay que ver: si se
    repite la corrida contra una base mejor y ahora falla, el candidato falla. Eso seria
    un `PASS` con letra pequeña;
  - *borrar la anterior* — rompe el log append-only, que es la unica memoria de por que
    se volvio a correr.

**LA REGLA, y sale de que `NO_CIERRA` no es un veredicto peor: es NINGUN veredicto.** Una
corrida que no puede cerrar el frente —`-remote`, parametros tocados, md5 que no cuadra—
**no es evidencia sobre este candidato**. No lo empeora ni lo mejora: no habla de el.

  1. manda la ULTIMA corrida que PUEDE dar veredicto — aunque despues haya exploraciones;
  2. entre las que pueden, la ultima SIEMPRE, aunque sea peor que la anterior: repetir
     contra una base mejor y sacar FAIL tiene que degradar;
  3. si NINGUNA puede, se enseña la ultima con su `NO_CIERRA` y su motivo;
  4. y si habia exploraciones DESPUES de la que manda, **se dice** — callarlo dejaria
     creyendo que la ultima que se subio es la que cuenta.
"""

import unittest

from shmir_design import blast
from shmir_design.blast_store import BlastDatabase, BlastRun, BlastStore
from shmir_design.filters import FilterState
from shmir_design.presentation import query_name
from shmir_design.specificity import target_accessions

CONSULTA = query_name("raton", 200, "guia")
GUIA = "TTATATTCTTATTGGCCCGGTG"


#: Los sujetos se PIDEN a la tabla de la diana: una corrida limpia acierta contra su
#: propio blanco y contra nada mas, y escribir aqui un `NM_1` cualquiera era codificar el
#: supuesto que la errata nº 56 quito de en medio — con el umbral viejo (`> 1`) un solo
#: acierto pasaba fuese contra lo que fuese.
DIANA = target_accessions("raton")[0]


def _corrida(run_id, *, fecha="2026-09-01", remota=False, hits=1, fuera=0):
    """`hits` aciertos contra la DIANA y `fuera` contra otros transcritos.

    En ANTISENTIDO (`send < sstart`), que es como BLAST devuelve el acierto de una guia
    contra un mRNA: el mensajero lleva el complemento inverso de la sonda. Estaban
    escritos en SENTIDO — una orientacion que esa corrida no puede producir.
    """
    sujetos = [DIANA] * hits + [f"NM_offtarget_{i}" for i in range(fuera)]
    crudo = "".join(
        f"{CONSULTA}\t{s}\t100.000\t22\t0\t0\t1\t22\t1191\t1170\t1e-05\t44.1\n"
        for s in sujetos
    )
    return BlastRun.create(
        run_id=run_id, date=fecha, uploaded_by="responsable",
        params=blast.BlastParams.for_species("raton", remote=remota),
        database=BlastDatabase(
            name="refseq_mouse", version="v1", md5="a" * 32, remote=remota,
        ),
        query=blast.QueryFasta.from_records(((CONSULTA, GUIA),)),
        raw=crudo,
    )


class TestUnaEXPLORACIONposteriorNOdegrada(unittest.TestCase):
    """El caso que motiva la regla."""

    def setUp(self):
        self.almacen = BlastStore()
        self.almacen.add(_corrida("buena", fecha="2026-09-01"))
        self.almacen.add(_corrida("exploracion", fecha="2026-09-02", remota=True))

    def test_el_frente_SIGUE_cerrado(self):
        resultado = self.almacen.verdict_for(CONSULTA, species="mouse")
        self.assertIs(resultado.state, FilterState.PASS)

    def test_y_manda_la_corrida_BUENA_por_su_id(self):
        self.assertIn("buena", self.almacen.verdict_for(CONSULTA, species="mouse").reason)

    def test_pero_la_exploracion_posterior_NO_se_calla(self):
        # Sin esto, quien subio la remota se queda creyendo que es la que cuenta.
        motivo = self.almacen.verdict_for(CONSULTA, species="mouse").reason
        self.assertIn("exploracion", motivo)


class TestEntreLasQuePUEDEN_mandaLaULTIMA(unittest.TestCase):
    """Aunque sea PEOR. «La mejor manda» seria un PASS con letra pequeña."""

    def test_una_FAIL_posterior_DEGRADA_un_PASS(self):
        almacen = BlastStore()
        almacen.add(_corrida("limpia", fecha="2026-09-01", hits=1))
        almacen.add(_corrida("sucia", fecha="2026-09-02", hits=1, fuera=4))
        resultado = almacen.verdict_for(CONSULTA, species="mouse")
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("sucia", resultado.reason)


class TestSiNINGUNApuede(unittest.TestCase):

    def test_se_enseña_la_ultima_con_su_motivo(self):
        almacen = BlastStore()
        almacen.add(_corrida("r1", remota=True))
        resultado = almacen.verdict_for(CONSULTA, species="mouse")
        self.assertIs(resultado.state, FilterState.NO_CIERRA)
        self.assertIn("REPITIENDO", resultado.reason)


class TestNADAseBORRA(unittest.TestCase):
    """La regla decide cual MANDA, no cual se guarda. El log no se toca."""

    def test_las_dos_siguen_en_el_historial(self):
        almacen = BlastStore()
        almacen.add(_corrida("buena"))
        almacen.add(_corrida("exploracion", fecha="2026-09-02", remota=True))
        self.assertEqual(len(almacen.history(CONSULTA)), 2)


if __name__ == "__main__":
    unittest.main()
