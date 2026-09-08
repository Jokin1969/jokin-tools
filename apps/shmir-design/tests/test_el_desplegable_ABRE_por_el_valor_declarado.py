"""Un desplegable se abre por el valor DECLARADO, no por el primero de la lista.

**Reportado (2026-09-08)**: *«la corrida de seed_colision que guardé salió con ventana
2-7, NO ESTÁNDAR… ¿hay algún ajuste que restablecer para que salga 2-8?»*.

**Lo hay, y lo eligió la app.** `seed_setting_rows` daba las opciones y la página llamaba
a `st.selectbox` **sin `index=`**, así que Streamlit preselecciona la PRIMERA. Y la
primera no es la declarada:

| ajuste | lo que preseleccionaba | lo que declara `SeedParams` |
|---|---|---|
| `window` | `2-7` (alfabético) | **`2-8`** |
| `level` | `nucleo` (orden de `LEVELS`) | **`ambos`** |
| `species_prefix` | `mmu-` (escrito a mano) | `None` = lo resuelve la especie |

O sea que **el orden alfabético decidía un parámetro científico**: con `2-7` el espacio
de seeds pasa de 16.384 a 4.096 y la tasa base de 9,7 % a 31,1 %, así que un `LIMPIO`
significa mucho menos. Y con `level=nucleo` la capa ampliada no corre.

Es el principio nº 32 en la interfaz: **una opción que nadie eligió pasa a ser la
configuración**, y se lee como si alguien la hubiera decidido. Este proyecto ya lo tenía
escrito para el desplegable de especies —«`modelo` como valor inicial era PEOR que
vacío: parecía configurado»— y no se había aplicado a este eje.

Y el `mmu-` escrito en `opciones` es la puerta de atrás que `--mirbase-especies` cerró en
el CLI: un prefijo tecleado que sobre otra especie da CERO colisiones, que parece una
buena noticia. La página deja de ofrecerlo: el prefijo lo resuelve la especie de la
corrida.

Regla 5: escritos antes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design import seed_scan

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


class TestElIndiceEsElDelValorDECLARADO(unittest.TestCase):
    def test_cada_ajuste_dice_por_que_opcion_abrirse(self):
        for fila in presentation.seed_setting_rows(seed_scan.DEFAULTS):
            if fila["fijo"]:
                continue
            with self.subTest(ajuste=fila["ajuste"]):
                self.assertIn("indice", fila)
                self.assertEqual(
                    fila["opciones"][fila["indice"]], fila["por_defecto"],
                    "el desplegable abriría por una opción que nadie ha declarado",
                )

    def test_la_ventana_abre_por_2_8_y_NO_por_la_primera_alfabetica(self):
        fila = next(
            f for f in presentation.seed_setting_rows(seed_scan.DEFAULTS)
            if f["ajuste"] == "window"
        )
        self.assertEqual(fila["opciones"][fila["indice"]], "2-8")
        # El control adversario: si la lista dejara de estar ordenada al revés, este
        # test pasaría por casualidad y no diría nada.
        self.assertEqual(fila["opciones"][0], "2-7")

    def test_el_nivel_abre_por_ambos_y_NO_por_nucleo(self):
        fila = next(
            f for f in presentation.seed_setting_rows(seed_scan.DEFAULTS)
            if f["ajuste"] == "level"
        )
        self.assertEqual(fila["opciones"][fila["indice"]], "ambos")
        self.assertEqual(fila["opciones"][0], "nucleo")


class TestElPrefijoNoSeTECLEA(unittest.TestCase):
    """`mmu-` escrito en la lista de opciones es un dato de UNA especie en el código."""

    def test_el_desplegable_ya_no_ofrece_un_prefijo_escrito(self):
        fila = next(
            f for f in presentation.seed_setting_rows(seed_scan.DEFAULTS)
            if f["ajuste"] == "species_prefix"
        )
        self.assertNotIn("mmu-", fila["opciones"])

    def test_la_opcion_por_defecto_deja_que_lo_resuelva_la_corrida(self):
        fila = next(
            f for f in presentation.seed_setting_rows(seed_scan.DEFAULTS)
            if f["ajuste"] == "species_prefix"
        )
        elegido = fila["opciones"][fila["indice"]]
        params = presentation.seed_params_from_form({"species_prefix": elegido})
        self.assertIsNone(
            params.species_prefix,
            "`None` es «no declarado» y es lo que hace que `run_scan` lo resuelva con "
            "la especie; `\"\"` sería «todas», que es otra cosa",
        )

    def test_TODAS_sigue_siendo_posible_y_NO_es_lo_mismo_que_no_declarado(self):
        params = presentation.seed_params_from_form({"species_prefix": "TODAS"})
        self.assertEqual(params.species_prefix, "")

    def test_sin_nada_en_el_formulario_no_se_inventa_un_prefijo(self):
        self.assertIsNone(presentation.seed_params_from_form({}).species_prefix)


class TestElMismoFalloEnElOTRO_MODAL(unittest.TestCase):
    """La familia, no el caso: el modal de off-targets tenía el mismo desplegable.

    Un comentario protege su clase; un mecanismo protege la siguiente (principio nº 31).
    Aquí lo que salió al barrer los OCHO `st.selectbox` de la página es que el de
    off-targets abría `null_seed` por una etiqueta que **ni siquiera estaba entre sus
    opciones**: `str(0 or "TODAS")` convierte una semilla de 0 —perfectamente válida— en
    la etiqueta de «sin filtro». Es la errata nº 18 otra vez: la pregunta era por el
    CONTENIDO y la comprobación miraba si el valor era falso.
    """

    def test_un_CERO_no_se_llama_TODAS(self):
        from shmir_design.offtarget import DEFAULTS as OFFTARGET

        fila = next(
            f for f in presentation.offtarget_setting_rows(OFFTARGET)
            if f["ajuste"] == "null_seed"
        )
        self.assertEqual(fila["por_defecto"], "0")
        self.assertIn(fila["por_defecto"], fila["opciones"])

    def test_todos_sus_ajustes_abren_por_lo_declarado(self):
        from shmir_design.offtarget import DEFAULTS as OFFTARGET

        for fila in presentation.offtarget_setting_rows(OFFTARGET):
            if fila["fijo"]:
                continue
            with self.subTest(ajuste=fila["ajuste"]):
                self.assertEqual(
                    fila["opciones"][fila["indice"]], fila["por_defecto"]
                )

    def test_y_la_pagina_tambien_le_pasa_el_indice(self):
        inicio = FUENTE.index("def _modal_offtarget")
        fin = FUENTE.find("\ndef ", inicio + 10)
        cuerpo = FUENTE[inicio : fin if fin != -1 else len(FUENTE)]
        limpio = "\n".join(
            l for l in cuerpo.split("\n") if not l.lstrip().startswith("#")
        )
        hueco = limpio.index("st.selectbox(")
        self.assertIsNotNone(
            re.search(r"index=ajuste\[.indice.\]", limpio[hueco : hueco + 400])
        )


class TestNINGUN_desplegable_abre_por_algo_que_nadie_declaro(unittest.TestCase):
    """El barrido de los OCHO, para que no haga falta acordarse del noveno."""

    def test_los_que_tienen_un_valor_declarado_lo_usan(self):
        # Se declara qué emisor de filas alimenta cada desplegable de ajustes. Los otros
        # —elegir un candidato, elegir un proyecto— no tienen «valor declarado»: su
        # primera opción es la respuesta correcta o un centinela «ninguno», y por eso no
        # entran. Un guardia con falsos positivos se acaba apagando.
        from shmir_design.offtarget import DEFAULTS as OFFTARGET

        for emisor, defectos in (
            (presentation.seed_setting_rows, seed_scan.DEFAULTS),
            (presentation.offtarget_setting_rows, OFFTARGET),
        ):
            for fila in emisor(defectos):
                if fila["fijo"]:
                    continue
                with self.subTest(emisor=emisor.__name__, ajuste=fila["ajuste"]):
                    self.assertIn(fila["por_defecto"], fila["opciones"])
                    self.assertEqual(
                        fila["opciones"][fila["indice"]], fila["por_defecto"]
                    )


class TestLaPaginaPASAelIndice(unittest.TestCase):
    """Emitirlo y no usarlo sería la novena vez del patrón de `page_run`."""

    def test_el_selectbox_del_modal_recibe_index(self):
        inicio = FUENTE.index("def _modal_seed")
        cuerpo = FUENTE[inicio : FUENTE.index("\ndef ", inicio + 10)]
        limpio = "\n".join(
            l for l in cuerpo.split("\n") if not l.lstrip().startswith("#")
        )
        hueco = limpio.index("st.selectbox(")
        trozo = limpio[hueco : hueco + 400]
        self.assertIsNotNone(
            re.search(r"index=ajuste\[.indice.\]", trozo),
            "el desplegable se pinta sin índice: vuelve a abrirse por la primera opción",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
