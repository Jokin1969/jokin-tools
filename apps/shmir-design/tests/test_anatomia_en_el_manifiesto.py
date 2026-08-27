"""La anatomía de cada transcrito, registrada en el manifiesto y atada a `REFERENCES`.

El manifiesto registraba los FICHEROS —nombre, tamaño, md5, accession, longitud— y la
anatomía vivía solo en `reference.REFERENCES`. Eso dejaba dos cosas mal:

  - añadir una tercera especie era EDITAR CÓDIGO, aunque su fichero entrara por el
    gestor como cualquier otro;
  - la frontera del 3'UTR —de la que cuelgan los tercios, la región de cada ventana y
    la distancia de cada señal de polyA al extremo— no tenía ninguna línea que la
    registrara, así que un veredicto de hace tres meses no se podía auditar sin la
    versión del código con la que se sacó.

Ahora está en las dos partes, y eso SOLO es admisible si algo obliga a que coincidan:
dos definiciones del mismo dato que nada cruza son el patrón que este proyecto ya se ha
encontrado cuatro veces (`ceiling_layers`, `verdict_state`, `analyze_3utr`, los dos
montadores del módulo). Estos tests son ese cruce, en las dos direcciones.
"""

import unittest
from pathlib import Path

from shmir_design.manifest import MANIFEST_COLUMNS, MANIFEST_NAME, entry_row, load_manifest
from shmir_design.reference import REFERENCES

DIRECTORIO = Path(__file__).resolve().parent.parent / "data" / "reference"

#: Qué fichero describe la anatomía de qué transcrito. El `.fa` y el `.gb` describen LA
#: MISMA: el `.gb` es de donde sale, y si discreparan uno de los dos estaría mal.
POR_FICHERO = {
    "NM_011170.3.fa": "NM_011170.3",
    "NM_011170.3.gb": "NM_011170.3",
    "NM_000311.5.fa": "NM_000311.5",
    "NM_000311.5.gb": "NM_000311.5",
}


class TestElManifiestoLlevaLaAnatomia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manifiesto = load_manifest(DIRECTORIO / MANIFEST_NAME)

    def test_cada_transcrito_declara_su_CDS_y_sus_dos_md5_canonicos(self):
        for fichero, accession in POR_FICHERO.items():
            with self.subTest(fichero=fichero):
                entrada = self.manifiesto.entry(fichero)
                referencia = REFERENCES[accession]
                self.assertEqual(entrada.cds, referencia.cds)
                self.assertEqual(entrada.sequence_md5, referencia.md5)
                self.assertEqual(entrada.utr3_md5, referencia.utr3_md5)

    def test_el_fa_y_el_gb_del_mismo_transcrito_dicen_LO_MISMO(self):
        # Si discreparan, uno de los dos ficheros no es del transcrito que dice ser — y
        # eso no daria ningun error, solo una anatomia distinta segun cual se cargara.
        for accession in ("NM_011170.3", "NM_000311.5"):
            with self.subTest(accession=accession):
                fa = self.manifiesto.entry(f"{accession}.fa")
                gb = self.manifiesto.entry(f"{accession}.gb")
                self.assertEqual(fa.cds, gb.cds)
                self.assertEqual(fa.sequence_md5, gb.sequence_md5)
                self.assertEqual(fa.utr3_md5, gb.utr3_md5)

    def test_TODA_referencia_declarada_tiene_su_linea_con_anatomia(self):
        # La direccion que faltaria si solo se comprobara la anterior: añadir una
        # especie a `REFERENCES` y olvidar el manifiesto.
        registradas = {
            e.accession for e in self.manifiesto.entries if e.cds is not None
        }
        self.assertEqual(registradas, set(REFERENCES))

    def test_los_TRES_md5_de_una_fila_son_DISTINTOS(self):
        # El del fichero en disco, el de la secuencia canonica y el del 3'UTR. Copiar
        # uno en el sitio de otro hace que el fichero bueno se rechace, y la unica señal
        # seria un rechazo que parece un fichero corrupto.
        for fichero in POR_FICHERO:
            with self.subTest(fichero=fichero):
                e = self.manifiesto.entry(fichero)
                self.assertEqual(len({e.md5, e.sequence_md5, e.utr3_md5}), 3)

    def test_lo_que_NO_es_un_transcrito_lleva_la_anatomia_VACIA(self):
        # Vacio significa NO REGISTRADO. Un `0..0` o un md5 de relleno serian un dato.
        for nombre in ("mature.fa", "rmsk_mouse.out", "aav_casete.fa"):
            with self.subTest(fichero=nombre):
                entrada = self.manifiesto.entry(nombre)
                self.assertIsNone(entrada.cds)
                self.assertEqual(entrada.sequence_md5, "")
                self.assertEqual(entrada.utr3_md5, "")


class TestLaFilaNoSeDescuadra(unittest.TestCase):

    def test_entry_row_escribe_TANTOS_campos_como_columnas(self):
        entrada = load_manifest(DIRECTORIO / MANIFEST_NAME).entry("NM_011170.3.fa")
        self.assertEqual(len(entry_row(entrada).split("\t")), len(MANIFEST_COLUMNS))

    def test_la_fila_reescrita_vuelve_a_leerse_igual(self):
        # Ida y vuelta: si `entry_row` se dejara una columna, el md5 del 3'UTR acabaria
        # leyendose en la columna de al lado sin dar ningun error.
        original = load_manifest(DIRECTORIO / MANIFEST_NAME).entry("NM_000311.5.fa")
        texto = "\t".join(MANIFEST_COLUMNS) + "\n" + entry_row(original) + "\n"
        from shmir_design.manifest import parse_manifest

        vuelta = parse_manifest(texto, source="<ida y vuelta>").entry("NM_000311.5.fa")
        self.assertEqual(vuelta.cds, original.cds)
        self.assertEqual(vuelta.sequence_md5, original.sequence_md5)
        self.assertEqual(vuelta.utr3_md5, original.utr3_md5)


if __name__ == "__main__":
    unittest.main()
