"""Tres servicios más en la fila, y el cruce cuando la guía NO mide 22 nt.

**Pedido (2026-09-04)**: añadir siDirect y BLOCK-iT RNAi Designer a la fila que ya
tienen miRarchitect, SplashRNA y el GPP Web Portal, con el mismo tratamiento — se abren
a mano, ningún código las llama, y su score sólo entra por `tools/import_scores.py`.

**Y con la advertencia que aquí muerde más.** El importador cruza POR SECUENCIA, con
solapamiento exacto: eso funciona mientras las dos partes emitan ventanas de la misma
longitud. **siDirect diseña 19-mers**, no ventanas de 22. Sus candidatos NO van a
coincidir por identidad de cadena con los nuestros aunque señalen exactamente el mismo
sitio — así que el cruce por igualdad daría **cero coincidencias** y eso se leería como
«no hay convergencia», que es una conclusión, no un fallo visible. Es la familia del
«Alu 0 %»: un cero obtenido sin poder buscar.

Dos cosas, y ninguna sobra:

1. **cada servicio DECLARA qué longitud de guía produce**, porque es lo que decide cómo
   se cruza. Sin declararla no se cruza nada: se aborta diciendo dónde se declara;
2. **el cruce va por SOLAPAMIENTO DE VENTANA sobre la referencia**, nunca por igualdad
   de cadena, y el importador **aborta si le llegan longitudes distintas de las
   declaradas** — en vez de no cruzar nada y parecer que no hay convergencia.

Regla 5: escritos antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import external_score as ext  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_3utr,
)

#: EL 3'UTR MURINO DE VERDAD, no una sonda fabricada (regla 5). Y aqui no es una
#: formalidad: una sonda es un motivo repetido, asi que TODA ventana aparece varias
#: veces y `window_overlap` aborta —correctamente— por ambigüedad. El cruce por posicion
#: solo se puede probar sobre una secuencia con ventanas unicas, que es lo que es un
#: 3'UTR real.
RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
REFERENCIA = load_3utr(RATON) if HAY else ""


class TestLaFilaDeServicios(unittest.TestCase):

    def _por_nombre(self, nombre):
        for herramienta in ext.EXTERNAL_TOOLS:
            if herramienta.name == nombre:
                return herramienta
        raise AssertionError(
            f"sin {nombre!r}; los que hay: "
            f"{[h.name for h in ext.EXTERNAL_TOOLS]}"
        )

    def test_estan_los_cinco(self):
        nombres = [h.name for h in ext.EXTERNAL_TOOLS]
        for nombre in ("miRarchitect", "SplashRNA", "GPP Web Portal",
                       "siDirect", "BLOCK-iT RNAi Designer"):
            self.assertIn(nombre, nombres)

    def test_el_GPP_NO_se_duplica(self):
        """El GPP Web Portal YA es el del Broad: comprobado antes de añadir nada.

        Su URL es `portals.broadinstitute.org` y su descripción dice «Genetic
        Perturbation Platform del Broad» desde que se escribió. Añadir «Broad» como
        servicio aparte habría sido la misma herramienta dos veces en la misma fila,
        con dos nombres — que es como se acaba comparando una lista consigo misma.
        """
        broads = [
            h for h in ext.EXTERNAL_TOOLS
            if "broadinstitute.org" in h.url or "broad" in h.name.lower()
        ]
        self.assertEqual(len(broads), 1, [h.name for h in broads])
        self.assertEqual(broads[0].name, "GPP Web Portal")

    def test_cada_servicio_DECLARA_su_longitud_de_guia(self):
        for herramienta in ext.EXTERNAL_TOOLS:
            with self.subTest(herramienta.name):
                self.assertIsInstance(herramienta.guide_length, int)

    def test_siDirect_declara_19(self):
        self.assertEqual(self._por_nombre("siDirect").guide_length, 19)

    def test_los_nuestros_declaran_22(self):
        for nombre in ("miRarchitect", "SplashRNA"):
            self.assertEqual(self._por_nombre(nombre).guide_length, 22)

    def test_BLOCK_iT_NO_se_inventa_la_longitud(self):
        """No se declaró cuál produce, así que sale SIN DECLARAR y no cruza.

        Escribir un 21 de memoria es exactamente lo que la regla 4 prohíbe un nivel más
        abajo: no es una URL, pero es un dato de un servicio ajeno que decide cómo se
        cruza. Un número inventado ahí no da error — da un cruce con la forma correcta.
        """
        herramienta = self._por_nombre("BLOCK-iT RNAi Designer")
        self.assertEqual(herramienta.guide_length, 0)
        self.assertFalse(herramienta.length_declared)
        self.assertIn("declara", herramienta.length_note.lower())

    def test_ninguna_direccion_se_INVENTA(self):
        """Las que no aportó nadie salen VACÍAS y diciéndolo, no adivinadas.

        Las tres primeras las dio el responsable del proyecto. Para las dos nuevas no
        hay dirección aportada, y desde aquí no se puede verificar ninguna —las
        comprobaciones dan 403 en el CONNECT del proxy, que es política de red y no una
        respuesta del servicio—. Regla 4: si no lo has comprobado, no lo escribas.
        """
        for herramienta in ext.EXTERNAL_TOOLS:
            with self.subTest(herramienta.name):
                if not herramienta.url:
                    self.assertIn("dirección", herramienta.url_note.lower())
                else:
                    self.assertTrue(herramienta.url.startswith("http"))

    def test_ninguna_la_llama_el_codigo(self):
        """Mismo trato que las tres de antes: son ENLACES, no endpoints."""
        fuente = (RAIZ / "shmir_design" / "external_score.py").read_text("utf-8")
        for prohibido in ("requests.", "urlopen(", "http.client", "urllib.request"):
            self.assertNotIn(prohibido, fuente)


class TestPorQueNoSonLaFuentePRINCIPAL(unittest.TestCase):
    """La decisión va ESCRITA, no deducida de que no aparezcan.

    Un servicio que no está en la lista y uno que se miró y se descartó son cosas
    distintas, y sin la nota se leen igual: como que nadie lo pensó.
    """

    def test_la_nota_existe_y_da_los_DOS_motivos(self):
        nota = ext.WHY_NOT_PRIMARY.lower()
        self.assertIn("no declaran", nota)
        self.assertIn("poliadenilación", nota)

    def test_y_dice_para_QUE_si_valen(self):
        self.assertIn("contraste", ext.WHY_NOT_PRIMARY.lower())

    def test_entra_en_el_informe(self):
        from shmir_design import informe_doc

        fuente = (RAIZ / "shmir_design" / "informe_doc.py").read_text("utf-8")
        self.assertIn("WHY_NOT_PRIMARY", fuente)
        self.assertTrue(informe_doc)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElCruceVaPorVENTANA(unittest.TestCase):
    """Con longitudes distintas, la igualdad de cadena da CERO y parece un resultado."""

    def setUp(self):
        # Una ventana nuestra de 22 y el 19-mer que cae DENTRO de ella: el mismo sitio.
        self.nuestra = REFERENCIA[440:462]
        self.suya = REFERENCIA[442:461]

    def test_lo_que_de_verdad_pasa_CON_guide_shift_esta_MEDIDO(self):
        """CORRECCIÓN DE LA PREMISA, y va fijada para que no se repita.

        Se pidió esto dando por hecho que un 19-mer **no cruzaría** con una ventana de
        22 «por identidad de secuencia» y daría cero coincidencias. **Medido: no es
        así.** `guide_shift` no compara cadenas iguales — busca el desplazamiento con
        solapamiento exacto de al menos `MIN_OVERLAP`, así que un 19-mer contenido en
        una ventana nuestra **sí cruza**. Sobre el panel murino real: de los **120**
        19-mers que solapan ≥15 nt con alguna de las diez ventanas, `guide_shift` cruza
        **los 120**. Cero fallos.

        Lo que sí está roto es OTRA cosa, y es de la familia del principio nº 27.
        """
        self.assertNotEqual(self.nuestra, self.suya)
        self.assertIsNotNone(ext.guide_shift(self.nuestra, self.suya))

    def test_pero_el_NUMERO_que_devuelve_mezcla_dos_cantidades(self):
        """Un 19-mer CENTRADO en nuestra ventana no está desplazado, y sale con un 2.

        `guide_shift` devuelve un DESPLAZAMIENTO, y con longitudes distintas ese número
        mezcla cuánto está corrida la ventana con cuánto más corta es la guía. Son dos
        cantidades bajo el mismo nombre — principio nº 27 — y de ese número cuelgan
        `DISPLACED_SHIFT` y `MIN_OVERLAP`, los dos DERIVADOS de 22 contra 22.
        """
        # La suya empieza 2 nt DENTRO de la nuestra y acaba 1 nt antes: contenida.
        self.assertEqual(ext.guide_shift(self.nuestra, self.suya), 2)
        # Y lo que hay de verdad es un solapamiento de 19 sobre 19: el máximo posible.
        cruce = ext.window_overlap(self.nuestra, self.suya, reference=REFERENCIA)
        self.assertEqual(cruce.overlap, len(self.suya))

    def test_por_solapamiento_de_ventana_SI(self):
        solape = ext.window_overlap(
            self.nuestra, self.suya, reference=REFERENCIA,
        )
        self.assertIsNotNone(solape)
        self.assertEqual(solape.overlap, 19)

    def test_una_guia_que_NO_esta_en_la_referencia_no_cruza(self):
        # No es un fallo: es informacion. La fuente puede haber diseñado sobre otra
        # secuencia, y eso hay que poder verlo en vez de que reviente.
        self.assertIsNone(
            ext.window_overlap(self.nuestra, "ACGTACGTACGTACGTACG",
                               reference=REFERENCIA)
        )

    def test_dos_sitios_LEJANOS_no_cruzan(self):
        lejana = REFERENCIA[100:119]
        self.assertIsNone(
            ext.window_overlap(self.nuestra, lejana, reference=REFERENCIA)
        )

    def test_una_guia_REPETIDA_en_la_referencia_ABORTA(self):
        """Si la secuencia sale dos veces no identifica ninguna posición.

        Elegir la primera aparición sería fabricar una coordenada. Se aborta, que es lo
        mismo que hace el anclaje del andamio cuando su secuencia no es única.
        """
        repetida = "AAAA"
        if REFERENCIA.count(repetida) < 2:  # pragma: no cover - el 3'UTR murino los tiene
            self.skipTest("el 3'UTR no repite ese tramo")
        with self.assertRaises(ShmirDesignError):
            ext.window_overlap(self.nuestra, repetida, reference=REFERENCIA,
                               min_overlap=1)


class TestLasLongitudesSeCOMPRUEBAN(unittest.TestCase):
    """Si llegan longitudes distintas de las declaradas, ABORTA."""

    def test_lo_que_declara_la_fuente_es_lo_que_se_exige(self):
        ext.check_guide_lengths(["ACGT" * 4 + "ACG"], expected=19, source_name="siDirect")

    def test_una_longitud_distinta_ABORTA_nombrando_las_dos(self):
        with self.assertRaises(ShmirDesignError) as caja:
            ext.check_guide_lengths(["ACGT" * 5 + "AC"], expected=19,
                                    source_name="siDirect")
        mensaje = str(caja.exception)
        self.assertIn("19", mensaje)
        self.assertIn("22", mensaje)
        self.assertIn("siDirect", mensaje)

    def test_y_NO_se_queda_en_cero_cruces_sin_decir_nada(self):
        """Es la diferencia entera: abortar en vez de parecer que no hay convergencia."""
        with self.assertRaises(ShmirDesignError) as caja:
            ext.check_guide_lengths(["ACGT" * 5 + "AC"], expected=19,
                                    source_name="siDirect")
        self.assertIn("convergencia", str(caja.exception).lower())

    def test_sin_longitud_declarada_ABORTA_diciendo_donde_se_declara(self):
        with self.assertRaises(ShmirDesignError) as caja:
            ext.check_guide_lengths(["ACGT" * 4 + "ACG"], expected=0,
                                    source_name="BLOCK-iT RNAi Designer")
        self.assertIn("EXTERNAL_TOOLS", str(caja.exception))


if __name__ == "__main__":
    unittest.main()
