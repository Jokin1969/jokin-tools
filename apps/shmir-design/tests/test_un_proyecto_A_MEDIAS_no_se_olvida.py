"""Un proyecto elegido y NO reabrible se queda elegido, y se abre solo al subir la entrada.

**Reportado (2026-09-04)**: *«después de llegar donde llegué, habiendo empezado desde
cero, luego seleccionado el proyecto que tenía… sigue pidiéndome lo de la especie. A
pesar de que ya le he metido el proyecto que tiene esa información»*. Y además: *«ahora
no sale eso en amarillo de que le falta»*.

**Las dos mitades son el mismo fallo mío, y la segunda es la peor.**

`_paso_cero_proyecto` avisaba de que al proyecto le faltaba la secuencia y acto seguido
**se olvidaba de él** (`session_state.pop`). Así que:

1. el aviso se pintaba UNA vez y desaparecía en el siguiente repintado —y en Streamlit
   cada tecla es un repintado—, mientras la exigencia de contestar los pasos 1 y 2 se
   quedaba. **La app dejaba de explicar por qué estaba preguntando**, que es peor que no
   avisar: el aviso desaparecido se lee como que ya está resuelto;
2. y al subir la secuencia, el proyecto elegido **no era el que se abría**: había que ir
   a la barra lateral, marcar la casilla y volver a elegirlo a mano (errata nº 83). O
   sea que el mensaje nombraba el paso y la app no lo daba.

Ahora un proyecto elegido **se queda elegido** aunque no se pueda reabrir solo: el aviso
sigue ahí mientras el motivo siga ahí, y la barra lateral recibe ese slug para abrirlo en
cuanto haya secuencia — que es cuando la migración de la entrada se escribe sola
(errata nº 80).

Regla 5: escritos antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

FUENTE = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(l for l in texto.split("\n") if not l.lstrip().startswith("#"))


def _cuerpo(nombre: str) -> str:
    limpia = _sin_comentarios(FUENTE)
    inicio = limpia.index(f"def {nombre}")
    return limpia[inicio : limpia.index("\ndef ", inicio + 10)]


class TestNoSeOlvidaDelProyectoElegido(unittest.TestCase):
    def test_el_paso_cero_NO_borra_lo_elegido_al_avisar(self):
        """Olvidarlo sólo puede ser una DECISIÓN de quien mira, nunca automático.

        El `pop` automático era lo que hacía desaparecer el aviso —y con él la
        explicación de por qué se sigue preguntando— al primer repintado. Dentro de un
        botón es lo contrario: es la salida explícita «elegir otro».
        """
        cuerpo = _cuerpo("_paso_cero_proyecto")
        rama = cuerpo[cuerpo.index('if not vuelta["reabrible"]'):]
        rama = rama[:rama.index("st.success")]
        for linea in rama.split("\n"):
            if 'pop("p0_retomado"' not in linea:
                continue
            sangria = len(linea) - len(linea.lstrip())
            self.assertGreater(
                sangria, 12,
                "el paso 0 se olvida del proyecto SIN que nadie se lo pida: el aviso "
                "dura un repintado y la pregunta se queda sin explicar.",
            )

    def test_y_la_barra_lateral_RECIBE_el_proyecto_pendiente(self):
        # Sin esto, el mensaje nombra el paso —«elígelo en la barra lateral»— y la app
        # no lo da: hay que repetir a mano lo que ya se contestó arriba.
        self.assertRegex(
            _sin_comentarios(FUENTE),
            r"_panel_proyecto\([^)]*pendiente\s*=",
            "la barra lateral no recibe el proyecto elegido a medias, así que al subir "
            "la secuencia no se abre el que se eligió.",
        )

    def test_con_un_pendiente_la_barra_lateral_NO_vuelve_a_preguntar(self):
        cuerpo = _cuerpo("_panel_proyecto")
        casilla = cuerpo.index("pr_activo_")
        self.assertIn(
            "pendiente", cuerpo[:casilla],
            "con un proyecto ya elegido arriba, la casilla de guardar vuelve a "
            "preguntar lo mismo: dos respuestas para la misma pregunta.",
        )


if __name__ == "__main__":
    unittest.main()
