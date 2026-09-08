"""`--usar-manifiesto` conecta los ficheros DE LA ESPECIE QUE SE DISEÑA.

Regla 5: escrito antes.

**El fallo que cierra.** `conectar_desde_manifiesto` emparejaba por el NOMBRE del
fichero contra `manifest.ROLES`, que trae los nombres MURINOS escritos. Con un diseño
humano y una sola especie, el CLI conectaba `aav_casete.fa` y `rmsk_mouse.out` — y de
los diez ficheros que `species.required_files` pide para humano reconocia DOS, los dos
que no llevan especie.

Lo que se veia era el aborto del guardia de la mascara (`RepeatMask.query_length`). Lo
que ese aborto TAPABA es que el casete murino ya se habia conectado como filtro del
transgen, y ahi no hay ningun guardia: medido, emite 415 PASS y 4 FAIL sobre ventanas
humanas contra una construccion que no es la suya.

Es la QUINTA divergencia entre los dos frontales —la pagina si pasa `species=` a
`resources.load_from_manifest`— y la misma clase que obligo a escribir `resolve.py`.

**Corre contra el manifiesto REAL**, no contra uno sintetico en un temporal: el fallo
vive justo en que los nombres del manifiesto de verdad son murinos, asi que un
manifiesto fabricado para el test no puede delatarlo (principio nº 18).
"""

import argparse
import unittest
from pathlib import Path

from shmir_design.manifest import MANIFEST_NAME
from shmir_design.species import required_files, resolve
from tools.design import DESTINOS, conectar_desde_manifiesto, estado_de_los_datos

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
HAY_MANIFIESTO = (DATOS / MANIFEST_NAME).is_file()

#: Los destinos que este test mira. Se DERIVAN de `DESTINOS`, no se escriben: un rol
#: nuevo con bandera queda cubierto sin que nadie se acuerde.
CON_BANDERA = tuple(sorted(r for r, c in DESTINOS.items() if c is not None))


def _args(nombre: str) -> argparse.Namespace:
    """Un Namespace con todos los destinos a `None`, como sale del parser."""
    vacios = {}
    for conexion in DESTINOS.values():
        if conexion is None:
            continue
        for campo in conexion:
            if campo is not None:
                vacios[campo] = None
    return argparse.Namespace(
        datos=DATOS, name=nombre,
        rmsk_especie=None, rmsk_biblioteca=None, rmsk_resumen=None, **vacios,
    )


def _conectados(nombre: str) -> dict[str, str]:
    """Que fichero acaba en cada destino, corriendo la conexion de verdad."""
    estado, _ = estado_de_los_datos(DATOS, permitir_sin_manifiesto=False)
    args = _args(nombre)
    conectar_desde_manifiesto(args, estado, species=resolve(nombre))
    salida = {}
    for rol, conexion in DESTINOS.items():
        if conexion is None:
            continue
        valor = getattr(args, conexion[0])
        if valor is not None:
            salida[rol] = Path(valor).name
    return salida


@unittest.skipUnless(HAY_MANIFIESTO, "NOT_RUN: no hay manifiesto en data/reference")
class TestNingunFicheroDeOtraEspecie(unittest.TestCase):

    def test_el_HUMANO_no_recibe_ningun_fichero_murino(self):
        conectados = _conectados("humano")
        murinos = {
            r.filename for r in required_files(resolve("mouse"))
        } - {r.filename for r in required_files(resolve("humano"))}
        colados = {rol: n for rol, n in conectados.items() if n in murinos}
        self.assertEqual(
            colados, {},
            f"El diseño humano recibio ficheros murinos: {colados}. Es el agujero de "
            f"`rmsk_mouse.out` conectado por su rol, y con el casete no hay guardia "
            f"que lo cace despues.",
        )

    def test_y_el_CASETE_es_el_caso_sin_guardia(self):
        # Se nombra aparte porque es el unico cuyo fallo seria SILENCIOSO: la mascara
        # aborta por longitud de consulta y el casete no tiene nada equivalente.
        self.assertNotEqual(_conectados("humano").get("transgen"), "aav_casete.fa")

    def test_el_RATON_sigue_recibiendo_los_suyos(self):
        # El control adversario: desconectarlo todo tambien pasaria el test de arriba.
        conectados = _conectados("raton")
        self.assertEqual(conectados.get("transgen"), "aav_casete.fa")
        self.assertEqual(conectados.get("rmsk"), "rmsk_mouse.out")

    def test_y_el_HUMANO_recibe_el_suyo_cuando_esta(self):
        # `rmsk_human.out` SI esta en el repositorio, asi que este es el caso positivo:
        # no basta con no conectar lo ajeno, hay que conectar lo propio.
        self.assertEqual(_conectados("humano").get("rmsk"), "rmsk_human.out")

    def test_la_especie_del_rmsk_sale_de_SU_referencia(self):
        estado, _ = estado_de_los_datos(DATOS, permitir_sin_manifiesto=False)
        args = _args("humano")
        conectar_desde_manifiesto(args, estado, species=resolve("humano"))
        self.assertEqual(args.rmsk_especie, "homo sapiens")


@unittest.skipUnless(HAY_MANIFIESTO, "NOT_RUN: no hay manifiesto en data/reference")
class TestUnaEspecieSinDeclararNoConectaNada(unittest.TestCase):
    """Sin especie declarada no se puede saber que ficheros son los tuyos.

    `--name` vale `3utr` por defecto: es una ETIQUETA, no una especie. Conectar por rol
    con eso puesto es exactamente lo que producia el fallo, asi que se ABORTA diciendo
    donde se declaran las especies — no se conecta «lo que haya».
    """

    def test_aborta_y_dice_donde_se_declara(self):
        estado, _ = estado_de_los_datos(DATOS, permitir_sin_manifiesto=False)
        with self.assertRaises(Exception) as caso:
            conectar_desde_manifiesto(_args("3utr"), estado, species=None)
        mensaje = str(caso.exception)
        self.assertIn("3utr", mensaje)
        self.assertIn("species.SPECIES", mensaje)

    def test_y_NO_menciona_ningun_fichero_como_si_fuera_suyo(self):
        estado, _ = estado_de_los_datos(DATOS, permitir_sin_manifiesto=False)
        with self.assertRaises(Exception) as caso:
            conectar_desde_manifiesto(_args("3utr"), estado, species=None)
        self.assertNotIn("aav_casete.fa", str(caso.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
