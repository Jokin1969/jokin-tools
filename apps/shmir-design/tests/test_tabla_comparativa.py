"""Tests de la tabla comparativa unica (bloque 6).

Regla 5: escritos antes de implementarla.

Es lo que mas valor añade de la tanda: una sola tabla con los N seleccionados y TODOS
los parametros lado a lado, para poder discutir descartes sobre datos en vez de sobre
impresiones.

Y una columna `knockdown_medido` VACIA: la idea es que ese TSV vuelva del laboratorio
relleno y se pueda correlacionar cada parametro contra la potencia real. Ahora mismo se
ordena por asimetria, que predice seleccion de hebra y no potencia; con diez medidas se
sabra que parametros predicen algo y cuales son decoracion.
"""

import unittest

from shmir_design.comparative import COMPARATIVE_COLUMNS, comparative_rows, comparative_tsv
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.selection import SelectionConfig, select_from_report
from shmir_design.specificity import SpecificityDatabase
from shmir_design.tiling import tile_utr

SONDA = "GCGTCAGTACGATCGAATTACT" * 20


def _piezas(**kwargs):
    tiling = tile_utr(SONDA, **kwargs)
    return tiling, select_from_report(tiling, SelectionConfig(n_candidates=3))


class TestColumnas(unittest.TestCase):

    def test_estan_todas_las_que_se_pidieron(self):
        esperadas = (
            "inicio_3utr", "inicio_transcrito", "tercio", "region",
            "diana", "guia", "pasajera", "gblock_149",
            "GC", "asimetria",
            "polyA_hexamero", "polyA_clase", "polyA_posicion_rel",
            "polyA_solapa_seed", "polyA_veredicto",
            "riesgo_APA",
            "especificidad_0mm", "especificidad_1mm", "especificidad_2mm",
            "transgen", "seed_colision", "carga_seed", "accesibilidad",
            "veredicto", "knockdown_medido",
        )
        for columna in esperadas:
            self.assertIn(columna, COMPARATIVE_COLUMNS, columna)

    def test_hay_una_columna_por_filtro(self):
        tiling, seleccion = _piezas()
        columnas = comparative_rows(seleccion, SGEP_SCAFFOLD)[0]
        for filtro in tiling.windows[0].filters:
            self.assertIn(f"filtro:{filtro.name}", columnas)

    def test_knockdown_medido_es_la_ultima(self):
        self.assertEqual(COMPARATIVE_COLUMNS[-1], "knockdown_medido")


class TestFilas(unittest.TestCase):

    def test_una_fila_por_candidato_mas_la_cabecera(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        self.assertEqual(len(filas) - 1, len(seleccion.selection.chosen))

    def test_todas_las_filas_tienen_el_mismo_ancho(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        for fila in filas[1:]:
            self.assertEqual(len(fila), len(filas[0]))

    def test_la_columna_de_knockdown_va_vacia(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        indice = filas[0].index("knockdown_medido")
        for fila in filas[1:]:
            self.assertEqual(fila[indice], "")

    def test_la_guia_y_la_pasajera_no_van_vacias(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        for nombre in ("guia", "pasajera"):
            indice = filas[0].index(nombre)
            for fila in filas[1:]:
                self.assertTrue(fila[indice])

    def test_el_modulo_de_149_nt_esta_entero(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        indice = filas[0].index("gblock_149")
        for fila in filas[1:]:
            self.assertEqual(len(fila[indice]), 149)

    def test_los_campos_sin_dato_van_vacios_no_a_cero(self):
        """Sin base de datos, la especificidad no es 0 hits: es que no se conto."""
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        for columna in ("especificidad_0mm", "carga_seed", "accesibilidad"):
            indice = filas[0].index(columna)
            for fila in filas[1:]:
                self.assertEqual(fila[indice], "", columna)

    def test_con_especificidad_los_recuentos_salen(self):
        base = SpecificityDatabase(
            name="base de prueba", version="v", checksum="0" * 32,
            records={"diana": SONDA},
        )
        _, seleccion = _piezas(specificity_db=base, specificity_target="diana")
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        indice = filas[0].index("especificidad_0mm")
        self.assertTrue(any(fila[indice] != "" for fila in filas[1:]))


class TestTSV(unittest.TestCase):

    def test_es_un_TSV_con_cabecera(self):
        _, seleccion = _piezas()
        texto = comparative_tsv(seleccion, SGEP_SCAFFOLD)
        self.assertTrue(texto.splitlines()[0].startswith("inicio_3utr\t"))

    def test_ningun_campo_lleva_tabuladores_ni_saltos(self):
        _, seleccion = _piezas()
        texto = comparative_tsv(seleccion, SGEP_SCAFFOLD)
        anchos = {len(l.split("\t")) for l in texto.splitlines()}
        self.assertEqual(len(anchos), 1)

    def test_lleva_una_cabecera_de_comentario_que_explica_la_columna_vacia(self):
        _, seleccion = _piezas()
        texto = comparative_tsv(seleccion, SGEP_SCAFFOLD, with_header=True)
        self.assertIn("knockdown_medido", texto.splitlines()[0])
        self.assertTrue(texto.startswith("#"))


if __name__ == "__main__":
    unittest.main()


class TestBloqueLegible(unittest.TestCase):
    """Un candidato del CDS no tiene coordenada de 3'UTR: la fila no puede salir coja."""

    def test_la_primera_columna_nunca_va_vacia(self):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.comparative import comparative_text
        from shmir_design.selection import SelectionConfig, select_from_report

        utr5 = "GCGTCAGTACGATCGAATTACT" * 2
        cds = "ATG" + "GCTAACGGGACT" * 8 + "TAA"
        utr3 = "GCGTCAGTACGATCGAATTACT" * 20
        secuencia = utr5 + cds + utr3
        tiling = tile_utr(
            secuencia,
            anatomy=Anatomy.from_cds(cds=(45, 146), length=len(secuencia)),
        )
        from shmir_design.anatomy import Region

        seleccion = select_from_report(
            tiling,
            SelectionConfig(
                n_candidates=2,
                region_quota=((Region.UTR3, 1), (Region.CDS, 1)),
                require_one_per_tercio=False,
            ),
        )
        texto = comparative_text(seleccion, SGEP_SCAFFOLD)
        for linea in texto.splitlines()[1:3]:
            self.assertTrue(linea.strip().split()[0].isdigit(), linea)

    def test_el_bloque_dice_la_region_de_cada_candidato(self):
        from shmir_design.comparative import comparative_text

        _, seleccion = _piezas()
        self.assertIn("region", comparative_text(seleccion, SGEP_SCAFFOLD))


class TestGuardaContraColisionDeColumnas(unittest.TestCase):
    """Cuatro filtros se llaman IGUAL que columnas fijas: GC, asimetria, transgen y
    seed_colision. Hoy no chocan porque las de filtro llevan prefijo `filtro:`, pero
    nada lo obligaba. Si alguien quita el prefijo, el diccionario fusionado pierde el
    valor numerico en silencio — que es el fallo que ya se colo una vez en la interfaz.
    """

    def test_hay_nombres_de_filtro_que_coinciden_con_columnas_fijas(self):
        tiling, _ = _piezas()
        nombres = {r.name for r in tiling.windows[0].filters}
        self.assertTrue(
            nombres & set(COMPARATIVE_COLUMNS),
            "si esto deja de ser cierto, este guarda ya no hace falta",
        )

    def test_pero_ninguna_columna_aparece_dos_veces(self):
        _, seleccion = _piezas()
        columnas = comparative_rows(seleccion, SGEP_SCAFFOLD)[0]
        self.assertEqual(len(columnas), len(set(columnas)))

    def test_y_las_de_filtro_van_todas_con_prefijo(self):
        tiling, seleccion = _piezas()
        columnas = comparative_rows(seleccion, SGEP_SCAFFOLD)[0]
        for filtro in tiling.windows[0].filters:
            self.assertIn(f"filtro:{filtro.name}", columnas)
            self.assertNotIn(filtro.name, COMPARATIVE_COLUMNS[:-1] + ("knockdown_medido",)
                             if filtro.name not in COMPARATIVE_COLUMNS else ())

    def test_la_columna_GC_sigue_siendo_el_numero_y_no_el_estado(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        gc = filas[1][filas[0].index("GC")]
        float(gc)  # si fuera el estado del filtro, esto reventaria
        self.assertIn(filas[1][filas[0].index("filtro:GC")], ("PASS", "FAIL", "NOT_RUN"))
