"""El fragmento de síntesis se saca DONDE se emite, y su hoja sabe qué se preguntó.

**Reportado (2026-09-08)**: *«el FASTA de fragmentos debería tener botón propio o bloque
copiable, como los demás»*.

Y tenía botón — **tres secciones más abajo**, dentro del ZIP de «Descargas» y sólo
después de pulsar «Seguir», mezclado con los otros seis ficheros. Es el principio nº 47:
**la salida va donde está el bloqueo**, y aquí el bloqueo está delante de la tabla del
fragmento, que es donde alguien decide qué manda a sintetizar. Los cuatro modales ya lo
hacen así —FASTA de BLAST, bloque de seed, FASTA de construcciones, bloque de
off-targets—; éste era el único emisor que mandaba a buscar su fichero a otra parte.

**Y al cablearlo salió lo de debajo, que es peor**: la página llamaba a
`fragment_bundle` **sin `tiling` ni `stores`**, así que `candidate_fronts` no se
calculaba y la hoja de pedido decía `sin_preguntar` para TODOS los candidatos — con las
corridas guardadas en el proyecto. Es la enésima vez del patrón de `page_run`: la
capacidad escrita, probada, y el llamador de verdad sin pasarla.

Eso importa aquí más que en otros sitios porque **es lo que se manda al banco**: la hoja
existe para que un candidato sin BLAST no se cuele en una tanda de once verificados, y
`sin_preguntar` en los once la deja diciendo lo mismo de todos.

Regla 5: escritos antes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.fragmento import FRONTS_FIELD_NOT_ASKED

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(l for l in texto.split("\n") if not l.lstrip().startswith("#"))


def _bloque_del_fragmento() -> str:
    """El trozo de la página que emite el fragmento, sin comentarios."""
    limpio = _sin_comentarios(FUENTE)
    inicio = limpio.index("Fragmento de síntesis — el intrón completo")
    return limpio[inicio : limpio.index("salida = output_bundle", inicio)]


class TestSeSacaDONDEseEmite(unittest.TestCase):
    def test_el_FASTA_tiene_boton_propio_ahi_mismo(self):
        bloque = _bloque_del_fragmento()
        self.assertIn("st.download_button(", bloque,
                      "el FASTA de fragmentos no se puede sacar donde se emite")

    def test_y_su_SEGUNDA_VIA_tambien(self):
        # Una vía y su alternativa no pueden compartir el mecanismo que falla: el botón
        # es `st.download_button`, que es justo el que se cuelga (errata nº 130).
        self.assertIn("_segunda_via(", _bloque_del_fragmento())

    def test_la_HOJA_DE_PEDIDO_sale_tambien(self):
        # Son DOS ficheros y no el mismo: el FASTA es lo que se sintetiza y la hoja es
        # lo que se lee. Sacar sólo uno deja al otro donde estaba.
        #
        # Y se comprueba sobre lo que EMITE el núcleo, no buscando el nombre en la
        # página: el nombre lo monta `output_stem` y escribirlo en la vista es justo el
        # fallo de al lado. La página itera lo que le den.
        paquete = {
            "Mus_musculus_fragmentos.fasta": ">x\nACGT\n",
            "Mus_musculus_fragmentos.txt": "hoja",
        }
        salen = [f["nombre"] for f in presentation.fragment_files(paquete)]
        self.assertEqual(sorted(salen), sorted(paquete))
        self.assertIn("for entrega in fragment_files(", _bloque_del_fragmento())

    def test_cada_uno_se_llama_por_LO_QUE_ES_y_no_por_su_fichero(self):
        paquete = {"x_fragmentos.fasta": ">x\n", "x_fragmentos.txt": "hoja"}
        for fila in presentation.fragment_files(paquete):
            with self.subTest(fichero=fila["nombre"]):
                self.assertNotEqual(fila["etiqueta"], fila["nombre"])

    def test_el_FASTA_para_comprobar_el_montaje_se_DERIVA_del_paquete(self):
        # El fallo real: la página pedía `f"{especie}_fragmentos.fasta"` con el nombre
        # CIENTÍFICO, y las claves las monta `output_stem`, que le quita los espacios.
        # `Mus musculus_…` contra `Mus_musculus_…`: nunca coincidían, así que la
        # comprobación del plásmido montado NUNCA tuvo el fichero emitido.
        from shmir_design.outputs import output_stem

        clave = f"{output_stem('Mus musculus')}_fragmentos.fasta"
        self.assertNotEqual(clave, "Mus musculus_fragmentos.fasta")
        paquete = {clave: ">x\nACGT\n", "x_fragmentos.txt": "hoja"}
        self.assertEqual(presentation.fragment_fasta_text(paquete), ">x\nACGT\n")

    def test_sin_casete_no_hay_FASTA_y_se_devuelve_vacio(self):
        # Sin casete el paquete trae sólo el `.txt` que explica por qué está vacío. Un
        # `KeyError` aquí tumbaría la sección; vacío es la verdad.
        self.assertEqual(
            presentation.fragment_fasta_text({"x_fragmentos.txt": "falta el casete"}), ""
        )

    def test_el_nombre_del_fichero_lo_pone_el_NUCLEO(self):
        # Regla 6, y además: el fichero es EL MISMO que va en el ZIP, así que no puede
        # tener dos nombres según por dónde se baje. Las claves salen del propio paquete.
        bloque = _bloque_del_fragmento()
        self.assertNotIn('f"{nombre}_fragmentos', bloque.replace("paquete.get", ""))


class TestLaHojaSABEqueSePregunto(unittest.TestCase):
    """`sin_preguntar` en los once no es una hoja: es una hoja sin contestar."""

    def test_la_pagina_le_pasa_el_tilado_y_los_almacenes(self):
        bloque = _bloque_del_fragmento()
        llamada = bloque[bloque.index("fragment_bundle(") :]
        llamada = llamada[: llamada.index(")") + 1]
        self.assertIn("tiling=", llamada,
                      "sin `tiling` la hoja dice «sin_preguntar» para TODOS")
        self.assertIn("stores=", llamada,
                      "sin `stores` no ve las corridas guardadas del proyecto")

    def test_CONTROL_sin_tiling_la_hoja_dice_que_nadie_pregunto(self):
        # La otra mitad: se comprueba que el valor por defecto SIGUE siendo honesto —
        # `None` es «nadie ha preguntado» y no `()`, que se leería como «no falta nada».
        self.assertEqual(FRONTS_FIELD_NOT_ASKED, "sin_preguntar")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
