"""Un ítem de `pending` declara QUÉ bloquea: el dato entero, o un veredicto.

Regla 5: escrito antes.

**El campo tenía UN solo significado y hacían falta DOS.** `pending` estaba documentado
como «comprobaciones que BLOQUEAN el uso del dato», y de ahí salía `usable`. Con esa
definición no cabe el ítem que el panel humano necesita escribir:

    3utr:1-248 declarado INMUNE; es falso para el 1,4% de transcritos que cortan en
    3utr:128-134; corrección pende de CutOnlySite

Ese ítem **no bloquea el dato** —la fracción sigue siendo 0,998 y sigue entrando— sino
un **veredicto categórico de un tramo**. Metido en el `pending` de antes, el informe
imprimía «El dato NO entra al pipeline todavía» encima de un informe que lo estaba
usando: la misma contradicción que el ítem viene a anotar.

**Y `usable` no lo leía nadie**, medido: con un `pending` puesto a mano, `resolve_measured`
seguía promoviendo las cuatro señales. O sea que el campo afirmaba un bloqueo que no
ocurría — la familia de la errata nº 29, un guardia que no guarda.

Lo que se fija aquí:

  · el alcance **se declara y no tiene valor por defecto** (principio nº 58). Un
    `# pendiente` a secas ABORTA diciendo cuál de las dos claves hay que usar: el
    defecto que saldría sería justo el que decide si el dato entra;
  · `usable` se DERIVA del alcance, así que deja de mentir en las dos direcciones;
  · el informe saca los dos grupos con **texto distinto**. Fundirlos deja un
    «no entra al pipeline» encima de un número que sí entró.
"""

import unittest

from shmir_design.apa import (
    PendingScope,
    find_polyadb,
    parse_polyadb,
    resolve_measured,
)
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

HUMANO = REFERENCES["NM_000311.5"]

CABECERA = "\n".join([
    "# fuente\tPolyA_DB",
    "# version\tv4.1",
    "# fecha\t2025-09-15",
    "# ensamblaje\thg38",
    "# gen\tPRNP",
    "# gen_id\t5621",
    "# pas_totales\t11",
    "# pas_con_expresion\t11",
    "# utr3_md5\tf7fdb4a88d4834dbbf9a23edf9ec85dc",
    "# tejido\tTODOS LOS TEJIDOS, no cerebro",
])
FILAS = "\n".join([
    "pas_id\tcoordenada\tclase\tpse\tavgrpm\tdistal\tnota",
    "chr20:+:4701587\t4701587\tAUUAAA\t0.937\t156.20\tsi\tterminal",
])


def _tabla(*cabeceras: str):
    texto = "\n".join([CABECERA, *cabeceras, FILAS])
    return parse_polyadb(texto, source="prueba")


class TestElAlcanceSeDECLARA(unittest.TestCase):

    def test_un_pendiente_SIN_alcance_aborta(self):
        # El defecto que saldria decide si el dato entra al pipeline, asi que no puede
        # haber defecto. Principio nº 58.
        with self.assertRaises(ShmirDesignError) as caso:
            _tabla("# pendiente\tfalta cruzar el techo con el 3'-end seq")
        mensaje = str(caso.exception)
        self.assertIn("pendiente_dato", mensaje)
        self.assertIn("pendiente_veredicto", mensaje)

    def test_pendiente_dato_bloquea_el_dato(self):
        tabla = _tabla("# pendiente_dato\tel anclaje no cierra")
        self.assertEqual([p.scope for p in tabla.pending], [PendingScope.DATO])
        self.assertFalse(tabla.usable)

    def test_pendiente_veredicto_NO_bloquea_el_dato(self):
        tabla = _tabla("# pendiente_veredicto\t3utr:1-248 declarado INMUNE")
        self.assertEqual([p.scope for p in tabla.pending], [PendingScope.VEREDICTO])
        self.assertTrue(tabla.usable)

    def test_varios_del_mismo_alcance_NO_se_pisan(self):
        # Van en una lista, como las reservas: en un diccionario el segundo borraria al
        # primero y el aviso desapareceria sin dar ningun error.
        tabla = _tabla(
            "# pendiente_veredicto\tprimero",
            "# pendiente_veredicto\tsegundo",
        )
        self.assertEqual([p.text for p in tabla.pending], ["primero", "segundo"])

    def test_y_un_alcance_manda_sobre_el_otro(self):
        tabla = _tabla(
            "# pendiente_veredicto\tno bloquea",
            "# pendiente_dato\testo si",
        )
        self.assertFalse(tabla.usable)


class TestElInformeNoFUNDElosDosGrupos(unittest.TestCase):

    def test_el_que_bloquea_el_dato_dice_que_NO_entra(self):
        texto = "\n".join(_tabla("# pendiente_dato\tel anclaje no cierra").describe())
        self.assertIn("NO entra al pipeline", texto)
        self.assertIn("el anclaje no cierra", texto)

    def test_el_que_bloquea_un_VEREDICTO_dice_que_el_dato_SI_entra(self):
        texto = "\n".join(
            _tabla("# pendiente_veredicto\t3utr:1-248 declarado INMUNE").describe()
        )
        self.assertIn("3utr:1-248 declarado INMUNE", texto)
        self.assertNotIn("NO entra al pipeline", texto)
        # Y no se puede leer como «sin nada pendiente», que es la otra forma de mentir.
        self.assertNotIn("SIN COMPROBACIONES PENDIENTES", texto)

    def test_sin_ninguno_sigue_diciendo_que_no_hay_pendientes(self):
        texto = "\n".join(_tabla().describe())
        self.assertIn("SIN COMPROBACIONES PENDIENTES", texto)


@unittest.skipUnless(fixture_available(HUMANO), "NOT_RUN: falta el fixture humano")
class TestElItemDelPanelHUMANO(unittest.TestCase):
    """El texto exacto que el responsable del proyecto pidió que constara."""

    TEXTO = (
        "3utr:1-248 declarado INMUNE; es falso para el 1,4% de transcritos que cortan "
        "en 3utr:128-134; corrección pende de CutOnlySite"
    )

    @classmethod
    def setUpClass(cls):
        cls.tabla = find_polyadb(species="human")

    def test_esta_escrito_LITERAL(self):
        self.assertIn(self.TEXTO, [p.text for p in self.tabla.pending])

    def test_y_NO_bloquea_el_dato(self):
        self.assertTrue(self.tabla.usable)

    def test_asi_que_las_cuatro_señales_siguen_entrando(self):
        medida = resolve_measured(load_3utr(HUMANO), self.tabla)
        self.assertIsNotNone(medida)
        self.assertEqual(medida.signal_starts, (233, 955, 1167, 1582))

    def test_y_el_informe_lo_saca_SIN_decir_que_el_dato_no_entra(self):
        texto = "\n".join(self.tabla.describe())
        self.assertIn(self.TEXTO, texto)
        self.assertNotIn("NO entra al pipeline", texto)


if __name__ == "__main__":
    unittest.main()
