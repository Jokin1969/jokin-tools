"""Interfaz Streamlit sobre el nucleo de shmir-design.

**Esta capa no tiene logica.** Todo lo que decide algo —el semaforo, las filas de las
tablas, el mapa, los ficheros de salida— vive en `shmir_design/presentation.py` y en el
resto del nucleo, y tiene tests. Aqui solo se recogen entradas, se llama y se pinta.

    pip install -r apps/shmir-design/requirements-ui.txt
    streamlit run apps/shmir-design/ui/streamlit_app.py

El nucleo sigue siendo stdlib pura: Streamlit es una dependencia SOLO de esta interfaz
(ver `docs/dependencias-autorizadas.md`). El CLI funciona sin ella.
"""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from shmir_design.conservation import Utr3, build_conservation_report  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.fetch import parse_fasta_payload  # noqa: E402
from shmir_design.hard_filters import DEFAULT_THRESHOLDS, Thresholds  # noqa: E402
from shmir_design.masking import RepeatMask  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402
from shmir_design.presentation import (  # noqa: E402
    anatomy_rows,
    candidate_rows,
    map_svg,
    block_rows,
    output_bundle,
    status_light,
    window_rows,
)
from shmir_design.reference import REFERENCES, extract_3utr, sequence_md5  # noqa: E402
from shmir_design.scaffold import SGEP_SCAFFOLD, load_scaffold  # noqa: E402
from shmir_design.seeds import BOOTSTRAP_SEEDS, parse_seed_table  # noqa: E402
from shmir_design.selection import (  # noqa: E402
    DEFAULT_CANDIDATES,
    DEFAULT_MIN_SPACING,
    SelectionConfig,
    select_from_report,
)
from shmir_design.tiling import tile_utr  # noqa: E402

COLORES = {"verde": ("#2f7d5d", "🟢"), "ambar": ("#b58900", "🟠")}


def _read_upload(upload) -> str:
    return upload.getvalue().decode("utf-8")


def _fasta_sequence(upload) -> str:
    """Parseo y validacion con las mismas funciones que usa el CLI."""
    _, secuencia = parse_fasta_payload(_read_upload(upload), source=upload.name)
    return normalize_sequence(secuencia, name=f"secuencia de {upload.name}")


def anatomia_y_utr3(sequence: str, etiqueta: str):
    """Si el mRNA coincide con una referencia verificada, usa SU anatomia.

    Si no coincide, NO se adivina el ORF: las coordenadas las declara quien sube el
    fichero, y quedan marcadas como no verificadas.
    """
    md5 = sequence_md5(sequence)
    for reference in REFERENCES.values():
        if reference.md5 == md5:
            return reference, extract_3utr(sequence, reference)

    st.warning(
        f"**{etiqueta}**: el mRNA no coincide con ninguna referencia verificada "
        f"(md5 `{md5}`). No hay deteccion de ORF en el nucleo, asi que las coordenadas "
        f"del 3'UTR las declaras tu y salen marcadas como no verificadas."
    )
    inicio = st.number_input(
        f"{etiqueta} — inicio del 3'UTR (1-based)",
        min_value=1,
        max_value=len(sequence),
        value=1,
        key=f"{etiqueta}_inicio",
    )
    fin = st.number_input(
        f"{etiqueta} — fin del 3'UTR",
        min_value=int(inicio),
        max_value=len(sequence),
        value=len(sequence),
        key=f"{etiqueta}_fin",
    )
    return None, sequence[int(inicio) - 1 : int(fin)]


def panel_umbrales() -> tuple[Thresholds, SelectionConfig, int]:
    st.sidebar.header("Umbrales")
    st.sidebar.caption(
        "Cada control trae su valor por defecto, que es el verificado del proyecto."
    )
    gc_min = st.sidebar.number_input(
        f"GC mínimo (por defecto: {DEFAULT_THRESHOLDS.gc_min})",
        0.0, 1.0, DEFAULT_THRESHOLDS.gc_min, step=0.01,
    )
    gc_max = st.sidebar.number_input(
        f"GC máximo (por defecto: {DEFAULT_THRESHOLDS.gc_max})",
        0.0, 1.0, DEFAULT_THRESHOLDS.gc_max, step=0.01,
    )
    homopolimero = st.sidebar.number_input(
        f"Homopolímero máximo (por defecto: {DEFAULT_THRESHOLDS.max_homopolymer})",
        1, 22, DEFAULT_THRESHOLDS.max_homopolymer,
    )
    asimetria = st.sidebar.number_input(
        f"Asimetría mínima, kcal/mol (por defecto: {DEFAULT_THRESHOLDS.min_asymmetry})",
        -10.0, 10.0, DEFAULT_THRESHOLDS.min_asymmetry, step=0.1,
    )
    flanco = st.sidebar.number_input(
        f"Flanco prohibido alrededor de la señal polyA, nt "
        f"(por defecto: {DEFAULT_THRESHOLDS.polya_flank})",
        0, 200, DEFAULT_THRESHOLDS.polya_flank,
    )

    st.sidebar.header("Selección")
    candidatos = st.sidebar.number_input(
        f"Candidatos por especie (por defecto: {DEFAULT_CANDIDATES})",
        1, 100, DEFAULT_CANDIDATES,
    )
    espaciado = st.sidebar.number_input(
        f"Espaciado mínimo entre sitios, nt (por defecto: {DEFAULT_MIN_SPACING})",
        0, 2000, DEFAULT_MIN_SPACING,
        help="Se mide entre las posiciones de inicio de los candidatos elegidos.",
    )
    bloque = st.sidebar.number_input(
        "Longitud mínima de bloque conservado, nt (por defecto: 15)", 4, 200, 15
    )

    return (
        Thresholds(
            gc_min=float(gc_min),
            gc_max=float(gc_max),
            max_homopolymer=int(homopolimero),
            min_asymmetry=float(asimetria),
            polya_flank=int(flanco),
        ),
        SelectionConfig(n_candidates=int(candidatos), min_spacing=int(espaciado)),
        int(bloque),
    )


def semaforo(luz) -> None:
    color, emoji = COLORES[luz.color]
    st.markdown(
        f'<div style="border-left:8px solid {color};background:#faf8f3;'
        f'padding:14px 18px;border-radius:6px;margin-bottom:14px">'
        f'<div style="font-size:1.15rem;font-weight:700;color:{color}">'
        f"{emoji} {luz.headline}</div>"
        f'<div style="color:#4a443a;margin-top:6px">{luz.detail}</div></div>',
        unsafe_allow_html=True,
    )


def bloque_especie(nombre, transcrito, utr3, umbrales, config, seeds, mask, scaffold,
                   conservacion) -> dict[str, str]:
    st.subheader(f"{nombre}")
    tiling = tile_utr(utr3, seeds=seeds, mask=mask, thresholds=umbrales)
    seleccion = select_from_report(tiling, config)

    semaforo(status_light(seleccion))

    st.markdown("**Anatomía del transcrito**")
    st.dataframe(anatomy_rows(transcrito, utr3_length=len(utr3)), hide_index=True)

    st.markdown("**Mapa del 3'UTR**")
    st.html(map_svg(tiling, seleccion, conservation=conservacion, species=nombre))

    st.markdown("**Candidatos** — un estado por filtro, en columnas separadas")
    filas = candidate_rows(seleccion)
    if filas:
        st.dataframe(filas, hide_index=True)
    else:
        st.info("Ningún candidato con estos umbrales.")

    with st.expander(f"Todas las ventanas de {nombre} ({len(tiling.windows)})"):
        st.dataframe(window_rows(tiling), hide_index=True)

    bloques = st.checkbox(
        f"Generar los bloques listos para pedir de {nombre}",
        key=f"bloques_{nombre}",
        help=(
            "Modulo NheI-SacI de 149 nt y cassette MluI-AgeI de 318 pb, con y sin "
            "brazos de homologia, mas la hoja de pedido."
        ),
    )
    if bloques and seleccion.selection.chosen:
        st.dataframe(block_rows(seleccion, scaffold), hide_index=True)
        st.caption(
            "XhoI y EcoRI van DENTRO del modulo, heredadas de SGEP, y en el plasmido "
            "final no son unicas: el clonaje va por NheI/SacI o por sintesis. "
            "`modulo_seguro = no` significa que no se ha confirmado que la horquilla "
            "sobreviva dentro del intron."
        )

    return output_bundle(
        species=nombre,
        tiling=tiling,
        selection=seleccion,
        scaffold=scaffold,
        transcript=transcrito,
        conservation=conservacion,
        blocks=bloques,
    )


def main() -> None:
    st.set_page_config(page_title="shmir-design", layout="wide")
    st.title("shmir-design")
    st.caption(
        "Interfaz sobre el núcleo ya testado. Ninguna decisión se toma aquí: esta "
        "página solo llama a funciones con tests."
    )

    umbrales, config, min_bloque = panel_umbrales()

    st.sidebar.header("Recursos externos (opcionales)")
    seeds_file = st.sidebar.file_uploader("Tabla de seeds `seed familia`", type=["txt", "tsv"])
    usar_arranque = st.sidebar.checkbox(
        "Usar la lista de arranque de 12 seeds (mecánica, NO filtro real)"
    )
    repeats_file = st.sidebar.file_uploader("Repeticiones `inicio fin`", type=["txt", "tsv", "bed"])
    scaffold_file = st.sidebar.file_uploader("Andamio (TOML)", type=["toml"])

    columnas = st.columns(2)
    with columnas[0]:
        modelo = st.file_uploader("mRNA — especie modelo", type=["fa", "fasta", "txt"])
        nombre_modelo = st.text_input("Nombre de la especie modelo", "modelo")
    with columnas[1]:
        diana = st.file_uploader("mRNA — especie diana", type=["fa", "fasta", "txt"])
        nombre_diana = st.text_input("Nombre de la especie diana", "diana")

    if not modelo or not diana:
        st.info("Sube los dos FASTA de mRNA para empezar.")
        return

    try:
        seeds = BOOTSTRAP_SEEDS if usar_arranque else None
        if seeds_file is not None:
            seeds = parse_seed_table(_read_upload(seeds_file), source=seeds_file.name)
        mask = None
        if repeats_file is not None:
            intervalos = tuple(
                (int(a), int(b))
                for a, b in (
                    linea.split()
                    for linea in _read_upload(repeats_file).splitlines()
                    if linea.strip() and not linea.startswith("#")
                )
            )
            mask = RepeatMask(intervals=intervalos, source=repeats_file.name)
        scaffold = SGEP_SCAFFOLD
        if scaffold_file is not None:
            ruta = Path(tempfile.mkdtemp()) / scaffold_file.name
            ruta.write_bytes(scaffold_file.getvalue())
            scaffold = load_scaffold(ruta)

        secuencias = {
            nombre_modelo: _fasta_sequence(modelo),
            nombre_diana: _fasta_sequence(diana),
        }
    except (ShmirDesignError, ValueError, OSError) as exc:
        # rule2-ok: frontera de la interfaz. El fallo se enseña entero al usuario y no
        # se pinta ningun resultado: no hay degradado silencioso.
        st.error(f"**PARA** — {exc}")
        return

    if not scaffold.verified:
        st.warning(
            "**ANDAMIO_NO_VERIFICADO** — las secuencias flanqueantes de este andamio no "
            "han sido contrastadas contra la publicación original. El aviso viaja "
            "también en cada fila del TSV de oligos y no se puede silenciar."
        )

    try:
        # La anatomia se resuelve UNA vez por especie: si el mRNA no coincide con una
        # referencia verificada, aqui es donde se piden las coordenadas del 3'UTR.
        anatomias = {
            nombre: anatomia_y_utr3(secuencia, nombre)
            for nombre, secuencia in secuencias.items()
        }
        conservacion = build_conservation_report(
            Utr3(nombre_modelo, anatomias[nombre_modelo][1]),
            Utr3(nombre_diana, anatomias[nombre_diana][1]),
            min_length=min_bloque,
            thresholds=umbrales,
        )

        ficheros: dict[str, str] = {}
        for nombre, (transcrito, utr3) in anatomias.items():
            ficheros.update(
                bloque_especie(
                    nombre, transcrito, utr3, umbrales, config, seeds, mask, scaffold,
                    conservacion,
                )
            )
    except (ShmirDesignError, ValueError, OSError) as exc:
        # rule2-ok: frontera de la interfaz, mismo criterio que arriba.
        st.error(f"**PARA** — {exc}")
        return

    st.subheader("Descargas")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in sorted(ficheros.items()):
            zf.writestr(nombre, contenido)
    st.download_button(
        "Descargar todo (zip)", buffer.getvalue(), "shmir-design.zip", "application/zip"
    )
    for nombre, contenido in sorted(ficheros.items()):
        st.download_button(nombre, contenido, nombre, "text/plain", key=f"dl_{nombre}")


if __name__ == "__main__":
    main()
