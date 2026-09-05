"""OBSOLETO: una corrida cuyo fichero de entrada YA NO ES EL MISMO.

Regla 5: escrito antes.

Es el estado que faltaba, y estaba bloqueado por una sola cosa: `SeedScan` no guardaba
el md5 de `mature.fa`, así que para las corridas de seed no había con qué comparar. Con
el md5 como campo —y con `insumos.CONSUMIDOS` diciendo dónde vive el de cada tipo de
corrida— la comparación se puede DERIVAR en vez de anotarse a mano, que es lo que se
pidió.

Las tres distinciones que hacen falta, y ninguna sobra:

  · **PASS**  — la corrida se hizo y sus ficheros siguen siendo los mismos.
  · **OBSOLETO** — se hizo, pero un fichero que consumió ha cambiado debajo. NO es
    NOT_RUN: hay un resultado y se puede leer. Y no es PASS: no se puede defender un
    veredicto con un fichero que ya no existe.
  · **NOT_RUN** — no se hizo, o se hizo sin guardar el md5, así que no se ha podido
    comprobar. No haber podido comprobar no es «coincide», que es la misma regla del
    `.out` sin resumen.
"""

import unittest

from shmir_design.filters import FilterState


class TestElEstadoExiste(unittest.TestCase):
    def test_OBSOLETO_es_un_estado_propio(self):
        self.assertIn("OBSOLETO", FilterState.__members__)

    def test_y_no_es_ni_PASS_ni_NOT_RUN(self):
        self.assertIsNot(FilterState.OBSOLETO, FilterState.PASS)
        self.assertIsNot(FilterState.OBSOLETO, FilterState.NOT_RUN)


class TestLaDerivacion(unittest.TestCase):
    """De la tabla de insumos y de los md5, sin una nota escrita a mano.

    El nombre del fichero tampoco se escribe aqui: se pide a `insumos.fichero_de`, que
    es quien lo resuelve contra el gestor. Escribirlo haria que el test preguntase por
    la clave que el mismo ha puesto — que es lo que dejo pasar la errata nº 47.
    """

    PAYLOAD = {"mature_md5": "a" * 32, "result_md5": "r" * 32}
    ESPECIE = "mouse"

    @property
    def MADUROS(self):
        from shmir_design import insumos

        return insumos.fichero_de(insumos.insumos_de("corrida_seed")[0], self.ESPECIE)

    def _estado(self, actuales):
        from shmir_design.presentation import run_freshness

        return run_freshness(
            "corrida_seed", self.PAYLOAD, actuales=actuales, especie=self.ESPECIE,
        )

    def test_mismo_md5_es_PASS(self):
        estado = self._estado({self.MADUROS: "a" * 32})
        self.assertIs(estado["estado"], FilterState.PASS)
        self.assertEqual(estado["motivos"], [])

    def test_md5_distinto_es_OBSOLETO_y_NOMBRA_el_fichero(self):
        estado = self._estado({self.MADUROS: "b" * 32})
        self.assertIs(estado["estado"], FilterState.OBSOLETO)
        self.assertIn(self.MADUROS, estado["motivos"][0])

    def test_sin_md5_de_hoy_es_NOT_RUN_y_NO_pasa_por_vigente(self):
        estado = self._estado({})
        self.assertIs(estado["estado"], FilterState.NOT_RUN)
        self.assertIn("no se ha podido comprobar", estado["motivos"][0])

    def test_una_corrida_vieja_SIN_el_campo_tambien_es_NOT_RUN(self):
        from shmir_design.presentation import run_freshness

        estado = run_freshness(
            "corrida_seed", {"result_md5": "r" * 32},
            actuales={self.MADUROS: "a" * 32}, especie=self.ESPECIE,
        )
        self.assertIs(estado["estado"], FilterState.NOT_RUN)

    def test_la_corrida_de_empalme_no_consume_ficheros_y_sale_PASS(self):
        from shmir_design.presentation import run_freshness

        self.assertIs(
            run_freshness(
                "corrida_empalme", {}, actuales={}, especie=self.ESPECIE,
            )["estado"],
            FilterState.PASS,
        )


class TestLosMd5DeHoySalenDelDirectorio(unittest.TestCase):
    def test_se_calculan_del_fichero_nunca_se_declaran(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from shmir_design.presentation import reference_md5s

        with TemporaryDirectory() as tmp:
            (Path(tmp) / "mature.fa").write_text(">x\nACGU\n", encoding="utf-8")
            md5s = reference_md5s(tmp)
        self.assertIn("mature.fa", md5s)
        self.assertRegex(md5s["mature.fa"], r"^[0-9a-f]{32}$")

    def test_un_fichero_VACIO_no_cuenta_como_presente(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from shmir_design.presentation import reference_md5s

        with TemporaryDirectory() as tmp:
            (Path(tmp) / "mature.fa").write_bytes(b"")
            self.assertEqual(reference_md5s(tmp), {})


class TestSeVE(unittest.TestCase):
    """Media función es la que corre y no llega a la pantalla. Errata nº 17."""

    def test_la_pagina_pide_las_filas_a_presentation(self):
        from pathlib import Path

        pagina = (
            Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("obsolete_rows", pagina)


if __name__ == "__main__":
    unittest.main()
