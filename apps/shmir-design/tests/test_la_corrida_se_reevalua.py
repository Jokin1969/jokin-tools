"""Una corrida guardada se REEVALUA cuando aparece el fichero que le faltaba.

Reportado el 2026-09-02, y el diagnostico del que lo reporta era el correcto: el estado
se deriva comparando md5 —eso esta bien— pero el resultado de esa comparacion parecia
quedarse congelado. No estaba congelado: **la comparacion no podia darse nunca**.

`insumos.CONSUMIDOS` nombraba el insumo de BLAST en PROSA —«base de datos de BLAST»— y
`actuales` viene indexado por el NOMBRE DEL FICHERO en el deposito, que es
`refseq_rna.fa`. Asi que `actuales.get(...)` devolvia `None` pasara lo que pasara, y la
corrida salia «no se ha podido comprobar» **para siempre**, con el fichero delante y con
el md5 correcto.

Y lo que lo tapaba es la misma forma que la errata nº 44, un piso mas abajo: los tests
de `obsoleta` **transcribian la clave que ellos mismos habian escrito**
(`actuales={"base de datos de BLAST": ...}`), asi que preguntaban por su propio nombre y
no podian discrepar del deposito nunca.

Se cierra DERIVANDO (principio nº 13): el insumo declara su ROL y el nombre lo pone
`species.required_files`, que es la unica fuente de los nombres del deposito. Con eso la
discrepancia no es que este arreglada: es que no se puede escribir.
"""

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import blast, blast_store, insumos, presentation, species
from shmir_design import store as st
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState

CONTENIDO = b">NM_000000.1 de mentira, solo para tener un md5\nACGTACGTACGTACGT\n"
MD5 = hashlib.md5(CONTENIDO, usedforsecurity=False).hexdigest()


def _corrida(*, md5: str):
    esp = species.resolve("mouse")
    nombre = presentation.query_name(esp, 959, "guia")
    consulta = blast.QueryFasta.from_records([(nombre, "ACGTACGTACGTACGTACGTAC")])
    crudo = f"{nombre}\tNM_1\t100.0\t22\t0\t0\t1\t22\t1\t22\t1e-5\t44.1\n"
    return blast_store.BlastRun.create(
        run_id="r1", date="2026-09-01", uploaded_by="jc", query=consulta, raw=crudo,
        params=blast.BlastParams.for_species("mouse"),
        database=blast_store.BlastDatabase(
            name="refseq_rna_mouse", version="2026-09", md5=md5, remote=False,
        ),
    )


class TestElFicheroAPARECEyLaCorridaSEREEVALUA(unittest.TestCase):
    """El caso reportado, de punta a punta y por el camino de la pagina."""

    def setUp(self):
        self.deposito = Path(tempfile.mkdtemp())
        self.proyectos = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.deposito, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.proyectos, ignore_errors=True)
        self.almacen = st.ProjectStore.create(
            self.proyectos, slug="reevaluacion", sequence="ACGT" * 40, species="mouse",
            anatomy=None, anatomy_source="lo subido ya es el 3'UTR",
            created="2026-09-01",
        )
        st.save_blast_run(self.almacen, _corrida(md5=MD5))

    def _estado(self):
        filas = presentation.obsolete_rows(self.almacen, directory=self.deposito)
        self.assertEqual(len(filas), 1)
        return filas[0]

    def test_sin_el_fichero_dice_que_NO_SE_HA_PODIDO_COMPROBAR(self):
        fila = self._estado()
        self.assertIs(fila["estado"], FilterState.NOT_RUN)
        self.assertTrue(any("no se ha podido comprobar" in m for m in fila["motivos"]))
        # Y NOMBRA el fichero que hace falta, con el nombre del deposito: es lo que
        # convierte el motivo en una instruccion.
        self.assertTrue(any("refseq_rna.fa" in m for m in fila["motivos"]))

    def test_cuando_APARECE_con_el_mismo_md5_la_corrida_pasa_a_VIGENTE(self):
        (self.deposito / "refseq_rna.fa").write_bytes(CONTENIDO)
        fila = self._estado()
        self.assertIs(fila["estado"], FilterState.PASS)
        self.assertEqual(fila["motivos"], [])

    def test_y_si_luego_CAMBIA_vuelve_a_salir_OBSOLETA(self):
        # La otra mitad, y sin ella «pasa a PASS» no demuestra que se compare nada:
        # un `PASS` fijo daria el mismo resultado en el test de arriba.
        (self.deposito / "refseq_rna.fa").write_bytes(CONTENIDO + b"ACGT\n")
        fila = self._estado()
        self.assertIs(fila["estado"], FilterState.OBSOLETO)
        self.assertTrue(any(MD5 in m for m in fila["motivos"]))

    def test_se_RECALCULA_en_cada_consulta_sin_tocar_el_log(self):
        # Es la logica de OBSOLETO y el requisito del que lo reporto: aparecer o
        # desaparecer un fichero se refleja solo, sin volver a guardar la corrida.
        self.assertIs(self._estado()["estado"], FilterState.NOT_RUN)
        (self.deposito / "refseq_rna.fa").write_bytes(CONTENIDO)
        self.assertIs(self._estado()["estado"], FilterState.PASS)
        (self.deposito / "refseq_rna.fa").unlink()
        self.assertIs(self._estado()["estado"], FilterState.NOT_RUN)


class TestElNombreSEDERIVAdelGestor(unittest.TestCase):
    """El mecanismo. Sin esto el arreglo protege esta tabla y no la siguiente."""

    def _del_deposito(self, especie):
        return {f.filename for f in species.required_files(species.resolve(especie))}

    def test_todo_insumo_resuelve_a_un_fichero_QUE_EL_GESTOR_PIDE(self):
        for especie in species.SPECIES:
            pedidos = self._del_deposito(especie)
            for tipo, lista in insumos.CONSUMIDOS.items():
                for ins in lista:
                    with self.subTest(f"{especie}/{tipo}/{ins.rol}"):
                        self.assertIn(insumos.fichero_de(ins, especie), pedidos)

    def test_un_rol_que_el_gestor_no_declara_ABORTA(self):
        inventado = insumos.Insumo(rol="no_existe", ruta=("a",), porque="prueba")
        with self.assertRaises(ShmirDesignError) as caja:
            insumos.fichero_de(inventado, "mouse")
        self.assertIn("no_existe", str(caja.exception))

    def test_el_nombre_DEPENDE_de_la_especie(self):
        # Control adversario: si la resolucion devolviera siempre lo mismo, el test de
        # arriba pasaria igual y no estaria midiendo ninguna derivacion.
        ins = insumos.insumos_de("corrida_blast")[0]
        self.assertEqual(insumos.fichero_de(ins, "mouse"), "refseq_rna.fa")
        self.assertEqual(insumos.fichero_de(ins, "human"), "refseq_rna_human.fa")


class TestNingunTestTRANSCRIBEsuPropiaClave(unittest.TestCase):
    """Lo que dejo pasar el fallo, cerrado como regresion.

    Un test que construye `actuales` con un nombre escrito a mano pregunta por la clave
    que el mismo ha puesto: coincide siempre y no puede discrepar del deposito. La
    unica forma de construir `actuales` es `presentation.reference_md5s`, que lo lee del
    directorio, o `species.required_files`, que es de donde salen esos nombres.
    """

    FUENTES = ("tests/test_insumos_de_cada_corrida.py", "tests/test_obsoleto.py")

    def test_no_queda_ninguna_clave_de_actuales_escrita_a_mano(self):
        raiz = Path(__file__).resolve().parent.parent
        for relativo in self.FUENTES:
            texto = (raiz / relativo).read_text(encoding="utf-8")
            with self.subTest(relativo):
                self.assertFalse(
                    "base de datos de BLAST" in texto,
                    f"{relativo} vuelve a escribir a mano la clave de `actuales`. Esa "
                    f"clave es el NOMBRE DEL FICHERO en el deposito y sale de "
                    f"`species.required_files`; escribirla aqui hace que el test "
                    f"pregunte por su propia respuesta (errata nº 47).",
                )


if __name__ == "__main__":
    unittest.main()
