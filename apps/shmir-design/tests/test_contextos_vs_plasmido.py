"""La comprobación de los contextos contra el plásmido CORRE, y corre siempre.

`verify_contexts_against_plasmid` existía desde el generador de bloques y sólo la
llamaban sus propios tests: una comprobación que aborta si los contextos del módulo no
coinciden con el vector real, escrita, probada, y sin correr nunca donde serviría de
algo. Es el patrón de `store.save_*` sobre algo más grave — aquí lo que no se contrasta
son secuencias que se van a PEDIR.

Ahora es el quinto `FilterResult` de `build_gblock`, así que corre en cada generación de
módulo. Y como depende de un recurso que HOY NO ESTÁ en el repositorio —el plásmido SGEP
depositado; `data/reference/aav_casete.fa` es pAAV con PrP murino y no lo contiene,
comprobado—, su estado sin él es `NOT_RUN` y no `PASS`: la regla 3 en su forma literal.
"""

import unittest

from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState, Verdict
from shmir_design.gblock import (
    CONTEXT_3,
    CONTEXT_5,
    CONTEXT_POSITIONS,
    build_gblock,
)
from shmir_design.scaffold import build_hairpin

from tests import plasmido_sgep as sgep

GUIA = "TATTTAATGTCAGTCTGATAGC"


#: EL PLASMIDO DE VERDAD. Aqui habia un relleno de A's con los dos contextos metidos en
#: sus coordenadas DECLARADAS, y eso probaba el comparador y no las coordenadas (principio
#: nº 18) — lo dice el propio registro. Desde que la comprobacion se ancla en la ANOTACION,
#: ademas es imposible: un relleno no tiene bloque FEATURES.
def plasmido() -> str:
    return sgep.texto()


class TestElQuintoCheck(unittest.TestCase):

    def test_el_modulo_lleva_la_comprobacion_de_contextos(self):
        nombres = [c.name for c in build_gblock(build_hairpin(GUIA)).checks]
        self.assertIn("contextos_vs_plasmido", nombres)

    def test_sin_plasmido_es_NOT_RUN_y_dice_que_falta(self):
        check = next(
            c for c in build_gblock(build_hairpin(GUIA)).checks
            if c.name == "contextos_vs_plasmido"
        )
        self.assertIs(check.state, FilterState.NOT_RUN)
        self.assertIn("plásmido", check.reason)

    def test_y_por_eso_el_modulo_sale_INCOMPLETE_no_PASS(self):
        # La consecuencia buscada: un módulo cuyos contextos NADIE ha contrastado con el
        # vector real no puede salir apto. Es la regla 3, y aquí lo que se pide con un
        # PASS falso es ADN.
        modulo = build_gblock(build_hairpin(GUIA))
        self.assertIs(modulo.verdict, Verdict.INCOMPLETE)
        self.assertFalse(modulo.ok)

    def test_con_el_plasmido_bueno_PASA_y_el_modulo_es_apto(self):
        modulo = build_gblock(build_hairpin(GUIA), plasmid=plasmido())
        check = next(c for c in modulo.checks if c.name == "contextos_vs_plasmido")
        self.assertIs(check.state, FilterState.PASS)
        self.assertIs(modulo.verdict, Verdict.PASS)
        self.assertTrue(modulo.ok)

    def test_con_un_plasmido_que_NO_coincide_ABORTA(self):
        # No es un FAIL de este candidato: si los contextos no son los del vector, TODOS
        # los módulos están mal, no éste. Un veredicto por candidato lo haría pasar por
        # un problema de la ventana. Se cambia UNA base del contexto 5' sobre el fichero
        # real, que es lo que hace de esto un control y no una comprobación de sí mismo.
        with self.assertRaises(ShmirDesignError) as ctx:
            build_gblock(
                build_hairpin(GUIA), plasmid=sgep.con_una_base_cambiada(1758)
            )
        self.assertIn("contexto_5", str(ctx.exception))

    def test_y_un_plasmido_demasiado_corto_tambien(self):
        with self.assertRaises(ShmirDesignError):
            build_gblock(build_hairpin(GUIA), plasmid="ACGT" * 100)

    def test_y_con_la_ANOTACION_movida_tambien(self):
        # La otra mitad del ancla: la anotación tiene que caer DENTRO del andamio
        # localizado por secuencia. Sin esto, anclarse en ella sería decorativo.
        with self.assertRaises(ShmirDesignError) as ctx:
            build_gblock(build_hairpin(GUIA), plasmid=sgep.con_la_anotacion_movida())
        self.assertIn("NO cae dentro", str(ctx.exception))


class TestElRecursoNOESTA(unittest.TestCase):

    def test_el_casete_AAV_no_es_el_plasmido_SGEP(self):
        # Comprobado, no supuesto: es el motivo por el que el estado por defecto es
        # NOT_RUN y no PASS. Si algún día alguien apunta la comprobación a este fichero
        # creyendo que vale, este test lo para.
        from pathlib import Path

        ruta = Path(__file__).resolve().parent.parent / "data" / "reference" / "aav_casete.fa"
        if not ruta.exists():
            self.skipTest(f"no está {ruta}")
        seq = "".join(
            l.strip() for l in ruta.read_text().splitlines() if not l.startswith(">")
        ).upper()
        self.assertNotIn(CONTEXT_5, seq)
        self.assertNotIn(CONTEXT_3, seq)


if __name__ == "__main__":
    unittest.main()


class TestElOTROGeneradorDeModulos(unittest.TestCase):
    """Hay DOS sitios que montan el módulo, y «en cada generación» son los dos.

    `gblock.build_gblock` monta el de 149 nt para los oligos; `blocks.build_block` monta
    ese MISMO módulo más el cassette y el intrón, y es el que alimenta la ficha. Cablear
    sólo el primero habría dejado la comprobación fuera justo del camino que se lee.
    """

    def test_el_bloque_lleva_la_comprobacion_de_contextos(self):
        from shmir_design.blocks import build_block

        bloque = build_block(GUIA, available=False)
        self.assertIn("contextos_vs_plasmido", [c.name for c in bloque.checks])

    def test_sin_plasmido_sale_en_not_run(self):
        from shmir_design.blocks import build_block

        bloque = build_block(GUIA, available=False)
        self.assertIn(
            "contextos_vs_plasmido", [c.name for c in bloque.not_run]
        )

    def test_con_el_plasmido_bueno_pasa(self):
        from shmir_design.blocks import build_block

        bloque = build_block(GUIA, available=False, plasmid=plasmido())
        self.assertIs(bloque.check("contextos_vs_plasmido").state, FilterState.PASS)


class TestLosDosGeneradoresUSANLASMISMASPIEZAS(unittest.TestCase):
    """El cuarto par duplicado, y éste es ADN.

    `blocks.py` monta el módulo con SUS piezas (`PIECES`) y `gblock.py` con SUS
    constantes. Hoy coinciden —comprobado aquí—, pero nada lo obligaba: si alguien
    corrige un contexto en un sitio, la ficha y los oligos empiezan a describir dos
    módulos distintos y no salta nada. Y la comprobación contra el plásmido usa las
    constantes de `gblock`, así que validaría un módulo que la ficha no monta.
    """

    def test_los_cuatro_trozos_son_LOS_MISMOS(self):
        from shmir_design import blocks
        from shmir_design.gblock import NHEI_SITE, SACI_SITE

        for nombre, esperado in (
            ("contexto5", CONTEXT_5),
            ("contexto3", CONTEXT_3),
            ("NheI", NHEI_SITE),
            ("SacI", SACI_SITE),
        ):
            with self.subTest(nombre=nombre):
                self.assertEqual(blocks._s(nombre), esperado)

    def test_pero_ademas_hay_UN_SOLO_ORIGEN__no_dos_que_coinciden(self):
        """Lo que de verdad cierra el par: `gblock` DERIVA de `blocks.PIECES`.

        Un test de cruce comprueba que la divergencia no ha pasado todavía; una
        definición única impide que pase. Con dos juegos de constantes, alguien corrige
        un contexto en un sitio, el test salta, y hay que decidir cuál de los dos tiene
        razón — y lo que se decide mal es ADN que se manda a sintetizar. Derivando, la
        pregunta no llega a existir.
        """
        import shmir_design.gblock as g
        from shmir_design import blocks

        # No basta con que sean iguales: tienen que ser EL MISMO objeto de cadena, que
        # es lo que sólo pasa si uno sale del otro y no de una segunda copia literal.
        for constante, pieza in (
            (g.CONTEXT_5, "contexto5"),
            (g.CONTEXT_3, "contexto3"),
            (g.NHEI_SITE, "NheI"),
            (g.SACI_SITE, "SacI"),
        ):
            with self.subTest(pieza=pieza):
                self.assertIs(constante, blocks.PIECES[pieza].sequence)

    def test_y_las_POSICIONES_en_el_plasmido_tambien_salen_de_la_pieza(self):
        # Estaban en un dict aparte de `gblock`, repitiendo lo que ya decía la
        # procedencia de la pieza. Tercera copia del mismo dato.
        from shmir_design import blocks

        for clave, pieza in (("contexto_5", "contexto5"), ("contexto_3", "contexto3")):
            with self.subTest(clave=clave):
                self.assertEqual(
                    CONTEXT_POSITIONS[clave], blocks.PIECES[pieza].span
                )

    def test_y_los_dos_montan_EL_MISMO_modulo(self):
        # El cruce de verdad: no que las piezas coincidan, sino que el resultado
        # coincida. Es lo que se pide sintetizar.
        from shmir_design.blocks import build_block
        from shmir_design.gblock import build_gblock
        from shmir_design.scaffold import build_hairpin

        self.assertEqual(
            build_block(GUIA, available=False).module,
            build_gblock(build_hairpin(GUIA)).sequence,
        )
