"""La calibración del motivo del punto de ramificación. ES la justificación.

No hay literatura citada detrás de ninguno de los motivos que se barajaron, así que
elegir «el implementado» o «el que suena mejor» habría sido una preferencia entre dos
cadenas que nadie puede citar. El criterio es otro y es comprobable: **que recupere los
casos conocidos**, y que siga siendo discriminante.

`CTGAC` es el punto de ramificación canónico de mamífero y está en el intrón quimérico.
Un motivo que lo pierde está mal calibrado, por definición — no importa qué otra cosa
acierte. Lo conservado de verdad es la A de ramificación con una pirimidina detrás; la
posición 2 varía, y exigir purina ahí (que es lo que hace `YURAY`) descarta el ejemplo
de manual.

EL ANCLA ES LA A DE RAMIFICACIÓN, no el inicio del motivo. Sin eso los motivos no son
comparables: la A está en la posición 3 de `YURAY`, en la 4 de `YTNAY` y en la 6 de
`YNYURAY`, así que una ventana sobre el inicio del motivo mide una cosa distinta en cada
uno. Es el mismo fallo de marco que el mapa del 3'UTR, un nivel más abajo.

Este fichero corre la prueba entera cada vez. Si alguien cambia el motivo, aquí se ve
qué gana y qué pierde.
"""

import unittest

from shmir_design.introns import BRANCH_WINDOW, INTRONS, locate_elements

_Y, _R = frozenset("CT"), frozenset("AG")


def _yuray(m):
    return m[0] in _Y and m[1] in _R and m[2] == "A" and m[4] in _Y


def _ytnay(m):
    return m[0] in _Y and m[1] == "T" and m[3] == "A" and m[4] in _Y


def _ynyuray(m):
    return (m[0] in _Y and m[2] in _Y and m[3] == "T" and m[4] in _R
            and m[5] == "A" and m[6] in _Y)


def _minimo(m):
    return m[0] == "A" and m[1] in _Y


#: (nombre, longitud, índice 0-based de la A de ramificación, predicado)
MOTIVOS = (
    ("YURAY", 5, 2, _yuray),
    ("YTNAY", 5, 3, _ytnay),
    ("YNYURAY", 7, 5, _ynyuray),
    ("A+pirimidina", 2, 0, _minimo),
)

#: Cuántos candidatos son «media docena»: a partir de aquí el motivo ya no discrimina y
#: emitirlos todos es lo mismo que no emitir ninguno.
TOPE_DISCRIMINANTE = 4


def _candidatos(sequence, largo, indice_a, casa, ventana=None):
    """Todos los candidatos, anclados en la A de ramificación."""
    lo, hi = ventana or BRANCH_WINDOW
    n = len(sequence)
    a_aceptor = n - 1
    salida = []
    for inicio in range(1, n - largo + 2):
        motivo = sequence[inicio - 1:inicio - 1 + largo]
        if len(motivo) < largo or not casa(motivo):
            continue
        pos_a = inicio + indice_a
        distancia = a_aceptor - pos_a
        if lo <= distancia <= hi:
            salida.append((pos_a, motivo, distancia))
    return salida


def _secuencias():
    return {
        "mvm_actual": INTRONS["mvm_actual"].empty_sequence,
        "intron_quimerico": INTRONS["intron_quimerico"].require_sequence(),
    }


class TestLaPruebaQueDECIDE(unittest.TestCase):

    def setUp(self):
        self.secuencias = _secuencias()
        self.resultado = {
            nombre: {
                intron: _candidatos(s, largo, ia, casa)
                for intron, s in self.secuencias.items()
            }
            for nombre, largo, ia, casa in MOTIVOS
        }

    def test_YURAY_PIERDE_el_caso_conocido(self):
        # El motivo que estaba implementado. Cero candidatos en el quimérico: descarta
        # `CTGAC` porque su segunda base es T, una pirimidina.
        self.assertEqual(self.resultado["YURAY"]["intron_quimerico"], [])

    def test_YNYURAY_recupera_CTGAC_pero_PIERDE_el_MVM(self):
        quimerico = self.resultado["YNYURAY"]["intron_quimerico"]
        self.assertEqual(len(quimerico), 1)
        self.assertIn("CTGAC", quimerico[0][1])
        self.assertEqual(self.resultado["YNYURAY"]["mvm_actual"], [])

    def test_el_MINIMO_recupera_todo_y_NO_DISCRIMINA(self):
        minimo = self.resultado["A+pirimidina"]
        self.assertGreater(len(minimo["intron_quimerico"]), TOPE_DISCRIMINANTE)

    def test_YTNAY_recupera_LOS_DOS_y_sigue_discriminando(self):
        elegido = self.resultado["YTNAY"]
        self.assertEqual(len(elegido["mvm_actual"]), 1)
        self.assertEqual(len(elegido["intron_quimerico"]), 2)
        self.assertLessEqual(len(elegido["intron_quimerico"]), TOPE_DISCRIMINANTE)
        self.assertIn("CTGAC", [m for _, m, _ in elegido["intron_quimerico"]])

    def test_y_es_EL_MAS_LAXO_de_los_que_valen(self):
        # «Más laxo» = más candidatos. Entre los que recuperan los dos intrones y siguen
        # discriminando, se elige el que más encuentra: perder un punto real cuesta más
        # que emitir uno de más, porque los de más SE VEN y se descartan mirándolos.
        validos = {
            nombre: r for nombre, r in self.resultado.items()
            if all(r[i] for i in self.secuencias)
            and max(len(r[i]) for i in self.secuencias) <= TOPE_DISCRIMINANTE
        }
        self.assertEqual(set(validos), {"YTNAY"})

    def test_TRES_de_los_cuatro_coinciden_en_la_A_del_quimerico(self):
        # La convergencia que da confianza en el 107: no es que un motivo lo diga, es
        # que los tres que lo ven lo ponen en el mismo sitio.
        posiciones = {
            nombre: {a for a, _, _ in r["intron_quimerico"]}
            for nombre, r in self.resultado.items()
        }
        for nombre in ("YTNAY", "YNYURAY", "A+pirimidina"):
            self.assertIn(107, posiciones[nombre], nombre)


class TestLoQueQUEDOImplementado(unittest.TestCase):

    def test_el_codigo_usa_YTNAY_en_la_ventana_18_40(self):
        self.assertEqual(BRANCH_WINDOW, (18, 40))

    def test_el_MVM_da_su_candidato(self):
        elementos = locate_elements(
            INTRONS["mvm_actual"].empty_sequence, name="mvm_actual"
        )
        self.assertEqual(len(elementos.branch_candidates), 1)
        self.assertEqual(elementos.branch_candidates[0].sequence, "TTAAT")

    def test_el_quimerico_da_LOS_DOS_y_no_se_elige(self):
        elementos = locate_elements(
            INTRONS["intron_quimerico"].require_sequence(), name="intron_quimerico"
        )
        self.assertEqual(
            {c.sequence for c in elementos.branch_candidates}, {"CTGAC", "CTTAC"}
        )
        self.assertTrue(elementos.branch_ambiguous)

    def test_cada_candidato_trae_la_A_y_su_distancia_al_aceptor(self):
        elementos = locate_elements(
            INTRONS["intron_quimerico"].require_sequence(), name="intron_quimerico"
        )
        for candidato in elementos.branch_candidates:
            with self.subTest(candidato.sequence):
                self.assertTrue(1 <= candidato.branch_a <= elementos.length)
                self.assertEqual(
                    candidato.to_acceptor, elementos.acceptor.start - candidato.branch_a
                )

    def test_punto_ACEPTOR_sale_como_INTERVALO_cuando_hay_varios(self):
        # Lo pedido: con dos candidatos no hay «el» número, hay un rango.
        elementos = locate_elements(
            INTRONS["intron_quimerico"].require_sequence(), name="intron_quimerico"
        )
        self.assertEqual(elementos.branch_to_acceptor_range, (25, 29))

    def test_y_como_intervalo_de_un_punto_cuando_hay_uno(self):
        elementos = locate_elements(
            INTRONS["mvm_actual"].empty_sequence, name="mvm_actual"
        )
        self.assertEqual(elementos.branch_to_acceptor_range, (36, 36))


if __name__ == "__main__":
    unittest.main()
