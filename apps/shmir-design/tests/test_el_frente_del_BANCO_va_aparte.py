"""El frente que NO se cierra aquí va aparte, y un frente cerrado enseña el RESULTADO.

**Reportado (2026-09-05), dos cosas y la misma raíz — una tarjeta que no distingue
estados:**

1. `empalme_intron` está *«en la misma cuadrícula, con el mismo aspecto y el mismo "Cómo
   se hace", así que se lee como una comprobación pendiente más»*. No lo es: es el único
   frente **binario** —si el intrón no se escinde no hay proteína DN, y ninguno de los
   otros lo detecta— y el único que **no se cierra con nada de lo que hay en la app**.
   Encima **suma en el mismo contador** que los que sí se cierran con un fichero, así que
   ese contador tiene un máximo inalcanzable.
2. Un frente **CERRADO** enseña el bloque «CÓMO CERRAR EL FRENTE» igual que uno abierto.
   `fraccion_isoforma_larga` sale en verde, con `polya_db_mouse.tsv` cargado, y **manda a
   conseguir un fichero que ya está** — incluido `apa_medido.tsv`, que la propia ficha
   marca como opcional. Es el `why_missing` que envejeció (principio nº 11) en su versión
   de interfaz: *un texto correcto cuando se escribió que hoy manda a hacer algo ya
   hecho*.

El criterio, con sus palabras: **«alguien tiene que poder ver de un vistazo que quedan
seis comprobaciones que puede hacer y una que no depende de la app en absoluto»**.

Regla 5: escritos antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import obtencion, presentation  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _corrida():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(species="raton", sequence=tx, anatomy=anat)


class TestDondeSeCierraCadaFrenteESTA_DECLARADO(unittest.TestCase):
    """Y en UN sitio. Estaba en dos: `informe_doc.BENCH_FRONTS` y la prosa de la ficha."""

    def test_toda_ficha_declara_DONDE_se_cierra(self):
        for nombre, ficha in obtencion.load_all().items():
            with self.subTest(ficha=nombre):
                self.assertIn(ficha.closed_at, obtencion.CLOSING_PLACES)

    def test_el_del_BANCO_es_el_del_empalme_y_solo_ese(self):
        self.assertEqual(obtencion.bench_fronts(), {"empalme_intron"})

    def test_informe_doc_lo_DERIVA_y_no_lo_repite(self):
        from shmir_design import informe_doc

        self.assertEqual(set(informe_doc.BENCH_FRONTS), obtencion.bench_fronts())

    def test_una_ficha_SIN_declararlo_aborta(self):
        """Principio nº 32: un valor por defecto aquí convertiría un frente de banco
        olvidado en uno más de la cuadrícula, en silencio."""
        import tempfile

        from shmir_design.errors import ShmirDesignError

        fuente = (obtencion.FICHA_DIR / "empalme_intron.toml").read_text("utf-8")
        sin = "\n".join(
            l for l in fuente.splitlines() if not l.startswith("se_cierra_en")
        )
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "empalme_intron.toml"
            ruta.write_text(sin, "utf-8")
            with self.assertRaises(ShmirDesignError):
                obtencion.load_ficha(ruta)

    def test_y_un_sitio_INVENTADO_tambien(self):
        import tempfile

        from shmir_design.errors import ShmirDesignError

        fuente = (obtencion.FICHA_DIR / "seed.toml").read_text("utf-8")
        raro = fuente.replace(
            f'se_cierra_en = "{obtencion.CLOSED_IN_APP}"', 'se_cierra_en = "el pasillo"'
        )
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "seed.toml"
            ruta.write_text(raro, "utf-8")
            with self.assertRaises(ShmirDesignError):
                obtencion.load_ficha(ruta)

    def test_sin_fichero_y_del_banco_NO_son_lo_mismo(self):
        """`intron_sin_criptico` también dice `sin_fichero`, y es lo contrario: lo
        DISEÑA la app. Derivar el banco de ahí habría sacado un intrón de la cuadrícula."""
        fichas = obtencion.load_all()
        self.assertTrue(fichas["intron_sin_criptico"].no_file)
        self.assertEqual(fichas["intron_sin_criptico"].closed_at, obtencion.CLOSED_IN_APP)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaTarjetaDelBancoVA_APARTE(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.tarjetas = presentation.front_card_rows(cls.corrida, species="raton")
        cls.banco = [t for t in cls.tarjetas if not t["cierra_aqui"]]
        cls.aqui = [t for t in cls.tarjetas if t["cierra_aqui"]]

    def test_hay_UNA_de_banco_y_es_la_del_empalme(self):
        self.assertEqual([t["frente"] for t in self.banco], ["empalme_intron"])

    def test_su_encabezado_dice_lo_que_la_DISTINGUE(self):
        cabecera = self.banco[0]["encabezado"]
        self.assertIn("no se cierra aquí", cabecera.lower())
        self.assertIn("banco", cabecera.lower())

    def test_y_dice_que_es_BINARIA_que_es_lo_otro_que_la_separa(self):
        self.assertIn("binari", self.banco[0]["por_que_aparte"].lower())

    def test_las_demas_NO_llevan_encabezado_aparte(self):
        for tarjeta in self.aqui:
            with self.subTest(frente=tarjeta["frente"]):
                self.assertEqual(tarjeta["encabezado"], "")


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElContadorNoMezclaLasDosCosas(unittest.TestCase):
    """Hoy suma en «X de 7» junto a frentes que dependen de una descarga."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.tarjetas = presentation.front_card_rows(cls.corrida, species="raton")
        cls.progreso = presentation.front_progress(cls.tarjetas)

    def test_el_total_es_solo_lo_que_SE_PUEDE_hacer_aqui(self):
        cierran_aqui = sum(1 for t in self.tarjetas if t["cierra_aqui"])
        self.assertEqual(self.progreso["total"], cierran_aqui)
        self.assertEqual(self.progreso["total"], len(self.tarjetas) - 1)

    def test_el_maximo_es_ALCANZABLE(self):
        """Con el frente de banco dentro, «7 de 7» no podía salir nunca."""
        self.assertLessEqual(self.progreso["hechas"], self.progreso["total"])
        self.assertNotIn("empalme_intron", [
            t["frente"] for t in self.tarjetas if t["cierra_aqui"]
        ])

    def test_la_de_banco_se_cuenta_APARTE_y_se_dice(self):
        self.assertEqual(self.progreso["en_el_banco"], 1)
        self.assertIn("banco", self.progreso["texto"].lower())

    def test_la_fraccion_tampoco_la_incluye(self):
        self.assertAlmostEqual(
            self.progreso["fraccion"],
            self.progreso["hechas"] / self.progreso["total"],
        )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestUnFrenteCERRADO_ensena_el_RESULTADO(unittest.TestCase):
    """«Un frente abierto y uno cerrado no pueden mostrar lo mismo en el mismo sitio.»"""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.tarjetas = {
            t["frente"]: t
            for t in presentation.front_card_rows(cls.corrida, species="raton")
        }

    def test_el_de_APA_esta_cerrado_y_lo_primero_es_el_RESULTADO(self):
        apa = self.tarjetas["fraccion_isoforma_larga"]
        self.assertEqual(apa["estado"], "HECHO")
        self.assertTrue(apa["resultado"])
        self.assertIn("CERRADO", apa["resultado"])

    def test_y_su_ficha_pasa_a_PASADO(self):
        apa = self.tarjetas["fraccion_isoforma_larga"]
        self.assertIn("consiguió", apa["ficha_titulo"])
        self.assertNotIn("se consigue", apa["ficha_titulo"])

    def test_el_texto_de_la_ficha_YA_no_manda_a_conseguir_nada(self):
        apa = self.tarjetas["fraccion_isoforma_larga"]
        self.assertNotIn("COMO CERRAR EL FRENTE", apa["ficha_texto"])
        self.assertNotIn("QUE HACEN FALTA", apa["ficha_texto"])

    def test_un_frente_ABIERTO_sigue_en_presente(self):
        seed = self.tarjetas["seed"]
        self.assertEqual(seed["estado"], "SIN_HACER")
        self.assertIn("consigue", seed["ficha_titulo"])
        self.assertIn("COMO CERRAR EL FRENTE", seed["ficha_texto"])

    def test_ES_GENERAL_y_no_un_arreglo_de_uno(self):
        """«Comprueba si pasa en los otros cerrados.» Si es general, es un solo arreglo."""
        cerrados = [t for t in self.tarjetas.values() if t["estado"] == "HECHO"]
        self.assertTrue(cerrados)
        for tarjeta in cerrados:
            with self.subTest(frente=tarjeta["frente"]):
                self.assertNotIn("COMO CERRAR EL FRENTE", tarjeta["ficha_texto"])
                self.assertIn("consiguió", tarjeta["ficha_titulo"])
                self.assertTrue(tarjeta["resultado"])

    def test_la_de_banco_NO_es_ninguna_de_las_dos_cosas(self):
        banco = self.tarjetas["empalme_intron"]
        self.assertNotIn("COMO CERRAR EL FRENTE", banco["ficha_texto"])
        self.assertIn("banco", banco["ficha_titulo"].lower())


class TestLaFichaRENDERIZA_SEGUN_EL_ESTADO(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.species import resolve

        cls.ficha = obtencion.resolve_ficha(
            "fraccion_isoforma_larga", species=resolve("raton")
        )

    def test_abierta_manda_a_conseguir(self):
        texto = self.ficha.render()
        self.assertIn("COMO CERRAR EL FRENTE", texto)
        self.assertIn("QUE HACEN FALTA", texto)

    def test_cerrada_es_una_REFERENCIA_de_lo_que_se_uso(self):
        texto = self.ficha.render(closed=True)
        self.assertIn("CÓMO SE CONSIGUIÓ", texto)
        self.assertNotIn("QUE HACEN FALTA", texto)
        self.assertIn("SE CERRÓ", texto)

    def test_y_el_opcional_sigue_marcado_como_opcional(self):
        """`apa_medido.tsv` es opcional y la ficha lo dice; lo que no puede es pedirlo."""
        texto = self.ficha.render(closed=True)
        self.assertIn("opcional", texto)


class TestLaPaginaNoDecideCUAL_va_aparte(unittest.TestCase):
    """Principio nº 31: un mecanismo, no un comentario. Si mañana hay un segundo frente
    de banco, la página no tiene que enterarse."""

    FUENTE = (RAIZ / "ui" / "streamlit_app.py").read_text("utf-8")

    def test_la_pagina_no_nombra_ningun_frente(self):
        self.assertNotIn("empalme_intron", self.FUENTE)

    def test_la_pagina_separa_por_la_BANDERA_de_la_tarjeta(self):
        self.assertIn('cierra_aqui', self.FUENTE)


if __name__ == "__main__":
    unittest.main()
