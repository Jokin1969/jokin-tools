"""Un informe que lee estado MUTABLE declara contra QUE estado se genero.

**El corolario, del responsable del proyecto (2026-09-01)**: *la fecha no basta — dos
corridas del mismo dia son dos documentos distintos.* Hasta ahora el documento decia
CUANDO se genero; en cuanto empieza a leer los almacenes, eso deja de identificarlo.

Tres cosas, y ninguna sustituye a otra:

  - la HUELLA del log en la cabecera: un md5 de la lista de `run_id` presentes al
    generar. Dos informes con la misma huella son el mismo documento; con huellas
    distintas, la diferencia **se explica sola** sin que nadie tenga que acordarse de
    que subio un BLAST en medio;
  - por cada frente cerrado por una corrida: `run_id`, fecha, md5 del fichero subido y
    md5 de la base o catalogo usado. Es lo mismo que ya se le exige a un fichero de
    referencia, aplicado a un RESULTADO;
  - y las fichas del documento leyendo los almacenes de verdad, que es lo que hace que
    todo lo anterior signifique algo.
"""

import unittest

from shmir_design import blast, presentation
from shmir_design.blast_store import BlastDatabase, BlastRun, BlastStore

CONSULTA = presentation.query_name("raton", 200, "guia")
GUIA = "TTATATTCTTATTGGCCCGGTG"


def _corrida(run_id="r1"):
    fasta = blast.QueryFasta.from_records(((CONSULTA, GUIA),))
    return BlastRun.create(
        run_id=run_id, date="2026-09-01", uploaded_by="responsable",
        params=blast.BlastParams.for_species("raton"),
        database=BlastDatabase(
            name="refseq_mouse", version="2026-09-01", md5="a" * 32, remote=False,
        ),
        query=fasta,
        raw=f"{CONSULTA}\tNM_011170.3\t100.000\t22\t0\t0\t1\t22\t1170\t1191\t1e-05\t44.1\n",
    )


class TestLaHUELLAdelLOG(unittest.TestCase):

    def test_sin_ninguna_corrida_hay_huella_y_lo_DICE(self):
        # No se omite: un documento sin huella y uno generado sin corridas se leerian
        # igual, y son cosas distintas.
        huella = presentation.log_fingerprint({})
        self.assertTrue(huella["huella"])
        self.assertEqual(huella["corridas"], 0)

    def test_dos_veces_el_MISMO_estado_dan_la_MISMA_huella(self):
        almacen = BlastStore()
        almacen.add(_corrida())
        estado = {"blast": almacen}
        self.assertEqual(
            presentation.log_fingerprint(estado)["huella"],
            presentation.log_fingerprint(estado)["huella"],
        )

    def test_y_una_corrida_MAS_la_cambia(self):
        almacen = BlastStore()
        almacen.add(_corrida("r1"))
        antes = presentation.log_fingerprint({"blast": almacen})["huella"]
        almacen.add(_corrida("r2"))
        despues = presentation.log_fingerprint({"blast": almacen})["huella"]
        self.assertNotEqual(antes, despues)

    def test_el_ORDEN_de_llegada_no_cambia_la_huella(self):
        # Dos logs con las mismas corridas son el mismo estado. Si el orden contara, dos
        # informes identicos saldrian con huellas distintas y la señal dejaria de valer.
        uno, otro = BlastStore(), BlastStore()
        uno.add(_corrida("r1")); uno.add(_corrida("r2"))
        otro.add(_corrida("r2")); otro.add(_corrida("r1"))
        self.assertEqual(
            presentation.log_fingerprint({"blast": uno})["huella"],
            presentation.log_fingerprint({"blast": otro})["huella"],
        )


class TestLaPROCEDENCIAdeCADAcorrida(unittest.TestCase):
    """Lo mismo que ya se le exige a un fichero de referencia, sobre un RESULTADO."""

    @classmethod
    def setUpClass(cls):
        almacen = BlastStore()
        almacen.add(_corrida())
        cls.filas = presentation.run_provenance_rows({"blast": almacen})

    def test_hay_una_fila_por_corrida(self):
        self.assertEqual(len(self.filas), 1)

    def test_y_trae_los_CUATRO_datos(self):
        fila = self.filas[0]
        self.assertEqual(fila["run_id"], "r1")
        self.assertEqual(fila["fecha"], "2026-09-01")
        self.assertTrue(fila["md5_subido"])
        self.assertEqual(fila["md5_base"], "a" * 32)

    def test_el_md5_del_SUBIDO_es_el_del_resultado_no_el_de_la_consulta(self):
        # Son dos md5 distintos y confundirlos deja la procedencia apuntando al fichero
        # que la app genero, no al que llego de fuera — que es el que hay que poder
        # cotejar.
        almacen = BlastStore()
        corrida = _corrida()
        almacen.add(corrida)
        fila = presentation.run_provenance_rows({"blast": almacen})[0]
        self.assertEqual(fila["md5_subido"], corrida.result_md5)
        self.assertNotEqual(fila["md5_subido"], corrida.query_md5)


if __name__ == "__main__":
    unittest.main()
