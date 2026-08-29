"""Ninguna constante se apoya en un fichero RETIRADO. Sobre todas, no sólo sobre una.

EL CASO. `external_score.EVIDENCE` registra la DIRECCIÓN de la escala de miRarchitect —si
menor es mejor— con los pares (puesto, score) de los que salió. Esos cinco pares estaban
transcritos a mano, y al derivarlos del fichero se vio que **no eran del fichero que la
constante decía**: cuadran con `mirarchitect_prnp_raton.tsv`, que el manifiesto marca
«NO USAR» porque se puntuó sobre el 3'UTR FABRICADO de 1246 nt — la errata nº 5.

Lo que eso significa, y es lo que hace falta un test y no una corrección: `lower_is_better()`
existe justo para impedir que se ordene por un score de dirección desconocida y se manden
a síntesis los peores. **La contramedida contra el peor fallo del proyecto estaba apoyada
en el dato que ese mismo fallo retiró.** La dirección no cambió por suerte: si la corrida
retirada hubiera venido al revés, hoy tendríamos la dirección invertida, con cinco pares
de aval, un test verde y `lower_is_better()` aprobando.

Un fichero retirado NO se retira solo de las constantes que lo citan. Por eso esto barre
`shmir_design/` y `tools/` ENTEROS, y la lista de retirados se DERIVA del manifiesto: si
mañana se retira otro, este test lo cubre sin que nadie lo añada.
"""

import ast
import unittest
from pathlib import Path

from shmir_design.manifest import MANIFEST_NAME, load_manifest

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIA = RAIZ / "data" / "reference"

#: CÓMO se puede nombrar un fichero retirado: diciendo, EN EL MISMO LITERAL, que lo
#: está. No es una lista de módulos exentos — una exención por módulo habría dejado
#: ciego justo al módulo que motivó este test — sino una regla que se cumple sola:
#: quien escribe el nombre tiene que escribir al lado por qué no se usa.
#:
#: Un fixture negativo se nombra a propósito (es evidencia, y borrarlo sería perderla);
#: lo que no puede pasar es nombrarlo COMO SI FUERA una fuente viva.
MARCAS_DE_RETIRADA = ("NO USAR", "FIXTURE NEGATIVO", "RETIRAD", "FABRICAD",
                      "ERRATA", "BIBLIOTECA EQUIVOCADA")


def _retirados() -> dict[str, str]:
    """Los ficheros retirados y por qué, LEÍDOS del manifiesto. No se teclean."""
    manifiesto = load_manifest(REFERENCIA / MANIFEST_NAME)
    fuera = {}
    for entrada in manifiesto.entries:
        texto = f"{entrada.origin} {entrada.filter_name}".upper()
        if "NO USAR" in texto or "FIXTURE NEGATIVO" in texto:
            fuera[entrada.name] = entrada.origin
    return fuera


def _fuentes():
    for carpeta in ("shmir_design", "tools"):
        yield from sorted((RAIZ / carpeta).glob("*.py"))


class TestLosRetiradosSeDERIVANDelManifiesto(unittest.TestCase):

    def test_hay_retirados_y_se_leen_del_manifiesto(self):
        # Si esto saliera vacío, el resto de la suite pasaría sin comprobar nada.
        fuera = _retirados()
        self.assertGreaterEqual(len(fuera), 4)
        self.assertIn("mirarchitect_prnp_raton.tsv", fuera)
        self.assertIn("prnp_3utr_fabricado_1246nt.txt", fuera)

    def test_cada_uno_dice_POR_QUE_esta_retirado(self):
        for nombre, motivo in _retirados().items():
            with self.subTest(fichero=nombre):
                self.assertTrue(motivo.strip(), nombre)


class TestNingunaConstanteLosCITA(unittest.TestCase):
    """Una constante que cita un fichero se DERIVA de él. Si el fichero está retirado,
    lo que se derive de él está retirado también — y eso no se ve leyendo la constante."""

    def test_ningun_modulo_nombra_un_fichero_retirado(self):
        fuera = _retirados()
        hallazgos = []
        for ruta in _fuentes():
            arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
            for nodo in ast.walk(arbol):
                if not (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)):
                    continue
                texto = nodo.value.upper()
                if any(m in texto for m in MARCAS_DE_RETIRADA):
                    continue
                for nombre in fuera:
                    if nombre in nodo.value:
                        hallazgos.append(f"{ruta.name}:{nodo.lineno} → {nombre}")
        self.assertEqual(
            hallazgos, [],
            "Hay código que nombra un fichero RETIRADO sin decir que lo está. Si lo usa "
            "como fuente, lo que salga de ahí hereda el motivo por el que se retiró; si "
            "sólo lo menciona, dilo en el mismo texto — quien lo lea tiene que ver las "
            "dos cosas a la vez.",
        )

    def test_la_regla_MUERDE_cuando_falta_la_marca(self):
        """La mitad sin la que «no encuentra nada» y «no mira» son lo mismo."""
        fuera = next(iter(_retirados()))
        codigo = f'RUTA = "data/reference/{fuera}"\n'
        arbol = ast.parse(codigo)
        literales = [
            n.value for n in ast.walk(arbol)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        marcado = [
            v for v in literales
            if not any(m in v.upper() for m in MARCAS_DE_RETIRADA) and fuera in v
        ]
        self.assertEqual(len(marcado), 1)

    def test_y_CALLA_cuando_la_marca_esta(self):
        fuera = next(iter(_retirados()))
        texto = f"{fuera} — NO USAR, es un FIXTURE NEGATIVO."
        self.assertTrue(any(m in texto.upper() for m in MARCAS_DE_RETIRADA))


class TestElAnclaDeLaEvidencia(unittest.TestCase):
    """El caso concreto, fijado: de dónde sale la dirección de la escala."""

    def test_el_ancla_declarada_NO_esta_retirada(self):
        from shmir_design.external_score import MANUAL_EVIDENCE_FILE

        self.assertNotIn(MANUAL_EVIDENCE_FILE, _retirados())

    def test_y_esta_en_el_manifiesto_con_md5(self):
        from shmir_design.external_score import MANUAL_EVIDENCE_FILE

        entrada = load_manifest(REFERENCIA / MANIFEST_NAME).entry(MANUAL_EVIDENCE_FILE)
        self.assertEqual(len(entrada.md5), 32)

    def test_lower_is_better_sigue_diciendo_lo_mismo(self):
        # La dirección NO cambió al corregir el ancla, y eso es SUERTE: los tres
        # ficheros vienen crecientes. Se fija para que se vea que lo que cambió fue de
        # dónde sale la evidencia, no qué dice.
        from shmir_design.external_score import ScoreSource, lower_is_better

        self.assertTrue(lower_is_better(ScoreSource.MANUAL_MIRARCHITECT))


class TestLosOtrosDosFixturesNegativos(unittest.TestCase):
    """Y se dice CÓMO se buscó, no sólo que no se encontró nada.

    «No hay nada anclado a ellos» sin decir con qué se miró es la misma frase que el
    «Alu 0 %» obtenido sin buscar Alu. Aquí van las dos búsquedas, escritas, para que la
    próxima vez no haya que fiarse de que alguien miró.
    """

    @staticmethod
    def _cadena(nombre: str) -> str:
        texto = (REFERENCIA / nombre).read_text(encoding="utf-8")
        return "".join(
            l for l in texto.splitlines() if not l.startswith(">")
        ).replace(" ", "").upper()

    @staticmethod
    def _literales_de_adn():
        import re

        adn = re.compile(r"^[ACGT]{8,}$")
        for carpeta in ("shmir_design", "tools"):
            for ruta in sorted((RAIZ / carpeta).glob("*.py")):
                arbol = ast.parse(ruta.read_text(encoding="utf-8"))
                for nodo in ast.walk(arbol):
                    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                        valor = nodo.value.strip().upper()
                        if adn.match(valor):
                            yield ruta.name, nodo.lineno, valor

    def test_ningun_literal_de_ADN_sale_del_3utr_FABRICADO(self):
        """El fixture negativo de la errata nº 5, buscado POR SECUENCIA.

        Un número anclado a él no se distingue de uno bueno —comparten casi todo— pero
        una SUBCADENA que esté en el fabricado y no en ninguna referencia verdadera sólo
        puede venir de ahí. Es la misma lógica del anclaje de PolyA_DB: se exige que
        aterrice en el sitio bueno, no que no aterrice en el malo.
        """
        fabricado = self._cadena("prnp_3utr_fabricado_1246nt.txt")
        verdaderas = [
            self._cadena("NM_011170.3.fa"), self._cadena("NM_000311.5.fa"),
        ]
        culpables = [
            (m, n, v) for m, n, v in self._literales_de_adn()
            if v in fabricado and not any(v in r for r in verdaderas)
        ]
        self.assertEqual(culpables, [])

    def test_y_la_busqueda_ENCUENTRA_algo_cuando_lo_hay(self):
        # Sin esto, «cero culpables» y «la búsqueda no mira» son el mismo resultado.
        fabricado = self._cadena("prnp_3utr_fabricado_1246nt.txt")
        verdaderas = [self._cadena("NM_011170.3.fa"), self._cadena("NM_000311.5.fa")]
        # Un tramo del fabricado que NO está en ninguna referencia: existe, porque el
        # fabricado difiere en 20 sucesos. Se busca uno de verdad, no se inventa.
        exclusivo = next(
            (
                fabricado[i : i + 20]
                for i in range(len(fabricado) - 20)
                if not any(fabricado[i : i + 20] in r for r in verdaderas)
            ),
            None,
        )
        self.assertIsNotNone(
            exclusivo,
            "El fabricado no tiene ningún tramo exclusivo, así que esta búsqueda no "
            "podría distinguir nada y el test de arriba no prueba lo que dice.",
        )

    def test_el_out_de_biblioteca_equivocada_no_aporta_NINGUNA_cifra_propia(self):
        """Y la razón es la propia demostración: es el MISMO fichero byte a byte.

        No hay ninguna cifra que sólo esté en él, porque no hay ninguna cifra suya que
        no esté también en la corrida válida. Lo que lo distingue vive en el `.tbl`.
        """
        malo = (REFERENCIA / "rmsk_human_WRONG_SPECIES_mouse_lib.out").read_bytes()
        bueno = (REFERENCIA / "rmsk_human.out").read_bytes()
        self.assertEqual(malo, bueno)

    def test_y_del_tbl_equivocado_tampoco_hay_ninguna_en_el_codigo(self):
        import re

        numero = re.compile(r"\b\d+(?:\.\d+)?\b")

        def cifras(nombre):
            return set(
                numero.findall(
                    (REFERENCIA / nombre).read_text(encoding="utf-8", errors="replace")
                )
            )

        exclusivas = (
            cifras("rmsk_human_WRONG_SPECIES_mouse_lib.tbl")
            - cifras("rmsk_human.tbl")
            - cifras("rmsk_mouse.tbl")
        )
        literales = set()
        for carpeta in ("shmir_design", "tools"):
            for ruta in sorted((RAIZ / carpeta).glob("*.py")):
                for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
                    if isinstance(nodo, ast.Constant) and isinstance(
                        nodo.value, (int, float)
                    ) and not isinstance(nodo.value, bool):
                        literales.add(repr(nodo.value))
        self.assertEqual(sorted(exclusivas & literales), [])


if __name__ == "__main__":
    unittest.main()
