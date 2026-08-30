"""El registro de andamios: qué tiene cada uno y qué le falta.

Regla 5: escrito antes que el registro.

**Por qué existe.** Cambiar de andamio NO es sustituir un flanco: es rediseñar el módulo
entero. Hoy `blocks.PIECES` sólo tiene miR-E y `verify_contexts_against_plasmid` compara
contra el plásmido de SGEP. Con cuatro andamios sobre la mesa —miR-E, miR-30 original,
miR-155 y miR-451— hace falta la misma disciplina que con los intrones: **secuencia
verificada de fichero, nunca tecleada** (regla 1).

**Y la regla de la pasajera pasa a ser PROPIEDAD DEL ANDAMIO, no constante global.** El
precedente está medido y es del tamaño de la diferencia: la pasajera de miR-30a de
miRarchitect es `revcomp(guía)[0:9] + revcomp(guía)[11:22] + "GC"` —dos nucleótidos
borrados tras la posición 9 y un `GC` terminal— y la de miR-E es revcomp con
desapareamiento en la posición 1 elegido **plegando contra SGEP**. No se parecen en nada.

Lo que se fija aquí es que **la app se niegue a montar un módulo con un andamio
incompleto**, en vez de montarlo con una regla prestada.
"""

import unittest

from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.scaffold_registry import (
    SCAFFOLDS,
    inventory,
    require_verified,
)


class TestLosCuatroEstanDECLARADOS(unittest.TestCase):

    def test_estan_los_cuatro(self):
        self.assertEqual(
            sorted(SCAFFOLDS), ["mir155", "mir30_original", "mir451", "mir_e"]
        )

    def test_solo_miR_E_esta_COMPLETO(self):
        listos = [n for n, a in SCAFFOLDS.items() if a.state is FilterState.PASS]
        self.assertEqual(listos, ["mir_e"])

    def test_los_otros_tres_estan_en_NOT_RUN_no_en_FAIL(self):
        """No es que fallen: es que no se ha corrido nada con ellos. Regla 3."""
        for nombre in ("mir30_original", "mir155", "mir451"):
            with self.subTest(nombre):
                self.assertIs(SCAFFOLDS[nombre].state, FilterState.NOT_RUN)

    def test_cada_hueco_dice_POR_QUE_y_QUE_LO_CERRARIA(self):
        for nombre, andamio in SCAFFOLDS.items():
            if andamio.state is FilterState.PASS:
                continue
            with self.subTest(nombre):
                self.assertGreater(len(andamio.why_missing), 80, nombre)
                self.assertGreater(len(andamio.como_conseguirlo), 80, nombre)


class TestLaSecuenciaSALEdeUnFICHERO(unittest.TestCase):
    """Regla 1, y la misma que cerró el intrón quimérico: `provided` se DERIVA de si hay
    secuencia, no se declara. Un campo declarado dio un PASS falso una vez."""

    def test_ninguna_secuencia_esta_TECLEADA_en_el_registro(self):
        import inspect

        from shmir_design import scaffold_registry

        fuente = inspect.getsource(scaffold_registry)
        for linea in fuente.splitlines():
            crudo = linea.strip().strip('"').strip("'")
            if len(crudo) >= 20 and set(crudo) <= set("ACGTU"):
                self.fail(f"Secuencia tecleada en el registro: {crudo[:40]}")

    def test_la_de_miR_E_viene_del_andamio_VERIFICADO(self):
        from shmir_design.scaffold import SGEP_SCAFFOLD

        self.assertIs(SCAFFOLDS["mir_e"].spec, SGEP_SCAFFOLD)
        self.assertTrue(SGEP_SCAFFOLD.verified)

    def test_los_que_no_tienen_fichero_tienen_spec_None(self):
        for nombre in ("mir30_original", "mir155", "mir451"):
            with self.subTest(nombre):
                self.assertIsNone(SCAFFOLDS[nombre].spec)


class TestLaPasajeraEsPROPIEDADdelAndamio(unittest.TestCase):

    def test_miR_E_trae_la_suya_con_su_CRITERIO(self):
        regla = SCAFFOLDS["mir_e"].passenger_rule
        self.assertIsNotNone(regla)
        self.assertIn("pleg", regla.criterion.lower())
        self.assertTrue(regla.derived_from)

    def test_los_otros_tres_NO_heredan_la_de_miR_E(self):
        """Prestarla es exactamente el fallo que este registro existe para impedir."""
        for nombre in ("mir30_original", "mir155", "mir451"):
            with self.subTest(nombre):
                self.assertIsNone(SCAFFOLDS[nombre].passenger_rule)

    def test_el_precedente_MEDIDO_de_miR_30a_esta_registrado_como_lo_que_es(self):
        """`mirarchitect.passenger_of` está verificada contra 26 filas del export y NO
        se usa para diseñar. Es la medida del tamaño de la diferencia entre andamios, no
        una regla que se pueda adoptar."""
        andamio = SCAFFOLDS["mir30_original"]
        self.assertIn("miRarchitect", andamio.precedent)
        self.assertIn("no se adopta", andamio.precedent.lower())
        self.assertIsNone(andamio.passenger_rule)


class TestLaAppSeNIEGAaMontarConUnoIncompleto(unittest.TestCase):
    """El guardia. Montarlo con una regla prestada saldría con la forma correcta, que es
    peor que no salir — la misma razón que `VECTOR_SPECIES`."""

    def test_con_miR_E_deja(self):
        self.assertIs(require_verified("mir_e"), SCAFFOLDS["mir_e"])

    def test_con_los_otros_tres_ABORTA(self):
        for nombre in ("mir30_original", "mir155", "mir451"):
            with self.subTest(nombre):
                with self.assertRaises(ShmirDesignError) as caja:
                    require_verified(nombre)
                mensaje = str(caja.exception)
                self.assertIn(nombre, mensaje)
                # El aborto DICE qué falta, no sólo que falta.
                self.assertTrue(len(mensaje) > 120, mensaje)

    def test_un_andamio_DESCONOCIDO_tambien_aborta(self):
        with self.assertRaises(ShmirDesignError):
            require_verified("mir_inventado")


class TestElINVENTARIO(unittest.TestCase):
    """«Emite, por andamio, qué tiene y qué le falta.»"""

    def test_una_fila_por_andamio_con_las_dos_columnas(self):
        filas = inventory()
        self.assertEqual(len(filas), len(SCAFFOLDS))
        for fila in filas:
            with self.subTest(fila["andamio"]):
                self.assertIsInstance(fila["tiene"], list)
                self.assertIsInstance(fila["falta"], list)

    def test_miR_E_MONTA_pero_le_falta_su_PLASMIDO(self):
        """Lo daba por completo y no lo está, y salió al montar el registro: SGEP
        #111170 NO está en el repositorio. El 97-mero sí está verificado —contra la
        publicación y el plegado— así que monta; lo que nadie ha contrastado contra un
        fichero son los CONTEXTOS, y `verify_contexts_against_plasmid` queda en NOT_RUN
        en toda corrida real. Su test monta un plásmido sintético de N's con los dos
        contextos dentro: prueba el comprobador, no las coordenadas."""
        fila = next(f for f in inventory() if f["andamio"] == "mir_e")
        self.assertEqual(fila["estado"], "PASS")
        self.assertEqual(len(fila["falta"]), 1, fila["falta"])
        self.assertIn("plásmido", fila["falta"][0])

    def test_y_montar_NO_depende_del_plasmido(self):
        """Los dos ejes, separados: fundirlos dejaría `mir_e` en NOT_RUN y la app
        dejaría de emitir lo único que hoy emite bien."""
        require_verified("mir_e")

    def test_y_los_otros_tres_tienen_MAS_de_una_cosa_pendiente(self):
        for fila in inventory():
            if fila["andamio"] == "mir_e":
                continue
            with self.subTest(fila["andamio"]):
                self.assertGreaterEqual(len(fila["falta"]), 2, fila["falta"])


class TestLoQueTRAENdeVerdadLosDosPLASMIDOS(unittest.TestCase):
    """Lo que se leyó DE LOS FICHEROS, no lo que dice su título.

    Ninguno de los dos trae el andamio como feature, y eso es el hallazgo: #20670 anota
    el **loop** de 15 nt —no el andamio— y #78126 no anota ninguna feature de miARN.
    Buscarlo por secuencia contra una construida por nosotros sería justamente lo que la
    regla 1 prohíbe.
    """

    def test_el_20670_trae_el_LOOP_y_no_el_andamio(self):
        andamio = SCAFFOLDS["mir30_original"]
        self.assertEqual(andamio.plasmid, "addgene_20670.gb")
        self.assertIsNotNone(andamio.loop_feature)
        self.assertIn("loop", andamio.loop_feature[1].lower())
        self.assertIsNone(andamio.scaffold_feature)

    def test_el_78126_no_trae_NINGUNA_feature_de_miARN(self):
        andamio = SCAFFOLDS["mir155"]
        self.assertEqual(andamio.plasmid, "addgene_78126.gb")
        self.assertIsNone(andamio.scaffold_feature)
        self.assertIsNone(andamio.loop_feature)


class TestElHUECOsinAnotarSeDERIVAdelFichero(unittest.TestCase):
    """El número que hay en la ficha de obtención de miR-155 no está transcrito.

    Lo escribí primero de cabeza —«222 nt en 882..1103»— y al medirlo salieron **215 nt
    en 883..1097**. Principio nº 13: se deriva o no se escribe. Este test lo cruza contra
    las anotaciones del fichero real, así que un export distinto lo dice.
    """

    def _huecos(self):
        import re
        from pathlib import Path

        from shmir_design.genbank import _features

        raiz = Path(__file__).resolve().parent.parent
        texto = (raiz / "data" / "reference" / "addgene_78126.gb").read_text(
            encoding="utf-8"
        )
        ocupado = sorted(
            (int(a), int(b))
            for tipo, loc, _ in _features(texto)
            if tipo != "source"
            for a, b in re.findall(r"(\d+)\.\.(\d+)", loc)
        )
        huecos, cursor = [], 1
        for a, b in ocupado:
            if a > cursor:
                huecos.append((cursor, a - 1))
            cursor = max(cursor, b + 1)
        return huecos

    def test_el_hueco_del_casete_es_el_que_dice_la_ficha(self):
        grandes = [(a, b) for a, b in self._huecos() if b - a + 1 > 50 and a < 1400]
        self.assertIn((883, 1097), grandes)
        ficha = SCAFFOLDS["mir155"].como_conseguirlo
        self.assertIn("883..1097", ficha)
        self.assertIn("215 nt", ficha)

    def test_y_ese_hueco_NO_es_el_unico_del_plasmido(self):
        """Para que nadie lo lea como «ahí está el andamio»: hay seis huecos de más de
        100 nt en el plásmido. El del casete es el único donde el inserto PUEDE estar,
        por su posición entre el promotor y el terminador — no porque se haya mirado
        dentro."""
        self.assertGreater(len([h for h in self._huecos() if h[1]-h[0]+1 > 100]), 1)
