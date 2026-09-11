"""La colision de seed va por ORGANISMO, con la MISMA lista que los off-targets.

**LA DECISION (2026-09-11)**, con las palabras del responsable del proyecto: *«el panel
humano se valida en el raton humanizado Tg650. El shmiR se expresa en neuronas de raton,
cuya maquinaria endogena de miARN es murina. Por la misma logica que el eje de
transcriptoma dual, `seed_colision` debe correr contra `hsa-` Y `mmu-` por separado — el
murino mide el experimento y el humano mide el paciente. Los veredictos de cada prefijo
van SEPARADOS, SIN fundirse»*.

Lo que este fichero fija no es que hoy haya dos columnas —eso cambia con la especie—
sino las cuatro propiedades que hacen que el eje no se pueda deshacer sin que la suite
lo diga:

  1. **la lista de organismos es UNA** (`species.model_organisms`) y la comparten los dos
     frentes. Con una por frente, el dia que se declare un segundo fondo genetico uno de
     los dos se quedaria con uno solo, y el sintoma seria medir la mitad con la forma
     correcta;
  2. **el prefijo se DERIVA del organismo del eje**, no de la especie del diseño. Con la
     del diseño, las dos corridas del panel humano filtrarian las dos por `hsa-`: dos
     columnas, el mismo numero, y ninguna forma de verlo;
  3. **una corrida es de UN organismo y lo declara**; una que no lo declare —las
     guardadas antes del eje— no contesta por ninguno;
  4. **la tasa base sigue al conjunto consultado**, asi que la de la union NO sustituye a
     la de cada eje (errata nº 118, un eje mas alla).

Y una quinta que no es de diseño sino de mecanica, y que habria bloqueado el eje entero:
el `run_id` sale del md5 del CRUDO, asi que dos corridas del mismo panel que salgan
LIMPIAS en los dos ejes tendrian el mismo crudo y el mismo id — la segunda se rechazaria
como «el mismo fichero subido dos veces». El organismo va DENTRO del crudo.

Regla 5: escritos antes.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import unittest
from pathlib import Path

from shmir_design import mirna, presentation
from shmir_design import identidad
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterResult, FilterState
from shmir_design.seed_scan import SeedParams, union_base_rate
from shmir_design.seed_store import FILTER_NAME, SeedStore
from shmir_design.species import (
    MIRNA_AXIS_IS_ONE_FILE, mirna_axis, model_organism_slugs,
    off_target_catalogue_slugs,
)

PANEL = (10, 60, 143)


class _ScanFalso:
    """La superficie minima de un `SeedScan` para el almacen, CON su organismo."""

    def __init__(self, consultas, *, organism, level="LIMPIO"):
        self.organism = organism
        self.params = SeedParams(species_prefix="mmu-")
        self.base_rate = None
        self._consultas = tuple(consultas)
        self._level = level
        self.results = tuple(
            _ResultadoFalso(c, level=level) for c in self._consultas
        )

    def axis_line(self) -> str:
        return f"EJE: {self.organism}."


class _ResultadoFalso:
    def __init__(self, consulta, *, level):
        self.query = consulta
        self.strand = "guia"
        self.window = "2-8"
        self.heptamer = "ACGTACG"
        self.level = level
        self.collisions = ()
        self.mir30 = False


class _CorridaFalsa:
    def __init__(self, consultas, *, organism, run_id, level="LIMPIO"):
        self.run_id = run_id
        self.date = "2026-09-11"
        self.ran_by = "prueba"
        self.source = "mature.fa de prueba"
        self.scan = _ScanFalso(consultas, organism=organism, level=level)

    @property
    def organism(self) -> str:
        return self.scan.organism

    @property
    def query_names(self):
        return tuple(r.query for r in self.scan.results)

    def result_for(self, consulta):
        return next(
            (r for r in self.scan.results if r.query == consulta), None,
        )

    def verdict(self, consulta) -> FilterResult:
        resultado = self.result_for(consulta)
        estado = FilterState.FAIL if resultado.level == "FAIL" else FilterState.PASS
        return FilterResult(
            name=FILTER_NAME, state=estado,
            reason=f"{resultado.level}. {self.scan.axis_line()}",
        )


def _id(sufijo: str) -> str:
    """El `run_id`, PEDIDO y no escrito (principio nº 25).

    Un test que teclea la clave por la que pregunta coincide por construccion, y este la
    usa para distinguir dos corridas del mismo panel: escrita, no podria ver el dia que
    el formato cambie — que es justo lo que paso con `raton_pos200_guia`.
    """
    return identidad.run_id(
        kind="corrida_seed", date="2026-09-11",
        result_md5=identidad.result_fingerprint(sufijo),
    )


def _almacen_con(*corridas) -> SeedStore:
    tienda = SeedStore()
    tienda.runs.extend(corridas)
    return tienda


def _consultas(especie, starts=PANEL, hebras=("guia", "pasajera")):
    return [
        presentation.query_name(especie, inicio, hebra)
        for inicio in starts for hebra in hebras
    ]


class TestElEjeEsElMISMOqueElDeOffTargets(unittest.TestCase):
    """La propiedad 1: una sola lista, dos frentes."""

    def test_los_dos_frentes_declaran_el_eje(self):
        for frente in ("seed_colision", "offtarget_seed"):
            with self.subTest(frente):
                self.assertTrue(
                    presentation.STORE_FOR_FRONT[frente]["por_catalogo"],
                    f"{frente} dejó de declarar el eje de organismo",
                )

    def test_y_la_lista_de_organismos_sale_del_MISMO_sitio(self):
        for especie in ("raton", "human"):
            with self.subTest(especie):
                self.assertEqual(
                    model_organism_slugs(especie),
                    off_target_catalogue_slugs(especie),
                )

    def test_el_humano_declara_DOS_y_el_raton_UNO(self):
        # No es el numero lo que se fija —eso cambia con la declaracion— sino que el
        # humano tenga fondo genetico y el raton no: si el humano se quedara con uno,
        # este eje habria dejado de existir sin que nada lo dijera.
        self.assertEqual(model_organism_slugs("human"), ("human", "mouse"))
        self.assertEqual(model_organism_slugs("raton"), ("mouse",))

    def test_las_columnas_del_panel_humano_son_CUATRO(self):
        columnas = presentation.store_front_columns(
            "seed_colision", presentation.STORE_FOR_FRONT["seed_colision"],
            species="Homo sapiens",
        )
        self.assertEqual(
            sorted(columnas),
            [
                "seed_colision:guia:human", "seed_colision:guia:mouse",
                "seed_colision:pasajera:human", "seed_colision:pasajera:mouse",
            ],
        )

    def test_el_eje_NO_necesita_ningun_fichero_nuevo_y_SE_DICE(self):
        # `mature.fa` trae los maduros de todas las especies: el eje es un filtro por
        # prefijo sobre el mismo fichero. Sin decirlo, la segunda corrida se lee como si
        # esperara una descarga y se aplaza por una razon que no existe.
        self.assertIn("mature.fa", MIRNA_AXIS_IS_ONE_FILE)
        opciones = presentation.seed_axis_options(species="Homo sapiens")
        self.assertEqual([o["organismo"] for o in opciones], ["human", "mouse"])
        # NINGUNA opcion habla de depositar un fichero: no hay ninguno que depositar.
        for opcion in opciones:
            self.assertNotIn("nombre", opcion)


class TestElPrefijoSaleDelEJE(unittest.TestCase):
    """La propiedad 2, que es la que hace que las dos columnas digan cosas distintas."""

    def test_cada_organismo_trae_SU_prefijo(self):
        self.assertEqual(
            mirna_axis("human"), (("human", "hsa-"), ("mouse", "mmu-")),
        )

    def test_y_son_DISTINTOS(self):
        # El control que importa: si los dos ejes filtraran por el mismo prefijo, las
        # dos columnas darian el mismo numero y no habria forma de verlo.
        prefijos = [p for _, p in mirna_axis("human")]
        self.assertEqual(len(set(prefijos)), len(prefijos))

    def test_una_especie_SIN_declarar_no_tiene_eje_y_no_se_inventa_uno(self):
        self.assertEqual(mirna_axis("conejo"), ())
        self.assertEqual(presentation.seed_axis_options(species="conejo"), [])


class TestElVeredictoSePidePORORGANISMO(unittest.TestCase):
    """La propiedad 3: sin organismo no hay veredicto, y no hay defecto."""

    def setUp(self):
        self.consulta = presentation.query_name("human", 10, "guia")
        self.tienda = _almacen_con(
            _CorridaFalsa(
                [self.consulta], organism="human", run_id=_id("aaa"),
            ),
        )

    def test_sin_organismo_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            self.tienda.verdict_for(self.consulta, background="")

    def test_contesta_por_el_SUYO(self):
        resultado = self.tienda.verdict_for(self.consulta, background="human")
        self.assertIs(resultado.state, FilterState.PASS)

    def test_y_NO_contesta_por_el_OTRO(self):
        # Es la mitad adversaria: sin ella, «contesta» y «contesta a cualquier cosa»
        # dan el mismo verde — y eso es el veredicto fundido que la decisión prohíbe.
        resultado = self.tienda.verdict_for(self.consulta, background="mouse")
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("mouse", resultado.reason)

    def test_una_corrida_SIN_organismo_no_contesta_por_ninguno(self):
        vieja = _almacen_con(
            _CorridaFalsa(
                [self.consulta], organism="", run_id=_id("bbb"),
            ),
        )
        for organismo in ("human", "mouse"):
            with self.subTest(organismo):
                resultado = vieja.verdict_for(self.consulta, background=organismo)
                self.assertIs(resultado.state, FilterState.NOT_RUN)
                self.assertIn("NO DECLARAN", resultado.reason)

    def test_un_AVISO_en_un_eje_NO_arrastra_al_otro(self):
        """Lo que se pidió con esas palabras: «sin bloquear el otro»."""
        consulta = presentation.query_name("human", 10, "guia")
        tienda = _almacen_con(
            _CorridaFalsa(
                [consulta], organism="human", run_id=_id("ccc"),
            ),
            _CorridaFalsa(
                [consulta], organism="mouse", run_id=_id("ddd"),
                level="FAIL",
            ),
        )
        humano = tienda.verdict_for(consulta, background="human")
        murino = tienda.verdict_for(consulta, background="mouse")
        self.assertIs(humano.state, FilterState.PASS)
        self.assertIs(murino.state, FilterState.FAIL)


class TestElFrenteSoloCierraConLasCUATRO(unittest.TestCase):
    """La regla de siempre —todas las columnas, todo el panel— sobre el eje nuevo."""

    def _estados(self, organismos):
        corridas = [
            _CorridaFalsa(
                _consultas("human"), organism=organismo,
                run_id=_id(organismo),
            )
            for organismo in organismos
        ]
        return presentation.store_states_by_front(
            {"seed": _almacen_con(*corridas)}, species="human", starts=PANEL,
        )

    def test_con_los_DOS_ejes_el_frente_se_cierra(self):
        from shmir_design.coords import Frame

        estados = self._estados(("human", "mouse"))
        self.assertIn("seed_colision", estados)
        self.assertIn(
            "seed_colision",
            presentation.fronts_closed_over_panel(
                estados, starts=PANEL, frame=Frame.UTR3,
            ),
        )

    def test_Y_CON_UNO_SOLO_NO(self):
        """La mitad adversaria. Sin ella, «cierra» y «no mira nada» dan el mismo verde."""
        from shmir_design.coords import Frame

        estados = self._estados(("human",))
        self.assertNotIn(
            "seed_colision",
            presentation.fronts_closed_over_panel(
                estados, starts=PANEL, frame=Frame.UTR3,
            ),
            "con un solo eje corrido el frente NO puede cerrarse: la mitad de la "
            "pregunta no se ha hecho.",
        )


class TestLaTasaDeLaUNIONnoSustituyeALaDeCadaEJE(unittest.TestCase):
    """La propiedad 4. Es la errata nº 118 con un eje más."""

    def test_la_de_la_union_se_DECLARA_como_tal(self):
        rate = union_base_rate(_MaduroFalso(), SeedParams(), ["hsa-", "mmu-"])
        self.assertTrue(rate.is_union)
        self.assertEqual(rate.union_of, ("hsa-", "mmu-"))
        self.assertIn("NO es la tasa de ningún veredicto", rate.describe())

    def test_y_la_de_UN_solo_prefijo_NO_es_union(self):
        from shmir_design.seed_scan import base_rate

        rate = base_rate(_MaduroFalso(), SeedParams(species_prefix="hsa-"))
        self.assertFalse(rate.is_union)

    def test_la_union_de_UNO_da_lo_mismo_que_la_de_ese_uno(self):
        # Con una sola especie declarada no puede haber dos cifras donde hay una.
        from shmir_design.seed_scan import base_rate

        maduros = _MaduroFalso()
        params = SeedParams(species_prefix="hsa-")
        self.assertEqual(
            union_base_rate(maduros, params, ["hsa-"]).distinct,
            base_rate(maduros, params).distinct,
        )

    def test_sin_ningun_prefijo_ABORTA_en_vez_de_dar_cero(self):
        with self.assertRaises(ShmirDesignError):
            union_base_rate(_MaduroFalso(), SeedParams(), [])

    def test_la_cifra_publicada_se_DECLARA_con_su_procedencia(self):
        publicada = mirna.UNION_RATE_MEASURED
        self.assertEqual(publicada["prefijos"], ("mmu-", "hsa-"))
        self.assertEqual(publicada["space"], 16384)
        self.assertTrue(publicada["mature_md5"])
        # Y lo que SIGNIFICA va al lado: sin eso, dos tasas distintas en la misma
        # pantalla se leen como una discrepancia y alguien promedia.
        self.assertIn("no es la tasa de ningún veredicto", mirna.WHY_THE_UNION_RATE.lower())


class _MaduroFalso:
    """Un `MatureSet` minimo: seeds con sus nombres, de dos especies.

    Es un DOBLE en memoria, no un artefacto fabricado en el deposito: lo que se
    prueba aqui es la MECANICA del eje —que el prefijo filtre, que la union sume sin
    contar dos veces— y para eso hace falta un fichero con maduros de DOS especies y
    seeds que se puedan contar a mano. Las cifras reales las cruza
    `TestLaUNIONsobreElFicheroDEVERDAD`, que se salta si `mature.fa` no esta.
    """

    provenance = "mature.fa de prueba, md5 000, release 0"
    checksum = "0" * 32
    version = "release de prueba"
    seeds = {
        "ACGTACG": ["hsa-miR-1", "mmu-miR-1"],
        "TTTTTTT": ["hsa-miR-2"],
        "GGGGGGG": ["mmu-miR-3"],
    }


class TestUnaCorridaDECLARAsuORGANISMO(unittest.TestCase):
    """`run_scan` de punta a punta: el camino que ESCRIBE en el almacén."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.reference import (
            REFERENCES, fixture_available, load_reference,
        )

        cls.ref = REFERENCES["NM_011170.3"]
        if not fixture_available(cls.ref):
            raise unittest.SkipTest("NOT_RUN: falta data/reference/NM_011170.3.fa")
        secuencia = load_reference(cls.ref)
        anatomia = Anatomy.from_cds(
            cds=cls.ref.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
        )
        cls.panel = presentation.chosen_starts(cls.corrida.selection)[:2]

    def _scan(self, organismo, **cambios):
        from shmir_design.seed_scan import run_scan

        return run_scan(
            self.corrida.selection, mature=_MaduroFalso(), species="raton",
            starts=self.panel, guides=True, passengers=False,
            organism=organismo, **cambios,
        )

    def test_sin_organismo_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            self._scan("")

    def test_un_organismo_que_NO_esta_en_el_eje_ABORTA(self):
        # Comparar contra los maduros de un organismo que este diseño no mide es
        # inventarse la procedencia de un veredicto.
        with self.assertRaises(ShmirDesignError):
            self._scan("human")

    def test_el_scan_DECLARA_su_organismo_y_deriva_su_prefijo(self):
        scan = self._scan("mouse")
        self.assertEqual(scan.organism, "mouse")
        self.assertEqual(scan.params.species_prefix, "mmu-")

    def test_y_el_ORGANISMO_va_DENTRO_del_crudo(self):
        """Sin esto, las dos corridas del panel humano chocarían de `run_id`.

        El id es `seed-<fecha>-<md5 del crudo>`, así que dos ejes que salgan LIMPIOS en
        todo el panel darían el mismo crudo, el mismo md5 y el mismo id: la segunda se
        rechazaría como «el mismo fichero subido dos veces» y el eje que se venía a
        cubrir se quedaría sin corrida.
        """
        scan = self._scan("mouse")
        self.assertIn("# organismo\tmouse\tmmu-", scan.raw)

    def test_el_bloque_exportable_dice_CONTRA_QUIEN(self):
        # Se lee sin la app delante: un `LIMPIO` sin decir contra qué conjunto se lee
        # como limpio contra los dos (principio nº 55).
        bloque = self._scan("mouse").export_block()
        self.assertIn("EJE:", bloque)
        self.assertIn("Mus musculus", bloque)


MATURE = (
    Path(__file__).resolve().parent.parent / "data" / "reference" / "mature.fa"
)


@unittest.skipUnless(MATURE.is_file(), f"NOT_RUN: falta {MATURE}")
class TestLaUNIONsobreElFicheroDEVERDAD(unittest.TestCase):
    """La cifra publicada, CRUZADA contra el fichero. Principio nº 13.

    Sin este cruce, `UNION_RATE_MEASURED` sería prosa que se queda atrás con la
    siguiente release de miRBase; con él, es lo que delata el día que el fichero cambie
    sin que nadie mire las cifras.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.mirna import load_mature
        from shmir_design.trabajo import reference_dir

        cls.maduros = load_mature(reference_dir() / "mature.fa")

    def test_la_union_coincide_con_la_publicada(self):
        publicada = mirna.UNION_RATE_MEASURED
        medida = union_base_rate(
            self.maduros,
            SeedParams(window=publicada["window"], level=publicada["level"]),
            publicada["prefijos"],
        )
        self.assertEqual(medida.matures, publicada["matures"])
        self.assertEqual(medida.distinct, publicada["distinct"])
        self.assertEqual(medida.space, publicada["space"])

    def test_y_la_de_CADA_eje_es_MENOR_que_la_de_la_union(self):
        # La lectura entera: la union no es la tasa de ningun veredicto, y por eso no
        # puede sustituirla — es sensiblemente mayor.
        from shmir_design.seed_scan import base_rate

        union = union_base_rate(
            self.maduros, SeedParams(), ["mmu-", "hsa-"],
        ).fraction
        for prefijo in ("mmu-", "hsa-"):
            with self.subTest(prefijo):
                sola = base_rate(
                    self.maduros, SeedParams(species_prefix=prefijo),
                ).fraction
                self.assertLess(sola, union)


if __name__ == "__main__":
    unittest.main()
