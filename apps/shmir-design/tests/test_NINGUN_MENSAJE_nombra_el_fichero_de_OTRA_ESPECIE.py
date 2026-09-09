"""Lo que la app EMITE en una corrida humana no nombra ningun fichero murino.

Regla 5: escrito antes.

**El fallo.** `offtarget.MISSING_FILE` valia `"transcriptoma_3utr.fa"` —el nombre
MURINO— y lo leian cinco mensajes, mas un sexto escrito inline en
`selection.blocking_fronts`. En humano el gestor pide `transcriptoma_3utr_human.fa`, asi
que los seis mandaban a conseguir un fichero que nadie pide. Es la errata nº 83 —«un
aviso que no nombra el paso que lo cierra no es una instruccion»— con la especie como eje.

Y estaba anticipado: `insumos.py` lo dejo escrito al cerrar la errata nº 47 —*«
`transcriptoma_3utr.fa` es el nombre murino, o sea que en humano fallaban igual»*—. Se
derivo la COMPARACION de md5 y se dejaron los MENSAJES.

**EL GUARDIA MIDE LO QUE SE EMITE, NO EL FUENTE**, y es una decision calibrada
(principio nº 34). Un barrido de literales da **17 ficheros** y casi todos son prosa
legitima —una errata que cita el caso murino, la tabla de nombres base del manifiesto,
la procedencia de un fichero versionado—: exigir una declaracion por cada uno seria un
auditor con falsos positivos, y un auditor asi se apaga el primer dia. Lo que no puede
pasar no es que el nombre este escrito: es que SALGA en una corrida de otra especie.
"""

import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.resolve import resolve_anatomy
from shmir_design.selection import blocking_fronts
from shmir_design.species import SPECIES, required_files, resolve

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(HUMANO)


def nombres_ajenos(slug: str) -> set[str]:
    """Los nombres del deposito que NO son de esta especie. Derivados, no escritos."""
    mios = {f.filename for f in required_files(resolve(slug))}
    ajenos = set()
    for otra in SPECIES:
        if otra == resolve(slug).slug:
            continue
        ajenos |= {f.filename for f in required_files(resolve(otra))} - mios
    return ajenos


def _corrida_humana():
    secuencia = load_reference(HUMANO)
    anatomia = resolve_anatomy(
        name="humano", sequence=secuencia, genbank=DATOS / "NM_000311.5.gb",
    )
    return presentation.page_run(
        species="humano", sequence=secuencia, anatomy=anatomia,
    )


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture humano")
class TestLoQueSeEmiteEnHumano(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida_humana()
        cls.ajenos = nombres_ajenos("humano")

    def test_los_nombres_ajenos_se_DERIVAN_y_no_estan_vacios(self):
        # Control: con el conjunto vacio el guardia daria verde sin mirar nada.
        self.assertTrue(self.ajenos)
        self.assertIn("rmsk_mouse.out", self.ajenos)
        self.assertNotIn("transcriptoma_3utr_human.fa", self.ajenos)

    def test_y_el_CATALOGO_MURINO_ya_NO_es_ajeno_en_humano(self):
        # SE MUEVE CON LA DECISION (2026-09-09). Era el ejemplo de este control, y desde
        # el eje de catalogo `transcriptoma_3utr.fa` es el catalogo del FONDO GENETICO
        # de un diseño humano: nombrarlo en una corrida humana es CORRECTO, y prohibirlo
        # dejaria el segundo barrido sin fichero que pedir. Lo que sigue siendo ajeno es
        # todo lo demas del raton.
        self.assertNotIn("transcriptoma_3utr.fa", self.ajenos)
        pedidos = {
            f.filename for f in required_files(resolve("humano"))
        }
        self.assertIn("transcriptoma_3utr.fa", pedidos)

    def _sin_ajenos(self, textos, donde: str):
        colados = sorted(
            {n for t in textos for n in self.ajenos if n in str(t)}
        )
        self.assertEqual(
            colados, [],
            f"{donde} nombra ficheros que no son de esta especie: {colados}. En humano "
            f"el gestor pide otros, asi que el mensaje manda a conseguir un fichero que "
            f"nadie pide. El nombre se le pide a `species.required_files` por su ROL.",
        )

    def test_ningun_MOTIVO_DE_FRENTE_nombra_uno(self):
        frentes = blocking_fronts(self.corrida.tiling, self.corrida.selection)
        self._sin_ajenos([f.reason for f in frentes], "El motivo de un frente")

    def test_ningun_MOTIVO_DE_FILTRO_de_una_ventana_nombra_uno(self):
        motivos = [
            r.reason
            for ventana in self.corrida.tiling.windows[:200]
            for r in ventana.filters
        ]
        self._sin_ajenos(motivos, "El motivo de un filtro")

    def test_y_el_hueco_de_la_CARGA_DE_OFF_TARGETS_tampoco(self):
        # Es el que lo motiva: `offtarget.MISSING_FILE` con el nombre murino escrito.
        hueco = presentation.offtarget_placeholder(None, species="humano")
        self._sin_ajenos([str(v) for v in hueco.values()], "El hueco de la carga")

    def test_ni_el_INFORME_ENTERO(self):
        """El informe es el artefacto que llega MÁS lejos de quien lo generó, así que es
        el que menos margen tiene de nombrar el fichero de otra especie (principio nº 55).

        Barrerlo entero es lo que cazó el OCTAVO emisor —la lectura de banco del parental
        sin intrón, en `splicing.splicing_readouts`—, que no está en ningún motivo de
        frente ni en ninguna ficha: los siete anteriores se derivaron uno a uno y éste no
        aparecía en la lista de ninguno de ellos.
        """
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD

        texto = text_report(
            species="humano", tiling=self.corrida.tiling,
            selection=self.corrida.selection, scaffold=SGEP_SCAFFOLD,
        )
        self._sin_ajenos([texto], "El informe")

    def test_y_el_hueco_del_MODAL_DE_SEED_tampoco(self):
        """El SÉPTIMO emisor, y salió al derivar los otros seis: un nombre escrito no
        aparece en la lista de quien lee la constante que se acaba de derivar."""
        hueco = presentation.seed_load_placeholder(None, species="humano")
        self._sin_ajenos([str(v) for v in hueco.values()], "El hueco del modal de seed")

    def test_y_la_FICHA_de_un_candidato_tampoco(self):
        """La ficha es el artefacto POR CANDIDATO que viaja, y la lee quien no tiene la
        pantalla delante (principio nº 55). Ahi el `offtarget_seed` por hebra llegaba sin
        especie, asi que nombraba el catalogo murino."""
        from shmir_design.dossier import build_dossier

        inicio = self.corrida.selection.selection.chosen[0].start
        ficha = build_dossier(
            species="humano", tiling=self.corrida.tiling,
            selection=self.corrida.selection, start=inicio,
        )
        self._sin_ajenos([ficha.render()], "La ficha de un candidato")

    def test_el_RATON_sigue_nombrando_LOS_SUYOS(self):
        # Control adversario: dejar de nombrar ficheros tambien pasaria lo de arriba, y
        # un aviso que no dice que fichero falta no es una instruccion.
        secuencia = load_reference(REFERENCES["NM_011170.3"])
        anatomia = resolve_anatomy(
            name="raton", sequence=secuencia, genbank=DATOS / "NM_011170.3.gb",
        )
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
        )
        motivos = " ".join(
            f.reason for f in blocking_fronts(corrida.tiling, corrida.selection)
        )
        self.assertIn("transcriptoma_3utr.fa", motivos)


class TestLasFICHAS_RESUELTAS_tampoco(unittest.TestCase):
    """Y la ficha de obtencion es lo que se lee para conseguir el fichero que falta.

    No necesita el fixture humano: las fichas se resuelven contra la `Species`, no
    contra una corrida. Se barren TODAS y para TODAS las especies declaradas, en vez
    de las tres que se vieron: barrer solo donde ya se ha mirado es como se llega a
    tener tres copias del mismo fallo (principio nº 31).

    Las tres que lo motivan: `transgen` y `empalme_intron` afirmaban un hecho MURINO
    —el casete versionado es el parental sin modulo— nombrando `aav_casete.fa` como si
    fuera «el casete de este proyecto», y `offtarget_seed` decia `refseq_rna.fa`. La
    lista de ficheros de cada ficha si estaba derivada; lo que se quedo atras es la
    prosa de los pasos y los avisos.
    """

    def _textos(self, ficha):
        return (
            list(ficha.steps)
            + list(ficha.warnings)
            + [
                ficha.plain, ficha.question, ficha.validation, ficha.size,
                ficha.source, ficha.url, ficha.why_no_file,
            ]
            + [f.name for f in ficha.files] + [f.why for f in ficha.files]
            + [m.name for m in ficha.metadata] + [m.why for m in ficha.metadata]
        )

    def test_ninguna_ficha_nombra_el_fichero_de_OTRA_especie(self):
        from shmir_design.obtencion import load_all, resolve_ficha

        frentes = sorted(load_all())
        # Control: sin fichas que barrer, esto daria verde sin mirar nada.
        self.assertGreater(len(frentes), 5)
        for slug in SPECIES:
            especie = resolve(slug)
            ajenos = nombres_ajenos(slug)
            self.assertTrue(ajenos, f"{slug}: el conjunto ajeno no puede estar vacio")
            for front in frentes:
                ficha = resolve_ficha(front, species=especie)
                colados = sorted(
                    {n for t in self._textos(ficha) for n in ajenos if n in str(t)}
                )
                self.assertEqual(
                    colados, [],
                    f"La ficha «{front}» resuelta para {especie.scientific} nombra "
                    f"{colados}, que el gestor NO pide para esa especie. El nombre se "
                    f"escribe como `{{fichero_<rol>}}` y lo pone `required_files`.",
                )

    def test_y_la_del_raton_SIGUE_nombrando_los_suyos(self):
        # Control adversario: quitar los nombres de la prosa tambien pasaria lo de
        # arriba, y una ficha que no dice que fichero hay que conseguir no sirve.
        from shmir_design.obtencion import resolve_ficha

        raton = resolve("raton")
        for front, nombre in (
            ("transgen", "aav_casete.fa"),
            ("empalme_intron", "aav_casete.fa"),
            ("offtarget_seed", "refseq_rna.fa"),
        ):
            texto = " ".join(str(t) for t in self._textos(resolve_ficha(front, species=raton)))
            self.assertIn(nombre, texto, f"la ficha «{front}» dejo de nombrarlo")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
