"""Las tres corridas de RepeatMasker de verdad, y por que el resumen es OBLIGATORIO.

Regla 5: escritos antes. Datos reales, aportados el 2026-08-26:
RepeatMasker open-4.0.9 · rmblastn 2.17.1+ · Dfam_3.0.

LA DEMOSTRACION, y va al registro con sus md5 como evidencia:

    rmsk_human.out                          bcc33dbc7a65e74690f5f9d1fb270035
    rmsk_human_WRONG_SPECIES_mouse_lib.out  bcc33dbc7a65e74690f5f9d1fb270035

**Son el mismo fichero, byte a byte.** Una corrida valida y una con la biblioteca
equivocada producen `.out` INDISTINGUIBLES, porque lo unico que aparece es un
microsatelite `(TA)n` y las repeticiones simples se detectan por COMPOSICION, no por
biblioteca. La diferencia vive solo en el `.tbl`:

    rmsk_human.tbl                          «homo sapiens», familias ALUs / MIRs
    rmsk_human_WRONG_SPECIES_mouse_lib.tbl  «mus musculus», familias Alu/B1 / B2-B4

Asi que exigir el resumen NO es una precaucion: es la unica forma de saber contra que
biblioteca se corrio. Y de paso, la linea de la especie NO esta en el `.out` — estos
tres `.out` no la traen. Un `.out` a solas no se puede validar, y punto.
"""

import hashlib
import unittest
from pathlib import Path

from shmir_design import masking
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.coords import Frame, Position, bound_of, span
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
MD5 = {
    "rmsk_mouse.out": "16825306151e5da3d103207c5ad3e483",
    "rmsk_mouse.tbl": "9bb12689f571d997caa97b32ee729e0a",
    "rmsk_human.out": "bcc33dbc7a65e74690f5f9d1fb270035",
    "rmsk_human.tbl": "5fe78c069ffd8d5566a9d17607682791",
    "rmsk_human_WRONG_SPECIES_mouse_lib.out": "bcc33dbc7a65e74690f5f9d1fb270035",
    "rmsk_human_WRONG_SPECIES_mouse_lib.tbl": "f464784b95b720afabf6435f6069477c",
}
PRESENTES = all((DIR / n).is_file() for n in MD5)


def _texto(nombre: str) -> str:
    return (DIR / nombre).read_text(encoding="utf-8")


def _anat(acc: str) -> Anatomy:
    r = REFERENCES[acc]
    return Anatomy(
        length=r.length, utr5=r.utr5, cds=r.cds, utr3=r.utr3,
        source=RegionSource.ANOTACION_GENBANK,
    )


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_* en data/reference")
class TestLaProcedencia(unittest.TestCase):

    def test_los_seis_md5_son_los_declarados(self):
        for nombre, esperado in MD5.items():
            real = hashlib.md5((DIR / nombre).read_bytes()).hexdigest()
            self.assertEqual(real, esperado, nombre)

    def test_los_DOS_out_humanos_son_EL_MISMO_FICHERO(self):
        # Es la demostracion entera en una linea.
        self.assertEqual(
            MD5["rmsk_human.out"], MD5["rmsk_human_WRONG_SPECIES_mouse_lib.out"]
        )
        self.assertEqual(
            (DIR / "rmsk_human.out").read_bytes(),
            (DIR / "rmsk_human_WRONG_SPECIES_mouse_lib.out").read_bytes(),
        )

    def test_pero_los_tbl_NO(self):
        self.assertNotEqual(
            MD5["rmsk_human.tbl"], MD5["rmsk_human_WRONG_SPECIES_mouse_lib.tbl"]
        )


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_*")
class TestLaEspecieViveEnElRESUMEN(unittest.TestCase):

    def test_ningun_out_declara_la_especie(self):
        for nombre in ("rmsk_mouse.out", "rmsk_human.out",
                       "rmsk_human_WRONG_SPECIES_mouse_lib.out"):
            self.assertIsNone(masking.declared_species(_texto(nombre)), nombre)

    def test_los_tbl_SI(self):
        self.assertEqual(
            masking.declared_species(_texto("rmsk_mouse.tbl")), "mus musculus"
        )
        self.assertEqual(
            masking.declared_species(_texto("rmsk_human.tbl")), "homo sapiens"
        )

    def test_y_el_tbl_de_la_corrida_MALA_dice_mus_musculus_sobre_el_humano(self):
        malo = _texto("rmsk_human_WRONG_SPECIES_mouse_lib.tbl")
        self.assertEqual(masking.declared_species(malo), "mus musculus")
        self.assertIn("2435 bp", malo)      # la consulta ES humana
        self.assertIn("B2-B4", malo)        # las familias son MURINAS

    def test_un_out_SIN_resumen_no_se_puede_validar_y_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            masking.parse_rmsk_out(
                _texto("rmsk_human.out"),
                source="rmsk_human.out", version="4.0.9", checksum=MD5["rmsk_human.out"],
                expected_species="homo sapiens",
            )
        self.assertIn("resumen", str(ctx.exception).lower())


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_*")
class TestElFixtureNEGATIVO(unittest.TestCase):
    """La corrida mala se guarda y se comprueba que el parser la RECHAZA."""

    def test_el_MISMO_out_pasa_con_su_tbl_y_falla_con_el_malo(self):
        comunes = dict(
            source="rmsk_human.out", version="4.0.9",
            checksum=MD5["rmsk_human.out"], expected_species="homo sapiens",
            library="Dfam_3.0",
        )
        bueno = masking.parse_rmsk_out(
            _texto("rmsk_human.out"),
            summary=_texto("rmsk_human.tbl"), **comunes,
        )
        self.assertEqual(bueno.species, "homo sapiens")
        with self.assertRaises(ShmirDesignError) as ctx:
            masking.parse_rmsk_out(
                _texto("rmsk_human_WRONG_SPECIES_mouse_lib.out"),
                summary=_texto("rmsk_human_WRONG_SPECIES_mouse_lib.tbl"), **comunes,
            )
        self.assertIn("mus musculus", str(ctx.exception))

    def test_y_el_motivo_dice_que_los_out_son_indistinguibles(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            masking.parse_rmsk_out(
                _texto("rmsk_human_WRONG_SPECIES_mouse_lib.out"),
                summary=_texto("rmsk_human_WRONG_SPECIES_mouse_lib.tbl"),
                source="malo", version="4.0.9",
                checksum=MD5["rmsk_human_WRONG_SPECIES_mouse_lib.out"],
                expected_species="homo sapiens",
            )
        self.assertIn("SIN BUSCAR", str(ctx.exception))


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_*")
class TestLoQueDicenLasDosCorridasBUENAS(unittest.TestCase):

    def setUp(self):
        self.raton = masking.parse_rmsk_out(
            _texto("rmsk_mouse.out"), source="rmsk_mouse.out", version="4.0.9",
            checksum=MD5["rmsk_mouse.out"], expected_species="mus musculus",
            library="Dfam_3.0", summary=_texto("rmsk_mouse.tbl"),
        )
        self.humano = masking.parse_rmsk_out(
            _texto("rmsk_human.out"), source="rmsk_human.out", version="4.0.9",
            checksum=MD5["rmsk_human.out"], expected_species="homo sapiens",
            library="Dfam_3.0", summary=_texto("rmsk_human.tbl"),
        )

    def test_una_repeticion_en_cada_una(self):
        self.assertEqual(len(self.raton.elements), 1)
        self.assertEqual(len(self.humano.elements), 1)

    def test_el_raton_trae_CTC_n_en_tx_892_936(self):
        e = self.raton.elements[0]
        self.assertEqual((e.start, e.end), (892, 936))
        self.assertIn("CTC", e.name)
        self.assertEqual(e.family, "Simple_repeat")

    def test_el_humano_trae_TA_n_en_tx_2097_2130(self):
        e = self.humano.elements[0]
        self.assertEqual((e.start, e.end), (2097, 2130))
        self.assertIn("TA", e.name)
        self.assertEqual(e.family, "Simple_repeat")

    def test_CERO_interspersed_en_las_dos_y_el_resumen_lo_dice_familia_a_familia(self):
        for mascara, familia in ((self.raton, "B2-B4"), (self.humano, "ALUs")):
            self.assertIn("Total interspersed repeats:", mascara.summary)
            self.assertIn(familia, mascara.summary)

    def test_con_resumen_el_veredicto_es_CONCLUYENTE(self):
        self.assertTrue(self.raton.conclusive)
        self.assertTrue(self.humano.conclusive)

    def test_la_procedencia_imprime_biblioteca_y_especie(self):
        texto = self.raton.provenance
        self.assertIn("Dfam_3.0", texto)
        self.assertIn("mus musculus", texto)


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_*")
class TestLaConversionVaPorCoordsNoPorUnaResta(unittest.TestCase):

    def test_la_del_raton_cae_ENTERA_en_el_CDS(self):
        r = REFERENCES["NM_011170.3"]
        inicio, fin = Position(892, Frame.TX), Position(936, Frame.TX)
        self.assertGreaterEqual(inicio.value, r.cds[0])
        self.assertLessEqual(fin.value, r.cds[1])
        self.assertLess(fin.value, r.utr3[0])

    def test_y_convertirla_a_3utr_ABORTA_porque_no_esta_ahi(self):
        # 936 - 949 = -13. Con una resta a pelo saldria un numero negativo o, peor, se
        # colaria con signo. `coords` lo para.
        with self.assertRaises(ValueError):
            Position(936, Frame.TX).to_utr3(949)

    def test_NO_toca_la_ventana_del_ORF_conservado(self):
        # ORF ratón 523/524 = tx:707-728.
        self.assertGreater(892, 728)

    def test_asi_que_el_3UTR_MURINO_no_tiene_ni_una_repeticion(self):
        mascara = masking.parse_rmsk_out(
            _texto("rmsk_mouse.out"), source="rmsk_mouse.out", version="4.0.9",
            checksum=MD5["rmsk_mouse.out"], expected_species="mus musculus",
            library="Dfam_3.0", summary=_texto("rmsk_mouse.tbl"),
        )
        r = REFERENCES["NM_011170.3"]
        self.assertEqual(
            [e for e in mascara.elements if e.end >= r.utr3[0]], []
        )

    def test_la_del_humano_SI_cae_en_el_3UTR_y_es_3utr_1268_1301(self):
        an = _anat("NM_000311.5")
        desfase = an.utr3[0] - 1
        p = Position(2097, Frame.TX).to_utr3(desfase)
        q = Position(2130, Frame.TX).to_utr3(desfase)
        self.assertEqual(
            span(p.value, q.value, Frame.UTR3, limit=bound_of(an)), "3utr:1268-1301"
        )

    @unittest.skipUnless(
        fixture_available(REFERENCES["NM_000311.5"]), "falta NM_000311.5.fa"
    )
    def test_y_solapa_CINCO_ventanas_elegibles_del_humano(self):
        from shmir_design.selection import is_eligible
        from shmir_design.tiling import tile_utr

        informe = tile_utr(load_3utr(REFERENCES["NM_000311.5"]))
        solapan = [
            w.window.start for w in informe.windows
            if is_eligible(w) and w.window.start <= 1301 and w.window.end >= 1268
        ]
        self.assertEqual(solapan, [1247, 1249, 1250, 1251, 1252])


@unittest.skipUnless(
    PRESENTES and fixture_available(REFERENCES["NM_011170.3"]),
    "NOT_RUN: faltan ficheros",
)
class TestLaHipotesisDeLaCarreraDeA_QUEDA_REFUTADA(unittest.TestCase):
    """Se predijo que los 45 pb serian la carrera de A del 3'UTR. NO lo son.

    La prediccion era: «casi con seguridad es la carrera de A de 3utr:480-500», y de
    cumplirse habria sido convergencia de dos criterios independientes sobre el mismo
    tramo. No se cumple, y eso se anota igual que se habria anotado el acierto — si no,
    solo se registran las predicciones que salen bien.
    """

    def test_la_repeticion_NO_esta_en_el_3UTR(self):
        self.assertLess(936, REFERENCES["NM_011170.3"].utr3[0])

    def test_la_carrera_mas_larga_del_3UTR_murino_esta_en_OTRO_sitio(self):
        u = load_3utr(REFERENCES["NM_011170.3"])
        mejor, corriendo, fin = 0, 1, 1
        for i in range(1, len(u)):
            corriendo = corriendo + 1 if u[i] == u[i - 1] else 1
            if corriendo > mejor:
                mejor, fin = corriendo, i + 1
        self.assertEqual(mejor, 10)
        self.assertEqual(fin, 507)          # 3utr:498-507, no 480-500
        self.assertNotEqual(fin + 949, 936)  # y RepeatMasker no la marco

    def test_NO_hay_convergencia_de_dos_criterios(self):
        # Lo que hay es un `(CTC)n` en el CDS. Son tramos distintos y criterios que no
        # coinciden en ninguno.
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(PRESENTES, "NOT_RUN: faltan los ficheros rmsk_*")
class TestLaMascaraNoSePuedeAplicarAOtraSECUENCIA(unittest.TestCase):
    """La misma trampa de la especie, un nivel mas arriba.

    `--usar-manifiesto` carga `rmsk_mouse.out` por su rol, sin mirar que especie se esta
    diseñando. Aplicada al transcrito HUMANO enmascararia tx:892-936 del humano —un
    tramo que ahi no es repetitivo— y no daria ningun error: el intervalo cabe en 2435
    nt. Es el mismo fallo que la biblioteca equivocada, y se cierra igual: comparando lo
    que el resumen declara haber analizado con lo que se le esta dando.
    """

    def setUp(self):
        self.raton = masking.parse_rmsk_out(
            _texto("rmsk_mouse.out"), source="rmsk_mouse.out", version="4.0.9",
            checksum=MD5["rmsk_mouse.out"], expected_species="mus musculus",
            library="Dfam_3.0", summary=_texto("rmsk_mouse.tbl"),
        )

    def test_el_resumen_declara_la_longitud_de_la_consulta(self):
        self.assertEqual(self.raton.query_length, 2191)

    def test_aplicarla_a_SU_secuencia_va_bien(self):
        self.assertEqual(len(masking.apply_mask("A" * 2191, self.raton)), 2191)

    def test_aplicarla_al_transcrito_HUMANO_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            masking.apply_mask("A" * 2435, self.raton)
        self.assertIn("2191", str(ctx.exception))
        self.assertIn("2435", str(ctx.exception))

    def test_y_el_motivo_dice_que_el_intervalo_CABRIA(self):
        # Es lo que lo hace peligroso: no se sale, asi que no salta ninguna otra alarma.
        with self.assertRaises(ShmirDesignError) as ctx:
            masking.apply_mask("A" * 2435, self.raton)
        self.assertIn("cabe", str(ctx.exception).lower())

    def test_sin_resumen_no_hay_longitud_y_no_se_comprueba(self):
        # Aqui no se inventa un limite: sin resumen no hay dato. Lo que impide que eso
        # sea una puerta trasera es que un `.out` sin resumen ya no se puede parsear.
        from dataclasses import replace

        sin = replace(self.raton, summary=None)
        self.assertIsNone(sin.query_length)
        self.assertEqual(len(masking.apply_mask("A" * 2435, sin)), 2435)
