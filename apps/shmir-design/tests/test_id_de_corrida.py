"""Repetir una corrida el MISMO DIA es lo normal, y el id tiene que admitirlo.

**Reportado por el responsable del proyecto (2026-09-02), tres veces el mismo dia**:
`Mus musculus-blast-02/09/2026` ya existe y la subida aborta. El id era
`especie + tipo + fecha`, asi que la segunda corrida del dia no cabia — y hubo cuatro,
todas por fallos de la app, no por capricho. La salida que quedaba era inventarse una
fecha o crear un proyecto nuevo, y lo segundo **tira el historial que el log existe para
conservar**: por que se volvio a correr.

LA PROPIEDAD QUE HACE FALTA la nombro el: **el `result_md5`**. Dos ficheros distintos no
chocan, y dos identicos si — que es exactamente cuando abortar es lo correcto, porque es
subir dos veces lo mismo.

Y hay una segunda mitad, tan importante como la primera: **el mensaje tiene que decir
como salir**. Uno que solo dice que aborta empuja a inventarse una fecha falsa, que es lo
que se acaba de quitar.

La especie SALE del id: el log es de UN proyecto y el proyecto ya declara su especie
(`proyecto.json`). Estaba repetida en cada linea.
"""

import unittest

from shmir_design import blast, blast_store, identidad, presentation
from shmir_design.errors import ShmirDesignError
from shmir_design.species import resolve

FECHA = "2026-09-02"


def _consulta():
    nombre = presentation.query_name(resolve("mouse"), 959, "guia")
    return nombre, blast.QueryFasta.from_records(
        [(nombre, "ACGTACGTACGTACGTACGTAC")]
    )


def _corrida(crudo: str):
    nombre, consulta = _consulta()
    return presentation.blast_run_from_upload(
        raw=crudo, query=consulta, params=blast.BlastParams.for_species("mouse"),
        declared_query_md5=consulta.md5, panel_names=consulta.names,
        database={
            "nombre": "refseq_rna_mouse", "version": "2026-09",
            "md5": "a" * 32, "remota": False,
        },
        date=FECHA, uploaded_by="jc",
    )


def _crudo(bitscore: str):
    nombre, _ = _consulta()
    return f"{nombre}\tNM_1\t100.0\t22\t0\t0\t1\t22\t1\t22\t1e-5\t{bitscore}\n"


class TestCuatroCorridasElMismoDia(unittest.TestCase):
    """El caso reportado, tal cual: cuatro reintentos en un dia."""

    def test_entran_las_cuatro(self):
        almacen = blast_store.BlastStore()
        for i in range(4):
            almacen.add(_corrida(_crudo(f"4{i}.1")))
        self.assertEqual(len(almacen.runs), 4)
        self.assertEqual(len({r.run_id for r in almacen.runs}), 4)

    def test_y_NO_hace_falta_ni_otra_fecha_ni_otro_proyecto(self):
        # Las cuatro llevan la MISMA fecha. Era lo que habia que inventarse.
        almacen = blast_store.BlastStore()
        for i in range(4):
            almacen.add(_corrida(_crudo(f"4{i}.1")))
        self.assertEqual({r.date for r in almacen.runs}, {FECHA})


class TestSUBIRDOSVECESLOMISMOsiABORTA(unittest.TestCase):
    """La otra mitad. Sin esto, «admite repetir» seria «no comprueba nada»."""

    def setUp(self):
        self.almacen = blast_store.BlastStore()
        self.primera = _corrida(_crudo("44.1"))
        self.almacen.add(self.primera)

    def test_el_mismo_fichero_otra_vez_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            self.almacen.add(_corrida(_crudo("44.1")))

    def test_y_el_mensaje_dice_COMO_SALIR(self):
        with self.assertRaises(ShmirDesignError) as caja:
            self.almacen.add(_corrida(_crudo("44.1")))
        texto = str(caja.exception)
        # 1. QUE ha pasado: es el MISMO fichero, no una corrida nueva.
        self.assertIn("byte a byte", texto)
        # 2. DONDE esta la que ya hay, para poder ir a mirarla.
        self.assertIn(self.primera.run_id, texto)
        self.assertIn(self.primera.date, texto)
        # 3. Y las dos salidas FALSAS, dichas por su nombre para que nadie las tome.
        self.assertIn("fecha", texto)
        self.assertIn("proyecto", texto)

    def test_el_mensaje_NO_manda_borrar_nada(self):
        # El log es append-only: «borra la anterior» no es una salida que exista, y
        # ofrecerla manda a pelearse con un fichero que no se debe tocar.
        with self.assertRaises(ShmirDesignError) as caja:
            self.almacen.add(_corrida(_crudo("44.1")))
        self.assertIn("append-only", str(caja.exception))


class TestElIdSEDERIVAdelResultado(unittest.TestCase):

    def test_el_id_TERMINA_en_el_result_md5_de_la_propia_corrida(self):
        # Si el id y el md5 guardado pudieran discrepar, habria dos identidades de la
        # misma corrida y nada obligaria a que coincidieran.
        corrida = _corrida(_crudo("44.1"))
        self.assertTrue(corrida.run_id.endswith(corrida.result_md5))

    def test_la_especie_NO_entra_en_el_id(self):
        corrida = _corrida(_crudo("44.1"))
        self.assertNotIn("mus", corrida.run_id.lower())

    def test_un_tipo_de_corrida_desconocido_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            identidad.run_id(kind="corrida_inventada", date=FECHA, result_md5="a" * 32)

    def test_los_cuatro_tipos_tienen_id(self):
        from shmir_design.store import RECORD_KINDS

        for kind in (k for k in RECORD_KINDS if k.startswith("corrida_")):
            with self.subTest(kind):
                self.assertTrue(
                    identidad.run_id(kind=kind, date=FECHA, result_md5="a" * 32)
                )

    def test_dos_tipos_distintos_con_el_MISMO_crudo_no_chocan(self):
        # Control adversario: si el tipo no entrara en el id, un scan de seed y uno de
        # off-target con la misma salida se pisarian.
        uno = identidad.run_id(kind="corrida_seed", date=FECHA, result_md5="a" * 32)
        otro = identidad.run_id(
            kind="corrida_offtarget", date=FECHA, result_md5="a" * 32
        )
        self.assertNotEqual(uno, otro)


class TestUnSoloSitioCALCULAelMd5(unittest.TestCase):
    """Cuatro copias de `hashlib.md5(raw)` eran cuatro definiciones del mismo numero."""

    def test_los_cuatro_almacenes_usan_result_fingerprint(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent / "shmir_design"
        for nombre in (
            "blast_store.py", "seed_store.py", "offtarget_store.py", "splice_store.py",
        ):
            fuente = (raiz / nombre).read_text(encoding="utf-8")
            with self.subTest(nombre):
                self.assertIn("result_fingerprint", fuente)
                self.assertNotIn("hashlib.md5", fuente)


class TestLaPAGINAnoCONSTRUYEidentidades(unittest.TestCase):
    """Regla 6: el id decide si una corrida entra o se rechaza. Eso no vive en la página."""

    def test_la_pagina_no_arma_ningun_run_id(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("run_id=", fuente)


if __name__ == "__main__":
    unittest.main()
