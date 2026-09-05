"""Un proyecto de antes recupera su entrada la primera vez que se abre con ella.

**Reportado con la captura (2026-09-04)**: se elige `Intento_17` —3 registros, última
actividad 2026-09-02— y sale «este proyecto se creó antes de que la app guardara la
secuencia de entrada». Y la pregunta: *«no parece cierto que ese proyecto se creara cuando
dice el comentario»*.

**El mensaje era cierto y aun así estaba mal.** Cierto porque el campo `sequence` entró en
`proyecto.json` el 2026-09-04, así que cualquier proyecto anterior —incluido uno de
anteayer— no lo tiene. Y mal por dos razones:

1. **fecha la causa en vez de decir qué hacer.** «Se creó antes de que la app guardara X»
   invita a comprobar cuándo se creó, que es información que no sirve para nada: lo que
   hay que saber es que falta la entrada y que se arregla subiéndola;
2. **y no se arreglaba.** Subir la secuencia abría el proyecto, sí — pero no la guardaba,
   así que al día siguiente salía el mismo aviso. Un mensaje que dice «súbela como
   siempre» y deja el proyecto igual que estaba es una tarea de disciplina, no un arreglo.

Ahora **se rellena sola**: al abrir con la secuencia delante, si el proyecto no la tenía y
su md5 es el que el proyecto declara, se escribe. El md5 es lo que lo hace seguro — es la
misma comprobación que ya impide abrir un proyecto con otra entrada, así que rellenar no
puede meter una secuencia que no sea la suya.

Regla 5: escritos antes.
"""

import json
import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_reference, sequence_md5
from shmir_design.store import PROJECT_FILE

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestSeRellenaAlAbrirla(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="proyectos_"))
        self.secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(self.secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        payload, fuente = presentation.anatomy_payload(anatomia)
        # Un proyecto COMO LOS DE ANTES: con todo menos la secuencia.
        directorio = self.raiz / "Intento_17"
        directorio.mkdir(parents=True)
        (directorio / PROJECT_FILE).write_text(
            json.dumps({
                "slug": "Intento_17", "created": "2026-09-02",
                "sequence_md5": sequence_md5(self.secuencia),
                "sequence_length": len(self.secuencia),
                "species": "raton", "anatomy": payload, "anatomy_source": fuente,
            }), encoding="utf-8",
        )
        (directorio / "registro.jsonl").write_text("", encoding="utf-8")

    def _guardado(self) -> dict:
        return json.loads(
            (self.raiz / "Intento_17" / PROJECT_FILE).read_text("utf-8")
        )

    def test_antes_de_abrirlo_NO_es_reabrible(self):
        self.assertFalse(presentation.project_resume(self.raiz, "Intento_17")["reabrible"])

    def test_al_abrirlo_CON_la_secuencia_se_rellena(self):
        presentation.project_open(
            self.raiz, "Intento_17", expect_md5=sequence_md5(self.secuencia),
            sequence=self.secuencia,
        )
        self.assertEqual(
            self._guardado()["sequence"], "".join(self.secuencia.split()).upper()
        )

    def test_y_a_partir_de_ahi_YA_es_reabrible_solo(self):
        presentation.project_open(
            self.raiz, "Intento_17", expect_md5=sequence_md5(self.secuencia),
            sequence=self.secuencia,
        )
        vuelta = presentation.project_resume(self.raiz, "Intento_17")
        self.assertTrue(vuelta["reabrible"])
        self.assertEqual(vuelta["secuencia"], "".join(self.secuencia.split()).upper())

    def test_una_secuencia_que_NO_es_la_suya_no_rellena_nada(self):
        # El md5 ya impide abrirlo; lo que se comprueba es que tampoco escriba.
        otra = load_reference(REFERENCES["NM_000311.5"])
        with self.assertRaises(ShmirDesignError):
            presentation.project_open(
                self.raiz, "Intento_17", expect_md5=sequence_md5(otra), sequence=otra,
            )
        self.assertNotIn("sequence", {k: v for k, v in self._guardado().items() if v})

    def test_un_proyecto_que_YA_la_tiene_no_se_reescribe(self):
        # Rellenar es una migración de una vez, no una escritura en cada apertura: el
        # `proyecto.json` es la mitad del par que el log encadena.
        presentation.project_open(
            self.raiz, "Intento_17", expect_md5=sequence_md5(self.secuencia),
            sequence=self.secuencia,
        )
        antes = (self.raiz / "Intento_17" / PROJECT_FILE).stat().st_mtime_ns
        presentation.project_open(
            self.raiz, "Intento_17", expect_md5=sequence_md5(self.secuencia),
            sequence=self.secuencia,
        )
        self.assertEqual(
            antes, (self.raiz / "Intento_17" / PROJECT_FILE).stat().st_mtime_ns
        )


class TestLaEtiquetaDiceQUEson(unittest.TestCase):
    """«3 registro(s)» se leía como «tres cosas que se pueden abrir». No lo son."""

    def test_no_se_llaman_registros_a_secas(self):
        from shmir_design.presentation import PROJECT_ENTRY_WORD

        # Un «registro» es una LÍNEA del historial de ese proyecto —una corrida
        # guardada, una selección, una nota—, no otro proyecto ni otra cosa que abrir.
        self.assertNotIn("registro", PROJECT_ENTRY_WORD.lower())


if __name__ == "__main__":
    unittest.main()
