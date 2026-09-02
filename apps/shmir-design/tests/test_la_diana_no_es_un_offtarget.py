"""Un gen tiene VARIAS variantes de transcrito y todas son la diana.

**Reportado con el `.tsv` delante (2026-09-02)**: `FAIL` en los diez candidatos, y diez
de diez apunta a criterio mal aplicado, no a diez guías malas. La hipótesis la trajo quien
lo reportó y era la correcta en la consecuencia:

    mouse_pos959_guia   NM_011170.3      100%
    mouse_pos959_guia   NM_001278256.1   100%

`NM_011170.3` es el transcrito del diseño; `NM_001278256.1` es **otra variante del mismo
gen** —la que PolyA_DB usa como representante de Prnp, y que ya salió en el anclaje del
APA—. Cada candidato fallaba **contra su propio blanco**.

**El mecanismo era peor que la hipótesis**: no había exención por accession ni por nada.
`verdict()` no miraba `subject` siquiera —comprobado sobre su bytecode— y fallaba con
«más de un» acierto grave. Ese `> 1` era una exención IMPLÍCITA: «uno es tuyo».

Regla 5: escritos antes.
"""

import unittest

from shmir_design import blast, blast_store, specificity
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.presentation import query_name

#: SE LE PIDE al productor, no se transcribe. Escribir aqui el formato haria que este
#: test coincidiera consigo mismo (principio nº 25): el dia que la clave cambie, seguiria
#: en verde mientras la app deja de emparejar nada.
CONSULTA = query_name("mouse", 959, "guia")
GUIA = "TTATATTCTTATTGGCCCGGTG"
DIANA = specificity.target_accessions("mouse")


def _hit(sujeto, *, mismatches=0, antisentido=True):
    inicio, fin = (1191, 1170) if antisentido else (1170, 1191)
    return (
        f"{CONSULTA}\t{sujeto}\t100.000\t22\t{mismatches}\t0\t1\t22\t"
        f"{inicio}\t{fin}\t1e-05\t44.1\n"
    )


def _corrida(crudo):
    return blast_store.BlastRun.create(
        run_id="r1", date="2026-09-02", uploaded_by="jc",
        params=blast.BlastParams.for_species("mouse"),
        database=blast_store.BlastDatabase(
            name="refseq_rna_mouse", version="2026-09", md5="a" * 32, remote=False,
        ),
        query=blast.QueryFasta.from_records(((CONSULTA, GUIA),)),
        raw=crudo,
    )


class TestElCasoReportado(unittest.TestCase):
    """Las dos variantes del gen, tal cual salieron en el `.tsv`."""

    def test_dos_variantes_de_la_DIANA_dan_PASS(self):
        corrida = _corrida(_hit(DIANA[0]) + _hit(DIANA[1]))
        self.assertIs(
            corrida.verdict(CONSULTA, species="mouse").state, FilterState.PASS
        )

    def test_y_el_motivo_DICE_contra_que_acerto(self):
        # Lo pidió con esas palabras: con el accession al lado, esto se habría visto en
        # dos segundos en vez de en un intercambio.
        motivo = _corrida(_hit(DIANA[0]) + _hit(DIANA[1])).verdict(
            CONSULTA, species="mouse"
        ).reason
        for accession in DIANA:
            self.assertIn(accession, motivo)
        self.assertIn("propia diana", motivo)

    def test_un_off_target_de_VERDAD_sigue_dando_FAIL(self):
        # Control adversario: si la exención tapara todo, el frente no mediría nada.
        corrida = _corrida(_hit(DIANA[0]) + _hit("NM_999999.1"))
        resultado = corrida.verdict(CONSULTA, species="mouse")
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("NM_999999.1", resultado.reason)


class TestElUmbralYaNOesconde_unSupuesto(unittest.TestCase):
    """`> 1` significaba «uno es tuyo», y fallaba en las DOS direcciones."""

    def test_UN_solo_acierto_fuera_de_la_diana_YA_es_FAIL(self):
        # Con el umbral viejo esto pasaba: un off-target perfecto se colaba como si
        # fuera la diana. Es la dirección que NO se ve.
        corrida = _corrida(_hit("NM_999999.1"))
        self.assertIs(
            corrida.verdict(CONSULTA, species="mouse").state, FilterState.FAIL
        )

    def test_y_si_NO_acierta_a_su_propia_diana_se_DICE(self):
        # La otra dirección: el umbral viejo daba PASS a una guía que no reconoce su
        # blanco, por no tener con qué compararse. No veta —la potencia es otro frente—
        # pero deja de pasar en silencio.
        resultado = _corrida(_hit("NM_555555.1", mismatches=2)).verdict(
            CONSULTA, species="mouse"
        )
        self.assertIn("ningún acierto contra su propia diana", resultado.reason.lower()
                      .replace("ningun", "ningún"))


class TestLaORIENTACION(unittest.TestCase):
    """`filter_specificity` descartaba los hits en sentido; `verdict` no los miraba."""

    def test_un_hit_en_SENTIDO_no_es_un_off_target(self):
        corrida = _corrida(_hit(DIANA[0]) + _hit("NM_999999.1", antisentido=False))
        resultado = corrida.verdict(CONSULTA, species="mouse")
        self.assertIs(resultado.state, FilterState.PASS)
        self.assertIn("SENTIDO", resultado.reason)

    def test_la_orientacion_se_DERIVA_del_intervalo_del_sujeto(self):
        # En `-outfmt 6` no hay columna de hebra: está en el signo de `sstart`→`send`.
        hits = blast.parse_outfmt6(_hit("NM_1") + _hit("NM_2", antisentido=False))
        self.assertEqual([h.antisense for h in hits], [True, False])


class TestSinDIANAdeclaradaNOhayVEREDICTO(unittest.TestCase):
    """La condición sin la cual la exención sería un colador."""

    def test_una_especie_sin_declarar_da_NO_CIERRA_y_NO_un_PASS(self):
        resultado = _corrida(_hit(DIANA[0])).verdict(CONSULTA, species="human")
        self.assertIs(resultado.state, FilterState.NO_CIERRA)
        self.assertIn("variantes de transcrito", resultado.reason)

    def test_sin_especie_tampoco(self):
        self.assertIs(
            _corrida(_hit(DIANA[0])).verdict(CONSULTA).state, FilterState.NO_CIERRA
        )

    def test_el_criterio_ABORTA_con_la_lista_vacia(self):
        with self.assertRaises(ValueError):
            specificity.judge_hits((), target_accessions=())

    def test_la_tabla_declara_procedencia_de_cada_especie(self):
        import tomllib
        from pathlib import Path

        ruta = (
            Path(__file__).resolve().parent.parent / "data" / "diana" / "variantes.toml"
        )
        with ruta.open("rb") as f:
            tabla = tomllib.load(f)
        for especie, entrada in tabla.items():
            with self.subTest(especie):
                self.assertTrue(entrada["accessions"])
                self.assertTrue(entrada["procedencia"].strip())


class TestUNsoloCRITERIO(unittest.TestCase):
    """Eran dos implementaciones del mismo frente y la del veredicto no tenía diana."""

    def test_filter_specificity_LLAMA_al_criterio_comun(self):
        import inspect

        self.assertIn(
            "judge_hits", inspect.getsource(specificity.filter_specificity)
        )

    def test_y_el_veredicto_de_la_corrida_TAMBIEN(self):
        import inspect

        self.assertIn("judge_hits", inspect.getsource(blast_store.BlastRun.verdict))

    def test_los_dos_lados_dan_LO_MISMO_sobre_los_mismos_aciertos(self):
        # El cruce que ata los dos contadores del mismo suceso: mismos hits, mismo
        # veredicto. Sin esto vuelven a separarse.
        class _Falso:
            def __init__(self, transcript, mismatches, antisense):
                self.transcript, self.mismatches = transcript, mismatches
                self.antisense = antisense

            def describe(self):
                return self.transcript

        propios = blast.parse_outfmt6(_hit(DIANA[0]) + _hit("NM_999999.1"))
        ajenos = [_Falso(h.transcript, h.mismatches, h.antisense) for h in propios]
        self.assertEqual(
            specificity.judge_hits(propios, target_accessions=DIANA).state,
            specificity.judge_hits(ajenos, target_accessions=DIANA).state,
        )


if __name__ == "__main__":
    unittest.main()
