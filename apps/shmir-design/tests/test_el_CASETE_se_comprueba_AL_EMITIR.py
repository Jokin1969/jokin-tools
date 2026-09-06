"""El casete con el que se emite tiene que ser el del depósito, y se mira ANTES.

**EL CASO (2026-09-06).** Un FASTA descargado de producción traía:

    contexto5=3133 contexto3=1955 longitud=5384
    contexto_origen=casete:md5=a9f6ac140d33f504313dc03ba7805b1f:5170nt
    estado=COMPLETO

y el casete del depósito —`aav_casete.fa`, el que había subido su autor— mide **5.282 nt**
(md5 `74f3fd79…`). Con ése, las construcciones salen de **5.496** y el flanco 3' mide
2.067. O sea: **se emitió con un casete y se validó con otro**, y la app sólo lo dijo al
subir el resultado — con la corrida de SpliceAI ya gastada.

**Lo que la cabecera SÍ hizo bien**: `contexto_origen` es lo que permitió verlo. Esa
mitigación es de la errata anterior y funciona. Lo que faltaba es que la comprobación
ocurriera **donde todavía sirve de algo**: al emitir. Un aviso después de gastar la corrida
no es una salida, es una autopsia (principio nº 47).

**Y `estado=COMPLETO` no decía nada del casete**: completo se refería al panel —cuántas
construcciones de las anunciadas salieron— y se leía como «todo en orden». Dos ejes
distintos con una sola palabra.

Regla 5: escritos antes del arreglo, con el fichero real del depósito.
"""

import hashlib
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation, specificity  # noqa: E402
from shmir_design.manifest import ROLES  # noqa: E402

#: El rol y su fichero se le PIDEN al manifiesto: escribir «aav_casete.fa» aquí sería
#: una segunda definición de la misma correspondencia (principio nº 13).
CASETE = next(r for r in ROLES if r.role == "transgen")
DEPOSITO = RAIZ / "data" / "reference" / CASETE.filename


def _secuencia(ruta: Path) -> str:
    db = specificity.load_database(str(ruta), name="casete", version="test")
    return "".join(next(iter(db.records.values())).split()).upper()


def _md5(texto: str) -> str:
    return hashlib.md5(texto.encode("ascii"), usedforsecurity=False).hexdigest()


@unittest.skipUnless(DEPOSITO.is_file(), "no está el casete versionado")
class TestElCaseteDelDepositoSeReconoce(unittest.TestCase):

    def setUp(self):
        self.deposito = _secuencia(DEPOSITO)

    def test_el_del_deposito_COINCIDE_consigo_mismo(self):
        ficha = presentation.cassette_deposit_check(
            self.deposito, directory=DEPOSITO.parent
        )
        self.assertEqual(ficha["estado"], presentation.CASETE_COINCIDE)
        self.assertEqual(ficha["md5_en_uso"], ficha["md5_deposito"])
        self.assertEqual(ficha["nt_en_uso"], len(self.deposito))

    def test_OTRO_casete_NO_coincide_y_lo_dice_con_los_dos_md5(self):
        """El caso real: mismo flanco 5', 112 nt menos por el 3'."""
        otro = self.deposito[:len(self.deposito) - 112]
        ficha = presentation.cassette_deposit_check(otro, directory=DEPOSITO.parent)
        self.assertEqual(ficha["estado"], presentation.CASETE_NO_COINCIDE)
        self.assertEqual(ficha["nt_en_uso"], len(self.deposito) - 112)
        self.assertEqual(ficha["nt_deposito"], len(self.deposito))
        # Los DOS md5 en el motivo: sin ellos, «no coincide» no se puede investigar.
        self.assertIn(_md5(otro)[:8], ficha["motivo"])
        self.assertIn(_md5(self.deposito)[:8], ficha["motivo"])
        self.assertIn(CASETE.filename, ficha["motivo"])

    def test_y_la_diferencia_de_longitud_va_en_el_motivo(self):
        otro = self.deposito[:len(self.deposito) - 112]
        motivo = presentation.cassette_deposit_check(
            otro, directory=DEPOSITO.parent
        )["motivo"]
        self.assertIn("5170", motivo)
        self.assertIn(str(len(self.deposito)), motivo)


class TestSinCaseteNoSeINVENTA_UN_VERDICTO(unittest.TestCase):
    """NOT_RUN no es COINCIDE: no haber podido comprobar no es haber comprobado."""

    def test_sin_casete_en_la_mano_es_NOT_RUN(self):
        ficha = presentation.cassette_deposit_check(None, directory=DEPOSITO.parent)
        self.assertEqual(ficha["estado"], presentation.CASETE_SIN_COMPROBAR)
        self.assertTrue(ficha["motivo"].strip())

    def test_sin_fichero_en_el_deposito_TAMBIEN_es_NOT_RUN(self):
        import tempfile

        with tempfile.TemporaryDirectory() as vacio:
            ficha = presentation.cassette_deposit_check("ACGT", directory=Path(vacio))
        self.assertEqual(ficha["estado"], presentation.CASETE_SIN_COMPROBAR)
        self.assertIn(CASETE.filename, ficha["motivo"])

    def test_los_tres_estados_son_DISTINTOS(self):
        estados = {
            presentation.CASETE_COINCIDE,
            presentation.CASETE_NO_COINCIDE,
            presentation.CASETE_SIN_COMPROBAR,
        }
        self.assertEqual(len(estados), 3)


@unittest.skipUnless(DEPOSITO.is_file(), "no está el casete versionado")
class TestElEstadoVIAJA_EN_EL_FASTA(unittest.TestCase):
    """`estado=COMPLETO` hablaba del PANEL. El casete es otro eje y va aparte."""

    def test_la_cabecera_declara_el_estado_del_casete(self):
        from shmir_design.spliceai import Construction

        construccion = Construction(
            name="mvm_actual__3utr959", candidate_start=959, intron="mvm_actual",
            sequence="ACGT" * 10, md5="da", context_5=3133, context_3=1955,
            donor_position=10, acceptor_position=20, cryptic_position=0,
            context_source="casete:md5=abc:5170nt",
            cassette_check=presentation.CASETE_NO_COINCIDE,
        )
        texto = presentation.splice_query_text([construccion])
        self.assertIn(f"casete_del_deposito={presentation.CASETE_NO_COINCIDE}", texto)

    def test_y_sin_comprobar_TAMBIEN_se_declara(self):
        """El silencio se leería como «coincide», que es justo lo que pasó."""
        from shmir_design.spliceai import Construction

        construccion = Construction(
            name="mvm_actual__3utr959", candidate_start=959, intron="mvm_actual",
            sequence="ACGT" * 10, md5="da", context_5=5, context_3=5,
            donor_position=10, acceptor_position=20, cryptic_position=0,
        )
        texto = presentation.splice_query_text([construccion])
        self.assertIn(
            f"casete_del_deposito={presentation.CASETE_SIN_COMPROBAR}", texto
        )


if __name__ == "__main__":
    unittest.main()
