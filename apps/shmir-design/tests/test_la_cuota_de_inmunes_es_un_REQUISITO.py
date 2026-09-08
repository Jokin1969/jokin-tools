"""La cuota de inmunes se CUMPLE si hay forma de cumplirla, aunque no sea la voraz.

Regla 5: escrito antes del arreglo.

**El fallo, y sale de una consecuencia y no de una sospecha.** Al mover el homopolímero a
la molécula (errata nº 144) caen `3utr:143` y otros tres, y el panel resultante se queda
con **DOS inmunes de los tres pedidos** — con la selección diciéndolo, eso sí. Pero la
cuota SÍ se podía cumplir: `{3utr:60, 3utr:144, 3utr:200}` son tres sitios inmunes que
cumplen el espaciado entre ellos y con el resto del panel.

No lo encontraba porque el relleno es **voraz**: coge `3utr:187` (+4,06) por delante de
`3utr:144` (+3,69), y `3utr:187` deja a 43 nt a `3utr:144` y a 13 nt a `3utr:200` — o
sea que se lleva por delante a los dos que habrían completado la cuota.

**Una cuota es un REQUISITO, no una preferencia.** Si el orden voraz la deja corta y
existe un conjunto que la cumple, se toma ese conjunto. Y sólo entonces: donde la voraz
ya la cumple, no cambia nada — que es lo que mantiene el panel confirmado en su sitio.

Decisión del responsable del proyecto (2026-09-07), eligiendo el panel B sobre el que
salía solo: *«es el único que no toca ninguna decisión anterior: conserva la cuota de
inmunes, mantiene la retirada de 3utr:10 y no cede en el espaciado»*.
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.selection import default_config, select_from_report
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: PANEL B, en el marco del 3'UTR. Es el que sale al exigir la cuota, y el que el
#: responsable del proyecto eligió sobre las otras dos opciones el 2026-09-07.
PANEL_B = (60, 144, 200, 359, 449, 553, 673, 736, 818, 1018, 1071)

#: El corte de inmunidad se DERIVA del informe; esto es lo que vale hoy sobre el ratón y
#: se comprueba, no se supone: si un sitio de APA medido lo adelanta, este test lo dice.
CORTE_ESPERADO_TX = 1200


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElPanelCumpleLaCuotaDeInmunes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.informe = tile_utr(secuencia, anatomy=anatomia, species="raton")
        cls.config = default_config()
        cls.seleccion = select_from_report(cls.informe, cls.config)
        cls.offset = RATON.cds[1]

    def _en_utr3(self):
        return tuple(sorted(c.start - self.offset for c in self.seleccion.selection.chosen))

    def test_el_panel_es_el_B(self):
        self.assertEqual(self._en_utr3(), PANEL_B)

    def test_y_salen_LOS_TRES_inmunes(self):
        # El corte SALE de la selección, no de la constante de arriba: la constante
        # sólo sirve para que este test falle si el corte se mueve (principio nº 48).
        corte = self.seleccion.selection.config.apa_immune_before
        self.assertEqual(corte, CORTE_ESPERADO_TX, "el corte se movió: revisa el panel")
        cuantos = sum(1 for c in self.seleccion.selection.chosen if c.start <= corte)
        self.assertEqual(cuantos, self.config.apa_immune_quota)

    def test_y_NO_queda_ninguna_cuota_sin_cubrir(self):
        self.assertEqual(list(self.seleccion.selection.quota_unfilled), [])

    def test_la_seleccion_DICE_que_no_fue_por_el_orden_voraz(self):
        """Una decisión que cambia el panel no puede tomarse en silencio.

        Va en `decisions` y NO en `notes`: `notes` dice lo que se pidió y no se pudo dar
        —algo que quien lee puede cambiar— y esto dice CÓMO se cumplió la cuota. En
        `notes` saldría en rojo en toda corrida por defecto, y un aviso que sale siempre
        deja de leerse.
        """
        texto = " ".join(self.seleccion.selection.decisions)
        self.assertIn("inmunes", texto.lower())
        self.assertIn("espaciado", texto.lower())

    def test_el_espaciado_se_respeta_entre_TODOS(self):
        inicios = sorted(c.start for c in self.seleccion.selection.chosen)
        for a, b in zip(inicios, inicios[1:]):
            self.assertGreaterEqual(b - a, self.config.min_spacing, f"{a} y {b}")


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestCUANTOSCABENSeDERIVA(unittest.TestCase):
    """«Caben cuatro» y «el panel lleva tres» son DOS cantidades, y las dos ciertas.

    La tarjeta del frente de APA —la verde, la que más se lee— decía «el espaciado deja
    meter **cuatro**, que son los **3** que ya están». El cuatro estaba ESCRITO desde que
    la cuota era cuatro y el tres se DERIVA, así que en cuanto la cuota bajó por
    geometría (2026-09-07, retirada de `3utr:10`) la frase se contradecía sola y no daba
    ningún error. Principios nº 13 y nº 27.

    Las dos siguen siendo verdad y por eso no se elige una: **caben** se mide sobre los
    SITIOS ELEGIBLES —que no cambian al retirar un candidato del panel— y **lleva** es
    del panel. Lo que se arregla es pegarlas con un «que son».
    """

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.informe = tile_utr(secuencia, anatomy=anatomia)
        cls.seleccion = select_from_report(cls.informe, default_config())

    def _inmunes(self):
        from shmir_design.selection import derive_immune_cut

        corte = derive_immune_cut(self.informe)
        self.assertIsNotNone(corte, "sin corte no hay inmunidad que medir")
        return [s for s in self.seleccion.selection.sites if s.best.start < corte]

    def test_el_barrido_voraz_da_el_MAXIMO_igual_que_la_busqueda_completa(self):
        """Regla 5 / principio nº 5: dos implementaciones cruzadas, no una borrada.

        El barrido por posición es O(n) y la búsqueda combinatoria es exacta por
        definición. Que coincidan sobre los sitios REALES es lo que permite usar el
        barato en un texto que se repinta en cada rerun (errata nº 59).
        """
        from shmir_design.selection import _conjunto_que_cumple, inmunes_que_caben

        sitios = self._inmunes()
        espaciado = self.seleccion.selection.config.min_spacing
        exacto = _conjunto_que_cumple(sitios, len(sitios), [], espaciado)
        self.assertIsNotNone(exacto, "control adversario: no cabe ni uno")
        self.assertEqual(inmunes_que_caben(sitios, espaciado), len(exacto))

    def test_CABEN_cuatro_y_el_panel_lleva_TRES(self):
        """Las dos cifras medidas, y la primera INCLUYE al retirado.

        `3utr:10` sigue siendo un sitio elegible —lo que se retiró es su plaza—, así que
        cuenta para «cuántos caben». Es exactamente por lo que las dos cantidades no
        pueden fundirse.
        """
        from shmir_design.selection import inmunes_que_caben

        espaciado = self.seleccion.selection.config.min_spacing
        self.assertEqual(inmunes_que_caben(self._inmunes(), espaciado), 4)
        corte = self.seleccion.selection.config.apa_immune_before
        lleva = sum(1 for c in self.seleccion.selection.chosen if c.start <= corte)
        self.assertEqual(lleva, 3)

    def test_y_la_TARJETA_las_emite_como_dos_y_sin_ningun_numero_escrito(self):
        """Lo que se lee, no lo que se calcula (principio nº 23).

        El control que importa es el segundo: la frase no puede volver a llevar un
        número en letra al lado de otro derivado. Se comprueba sobre el texto que emite
        el frente, que es el que va a la tarjeta y al informe descargable.
        """
        from shmir_design.selection import blocking_fronts

        frente = next(
            f for f in blocking_fronts(self.informe, self.seleccion)
            if f.name == "fraccion_isoforma_larga"
        )
        self.assertIn("caben 4 de esos sitios juntos", frente.reason)
        self.assertIn("el panel lleva 3", frente.reason)
        self.assertIn("Son DOS cantidades", frente.reason)
        for escrito in ("cuatro", "tres", "cinco"):
            self.assertNotIn(escrito, frente.reason, f"«{escrito}» va escrito a mano")
