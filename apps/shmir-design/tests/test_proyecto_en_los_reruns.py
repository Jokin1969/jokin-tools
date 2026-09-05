"""El proyecto abierto SOBREVIVE al rerun, y la cabecera del FASTA no lleva espacios.

TRES FALLOS DE LA MISMA TANDA, y los tres se cobran donde mas caro sale: detras de una
descarga de decenas de GB y una corrida de BLAST de horas.

1. **El proyecto se perdia en cada rerun.** La pagina lo abria dentro de un `if
   boton:`, y un boton de Streamlit vale `True` UN SOLO rerun. Asi que en cuanto el
   usuario escribia en cualquier `text_input` —el de «Fecha» del propio formulario de
   guardar, por ejemplo— la pagina se repintaba, el boton ya no estaba pulsado, el panel
   devolvia `None` y el formulario de guardar DESAPARECIA con el aviso «Sin proyecto
   abierto». El formulario era imposible de completar: para rellenarlo hay que escribir,
   y escribir lo borraba.

2. **El modal aceptaba el fichero sin proyecto abierto** y avisaba en gris de que no se
   iba a guardar nada. Eso es una trampa: dejar soltar el resultado de una corrida de
   horas en un sitio donde no se guarda no es informar, es invitar a perderla.

3. **El FASTA de consulta emitia cabeceras con ESPACIOS** (`>Mus musculus_pos959_guia`).
   BLAST corta `qseqid` en el primer espacio, asi que las veinte consultas salian todas
   como `Mus` en el `-outfmt 6` y NO SE DISTINGUIAN ENTRE SI. El fichero de resultados
   no es recuperable —no contiene de que consulta viene cada fila— y no da ningun error:
   es un `.tsv` con la forma correcta.
"""

import unittest

from shmir_design import presentation
from shmir_design.blast import QueryFasta
from shmir_design.errors import ShmirDesignError

NUEVO = presentation.PROJECT_NEW_OPTION


class TestElProyectoSOBREVIVEalRerun(unittest.TestCase):
    """`project_target` decide, y la pagina solo se acuerda. Regla 6."""

    def _plan(self, **cambios):
        base = dict(active=True, chosen=NUEVO, new_name="", date="", clicked=False,
                    remembered="")
        return presentation.project_target(**{**base, **cambios})

    def test_al_pulsar_CREAR_se_crea(self):
        plan = self._plan(new_name="prueba", date="2026-09-01", clicked=True)
        self.assertEqual(plan["accion"], "crear")
        self.assertEqual(plan["slug"], "prueba")

    def test_Y_EN_EL_RERUN_SIGUIENTE_SIGUE_ABIERTO(self):
        """EL FALLO. El boton ya no esta pulsado y el proyecto tiene que seguir ahi."""
        creado = self._plan(new_name="prueba", date="2026-09-01", clicked=True)
        # Lo que la pagina recuerda es el SLUG, no el almacen: un objeto en
        # `session_state` sobreviviria igual pero no se podria revalidar, y el md5 de la
        # secuencia hay que volver a comprobarlo en cada rerun.
        siguiente = self._plan(
            new_name="prueba", date="2026-09-01", clicked=False,
            remembered=creado["recordar"],
        )
        self.assertEqual(siguiente["accion"], "abrir")
        self.assertEqual(siguiente["slug"], "prueba")

    def test_y_lo_sigue_estando_AUNQUE_SE_BORRE_el_nombre_tecleado(self):
        # El nombre vive en un widget y el usuario puede vaciarlo; el proyecto ya existe.
        plan = self._plan(remembered="prueba")
        self.assertEqual(plan["accion"], "abrir")
        self.assertEqual(plan["slug"], "prueba")

    def test_elegir_otro_del_desplegable_MANDA_sobre_lo_recordado(self):
        plan = self._plan(chosen="otro", remembered="prueba")
        self.assertEqual(plan["accion"], "abrir")
        self.assertEqual(plan["slug"], "otro")
        self.assertEqual(plan["recordar"], "otro")

    def test_crear_otro_MANDA_sobre_lo_recordado(self):
        plan = self._plan(
            new_name="segundo", date="2026-09-01", clicked=True, remembered="prueba"
        )
        self.assertEqual(plan["accion"], "crear")
        self.assertEqual(plan["slug"], "segundo")

    def test_desactivar_la_casilla_OLVIDA_el_proyecto(self):
        # Si no olvidara, volver a marcarla reabriria uno que el usuario habia cerrado.
        plan = self._plan(active=False, remembered="prueba")
        self.assertEqual(plan["accion"], "ninguna")
        self.assertEqual(plan["recordar"], "")
        self.assertIn("se pierde", plan["aviso"])

    def test_sin_nombre_ni_fecha_no_se_crea_nada_y_se_DICE(self):
        plan = self._plan(new_name="", date="")
        self.assertEqual(plan["accion"], "ninguna")
        self.assertTrue(plan["aviso"])

    def test_con_nombre_y_fecha_pero_SIN_pulsar_tampoco(self):
        plan = self._plan(new_name="prueba", date="2026-09-01", clicked=False)
        self.assertEqual(plan["accion"], "ninguna")
        self.assertIn("Crear", plan["aviso"])


class TestLaPaginaNOreimplementaLaDecision(unittest.TestCase):
    """Regla 6: si la condicion vive en la pagina, no tiene test y puede divergir."""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        cls.fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")

    def test_la_pagina_llama_a_project_target(self):
        self.assertIn("project_target", self.fuente)

    def test_y_NO_crea_el_proyecto_dentro_de_un_if_de_boton(self):
        """La regresion exacta: `project_create` colgando de un boton de un solo rerun."""
        for linea in self.fuente.splitlines():
            if "project_create(" in linea:
                self.assertNotIn("button", linea)
        # Y el plan se recuerda entre reruns.
        self.assertIn("pr_abierto_", self.fuente)


class TestSinProyectoNOseACEPTAelFICHERO(unittest.TestCase):
    """Aceptarlo y avisar en gris es una trampa: detras hay horas de corrida."""

    def test_sin_proyecto_NO_se_permite_subir_y_se_dice_por_que(self):
        veredicto = presentation.upload_allowed(None)
        self.assertFalse(veredicto["permitido"])
        self.assertTrue(veredicto["motivo"])

    def test_con_proyecto_si(self):
        veredicto = presentation.upload_allowed(object())
        self.assertTrue(veredicto["permitido"])
        self.assertEqual(veredicto["motivo"], "")

    def test_el_motivo_dice_QUE_HACER_no_solo_que_no(self):
        motivo = presentation.upload_allowed(None)["motivo"]
        self.assertIn("barra lateral", motivo)

    def test_LOS_TRES_modales_que_suben_fichero_lo_comprueban(self):
        """Los tres, no solo el de BLAST: el patron es el mismo en los tres."""
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        # Se cuentan las LLAMADAS, no las apariciones: el `import` es una mas y contarlo
        # dejaria pasar dos modales comprobando y uno no.
        self.assertEqual(fuente.count("upload_allowed(proyecto)"), 3)


class TestLaCABECERAdelFASTAnoLLEVAespacios(unittest.TestCase):
    """BLAST corta `qseqid` en el primer espacio. Sin esto, veinte consultas son una."""

    def test_un_nombre_con_ESPACIOS_aborta(self):
        with self.assertRaises(ShmirDesignError) as caja:
            QueryFasta.from_records([("Mus musculus_pos959_guia", "ACGT")])
        mensaje = str(caja.exception)
        self.assertIn("qseqid", mensaje)
        self.assertIn("Mus musculus_pos959_guia", mensaje)

    def test_y_cualquier_otro_blanco_TAMBIEN(self):
        # `-outfmt 6` es un TSV: un tabulador dentro del nombre parte la fila entera.
        for blanco in ("\t", "\n", "\r", "\v"):
            with self.subTest(blanco=repr(blanco)):
                with self.assertRaises(ShmirDesignError):
                    QueryFasta.from_records([(f"guia{blanco}1", "ACGT")])

    def test_un_nombre_LIMPIO_pasa(self):
        fasta = QueryFasta.from_records([("mouse_pos959_guia", "ACGT")])
        self.assertEqual(fasta.names, ("mouse_pos959_guia",))


class TestElNOMBREdeLaCONSULTAlleva_el_SLUG(unittest.TestCase):
    """El slug es lo que no tiene espacios; el nombre cientifico si los tiene."""

    def test_el_prefijo_es_el_SLUG_de_la_especie(self):
        self.assertEqual(presentation.query_name("Mus musculus", 959, "guia"),
                         "mouse_pos959_guia")

    def test_y_da_igual_como_se_escriba_la_especie(self):
        # `mouse`, `raton`, `Mus musculus` son la MISMA especie: un nombre de consulta
        # distinto por cada alias haria incomparables dos corridas de lo mismo.
        for alias in ("mouse", "raton", "Mus musculus"):
            with self.subTest(alias=alias):
                self.assertEqual(presentation.query_name(alias, 959, "guia"),
                                 "mouse_pos959_guia")

    def test_una_especie_SIN_declarar_tambien_da_un_nombre_SIN_espacios(self):
        """Y NO aborta aqui: el slug se DERIVA del nombre, no se inventa.

        Escribi este test esperando un aborto y el proyecto hace otra cosa, que es la
        correcta: `species.resolve` admite una especie no declarada —la interfaz tiene
        una opcion explicita para ella— y lo que aborta es lo que de verdad falta, el
        TAXID, cuando se construye la orden. Abortar aqui movería el fallo a un sitio
        que no es el suyo; lo único que este nivel tiene que garantizar es que el
        identificador sea utilizable.
        """
        nombre = presentation.query_name("Oryctolagus inventado", 959, "guia")
        self.assertEqual(nombre, "oryctolagus_inventado_pos959_guia")
        self.assertNotIn(" ", nombre)


if __name__ == "__main__":
    unittest.main()
