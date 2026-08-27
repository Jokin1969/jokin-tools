"""Dónde puede ir el módulo DENTRO del intrón, con las dos restricciones declaradas.

El sitio de inserción no es libre: el módulo tiene que caer entre el donante y el tracto
de polipirimidinas, y sin invadir el punto de ramificación. Son las DOS restricciones
que se declararon, y son las únicas que hay aquí: no se añade ningún mínimo de distancia
—«el punto de ramificación tiene que estar a más de N nt del aceptor»— porque nadie lo ha
autorizado. Es la lección de G4: un criterio que aparece sin haber sido discutido acaba
emitiendo veredictos que nadie pidió. Aquí se emiten DISTANCIAS, que son un hecho, y la
decisión se toma mirándolas.

Los datos reales son el MVM de 82 nt, que es el intrón que SÍ tenemos: se ensambla de
piezas versionadas y nadie lo teclea. Con él se comprueba el caso apretado; el quimérico
de 133 pb entrará por la misma función en cuanto esté el fichero.
"""

import unittest

from shmir_design.errors import ShmirDesignError
from shmir_design.introns import INTRONS, insertion_window, locate_elements

MODULO = 149  # nt del módulo NheI-SacI


class TestSobreElMVMDeVerdad(unittest.TestCase):

    def setUp(self):
        self.secuencia = INTRONS["mvm_actual"].empty_sequence
        self.elementos = locate_elements(self.secuencia, name="mvm_actual")
        self.ventana = insertion_window(self.elementos, module_length=MODULO)

    def test_el_MVM_mide_82_y_sus_elementos_son_los_esperados(self):
        # Ancla: si esto cambia, todo lo de abajo habla de otro intrón.
        self.assertEqual(len(self.secuencia), 82)
        self.assertEqual(self.elementos.donor.end, 2)
        self.assertEqual(self.elementos.ppt.start, 72)
        self.assertEqual(self.elementos.acceptor.start, 81)

    def test_los_tramos_empiezan_TRAS_el_donante_y_acaban_ANTES_del_tracto(self):
        primero = self.ventana.ranges[0]
        ultimo = self.ventana.ranges[-1]
        self.assertEqual(primero[0], self.elementos.donor.end + 1)
        self.assertEqual(ultimo[1], self.elementos.ppt.start - 1)

    def test_el_punto_de_ramificacion_PARTE_la_ventana_en_dos(self):
        # 43-47 es el candidato del MVM. Un tramo antes y otro después.
        self.assertEqual(len(self.ventana.ranges), 2)
        self.assertEqual(self.ventana.ranges, ((3, 42), (48, 71)))

    def test_ninguna_opcion_cae_DENTRO_de_un_candidato(self):
        prohibidas = {
            p
            for c in self.elementos.branch_candidates
            for p in range(c.start, c.end + 1)
        }
        for opcion in self.ventana.options:
            with self.subTest(after=opcion.after):
                self.assertNotIn(opcion.after, prohibidas)

    def test_cada_opcion_trae_su_distancia_a_CADA_elemento(self):
        opcion = self.ventana.options[0]
        self.assertEqual(opcion.after, 3)
        # Insertar tras la posición 3: quedan 3-2 = 1 nt entre el donante y el módulo.
        self.assertEqual(opcion.to_donor, 1)
        # Y del módulo al tracto, las posiciones 4..71 = 68 nt.
        self.assertEqual(opcion.to_ppt, self.elementos.ppt.start - 1 - 3)
        self.assertEqual(opcion.to_acceptor, self.elementos.acceptor.start - 1 - 3)

    def test_la_distancia_al_punto_de_ramificacion_va_POR_CANDIDATO_y_con_lado(self):
        # Emitir «la» distancia al punto de ramificación cuando hay varios candidatos
        # sería elegir uno. Va una por candidato, y con el lado, porque insertar aguas
        # arriba y aguas abajo del punto no es lo mismo.
        opcion = self.ventana.options[0]
        self.assertEqual(len(opcion.to_branch), len(self.elementos.branch_candidates))
        for distancia in opcion.to_branch:
            self.assertIn(distancia.side, ("aguas arriba", "aguas abajo"))
            self.assertGreaterEqual(distancia.nt, 0)

    def test_el_MODULO_no_alarga_el_hueco_en_el_que_CAE__lo_parte(self):
        # La distinción que este test existe para fijar, porque su primera versión la
        # tenía mal y daba un número plausible: insertar tras la posición 3 deja el
        # módulo entre 3 y 4, así que del módulo al candidato (43) siguen habiendo las
        # posiciones 4..42 = 39 nt. Ni una más. El módulo no se pega al lado del hueco.
        antes = next(o for o in self.ventana.options if o.after == 3)
        candidato = self.elementos.branch_candidates[0]
        self.assertEqual(antes.to_branch[0].nt, candidato.start - 3 - 1)

    def test_lo_que_SI_alarga_son_las_separaciones_que_lo_CRUZAN(self):
        # Donante→punto de ramificación en el intrón vacío son las posiciones 3..42,
        # 40 nt. Con el módulo intercalado en medio, 40 + 149.
        antes = next(o for o in self.ventana.options if o.after == 3)
        candidato = self.elementos.branch_candidates[0]
        vacio = candidato.start - self.elementos.donor.end - 1
        self.assertEqual(vacio, 40)
        self.assertEqual(antes.to_branch[0].donor_to_branch, vacio + MODULO)
        # Y la de abajo NO cambia: el módulo no está en medio.
        self.assertEqual(
            antes.to_branch[0].branch_to_acceptor,
            self.elementos.acceptor.start - candidato.end - 1,
        )

    def test_insertar_DESPUES_alarga_LA_OTRA_separacion(self):
        despues = next(o for o in self.ventana.options if o.after == 60)
        candidato = self.elementos.branch_candidates[0]
        self.assertEqual(despues.to_branch[0].side, "aguas abajo")
        # Ahora el módulo cruza punto→aceptor, y donante→punto se queda como estaba.
        self.assertEqual(
            despues.to_branch[0].donor_to_branch,
            candidato.start - self.elementos.donor.end - 1,
        )
        self.assertEqual(
            despues.to_branch[0].branch_to_acceptor,
            self.elementos.acceptor.start - candidato.end - 1 + MODULO,
        )

    def test_el_resumen_dice_los_tramos_y_NO_elige(self):
        texto = "\n".join(self.ventana.describe())
        self.assertIn("3-42", texto)
        self.assertIn("48-71", texto)
        self.assertIn("no se elige", texto.lower())


class TestLoQueABORTA(unittest.TestCase):

    def test_un_modulo_de_longitud_cero_o_negativa_aborta(self):
        elementos = locate_elements(
            INTRONS["mvm_actual"].empty_sequence, name="mvm_actual"
        )
        for largo in (0, -1):
            with self.subTest(largo=largo):
                with self.assertRaises(ShmirDesignError):
                    insertion_window(elementos, module_length=largo)

    def test_si_NO_queda_ni_una_posicion_se_dice_con_los_numeros(self):
        # Un intrón donde el tracto empieza justo tras el donante no admite inserción.
        # No se devuelve una lista vacía sin más: se dice por qué, con las posiciones.
        from shmir_design.introns import IntronElements, SpliceElement, ElementOrigin

        apretado = IntronElements(
            donor=SpliceElement(
                name="donante", start=1, end=2, sequence="GT",
                origin=ElementOrigin.DERIVADO,
            ),
            ppt=SpliceElement(
                name="tracto_polipirimidinas", start=3, end=5, sequence="CTT",
                origin=ElementOrigin.DERIVADO,
            ),
            acceptor=SpliceElement(
                name="aceptor", start=6, end=7, sequence="AG",
                origin=ElementOrigin.DERIVADO,
            ),
            branch_point=None,
            branch_candidates=(),
            length=7,
        )
        with self.assertRaises(ShmirDesignError) as ctx:
            insertion_window(apretado, module_length=MODULO)
        self.assertIn("donante", str(ctx.exception))
        self.assertIn("tracto", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
