"""Un aborto por fichero repetido NO adivina por que se ha repetido.

Regla 5: escrito antes.

**Reportado el 2026-09-07**, con el mensaje delante por segunda vez y en estas palabras:
*«sigo viendo esto»*. El aborto decia, entre lo que hay que hacer:

    «Casi seguro has cogido el resultado viejo de SpliceAI: comprueba el fichero, o
    vuelve a correrlo y sube ESE.»

**Y eso no se ha comprobado. Peor: esta DESCARTADO por el guardia que el fichero acaba
de pasar.** `spliceai.parse_result` valida CADA fila contra las construcciones de ESTA
corrida —por nombre y por md5, con el nombre heredado admitido solo si el md5 lo
confirma— y rechaza el fichero entero si alguna nombra una construccion que este panel no
genera. Un resultado del panel de DIEZ lleva filas de `3utr:10`, que hoy esta retirado, y
por tanto **no puede llegar al guardia del duplicado**: aborta antes, y con otro mensaje.

O sea que cuando este aborto salta, lo unico que puede ser el fichero es un resultado de
ESTE panel — justo lo contrario de lo que el mensaje mandaba a buscar. Se mando dos veces
a mirar el sitio equivocado.

Es el principio nº 3 otra vez —**un diagnostico equivocado cuesta mas que ninguno**— y la
misma forma que «comprueba que Streamlit esta instalado» pegado a un conflicto de
configuracion, y que el «Alu 0 %» obtenido sin buscar Alu. La regla del proyecto ya
estaba escrita en `process.diagnose`: **una pista solo cuando la propia evidencia la
nombra**.

Lo que el aborto SI sabe, y con eso basta: que el md5 coincide, o sea que es el mismo
fichero; y que ha pasado la validacion contra las construcciones de esta corrida, o sea
que NO es de otro panel. Las dos son comprobaciones hechas, no conjeturas.
"""

import unittest

from shmir_design import blast_store, identidad, splice_store
from shmir_design.reference import REFERENCES, fixture_available

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: El resultado VERSIONADO del panel de diez. Aqui es la ENTRADA de la comprobacion, no
#: su valor esperado: lo que se mide es que hoy no entra.
MEDIDO = "data/medido/spliceai_dos_intrones_2026-09-05.tsv"

#: Adverbios de conjetura. Un aborto que los usa esta ADIVINANDO, y quien lo lee no tiene
#: forma de saber que lo hace: la frase tiene la misma forma que un hecho medido.
CONJETURA = ("casi seguro", "probablemente", "seguramente", "lo mas probable",
             "lo más probable", "suele ser", "sera que", "será que", "quiza", "quizá")


def _mensaje(**extra):
    # El id se PIDE, no se teclea (errata nº 49): un test que escribe la clave por la
    # que pregunta coincide por construccion. Aqui ni siquiera se compara con nada, y
    # aun asi se deriva — la regla es del productor, no del uso.
    base = {
        "run_id": identidad.run_id(
            kind="corrida_empalme", date="2026-09-07", result_md5="abc",
        ),
        "date": "2026-09-07", "by": "JCC",
        "que_es": "corrida de empalme", "como_repetir": "",
    }
    base.update(extra)
    return identidad.mensaje_de_id_repetido(**base)


@unittest.skipUnless(HAY, "falta el fixture del raton")
class TestUnResultadoDeOTRO_PANEL_no_LLEGA(unittest.TestCase):
    """La premisa del mensaje retirado, MEDIDA sobre el fichero real y no argumentada.

    Es lo que convierte «no se habia comprobado» en «esta descartado»: con el resultado
    versionado del 2026-09-05 —panel de DIEZ, con `3utr:10` dentro— contra las
    construcciones del panel de hoy, `parse_result` **rechaza el fichero entero** por la
    primera fila. O sea que ese fichero no puede llegar al guardia del duplicado, y por
    tanto no puede ser lo que el aborto mandaba a buscar.

    Si algun dia el panel volviera a incluir a ese candidato, este test lo diria — que es
    justo lo que un argumento escrito en prosa no hace.
    """

    def test_parse_result_lo_RECHAZA_antes_de_llegar_al_duplicado(self):
        from pathlib import Path

        from shmir_design import introns, presentation, spliceai
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.errors import ShmirDesignError
        from shmir_design.reference import load_reference

        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia
        )
        panel = spliceai.build_panel(
            corrida.selection, intron_names=[i.name for i in introns.buildable()],
        )
        viejo = Path(__file__).resolve().parent.parent / MEDIDO
        with self.assertRaises(ShmirDesignError) as cm:
            spliceai.parse_result(
                viejo.read_text(encoding="utf-8"), constructions=panel.constructions
            )
        # Y el motivo NOMBRA la construccion que sobra, que es lo accionable.
        self.assertIn("no es ninguna de las que", str(cm.exception))


class TestElAbortoNoAdivina(unittest.TestCase):

    def test_el_mensaje_COMUN_no_conjetura(self):
        texto = _mensaje().lower()
        for palabra in CONJETURA:
            with self.subTest(palabra):
                self.assertNotIn(palabra, texto)

    def test_NI_el_de_EMPALME_ni_el_de_BLAST(self):
        """Los dos lo tenian, y con la misma frase. Se barren los dos almacenes.

        Se leen del fuente porque son argumentos de una llamada: comprobar solo el que
        se recuerda es como llegamos a que hubiera dos.
        """
        import inspect

        for modulo in (splice_store, blast_store):
            fuente = inspect.getsource(modulo).lower()
            for palabra in CONJETURA:
                with self.subTest(modulo=modulo.__name__, palabra=palabra):
                    self.assertNotIn(palabra, fuente)

    def test_y_DICE_lo_que_SI_se_ha_comprobado(self):
        """Quitar la conjetura no puede dejar el hueco vacio: eso es un aborto a secas.

        Lo que se sabe es que el fichero PASO la validacion contra las construcciones de
        esta corrida. Decirlo es lo que impide volver a mandar a buscar un fichero viejo.
        """
        texto = splice_store.COMO_REPETIR_EMPALME.lower()
        self.assertIn("validaci", texto)
        self.assertIn("panel", texto)

    def test_el_de_BLAST_dice_lo_suyo_y_NO_lo_del_otro(self):
        """Cada uno nombra SU validacion: la de BLAST es el md5 del FASTA de consulta."""
        texto = blast_store.COMO_REPETIR_BLAST.lower()
        self.assertIn("consulta", texto)
        self.assertNotIn("spliceai", texto)

    def test_control_adversario_el_detector_ENCUENTRA_una_conjetura(self):
        """Sin esto, «ninguno conjetura» y «el barrido no mira nada» dan el mismo verde."""
        con_conjetura = _mensaje(
            como_repetir="Casi seguro has cogido el resultado viejo."
        ).lower()
        self.assertTrue(any(p in con_conjetura for p in CONJETURA))


if __name__ == "__main__":
    unittest.main()
