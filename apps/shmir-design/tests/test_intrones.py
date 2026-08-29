"""El registro de intrones. La unidad de analisis del cuarto modal NO es el candidato.

Regla 5: escritos antes.

Los otros tres modales preguntan sobre una guia de 22 nt. Este pregunta sobre el
**cassette montado**: intron completo, con su modulo dentro, con la guia y la pasajera de
ese candidato concreto, y con contexto exonico a los dos lados. Asi que la unidad es el
par **candidato x intron**, y eso obliga a que el registro de intrones sea de primera
clase en vez de una constante escondida en `blocks.PIECES`.

Los tres estados son distintos y el registro los distingue:

  - `mvm_actual` — DISPONIBLE. Se ensambla de piezas versionadas; nadie lo teclea.
  - `intron_quimerico` — APORTADO desde 2026-08-27. Se EXTRAE por su anotacion del
    plasmido de Addgene #198131 y se comprueba contra la longitud y el md5 declarados;
    no se teclea. Antes se llamaba `quimerico_cmv_globina` y se describia como «CMV /
    beta-globina»: las dos cosas estaban mal —CMV es el PROMOTOR del plasmido, no parte
    del intron— y salieron a la luz al llegar el fichero.
  - `mvm_sin_criptico` — lo DISEÑA la app, derivado del primero, con dos criterios
    computables. Es una PROPUESTA, no una construccion aprobada.
"""

import unittest

from shmir_design import blocks, introns
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState


class TestLosTresEstadosSonDISTINTOS(unittest.TestCase):

    def test_estan_los_tres_declarados(self):
        self.assertEqual(
            set(introns.INTRONS),
            {"mvm_actual", "intron_quimerico", "mvm_sin_criptico"},
        )

    def test_la_clave_VIEJA_ya_no_existe(self):
        # `quimerico_cmv_globina` describia mal el intron. No se conserva por
        # compatibilidad: no hay ningun dato guardado con esa clave, y una clave que
        # miente es peor que una rota.
        self.assertNotIn("quimerico_cmv_globina", introns.INTRONS)

    def test_el_MVM_esta_DISPONIBLE(self):
        self.assertTrue(introns.INTRONS["mvm_actual"].provided)

    def test_el_quimerico_YA_ESTA_y_sale_del_fichero(self):
        quimerico = introns.INTRONS["intron_quimerico"]
        self.assertTrue(quimerico.provided)
        self.assertIn("198131", quimerico.source)
        self.assertIn("1216-1348", quimerico.source)

    def test_y_su_secuencia_mide_133_pb(self):
        self.assertEqual(len(introns.INTRONS["intron_quimerico"].require_sequence()), 133)

    def test_la_descripcion_ya_NO_dice_CMV(self):
        # CMV es el promotor del plásmido (497-1080), no parte del intrón. La quimera es
        # de beta-globina humana e inmunoglobulina de cadena pesada, y lo dice la nota de
        # la propia anotación.
        descripcion = introns.INTRONS["intron_quimerico"].description
        self.assertNotIn("CMV", descripcion)
        self.assertIn("globina", descripcion.lower())
        self.assertIn("inmunoglobulina", descripcion.lower())

    def test_el_de_sin_criptico_es_DERIVADO_no_aportado_ni_tecleado(self):
        variante = introns.INTRONS["mvm_sin_criptico"]
        self.assertTrue(variante.derived)
        self.assertEqual(variante.derived_from, "mvm_actual")

    def test_y_sale_marcado_como_PROPUESTA(self):
        variante = introns.INTRONS["mvm_sin_criptico"]
        self.assertIn("propuesta", variante.description.lower())


class TestElMVM_SE_ENSAMBLA_NO_SE_TECLEA(unittest.TestCase):

    def test_sale_de_las_piezas_versionadas(self):
        mvm = introns.INTRONS["mvm_actual"]
        self.assertEqual(
            mvm.empty_sequence,
            blocks.PIECES["MVM5"].sequence + blocks.PIECES["MVM3"].sequence,
        )

    def test_no_hay_ni_una_secuencia_escrita_en_el_modulo(self):
        """Regla 1 por la puerta de atras: un literal de ADN aqui seria una pieza que
        deja de estar versionada y que nadie volveria a comprobar."""
        import re
        from pathlib import Path

        fuente = (
            Path(introns.__file__).resolve()
        ).read_text(encoding="utf-8")
        # Se quitan los docstrings y comentarios: ahi si se nombran motivos como GTGAGCG.
        codigo = "\n".join(
            l.split("#")[0] for l in fuente.splitlines() if not l.strip().startswith("#")
        )
        for cadena in re.findall(r'"([ACGT]{8,})"', codigo):
            self.fail(f"literal de ADN en el código: {cadena}")

    def test_el_intron_VACIO_mide_82_nt(self):
        """Es el del casete parental, y esta DOS nt por encima del suelo de 80."""
        self.assertEqual(len(introns.INTRONS["mvm_actual"].empty_sequence), 82)

    def test_con_el_modulo_dentro_mide_296(self):
        mvm = introns.INTRONS["mvm_actual"]
        montado = mvm.with_module("N" * blocks.MODULE_LENGTH)
        self.assertEqual(len(montado), blocks.INTRON_LENGTH)


class TestLosCuatroElementosSeDERIVAN(unittest.TestCase):
    """Ninguna de las cuatro coordenadas se teclea: se buscan en la secuencia."""

    def setUp(self):
        self.elementos = introns.locate_elements(
            introns.INTRONS["mvm_actual"].empty_sequence, name="mvm vacío"
        )

    def test_el_donante_es_el_GT_del_principio(self):
        self.assertEqual(self.elementos.donor.sequence, "GT")
        self.assertEqual((self.elementos.donor.start, self.elementos.donor.end), (1, 2))

    def test_el_aceptor_es_el_AG_del_final(self):
        self.assertEqual(self.elementos.acceptor.sequence, "AG")
        self.assertEqual(self.elementos.acceptor.end, 82)

    def test_el_tracto_son_las_pirimidinas_CONTIGUAS_no_un_porcentaje(self):
        """Contiguas, no el porcentaje en una ventana, que diluye. Son NUEVE."""
        self.assertEqual(len(self.elementos.ppt.sequence), 9)
        self.assertTrue(set(self.elementos.ppt.sequence) <= set("CT"))

    def test_el_punto_de_ramificacion_sale_como_CANDIDATO_no_como_dato(self):
        """YURAY es un criterio DECLARADO, no una medida. Aunque salga uno solo."""
        self.assertIs(
            self.elementos.branch_point.origin, introns.ElementOrigin.CANDIDATO
        )

    def test_y_con_el_MVM_hay_exactamente_UNO(self):
        self.assertEqual(len(self.elementos.branch_candidates), 1)
        self.assertEqual(self.elementos.branch_point.sequence, "TTAAT")

    def test_donante_y_aceptor_SI_son_derivados_sin_ambiguedad(self):
        self.assertIs(self.elementos.donor.origin, introns.ElementOrigin.DERIVADO)
        self.assertIs(self.elementos.acceptor.origin, introns.ElementOrigin.DERIVADO)

    def test_una_secuencia_que_no_empieza_por_GT_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            introns.locate_elements("AATTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTCTTTTTTTCAG",
                                    name="inventado")
        self.assertIn("GT", str(caja.exception))

    def test_una_que_no_acaba_en_AG_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            introns.locate_elements("GT" + "A" * 60 + "CC", name="inventado")

    def test_sin_ningun_YURAY_el_punto_de_ramificacion_es_None_y_no_se_inventa(self):
        elementos = introns.locate_elements("GT" + "G" * 60 + "CTTTTTTTCAG", name="x")
        self.assertIsNone(elementos.branch_point)
        self.assertEqual(elementos.branch_candidates, ())

    def test_con_el_modulo_dentro_los_elementos_SIGUEN_derivandose(self):
        """El punto de ramificacion vive en MVM3, asi que viaja con el."""
        montado = introns.INTRONS["mvm_actual"].with_module("A" * blocks.MODULE_LENGTH)
        elementos = introns.locate_elements(montado, name="mvm con módulo")
        self.assertEqual(elementos.branch_point.sequence, "TTAAT")
        self.assertEqual(len(elementos.ppt.sequence), 9)


class TestElSueloDeOCHENTA_NT(unittest.TestCase):
    """Por debajo de 80 nt el espliceosoma no ensambla bien. Se aplica a los TRES."""

    def test_el_umbral_va_declarado(self):
        self.assertEqual(introns.MIN_INTRON_LENGTH, 80)

    def test_un_intron_montado_por_debajo_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            introns.check_length("GT" + "A" * 40 + "CTTTTTTTCAG", name="corto")
        texto = str(caja.exception)
        self.assertIn("80", texto)
        self.assertIn("espliceosoma", texto)

    def test_el_MVM_con_su_modulo_lo_cumple_de_sobra(self):
        montado = introns.INTRONS["mvm_actual"].with_module("A" * blocks.MODULE_LENGTH)
        self.assertEqual(introns.check_length(montado, name="mvm"), len(montado))

    def test_y_el_VACIO_lo_cumple_por_DOS_nt(self):
        """No es teorico: el intron del casete parental mide 82."""
        vacio = introns.INTRONS["mvm_actual"].empty_sequence
        self.assertEqual(introns.check_length(vacio, name="vacio"), 82)

    def test_donde_MUERDE_de_verdad_va_dicho(self):
        """Con el modulo de 149 nt dentro es inalcanzable. Decir que protege algo que no
        puede pasar seria peor que no ponerlo: el aviso vale para los intrones que
        vengan, no para este."""
        self.assertIn("149", introns.WHY_MIN_LENGTH)


class TestLaFichaDelQueFALTA(unittest.TestCase):

    def test_el_quimerico_tiene_ficha_de_obtencion(self):
        from shmir_design import obtencion

        self.assertTrue(
            introns.INTRONS["intron_quimerico"].ficha in obtencion.load_all(),
            "el quimérico no tiene ficha de obtencion",
        )

    def test_y_dice_de_donde_se_saca(self):
        from shmir_design import obtencion, species

        ficha = obtencion.resolve_ficha(
            introns.INTRONS["intron_quimerico"].ficha,
            species=species.resolve("raton"),
        )
        texto = ficha.render()
        self.assertIn("pAAV", texto)
        for formato in (".dna", ".gb"):
            self.assertIn(formato, texto)

    def test_y_que_al_cargarlo_los_elementos_se_LOCALIZAN(self):
        from shmir_design import obtencion, species

        ficha = obtencion.resolve_ficha(
            introns.INTRONS["intron_quimerico"].ficha,
            species=species.resolve("raton"),
        )
        self.assertIn("localiza", ficha.render().lower())


if __name__ == "__main__":
    unittest.main()
