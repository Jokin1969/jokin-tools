"""La convención de posiciones viaja PEGADA A LOS DATOS, y un marco ajeno se detecta.

**Medido (2026-09-05, corrida real con SpliceAI 1.3, cinco modelos promediados)**: la app
declara `donante=3134` y el pico está en **3133**; declara `aceptor=3428` y el pico está
en **3430**. No es un error de nadie: son **dos convenciones distintas para el mismo
sitio**.

```
donante   app → la G de GT      SpliceAI → última base exónica   → donante − 1
aceptor   app → la A de AG      SpliceAI → primera base exónica  → aceptor + 2
```

Lo que lo convierte en errata es lo que pasó sin corregir: **en la posición declarada la
puntuación es `2e-07`, no cero**, así que la salvaguarda `donante legítimo <= 0` NO
mordió y se escribió un análisis entero —107.680 filas— que no se podía normalizar.
Es el principio nº 33 otra vez con otra cara: el guardia estaba y el número que le
llegaba pasaba por encima de su criterio.

Y de aquí salen dos exigencias distintas:

1. **Que la cabecera del FASTA declare la CONVENCIÓN, no sólo la posición.** Quien escriba
   el siguiente puente tiene que poder saberlo sin medirlo.
2. **Que el estado del panel viaje DENTRO del fichero**, no sólo en su nombre: *«un nombre
   se pierde en el primer `mv`»*. Lo que va pegado a los datos sobrevive.

Regla 5: escritos antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation, spliceai  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.filters import FilterState  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

RATON = REFERENCES["NM_011170.3"]
CASETE = RAIZ / "data" / "reference" / "aav_casete.fa"
MEDIDO = RAIZ / "data" / "medido" / "spliceai_mvm_actual_2026-09-05.tsv"
HAY = fixture_available(RATON) and CASETE.exists() and MEDIDO.exists()

DOS = ("mvm_actual", "intron_quimerico")


def _corrida():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(species="raton", sequence=tx, anatomy=anat)


def _casete() -> str:
    return "".join(
        l.strip() for l in CASETE.read_text("utf-8").splitlines()
        if not l.startswith(">")
    )


def _panel(corrida, intrones=("mvm_actual",)):
    return spliceai.build_panel(
        corrida.selection, intron_names=intrones, scaffold=SGEP_SCAFFOLD,
        cassette=_casete(), context_nt=5000,
    )


def _resultado_medido(panel, *, convencion: str | None) -> str:
    """El resultado REAL, con el md5 de la construcción DE HOY.

    Las **puntuaciones no se tocan**: salen tal cual de la corrida del 2026-09-05. Lo que
    se reescribe es la columna `md5`, y el motivo va escrito porque importa: aquella
    corrida se montó con un casete cuyo flanco 3' medía **112 nt menos** que el que hay
    hoy versionado (5.384 nt frente a 5.496), así que la construcción **no se puede
    reconstruir bit a bit** y su md5 no valdría. Todo lo demás coincide —contexto 5' de
    3.133, donante en 3134, aceptor en 3428—, así que las posiciones medidas son
    exactamente las mismas en la construcción de hoy.
    """
    por_nombre = {c.name: c for c in panel.constructions}
    lineas = []
    if convencion:
        lineas.append(f"# convencion: {convencion}")
    with MEDIDO.open("r", encoding="utf-8") as f:
        lineas.append(next(f).rstrip("\n"))
        for fila in f:
            nombre, _md5, pos, tipo, pun = fila.rstrip("\n").split("\t")
            construccion = por_nombre.get(nombre)
            if construccion is None:
                continue
            lineas.append("\t".join((nombre, construccion.md5, pos, tipo, pun)))
    return "\n".join(lineas) + "\n"


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestLaCabeceraDeclaraLaCONVENCION(unittest.TestCase):
    """Sin esto, el siguiente puente tiene que MEDIR para saber a qué base apunta."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.panel = _panel(cls.corrida)
        cls.fasta = spliceai.constructions_fasta(cls.panel.constructions)
        cls.cabeceras = [l for l in cls.fasta.splitlines() if l.startswith(">")]

    def test_la_posicion_lleva_A_QUE_BASE_apunta(self):
        for cabecera in self.cabeceras:
            self.assertIn("donante=3134(G de GT)", cabecera)
            self.assertIn("aceptor=3428(A de AG)", cabecera)

    def test_y_lleva_la_MISMA_posicion_en_la_convencion_de_spliceai(self):
        # Que no haya que aplicar el desplazamiento a mano: viene aplicado.
        for cabecera in self.cabeceras:
            self.assertIn("spliceai_donante=3133", cabecera)
            self.assertIn("spliceai_aceptor=3430", cabecera)

    def test_el_desplazamiento_esta_declarado_y_es_el_medido(self):
        self.assertEqual(spliceai.TO_SPLICEAI["donante"], -1)
        self.assertEqual(spliceai.TO_SPLICEAI["aceptor"], +2)

    def test_el_bloque_de_comentario_explica_las_dos_convenciones(self):
        comentario = "\n".join(
            l for l in self.fasta.splitlines() if l.startswith("#")
        )
        self.assertIn("G de GT", comentario)
        self.assertIn("A de AG", comentario)
        self.assertIn("SpliceAI", comentario)

    def test_el_fasta_sigue_siendo_LEGIBLE_como_fasta(self):
        # Los comentarios van ANTES del primer «>» y ninguna línea de secuencia se toca.
        cuerpo = self.fasta.splitlines()
        primera = next(i for i, l in enumerate(cuerpo) if l.startswith(">"))
        self.assertTrue(all(l.startswith("#") for l in cuerpo[:primera]))
        secuencias = [l for l in cuerpo[primera:] if not l.startswith(">")]
        self.assertTrue(all(set(l) <= set("ACGTN") for l in secuencias))


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestElESTADO_viaja_DENTRO_del_fichero(unittest.TestCase):
    """*«Un nombre se pierde en el primer `mv`»*. Lo pegado a los datos, no."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.parcial = _panel(cls.corrida, intrones=DOS)
        cls.entero = _panel(cls.corrida)

    def _fasta(self, panel, intrones):
        resumen = presentation.splice_panel_summary(
            panel, introns=intrones, candidates=10,
        )
        return spliceai.constructions_fasta(panel.constructions, summary=resumen)

    def test_el_comentario_dice_CUANTAS_faltan_y_de_que_intron(self):
        fasta = self._fasta(self.parcial, DOS)
        comentario = "\n".join(l for l in fasta.splitlines() if l.startswith("#"))
        self.assertIn("PARCIAL", comentario)
        self.assertIn("10", comentario)
        self.assertIn("20", comentario)
        self.assertIn("intron_quimerico", comentario)

    def test_y_CADA_cabecera_lo_lleva_tambien(self):
        # El comentario lo puede tirar un parser; una cabecera «>» no la tira ninguno.
        fasta = self._fasta(self.parcial, DOS)
        cabeceras = [l for l in fasta.splitlines() if l.startswith(">")]
        self.assertEqual(len(cabeceras), 10)
        for cabecera in cabeceras:
            self.assertIn("panel=10de20", cabecera)
            self.assertIn("estado=PARCIAL", cabecera)

    def test_un_panel_COMPLETO_lo_dice_igual_de_explicito(self):
        fasta = self._fasta(self.entero, ("mvm_actual",))
        for cabecera in (l for l in fasta.splitlines() if l.startswith(">")):
            self.assertIn("panel=10de10", cabecera)
            self.assertIn("estado=COMPLETO", cabecera)

    def test_sin_resumen_NO_se_inventa_un_estado(self):
        # Un FASTA que no sabe de qué panel viene no dice «COMPLETO» por defecto.
        fasta = spliceai.constructions_fasta(self.parcial.constructions)
        for cabecera in (l for l in fasta.splitlines() if l.startswith(">")):
            self.assertNotIn("estado=", cabecera)


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestElGuardiaDelMARCO(unittest.TestCase):
    """`2e-07` no es cero, así que `<= 0` no mordía. Se compara CONTRA EL VECINDARIO."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.panel = _panel(cls.corrida)

    def test_el_marco_ajeno_ABORTA_en_vez_de_normalizar_contra_2e_07(self):
        crudo = _resultado_medido(self.panel, convencion=None)
        with self.assertRaises(ShmirDesignError) as caja:
            spliceai.scan_from_result(crudo, constructions=self.panel.constructions)
        mensaje = str(caja.exception)
        self.assertIn("3133", mensaje)
        self.assertIn("3134", mensaje)

    def test_y_NOMBRA_el_desplazamiento_y_como_declararlo(self):
        crudo = _resultado_medido(self.panel, convencion=None)
        with self.assertRaises(ShmirDesignError) as caja:
            spliceai.scan_from_result(crudo, constructions=self.panel.constructions)
        mensaje = str(caja.exception)
        self.assertIn("convencion: spliceai", mensaje)

    def test_DECLARADA_la_convencion_el_resultado_entra_y_se_normaliza(self):
        crudo = _resultado_medido(self.panel, convencion="spliceai")
        scan = spliceai.scan_from_result(
            crudo, constructions=self.panel.constructions
        )
        self.assertEqual(len(scan.pairs), 10)
        por_nombre = {p.construction: p for p in scan.pairs}
        # Las puntuaciones MEDIDAS, ya en el sitio que la app declara.
        self.assertAlmostEqual(
            por_nombre["mvm_actual__3utr959"].legit_donor, 0.6638, places=3,
        )
        self.assertAlmostEqual(
            por_nombre["mvm_actual__3utr1684"].legit_donor, 0.8714, places=3,
        )
        self.assertAlmostEqual(
            por_nombre["mvm_actual__3utr959"].legit_acceptor, 0.7979, places=3,
        )

    def test_una_convencion_DESCONOCIDA_no_se_adivina(self):
        crudo = _resultado_medido(self.panel, convencion="la_de_alguien")
        with self.assertRaises(ShmirDesignError):
            spliceai.scan_from_result(crudo, constructions=self.panel.constructions)

    def test_el_guardia_EMITE_estado_y_no_solo_aborta(self):
        crudo = _resultado_medido(self.panel, convencion="spliceai")
        scan = spliceai.scan_from_result(
            crudo, constructions=self.panel.constructions
        )
        for par in scan.pairs:
            self.assertIs(par.frame_check.state, FilterState.PASS)

    def test_sin_vecindario_dice_NOT_RUN_en_vez_de_pasar_callando(self):
        """Si el fichero sólo trae la posición declarada, el guardia NO puede correr."""
        construccion = self.panel.constructions[0]
        crudo = "\n".join((
            spliceai.RESULT_HEADER,
            f"{construccion.name}\t{construccion.md5}\t"
            f"{construccion.donor_position}\tdonante\t0.80",
            f"{construccion.name}\t{construccion.md5}\t"
            f"{construccion.acceptor_position}\taceptor\t0.85",
        )) + "\n"
        scan = spliceai.scan_from_result(crudo, constructions=(construccion,))
        self.assertIs(scan.pairs[0].frame_check.state, FilterState.NOT_RUN)
        self.assertTrue(scan.pairs[0].frame_check.reason)


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestCadaSitioDiceEnQUE_REGION_cae(unittest.TestCase):
    """El donante de 0,744 en 1516 **no lo introduce ninguna guía**: viene con el casete."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.panel = _panel(cls.corrida)
        cls.scan = spliceai.scan_from_result(
            _resultado_medido(cls.panel, convencion="spliceai"),
            constructions=cls.panel.constructions,
        )

    def test_1516_cae_en_el_contexto_5_no_en_el_intron(self):
        construccion = self.panel.constructions[0]
        self.assertEqual(spliceai.region_of(construccion, 1516), "contexto5")
        self.assertEqual(
            spliceai.region_of(construccion, construccion.donor_position), "intron"
        )
        self.assertEqual(
            spliceai.region_of(construccion, len(construccion.sequence)), "contexto3"
        )

    def test_el_criptico_mas_fuerte_de_las_diez_esta_en_el_CONTEXTO(self):
        # OJO al marco: el pico que SpliceAI da en 1516 es, en nuestra convención, la
        # G de GT en 1517. Es la traducción funcionando, no un desajuste.
        for par in self.scan.pairs:
            mejor = par.best_cryptic
            self.assertIsNotNone(mejor)
            self.assertEqual(mejor.position, 1517)
            self.assertEqual(mejor.region, "contexto5")

    def test_la_traduccion_CAE_SOBRE_EL_DINUCLEOTIDO_y_eso_la_confirma(self):
        """La comprobación que no depende de ninguna puntuación: la SECUENCIA.

        Si el desplazamiento fuera otro, las posiciones traducidas caerían en cualquier
        sitio. Caen sobre `GT` y `AG` — las diez, y también el críptico del contexto.
        """
        c = self.panel.constructions[0]
        self.assertEqual(c.sequence[c.donor_position - 1:c.donor_position + 1], "GT")
        self.assertEqual(
            c.sequence[c.acceptor_position - 1:c.acceptor_position + 1], "AG"
        )
        for par in self.scan.pairs:
            for criptico in par.cryptics:
                esperado = "GT" if criptico.kind == "donante" else "AG"
                self.assertEqual(
                    c.sequence[criptico.position - 1:criptico.position + 1], esperado,
                    f"{criptico.kind} en {criptico.position} no cae sobre {esperado}",
                )

    def test_y_la_fila_del_informe_lo_dice(self):
        filas = presentation.splice_result_rows(self.scan)
        self.assertTrue(all(f["mejor_criptico_region"] == "contexto5" for f in filas))


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestLaGuiaMODULA_el_donante_legitimo(unittest.TestCase):
    """De 0,664 a 0,871 entre hermanas: un 31 %. El sitio del contexto no se mueve."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.panel = _panel(cls.corrida)
        cls.scan = spliceai.scan_from_result(
            _resultado_medido(cls.panel, convencion="spliceai"),
            constructions=cls.panel.constructions,
        )

    def test_la_modulacion_se_MIDE_y_sale_por_intron(self):
        modulacion = spliceai.donor_modulation(self.scan)
        self.assertEqual(len(modulacion), 1)
        mvm = modulacion[0]
        self.assertEqual(mvm.intron, "mvm_actual")
        self.assertAlmostEqual(mvm.minimum, 0.6638, places=3)
        self.assertAlmostEqual(mvm.maximum, 0.8714, places=3)
        self.assertGreater(mvm.spread, 0.30)

    def test_cada_par_dice_como_queda_FRENTE_A_SUS_HERMANAS(self):
        filas = presentation.splice_result_rows(self.scan)
        por_nombre = {f["construccion"]: f for f in filas}
        self.assertAlmostEqual(
            por_nombre["mvm_actual__3utr1684"]["donante_vs_hermanas"], 1.0, places=6,
        )
        self.assertLess(
            por_nombre["mvm_actual__3utr959"]["donante_vs_hermanas"], 0.80,
        )

    def test_el_sitio_del_CONTEXTO_apenas_se_mueve_y_ese_es_el_contraste(self):
        """La guía modula lo que está en el intrón; lo del plásmido viene dado."""
        valores = [
            next(c.score for c in par.cryptics if c.position == 1517)
            for par in self.scan.pairs
        ]
        recorrido = (max(valores) - min(valores)) / min(valores)
        self.assertLess(recorrido, 0.05)


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestElFicheroDiceDE_QUE_VERSION_Y_CON_QUE_ENTRADAS_viene(unittest.TestCase):
    """Lo que faltaba el 2026-09-05: un FASTA que no cuadra y nada que lo explique.

    Aquel fichero traía construcciones de **5.384 nt** y el código de hoy con el casete
    versionado da **5.496** —112 nt de diferencia, sólo en el flanco 3'—. No se ha podido
    saber si fue otra versión desplegada o otro casete. Las dos cosas van ahora dentro.
    """

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.panel = _panel(cls.corrida)

    def test_la_cabecera_dice_DE_QUE_CASETE_salio_el_contexto(self):
        fasta = spliceai.constructions_fasta(self.panel.constructions)
        for cabecera in (l for l in fasta.splitlines() if l.startswith(">")):
            self.assertIn("contexto_origen=casete:md5=", cabecera)
            self.assertIn("5282nt", cabecera)

    def test_dos_casetes_DISTINTOS_dan_procedencias_distintas(self):
        entero = _casete()
        recortado = entero[:-112]
        self.assertNotEqual(
            spliceai._context_source(entero), spliceai._context_source(recortado)
        )

    def test_sin_casete_lo_dice_igual_y_no_calla(self):
        sin = spliceai.build_panel(
            self.corrida.selection, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD,
        )
        fasta = spliceai.constructions_fasta(sin.constructions)
        self.assertIn("contexto_origen=piezas", fasta)

    def test_el_BUILD_sale_del_entorno_y_sin_el_dice_sin_declarar(self):
        import os

        from shmir_design.identidad import BUILD_ENV, BUILD_NOT_DECLARED, build_stamp

        anterior = os.environ.pop(BUILD_ENV, None)
        try:
            self.assertEqual(build_stamp(), BUILD_NOT_DECLARED)
            os.environ[BUILD_ENV] = "a5fb5e0"
            self.assertEqual(build_stamp(), "a5fb5e0")
            fasta = spliceai.constructions_fasta(self.panel.constructions)
            self.assertIn("# BUILD: a5fb5e0", fasta)
        finally:
            os.environ.pop(BUILD_ENV, None)
            if anterior is not None:
                os.environ[BUILD_ENV] = anterior

    def test_sin_BUILD_el_fichero_NO_se_calla_la_ausencia(self):
        import os

        from shmir_design.identidad import BUILD_ENV, BUILD_NOT_DECLARED

        anterior = os.environ.pop(BUILD_ENV, None)
        try:
            fasta = spliceai.constructions_fasta(self.panel.constructions)
            self.assertIn(f"# BUILD: {BUILD_NOT_DECLARED}", fasta)
        finally:
            if anterior is not None:
                os.environ[BUILD_ENV] = anterior


if __name__ == "__main__":
    unittest.main()
