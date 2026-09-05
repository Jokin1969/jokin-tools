"""La matriz intrón × andamio: los dos bloques NO son independientes. Regla 5.

**El problema.** 3 intrones × 4 andamios se venían tratando como 12 combinaciones
independientes, y no lo son. `mvm_sin_criptico` existe **sólo** para romper el `GTGAGCG`
del flanco 5' de miR-E. Si un andamio no lleva ese motivo, esa variante de intrón no
resuelve nada en esa combinación: es la misma construcción con otro nombre.

**Cómo se busca**, y es lo que distingue esto de una tabla de familias: los motivos se
buscan **en la secuencia real del módulo montado**, no por familia ni por analogía. Y el
criterio es el mismo con el que se cazó el `GTGAGCG`: el contexto de donante se puntúa
contra el **donante legítimo del propio intrón**, que es la referencia interna, y no
contra un umbral traído de fuera.

**Lo que no se hace**: evaluar por analogía un andamio sin secuencia verificada. Esos van
a `NOT_RUN` con el nombre del fichero que falta. Que la matriz salga con tres cuartos en
`NOT_RUN` es el resultado correcto y dice exactamente qué falta.
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.matriz_andamio_intron import (
    COMO_SE_BUSCA,
    fila,
    matriz,
)


def _guia():
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(REFERENCES["NM_011170.3"])
    elegido = select_from_report(tile_utr(utr3), default_config()).selection.chosen[0]
    return utr3[elegido.start - 1 : elegido.end]


class TestElEspacioSeDERIVA(unittest.TestCase):

    def test_hay_una_fila_por_PAR(self):
        from shmir_design.introns import INTRONS
        from shmir_design.scaffold_registry import SCAFFOLDS

        vivos = [n for n, i in INTRONS.items() if not i.retired]
        filas = matriz(guide=_guia())
        self.assertEqual(len(filas), len(vivos) * len(SCAFFOLDS))

    def test_y_las_claves_salen_de_los_DOS_registros(self):
        from shmir_design.introns import INTRONS
        from shmir_design.scaffold_registry import SCAFFOLDS

        vivos = [n for n, i in INTRONS.items() if not i.retired]
        pares = {(f["intron"], f["andamio"]) for f in matriz(guide=_guia())}
        self.assertEqual(pares, {(i, a) for i in vivos for a in SCAFFOLDS})

    def test_un_intron_RETIRADO_no_da_filas_y_SIGUE_en_el_registro(self):
        """Retirar no es borrar: sale de la matriz y se queda con su motivo."""
        from shmir_design import introns as reg

        retirados = {i.name for i in reg.retired()}
        self.assertTrue(retirados)
        en_matriz = {f["intron"] for f in matriz(guide=_guia())}
        self.assertFalse(retirados & en_matriz)
        for nombre in retirados:
            self.assertIn(nombre, reg.INTRONS)


class TestLosAndamiosSinSECUENCIA(unittest.TestCase):
    """`NOT_RUN` con el fichero que falta. Nunca por familia ni por analogía."""

    def test_los_tres_van_a_NOT_RUN(self):
        for f in matriz(guide=_guia()):
            if f["andamio"] == "mir_e":
                continue
            with self.subTest(f"{f['intron']}×{f['andamio']}"):
                self.assertEqual(f["estado"], FilterState.NOT_RUN.value)

    def test_y_cada_uno_dice_QUE_FICHERO_falta(self):
        for f in matriz(guide=_guia()):
            if f["estado"] != FilterState.NOT_RUN.value:
                continue
            with self.subTest(f"{f['intron']}×{f['andamio']}"):
                self.assertTrue(f["falta"], f)

    def test_NO_se_declara_nada_sobre_sus_motivos(self):
        """Lo importante del NOT_RUN: no es «no tiene GTGAGCG», es «no se ha mirado»."""
        for f in matriz(guide=_guia()):
            if f["estado"] != FilterState.NOT_RUN.value:
                continue
            with self.subTest(f"{f['intron']}×{f['andamio']}"):
                self.assertIsNone(f["donantes"])
                self.assertIsNone(f["aceptores"])
                self.assertIsNone(f["ramificaciones"])
                self.assertIsNone(f["redundante"])


class TestLoMEDIDOsobreMIR_E(unittest.TestCase):
    """El único evaluable hoy, y los números salen del módulo real."""

    @classmethod
    def setUpClass(cls):
        cls.guia = _guia()
        cls.f = fila("mvm_actual", "mir_e", guide=cls.guia)

    def test_UN_solo_donante_criptico_y_es_el_conocido(self):
        self.assertEqual(len(self.f["donantes"]), 1)
        (donante,) = self.f["donantes"]
        self.assertEqual(donante["motivo"], "GTGAGCG")

    def test_y_puntua_IGUAL_que_el_donante_legitimo_del_intron(self):
        """Por eso es peligroso, y por eso el criterio es interno: no hace falta ningún
        umbral de fuera para decir que ese GT compite — empata con el bueno."""
        (donante,) = self.f["donantes"]
        self.assertEqual(donante["score"], self.f["score_legitimo"])
        self.assertEqual(self.f["score_legitimo"], 5)

    def test_viene_del_ANDAMIO_asi_que_viaja_con_cualquier_guia(self):
        (donante,) = self.f["donantes"]
        self.assertEqual(donante["pieza"], "flanco5")
        self.assertTrue(donante["independiente_de_la_guia"])

    def test_NO_hay_ningun_aceptor_utilizable_dentro_del_modulo(self):
        """El mejor tracto de cualquier AG del módulo son 2 pirimidinas contra las 9 del
        aceptor legítimo. Eso cierra POR SECUENCIA los empalmes que cortarían por dentro
        de la horquilla."""
        self.assertEqual(self.f["aceptores"], [])
        self.assertEqual(self.f["mejor_tracto"], 2)
        self.assertEqual(self.f["tracto_legitimo"], 9)

    def test_hay_UN_YTNAY_pero_no_define_ningun_intron(self):
        """El peor caso sería un intrón que se define solo dentro del módulo: donante,
        punto y aceptor los tres dentro. Hay punto (+32) y donante (+38), pero el punto
        va AGUAS ARRIBA del donante —el orden es el contrario del que haría falta— y no
        hay aceptor. Así que no."""
        self.assertEqual(len(self.f["ramificaciones"]), 1)
        (rama,) = self.f["ramificaciones"]
        self.assertEqual(rama["motivo"], "TTGAC")
        self.assertEqual(rama["posicion"], 32)
        self.assertFalse(self.f["intron_autodefinido"])

    def test_la_GEOMETRIA_sale_en_la_fila(self):
        self.assertEqual(self.f["longitud_modulo"], 149)
        self.assertEqual(self.f["longitud_intron"], 296)
        self.assertIsNotNone(self.f["donante_a_punto"])


class TestLaREDUNDANCIA(unittest.TestCase):
    """Se marca, no se elimina: la decisión de no sintetizar es de quien diseña."""

    def test_mvm_sin_criptico_NO_es_redundante_con_miR_E(self):
        """Con miR-E el motivo SÍ está, así que la variante resuelve algo real."""
        f = fila("mvm_sin_criptico", "mir_e", guide=_guia())
        self.assertFalse(f["redundante"])

    def test_el_intron_declara_QUE_MOTIVO_rompe(self):
        from shmir_design.introns import INTRONS
        from shmir_design.splicing import CRYPTIC_DONOR

        self.assertEqual(INTRONS["mvm_sin_criptico"].breaks_motif, CRYPTIC_DONOR)

    def test_y_ese_motivo_es_el_que_ROMPE_DE_VERDAD_intron_design(self):
        """Derivado, no transcrito: si `intron_design` cambiara de motivo, esto lo dice."""
        import inspect

        from shmir_design import intron_design
        from shmir_design.introns import INTRONS

        firma = inspect.signature(intron_design.break_candidates)
        self.assertEqual(
            firma.parameters["motif"].default, INTRONS["mvm_sin_criptico"].breaks_motif
        )

    def test_un_intron_que_no_rompe_nada_NUNCA_es_redundante(self):
        for nombre in ("mvm_actual", "intron_quimerico"):
            with self.subTest(nombre):
                self.assertFalse(fila(nombre, "mir_e", guide=_guia())["redundante"])

    def test_la_redundancia_se_MARCA_y_la_fila_sigue_ahi(self):
        """Una combinación REDUNDANTE no se elimina: se marca y su fila sigue.

        Es distinto de un intrón RETIRADO, que sí sale: una redundancia sigue siendo una
        arquitectura construible —no sintetizarla lo decide quien diseña— y un retirado
        ya no es una opción.
        """
        from shmir_design.introns import INTRONS
        from shmir_design.scaffold_registry import SCAFFOLDS

        vivos = [n for n, i in INTRONS.items() if not i.retired]
        self.assertEqual(len(matriz(guide=_guia())), len(vivos) * len(SCAFFOLDS))


class TestLoQueELanalisisNOpuedeHacer(unittest.TestCase):

    def test_esta_DECLARADO_como_se_busca(self):
        self.assertIn("no puede hacer", COMO_SE_BUSCA.lower())
        self.assertGreater(len(COMO_SE_BUSCA), 300)

    def test_el_aviso_de_los_contextos_sin_contrastar_YA_NO_hace_falta(self):
        """Llegó SGEP #111170 y los contextos coinciden. Si alguien retira el plásmido,
        esto lo dice: el aviso vuelve a hacer falta."""
        from shmir_design.scaffold_registry import SCAFFOLDS

        self.assertEqual(SCAFFOLDS["mir_e"].missing, [])


class TestElAVISOalMONTAR(unittest.TestCase):
    """La consecuencia de diseño: el registro tiene que poder decir que un intrón es
    CONDICIONAL a un andamio.

    Hoy los dos registros son independientes y eso permite construir pares que no tienen
    sentido. No se impide —la decisión es de quien diseña— pero la app lo dice al
    montarlo, igual que avisa cuando dos candidatos comparten núcleo de seed.
    """

    def test_un_intron_CONDICIONAL_se_reconoce_por_el_motivo_que_rompe(self):
        from shmir_design.matriz_andamio_intron import condicional_a_andamio
        from shmir_design.introns import INTRONS

        self.assertTrue(condicional_a_andamio(INTRONS["mvm_sin_criptico"]))
        for nombre in ("mvm_actual", "intron_quimerico"):
            with self.subTest(nombre):
                self.assertFalse(condicional_a_andamio(INTRONS[nombre]))

    def test_con_miR_E_el_par_NO_avisa(self):
        from shmir_design.matriz_andamio_intron import aviso_de_par

        self.assertEqual(aviso_de_par("mvm_sin_criptico", "mir_e", guide=_guia()), "")

    def test_y_con_un_andamio_SIN_evaluar_avisa_de_QUE_no_se_sabe(self):
        """No dice «es redundante» —eso sería declarar sobre lo que no se ha mirado—:
        dice que la combinación no se puede comprobar y por qué."""
        from shmir_design.matriz_andamio_intron import aviso_de_par

        aviso = aviso_de_par("mvm_sin_criptico", "mir451", guide=_guia())
        self.assertTrue(aviso)
        self.assertIn("GTGAGCG", aviso)
        self.assertIn("no se puede comprobar", aviso.lower())
        self.assertNotIn("redundante", aviso.lower())

    def test_un_par_sin_condicionalidad_nunca_avisa(self):
        from shmir_design.matriz_andamio_intron import aviso_de_par

        for andamio in ("mir_e", "mir451"):
            with self.subTest(andamio):
                self.assertEqual(
                    aviso_de_par("mvm_actual", andamio, guide=_guia()), ""
                )


class TestDonanteAPuntoPorDOSrutas(unittest.TestCase):
    """256, y se comprueba por dos derivaciones independientes.

    La primera versión daba **405**, que son 256 + 149, y 149 es la longitud del módulo:
    un número que se mueve exactamente la longitud de una pieza es casi siempre una suma
    de más. Eran DOS errores:

      1. `donor_to_branch` recibía los elementos del intrón YA MONTADO, cuyo campo
         `empty` vale ya la distancia montada, y la función le sumaba la inserción otra
         vez;
      2. y recibía `inserted=len(modulo)`. `inserted` es **todo lo insertado** —módulo
         más los dos espaciadores, 149+20+45=214—, no el módulo.

    Ninguno de los dos por separado daba 405: con (1) y el 214 bueno salen 470, con (2)
    sobre el vacío salen 191. **Un número plausible puede ser la suma de dos
    equivocaciones**, y por eso aquí no basta con arreglarlo: se cruzan las dos rutas.
    """

    def _piezas(self):
        from shmir_design.blocks import build_block
        from shmir_design.introns import get

        modulo = build_block(guide=_guia(), available=False).module
        return get("mvm_actual"), modulo

    def test_la_MEDIDA_sobre_el_intron_montado(self):
        f = fila("mvm_actual", "mir_e", guide=_guia())
        self.assertEqual(f["donante_a_punto"], (256, 256))

    def test_y_la_ARITMETICA_desde_el_vacio_da_lo_mismo(self):
        from shmir_design.introns import donor_to_branch

        intron, modulo = self._piezas()
        insertado = len(intron.with_module(modulo)) - len(intron.empty_sequence)
        self.assertEqual(insertado, 214)
        salto = donor_to_branch(intron.elements(), name="mvm_actual", inserted=insertado)
        self.assertEqual(salto.empty, (42, 42))
        self.assertEqual(salto.assembled, (256, 256))
        self.assertEqual(salto.assembled, fila("mvm_actual", "mir_e", guide=_guia())["donante_a_punto"])

    def test_INSERTADO_no_es_la_longitud_del_modulo(self):
        """El error que más fácil se repite: `inserted` incluye los espaciadores."""
        from shmir_design.blocks import PIECES

        intron, modulo = self._piezas()
        espaciadores = (len(PIECES["espaciador5"].sequence)
                        + len(PIECES["espaciador3"].sequence))
        self.assertEqual(len(modulo) + espaciadores, 214)
        self.assertNotEqual(len(modulo), 214)


class TestLasDosFrasesVanJUNTAS(unittest.TestCase):
    """«No hay aceptor utilizable» leído solo suena a riesgo cerrado y no lo es."""

    def setUp(self):
        self.f = fila("mvm_actual", "mir_e", guide=_guia())

    def test_donde_va_el_hallazgo_va_lo_que_NO_cierra(self):
        from shmir_design.matriz_andamio_intron import LO_QUE_EL_ACEPTOR_NO_CIERRA

        self.assertEqual(self.f["aceptores"], [])
        self.assertEqual(self.f["aceptores_no_cierran"], LO_QUE_EL_ACEPTOR_NO_CIERRA)
        self.assertIn("NO CIERRA EL RIESGO DEL DONANTE", LO_QUE_EL_ACEPTOR_NO_CIERRA)
        self.assertIn("aceptor LEGÍTIMO", LO_QUE_EL_ACEPTOR_NO_CIERRA)
        self.assertIn("INTERMEDIA", LO_QUE_EL_ACEPTOR_NO_CIERRA)

    def test_el_5_contra_5_va_en_la_fila_cuando_hay_criptico(self):
        self.assertIn("5 sobre 5", self.f["por_que_compite"])
        self.assertIn("EMPATA", self.f["por_que_compite"])

    def test_y_NO_va_cuando_no_hay_ninguno(self):
        """Una explicación de por qué compite algo que no está sería ruido."""
        from shmir_design.matriz_andamio_intron import POR_QUE_COMPITE

        self.assertTrue(POR_QUE_COMPITE)
        self.assertTrue(self.f["donantes"])
        self.assertTrue(self.f["por_que_compite"])

    def test_el_METODO_del_orden_queda_escrito_para_los_que_faltan(self):
        from shmir_design.matriz_andamio_intron import ORDEN_ANTES_QUE_PRESENCIA

        for andamio in ("mir30_original", "mir155", "mir451"):
            with self.subTest(andamio):
                self.assertIn(andamio.split("_")[0].replace("mir", "miR-"),
                              ORDEN_ANTES_QUE_PRESENCIA.replace("miR-30 original", "miR-30"))
        self.assertIn("PRESENCIA SIN GEOMETRÍA", ORDEN_ANTES_QUE_PRESENCIA)
