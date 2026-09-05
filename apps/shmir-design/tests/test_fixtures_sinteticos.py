"""El inventario de fixtures sintéticos donde existe el artefacto real.

Regla 5: escrito antes que la tabla no —la tabla ya estaba— pero sí antes de que la
justificación fuera OBLIGATORIA, que es lo que hace aquí.

De dónde sale: de la segunda mitad del principio nº 18. Un parámetro tecleado y un
fixture sintético son la misma enfermedad; los dos validan un camino que nadie recorre.
`test_usar_manifiesto.py` pasaba de punta a punta sobre un manifiesto PARCIAL montado en
un temporal, y el manifiesto real abortaba (errata nº 33).

Lo que falla aquí NO es fabricar —hay motivos buenos y están escritos— sino fabricar sin
decir por qué, o dejar una justificación que ya no corresponde a ningún test.
"""

import tomllib
import unittest
from pathlib import Path

from tools import auditar_fixtures as auditoria

RAIZ = Path(__file__).resolve().parent.parent
TABLA = tomllib.loads(
    (RAIZ / "data" / "fixtures_sinteticos.toml").read_text(encoding="utf-8")
)


class TestLaListaSeDERIVA(unittest.TestCase):
    """Los artefactos salen del directorio, no de una lista transcrita: uno nuevo en
    `data/reference/` entra solo en el radar (principio nº 13)."""

    def test_los_artefactos_salen_del_DIRECTORIO(self):
        reales = auditoria.artefactos_reales()
        en_disco = sorted(
            p.name for p in (RAIZ / "data" / "reference").iterdir() if p.is_file()
        )
        self.assertEqual(reales, en_disco)
        self.assertIn("mature.fa", reales)

    def test_y_el_manifiesto_REAL_esta_entre_ellos(self):
        """El caso que enseñó la errata: existe de verdad y había un fixture parcial."""
        self.assertIn("manifest.tsv", auditoria.artefactos_reales())


class TestLaTablaCubreLoQueHAY(unittest.TestCase):

    def setUp(self):
        self.informe = auditoria.auditar()

    def test_ninguna_fabricacion_se_queda_SIN_justificar(self):
        self.assertEqual(self.informe.sin_justificar, [])

    def test_y_ninguna_entrada_nombra_un_test_que_ya_no_fabrica(self):
        """Una justificación caducada es peor que ninguna: se lee como vigente."""
        self.assertEqual(self.informe.muertas, [])

    def test_toda_justificacion_esta_ESCRITA_y_no_es_un_hueco(self):
        for fila in self.informe.filas:
            if fila["usa_el_real"]:
                continue
            motivo = fila["por_que_no_el_real"]
            self.assertTrue(motivo, f"{fila['test']} → {fila['artefacto']}")
            self.assertGreater(
                len(motivo),
                60,
                f"{fila['test']} → {fila['artefacto']}: «{motivo}» no explica nada.",
            )

    def test_una_entrada_que_dice_usar_el_real_y_sigue_FABRICANDO_se_contradice(self):
        for fila in self.informe.filas:
            if fila["usa_el_real"]:
                self.fail(
                    f"{fila['test']} → {fila['artefacto']} declara que usa el real y el "
                    f"detector lo ve fabricándolo. Una de las dos cosas está mal."
                )

    def test_la_tabla_no_tiene_entradas_REPETIDAS(self):
        claves = [(e["test"], e["artefacto"]) for e in TABLA["fixture"]]
        self.assertEqual(len(claves), len(set(claves)))


class TestElCasoQueLOenseño(unittest.TestCase):
    """La errata nº 33, anclada: el fixture parcial sigue siendo legítimo, pero ya no
    está solo — hay una corrida contra el manifiesto REAL."""

    def test_el_manifiesto_parcial_sigue_justificado(self):
        entrada = next(
            e
            for e in TABLA["fixture"]
            if e["test"] == "test_usar_manifiesto.py"
        )
        self.assertIn("REAL", entrada["por_que_no_el_real"])

    def test_y_EXISTE_la_corrida_contra_el_manifiesto_real(self):
        """Lo que faltaba no era dejar de fabricar: era que ADEMÁS hubiera una contra el
        real. Si alguien borra ese fichero, la justificación deja de sostenerse."""
        real = RAIZ / "tests" / "test_roles_del_manifiesto.py"
        self.assertTrue(real.exists(), "se fue la corrida contra el manifiesto real")
        fuente = real.read_text(encoding="utf-8")
        self.assertIn("--usar-manifiesto", fuente)
        self.assertIn('"data" / "reference"', fuente)


class TestLoQueELdetectorNOpuedeHacer(unittest.TestCase):
    """Se contrasta el criterio: este detector ya se equivocó una vez, contando
    `shutil.copy` como fabricación —47 detecciones en 20 ficheros, y la mayoría eran
    tests haciendo lo correcto. Un auditor con falsos positivos se acaba apagando."""

    def test_copiar_el_real_NO_es_fabricarlo(self):
        self.assertNotIn("shutil", auditoria.ESCRITURA.pattern)
        self.assertIsNone(auditoria.ESCRITURA.search("shutil.copy(real, destino)"))

    def test_escribir_SI_lo_es(self):
        for linea in (
            '    (tmp / "inventado.fa").write_text(">a\\nACGU\\n")',
            '    destino.write_bytes(b"x")',
            '    with open(ruta, "w") as fh:',
        ):
            self.assertIsNotNone(auditoria.ESCRITURA.search(linea), linea)

    def test_el_detector_NO_distingue_un_EJEMPLO_de_una_fabricacion(self):
        """Límite propio, y lo cazó este mismo fichero DOS VECES: primero las líneas
        de ejemplo de arriba, que llevaban el nombre de un artefacto real; y después esta
        misma explicación, por nombrarlo al contarlo. Se reconoce por el NOMBRE, así que
        cualquier cadena que lo lleve cerca de una escritura cuenta, sea un ejemplo o sea
        prosa. Por eso los ejemplos usan un nombre que no existe y esta frase no nombra
        ninguno."""
        self.assertNotIn("inventado.fa", auditoria.artefactos_reales())

    def test_el_nombre_y_la_escritura_tienen_que_estar_CERCA(self):
        """Un fichero de test menciona muchos nombres; lo que delata la fabricación es
        que el nombre y el `write_text` estén juntos."""
        self.assertEqual(auditoria.CERCA, 2)
