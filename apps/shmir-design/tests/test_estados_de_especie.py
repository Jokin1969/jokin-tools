"""La página pintada con CADA especie, no sólo con el ratón.

Regla 5: escrito antes de que el inventario tenga el eje.

**Qué desbloquea (D2 de `docs/revision-preparacion-humano.md`).** `data/estados.toml`
modelaba `corrida`, `fichero:<rol>`, `modal:<corrida>`, `proyecto` y `rerun`. **No
modelaba la especie**, así que los 35 estados de hoy describían todos una corrida de
ratón — y es la contrapartida del principio nº 15 que ya se aprendió con el eje de
proyecto: *un inventario que no puede expresar un estado no puede echarlo de menos.*

**Y este eje NO está bloqueado**, que es lo que lo separa de los otros once: elegir la
especie es `selectbox.set_value(...)`, no hace falta ningún `file_uploader`. Los cuatro
valores se pueden pintar HOY.

**Lo que se ve al pintarlo**, medido y no supuesto:

| especie | bloques | huecos de subida |
|---|---|---|
| sin elegir | 5 | ninguno — la página no llega al gestor |
| `mouse` | 16 | 4 |
| `human` | 19 | **7** |
| no declarada | 5 | ninguno, y dice cómo se declara |

Los **tres huecos de más** del humano son `aav_casete_human.fa`, `polya_db_human.tsv` y
`apa_medido_human.tsv`: tres roles cuyo lado FALTA no lo había pintado nadie en la
especie que va a correr. Y `apa_medido` cambia de estado con la especie —`NO USADO` en
ratón, `FALTA` en humano—, o sea que uno de los cinco estados del panel sólo se pintaba
en un lado del eje que no existía.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.presentation import OTHER_SPECIES  # noqa: E402
from shmir_design.species import SPECIES, required_files, resolve  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT = True
except ImportError:  # rule2-ok: ausencia de una dependencia OPCIONAL de la interfaz.
    # Mismo criterio que en `test_estados_de_fichero.py`: el motivo se enseña en el skip
    # y el núcleo sigue siendo stdlib pura.
    STREAMLIT = False

RAIZ = Path(__file__).resolve().parent.parent
from tests.pagina import sin_proyectos  # noqa: E402

APP = RAIZ / "ui" / "streamlit_app.py"

#: El valor del eje que significa «la opción explícita de especie no declarada». Se
#: importa de `presentation` en vez de escribirlo: el desplegable y el marcador tienen
#: que nombrar lo mismo, y transcrito el día que cambie el texto quedan dos (principio
#: nº 13).
ESPECIE_NO_DECLARADA = OTHER_SPECIES


def _app():
    return AppTest.from_file(str(APP), default_timeout=90).run()


def pintada_sin_especie():
    """La página recién abierta: el desplegable SIN valor. El marcador del auditor."""
    return _app()


def pintada_como(especie: str):
    """La página pintada con ESA especie elegida. El marcador del auditor.

    Recibe el SLUG —`mouse`, `human`— y resuelve el nombre científico, que es lo que el
    desplegable enseña. El slug es lo estable; el rótulo es texto de la interfaz, y
    escribirlo en cada test sería la regla de siempre incumplida.

    `ESPECIE_NO_DECLARADA` se pasa tal cual: no es una especie, es la opción explícita.
    """
    valor = (
        ESPECIE_NO_DECLARADA if especie == ESPECIE_NO_DECLARADA
        else resolve(especie).scientific
    )
    app = _app()
    app.selectbox[0].set_value(valor).run()
    return app


def _huecos(app) -> set[str]:
    """Los nombres que el panel pide SUBIR. Es la vista por fichero, en pantalla."""
    return {
        w.label.removeprefix("Subir ")
        for w in app.get("file_uploader")
        if w.label.startswith("Subir ")
    }


def _texto(app) -> str:
    """Todo lo que la página escribe. Los `caption` VAN DENTRO, y no es un detalle: la
    primera versión de este ayudante los dejaba fuera y el test decía que la página no
    explicaba cómo se declara una especie —cuando sí lo hace, en un `st.caption`—. Es el
    principio nº 18 sobre el propio comprobador: un detector que mira menos que la
    pantalla acusa a la app de lo que le falta a él."""
    partes = [m.value for m in app.get("markdown")]
    partes += [e.label for e in app.get("expander")]
    partes += [w.label for w in app.get("file_uploader")]
    partes += [str(a.value) for a in app.get("warning")]
    partes += [str(a.value) for a in app.get("info")]
    partes += [str(c.value) for c in app.get("caption")]
    return "\n".join(partes)


def _ajenos(slug: str) -> set[str]:
    """Los nombres del depósito que NO son de esta especie. Derivados, no escritos."""
    mios = {f.filename for f in required_files(resolve(slug))}
    fuera: set[str] = set()
    for otra in SPECIES:
        if otra == resolve(slug).slug:
            continue
        fuera |= {f.filename for f in required_files(resolve(otra))} - mios
    return fuera


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
class TestLaPaginaSePINTAconCADAespecieDECLARADA(unittest.TestCase):
    """Y el barrido va por TODAS las declaradas, no por las dos que hay: una especie
    nueva queda cubierta sin que nadie se acuerde de añadir su caso."""

    def test_cada_especie_pide_SUS_ficheros_y_NINGUNO_de_otra(self):
        # Es el guardia de la errata nº 157 desde el otro lado: aquél mide lo que la app
        # EMITE en una corrida; éste, lo que la PÁGINA pide subir.
        with sin_proyectos():
            for slug in sorted(SPECIES):
                with self.subTest(slug):
                    huecos = _huecos(pintada_como(slug))
                    self.assertTrue(huecos, "ninguna especie pide cero ficheros")
                    ajenos = sorted(n for n in _ajenos(slug) if n in huecos)
                    self.assertEqual(ajenos, [], f"{slug} pide ficheros de otra especie")

    def test_y_el_HUMANO_pide_su_CASETE_aunque_el_MURINO_este_versionado(self):
        """El agujero que cerró la errata nº 157, ahora visible en la pantalla.

        `aav_casete.fa` está versionado en git, así que SIEMPRE está en el depósito. Con
        el nombre murino escrito, el humano lo daba por presente — un frente en verde con
        el vector de otra especie detrás.
        """
        with sin_proyectos():
            huecos = _huecos(pintada_como("human"))
        self.assertIn("aav_casete_human.fa", huecos)
        self.assertNotIn("aav_casete.fa", huecos)

    def test_el_RATON_sigue_teniendo_el_suyo_EN_el_deposito(self):
        # Control adversario: si la página dejara de reconocer los ficheros presentes,
        # lo de arriba pasaría igual de bien y no significaría nada.
        with sin_proyectos():
            huecos = _huecos(pintada_como("mouse"))
        self.assertNotIn("aav_casete.fa", huecos)
        self.assertIn("refseq_rna.fa", huecos)

    def test_y_el_CASETE_CAMBIA_DE_ESTADO_con_la_especie(self):
        """En ratón `aav_casete.fa` está versionado en git, así que su frente cierra y no
        sale como hueco; en humano `aav_casete_human.fa` no existe y sale FALTA.

        Es uno de los cinco estados del panel de refinamiento cuyo otro lado sólo se
        pinta cambiando de especie: sin este eje, los dos lados de la misma fila no se
        podían ver.

        **EL EJEMPLO ERA `apa_medido` y CADUCÓ el 2026-09-09** (principio nº 56): valía
        porque en humano no había tabla de PolyA_DB, y al llegar `polya_db_human.tsv` su
        frente cierra también ahí, así que la fila sale `NO USADO` en las dos. Lo que
        caducó es el EJEMPLO, no el eje — y el caso que lo sustituye es de la misma
        forma: un fichero que existe para una especie y no para la otra.
        """
        with sin_proyectos():
            raton, humano = _huecos(pintada_como("mouse")), _huecos(pintada_como("human"))
        self.assertNotIn("aav_casete.fa", raton)
        self.assertIn("aav_casete_human.fa", humano)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
class TestLosDosValoresQueNOsonUnaEspecie(unittest.TestCase):

    def test_SIN_ELEGIR_no_llega_al_gestor(self):
        """Es lo que ve quien abre la app, y `species_default()` devuelve `None` a
        propósito: un valor inicial parecía configurado y dejaba dos frentes rotos."""
        with sin_proyectos():
            app = pintada_sin_especie()
        self.assertIsNone(app.selectbox[0].value)
        self.assertEqual(_huecos(app), set())

    def test_NO_DECLARADA_lo_DICE_y_tampoco_ofrece_subidas(self):
        """La opción explícita. Esconderla no hace que el caso desaparezca: hace que
        llegue sin aviso."""
        with sin_proyectos():
            app = pintada_como(ESPECIE_NO_DECLARADA)
        self.assertEqual(_huecos(app), set())
        texto = _texto(app).lower()
        self.assertIn("no está declarada", texto)
        # Y dice CÓMO se declara, que es la única salida real.
        self.assertIn("species.species", texto)

    def test_y_NO_DECLARADA_pinta_algo_que_SIN_ELEGIR_no(self):
        """Control adversario: los dos se quedan sin gestor, así que sin esto «pinta lo
        mismo» y «pinta el aviso» darían el mismo verde — y entonces uno de los dos
        sería un estado CONSTANTE y no propio."""
        with sin_proyectos():
            sin, otra = _texto(pintada_sin_especie()), _texto(pintada_como(ESPECIE_NO_DECLARADA))
        self.assertNotEqual(sin, otra)
        self.assertGreater(len(otra), len(sin))


if __name__ == "__main__":
    unittest.main()
