"""Qué ficheros del depósito NO son los versionados. La pregunta que abrió el casete.

**De dónde sale.** De la errata nº 129. El casete con el que se emitía no era el del
depósito, y lo que permitía que eso viviera indefinidamente sin dar un solo error es que
**las dos comprobaciones que había eran autoconsistentes**: la siembra respeta lo que ya
está —a propósito, para no pisar lo subido— y el rol valida el fichero contra el md5 del
**propio manifiesto del volumen**. Ninguna de las dos mira lo versionado. Con las palabras
del responsable del proyecto:

    «La siembra respeta lo que está, el rol valida contra el manifiesto del volumen, y
    nadie compara el depósito con lo versionado. Los dos autoconsistentes, el desajuste
    invisible por construcción.»

Y la pregunta que salió de ahí, que es la que contesta esta comparación:

    «Si el depósito puede tener un fichero distinto del versionado sin que nada lo diga,
    ¿pasa con los otros?»

**INFORME, no guardia.** Un fichero del depósito distinto del versionado **no es un
fallo**: subir uno más nuevo por el gestor es exactamente para lo que existe el depósito.
Lo que no puede ser es que no se vea. El número correcto NO es cero.

**Lo que NO puede decir, declarado**: en local los dos directorios son EL MISMO
(`SHMIR_REFERENCE_DIR` sin declarar), así que no hay nada que comparar y lo dice —
`MISMO_DIRECTORIO`— en vez de devolver «todos iguales», que sería un verde sin haber
mirado (principio nº 51).

Regla 5: escritos antes.
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402
from shmir_design.manifest import ROLES  # noqa: E402
from shmir_design.reference import PACKAGE_REFERENCE_DIR  # noqa: E402

#: El casete, y un rol cuyo fichero NO está versionado. Los dos DERIVADOS del registro:
#: teclear «aav_casete.fa» o «apa_medido.tsv» sería escribir una clave que alguien
#: produce, y entonces este test no podría fallar el día que el rol apunte a otro
#: fichero (principio nº 25 y errata nº 42).
CASETE = next(r for r in ROLES if r.role == "transgen").filename
SOLO_SUBIDO = next(
    r.filename for r in ROLES
    if not (PACKAGE_REFERENCE_DIR / r.filename).exists()
)
#: Un fichero versionado que NO es un FASTA, para el caso «no se inventa una respuesta».
NO_ES_FASTA = next(
    p.name for p in sorted(PACKAGE_REFERENCE_DIR.iterdir())
    if p.is_file() and p.suffix == ".out"
)


class TestEnLocalNoHayNadaQueComparar(unittest.TestCase):

    def test_el_mismo_directorio_se_DICE_no_se_da_por_bueno(self):
        informe = presentation.deposit_vs_versioned(
            directory=PACKAGE_REFERENCE_DIR
        )
        self.assertEqual(informe["estado"], presentation.DEPOSITO_MISMO_DIRECTORIO)
        self.assertEqual(informe["filas"], [])
        self.assertIn("mismo", informe["motivo"].lower())


class TestConDosDirectoriosDISTINTOS(unittest.TestCase):

    def _informe(self, ficheros: dict[str, bytes]):
        with tempfile.TemporaryDirectory() as deposito:
            for nombre, datos in ficheros.items():
                (Path(deposito) / nombre).write_bytes(datos)
            return presentation.deposit_vs_versioned(directory=Path(deposito))

    def test_un_fichero_IGUAL_al_versionado_sale_IGUAL(self):
        nombre = CASETE
        datos = (PACKAGE_REFERENCE_DIR / nombre).read_bytes()
        informe = self._informe({nombre: datos})
        fila = next(f for f in informe["filas"] if f["fichero"] == nombre)
        self.assertEqual(fila["estado"], presentation.DEPOSITO_IGUAL)

    def test_uno_DISTINTO_sale_distinto_y_con_las_dos_longitudes(self):
        nombre = CASETE
        datos = (PACKAGE_REFERENCE_DIR / nombre).read_bytes()
        informe = self._informe({nombre: datos[:-200]})
        fila = next(f for f in informe["filas"] if f["fichero"] == nombre)
        self.assertEqual(fila["estado"], presentation.DEPOSITO_DISTINTO)
        self.assertNotEqual(fila["md5_deposito"], fila["md5_versionado"])
        self.assertLess(fila["bytes_deposito"], fila["bytes_versionado"])

    def test_el_que_solo_esta_en_el_DEPOSITO_se_ve(self):
        """Lo subido que no tiene versionado: no es un fallo, pero tiene que verse."""
        informe = self._informe({SOLO_SUBIDO: b"pos\tfrac\tnombre\n1\t0.5\tx\n"})
        fila = next(f for f in informe["filas"] if f["fichero"] == SOLO_SUBIDO)
        self.assertEqual(fila["estado"], presentation.DEPOSITO_SOLO_DEPOSITO)

    def test_el_que_solo_esta_VERSIONADO_tambien(self):
        """Es lo que la siembra copiaría; verlo distingue «no sembrado» de «igual»."""
        informe = self._informe({})
        self.assertTrue(informe["filas"])
        self.assertTrue(
            all(f["estado"] == presentation.DEPOSITO_SOLO_VERSIONADO
                for f in informe["filas"]),
            informe["filas"][:3],
        )

    def test_el_manifiesto_NO_cuenta_como_desajuste(self):
        """El del depósito se reescribe al subir: que difiera es lo normal."""
        informe = self._informe({"manifest.tsv": b"cualquier cosa\n"})
        self.assertNotIn(
            "manifest.tsv", [f["fichero"] for f in informe["filas"]]
        )


class TestDistingueOTRA_MOLECULA_DE_OTRO_FORMATO(unittest.TestCase):
    """El casete se declaró «otra molécula» porque el md5 de la SECUENCIA cambiaba.

    Un FASTA reenvuelto a otro ancho tiene otro md5 de fichero y la MISMA secuencia. Sin
    esta distinción, un reformateo se leería igual que un plásmido distinto — y esa es la
    diferencia entre «hay que reemplazarlo» y «da igual».
    """

    def _con(self, contenido: bytes):
        with tempfile.TemporaryDirectory() as deposito:
            (Path(deposito) / CASETE).write_bytes(contenido)
            informe = presentation.deposit_vs_versioned(directory=Path(deposito))
        return next(f for f in informe["filas"] if f["fichero"] == CASETE)

    def test_reenvuelto_a_otro_ancho_dice_que_la_SECUENCIA_es_la_misma(self):
        texto = (PACKAGE_REFERENCE_DIR / CASETE).read_text(encoding="utf-8")
        cabecera, _, cuerpo = texto.partition("\n")
        sec = "".join(cuerpo.split())
        reenvuelto = cabecera + "\n" + "\n".join(
            sec[i:i + 60] for i in range(0, len(sec), 60)
        ) + "\n"
        fila = self._con(reenvuelto.encode())
        self.assertEqual(fila["estado"], presentation.DEPOSITO_DISTINTO)
        self.assertIs(fila["misma_secuencia"], True)

    def test_y_una_secuencia_distinta_dice_que_NO(self):
        texto = (PACKAGE_REFERENCE_DIR / CASETE).read_text(encoding="utf-8")
        cabecera, _, cuerpo = texto.partition("\n")
        sec = "".join(cuerpo.split())[:-112]      # el caso real: 112 nt menos
        recortado = cabecera + "\n" + sec + "\n"
        fila = self._con(recortado.encode())
        self.assertEqual(fila["estado"], presentation.DEPOSITO_DISTINTO)
        self.assertIs(fila["misma_secuencia"], False)

    def test_para_lo_que_NO_es_FASTA_no_se_inventa_una_respuesta(self):
        # Con el fichero REAL, cambiado por el final: fabricar un `.out` de mentira
        # probaría el detector sobre algo que no se parece a lo que va a leer.
        real = (PACKAGE_REFERENCE_DIR / NO_ES_FASTA).read_bytes()
        with tempfile.TemporaryDirectory() as deposito:
            (Path(deposito) / NO_ES_FASTA).write_bytes(real + b"# una linea mas\n")
            informe = presentation.deposit_vs_versioned(directory=Path(deposito))
        fila = next(f for f in informe["filas"] if f["fichero"] == NO_ES_FASTA)
        self.assertEqual(fila["estado"], presentation.DEPOSITO_DISTINTO)
        self.assertIsNone(fila["misma_secuencia"])


class TestEsUnINFORME_y_lo_dice(unittest.TestCase):

    def test_un_fichero_distinto_NO_es_un_fallo(self):
        self.assertIn("no es un fallo", presentation.WHY_THE_DEPOSIT_MAY_DIFFER.lower())

    def test_y_el_motivo_de_que_nadie_lo_mirara_esta_escrito(self):
        texto = presentation.WHY_NOBODY_COMPARED
        self.assertIn("autoconsistente", texto.lower())
        self.assertIn("manifiesto", texto.lower())


if __name__ == "__main__":
    unittest.main()
