"""Los cuatro modales se comportan IGUAL frente al proyecto y al guardado.

**Reportado el 2026-09-02**: *«si BLAST, seed, off-targets y splicing tienen tres
comportamientos distintos frente al deposito, es que cada uno se escribio por su
cuenta»*. Lo mismo valia para el proyecto:

  · BLAST se negaba ANTES —sin proyecto no pinta el `file_uploader`—;
  · los otros tres CALCULABAN y avisaban DESPUES con un `st.caption`, que es el elemento
    mas silencioso que hay y aparece justo detras de un resultado. Quien lo pasa por alto
    cierra la pestaña y pierde el trabajo sin enterarse.

Y en el guardado: `verdicts_changed` solo corria en BLAST, porque era el unico que le
pasaba `tiling` y `seleccion` a `_guardar_corrida`. Los otros tres daban un «Guardada en
el log» plano — y el CERO, que existe justamente para que un guardado que no mueve nada
se vea, faltaba en tres de los cuatro.

Este test mira el FUENTE de la pagina, como los de la regla 6: lo que se comprueba es que
los cuatro pasen por las mismas piezas, no que una funcion concreta haga lo suyo.
"""

import re
import unittest
from pathlib import Path

PAGINA = (Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py").read_text(
    encoding="utf-8"
)

#: Los cuatro, por el nombre de su funcion. Si entra un quinto modal y no se añade aqui,
#: este test no lo echara de menos — por eso el de abajo los DERIVA del fuente.
MODALES = ("_modal_blast", "_modal_seed", "_modal_offtarget", "_modal_empalme")


def _cuerpo(nombre: str) -> str:
    inicio = PAGINA.index(f"def {nombre}(")
    siguiente = PAGINA.find("\ndef ", inicio + 1)
    return PAGINA[inicio: siguiente if siguiente > 0 else len(PAGINA)]


class TestLosModalesSonLosQueSonDE_VERDAD(unittest.TestCase):

    def test_la_lista_se_DERIVA_del_fuente(self):
        # Si un quinto modal entra y no pasa por lo de abajo, hay que enterarse aqui y no
        # el dia que alguien pierda una corrida.
        vivos = set(re.findall(r"^def (_modal_\w+)\(", PAGINA, re.M))
        self.assertEqual(vivos, set(MODALES))


class TestNingunoCalculaSinPROYECTO(unittest.TestCase):

    def test_los_tres_que_EJECUTAN_se_niegan_antes(self):
        for modal in ("_modal_seed", "_modal_offtarget"):
            with self.subTest(modal):
                self.assertIn("run_allowed(proyecto)", _cuerpo(modal))

    def test_y_BLAST_sigue_negandose_por_su_via(self):
        # El suyo es `upload_allowed`: lo que no se puede empezar ahi es la SUBIDA del
        # resultado, no un calculo. Son dos verbos y la misma decision.
        self.assertIn("upload_allowed(proyecto)", _cuerpo("_modal_blast"))

    def test_la_negativa_va_ANTES_del_boton_que_calcula(self):
        # Si fuera despues, el trabajo ya estaria hecho y tirado.
        for modal, boton in (
            ("_modal_seed", "Buscar colisiones"),
            ("_modal_offtarget", "Contar off-targets"),
        ):
            cuerpo = _cuerpo(modal)
            with self.subTest(modal):
                self.assertLess(
                    cuerpo.index("run_allowed(proyecto)"), cuerpo.index(boton),
                    f"{modal}: se niega DESPUES de ofrecer «{boton}», así que el trabajo "
                    f"se hace y se pierde.",
                )


class TestLosCUATRO_dicenQUE_CAMBIO_al_guardar(unittest.TestCase):

    def test_los_cuatro_pasan_tiling_y_seleccion(self):
        # `_guardar_corrida` solo cuenta veredictos si los recibe; sin ellos la
        # confirmacion es un «Guardada» plano y el cero no se ve.
        for modal in MODALES:
            with self.subTest(modal):
                cuerpo = _cuerpo(modal)
                if "_guardar_corrida(" not in cuerpo:
                    continue
                self.assertIn("tiling=tiling", cuerpo)
                self.assertIn("seleccion=seleccion", cuerpo)

    def test_y_los_cuatro_usan_el_MISMO_guardado(self):
        # Cuatro formularios distintos serian cuatro sitios donde olvidar la fecha.
        for modal in MODALES:
            with self.subTest(modal):
                self.assertIn("_guardar_corrida(", _cuerpo(modal))


if __name__ == "__main__":
    unittest.main()
