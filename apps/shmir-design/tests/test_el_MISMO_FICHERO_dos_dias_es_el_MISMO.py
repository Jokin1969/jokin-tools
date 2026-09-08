"""El mismo fichero subido dos días distintos NO es dos corridas.

Regla 5: escritos antes.

**Reportado el 2026-09-07, leyendo el historial del proyecto**: *«hay dos
`corrida_empalme` con el mismo `result_md5` en días distintos. El `run_id` incluye la
fecha, así que no chocan — pero son el mismo fichero subido dos veces y eso debería
reconocerse, como haces con BLAST»*.

**Y BLAST tampoco lo reconocía.** El `run_id` es `<tipo>-<fecha>-<result_md5>` (errata
nº 48), así que el mismo fichero en dos días da dos ids distintos y entra dos veces — en
los CUATRO almacenes. Lo que sí saltaba, y es lo que se había visto, es el caso del mismo
DÍA: ahí el id coincide y `add` aborta. O sea que la comprobación existía para la mitad
del caso y la mitad que faltaba es justo la que no se ve, porque no da ningún error.

**Lo que cuesta**: `latest` es la última corrida guardada, y una repetida la desplaza sin
aportar nada. Un historial con la misma medida dos veces se lee como dos comprobaciones
independientes, que es lo contrario de lo que es.

### Dónde va, y por qué ahí

En `ProjectStore.append`, que es por donde pasan los cuatro `save_*` y **el único sitio
por el que se ESCRIBE** en el log. No en `add` de cada almacén: `add` lo llaman también
los cargadores al releer el log, así que abortar ahí dejaría sin poder abrir un proyecto
que YA tiene el duplicado escrito — y el log es append-only, así que borrarlo no es una
opción. La regla se aplica al ESCRIBIR, no al leer.

Y se DERIVA del propio registro: cualquier tipo cuyo contenido lleve `result_md5` queda
cubierto sin nombrarlo. Escribir la lista de los cuatro tipos habría dejado fuera al
quinto modal el día que llegue — la lección de `offtarget_seed`.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design import store as store_mod
from shmir_design.errors import ShmirDesignError
from shmir_design.identidad import run_id

SECUENCIA = "ACGT" * 20


def _id(fecha: str, md5: str) -> str:
    """El id se PIDE, no se teclea: es la regresión de la errata nº 48 y del guardia de
    claves derivadas — un test que escribe la clave por la que pregunta coincide por
    construcción."""
    return run_id(kind="corrida_empalme", date=fecha, result_md5=md5)


def _proyecto(raiz):
    return store_mod.ProjectStore.create(
        raiz, slug="repetido", sequence=SECUENCIA, species="raton",
        anatomy={}, anatomy_source="declarado", created="2026-09-06",
    )


class TestElMismoResultadoDosDias(unittest.TestCase):

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="repetido_"))
        self.almacen = _proyecto(self.raiz)

    def test_el_segundo_ABORTA_y_nombra_al_primero(self):
        self.almacen.append(
            "corrida_empalme",
            {"run_id": _id("2026-09-06", "abc"), "result_md5": "abc"},
            date="2026-09-06",
        )
        with self.assertRaises(ShmirDesignError) as cm:
            self.almacen.append(
                "corrida_empalme",
                {"run_id": _id("2026-09-07", "abc"), "result_md5": "abc"},
                date="2026-09-07",
            )
        mensaje = str(cm.exception)
        self.assertIn("abc", mensaje)
        self.assertIn("2026-09-06", mensaje)
        # Y DICE QUE NO ES UN FALLO DE LA SUBIDA: el fichero ya está registrado.
        self.assertIn("mismo fichero", mensaje.lower())

    def test_un_resultado_DISTINTO_el_mismo_dia_entra_sin_problema(self):
        """Control adversario: repetir una corrida el mismo día es legítimo.

        Es exactamente el caso de la errata nº 48 — cuatro corridas en un día, todas por
        fallos de la app. Lo que no vale es subir DOS VECES LA MISMA.
        """
        self.almacen.append(
            "corrida_empalme",
            {"run_id": _id("2026-09-06", "abc"), "result_md5": "abc"},
            date="2026-09-06",
        )
        registro = self.almacen.append(
            "corrida_empalme",
            {"run_id": _id("2026-09-06", "def"), "result_md5": "def"},
            date="2026-09-06",
        )
        self.assertEqual(registro.payload["result_md5"], "def")

    def test_el_MISMO_md5_en_OTRO_tipo_de_corrida_no_choca(self):
        """Dos frentes distintos pueden dar el mismo digesto sin ser el mismo fichero."""
        self.almacen.append(
            "corrida_empalme",
            {"run_id": _id("2026-09-06", "abc"), "result_md5": "abc"},
            date="2026-09-06",
        )
        registro = self.almacen.append(
            "corrida_blast",
            {"run_id": run_id(kind="corrida_blast", date="2026-09-06", result_md5="abc"), "result_md5": "abc"},
            date="2026-09-06",
        )
        self.assertEqual(registro.kind, "corrida_blast")

    def test_un_registro_SIN_result_md5_no_pasa_por_la_comprobacion(self):
        """`seleccion`, `nota` y `descarte` no son ficheros: repetirlas es normal."""
        self.almacen.append("nota", {"texto": "la misma nota"}, date="2026-09-06")
        registro = self.almacen.append(
            "nota", {"texto": "la misma nota"}, date="2026-09-07"
        )
        self.assertEqual(registro.kind, "nota")

    def test_UN_LOG_QUE_YA_LO_TIENE_se_sigue_pudiendo_ABRIR(self):
        """La regla es al ESCRIBIR. El log es append-only y lo escrito no se borra.

        Si `add` abortara, un proyecto con el duplicado ya dentro —que es el caso que se
        reportó— dejaría de poder abrirse, y no habría forma de arreglarlo sin editar a
        mano un fichero cuya integridad se comprueba con una cadena de md5.
        """
        from shmir_design.store import ProjectStore

        # Se escribe la línea repetida SALTÁNDOSE la comprobación, que es como está en
        # el log del proyecto real: se escribió antes de que la comprobación existiera.
        self.almacen.append(
            "corrida_empalme",
            {"run_id": _id("2026-09-06", "abc"), "result_md5": "abc"},
            date="2026-09-06",
        )
        with self.almacen.log_path.open("a", encoding="utf-8") as salida:
            import json

            crudo = json.loads(self.almacen.log_path.read_text("utf-8").splitlines()[-1])
            seq = crudo["seq"] + 1
            payload = {"run_id": _id("2026-09-07", "abc"), "result_md5": "abc"}
            linea = {
                "seq": seq, "kind": "corrida_empalme", "date": "2026-09-07",
                "payload": payload, "prev_md5": crudo["md5"],
                "md5": store_mod._line_md5(
                    seq, "corrida_empalme", "2026-09-07", payload, crudo["md5"]
                ),
            }
            salida.write(json.dumps(linea, ensure_ascii=False, sort_keys=True) + "\n")

        vuelto = ProjectStore.open(self.raiz, "repetido")
        vuelto.verify()
        self.assertEqual(len(vuelto.records("corrida_empalme")), 2)


if __name__ == "__main__":
    unittest.main()
