"""Un log con la misma corrida dos veces se puede ABRIR. Leer no es escribir.

Regla 5: escritos antes.

**Reportado el 2026-09-07**, y contra lo que yo habia dicho: *«el aborto SI tumba la
pagina. El mensaje rojo del duplicado es el final de la pagina: por debajo no hay nada.
Ni tabla de candidatos, ni el resto de modales, ni las descargas, ni el paso 5. Asi que no
puedo hacer nada de lo que el propio mensaje me dice: el texto me manda a sitios que ese
mismo error ha hecho inalcanzables»*.

**MEDIDO sobre un proyecto de verdad**, no sobre un fixture, y con la comprobacion nueva
desactivada para reproducir el build desplegado:

    1a subida OK. registros: 1
    2a subida: NO ABORTA en el append. registros: 2
    load_stores REVIENTA: ShmirDesignError

O sea la cadena entera:

  1. `ProjectStore.append` NO miraba el `run_id`, asi que la segunda subida del mismo
     fichero **escribe una segunda linea** con el mismo id;
  2. quien miraba el id era `SpliceStore.add` — que lo llama tambien el CARGADOR;
  3. asi que desde ese momento **`load_stores` aborta en cada repintado**, y `load_stores`
     se llama en `_bloque_especie` antes de la tabla de candidatos y fuera de todo `try`;
  4. el log es **append-only**: esa linea no se puede quitar, asi que el proyecto queda
     inservible **para siempre**.

### La regla ya estaba escrita y aplicada a medias

`_rechaza_si_es_el_mismo_fichero` se puso en `append` con el motivo escrito: *«`add` lo
llaman tambien los cargadores al releer el log, asi que abortar ahi dejaria sin poder
ABRIR un proyecto que ya tiene el duplicado escrito»*. Eso se escribio del `result_md5`
**y `add` seguia haciendo exactamente eso con el `run_id`**. La regla era correcta y no se
aplico al guardia que ya estaba.

**`add` contesta DOS preguntas** —«¿acepto esta corrida nueva?» y «¿reproduzco esta linea
del log?»— y solo la primera estaba escrita. Es el principio nº 53 en un metodo.

### Y omitir NO es callar

Una repetida en el log se omite —es la misma medida, contarla dos veces seria decir que se
comprobo dos veces— y se APUNTA, para que la app pueda decirlo. Un log que se abre en
silencio despues de esto seria el `verify()` que no verificaba.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design import identidad, store as store_mod
from shmir_design.errors import ShmirDesignError

SECUENCIA = "ACGT" * 20


def _cargadores_declarados():
    """Los cargadores, DERIVADOS del modulo: un quinto modal queda cubierto solo.

    No se derivan de `RECORD_KINDS` porque el nombre del almacen no es el de la etiqueta
    —`corrida_empalme` se guarda en `splice`— y esa correspondencia ya esta declarada en
    `store_mod`. Derivar de una tabla que no manda seria inventarse un mapeo.
    """
    return {
        nombre: getattr(store_mod, nombre)
        for nombre in dir(store_mod)
        if nombre.startswith("load_") and nombre.endswith("_store")
    }


class TestLosCuatroCargadoresTOLERAN_una_REPETIDA(unittest.TestCase):

    def test_los_CUATRO_cargadores_usan_la_VIA_QUE_TOLERA(self):
        """Si uno volviera a `add`, ese almacen se lleva la pagina por delante otra vez.

        Se comprueba sobre el FUENTE porque lo que importa es a quien llama el cargador,
        y eso no se puede preguntar desde fuera sin construir un log con la repetida para
        cada uno. La cuenta se DERIVA: un quinto cargador entra solo.
        """
        import inspect

        cargadores = _cargadores_declarados()
        self.assertEqual(len(cargadores), 4, sorted(cargadores))
        for nombre, cargador in cargadores.items():
            with self.subTest(nombre):
                fuente = inspect.getsource(cargador)
                self.assertIn("add_recorded(", fuente)
                self.assertNotIn("almacen.add(", fuente)

    def test_add_SIGUE_abortando_al_escribir(self):
        """La comprobacion no se relaja: lo que cambia es QUIEN la hace, no si se hace."""
        from shmir_design.splice_store import SpliceStore

        almacen = SpliceStore()
        corrida = _corrida_de_empalme()
        almacen.add(corrida)
        with self.assertRaises(ShmirDesignError):
            almacen.add(_corrida_de_empalme())

    def test_pero_al_RELEER_se_OMITE_y_se_APUNTA(self):
        from shmir_design.splice_store import SpliceStore

        almacen = SpliceStore()
        almacen.add_recorded(_corrida_de_empalme())
        almacen.add_recorded(_corrida_de_empalme())
        self.assertEqual(len(almacen.runs), 1)
        # Y NO se calla: el id repetido queda apuntado para que la app lo diga.
        self.assertEqual(list(almacen.repetidas), [_corrida_de_empalme().run_id])

    def test_una_corrida_DISTINTA_al_releer_entra_igual(self):
        """Control adversario: sin esto, «tolera repetidas» y «no guarda nada» coinciden."""
        from shmir_design.splice_store import SpliceStore

        almacen = SpliceStore()
        almacen.add_recorded(_corrida_de_empalme())
        almacen.add_recorded(_corrida_de_empalme(md5="otro"))
        self.assertEqual(len(almacen.runs), 2)
        self.assertEqual(list(almacen.repetidas), [])


def _corrida_de_empalme(md5: str = "abc"):
    from shmir_design.spliceai import SpliceScan
    from shmir_design.splice_store import SpliceRun

    return SpliceRun(
        run_id=identidad.run_id(
            kind="corrida_empalme", date="2026-09-07", result_md5=md5,
        ),
        date="2026-09-07", ran_by="JCC", executor="prueba", result_md5=md5,
        scan=SpliceScan(pairs=()), raw="crudo", folding={},
    )


class TestElPROYECTO_afectado_se_VUELVE_a_ABRIR(unittest.TestCase):
    """El caso REAL: un log que ya tiene la linea repetida escrita.

    No se puede arreglar borrandola —el log es append-only y su integridad se comprueba
    con una cadena de md5— asi que la unica salida es que ABRIRLO funcione. Si no, el
    proyecto y todo lo que se decidio en el quedan inaccesibles para siempre.
    """

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="repetida_"))
        self.almacen = store_mod.ProjectStore.create(
            self.raiz, slug="repetida", sequence=SECUENCIA, species="raton",
            anatomy={}, anatomy_source="declarado", created="2026-09-07",
        )

    def _escribe_la_repetida(self):
        """Se escribe SALTANDOSE la comprobacion, que es como esta en el log real: se
        escribio antes de que la comprobacion existiera."""
        import json

        corrida = _corrida_de_empalme()
        contenido = {
            "run_id": corrida.run_id, "ran_by": "JCC", "executor": "prueba",
            "result_md5": "abc", "pairs": [], "raw": "crudo", "folding": {},
        }
        self.almacen.append("corrida_empalme", contenido, date="2026-09-07")
        crudo = json.loads(
            self.almacen.log_path.read_text("utf-8").splitlines()[-1]
        )
        linea = {
            "seq": crudo["seq"] + 1, "kind": "corrida_empalme", "date": "2026-09-07",
            "payload": contenido, "prev_md5": crudo["md5"],
            "md5": store_mod._line_md5(
                crudo["seq"] + 1, "corrida_empalme", "2026-09-07", contenido,
                crudo["md5"],
            ),
        }
        with self.almacen.log_path.open("a", encoding="utf-8") as salida:
            salida.write(json.dumps(linea, ensure_ascii=False, sort_keys=True) + "\n")

    def test_se_ABRE_y_la_cadena_VERIFICA(self):
        self._escribe_la_repetida()
        vuelto = store_mod.ProjectStore.open(self.raiz, "repetida")
        vuelto.verify()
        self.assertEqual(len(vuelto.records("corrida_empalme")), 2)

    def test_y_load_stores_NO_REVIENTA(self):
        """Es la llamada que corre en CADA repintado, antes de la tabla de candidatos."""
        self._escribe_la_repetida()
        vuelto = store_mod.ProjectStore.open(self.raiz, "repetida")
        from shmir_design import presentation

        almacenes = presentation.load_stores(vuelto)
        self.assertIn("splice", almacenes)

    def test_y_la_REPETIDA_se_DICE(self):
        """Omitir en silencio es el `verify()` que no verificaba."""
        from shmir_design import presentation

        self._escribe_la_repetida()
        vuelto = store_mod.ProjectStore.open(self.raiz, "repetida")
        aviso = presentation.duplicated_runs_note(presentation.load_stores(vuelto))
        self.assertTrue(aviso["activo"])
        self.assertIn(_corrida_de_empalme().run_id, aviso["texto"])
        # Y dice que NO se puede borrar, que es lo que evita que alguien lo intente.
        self.assertIn("append-only", aviso["texto"])

    def test_control_adversario_un_log_LIMPIO_no_avisa_de_nada(self):
        from shmir_design import presentation

        aviso = presentation.duplicated_runs_note(
            presentation.load_stores(store_mod.ProjectStore.open(self.raiz, "repetida"))
        )
        self.assertFalse(aviso["activo"])


if __name__ == "__main__":
    unittest.main()
