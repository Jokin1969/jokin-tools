"""Comprobar el plásmido montado a mano, no generarlo.

Regla 5: escritos antes que `shmir_design/montaje.py`.

## Por qué NO se generan los `.dna` completos

Un plásmido de 5.400 pb ensamblado por código es demasiada superficie para un error
silencioso, y el módulo y el casete ya se emiten. Lo que faltaba es lo otro: **entre lo
que la app emite y lo que acaba en el vector no había ninguna comprobación**. Es el mismo
criterio que `gblock.verify_contexts_against_plasmid` con SGEP — se comprueba lo que se
construyó, no se construye.

## Por secuencia, y no por coordenadas

Un número escrito no puede validar el fichero del que salió (principio nº 13). La
comprobación busca el fragmento EN el plásmido y compara secuencia con secuencia; no mira
la posición 3129 de nada. Una feature corrida un nucleótido no la engaña, y un plásmido
con el intrón en otro sitio pasa igual — que es lo correcto: lo que se pregunta es «¿está
dentro lo que emitimos?», no «¿está donde yo creía?».

## Lo que se le puede dar

El FASTA de fragmentos que emite la app, y el plásmido montado en GenBank, en FASTA, en
secuencia pelada o en el `.dna` binario de SnapGene. Del `.dna` se lee el segmento de ADN
y **se comprueban sus propias afirmaciones** —cabecera, longitud declarada y alfabeto—
antes de usarlo: el formato está DECLARADO, no verificado contra un fichero real de este
repositorio, así que el lector no se fía de él, lo interroga.
"""

import struct
import unittest
from pathlib import Path

from shmir_design import fragmento, montaje
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.scaffold import build_hairpin

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
CASETE = DIR / "aav_casete.fa"

GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"


def _casete() -> str:
    crudo = CASETE.read_text(encoding="utf-8").splitlines()
    return "".join(l.strip() for l in crudo if not l.startswith(">")).upper()


def _snapgene(secuencia: str) -> bytes:
    """Un `.dna` MÍNIMO con el segmento de ADN, para probar el lector.

    Fixture sintético declarado: no hay ningún `.dna` en el repositorio y el formato
    está descrito, no verificado. Por eso el lector comprueba lo que lee.
    """
    cuerpo = b"\x00" + secuencia.encode("ascii")
    cabecera = (
        b"\x09" + struct.pack(">I", 14) + b"SnapGene" + b"\x00" * 6
    )
    return cabecera + b"\x00" + struct.pack(">I", len(cuerpo)) + cuerpo


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestElMontajeCorrecto(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, label="3utr:1018"
        )
        cls.montado = cls.frag.feature.paste(cls.frag.sequence)
        cls.fasta = fragmento.fragments_fasta([cls.frag], species="mouse")

    def test_el_fasta_de_la_app_se_vuelve_a_leer(self):
        emitidos = montaje.parse_fragments_fasta(self.fasta)
        self.assertEqual(len(emitidos), 1)
        self.assertEqual(emitidos[0].sequence, self.frag.sequence)

    def test_el_md5_declarado_en_la_cabecera_se_CRUZA_con_la_secuencia(self):
        emitido = montaje.parse_fragments_fasta(self.fasta)[0]
        self.assertEqual(emitido.declared["md5"], emitido.md5)

    def test_un_fasta_manipulado_a_mano_se_caza(self):
        roto = self.fasta.replace("AAGAGGTAAGG", "AAGAGGTAAGT", 1)
        with self.assertRaises(ShmirDesignError) as cm:
            montaje.parse_fragments_fasta(roto)
        self.assertIn("md5", str(cm.exception))

    def test_el_plasmido_montado_PASA_entero(self):
        informe = montaje.verify_assembly(
            self.montado, self.fasta, name="montado a mano"
        )
        self.assertIs(informe.verdict_state, FilterState.PASS)
        for resultado in informe.checks:
            self.assertIn(
                resultado.state, (FilterState.PASS, FilterState.NO_APLICA),
                f"{resultado.name}: {resultado.reason}",
            )

    def test_dice_el_md5_de_los_dos_lados(self):
        informe = montaje.verify_assembly(self.montado, self.fasta)
        texto = informe.render()
        self.assertIn(self.frag.md5, texto)

    def test_no_mira_NINGUNA_coordenada_del_casete(self):
        """Movido de sitio, el mismo intrón sigue estando: y eso es un PASE."""
        movido = "TTTTTGGGGG" * 30 + self.montado
        informe = montaje.verify_assembly(movido, self.fasta)
        self.assertIs(informe.check("fragmento_presente").state, FilterState.PASS)


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestLoQueLaComprobacionCAZA(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        cls.frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=cls.casete, label="3utr:1018"
        )
        cls.fasta = fragmento.fragments_fasta([cls.frag], species="mouse")

    def test_el_intron_VIEJO_todavia_dentro(self):
        """El caso real: se pegó al lado en vez de encima, y el vacío sigue ahí."""
        mal = self.casete[: self.frag.feature.end] + self.frag.sequence + self.casete[
            self.frag.feature.end :
        ]
        informe = montaje.verify_assembly(mal, self.fasta)
        aviso = informe.check("fragmento_unico")
        self.assertIs(aviso.state, FilterState.PASS)
        self.assertIs(informe.check("sin_intron_previo").state, FilterState.FAIL)

    def test_una_sola_base_cambiada_al_pegar(self):
        montado = self.frag.feature.paste(self.frag.sequence)
        i = montado.index(self.frag.sequence) + 100
        mutado = montado[:i] + ("A" if montado[i] != "A" else "C") + montado[i + 1 :]
        informe = montaje.verify_assembly(mutado, self.fasta)
        fallo = informe.check("fragmento_presente")
        self.assertIs(fallo.state, FilterState.FAIL)
        # Y NO se inventa la causa: dice qué encontró, no por qué.
        self.assertIn("no aparece", fallo.reason)

    def test_el_fragmento_pegado_DOS_veces(self):
        montado = self.frag.feature.paste(self.frag.sequence)
        doble = montado + self.frag.sequence
        informe = montaje.verify_assembly(doble, self.fasta)
        self.assertIs(informe.check("fragmento_unico").state, FilterState.FAIL)

    def test_un_plasmido_que_no_lo_lleva_lo_dice_SIN_diagnosticar(self):
        informe = montaje.verify_assembly("ACGT" * 500, self.fasta)
        fallo = informe.check("fragmento_presente")
        self.assertIs(fallo.state, FilterState.FAIL)
        self.assertNotIn("porque", fallo.reason.lower())


class TestLosFormatosDeEntrada(unittest.TestCase):

    def test_secuencia_pelada(self):
        self.assertEqual(montaje.plasmid_sequence("acgt\nacgt"), "ACGTACGT")

    def test_fasta(self):
        self.assertEqual(montaje.plasmid_sequence(">x\nACGT\nTTTT\n"), "ACGTTTTT")

    def test_genbank(self):
        texto = (
            "LOCUS       x  8 bp\nORIGIN\n"
            "        1 acgtttt t\n//\n"
        )
        self.assertEqual(montaje.plasmid_sequence(texto), "ACGTTTTT")

    def test_snapgene_binario(self):
        self.assertEqual(montaje.plasmid_sequence(_snapgene("ACGTACGT")), "ACGTACGT")

    def test_un_snapgene_con_la_longitud_MENTIDA_aborta(self):
        crudo = bytearray(_snapgene("ACGTACGT"))
        cuerpo = 1 + len("ACGTACGT")
        crudo[-cuerpo - 1] = 0xFF   # byte bajo de la longitud declarada del segmento
        with self.assertRaises(ShmirDesignError):
            montaje.plasmid_sequence(bytes(crudo))

    def test_un_snapgene_con_letras_que_no_son_ADN_aborta(self):
        with self.assertRaises(ShmirDesignError) as cm:
            montaje.plasmid_sequence(_snapgene("ACGTZZZZ"))
        self.assertIn("alfabeto", str(cm.exception).lower())

    def test_el_formato_esta_DECLARADO_como_no_verificado(self):
        self.assertIn("declarado", montaje.SNAPGENE_FORMAT_DECLARED.lower())


if __name__ == "__main__":
    unittest.main()
