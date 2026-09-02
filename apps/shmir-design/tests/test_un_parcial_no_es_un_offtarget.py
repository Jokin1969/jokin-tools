"""Un alineamiento PARCIAL de 13 nt no es un off-target, y un `mismatches` de 0 no dice
que sea perfecto: dice que es perfecto EN LOS 13 nt que alineo.

**Reportado con el `.tsv` contado a mano (2026-09-02)**, errata nº 57:

> De las 20 consultas, ninguna tiene un solo acierto fuerte fuera de Prnp. Los unicos
> hits con >=21 nt alineados y <=1 desapareamiento son, en las 20, `NM_011170.3` y
> `NM_001278256.1`. Todo lo demas son parciales de 10-16 nt.

EL CRITERIO MIRABA `mismatches` Y NO MIRABA LA LONGITUD. En `-outfmt 6` la columna
`mismatch` cuenta los desapareamientos **dentro del segmento alineado**, asi que un
parcial de 13 nt clavado trae `mismatches = 0` y entraba como acierto grave. La sonda
son 22 nt: 13 de 22 no es un off-target, es ruido de un `blastn-short` con `evalue 1000`.

POR QUE NO LO TENIA `filter_specificity`, que comparte el criterio: su escaner
(`_scan_one`) casa ventanas de EXACTAMENTE `len(pattern)`, asi que todos sus hits son de
longitud completa y la condicion se cumplia sola. BLAST devuelve alineamientos LOCALES.
Al llevar el criterio de un sitio al otro no viajo el supuesto que lo sostenia — que es
el mismo patron de la errata nº 56 y por eso el umbral se DERIVA de la sonda en vez de
escribirse.
"""

import unittest

from shmir_design import blast
from shmir_design.blast_store import BlastDatabase, BlastRun, BlastStore
from shmir_design.filters import FilterState
from shmir_design.presentation import query_name
from shmir_design.specificity import target_accessions

GUIA = query_name("mouse", 1018, "guia")
PASAJERA = query_name("mouse", 1018, "pasajera")
SONDA = "TTATATTCTTATTGGCCCGGTG"          # 22 nt
DIANA = target_accessions("mouse")


def _fila(consulta, sujeto, *, largo, mm, antisentido):
    """Una fila de `-outfmt 6`. La orientacion va en el SIGNO del intervalo del sujeto."""
    inicio, fin = (1000 + largo - 1, 1000) if antisentido else (1000, 1000 + largo - 1)
    return (
        f"{consulta}\t{sujeto}\t100.000\t{largo}\t{mm}\t0\t1\t{largo}\t"
        f"{inicio}\t{fin}\t1e-05\t44.1\n"
    )


def _corrida(crudo, *, consultas=((GUIA, SONDA),)):
    return BlastRun.create(
        run_id="r1", date="2026-09-02", uploaded_by="responsable",
        params=blast.BlastParams.for_species("mouse"),
        database=BlastDatabase(
            name="refseq_rna_mouse", version="2026-09", md5="a" * 32, remote=False,
        ),
        query=blast.QueryFasta.from_records(consultas),
        raw=crudo,
    )


def _almacen(crudo, **kwargs):
    almacen = BlastStore()
    almacen.add(_corrida(crudo, **kwargs))
    return almacen


#: La corrida REAL, con las cuentas del `.tsv`: la guia acierta ANTISENTIDO contra las dos
#: variantes de Prnp, y todo lo demas son parciales de 10-16 nt clavados.
def _corrida_real(consulta, *, antisentido_diana, antisentido_parciales):
    crudo = "".join(
        _fila(consulta, acc, largo=22, mm=0, antisentido=antisentido_diana)
        for acc in DIANA
    )
    crudo += "".join(
        _fila(consulta, f"NM_ruido_{i}", largo=largo, mm=0,
              antisentido=antisentido_parciales)
        for i, largo in enumerate((10, 13, 16, 12, 15), start=1)
    )
    return crudo


class TestUnPARCIALnoCUENTA(unittest.TestCase):
    """El caso reportado, con los diez del panel."""

    def test_la_guia_sale_PASS_con_los_parciales_ANTISENTIDO(self):
        # Era el `FAIL` de los diez: los parciales antisentido, con `mismatches = 0`,
        # entraban como aciertos graves.
        almacen = _almacen(_corrida_real(
            GUIA, antisentido_diana=True, antisentido_parciales=True,
        ))
        self.assertIs(
            almacen.verdict_for(GUIA, species="mouse").state, FilterState.PASS
        )

    def test_y_tambien_con_los_parciales_EN_SENTIDO(self):
        # El control que separa las dos causas: antes el veredicto CAMBIABA con la
        # orientacion de un ruido que no debia contar en ningun caso.
        almacen = _almacen(_corrida_real(
            GUIA, antisentido_diana=True, antisentido_parciales=False,
        ))
        self.assertIs(
            almacen.verdict_for(GUIA, species="mouse").state, FilterState.PASS
        )

    def test_un_acierto_LARGO_fuera_de_la_diana_SIGUE_dando_FAIL(self):
        # El control adversario. Si el umbral de longitud tapara tambien lo que si es un
        # off-target, el filtro dejaria de medir y sus PASS no dirian nada.
        crudo = _corrida_real(GUIA, antisentido_diana=True, antisentido_parciales=True)
        crudo += _fila(GUIA, "NM_deverdad", largo=22, mm=1, antisentido=True)
        resultado = _almacen(crudo).verdict_for(GUIA, species="mouse")
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("NM_deverdad", resultado.reason)

    def test_el_umbral_se_DERIVA_de_la_sonda_y_no_va_escrito(self):
        # Con una sonda de 30 nt, un alineamiento de 22 pasa a ser parcial. Un `21`
        # escrito seria el `> 1` otra vez: un numero con un supuesto dentro (que la sonda
        # mide 22) que nadie escribio.
        sonda = "TTATATTCTTATTGGCCCGGTGAACCTTGG"       # 30 nt
        crudo = "".join(
            _fila(GUIA, acc, largo=30, mm=0, antisentido=True) for acc in DIANA
        )
        crudo += _fila(GUIA, "NM_parcial_para_30", largo=22, mm=0, antisentido=True)
        almacen = _almacen(crudo, consultas=((GUIA, sonda),))
        self.assertIs(
            almacen.verdict_for(GUIA, species="mouse").state, FilterState.PASS
        )

    def test_y_el_motivo_DICE_cuantos_parciales_descarto(self):
        # Callarlos los haria indistinguibles de «no habia nada»: es el «Alu 0 %».
        motivo = _almacen(_corrida_real(
            GUIA, antisentido_diana=True, antisentido_parciales=True,
        )).verdict_for(GUIA, species="mouse").reason
        self.assertIn("parcial", motivo.lower())
        self.assertIn("5", motivo)


class TestLaORIENTACIONesUnaFIRMA_noUnFiltro(unittest.TestCase):
    """La correccion estructural: guia → antisentido, pasajera → sentido.

    Descartar los hits en sentido copiando el criterio del otro escaner tiraba, en la
    PASAJERA, su acierto legitimo contra la propia diana — y con el la exencion, asi que
    disparaba «ningun acierto contra la propia diana» en las diez. La orientacion no
    filtra: DICE QUE HEBRA ES, y eso da un invariante mas fuerte.
    """

    def test_la_PASAJERA_acierta_a_su_diana_EN_SENTIDO_y_queda_eximida(self):
        almacen = _almacen(
            _corrida_real(PASAJERA, antisentido_diana=False,
                          antisentido_parciales=False),
            consultas=((PASAJERA, SONDA),),
        )
        resultado = almacen.verdict_for(PASAJERA, species="mouse")
        self.assertIs(resultado.state, FilterState.PASS)
        self.assertIn("Eximidos por ser la propia diana", resultado.reason)

    def test_y_NO_dispara_lo_de_ningun_acierto_contra_la_diana(self):
        motivo = _almacen(
            _corrida_real(PASAJERA, antisentido_diana=False,
                          antisentido_parciales=False),
            consultas=((PASAJERA, SONDA),),
        ).verdict_for(PASAJERA, species="mouse").reason
        self.assertNotIn("NINGÚN acierto contra su propia diana", motivo)

    def test_una_GUIA_que_acierta_a_su_diana_EN_SENTIDO_esta_MAL_MONTADA(self):
        # El invariante, que es lo que la orientacion si compra: una guia es antisentido
        # a su diana POR DEFINICION. Si su acierto sale en sentido, lo que hay es guia y
        # pasajera intercambiadas — y eso no lo detecta ningun otro guardia.
        motivo = _almacen(_corrida_real(
            GUIA, antisentido_diana=False, antisentido_parciales=False,
        )).verdict_for(GUIA, species="mouse").reason
        self.assertIn("ORIENTACIÓN", motivo.upper())
        self.assertIn("montad", motivo.lower())

    def test_la_pasajera_al_reves_TAMBIEN_avisa(self):
        motivo = _almacen(
            _corrida_real(PASAJERA, antisentido_diana=True,
                          antisentido_parciales=True),
            consultas=((PASAJERA, SONDA),),
        ).verdict_for(PASAJERA, species="mouse").reason
        self.assertIn("ORIENTACIÓN", motivo.upper())

    def test_el_AVISO_no_cambia_el_veredicto(self):
        # Es una comprobacion, no un descarte: sigue siendo PASS y lo que hace es DECIR
        # que algo no cuadra. Convertirlo en FAIL mezclaria «esta guia tiene off-targets»
        # con «esta construccion esta mal montada», que son dos cosas.
        self.assertIs(
            _almacen(_corrida_real(
                GUIA, antisentido_diana=False, antisentido_parciales=False,
            )).verdict_for(GUIA, species="mouse").state,
            FilterState.PASS,
        )


if __name__ == "__main__":
    unittest.main()
