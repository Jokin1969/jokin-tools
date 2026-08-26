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

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.comparative import (
    COMPARATIVE_COLUMNS,
    comparative_rows,
    comparative_text,
    comparative_tsv,
)
from shmir_design.external_score import FEATURE_COLUMNS, splashrna_features
from shmir_design.outputs import tsv_oligos
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


class TestScoreExterno(unittest.TestCase):
    """La columna `score_externo` viaja al lado de `knockdown_medido`.

    Las dos van vacias hasta que alguien traiga datos: una del laboratorio y la otra de
    miRarchitect. Ninguna se rellena con un numero calculado aqui — eso seria un score
    propio con etiqueta ajena, que es justo lo que se prohibio al pedir esta columna.
    """

    def columnas(self):
        _, seleccion = _piezas()
        return comparative_rows(seleccion, SGEP_SCAFFOLD)[0]

    def test_las_ultimas_son_las_que_esperan_dato_de_fuera(self):
        self.assertEqual(
            COMPARATIVE_COLUMNS[-6:],
            ("score_externo", "fuente_score", "mirarch_confirmado", "mirarch_rank",
             "mirarch_shift_nt", "knockdown_medido"),
        )

    def test_las_banderas_de_miRarchitect_nacen_vacias(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        for fila in filas[1:]:
            for columna in ("mirarch_confirmado", "mirarch_rank", "mirarch_shift_nt"):
                with self.subTest(columna):
                    self.assertEqual(fila[filas[0].index(columna)], "")

    def test_las_dos_columnas_del_score_van_vacias(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        cabecera = filas[0]
        for fila in filas[1:]:
            for columna in ("score_externo", "fuente_score"):
                with self.subTest(columna):
                    self.assertEqual(fila[cabecera.index(columna)], "")

    def test_las_features_de_splashrna_estan_en_columnas_separadas(self):
        columnas = self.columnas()
        for feature in FEATURE_COLUMNS:
            with self.subTest(feature):
                self.assertIn(feature, columnas)

    def test_las_features_si_traen_valor(self):
        # Las features SI se calculan —son aritmetica sobre la propia guia— y por eso
        # no van vacias. Lo que no existe es el score que saldria de combinarlas.
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        indice = filas[0].index("feat_GC_seed")
        for fila in filas[1:]:
            self.assertNotEqual(fila[indice], "")

    def test_las_features_de_cada_fila_son_las_de_SU_guia(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        guia = filas[0].index("guia")
        for fila in filas[1:]:
            esperado = splashrna_features(fila[guia])
            for feature, valor in esperado.items():
                with self.subTest(feature=feature, guia=fila[guia]):
                    self.assertEqual(fila[filas[0].index(feature)], valor)

    def test_la_cabecera_explica_que_el_score_no_es_un_veredicto(self):
        _, seleccion = _piezas()
        texto = comparative_tsv(seleccion, SGEP_SCAFFOLD, with_header=True)
        cabecera = "\n".join(
            l for l in texto.splitlines() if l.startswith("#")
        ).lower()
        self.assertIn("score_externo", cabecera)
        self.assertIn("informativ", cabecera)

    def test_ninguna_fila_pone_un_score_calculado_aqui(self):
        # Guarda explicita: si algun dia alguien rellena `score_externo` con una cuenta
        # local, este test lo para. La procedencia es parte del dato.
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        fuente = filas[0].index("fuente_score")
        for fila in filas[1:]:
            self.assertNotIn(fila[fuente], ("splashrna_features", "local", "shmir"))


class TestColumnaPasajera(unittest.TestCase):
    """La columna `pasajera` tiene que ser la SECUENCIA, no el objeto que la lleva.

    Llevaba el `repr` del dataclass `Passenger` entero —`Passenger(sequence='ATG...',
    reverse_complement='CTG...', ...)`— porque se escribia `hairpin.passenger` en vez de
    `hairpin.passenger.sequence`. La columna no iba vacia, asi que parecia buena: es
    exactamente el tipo de fallo que solo se ve mirando el fichero. Nadie puede pegar
    eso en un pedido.
    """

    def filas(self):
        _, seleccion = _piezas()
        return comparative_rows(seleccion, SGEP_SCAFFOLD)

    def test_es_una_secuencia_de_22_nt(self):
        filas = self.filas()
        indice = filas[0].index("pasajera")
        for fila in filas[1:]:
            with self.subTest(fila[indice]):
                self.assertEqual(len(fila[indice]), 22)

    def test_solo_lleva_bases(self):
        filas = self.filas()
        indice = filas[0].index("pasajera")
        for fila in filas[1:]:
            with self.subTest(fila[indice]):
                self.assertLessEqual(set(fila[indice]), set("ACGTU"))

    def test_no_lleva_el_repr_de_ningun_objeto(self):
        # Guarda generica: ninguna celda de la tabla puede ser un `repr`. Si alguien
        # olvida un `.sequence` o un `.value` en otra columna, salta aqui.
        filas = self.filas()
        for fila in filas[1:]:
            for columna, celda in zip(filas[0], fila):
                with self.subTest(columna=columna):
                    self.assertNotIn("=", celda.split("(")[0] + "(")
                    self.assertNotRegex(celda, r"^[A-Z][A-Za-z]+\(.*=")

    def test_coincide_con_la_pasajera_del_TSV_de_oligos(self):
        # Las dos salidas describen el mismo oligo: si no coinciden, una miente.
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        indice = filas[0].index("pasajera")
        oligos = tsv_oligos(seleccion, SGEP_SCAFFOLD, species="sonda").splitlines()
        cabecera = oligos[0].split("\t")
        col = cabecera.index("pasajera")
        de_oligos = [l.split("\t")[col] for l in oligos[1:]]
        self.assertEqual([f[indice] for f in filas[1:]], de_oligos)


class TestNotaDeCoordenadas(unittest.TestCase):
    """La cabecera tiene que decir en que marco va cada pareja de coordenadas.

    Cuando lo que se tila YA es un 3'UTR no hay offset, asi que `inicio_transcrito`
    sale igual que `inicio_3utr`. Los numeros son correctos; lo que no puede pasar es
    que alguien lea `inicio_transcrito = 21` dentro de seis meses y entienda que es la
    posicion 21 de NM_011170.3. La cabecera lo dice con todas las letras, y dice ademas
    de donde salio la anatomia.
    """

    def tsv(self, anatomia):
        _, seleccion = _piezas()
        return comparative_tsv(
            seleccion, SGEP_SCAFFOLD, with_header=True, anatomy=anatomia
        )

    def _sin_marco(self):
        return Anatomy.whole_is_utr3(
            len(SONDA), source=RegionSource.TODO_3UTR_DECLARADO
        )

    def _con_cds(self):
        return Anatomy.from_cds(
            cds=(45, 146), length=len(SONDA), source=RegionSource.CDS_DECLARADA
        )

    def cabecera(self, anatomia):
        return "\n".join(
            l for l in self.tsv(anatomia).splitlines() if l.startswith("#")
        )

    def test_sin_marco_de_transcrito_lo_dice(self):
        cabecera = self.cabecera(self._sin_marco())
        self.assertIn("no son coordenadas de ningun transcrito", cabecera)

    def test_sin_marco_avisa_de_que_las_dos_parejas_coinciden(self):
        self.assertIn("coinciden", self.cabecera(self._sin_marco()))

    def test_con_CDS_declarado_NO_dice_que_coincidan(self):
        # Ahi si hay offset y las dos parejas son cosas distintas.
        self.assertNotIn("coinciden", self.cabecera(self._con_cds()))

    def test_siempre_dice_de_donde_salio_la_anatomia(self):
        for anatomia in (self._sin_marco(), self._con_cds()):
            with self.subTest(anatomia.source.value):
                self.assertIn(anatomia.source.describe(), self.cabecera(anatomia))

    def test_sin_anatomia_dice_que_no_se_declaro(self):
        # Nadie deberia llamar asi, pero si pasa, el fichero no puede quedarse mudo.
        _, seleccion = _piezas()
        cabecera = comparative_tsv(seleccion, SGEP_SCAFFOLD, with_header=True)
        self.assertIn("no se declaro", cabecera)

    def test_el_bloque_del_informe_tambien_lo_dice(self):
        _, seleccion = _piezas()
        texto = comparative_text(seleccion, SGEP_SCAFFOLD, anatomy=self._sin_marco())
        self.assertIn("no son coordenadas de ningun transcrito", texto)

    def test_las_columnas_no_cambian_de_nombre_ni_de_sitio(self):
        # El esquema es estable: lo que cambia es lo que se explica de el.
        _, seleccion = _piezas()
        con = comparative_rows(seleccion, SGEP_SCAFFOLD, anatomy=self._sin_marco())[0]
        sin = comparative_rows(seleccion, SGEP_SCAFFOLD)[0]
        self.assertEqual(con, sin)


class TestMarcoDeLasColumnasDePolyA(unittest.TestCase):
    """La posicion del hexamero va en el marco de lo tilado, y se dice cual es.

    Es el mismo cuidado que con las dos parejas de coordenadas: un `1983` leido dentro
    de un año no dice por si solo si es del transcrito o del 3'UTR.
    """

    def test_la_cabecera_nombra_las_dos_columnas_de_polyA(self):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.comparative import coordinate_note

        nota = coordinate_note(
            Anatomy.from_cds(cds=(45, 146), length=586, source=RegionSource.CDS_DECLARADA)
        )
        self.assertIn("polyA_hexamero_pos", nota)
        self.assertIn("polyA_dist_extremo3", nota)

    def test_y_dice_en_que_marco_van(self):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.comparative import coordinate_note

        nota = coordinate_note(
            Anatomy.from_cds(cds=(45, 146), length=586, source=RegionSource.CDS_DECLARADA)
        )
        self.assertIn("marco de LO TILADO", nota)
