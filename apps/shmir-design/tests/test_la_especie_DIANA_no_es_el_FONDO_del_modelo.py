"""La especie DIANA y el FONDO GENÉTICO del modelo son dos cosas, y se declaran.

Regla 5: escrito antes.

**LA DECISIÓN (2026-09-08)**, con las palabras del responsable del proyecto:

    «Los candidatos humanos pasan off-targets contra los dos transcriptomas, en un
    frente con eje de transcriptoma y sin veredicto fundido, porque el murino mide el
    experimento y el humano el paciente.»

El modelo es un **ratón humanizado**: BAC de PRNP humana y `Prnp` murino noqueado. El
transcrito diana es `NM_000311.5`, pero **el transcriptoma que se expresa en ese animal
es el MURINO** más el transgén. Así que una corrida humana contra un solo catálogo mide
la mitad — y la mitad que mide es la del paciente, no la del experimento.

Lo que este fichero fija es la pieza de MODELO, que es la que faltaba: distinguir
**especie DIANA** —la del transcrito— de **fondo genético del MODELO** —donde se hace el
experimento—. Sin esa distinción, `required_files` pide los ficheros de UNA especie y
este diseño necesita los de dos.

**Se DECLARA y no se deduce** (principio nº 58): `None` es «nadie lo ha dicho» y `()` es
«se ha mirado y no hay ninguno más», que son dos cosas. El ratón declara `()` —su modelo
es él mismo— y por eso **su corrida no se mueve ni un byte**, que es la comprobación de
que esto no es un cambio de criterio disfrazado.
"""

import unittest

from shmir_design import species
from shmir_design.errors import ShmirDesignError


class TestSeDECLARA(unittest.TestCase):

    def test_el_raton_declara_que_NO_tiene_fondo_aparte(self):
        # `()` no es `None`: dice que se ha mirado. Un ratón se estudia en un ratón.
        self.assertEqual(species.SPECIES["mouse"].model_backgrounds, ())

    def test_el_humano_declara_el_FONDO_MURINO(self):
        self.assertEqual(species.SPECIES["human"].model_backgrounds, ("mouse",))

    def test_una_especie_SIN_declarar_no_se_deduce(self):
        conejo = species.resolve("Oryctolagus cuniculus")
        self.assertIsNone(conejo.model_backgrounds)
        with self.assertRaises(ShmirDesignError) as caso:
            species.off_target_catalogues(conejo)
        self.assertIn("model_backgrounds", str(caso.exception))


class TestLosCATALOGOSqueHayQueBarrer(unittest.TestCase):

    def test_el_raton_barre_UNO_y_es_el_suyo(self):
        catalogos = species.off_target_catalogues(species.resolve("mouse"))
        self.assertEqual([c.slug for c in catalogos], ["mouse"])

    def test_el_humano_barre_DOS_y_la_DIANA_va_primero(self):
        # El orden no es cosmetico: la diana es la pregunta principal —el paciente— y el
        # fondo es la del experimento. Ordenarlos al reves invierte que se lee primero.
        catalogos = species.off_target_catalogues(species.resolve("human"))
        self.assertEqual([c.slug for c in catalogos], ["human", "mouse"])

    def test_un_fondo_que_sea_la_propia_especie_NO_se_duplica(self):
        declarada = species.Species(
            "X", "x", "xxx-", "txid1", "xx1", model_backgrounds=("x",)
        )
        self.assertEqual(
            [c.slug for c in species.off_target_catalogues(declarada)], ["x"]
        )

    def test_un_fondo_que_NO_esta_declarado_como_especie_ABORTA(self):
        # Sin sus identificadores no se puede nombrar su catalogo ni su prefijo, asi que
        # decir que se barre seria decir que se hace algo que no se puede hacer.
        inventada = species.Species(
            "Y", "y", "yyy-", "txid2", "yy1", model_backgrounds=("no_declarada",)
        )
        with self.assertRaises(ShmirDesignError) as caso:
            species.off_target_catalogues(inventada)
        self.assertIn("no_declarada", str(caso.exception))


class TestLosFICHEROSquePideCadaUna(unittest.TestCase):

    def _roles(self, slug):
        return [f.role for f in species.required_files(species.resolve(slug))]

    def _por_rol(self, slug, rol):
        return [
            f for f in species.required_files(species.resolve(slug)) if f.role == rol
        ]

    def test_el_raton_sigue_pidiendo_UN_catalogo(self):
        # CONTROL: si el raton empezara a pedir dos, su corrida cambiaria — y esto no es
        # un cambio de criterio para el raton.
        self.assertEqual(self._roles("mouse").count("transcriptoma"), 1)
        self.assertEqual(self._roles("mouse").count("transcriptoma_fondo"), 0)

    def test_el_humano_pide_LOS_DOS(self):
        self.assertEqual(self._roles("human").count("transcriptoma"), 1)
        self.assertEqual(self._roles("human").count("transcriptoma_fondo"), 1)

    def test_y_cada_uno_con_SU_nombre(self):
        diana = self._por_rol("human", "transcriptoma")[0]
        fondo = self._por_rol("human", "transcriptoma_fondo")[0]
        self.assertEqual(diana.filename, "transcriptoma_3utr_human.fa")
        self.assertEqual(fondo.filename, "transcriptoma_3utr.fa")

    def test_el_del_fondo_DICE_que_es_del_fondo_y_por_que(self):
        fondo = self._por_rol("human", "transcriptoma_fondo")[0]
        self.assertIn("fondo", fondo.what.lower())
        self.assertIn("Mus musculus", fondo.what)

    def test_los_dos_cierran_el_MISMO_frente(self):
        for rol in ("transcriptoma", "transcriptoma_fondo"):
            with self.subTest(rol):
                self.assertEqual(
                    self._por_rol("human", rol)[0].fronts, ("offtarget_seed",)
                )

    def test_NINGUN_rol_sale_dos_veces(self):
        # `read_deposit` busca el PRIMERO con ese rol, asi que dos filas con el mismo rol
        # darian una respuesta silenciosamente equivocada.
        for slug in ("mouse", "human"):
            roles = self._roles(slug)
            with self.subTest(slug):
                self.assertEqual(len(roles), len(set(roles)))


if __name__ == "__main__":
    unittest.main()
