"""Retirar un candidato del panel es una DECISIÓN, y las decisiones dejan rastro.

Regla 5: escritos antes.

**El caso (2026-09-07)**: `3utr:10` sale del panel por el frente de EMPALME —introduce
crípticos que sus hermanas no tienen— y es el PRIMER candidato que ese frente quita. Si
se quitara a mano, la única huella dentro de un año sería una piscina más pequeña: la
forma exacta que tiene un candidato de desaparecer sin que nadie lo vea.

**Tres cosas y ninguna sobra**:

1. la retirada se DECLARA en `data/candidatos_retirados.toml`, con motivo, frente y
   fecha, y se aplica **por el md5 del 3'UTR** — no por el nombre del gen. Sobre otra
   secuencia no retira nada: retirar «3utr:10» de otro gen sería quitar una ventana que
   nadie ha mirado, el agujero de `rmsk_mouse.out` conectado por su rol;
2. **NO es silenciosa**: sale en las notas de la selección con su motivo;
3. una entrada que no case con nada sobre una secuencia que SÍ es la suya **aborta**:
   una retirada que no retira es una decisión perdida, y darla por aplicada es peor que
   no tenerla.

**Y la cuota de inmunes baja de cuatro a TRES POR GEOMETRÍA, no por criterio**: los 16
sitios inmunes se apelotonan entre `3utr:10` y `3utr:200`, así que con `60`, `143` y
`200` puestos ninguno de los trece restantes cabe a 50 nt. No se renuncia a la reserva —
no cabe. Y el espaciado no se baja para que quepa uno: compra independencia entre
apuestas, no número de apuestas.
"""

import unittest

from shmir_design import retirados, selection
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import (
    REFERENCES, fixture_available, load_3utr, load_reference, sequence_md5,
)
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


class TestLaTablaSE_DECLARA(unittest.TestCase):

    def test_cada_entrada_trae_motivo_frente_fecha_y_quien(self):
        entradas = retirados.declarados()
        self.assertTrue(entradas)
        for entrada in entradas:
            for campo in ("md5_utr3", "posicion", "motivo", "frente", "fecha", "quien"):
                self.assertTrue(entrada[campo], f"{campo}: {entrada}")

    def test_el_frente_declarado_EXISTE(self):
        """Un frente inventado dejaría la retirada sin poder cruzarse con nada."""
        from shmir_design.presentation import (
            FRONTS_WITHOUT_COLUMN, STORE_FOR_FRONT,
        )

        # Los frentes que tienen ALMACÉN de corridas, más los que se cierran por par y
        # no tienen columna por candidato. Un frente inventado en la tabla no podría
        # cruzarse con nada: la retirada diría caer por algo que no existe.
        conocidos = set(STORE_FOR_FRONT) | set(FRONTS_WITHOUT_COLUMN)
        for entrada in retirados.declarados():
            self.assertIn(entrada["frente"], conocidos, entrada)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestSobreLaSECUENCIA_QUE_ES(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        cls.anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.informe = tile_utr(secuencia, anatomy=cls.anatomia)
        cls.seleccion = selection.select_from_report(
            cls.informe, selection.default_config()
        )
        cls.panel = sorted(
            cls.informe.utr3_of(c.start) for c in cls.seleccion.selection.chosen
        )

    def test_la_tabla_habla_de_ESTE_3utr(self):
        self.assertEqual(
            retirados.declarados()[0]["md5_utr3"], sequence_md5(load_3utr(RATON))
        )

    def test_3utr10_YA_NO_esta_en_el_panel(self):
        self.assertNotIn(10, self.panel)

    def test_y_el_panel_es_el_DECIDIDO(self):
        """Medido: `3utr:359` entra DERIVADO, sin pinchar ninguna plaza a mano."""
        self.assertEqual(
            self.panel,
            [60, 143, 200, 359, 449, 553, 652, 735, 819, 1018, 1071],
        )

    def test_quedan_TRES_inmunes_y_son_60_143_y_200(self):
        corte = selection.derive_immune_cut(self.informe)
        inmunes = [
            self.informe.utr3_of(c.start)
            for c in self.seleccion.selection.chosen if c.start < corte
        ]
        self.assertEqual(sorted(inmunes), [60, 143, 200])

    def test_la_retirada_SE_DICE_en_las_DECISIONES(self):
        """Un panel que ya no lleva a alguien tiene que decir por qué."""
        notas = "\n".join(self.seleccion.selection.decisions)
        self.assertIn("3utr:10", notas)
        self.assertIn("empalme_sitios", notas)
        self.assertIn("2026-09-07", notas)
        # Y el motivo entero, no un resumen: es lo que se lee dentro de un año.
        self.assertIn("crípticos", notas)

    def test_y_NO_va_entre_los_AVISOS(self):
        """Una decisión tomada no es un aviso, y mezclarlas apaga los avisos.

        Sale en todas las corridas de esta secuencia: en la lista de avisos dejaría el
        rojo puesto para siempre, y a partir de ahí el aviso del espaciado —«se pedían
        50 candidatos y salen 13», que sí es accionable— no se distinguiría del fondo.
        Lo cazó el control adversario de aquel aviso, que lo exige VACÍO.
        """
        from shmir_design import presentation

        self.assertEqual(self.seleccion.selection.notes, ())
        filas = presentation.selection_notes(self.seleccion)
        self.assertEqual([f for f in filas if f["avisa"]], [])
        self.assertTrue([f for f in filas if not f["avisa"]])

    def test_un_RETIRADO_no_se_vuelve_a_proponer_para_una_plaza(self):
        """Sigue en la piscina, y aun así no puede salir como «el siguiente que cabe».

        `3utr:10` es un sitio elegible —la retirada sale de la SELECCIÓN, no de los
        elegibles, que es lo que le deja conservar sus veredictos y su sitio en la
        tabla—, así que la cobertura por tercios lo ofrecería como el mejor libre del
        proximal. La app estaría recomendando ocupar la plaza con exactamente el
        candidato que alguien retiró, y el motivo escrito no se vería por ninguna parte.
        """
        cobertura = selection.tercio_coverage(self.informe, self.seleccion)
        proximal = next(c for c in cobertura if c.tercio == "proximal")
        self.assertIn(10, proximal.retired)
        self.assertNotIn(10, [s.start for s in proximal.next_free])
        self.assertNotIn(10, [s.start for s in proximal.next_free_of_reference])
        # Y se NOMBRA: un hueco que se quita en silencio no se distingue de uno que
        # nunca estuvo.
        self.assertIn("3utr:10", "\n".join(proximal.describe()))

    def test_control_adversario_SI_hay_otros_libres_en_ese_tramo(self):
        """Sin esto, «no propone el retirado» y «no propone nada» dan lo mismo."""
        cobertura = selection.tercio_coverage(self.informe, self.seleccion)
        proximal = next(c for c in cobertura if c.tercio == "proximal")
        self.assertTrue(proximal.next_free_of_reference)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestSobreOTRA_SECUENCIA_NO_RETIRA_NADA(unittest.TestCase):
    """El control adversario: la tabla se aplica por md5, no por el nombre del gen."""

    def test_con_otro_3utr_la_entrada_NO_se_aplica(self):
        utr3 = load_3utr(RATON)
        # Otra secuencia: la misma con una base cambiada. NO se fabrica ninguna
        # secuencia biológica nueva — se altera una para comprobar que el md5 manda.
        otra = ("T" if utr3[0] != "T" else "A") + utr3[1:]
        aplicables = retirados.para(sequence_md5(otra))
        self.assertEqual(aplicables, ())

    def test_una_retirada_que_NO_RETIRA_NADA_aborta(self):
        """Sobre su propia secuencia, una posición que no es elegible es una decisión
        perdida: se aborta en vez de darla por aplicada."""
        entrada = dict(retirados.declarados()[0], posicion=1241)
        with self.assertRaises(ShmirDesignError) as cm:
            retirados.aplicar(
                [1, 2, 3], entradas=(entrada,), offset=0, md5_utr3=entrada["md5_utr3"],
            )
        self.assertIn("1241", str(cm.exception))


class TestLaCuotaBajaPOR_GEOMETRIA(unittest.TestCase):

    def test_la_constante_lo_dice_con_esas_palabras(self):
        self.assertEqual(selection.DEFAULT_IMMUNE_QUOTA, 3)
        texto = selection.WHY_THE_IMMUNE_QUOTA_IS_THREE
        self.assertIn("geometría", texto.lower())
        self.assertIn("16", texto)
        # Y lo que NO se hace, porque es la salida fácil y está decidido que no.
        self.assertIn("espaciado", texto.lower())
        self.assertIn("no se baja", texto.lower())
        # Y NIEGA expresamente la lectura que hay que impedir: que se renunció a la
        # reserva. Sin la negación escrita, «cuota de tres» se lee así dentro de un año.
        self.assertIn("renunc", texto.lower())


if __name__ == "__main__":
    unittest.main()
