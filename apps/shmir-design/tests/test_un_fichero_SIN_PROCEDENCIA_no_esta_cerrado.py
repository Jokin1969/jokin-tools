"""Verde en el panel y NOT_RUN en el veredicto: la tercera vez.

Regla 5: escritos antes.

## Lo reportado (2026-09-06), con la pantalla delante

`transcriptoma_3utr.fa` está en el depósito y figura como **conectado**, con marca verde
y la fila colapsada. Y el modal de off-targets **aborta**: le faltan los cuatro campos de
procedencia de la tabla —ensamblaje, tabla, fecha y criterio de representante— que
`offtarget.Provenance` exige para poder emitir veredicto.

> *«Hoy `transcriptoma_3utr.fa` figura como conectado y no desbloquea nada — es el caso
> de `refseq_rna.fa` otra vez: verde en el panel y NOT_RUN en el veredicto.»*

## Y el verde tenía una segunda consecuencia, peor

Una fila `CERRADO` va **colapsada**, así que sus cuatro acciones —Ver, Reemplazar,
Borrar, Descargar— y la caja de «completar la procedencia» quedaban detrás de un gesto.
Desde fuera el gestor se leía como una lista de nombres: el sitio donde está la salida
era justo el que el estado equivocado escondía.

**El estado tapaba su propio arreglo.** Por eso no basta con avisar: la fila no puede
estar CERRADA.

## El estado que faltaba

`PRESENTE, SIN PROCEDENCIA` no es `CERRADO` ni es `FALTA` —el fichero está, y volver a
subir 84 MB no es lo que hace falta—: es un tercer caso con su propia salida, que es
declarar los cuatro campos sobre el fichero que ya está.
"""

import hashlib
import pathlib
import tempfile
import unittest

from shmir_design.manifest import MANIFEST_COLUMNS
from shmir_design.presentation import (
    reference_manager_rows,
    refinement_panel,
)

NOMBRE = "transcriptoma_3utr.fa"


def _deposito(**procedencia) -> pathlib.Path:
    """Un depósito con el transcriptoma dentro y su línea en el manifiesto."""
    directorio = pathlib.Path(tempfile.mkdtemp())
    (directorio / NOMBRE).write_text(">a\nACGT\n", encoding="utf-8")
    md5 = hashlib.md5((directorio / NOMBRE).read_bytes()).hexdigest()
    fila = {c: "" for c in MANIFEST_COLUMNS}
    fila.update(
        {
            "nombre": NOMBRE,
            "filtro": "carga de off-targets por seed",
            "tamaño": "8",
            "md5": md5,
            "fecha_descarga": "2026-08-31",
            "origen": "UCSC Table Browser",
        }
    )
    fila.update(procedencia)
    (directorio / "manifest.tsv").write_text(
        "\t".join(MANIFEST_COLUMNS)
        + "\n"
        + "\t".join(fila[c] for c in MANIFEST_COLUMNS)
        + "\n",
        encoding="utf-8",
    )
    return directorio


COMPLETA = {
    "ensamblaje": "mm39 (GRCm39, Jun. 2020)",
    "tabla": "RefSeq Curated (ncbiRefSeqCurated)",
    "fecha_tabla": "2026-08-31",
    "representante": "RefSeq Curated — sólo transcritos NM_ curados",
}


def _fila(directorio):
    return next(
        f for f in refinement_panel("mouse", directory=directorio)["filas"]
        if f["nombre"] == NOMBRE
    )


class TestSinLosCuatroCamposNoEstaCerrado(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fila = _fila(_deposito())

    def test_el_gestor_YA_SABIA_cuales_faltan(self):
        """El dato estaba; lo que faltaba era que cambiara el estado de la fila."""
        crudo = next(
            f for f in reference_manager_rows("mouse", directory=_deposito())
            if f["nombre"] == NOMBRE
        )
        self.assertEqual(
            crudo["falta_procedencia"],
            ["ensamblaje", "tabla", "fecha_tabla", "representante"],
        )

    def test_NO_sale_CERRADO(self):
        self.assertNotEqual(self.fila["estado"], "CERRADO")

    def test_ni_verde(self):
        self.assertNotEqual(self.fila["marca"], "🟢")

    def test_y_NO_va_colapsada(self):
        """El estado tapaba su propio arreglo: la caja de declarar estaba detrás."""
        self.assertFalse(self.fila["colapsada"])

    def test_sigue_estando_PRESENTE_con_sus_cuatro_acciones(self):
        """No es `FALTA`: volver a subir 84 MB no es lo que hace falta."""
        self.assertTrue(self.fila["presente"])
        self.assertEqual(
            self.fila["acciones"], ["ver", "reemplazar", "borrar", "descargar"]
        )

    def test_la_fila_DICE_que_le_falta_y_que_NO_desbloquea(self):
        texto = f"{self.fila['por_que']} {self.fila['si_no_llega']}"
        for campo in ("ensamblaje", "tabla", "fecha_tabla", "representante"):
            self.assertIn(campo, texto)
        self.assertIn("NOT_RUN", texto)

    def test_y_cuenta_como_PENDIENTE_en_el_progreso(self):
        panel = refinement_panel("mouse", directory=_deposito())
        completo = refinement_panel("mouse", directory=_deposito(**COMPLETA))
        self.assertLess(
            panel["progreso"]["fraccion"], completo["progreso"]["fraccion"]
        )


class TestConLosCuatroSiCierra(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fila = _fila(_deposito(**COMPLETA))

    def test_con_la_procedencia_completa_vuelve_a_CERRADO(self):
        self.assertEqual(self.fila["estado"], "CERRADO")
        self.assertEqual(self.fila["marca"], "🟢")
        self.assertTrue(self.fila["colapsada"])

    def test_y_ya_no_le_falta_ninguno(self):
        self.assertEqual(self.fila["falta_procedencia"], [])


class TestElEstadoEstaDECLARADO(unittest.TestCase):
    """Un estado nuevo se declara con los demás, o el panel deja de saber pintarlo."""

    def test_tiene_color_y_marca_como_los_otros(self):
        from shmir_design.presentation import _COLOR, INCOMPLETE_PROVENANCE

        self.assertIn(INCOMPLETE_PROVENANCE, _COLOR)

    def test_y_sale_en_la_leyenda_del_panel(self):
        panel = refinement_panel("mouse", directory=_deposito())
        from shmir_design.presentation import INCOMPLETE_PROVENANCE

        self.assertIn(
            INCOMPLETE_PROVENANCE, [e["estado"] for e in panel["leyenda"]]
        )


if __name__ == "__main__":
    unittest.main()


class TestSeCompletaSOBRE_EL_QUE_YA_ESTA(unittest.TestCase):
    """La salida: declarar los cuatro campos sin volver a subir 84 MB.

    Con los valores REALES del fichero del proyecto, dados por el responsable el
    2026-09-06.
    """

    def test_declararlos_cierra_la_fila_y_NO_toca_el_fichero(self):
        from shmir_design.presentation import declare_provenance

        directorio = _deposito()
        antes = (directorio / NOMBRE).read_bytes()
        hecho = declare_provenance(
            directorio,
            filename=NOMBRE,
            species="mouse",
            assembly="mm39 (GRCm39, Jun. 2020)",
            table="RefSeq Curated (ncbiRefSeqCurated)",
            table_date="2026-08-31",
            representative="RefSeq Curated — sólo transcritos NM_ curados",
        )
        self.assertIn(NOMBRE, hecho["texto"])
        # El fichero no se ha tocado: es lo que hace que no haya que resubirlo.
        self.assertEqual((directorio / NOMBRE).read_bytes(), antes)
        fila = _fila(directorio)
        self.assertEqual(fila["estado"], "CERRADO")
        self.assertEqual(fila["falta_procedencia"], [])

    def test_con_un_campo_en_blanco_NO_se_da_por_declarada(self):
        from shmir_design.errors import ShmirDesignError
        from shmir_design.presentation import declare_provenance

        directorio = _deposito()
        with self.assertRaises((ShmirDesignError, ValueError)):
            declare_provenance(
                directorio, filename=NOMBRE, species="mouse",
                assembly="mm39 (GRCm39, Jun. 2020)",
                table="RefSeq Curated (ncbiRefSeqCurated)",
                table_date="",
                representative="RefSeq Curated — sólo transcritos NM_ curados",
            )
        self.assertNotEqual(_fila(directorio)["estado"], "CERRADO")
