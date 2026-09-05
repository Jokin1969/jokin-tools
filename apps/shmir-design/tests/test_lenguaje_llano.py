"""La app se explica a quien NO ha estado en estas conversaciones.

**El criterio de aceptacion ya estaba escrito** en el bloque de la primera pantalla:
«alguien que no haya estado en estas conversaciones tiene que poder abrir la app y llegar
a un informe». Lo que faltaba es que el TEXTO lo cumpliera. Frases como «Determina el
prefijo de miRBase, el taxid y el ensamblaje» son correctas y **no se entienden si no
sabes ya lo que son** — y quien abre esto sabe que quiere apagar un mRNA de una especie,
no que existe miRBase.

**No se sustituye lo tecnico: se ANTEPONE lo llano.** El detalle sigue estando, un clic
mas adentro. Quitarlo seria perder la procedencia, que es justo lo que este proyecto no
hace; esconderlo detras de una frase que se entiende es otra cosa.

**Y el idioma llano tiene test porque si no se pudre.** La proxima frase que alguien
escriba en la pagina volvera a ser tecnica si nada lo impide: es el principio nº 11 —la
prosa se queda atras y es la que alguien lee— aplicado a la claridad en vez de a la
exactitud.
"""

import unittest

from shmir_design import obtencion, presentation, species as species_mod
from shmir_design.errors import ShmirDesignError

#: Palabras que NO puede haber en un texto de primera linea. No es una lista de palabras
#: prohibidas en la app —el detalle tecnico las usa y debe usarlas— sino de las que no
#: pueden aparecer en lo PRIMERO que se lee, sin haber sido explicadas antes.
JERGA = (
    "miRBase", "taxid", "ensamblaje", "NOT_RUN", "INCOMPLETE", "manifiesto",
    "md5", "frente", "tilado", "ventana", "3'UTR", "anatomia", "anatomía",
)


def _sin_jerga(texto: str) -> list[str]:
    return [j for j in JERGA if j.lower() in str(texto).lower()]


class TestLaAppDICE_PARA_QUE_SIRVE(unittest.TestCase):
    """Faltaba un inicio. Sin el, la primera pantalla es un formulario sin pregunta."""

    def test_hay_un_texto_de_INICIO(self):
        self.assertTrue(presentation.APP_PURPOSE.strip())

    def test_dice_QUE_HACE_en_lenguaje_llano(self):
        texto = presentation.APP_PURPOSE
        self.assertEqual(_sin_jerga(texto), [], f"jerga en el inicio: {texto}")

    def test_y_dice_QUE_HACE_FALTA_tener_a_mano(self):
        # Sin esto el inicio es un eslogan: quien lo lee sigue sin saber si puede empezar.
        self.assertTrue(presentation.WHAT_YOU_NEED.strip())
        self.assertEqual(_sin_jerga(presentation.WHAT_YOU_NEED), [])


class TestCadaPASOdiceQUEsePIDEyPORQUE(unittest.TestCase):

    def test_hay_guia_llana_de_los_pasos_QUE_HAY(self):
        # DERIVADA del numero de pasos, no una lista escrita aparte: un paso nuevo sin
        # su explicacion llana hace fallar la suite.
        from shmir_design.trabajo import reference_dir

        pasos = presentation.steps_rows(
            species="raton", sequence_loaded=False, directory=reference_dir()
        )
        for paso in pasos:
            with self.subTest(paso=paso["numero"]):
                guia = presentation.step_plain(int(paso["numero"]))
                self.assertTrue(guia["titulo"])
                self.assertTrue(guia["que_se_pide"])
                self.assertTrue(guia["por_que"])

    def test_y_esa_guia_NO_usa_jerga(self):
        for numero in (1, 2, 3, 4, 5):
            guia = presentation.step_plain(numero)
            for campo in ("titulo", "que_se_pide", "por_que"):
                with self.subTest(paso=numero, campo=campo):
                    self.assertEqual(_sin_jerga(guia[campo]), [])

    def test_un_paso_que_no_existe_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            presentation.step_plain(99)


class TestLaESPECIEseEXPLICAantesDeDarSusCODIGOS(unittest.TestCase):
    """«prefijo mmu-, taxid txid10090, ensamblaje mm39» no dice nada a quien empieza."""

    def test_la_frase_de_primera_linea_es_LLANA(self):
        nota = presentation.species_plain("raton")
        self.assertEqual(_sin_jerga(nota["texto"]), [], nota["texto"])

    def test_y_nombra_la_especie_por_su_nombre(self):
        self.assertIn("Mus musculus", presentation.species_plain("raton")["texto"])

    def test_el_DETALLE_tecnico_sigue_estando_y_lleva_los_tres_codigos(self):
        # Anteponer lo llano no es esconder la procedencia: el detalle esta, un clic
        # mas adentro, y con los tres identificadores que decide la eleccion.
        detalle = presentation.species_plain("raton")["detalle"]
        for codigo in ("mmu-", "txid10090", "mm39"):
            self.assertIn(codigo, detalle)

    def test_una_especie_SIN_declarar_dice_QUE_pierde_en_llano(self):
        nota = presentation.species_plain(presentation.OTHER_SPECIES)
        self.assertTrue(nota["texto"])
        self.assertEqual(_sin_jerga(nota["texto"]), [], nota["texto"])


class TestElSEMAFOROseENTIENDE(unittest.TestCase):
    """«Faltan 4 de 10 filtros» + tres cifras de ventanas era un parrafo, no un aviso."""

    def _luz(self):
        from tests.test_corrida_de_la_pagina import _entrada

        sec, anat = _entrada()
        corrida = presentation.page_run(species="raton", sequence=sec, anatomy=anat)
        return presentation.status_light(corrida.selection)

    def test_el_titular_es_UNA_frase_corta(self):
        titular = presentation.semaforo_plain(self._luz())["titular"]
        self.assertLessEqual(len(titular), 120, titular)

    def test_y_dice_lo_que_hay_que_hacer_AHORA(self):
        self.assertTrue(presentation.semaforo_plain(self._luz())["que_hacer"])

    def test_el_DETALLE_con_las_cifras_sigue_estando(self):
        # Las tres cifras de ventanas no se borran: dejan de ser lo primero que se lee.
        detalle = presentation.semaforo_plain(self._luz())["detalle"]
        self.assertIn("2170", detalle)


class TestLasTARJETASdeCOMPROBACIONES(unittest.TestCase):
    """Lo que se llamaba «frentes» son las comprobaciones que faltan, en tarjetas."""

    @classmethod
    def setUpClass(cls):
        from tests.test_corrida_de_la_pagina import _entrada

        sec, anat = _entrada()
        cls.corrida = presentation.page_run(
            species="raton", sequence=sec, anatomy=anat
        )
        cls.tarjetas = presentation.front_card_rows(cls.corrida, species="raton")

    def test_hay_UNA_tarjeta_por_frente_y_se_DERIVAN(self):
        from shmir_design.selection import blocking_fronts

        frentes = blocking_fronts(self.corrida.tiling, self.corrida.selection)
        self.assertEqual(len(self.tarjetas), len(frentes))

    def test_cada_tarjeta_tiene_TITULO_LLANO_y_sin_jerga(self):
        for t in self.tarjetas:
            with self.subTest(frente=t["frente"]):
                self.assertTrue(t["titulo"])
                self.assertEqual(_sin_jerga(t["titulo"]), [], t["titulo"])

    def test_y_dice_EN_CRISTIANO_que_comprueba(self):
        for t in self.tarjetas:
            with self.subTest(frente=t["frente"]):
                self.assertTrue(t["en_cristiano"])
                self.assertEqual(_sin_jerga(t["en_cristiano"]), [], t["en_cristiano"])

    def test_cada_una_lleva_ESTADO_y_COLOR_y_los_pone_presentation(self):
        # El color en la pagina seria una decision sin test (regla 6), como paso con
        # `REFINEMENT_STATES`.
        for t in self.tarjetas:
            with self.subTest(frente=t["frente"]):
                self.assertIn(t["estado"], presentation.CARD_STATES)
                self.assertTrue(t["color"])

    def test_hoy_NINGUNA_esta_hecha_y_eso_es_lo_que_se_ve(self):
        # Control adversario del progreso: si todas salieran HECHO, la barra no mediria
        # nada y el verde no significaria nada.
        self.assertTrue(any(t["estado"] == "SIN_HACER" for t in self.tarjetas))

    def test_el_PROGRESO_se_deriva_de_las_tarjetas(self):
        """Y cuenta SOLO lo que se puede cerrar aquí (errata nº 102).

        Con el frente de banco dentro del denominador, el máximo era inalcanzable: ese
        frente siempre bloquea, así que «N de N» no podía salir nunca. Va aparte y se
        nombra, que no es lo mismo que quitarlo.
        """
        progreso = presentation.front_progress(self.tarjetas)
        aqui = [t for t in self.tarjetas if t["cierra_aqui"]]
        banco = [t for t in self.tarjetas if not t["cierra_aqui"]]
        self.assertEqual(progreso["total"], len(aqui))
        self.assertEqual(progreso["en_el_banco"], len(banco))
        self.assertEqual(len(aqui) + len(banco), len(self.tarjetas))
        self.assertEqual(
            progreso["hechas"],
            sum(1 for t in aqui if t["estado"] == "HECHO"),
        )
        # El máximo tiene que ser ALCANZABLE: ninguna de las que cuentan puede estar
        # condenada a bloquear.
        self.assertLessEqual(progreso["hechas"], progreso["total"])
        self.assertTrue(progreso["texto"])
        self.assertIn("banco", progreso["texto"])


class TestTODOfrenteTIENEsuTEXTOllano(unittest.TestCase):
    """En las DOS direcciones, como las fichas: sin texto falla, y huerfano tambien."""

    def test_ninguna_ficha_se_queda_sin_titulo_llano(self):
        for nombre, ficha in obtencion.load_all().items():
            with self.subTest(frente=nombre):
                self.assertTrue(ficha.plain_title, f"{nombre} sin `titulo_llano`")
                self.assertTrue(ficha.plain, f"{nombre} sin `en_cristiano`")

    def test_y_el_texto_llano_NO_usa_jerga(self):
        raton = species_mod.resolve("mouse")
        for nombre in obtencion.load_all():
            ficha = obtencion.resolve_ficha(nombre, species=raton)
            with self.subTest(frente=nombre):
                self.assertEqual(_sin_jerga(ficha.plain_title), [], ficha.plain_title)
                self.assertEqual(_sin_jerga(ficha.plain), [], ficha.plain)


class TestLosCANDIDATOSnoSONelFINAL(unittest.TestCase):
    """Estaba todo seguido, asi que la lista de candidatos parecia el resultado."""

    def test_hay_un_texto_de_CIERRE_del_primer_tramo(self):
        self.assertTrue(presentation.CANDIDATES_ARE_NOT_THE_END.strip())

    def test_que_dice_que_FALTA_y_no_solo_que_hay(self):
        texto = presentation.CANDIDATES_ARE_NOT_THE_END.lower()
        self.assertIn("falta", texto)

    def test_y_los_BOTONES_se_llaman_por_lo_que_HACEN(self):
        # «Diseñar» y «Estimar coste» no dicen que va a salir en pantalla.
        self.assertIn("candidat", presentation.BUTTON_DESIGN.lower())
        self.assertTrue(presentation.BUTTON_ESTIMATE)
        self.assertTrue(presentation.BUTTON_CONTINUE)


if __name__ == "__main__":
    unittest.main()
