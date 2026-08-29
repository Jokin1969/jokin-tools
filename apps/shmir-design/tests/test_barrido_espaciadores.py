"""Barrido de longitudes de espaciador: la CURVA, no un óptimo.

Los dos lados NO son simétricos y el barrido lo respeta:

  · el de 5' separa del DONANTE — recorte agresivo;
  · el de 3' separa del PUNTO DE RAMIFICACIÓN y del TRACTO, que son los elementos
    frágiles — recorte conservador.

Y el suelo NO ES UN NÚMERO: es la accesibilidad. Un espaciador de 8 nt en 5' vale si el
donante sigue desapareado; uno de 30 en 3' no vale si el punto no queda libre. Por eso lo
que se emite es la curva entera —cada longitud con la accesibilidad de los tres elementos
y el donante→punto resultante— y no un par elegido: el compromiso se ve, no se resume.

El CERO se prueba a propósito. Si el plegado aguanta sin espaciador, el argumento para
tenerlo desaparece, y eso hay que poder verlo en la tabla en vez de darlo por imposible.
"""

import unittest

from shmir_design import barrido
from shmir_design.errors import ShmirDesignError


class TestLaFormaDeLaCURVA(unittest.TestCase):
    """Sobre datos sintéticos rápidos: la forma, no los valores."""

    def _curva(self, **extra):
        return barrido.sweep_side(
            "mvm_actual", side="5", lengths=(0, 4, 8), other=45,
            module="A" * 149, medir=_medida_falsa, **extra,
        )

    def test_una_fila_por_longitud_probada(self):
        curva = self._curva()
        self.assertEqual([f.length for f in curva.points], [0, 4, 8])

    def test_cada_fila_trae_LOS_TRES_elementos(self):
        for punto in self._curva().points:
            for elemento in ("donante", "punto_de_ramificacion", "tracto_polipirimidinas"):
                self.assertIn(elemento, punto.unpaired)

    def test_y_el_donante_punto_resultante(self):
        for punto in self._curva().points:
            self.assertIsInstance(punto.donor_to_branch, int)

    def test_el_CERO_se_prueba(self):
        self.assertIn(0, [f.length for f in self._curva().points])

    def test_el_lado_se_declara_y_dice_QUE_separa(self):
        curva = self._curva()
        self.assertEqual(curva.side, "5")
        self.assertIn("DONANTE", curva.what_it_separates)

    def test_el_de_3_separa_OTRA_cosa(self):
        curva = barrido.sweep_side(
            "mvm_actual", side="3", lengths=(0, 20), other=20,
            module="A" * 149, medir=_medida_falsa,
        )
        self.assertIn("RAMIFICACIÓN", curva.what_it_separates)
        self.assertIn("TRACTO", curva.what_it_separates)


class TestLoADMISIBLE_NO_SE_COLAPSA(unittest.TestCase):

    def test_el_criterio_es_RELATIVO_al_punto_de_partida(self):
        # No se inventa un umbral absoluto. La referencia es 20/45, que es lo que hay
        # hoy: admisible = los tres elementos NO peor que ahí. Un número absoluto sacado
        # de la nada es exactamente lo que pasó con G4.
        self.assertIn("20/45", barrido.ADMISSIBILITY_RULE)
        self.assertIn("relativ", barrido.ADMISSIBILITY_RULE.lower())

    def test_si_varios_EMPATAN_salen_todos(self):
        curva = barrido.sweep_side(
            "mvm_actual", side="5", lengths=(0, 4, 8), other=45,
            module="A" * 149, medir=_medida_constante,
        )
        # Con la misma medida en las tres, las tres son admisibles y no se elige una.
        self.assertEqual([p.length for p in curva.admissible], [0, 4, 8])

    def test_y_NO_hay_ningun_campo_que_diga_el_optimo(self):
        curva = self._cualquiera()
        self.assertFalse(hasattr(curva, "best"))
        self.assertFalse(hasattr(curva, "optimo"))

    def _cualquiera(self):
        return barrido.sweep_side(
            "mvm_actual", side="5", lengths=(0,), other=45,
            module="A" * 149, medir=_medida_falsa,
        )


class TestLoQueABORTA(unittest.TestCase):

    def test_un_lado_que_no_es_5_ni_3(self):
        with self.assertRaises(ShmirDesignError):
            barrido.sweep_side(
                "mvm_actual", side="7", lengths=(0,), other=45,
                module="A" * 149, medir=_medida_falsa,
            )

    def test_una_longitud_fuera_del_rango_declarado(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            barrido.sweep_side(
                "mvm_actual", side="5", lengths=(0, 100), other=45,
                module="A" * 149, medir=_medida_falsa,
            )
        self.assertIn("45", str(ctx.exception))

    def test_y_una_longitud_NEGATIVA(self):
        with self.assertRaises(ShmirDesignError):
            barrido.sweep_side(
                "mvm_actual", side="5", lengths=(-1,), other=45,
                module="A" * 149, medir=_medida_falsa,
            )


def _medida_falsa(intron, module, spacer5, spacer3):
    """Medida determinista y barata: la accesibilidad crece con el espaciador."""
    largo = len(spacer5) + len(spacer3)
    return {
        "donante": min(1.0, 0.5 + largo / 200),
        "punto_de_ramificacion": min(1.0, 0.3 + largo / 200),
        "tracto_polipirimidinas": min(1.0, 0.4 + largo / 200),
    }


def _medida_constante(intron, module, spacer5, spacer3):
    return {
        "donante": 0.9,
        "punto_de_ramificacion": 0.9,
        "tracto_polipirimidinas": 0.9,
    }


if __name__ == "__main__":
    unittest.main()


class TestElRESULTADO_NEGATIVO_se_DICE(unittest.TestCase):
    """Si la longitud no se ve por encima del ruido, la curva lo dice y no disimula."""

    def _curva(self, medida):
        return barrido.sweep_side(
            "mvm_actual", side="5", lengths=(0, 20, 45), other=45,
            module="A" * 149, medir=medida, replicas=3,
        )

    def test_con_puro_RUIDO_no_es_concluyente(self):
        curva = self._curva(_ruido)
        self.assertFalse(curva.conclusive)
        texto = "\n".join(curva.describe())
        self.assertIn("NO CONCLUYENTE", texto)
        self.assertIn("ARTEFACTO", texto)

    def test_y_dice_que_lo_que_mueve_es_la_SECUENCIA(self):
        texto = "\n".join(self._curva(_ruido).describe())
        self.assertIn("SECUENCIA del espaciador, no su longitud", texto)

    def test_con_una_señal_de_verdad_SI_es_concluyente(self):
        curva = self._curva(_con_señal)
        self.assertTrue(curva.conclusive)
        self.assertNotIn("NO CONCLUYENTE", "\n".join(curva.describe()))

    def test_el_veredicto_va_ELEMENTO_a_ELEMENTO(self):
        curva = self._curva(_con_señal)
        self.assertEqual(set(curva.discriminates), set(barrido.FRAGILE))


_LLAMADAS = {"n": 0}


def _ruido(intron, module, spacer5, spacer3):
    """Dispersión grande dentro de cada longitud y ninguna tendencia entre ellas."""
    _LLAMADAS["n"] += 1
    valor = 0.2 + 0.6 * ((_LLAMADAS["n"] * 7) % 5) / 4
    return dict.fromkeys(barrido.FRAGILE, valor)


def _con_señal(intron, module, spacer5, spacer3):
    """Sin dispersión y con tendencia clara: la longitud sí se ve."""
    return dict.fromkeys(barrido.FRAGILE, min(1.0, 0.1 + len(spacer5) / 50))
