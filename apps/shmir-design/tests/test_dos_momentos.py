"""Los ficheros de referencia son DOS momentos, no uno.

Regla 5: escritos antes. Regla 6: la pagina pinta, `presentation.py` decide.

**El problema.** El paso 3 pedia TODOS los ficheros antes de diseñar, como si los siete
frentes sirvieran para lo mismo. No sirven para lo mismo:

  - **Momento 1 — obtener candidatos.** Necesita la secuencia y su anatomia, y nada mas.
    Los filtros biofisicos y la prediccion de polyA corren sin ningun fichero externo.
  - **Momento 2 — refinar y descartar.** `mature.fa`, `transcriptoma_3utr.fa`,
    `refseq_rna.fa`… Estos ficheros no cambian QUE candidatos salen: cambian que
    veredicto lleva cada uno y **cuales acaban cayendo**.

Presentarlos juntos hace creer que sin ellos no se puede empezar, y eso es FALSO: se
puede diseñar hoy y refinar mañana.

**Y no se declara: se DERIVA.** La primera clase de este fichero corre el diseño con el
directorio de referencia VACIO y comprueba que salen candidatos; las siguientes miden,
fichero a fichero, que el conjunto de elegibles con un fichero es un SUBCONJUNTO del que
sale sin el. Es la unica forma honesta de escribir la frase del paso 5 — decirla sin
medirla seria una prosa que el codigo puede contradecir (principio nº 11).
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation, species
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.resources import load_from_manifest
from shmir_design.selection import default_config, is_eligible
from shmir_design.tiling import tile_utr
from tests.sin_logica import comprobar_sin_logica

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "reference"
PAGINA = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

CONEJO = "Oryctolagus cuniculus"


def _directorio(*ficheros: str) -> Path:
    """Un directorio de referencia con EXACTAMENTE esos ficheros (y el manifiesto)."""
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(DATOS / "manifest.tsv", tmp / "manifest.tsv")
    for nombre in ficheros:
        shutil.copy(DATOS / nombre, tmp / nombre)
    return tmp


def _entrada():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    return secuencia, anatomia


def _elegibles(directorio: Path, *ficheros: str) -> set[int]:
    """Los inicios de las ventanas ELEGIBLES con ese directorio de referencia."""
    secuencia, anatomia = _entrada()
    recursos = (
        load_from_manifest(directorio, species=species.resolve("raton"))
        if ficheros
        else None
    )
    extra = dict(recursos.as_kwargs()) if recursos is not None else {}
    informe = tile_utr(
        secuencia, anatomy=anatomia, species="raton", reference_dir=directorio, **extra
    )
    config = default_config()
    return {w.window.start for w in informe.windows if is_eligible(w, config)}


# ────────────────────── 1. el momento 1 no necesita NINGUN fichero ──────────────────────


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestSePuedeDiseñarSinNingunFichero(unittest.TestCase):
    """La afirmacion del paso 3 —«hoy: ninguno»— se COMPRUEBA corriendo el diseño.

    Declararla en un texto la dejaria a merced de que alguien añada mañana un fichero
    obligatorio para tilar y el texto siguiera diciendo que no hace falta ninguno.
    """

    @classmethod
    def setUpClass(cls):
        cls.vacio = _directorio()
        cls.secuencia, cls.anatomia = _entrada()

    def test_con_el_directorio_VACIO_salen_candidatos(self):
        corrida = presentation.page_run(
            species="raton",
            sequence=self.secuencia,
            anatomy=self.anatomia,
            tile_range=None,
        )
        self.assertTrue(corrida.selection.selection.chosen, "no salio ningun candidato")

    def test_y_la_piscina_de_elegibles_NO_esta_vacia(self):
        self.assertTrue(_elegibles(self.vacio))

    def test_el_paso_3_no_pide_NINGUN_fichero(self):
        """Y el numero sale de la lista, no de un texto escrito a mano."""
        paso = presentation.design_files_rows("raton", directory=self.vacio)
        self.assertEqual(paso["hacen_falta"], 0)
        self.assertEqual(paso["filas"], [])

    def test_tampoco_para_una_especie_SIN_declarar(self):
        """No es una propiedad del raton: es una propiedad del paso."""
        paso = presentation.design_files_rows(CONEJO, directory=self.vacio)
        self.assertEqual(paso["hacen_falta"], 0)

    def test_y_el_texto_del_paso_3_dice_de_donde_sale_la_anatomia(self):
        texto = presentation.design_files_rows("raton", directory=self.vacio)["texto"]
        self.assertIn("anatomía", texto)
        self.assertIn(".gb", texto)


# ─────────────── 2. los del momento 2 sólo QUITAN, nunca añaden ───────────────


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLosFicherosDeRefinamientoSoloQuitan(unittest.TestCase):
    """La frase del paso 5, medida: «no cambian cuáles son, cambian cuáles sobreviven».

    El invariante es de SUBCONJUNTO: con cualquier fichero de referencia, el conjunto de
    elegibles cabe dentro del que sale sin ninguno. Ninguno INVENTA un candidato.
    """

    @classmethod
    def setUpClass(cls):
        cls.base = _elegibles(_directorio())

    def _con(self, *ficheros: str) -> set[int]:
        return _elegibles(_directorio(*ficheros), *ficheros)

    def test_la_tabla_de_PolyA_DB_quita_17_y_no_añade_ninguna(self):
        """Es exactamente `selection.measured_promotion_cost`: 287 → 270."""
        con = self._con("polya_db_mouse.tsv")
        self.assertTrue(con <= self.base)
        self.assertEqual(len(self.base) - len(con), 17)

    def test_mature_fa_quita_2_y_no_añade_ninguna(self):
        con = self._con("mature.fa")
        self.assertTrue(con <= self.base)
        self.assertEqual(len(self.base) - len(con), 2)

    def test_la_mascara_del_raton_no_quita_NINGUNA_y_eso_no_es_que_no_haga_nada(self):
        """El 3'UTR murino no tiene ni un elemento repetitivo: el `(CTC)n` esta en el CDS.

        Sobre el humano esa misma mascara tumba cinco ventanas elegibles. El cero de
        aqui es un hecho de ESTA secuencia, no una propiedad del fichero.
        """
        con = self._con("rmsk_mouse.out", "rmsk_mouse.tbl")
        self.assertTrue(con <= self.base)
        self.assertEqual(con, self.base)

    def test_el_casete_no_quita_ninguna_en_esta_corrida(self):
        con = self._con("aav_casete.fa")
        self.assertTrue(con <= self.base)

    def test_TODOS_juntos_siguen_siendo_un_subconjunto(self):
        con = self._con(
            "polya_db_mouse.tsv", "rmsk_mouse.out", "rmsk_mouse.tbl", "mature.fa",
            "aav_casete.fa",
        )
        self.assertTrue(con <= self.base)
        self.assertEqual(len(con - self.base), 0)
        self.assertLess(len(con), len(self.base))


# ──────────────────── 3. el paso 5: estados, orden y contador ────────────────────


class TestElPanelDeRefinamiento(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.completo = _directorio(
            "polya_db_mouse.tsv", "rmsk_mouse.out", "rmsk_mouse.tbl", "mature.fa",
            "aav_casete.fa",
        )
        cls.panel = presentation.refinement_panel("raton", directory=cls.completo)
        cls.vacio = presentation.refinement_panel("raton", directory=_directorio())

    def test_la_frase_de_encuadre_la_emite_presentation_y_NO_la_pagina(self):
        self.assertEqual(
            self.panel["frase"],
            "Los candidatos ya están. Estos ficheros no cambian cuáles son, cambian "
            "cuáles sobreviven.",
        )
        self.assertIn("REFINEMENT_FRAMING", PAGINA)
        self.assertNotIn("cambian cuáles sobreviven", PAGINA)

    def test_el_contador_va_en_el_encabezado_con_su_fraccion_para_la_barra(self):
        progreso = self.panel["progreso"]
        # OCHO desde 2026-09-02: el plásmido del andamio pasa a ser un fichero de
        # primera clase y cierra el frente de los contextos del módulo.
        self.assertEqual(progreso["total"], 8)
        self.assertEqual(
            progreso["texto"], f"{progreso['cerrados']} de 8 frentes cerrados"
        )
        # La fraccion se DERIVA del total, no de un 7 escrito: con el frente
        # nuevo el denominador cambio solo y esto lo habria cazado igual.
        self.assertAlmostEqual(
            progreso["fraccion"], progreso["cerrados"] / progreso["total"]
        )

    def test_el_contador_se_MUEVE_con_lo_que_hay(self):
        self.assertGreater(
            self.panel["progreso"]["cerrados"], self.vacio["progreso"]["cerrados"]
        )

    def test_los_estados_son_CINCO_y_siempre_los_mismos(self):
        # 2026-09-06: eran cuatro. Entra `SIN PROCEDENCIA` (errata nº 120): un fichero
        # que ESTA en el deposito y aun asi no cierra su frente porque a su linea del
        # manifiesto le faltan campos. No es CERRADO (no cierra) y no es FALTA (esta),
        # y colapsarlo con cualquiera de los dos escondia la unica salida del problema.
        self.assertEqual(
            [e["estado"] for e in presentation.REFINEMENT_STATES],
            ["CERRADO", "SIN PROCEDENCIA", "FALTA", "OPCIONAL", "NO USADO"],
        )
        for entrada in presentation.REFINEMENT_STATES:
            self.assertTrue(entrada["color"])
            self.assertTrue(entrada["significa"])

    def test_ninguna_fila_sale_con_un_estado_que_no_este_en_la_leyenda(self):
        declarados = {e["estado"] for e in presentation.REFINEMENT_STATES}
        for panel in (self.panel, self.vacio):
            for fila in panel["filas"]:
                self.assertIn(fila["estado"], declarados, fila["nombre"])

    def test_la_leyenda_va_al_PRINCIPIO_de_la_seccion_y_no_en_un_tooltip(self):
        self.assertEqual(self.panel["leyenda"], list(presentation.REFINEMENT_STATES))

    def test_el_color_lo_pone_presentation_y_la_pagina_no_elige_ninguno(self):
        for fila in self.panel["filas"]:
            self.assertTrue(fila["color"])

    # ── el orden es por IMPACTO, no alfabetico ──

    def test_primero_las_que_cierran_un_frente_y_luego_las_opcionales(self):
        grupos = [f["grupo"] for f in self.panel["filas"]]
        self.assertEqual(grupos, sorted(grupos))
        self.assertEqual(set(grupos) - {0, 1}, set())

    def test_dentro_de_cada_grupo_las_resueltas_van_ABAJO(self):
        for grupo in (0, 1):
            resueltas = [
                f["resuelta"] for f in self.panel["filas"] if f["grupo"] == grupo
            ]
            self.assertEqual(resueltas, sorted(resueltas), grupo)

    def test_y_NO_es_el_orden_alfabetico(self):
        nombres = [f["nombre"] for f in self.panel["filas"]]
        self.assertNotEqual(nombres, sorted(nombres))

    # ── las opcionales se marcan sin ambigüedad ──

    def test_expresion_cerebro_sale_OPCIONAL_y_dice_que_no_bloquea_nada(self):
        fila = self._fila(self.panel, "expresion_cerebro.tsv")
        self.assertEqual(fila["estado"], "OPCIONAL")
        self.assertFalse(fila["bloquea"])
        self.assertIn("no bloquea", fila["por_que"].lower())

    def test_y_NO_se_parece_a_una_que_falta_de_verdad(self):
        opcional = self._fila(self.panel, "expresion_cerebro.tsv")
        falta = self._fila(self.panel, "transcriptoma_3utr.fa")
        self.assertEqual(falta["estado"], "FALTA")
        self.assertTrue(falta["bloquea"])
        self.assertNotEqual(opcional["color"], falta["color"])
        self.assertNotEqual(opcional["grupo"], falta["grupo"])

    # ── una alternativa no usada NO es una que falta ──

    def test_apa_medido_NO_sale_como_FALTA_si_su_frente_ya_esta_cerrado(self):
        """`polya_db_mouse.tsv` cierra `fraccion_isoforma_larga`. Pedir ademas
        `apa_medido.tsv` con un ámbar de «FALTA» manda a buscar algo que no hace falta."""
        fila = self._fila(self.panel, "apa_medido.tsv")
        self.assertEqual(fila["estado"], "NO USADO")
        self.assertFalse(fila["bloquea"])
        self.assertIn("polya_db_mouse.tsv", fila["por_que"])

    def test_pero_SIN_la_tabla_de_PolyA_DB_vuelve_a_FALTAR(self):
        fila = self._fila(self.vacio, "apa_medido.tsv")
        self.assertEqual(fila["estado"], "FALTA")
        self.assertTrue(fila["bloquea"])

    def test_el_hermano_de_rmsk_NO_se_confunde_con_una_alternativa(self):
        """El `.out` y el `.tbl` hacen falta LOS DOS: con uno solo el frente no se abre,
        asi que el que falta es FALTA y no «alternativa no usada»."""
        panel = presentation.refinement_panel(
            "raton", directory=_directorio("rmsk_mouse.out")
        )
        self.assertEqual(self._fila(panel, "rmsk_mouse.tbl")["estado"], "FALTA")

    # ── densidad ──

    def test_las_resueltas_se_colapsan_y_lo_que_falta_se_queda_abierto(self):
        for fila in self.panel["filas"]:
            self.assertEqual(
                fila["colapsada"], fila["estado"] in {"CERRADO", "NO USADO"}, fila["nombre"]
            )

    def test_una_colapsada_conserva_sus_ACCIONES(self):
        """Colapsar es una linea, no quitar los botones: sobre lo que esta se sigue
        pudiendo ver, reemplazar, borrar y descargar."""
        for fila in self.panel["filas"]:
            if fila["estado"] == "CERRADO":
                self.assertTrue(fila["acciones"])

    # ── ¿qué pasa si no lo consigo? ──

    def test_cada_fila_que_falta_dice_QUE_PASA_si_no_llega(self):
        for fila in self.panel["filas"]:
            if fila["bloquea"]:
                self.assertIn("NOT_RUN", fila["si_no_llega"])
                self.assertIn("INCOMPLETE", fila["si_no_llega"])

    def test_y_una_opcional_NO_dice_que_deje_nada_en_NOT_RUN(self):
        fila = self._fila(self.panel, "expresion_cerebro.tsv")
        self.assertNotIn("INCOMPLETE", fila["si_no_llega"])

    def test_cada_fila_sigue_trayendo_su_ficha_de_obtencion(self):
        for fila in self.panel["filas"]:
            self.assertTrue(fila["ficha"]["texto"])

    def _fila(self, panel, nombre):
        for fila in panel["filas"]:
            if fila["nombre"] == nombre:
                return fila
        self.fail(f"{nombre} no sale en el panel: {[f['nombre'] for f in panel['filas']]}")


# ─────────────────────── 4. cinco pasos, y el quinto DESPUES ───────────────────────


class TestCincoPasos(unittest.TestCase):

    def _pasos(self, **kwargs):
        return presentation.steps_rows(
            species="raton", sequence_loaded=True, directory=_directorio(), **kwargs
        )

    def test_ahora_son_CINCO(self):
        self.assertEqual([p["numero"] for p in self._pasos()], [1, 2, 3, 4, 5])

    def test_el_quinto_NO_se_ve_hasta_haber_diseñado(self):
        self.assertFalse(self._pasos()[4]["visible"])
        self.assertTrue(self._pasos(designed=True)[4]["visible"])

    def test_los_otros_cuatro_se_ven_siempre(self):
        for paso in self._pasos()[:4]:
            self.assertTrue(paso["visible"], paso["numero"])

    def test_el_paso_3_ya_NO_pide_los_siete_frentes(self):
        """Era lo que hacia creer que sin ellos no se puede empezar."""
        tercero = self._pasos()[2]
        self.assertEqual(tercero["titulo"], "Ficheros de referencia — para diseñar")
        self.assertNotIn("de 7", tercero["detalle"])

    def test_y_dice_que_HOY_no_hace_falta_ninguno(self):
        self.assertIn("ninguno", self._pasos()[2]["detalle"].lower())

    def test_el_paso_3_esta_HECHO_cuando_no_hace_falta_nada(self):
        """Un paso que se queda abierto para siempre se lee como algo que falta."""
        self.assertTrue(self._pasos()[2]["hecho"])

    def test_el_paso_5_lleva_el_contador_en_su_TITULO_y_no_en_una_nota(self):
        quinto = self._pasos(designed=True)[4]
        self.assertEqual(quinto["titulo"], "Refinamiento")
        self.assertIn("de 8 frentes cerrados", quinto["detalle"])

    def test_el_paso_4_sigue_siendo_DISEÑAR(self):
        self.assertEqual(self._pasos()[3]["titulo"], "Diseñar")


# ─────────────────── 5. lo que la disposicion NO puede dar a entender ───────────────────


class TestElCriterioDeAceptacion(unittest.TestCase):
    """Alguien que abra la app dentro de un año, sin memoria de estas conversaciones,
    tiene que poder contestar cuatro preguntas de un vistazo. Y no puede concluir una."""

    @classmethod
    def setUpClass(cls):
        cls.directorio = _directorio("mature.fa", "polya_db_mouse.tsv")
        cls.pasos = presentation.steps_rows(
            species="raton", sequence_loaded=True, directory=cls.directorio,
            designed=True,
        )
        cls.panel = presentation.refinement_panel("raton", directory=cls.directorio)

    def test_1_puedo_diseñar_ya(self):
        self.assertTrue(self.pasos[2]["hecho"])

    def test_2_que_tengo_cerrado(self):
        self.assertIn("de 8 frentes cerrados", self.panel["progreso"]["texto"])

    def test_3_que_me_falta_y_para_que(self):
        faltan = [f for f in self.panel["filas"] if f["bloquea"]]
        self.assertTrue(faltan)
        for fila in faltan:
            self.assertTrue(fila["que_desbloquea"])

    def test_4_que_pasa_si_no_lo_consigo(self):
        """La pregunta se le hace a lo que NO esta. A un fichero que ya esta en el
        deposito no se le hace, y ahi el campo vacio es NO_APLICA y no un hueco."""
        ausentes = [f for f in self.panel["filas"] if f["estado"] != "CERRADO"]
        self.assertTrue(ausentes)
        for fila in ausentes:
            self.assertTrue(fila["si_no_llega"], fila["nombre"])
        for fila in self.panel["filas"]:
            if fila["estado"] == "CERRADO":
                self.assertEqual(fila["si_no_llega"], "")

    def test_lo_que_NO_puede_concluirse_que_haya_que_reunirlo_todo_antes(self):
        """El paso 3 no puede nombrar ni un fichero del momento 2."""
        detalle = self.pasos[2]["detalle"]
        for nombre in ("mature.fa", "transcriptoma_3utr.fa", "refseq_rna.fa"):
            self.assertNotIn(nombre, detalle)


# ─────────────────────────── 6. la pagina no decide nada ───────────────────────────


class TestLaPaginaSoloPinta(unittest.TestCase):

    def test_el_paso_5_se_pinta_DESPUES_de_los_resultados(self):
        """Y «despues» se mide en el fuente: el panel tiene que quedar por debajo del
        boton y por debajo del bloque de descargas, no en cualquier sitio de la pagina."""
        panel = PAGINA.index("_panel_refinamiento(nombre_modelo)")
        # El ancla es el ENCABEZADO del paso del boton, no su titulo: el titulo es
        # texto que se reescribe —«Diseñar» paso a «Buscar candidatos»— y anclar una
        # invariante a un texto la rompe cada vez que alguien mejora una frase.
        boton = PAGINA.index("_cabecera_paso(3, step_plain(3))")
        descargas = PAGINA.index('st.subheader("Descargas")')
        self.assertGreater(panel, boton)
        self.assertGreater(panel, descargas)

    def test_la_pagina_no_calcula_el_estado_ni_el_orden_ni_el_color(self):
        comprobar_sin_logica(self, _bloque_del_panel())

    def test_el_porque_de_los_dos_momentos_LLEGA_A_LA_PANTALLA(self):
        """Una frase escrita y no emitida es el patron de siempre: sin ella, un paso 3
        vacio se lee como un paso que no hace nada."""
        self.assertIn("WHY_TWO_MOMENTS", PAGINA)

    def test_la_pagina_no_escribe_ninguno_de_los_estados_a_mano(self):
        # La lista se DERIVA de `REFINEMENT_STATES` en vez de transcribirse: un estado
        # nuevo queda cubierto sin que nadie se acuerde (principio nº 13).
        bloque = _bloque_del_panel()
        for entrada in presentation.REFINEMENT_STATES:
            self.assertNotIn(f'"{entrada["estado"]}"', bloque)


def _bloque_del_panel() -> str:
    """El cuerpo de `_panel_refinamiento` en la pagina."""
    inicio = PAGINA.index("def _panel_refinamiento(")
    resto = PAGINA[inicio:]
    fin = resto.index("\ndef ", 1)
    return resto[:fin]


if __name__ == "__main__":
    unittest.main()
