"""Lo que se MIDIÓ sobre los tres plásmidos. Regla 5: escrito antes de decidir nada.

Ninguno de los dos plásmidos de Addgene traía su andamio anotado, y eso NO se resuelve
buscándolo por secuencia contra una construida por nosotros (regla 1). Lo que sí se puede
hacer sin suponer nada es **plegar** lo que las anotaciones acotan, y comparar contra un
CONTROL POSITIVO: SGEP #111170, donde el andamio sí lo conocemos y que anota su
`miR-30a loop` con la misma etiqueta de 15 nt que #20670.

Aquí NO se declara ningún andamio. Se fija lo medido, para que la decisión se tome
mirándolo y para que un fichero cambiado lo diga.
"""

import re
import unittest
from pathlib import Path

from shmir_design.folding import VIENNA_AVAILABLE, dot_bracket


def bucles_terminales(estructura: str) -> int:
    """Cuántos BUCLES TERMINALES tiene. Una horquilla limpia tiene UNO.

    El primer discriminante que escribí contaba `)(` —tallos SECUENCIALES— y no vale:
    estas estructuras son ANIDADAS, así que ninguna de las cuatro tiene un solo `)(`.
    Pasó en el control positivo **por casualidad**, que es como pasan los peores. Lo que
    de verdad distingue una horquilla de un plegado cualquiera es cuántos bucles cierra.
    """
    pila, cuantos = [], 0
    for i, caracter in enumerate(estructura):
        if caracter == "(":
            pila.append(i)
        elif caracter == ")":
            abre = pila.pop()
            if set(estructura[abre + 1 : i]) <= {"."}:
                cuantos += 1
    return cuantos

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIA = RAIZ / "data" / "reference"


def cargar(nombre: str) -> str:
    """La secuencia del `.gb`, del fichero. Cadena vacía si no está: no se inventa."""
    ruta = REFERENCIA / nombre
    if not ruta.is_file():
        return ""
    origen = ruta.read_text(encoding="utf-8").split("ORIGIN", 1)[1].split("//")[0]
    limpio = origen.translate(str.maketrans("", "", "0123456789"))
    return "".join(re.findall(r"[acgtnACGTN]", limpio)).upper()


def ventana_centrada(loop_a: int, loop_b: int, largo: int = 71) -> tuple[int, int]:
    """La ventana de `largo` nt con el loop EN EL CENTRO. Se deriva, no se adivina.

    El prompt propuso «~112 a ~183» para el loop 154..168 de #20670, y con esas
    coordenadas el loop NO queda centrado: cae en 43..57 de 72. La ventana centrada es
    126..196, y la diferencia se mide abajo — 14 kcal/mol y una horquilla contra dos
    elementos. Por eso el rango se calcula.
    """
    brazo, resto = divmod(largo - (loop_b - loop_a + 1), 2)
    return loop_a - brazo, loop_b + brazo + resto


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: falta ViennaRNA")
class TestElCONTROLpositivo(unittest.TestCase):
    """SGEP, donde el andamio SÍ se conoce. Sin esto, los otros dos plegados no tienen
    contra qué compararse y un ΔG suelto no dice nada."""

    def test_centrar_el_loop_anotado_recupera_UNA_horquilla(self):
        sgep = cargar("addgene_111170.gb")
        self.assertTrue(sgep, "falta addgene_111170.gb")
        a, b = ventana_centrada(1801, 1815)
        self.assertEqual((a, b), (1773, 1843))
        estructura, dg = dot_bracket(sgep[a - 1 : b])
        emparejadas = sum(1 for c in estructura if c in "()")
        self.assertLess(dg, -30.0, f"ΔG={dg}")
        self.assertGreater(emparejadas / 71, 0.80, estructura)
        # UNA sola horquilla: la estructura no se parte en dos tallos independientes.
        self.assertEqual(bucles_terminales(estructura), 1, estructura)


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: falta ViennaRNA")
class TestElVeredictoDE20670(unittest.TestCase):
    """SÍ sale horquilla, y comparable al control. NO se declara andamio."""

    def setUp(self):
        self.seq = cargar("addgene_20670.gb")
        self.a, self.b = ventana_centrada(154, 168)

    def test_la_ventana_derivada_es_126_196(self):
        self.assertEqual((self.a, self.b), (126, 196))

    def test_las_bases_AMBIGUAS_caen_FUERA(self):
        """El fichero tiene 10 N desde la 710. Si cayeran dentro, el plegado no valdría
        y habría que decirlo en vez de dar un número."""
        primera_n = self.seq.find("N") + 1
        self.assertEqual(primera_n, 710)
        self.assertLess(self.b, primera_n)
        self.assertEqual(self.seq[self.a - 1 : self.b].count("N"), 0)

    def test_sale_una_horquilla_comparable_al_control(self):
        estructura, dg = dot_bracket(self.seq[self.a - 1 : self.b])
        emparejadas = sum(1 for c in estructura if c in "()")
        self.assertLess(dg, -30.0, f"ΔG={dg}")
        self.assertGreater(emparejadas / 71, 0.70, estructura)
        self.assertEqual(bucles_terminales(estructura), 1, estructura)

    def test_y_el_rango_del_prompt_sale_PEOR_de_medida(self):
        """No es una corrección de estilo: son 14 kcal/mol y dos elementos en vez de uno.
        Centrar el loop no era un detalle."""
        _, dg_centrada = dot_bracket(self.seq[self.a - 1 : self.b])
        estructura, dg_prompt = dot_bracket(self.seq[112 - 1 : 183])
        self.assertGreater(dg_prompt - dg_centrada, 10.0)
        self.assertEqual(bucles_terminales(estructura), 2, estructura)


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: falta ViennaRNA")
class TestElVeredictoDE78126(unittest.TestCase):
    """NO sale horquilla: el hueco sin anotar es un POLILINKER VACÍO, y se descarta con
    motivo medido en vez de por ausencia de etiqueta."""

    HUECO = (883, 1097)

    #: Dianas canonicas de seis pares. Es nomenclatura de uso corriente, no una
    #: secuencia diseñada por nosotros: se cuentan, no se construye nada con ellas.
    DIANAS = {
        "NheI": "GCTAGC", "HindIII": "AAGCTT", "KpnI": "GGTACC", "SacI": "GAGCTC",
        "BamHI": "GGATCC", "SpeI": "ACTAGT", "EcoRI": "GAATTC", "PstI": "CTGCAG",
        "EcoRV": "GATATC", "NotI": "GCGGCCGC", "XhoI": "CTCGAG", "XbaI": "TCTAGA",
        "ApaI": "GGGCCC", "PmeI": "GTTTAAAC", "AflII": "CTTAAG", "BstBI": "TTCGAA",
    }

    def setUp(self):
        self.seq = cargar("addgene_78126.gb")
        a, b = self.HUECO
        self.tramo = self.seq[a - 1 : b]

    def test_ninguna_ventana_de_71_llega_al_control(self):
        """Se barren TODAS las ventanas del tamaño del control, no una elegida a ojo."""
        mejor = min(
            dot_bracket(self.tramo[i : i + 71])[1]
            for i in range(len(self.tramo) - 71 + 1)
        )
        self.assertGreater(mejor, -30.0, f"la mejor da ΔG={mejor}")

    def test_la_mejor_SI_es_una_horquilla_pero_no_es_eso_lo_que_decide(self):
        """CORRECCIÓN sobre lo primero que escribí: la mejor ventana **sí** cierra un
        solo bucle, o sea que topológicamente es una horquilla. Y no significa nada:
        cualquier tramo rico en GC pliega algo. Lo que la separa del control positivo es
        la MAGNITUD —9 kcal/mol y 17 puntos de emparejamiento—, no la forma. Decir
        «ramificada» habría sido un diagnóstico equivocado, que cuesta más que ninguno.
        """
        estructura, dg = min(
            (dot_bracket(self.tramo[i : i + 71]) for i in range(len(self.tramo) - 71 + 1)),
            key=lambda par: par[1],
        )
        self.assertEqual(bucles_terminales(estructura), 1, estructura)
        emparejadas = sum(1 for c in estructura if c in "()") / 71
        self.assertLess(emparejadas, 0.70, "menos emparejada que el control")
        self.assertGreater(dg, -30.0)

    def test_la_DENSIDAD_de_dianas_lo_delata(self):
        """Lo que decide no es el ΔG solo: es que ahí hay una hilera de dianas de
        clonaje, que es lo que se ve en un polilinker VACÍO."""
        dentro = sum(len(re.findall(d, self.tramo)) for d in self.DIANAS.values())
        distintas = sum(1 for d in self.DIANAS.values() if re.search(d, self.tramo))
        a, b = self.HUECO
        resto = self.seq[: a - 1] + self.seq[b:]
        fuera = sum(len(re.findall(d, resto)) for d in self.DIANAS.values())
        self.assertGreaterEqual(distintas, 12, f"{distintas} dianas distintas")
        densidad_dentro = len(self.tramo) / dentro
        densidad_fuera = len(resto) / fuera
        self.assertGreater(densidad_fuera / densidad_dentro, 50)


class TestElCALCULO2yLoQueDECIDE(unittest.TestCase):
    """Las 284 ventanas, y la consecuencia que se sigue de ellas.

    El número no es un detalle de cobertura: **decide si miR-451 puede entrar en la
    matriz como un cuarto brazo del mismo experimento o si es otro experimento.**
    """

    def _informes(self):
        from dataclasses import replace

        from shmir_design.filters import FilterState
        from shmir_design.reference import REFERENCES, load_3utr
        from shmir_design.tiling import tile_utr

        informe = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))

        def sin_asimetria(ventana):
            evaluacion = ventana.evaluation
            return replace(
                ventana,
                evaluation=replace(
                    evaluacion,
                    filters=tuple(
                        replace(f, state=FilterState.NO_APLICA, reason=MOTIVO_451)
                        if f.name == "asimetria"
                        else f
                        for f in evaluacion.filters
                    ),
                ),
            )

        return informe, replace(
            informe, windows=tuple(sin_asimetria(w) for w in informe.windows)
        )

    def test_caen_284_ventanas_SOLO_por_la_asimetria(self):
        from shmir_design.selection import default_config, is_eligible

        hoy, otro = self._informes()
        cfg = default_config()
        n_hoy = sum(1 for w in hoy.windows if is_eligible(w, cfg))
        n_otro = sum(1 for w in otro.windows if is_eligible(w, cfg))
        self.assertEqual(n_hoy, 270)
        self.assertEqual(n_otro, 554)
        self.assertEqual(n_otro - n_hoy, 284)

    def test_y_los_SITIOS_bajan_aunque_las_ventanas_suban(self):
        """El aviso, medido: 86 → 40 mientras las ventanas van de 270 a 554. No se
        pierden sitios, se FUNDEN. El recuento de sitios mide fragmentación, no
        oportunidad, y no es comparable entre criterios."""
        from shmir_design.selection import default_config, eligible_choices, group_choices

        hoy, otro = self._informes()
        cfg = default_config()
        sitios_hoy = group_choices(eligible_choices(hoy, cfg))
        sitios_otro = group_choices(eligible_choices(otro, cfg))
        self.assertEqual(len(sitios_hoy), 86)
        self.assertEqual(len(sitios_otro), 40)
        medio_hoy = sum(len(s.choices) for s in sitios_hoy) / len(sitios_hoy)
        medio_otro = sum(len(s.choices) for s in sitios_otro) / len(sitios_otro)
        self.assertLess(medio_hoy, 4)
        self.assertGreater(medio_otro, 13)

    def test_la_asimetria_va_a_NO_APLICA_y_no_a_PASS(self):
        """No es que la superen: es que la pregunta no se les hace. Regla 3."""
        from shmir_design.filters import FilterState

        _, otro = self._informes()
        estados = {
            f.state for w in otro.windows for f in w.filters if f.name == "asimetria"
        }
        self.assertEqual(estados, {FilterState.NO_APLICA})


#: LA CONSECUENCIA, escrita donde vive el numero que la sostiene.
CONSECUENCIA_451 = (
    "Con 284 ventanas que caen HOY sólo por la asimetría, miR-451 no es el panel actual "
    "con otro andamio: es UN PANEL PROPIO. Si entra en la matriz, entra con sus "
    "candidatos y deja de ser un experimento controlado frente a los otros tres — que sí "
    "comparten criterio, porque en miR-E, miR-30 original y miR-155 hay dos hebras "
    "compitiendo por cargarse y la asimetría sigue significando lo mismo. Eso hay que "
    "decidirlo ANTES de sintetizar, no después."
)

#: Por que la asimetria no aplica en este andamio. Va aqui y no repetido en cada test.
MOTIVO_451 = (
    "miR-451: Ago2 carga el pre-miR entero y corta él mismo el brazo 3'. No hay dos "
    "hebras compitiendo, así que la pregunta de la asimetría no se le hace."
)


class TestLaCONSECUENCIAestaESCRITA(unittest.TestCase):

    def test_dice_que_es_un_panel_PROPIO(self):
        self.assertIn("PANEL PROPIO", CONSECUENCIA_451)
        self.assertIn("284", CONSECUENCIA_451)

    def test_y_dice_CUANDO_hay_que_decidirlo(self):
        self.assertIn("ANTES de sintetizar", CONSECUENCIA_451)
