"""La pagina ENTERA, con el proyecto real y sus corridas guardadas, hasta la ultima linea.

**Pedido el 2026-09-07, con la pantalla delante**: *«corre la pagina de punta a punta con
este proyecto real y comprueba que se pinta hasta el final — no que el emisor concreto
esta arreglado»*. Nace de que tres arreglos seguidos destaparon tres cortes distintos en
la MISMA pantalla, cada uno debajo del anterior: mirar el emisor que se acaba de arreglar
no dice nada de lo que hay debajo.

**Que corre esto que no corria nada.** `tests/test_corrida_de_la_pagina.py` fija el
camino de la pagina contra un golden, y lo hace **con el proyecto VACIO**: sin corridas
guardadas no se pintan los percentiles destacados, ni las notas del registro, ni la tabla
del modal releida del log — que es justo la mitad de la pagina donde estaban los tres
cortes. Un golden generado sobre un proyecto sin nada dentro no puede ver lo que solo
aparece cuando hay algo dentro.

Y se pinta con **Streamlit de verdad** (`streamlit.testing.v1.AppTest`), no con un doble:
es la misma leccion del test de humo de `/shmir` —«un cliente que no se parece al real no
prueba nada»—, y el fallo del 2026-09-07 vivia precisamente en la frontera, donde el
`except` de `main()` convierte un `ValueError` en un mensaje rojo y **se lleva por
delante todo lo que faltaba por pintar**.

**LAS DOS EXIGENCIAS, y la segunda importa mas que la primera:**

1. que la pagina llegue al final —Descargas y paso 5— sin ningun `**PARA**`;
2. que **ninguna etiqueta `3utr:N` pase de la longitud del 3'UTR de ESTE proyecto**
   (1242 nt en el transcrito murino). El invariante de `coords` tiene el techo en 1606
   —el 3'UTR humano, que es el mas largo que conoce el proyecto— asi que de los once
   candidatos solo aborta con los cuatro que pasan de 1606: los otros siete se imprimen
   mal y en silencio. La primera exigencia caza lo que tumba la pagina; la segunda caza
   lo que la pagina dice mal sin caerse, que es lo que llevaba semanas pasando.

Regla 5: escrito antes.
"""

import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.offtarget import DEFAULTS as OFFTARGET_DEFAULTS
from shmir_design.offtarget import build_catalog, run_scan
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.trabajo import reference_dir

RAIZ = Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "ui" / "streamlit_app.py"
RATON = REFERENCES["NM_011170.3"]
MATURE = reference_dir() / "mature.fa"

try:  # La interfaz es OPCIONAL (`requirements-ui.txt`); el nucleo no la necesita.
    from streamlit.testing.v1 import AppTest
    HAY_STREAMLIT = True
except ImportError:  # rule2-ok: se declara como NOT_RUN, no se traga nada.
    AppTest = None
    HAY_STREAMLIT = False

HAY = (
    HAY_STREAMLIT
    and fixture_available(RATON)
    and fixture_available(REFERENCES["NM_000311.5"])
    and MATURE.exists()
)

#: La longitud del 3'UTR de este proyecto. **No se escribe**: se deriva de la anatomia
#: verificada del transcrito, que es lo que hace que este numero no caduque el dia que
#: la referencia cambie (principio nº 13).
def _utr3_length() -> int:
    return len(load_reference(RATON)) - RATON.cds[1]


def _proyecto_con_una_corrida(base: Path) -> str:
    """Un proyecto sobre el TRANSCRITO con una corrida de off-targets guardada.

    Sobre el transcrito y no sobre el 3'UTR pelado a proposito: es el unico caso donde
    `tx` y `3utr` NO coinciden, o sea el unico donde un marco escrito a mano se puede
    distinguir de uno derivado.
    """
    from shmir_design.identidad import result_fingerprint
    from shmir_design.mirna import load_mature_fa
    from shmir_design.offtarget import Provenance
    from shmir_design.reference import load_3utr

    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    corrida = presentation.page_run(
        species="Mus musculus", sequence=secuencia, anatomy=anatomia
    )
    registros = (
        (RATON.accession, load_3utr(RATON)),
        (REFERENCES["NM_000311.5"].accession, load_3utr(REFERENCES["NM_000311.5"])),
    )
    catalogo = build_catalog(
        registros,
        provenance=Provenance(
            source="fixtures del proyecto (NO es el transcriptoma)",
            assembly="n/a — dos 3'UTR de referencia, no un ensamblaje",
            table="data/reference/NM_011170.3.fa + NM_000311.5.fa",
            table_date="2026-08-26",
            representative="uno por gen porque solo hay dos genes",
            version="fixtures-2026-08-26",
            md5=result_fingerprint("".join(s for _, s in registros)),
        ),
    )
    payload, fuente = presentation.anatomy_payload(anatomia)
    almacen = presentation.project_create(
        base, slug="panel_del_transcrito", date="2026-09-07", sequence=secuencia,
        species="Mus musculus", anatomy=payload, anatomy_source=fuente,
    )
    escaneo = run_scan(
        corrida.selection, catalog=catalogo,
        mature=load_mature_fa(MATURE, version="23"), params=OFFTARGET_DEFAULTS,
        species="Mus musculus",
        starts=tuple(presentation.chosen_starts(corrida.selection)),
        guides=True, passengers=True, target=corrida.utr3,
        target_label="3'UTR de Mus musculus",
    )
    presentation.save_offtarget_run(
        almacen,
        presentation.offtarget_run_from_scan(
            escaneo, date="2026-09-07", ran_by="test"
        ),
    )
    return "panel_del_transcrito"


#: LOS TIPOS DE ELEMENTO QUE SE LEEN, declarados. No es `todo lo que tenga .value`: los
#: widgets levantan `KeyError` al pedirselo si nadie los ha tocado, y taparlo con un
#: `try` seria tragarse un error (regla 2). Aqui van los que PINTAN texto — incluidas las
#: tablas, que es donde estan la mitad de las etiquetas de posicion.
TIPOS_QUE_PINTAN = (
    "markdown", "caption", "info", "warning", "error", "success", "text", "code",
    "title", "header", "subheader", "dataframe", "table", "metric", "html",
    "exception", "divider_text",
)


def _texto_de_la_pagina(at) -> str:
    """TODO lo que se ve, incluidas las tablas. Lo que no se recoge no se comprueba."""
    piezas = []
    for elemento in at.main:
        if getattr(elemento, "type", "") not in TIPOS_QUE_PINTAN:
            continue
        valor = getattr(elemento, "value", None)
        if valor is not None:
            piezas.append(valor if isinstance(valor, str) else str(valor))
    return "\n".join(piezas)


@unittest.skipUnless(HAY, "NOT_RUN: falta Streamlit, un fixture o mature.fa")
class TestLaPaginaLlegaAlFinal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import os
        import tempfile

        cls._tmp = tempfile.TemporaryDirectory()
        cls._antes = os.environ.get("SHMIR_PROJECT_DIR")
        os.environ["SHMIR_PROJECT_DIR"] = cls._tmp.name
        slug = _proyecto_con_una_corrida(Path(cls._tmp.name))

        at = AppTest.from_file(str(PAGINA), default_timeout=900)
        at.run()
        opcion = next(
            o for o in at.selectbox(key="p0_slug").options if o.startswith(slug)
        )
        at.selectbox(key="p0_slug").select(opcion).run()
        at.button(key="p0_abrir").click().run()
        at.run()
        cls.at = at
        cls.texto = _texto_de_la_pagina(at)

    @classmethod
    def tearDownClass(cls):
        import os

        if cls._antes is None:
            os.environ.pop("SHMIR_PROJECT_DIR", None)
        else:
            os.environ["SHMIR_PROJECT_DIR"] = cls._antes
        cls._tmp.cleanup()

    def test_la_corrida_guardada_llega_a_la_pagina(self):
        # Si esto falla, el resto no prueba nada: seria la pagina sin proyecto otra vez,
        # que es justo lo que el golden ya cubre.
        self.assertIn("Mus musculus", [s.value for s in self.at.subheader])
        self.assertIn("percentil", self.texto.lower())

    def test_no_hay_ningun_PARA(self):
        rojos = [e.value for e in self.at.error if "**PARA**" in e.value]
        self.assertEqual(rojos, [], "\n".join(rojos))

    def test_ni_ninguna_excepcion_sin_recoger(self):
        self.assertEqual([str(e.value) for e in self.at.exception], [])

    def test_llega_HASTA_EL_FINAL_descargas_y_paso_5(self):
        titulos = [s.value for s in self.at.subheader]
        self.assertIn("Descargas", titulos, titulos)
        self.assertTrue(
            any(t.startswith("5)") for t in titulos),
            f"la página no llega al paso 5: {titulos}",
        )

    def test_ninguna_etiqueta_3utr_se_sale_del_3UTR_de_ESTE_proyecto(self):
        import re

        tope = _utr3_length()
        fuera = sorted(
            {
                int(n) for n in re.findall(r"3utr:(\d+)", self.texto)
                if int(n) > tope
            }
        )
        self.assertEqual(
            fuera, [],
            f"la página etiqueta como 3'UTR posiciones que no caben en su 3'UTR de "
            f"{tope} nt: {fuera}. Son coordenadas del transcrito con el marco "
            f"equivocado; el techo de `coords` (1606) sólo caza las que lo pasan.",
        )


if __name__ == "__main__":
    unittest.main()
