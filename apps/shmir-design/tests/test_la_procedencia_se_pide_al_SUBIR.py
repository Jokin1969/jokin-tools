"""La procedencia de una TABLA es del FICHERO, y se pide UNA VEZ: al subirlo.

**Pedido con el modal delante (2026-09-02)**: el de carga de off-targets pedia los seis
campos de procedencia —fuente, ensamblaje, tabla, fecha de la tabla, representante y
version— **en cada corrida**, siendo un dato del fichero que el deposito ya tenia. Dos
copias del mismo dato acaban divergiendo y nadie sabe cual manda; o eso, o el modal se
las inventa.

**Y LA CONDICION QUE ORDENA ESTE FICHERO, con las palabras con que se pidio**: si
`offtarget.Provenance` las exige para dar veredicto, un fichero sin ellas **no puede
entrar al deposito** y bloquear el frente tres pantallas despues sin decir por que. El
rechazo va DONDE ENTRA EL FICHERO, con el motivo — no tres pantallas mas alla.

Regla 5: escritos antes.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import deposito, manifest, offtarget, presentation, species
from shmir_design.errors import ShmirDesignError

#: El fichero de UCSC, con la forma REAL que produce «3' UTR Exons» — un registro por
#: exon, asi que el mismo accession sale repetido. Se IMPORTA del test que lo trajo
#: (errata nº 58) en vez de volver a escribirlo: dos copias del mismo fixture divergen
#: igual que dos copias de un dato.
from tests.test_el_transcriptoma_ENTRA import UCSC

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
TRANSCRIPTOMA = "transcriptoma_3utr.fa"

#: Los cuatro, con valores de la ruta que la propia ficha manda seguir.
PROCEDENCIA = {
    "assembly": "mm39",
    "table": "NCBI RefSeq — 3' UTR Exons",
    "table_date": "2026-09-01",
    "representative": "todas las isoformas, sin filtrar",
}


class _ConDeposito(unittest.TestCase):
    """Copia del manifiesto real en un temporal: no se toca el del repositorio."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "reference"
        self.dir.mkdir()
        (self.dir / manifest.MANIFEST_NAME).write_text(
            (DATOS / manifest.MANIFEST_NAME).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def _subir(self, nombre, crudo, **extra):
        return deposito.accept_upload(
            self.dir, filename=nombre, payload=crudo,
            species=species.resolve("raton"), origin="UCSC Table Browser",
            date="2026-09-01", **extra,
        )


class TestElRECHAZO_vaEnLaSubida(_ConDeposito):
    """Sin los cuatro campos el fichero NO entra, y el motivo va en la subida."""

    def test_sin_procedencia_se_RECHAZA(self):
        with self.assertRaises(ShmirDesignError):
            self._subir(TRANSCRIPTOMA, UCSC.encode("utf-8"))

    def test_y_NO_se_escribe_nada(self):
        # Un fichero escrito y luego rechazado deja el directorio con algo que la
        # siguiente comprobacion cuenta como presente.
        antes = (self.dir / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
        with self.assertRaises(ShmirDesignError):
            self._subir(TRANSCRIPTOMA, UCSC.encode("utf-8"))
        self.assertFalse((self.dir / TRANSCRIPTOMA).exists())
        self.assertFalse((self.dir / f".{TRANSCRIPTOMA}.subiendo").exists())
        self.assertEqual(
            (self.dir / manifest.MANIFEST_NAME).read_text(encoding="utf-8"), antes
        )

    def test_el_motivo_NOMBRA_los_campos_que_faltan(self):
        with self.assertRaises(ShmirDesignError) as caja:
            self._subir(TRANSCRIPTOMA, UCSC.encode("utf-8"), assembly="mm39")
        # La LISTA de lo que falta, no la explicacion de despues: ahi «ensamblaje»
        # aparece igual, y confundirlas dejaria pasar un mensaje que pide un campo ya
        # dado.
        lista = str(caja.exception).split("Falta la procedencia de la tabla:")[1]
        lista = lista.split(".")[0]
        self.assertEqual(
            [c.strip() for c in lista.split(",")],
            ["tabla", "fecha_tabla", "representante"],
        )

    def test_y_DICE_por_que_se_rechaza_aqui_y_no_despues(self):
        with self.assertRaises(ShmirDesignError) as caja:
            self._subir(TRANSCRIPTOMA, UCSC.encode("utf-8"))
        texto = str(caja.exception).lower()
        self.assertIn("reproducible", texto)
        self.assertIn("veredicto", texto)

    def test_un_campo_EN_BLANCO_no_cuenta_como_dado(self):
        # Control adversario del «obligatorias, no opcionales con casilla vacia»: una
        # casilla que se deja en blanco tiene que doler lo mismo que no ponerla.
        with self.assertRaises(ShmirDesignError):
            self._subir(
                TRANSCRIPTOMA, UCSC.encode("utf-8"), **{**PROCEDENCIA, "table_date": "   "}
            )


class TestConLosCuatro_ENTRA(_ConDeposito):

    def test_el_fichero_se_ESCRIBE(self):
        self._subir(TRANSCRIPTOMA, UCSC.encode("utf-8"), **PROCEDENCIA)
        self.assertTrue((self.dir / TRANSCRIPTOMA).is_file())

    def test_y_los_cuatro_QUEDAN_en_el_manifiesto(self):
        self._subir(TRANSCRIPTOMA, UCSC.encode("utf-8"), **PROCEDENCIA)
        entrada = manifest.load_manifest(
            self.dir / manifest.MANIFEST_NAME
        ).entry(TRANSCRIPTOMA)
        self.assertEqual(entrada.assembly, PROCEDENCIA["assembly"])
        self.assertEqual(entrada.table, PROCEDENCIA["table"])
        self.assertEqual(entrada.table_date, PROCEDENCIA["table_date"])
        self.assertEqual(entrada.representative, PROCEDENCIA["representative"])

    def test_y_se_leen_de_vuelta_TAL_CUAL_del_texto(self):
        # El manifiesto sigue siendo texto y sigue versionado: lo que se sube por la
        # interfaz se ve en el `git diff` igual que si se editara a mano.
        self._subir(TRANSCRIPTOMA, UCSC.encode("utf-8"), **PROCEDENCIA)
        texto = (self.dir / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
        fila = [l for l in texto.splitlines() if l.startswith(f"{TRANSCRIPTOMA}\t")]
        self.assertEqual(len(fila), 1)
        self.assertTrue(fila[0].endswith("\t".join(PROCEDENCIA.values())))


class TestLosDEMAS_no_los_piden(_ConDeposito):
    """Un casete de AAV no sale de ninguna tabla: ahi el hueco vacio es la VERDAD."""

    def test_el_casete_entra_SIN_procedencia_de_tabla(self):
        resultado = self._subir(
            "aav_casete.fa", (DATOS / "aav_casete.fa").read_bytes()
        )
        self.assertEqual(resultado.role, "transgen")

    def test_y_su_linea_las_deja_VACIAS(self):
        self._subir("aav_casete.fa", (DATOS / "aav_casete.fa").read_bytes())
        entrada = manifest.load_manifest(
            self.dir / manifest.MANIFEST_NAME
        ).entry("aav_casete.fa")
        self.assertEqual(
            (entrada.assembly, entrada.table, entrada.table_date, entrada.representative),
            ("", "", "", ""),
        )


class TestLaExigenciaSaleDeQUIEN_LA_USA(unittest.TestCase):
    """No es una lista de campos elegida aqui: son los de `offtarget.Provenance`."""

    def test_los_cuatro_son_campos_de_Provenance(self):
        campos = set(offtarget.Provenance.__dataclass_fields__)
        self.assertTrue(set(deposito.PROVENANCE_FIELDS) <= campos)

    def test_los_otros_tres_de_Provenance_YA_los_tenia_el_manifiesto(self):
        # `source` es el origen, `version` sale de la fecha y `md5` se calcula del
        # fichero. Si faltara alguno, esta lista de cuatro seria incompleta y el modal
        # tendria que seguir preguntando.
        faltan = set(offtarget.Provenance.__dataclass_fields__) - set(
            deposito.PROVENANCE_FIELDS
        )
        self.assertEqual(faltan, {"source", "version", "md5"})

    def test_las_cuatro_columnas_del_manifiesto_son_ESTAS_y_en_este_orden(self):
        self.assertEqual(
            tuple(deposito.MANIFEST_COLUMN_FOR[c] for c in deposito.PROVENANCE_FIELDS),
            manifest.MANIFEST_COLUMNS[-4:],
        )

    def test_el_rol_que_las_exige_esta_DECLARADO_con_motivo(self):
        self.assertIn("transcriptoma", deposito.PROVENANCE_REQUIRED)
        for rol, motivo in deposito.PROVENANCE_REQUIRED.items():
            with self.subTest(rol):
                self.assertIn(rol, deposito.VALIDATORS)
                self.assertTrue(motivo.strip())


class TestLaPAGINA_pide_los_campos_que_toquen(unittest.TestCase):
    """Regla 6: que casillas pintar lo decide `presentation`, no la pagina."""

    def _fila(self, nombre):
        filas = presentation.reference_manager_rows("raton", directory=DATOS)
        return next(f for f in filas if f["nombre"] == nombre)

    def test_la_fila_del_transcriptoma_TRAE_las_cuatro(self):
        campos = [c["clave"] for c in self._fila(TRANSCRIPTOMA)["procedencia"]]
        self.assertEqual(campos, list(deposito.PROVENANCE_FIELDS))

    def test_cada_una_con_su_etiqueta_y_su_ayuda(self):
        for campo in self._fila(TRANSCRIPTOMA)["procedencia"]:
            with self.subTest(campo["clave"]):
                self.assertTrue(campo["etiqueta"].strip())
                self.assertTrue(campo["ayuda"].strip())

    def test_y_la_del_casete_NO_pide_ninguna(self):
        self.assertEqual(self._fila("aav_casete.fa")["procedencia"], [])


class TestLaPAGINA_las_PINTA_y_no_las_elige(unittest.TestCase):
    """El texto de la pagina: las casillas salen de la fila, no escritas ahi."""

    def setUp(self):
        self.fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")

    def test_las_saca_de_la_fila(self):
        self.assertIn("_casillas_de_procedencia", self.fuente)
        self.assertIn('fila.get("procedencia")', self.fuente)

    def test_y_NO_escribe_ni_uno_de_los_cuatro_campos(self):
        # Escribirlos en la pagina seria la tercera copia de la misma lista —la de
        # `Provenance`, la del manifiesto y esta—, y las copias envejecen cada una por
        # su cuenta (errata nº 28).
        for campo in deposito.PROVENANCE_FIELDS:
            with self.subTest(campo):
                self.assertNotIn(f'"{campo}"', self.fuente)
        for columna in deposito.MANIFEST_COLUMN_FOR.values():
            with self.subTest(columna):
                self.assertNotIn(f'"{columna}"', self.fuente)

    def test_y_las_pasa_a_la_subida(self):
        # Las TRES vias por las que un fichero entra: la fila ausente del gestor, el
        # reemplazo, y el modal de off-targets cuando el catalogo no esta. Ninguna puede
        # quedarse sin pasarlas: seria la que deja entrar un fichero sin procedencia.
        self.assertEqual(self.fuente.count("**procedencia,"), 3)


if __name__ == "__main__":
    unittest.main()
