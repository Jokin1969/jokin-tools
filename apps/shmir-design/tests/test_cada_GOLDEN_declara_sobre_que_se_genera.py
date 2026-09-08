"""Cada golden dice EN SU CABECERA sobre qué entrada se genera.

Pedido por el responsable del proyecto (2026-09-06), y el motivo es exactamente lo que
acababa de pasar: al arreglar el marco del aviso de multiplexado cambió UN golden y no
cambiaron los otros tres, y esa lectura —«el que no cambia confirma dónde estaba el fallo
tanto como el que cambia»— sólo se pudo hacer **abriendo `regenerar_golden.py`**.

    «Es lo que hace legible que un golden no cambie — y hoy esa lectura sólo la pudiste
     hacer mirando regenerar_golden.py.»

Un artefacto de verificación que no declara sobre qué corre no permite interpretar su
silencio: un golden que no cambia puede significar «el fallo no está ahí» o «desde ahí no
se puede ver», y son cosas distintas.

Y la cabecera NO se transcribe: sale de `CONFIGURACION`, que es lo mismo que usa el
generador, así que no puede describir una entrada y generarse con otra (principio nº 13).
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GOLDENS = RAIZ / "tests" / "golden"
sys.path.insert(0, str(RAIZ))


@unittest.skipUnless(GOLDENS.is_dir(), f"NOT_RUN: falta {GOLDENS}")
class TestLaCabeceraDeCadaGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.regenerar_golden import CONFIGURACION, cabecera

        cls.CONFIGURACION = CONFIGURACION
        cls.cabecera = staticmethod(cabecera)
        cls.ficheros = sorted(
            p for p in GOLDENS.iterdir() if p.suffix in {".txt", ".md"}
        )

    def test_hay_goldens_que_mirar(self):
        """Sin esto, «todos declaran» y «no hay ninguno» dan el mismo verde."""
        self.assertTrue(self.ficheros)

    def test_TODOS_estan_declarados_en_CONFIGURACION(self):
        # En las dos direcciones: un golden sin entrada saldria mudo, y una entrada
        # huerfana describe algo que ya no existe — engaña igual que la ausencia.
        self.assertEqual(
            {p.name for p in self.ficheros}, set(self.CONFIGURACION),
        )

    def test_cada_uno_EMPIEZA_por_su_cabecera(self):
        for fichero in self.ficheros:
            with self.subTest(fichero.name):
                texto = fichero.read_text(encoding="utf-8")
                self.assertTrue(
                    texto.startswith(self.cabecera(fichero.name)),
                    f"{fichero.name} no empieza por la cabecera que declara su entrada",
                )

    def test_la_cabecera_dice_QUE_SE_TILA(self):
        # Es la pregunta que no se podia contestar sin abrir el generador: sobre el
        # transcrito entero o sobre el 3'UTR pelado. Las dos son configuraciones reales.
        for nombre in self.CONFIGURACION:
            with self.subTest(nombre):
                texto = self.cabecera(nombre).lower()
                self.assertTrue(
                    "transcrito" in texto or "3'utr" in texto,
                    f"{nombre}: su cabecera no dice sobre qué se tila",
                )

    def test_y_las_DOS_configuraciones_estan_cubiertas(self):
        """El fallo del marco sólo se veia tilando el transcrito, y las dos vias son
        reales: la pagina tila el transcrito y «lo que subo YA es el 3'UTR» tila el
        pelado. Si sólo hubiera una, la otra no estaria probada por nadie."""
        textos = [self.cabecera(n).lower() for n in self.CONFIGURACION]
        self.assertTrue(any("transcrito entero" in t for t in textos))
        self.assertTrue(any("3'utr pelado" in t for t in textos))


if __name__ == "__main__":
    unittest.main()
