"""Un proyecto guardado se reabre sin volver a subir nada, y enseña sus candidatos.

**Pedido (2026-09-03)**: «si yo esto ya lo he hecho antes y lo tengo grabado en un
proyecto, por qué no me pregunta antes de nada, al principio... si digo que sí, elijo cuál
quiero abrir e inmediatamente me mostraría el resultado de la búsqueda de candidatos que se
guardó en el proyecto.»

**Y eso no se podía hacer**, porque el proyecto no guardaba la secuencia: `proyecto.json`
tenía su `sequence_md5` y su `sequence_length`, que sirven para COMPROBAR una secuencia que
ya tengas delante y no para recuperarla. Así que reabrir exigía volver a subir el mismo
fichero, y el md5 sólo servía para decirte que te habías equivocado de fichero.

Es la misma regla que el proyecto ya tenía escrita para el registro —«un veredicto tiene
que sobrevivir a la app que lo escribió»— y estaba a medias: **sobrevivía el veredicto y
no la entrada sobre la que se emitió**. Un log de decisiones sobre una secuencia que no
está no se puede releer; a lo sumo se puede comprobar.

### Lo que NO se hace, y va escrito

La secuencia se guarda **verbatim**. No se reconstruye, no se deduce del md5 —no se puede—
y no se rellena: es la regla 1 por su lado bueno. Y el tilado **no se guarda**: se vuelve a
calcular al abrir, porque es determinista y cuesta 0,33 s. Guardar lo derivado sería tener
dos definiciones del panel y ninguna que mande.

Regla 5: escritos antes.
"""

import json
import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.store import PROJECT_FILE, ProjectStore

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _entrada():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    return secuencia, anatomia


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaEntradaSEGUARDAconElProyecto(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="proyectos_"))
        self.secuencia, self.anatomia = _entrada()
        payload, fuente = presentation.anatomy_payload(self.anatomia)
        presentation.project_create(
            self.raiz, slug="prueba", date="2026-09-03", sequence=self.secuencia,
            species="raton", anatomy=payload, anatomy_source=fuente,
        )

    def test_la_secuencia_esta_en_proyecto_json_TAL_CUAL(self):
        crudo = json.loads((self.raiz / "prueba" / PROJECT_FILE).read_text("utf-8"))
        self.assertEqual(crudo["sequence"], "".join(self.secuencia.split()).upper())

    def test_al_reabrir_vuelve_la_secuencia_SIN_subir_nada(self):
        vuelta = presentation.project_resume(self.raiz, "prueba")
        self.assertTrue(vuelta["reabrible"])
        self.assertEqual(vuelta["secuencia"], "".join(self.secuencia.split()).upper())
        self.assertEqual(vuelta["especie"], "raton")

    def test_y_la_ANATOMIA_vuelve_entera_con_su_procedencia(self):
        vuelta = presentation.project_resume(self.raiz, "prueba")
        anatomia = vuelta["anatomia"]
        self.assertEqual(anatomia.utr3, self.anatomia.utr3)
        self.assertEqual(anatomia.cds, self.anatomia.cds)
        self.assertEqual(anatomia.length, self.anatomia.length)
        # La PROCEDENCIA no se pierde: de ella cuelga que los tercios sean fiables.
        self.assertIs(anatomia.source, RegionSource.FIXTURE_VERIFICADO)

    def test_con_eso_SE_VUELVEN_A_SACAR_los_mismos_candidatos(self):
        vuelta = presentation.project_resume(self.raiz, "prueba")
        de_nuevo = presentation.page_run(
            species=vuelta["especie"], sequence=vuelta["secuencia"],
            anatomy=vuelta["anatomia"],
        )
        original = presentation.page_run(
            species="raton", sequence=self.secuencia, anatomy=self.anatomia,
        )
        self.assertEqual(
            presentation.chosen_starts(de_nuevo.selection),
            presentation.chosen_starts(original.selection),
        )

    def test_una_secuencia_MANIPULADA_en_el_fichero_aborta(self):
        # El `proyecto.json` es un fichero y se puede editar. Si la secuencia deja de
        # cuadrar con el md5 que el propio proyecto declara, abrirlo daría un panel con
        # la forma correcta sobre otra entrada. Misma disciplina que la cadena del log.
        fichero = self.raiz / "prueba" / PROJECT_FILE
        crudo = json.loads(fichero.read_text("utf-8"))
        crudo["sequence"] = "A" + crudo["sequence"][1:]
        fichero.write_text(json.dumps(crudo, ensure_ascii=False, indent=2), "utf-8")
        with self.assertRaises(ShmirDesignError) as caso:
            ProjectStore.open(self.raiz, "prueba")
        self.assertIn("md5", str(caso.exception))


class TestUnProyectoDeANTESsigueAbriendOSE(unittest.TestCase):
    """Los que ya existen no tienen secuencia. Se abren, y se DICE que falta."""

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="proyectos_"))
        directorio = self.raiz / "viejo"
        directorio.mkdir(parents=True)
        (directorio / PROJECT_FILE).write_text(
            json.dumps({
                "slug": "viejo", "created": "2026-08-01",
                "sequence_md5": "0" * 32, "sequence_length": 1242,
                "species": "raton", "anatomy": None, "anatomy_source": "sin_resolver",
            }), encoding="utf-8",
        )
        (directorio / "registro.jsonl").write_text("", encoding="utf-8")

    def test_se_abre_igual(self):
        almacen = ProjectStore.open(self.raiz, "viejo")
        self.assertEqual(almacen.project.slug, "viejo")

    def test_pero_NO_es_reabrible_solo_y_se_dice_por_que(self):
        vuelta = presentation.project_resume(self.raiz, "viejo")
        self.assertFalse(vuelta["reabrible"])
        self.assertIsNone(vuelta["secuencia"])
        # Ni se inventa la secuencia ni se calla: se dice qué falta y qué hacer.
        self.assertIn("secuencia", vuelta["motivo"])

    def test_y_no_se_reconstruye_NADA_del_md5(self):
        # Regla 1 por su lado bueno: del md5 no sale la secuencia, y no se finge.
        vuelta = presentation.project_resume(self.raiz, "viejo")
        self.assertIsNone(vuelta["anatomia"])


if __name__ == "__main__":
    unittest.main()
