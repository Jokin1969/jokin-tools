"""Una base de RefSeq de verdad NO cabe en el escáner por ventana, y se dice antes.

**Reportado (2026-09-04)**: «le doy a Buscar candidatos y lleva 10 min y aún no muestra
nada». Es una REGRESIÓN de esta misma mañana, y la cadena es corta:

1. hasta hoy, `resources._refseq` se negaba a conectar `refseq_rna.fa` sin un gen diana
   tecleado, así que `specificity_db` llegaba `None` y `filter_specificity` salía
   `NOT_RUN` **al instante**;
2. al derivar la diana de su tabla (errata nº 79) el fichero pasa a conectarse — que es
   lo correcto— y con él **se enciende un filtro que barre la base ENTERA por cada
   ventana elegible**.

**MEDIDO en esta máquina (2026-09-04)**, con secuencia real repetida como registros:
~37 Mnt/s por ventana (dos sondas × dos hebras). Con las **407 ventanas elegibles** de la
corrida murina por defecto:

    22 MB  →  3,8 min        100 MB  →  17 min        400 MB  →  73 min

Y la carga: 25 MB/s y **~5× el fichero en RAM** (45 MB de fichero → 234 MB de proceso).

O sea que el escáner en proceso **no puede** con una base de RefSeq de verdad, a ningún
tamaño plausible. Eso no es una limitación que haya que esconder: es **la razón de que
exista el modal de BLAST**, que prepara la orden, se corre fuera y se recoge — y desde la
errata nº 68 una corrida guardada cierra el frente igual que un fichero.

Así que el fichero **se queda en el depósito** —lo usa el modal y de él sale la
procedencia— y lo que no se hace es meterlo en un filtro que tardaría horas sin decirlo.

Regla 5: escritos antes.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design import specificity
from shmir_design.resources import _Omitir, _refseq


class TestElTechoSeDERIVA(unittest.TestCase):
    """No es un número escrito: sale del presupuesto y de la velocidad MEDIDA."""

    def test_el_techo_sale_del_presupuesto_y_de_la_velocidad(self):
        esperado = (
            specificity.SCAN_BUDGET_SECONDS
            * specificity.SCAN_RATE_NT_PER_SECOND
            // specificity.TYPICAL_ELIGIBLE_WINDOWS
        )
        self.assertEqual(specificity.MAX_SCANNABLE_NT, esperado)

    def test_y_la_velocidad_lleva_su_medida_escrita(self):
        # Un número sin fecha ni máquina es un número inventado con dos cifras.
        self.assertIn("MEDIDO", specificity.HOW_THE_RATE_WAS_MEASURED)
        self.assertIn("2026-09-04", specificity.HOW_THE_RATE_WAS_MEASURED)


class TestQueCabeYQueNo(unittest.TestCase):
    def test_una_base_pequeña_cabe(self):
        veredicto = specificity.scanner_budget(2_000_000, name="refseq_rna.fa")
        self.assertTrue(veredicto["cabe"])
        self.assertEqual(veredicto["motivo"], "")

    def test_una_de_cuatrocientos_MB_no_cabe(self):
        veredicto = specificity.scanner_budget(400_000_000, name="refseq_rna.fa")
        self.assertFalse(veredicto["cabe"])

    def test_y_el_motivo_lleva_LOS_NUMEROS_no_una_queja(self):
        motivo = specificity.scanner_budget(400_000_000, name="refseq_rna.fa")["motivo"]
        self.assertIn("400", motivo)          # cuánto pesa
        self.assertIn("407", motivo)          # sobre cuántas ventanas
        self.assertIn("min", motivo)          # cuánto tardaría
        self.assertIn("refseq_rna.fa", motivo)

    def test_el_motivo_dice_que_el_fichero_SIGUE_valiendo(self):
        # Es la mitad que impide la contradicción de la errata nº 79 al revés: abajo el
        # fichero en verde y arriba un texto que se lee como «no sirve».
        motivo = specificity.scanner_budget(400_000_000, name="refseq_rna.fa")["motivo"]
        self.assertIn("depósito", motivo)
        self.assertIn("modal", motivo)

    def test_el_tiempo_proyectado_ESCALA_con_el_tamaño(self):
        # Si no escalara, sería una frase con un número dentro y no una proyección.
        poco = specificity.scanner_budget(100_000_000, name="x")["minutos"]
        mucho = specificity.scanner_budget(400_000_000, name="x")["minutos"]
        self.assertAlmostEqual(mucho / poco, 4.0, places=1)

    def test_un_tamaño_que_no_se_sabe_ABORTA(self):
        # `None` no es «pequeña»: no haber podido mirar el tamaño y que quepa son cosas
        # distintas, y una de ellas cuelga la app una hora.
        with self.assertRaises(Exception):
            specificity.scanner_budget(None, name="x")


class TestElCargadorLOAPLICA(unittest.TestCase):
    """El presupuesto sin llamador sería la séptima vez de la familia de `page_run`.

    Y se comprueba sobre `_refseq`, que es quien lo tiene que aplicar — no sobre
    `scanner_budget`, que ya se prueba arriba. El fichero se crea VACÍO con el tamaño
    declarado (`truncate`): lo que decide es `st_size` y el guardia aborta antes de
    parsear nada, así que no hace falta —ni valdría— fabricar una base de 400 MB. Aquí
    no se inventa ninguna secuencia: se inventa un TAMAÑO, que es lo que se mide.
    """

    class _Entrada:
        name = "refseq_rna.fa"
        md5 = "0" * 32
        date = ""

    def _fichero(self, tamaño: int) -> Path:
        ruta = Path(tempfile.mkdtemp(prefix="base_")) / "refseq_rna.fa"
        with open(ruta, "wb") as fh:
            fh.truncate(tamaño)
        return ruta

    def test_una_base_enorme_NO_se_conecta_y_dice_por_que(self):
        with self.assertRaises(_Omitir) as caja:
            _refseq(self._fichero(400_000_000), self._Entrada(), {})
        self.assertIn("min", str(caja.exception))
        self.assertIn("depósito", str(caja.exception))

    def test_y_una_pequeña_SI_llega_al_cargador(self):
        # Llega, y falla por lo que tiene que fallar: un fichero vacío no es un FASTA.
        # Lo que importa es que el motivo NO sea el del presupuesto.
        with self.assertRaises(Exception) as caja:
            _refseq(self._fichero(1_000), self._Entrada(), {})
        self.assertNotIsInstance(caja.exception, _Omitir)


if __name__ == "__main__":
    unittest.main()
