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

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.external_score import EXTERNAL_TOOLS  # noqa: E402
from shmir_design.fetch import parse_fasta_payload  # noqa: E402
from shmir_design.hard_filters import DEFAULT_THRESHOLDS, Thresholds  # noqa: E402
from shmir_design.blast import DEFAULTS as DEFAULT_BLAST  # noqa: E402
from shmir_design.masking import RepeatMask  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402
from shmir_design.presentation import (  # noqa: E402
    BLAST_MODAL_NOTE,
    blast_candidate_rows,
    blast_command_text,
    blast_params_from_form,
    blast_executor_text,
    blast_query,
    blast_setting_rows,
    blast_warnings,
    anatomy_rows,
    candidate_rows,
    cost_text,
    map_svg,
    block_rows,
    conservation_for,
    output_bundle,
    status_light,
    window_rows,
)
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    PACKAGE_REFERENCE_DIR,
    REFERENCES,
    extract_3utr,
    sequence_md5,
)
from shmir_design.resources import load_from_manifest  # noqa: E402
from shmir_design.resolve import check_boundaries, resolve_anatomy  # noqa: E402
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


PISTA_UI = (
    "\nEn esta pagina: sube el `.gb` del RefSeq junto al FASTA, o declara las "
    "coordenadas\ndel CDS, o marca la casilla que dice que lo que has subido YA es el "
    "3'UTR."
)


def anatomia(sequence: str, etiqueta: str, genbank_file):
    """Resuelve la anatomia por las mismas tres vias que el CLI, o aborta.

    Aqui NO hay ningun valor por defecto que convierta un "no se" en un "todo es
    3'UTR": esa era la version anterior, y por eso un mRNA completo se tilaba entero
    como si fuera 3'UTR sin que nadie lo hubiera declarado. La decision la toma
    `resolve.resolve_anatomy`, que es la misma funcion que usa la consola.
    """
    md5 = sequence_md5(sequence)
    for reference in REFERENCES.values():
        if reference.md5 == md5:
            return reference, Anatomy.from_cds(
                cds=reference.cds,
                length=len(sequence),
                source=RegionSource.FIXTURE_VERIFICADO,
            )

    st.warning(
        f"**{etiqueta}**: el mRNA no coincide con ninguna referencia verificada "
        f"(md5 `{md5}`). No hay deteccion de ORF en el nucleo, asi que la anatomia la "
        f"declaras tu — y hasta que la declares no se tila nada."
    )
    if genbank_file is not None:
        ruta = Path(tempfile.mkdtemp()) / genbank_file.name
        ruta.write_bytes(genbank_file.getvalue())
        return None, resolve_anatomy(
            name=etiqueta, sequence=sequence, genbank=ruta, hint=PISTA_UI
        )

    ya_es_utr3 = st.checkbox(
        f"{etiqueta} — lo que he subido YA es el 3'UTR entero",
        key=f"{etiqueta}_ya_utr3",
        help="Marca esto solo si el FASTA no lleva ni 5'UTR ni CDS.",
    )
    if ya_es_utr3:
        return None, resolve_anatomy(
            name=etiqueta, sequence=sequence, whole_is_utr3=True, hint=PISTA_UI
        )

    declarar = st.checkbox(
        f"{etiqueta} — declarar las coordenadas del CDS a mano",
        key=f"{etiqueta}_declarar_cds",
        help="1-based e inclusivas, como las escribe GenBank. El codon de parada se "
             "comprueba: es lo que caza el off-by-one.",
    )
    if not declarar:
        # Sin via elegida no se sigue. El mensaje es el del nucleo, con las tres vias.
        return None, resolve_anatomy(
            name=etiqueta, sequence=sequence, hint=PISTA_UI
        )
    inicio = st.number_input(
        f"{etiqueta} — inicio del CDS (1-based)",
        min_value=1, max_value=len(sequence), value=1,
        key=f"{etiqueta}_cds_inicio",
    )
    fin = st.number_input(
        f"{etiqueta} — fin del CDS (incluye el codon de parada)",
        min_value=int(inicio), max_value=len(sequence), value=len(sequence),
        key=f"{etiqueta}_cds_fin",
    )
    return None, resolve_anatomy(
        name=etiqueta, sequence=sequence, cds=(int(inicio), int(fin)), hint=PISTA_UI
    )


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


def _utr3(secuencia: str, anat) -> str:
    """El tramo 3'UTR de la secuencia, segun la anatomia ya resuelta."""
    inicio, fin = anat.utr3
    return secuencia[inicio - 1 : fin]


def bloque_especie(nombre, transcrito, secuencia, anat, umbrales, config, seeds, mask,
                   scaffold, conservacion, recursos, accesibilidad) -> dict[str, str]:
    st.subheader(f"{nombre}")
    extra = dict(recursos.as_kwargs()) if recursos is not None else {}
    if mask is not None:
        extra["mask"] = mask  # la mascara subida a mano manda sobre la del manifiesto
    # Se tila la secuencia ENTERA con su anatomia, como el CLI: asi las coordenadas de
    # transcrito son coordenadas de transcrito de verdad y no una copia de las del
    # 3'UTR. Que ventanas entran lo decide `TileRange`, en el nucleo.
    tiling = tile_utr(
        secuencia, anatomy=anat, seeds=seeds, thresholds=umbrales,
        accessibility=accesibilidad, **extra
    )
    seleccion = select_from_report(tiling, config)
    utr3 = _utr3(secuencia, anat)

    semaforo(status_light(seleccion))

    st.markdown("**Anatomía del transcrito**")
    st.dataframe(
        anatomy_rows(transcrito, utr3_length=len(utr3), anatomy=anat), hide_index=True
    )

    st.markdown("**Mapa del 3'UTR**")
    st.html(map_svg(tiling, seleccion, conservation=conservacion, species=nombre))

    st.markdown("**Candidatos** — un estado por filtro, en columnas separadas")
    filas = candidate_rows(seleccion)
    if filas:
        st.dataframe(filas, hide_index=True)
    else:
        st.info("Ningún candidato con estos umbrales.")

    _modal_blast(seleccion, nombre)

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

    # Los tres servicios externos a los que se contrasta un diseño, arriba y visibles
    # antes de subir nada. Las direcciones y sus textos viven en
    # `external_score.EXTERNAL_TOOLS`: la pagina no tiene datos propios (regla 6).
    enlaces = st.columns(len(EXTERNAL_TOOLS) + 2)
    for columna, herramienta in zip(enlaces, EXTERNAL_TOOLS):
        with columna:
            st.link_button(
                f"↗ {herramienta.name}", herramienta.url, help=herramienta.tooltip,
                width="stretch",
            )
    st.caption(
        "Servicios externos, para contrastar. Sus direcciones no se han podido "
        "comprobar desde este entorno y **ningun codigo las llama**: se abren a mano. "
        "El score que devuelva miRarchitect entra por `tools/import_scores.py`, nunca "
        "calculado aqui."
    )
    st.divider()

    umbrales, config, min_bloque = panel_umbrales()

    st.sidebar.header("Ficheros de referencia")
    usar_manifiesto = st.sidebar.checkbox(
        "Usar los de data/reference/",
        help=(
            "Conecta cada fichero que este en OK con el filtro que le toca, con la "
            "version y el md5 del manifiesto. Sin esto, todos esos filtros quedan en "
            "NOT_RUN y el semaforo no puede llegar a verde."
        ),
    )
    gen_diana = st.sidebar.text_input(
        "Gen diana (accession)", "",
        help="Hace falta para la especificidad: es un accession, no un fichero, y el "
             "manifiesto no lo sabe.",
    )
    accesibilidad = st.sidebar.checkbox(
        "Calcular accesibilidad (lento)",
        help="Criterio de desempate, nunca filtro. Añade dos plegados por candidato.",
    )

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
        gb_modelo = st.file_uploader(
            "GenBank de la especie modelo (.gb, opcional)", type=["gb", "gbk", "genbank"],
            help="El CDS anotado del RefSeq. Es la via mas fiable de resolver la "
                 "anatomia: sin el, las coordenadas del CDS las tecleas tu.",
        )
    with columnas[1]:
        diana = st.file_uploader(
            "mRNA — segunda especie (opcional)", type=["fa", "fasta", "txt"]
        )
        nombre_diana = st.text_input("Nombre de la segunda especie", "diana")
        gb_diana = st.file_uploader(
            "GenBank de la segunda especie (.gb, opcional)",
            type=["gb", "gbk", "genbank"],
            help="Lo mismo para la segunda especie.",
        )

    if not modelo:
        st.info(
            "Sube al menos un FASTA de mRNA para empezar. Con dos se buscan ademas los "
            "bloques conservados entre ellos."
        )
        return
    if diana and nombre_diana == nombre_modelo:
        st.error(
            f"**PARA** — las dos especies se llaman igual ({nombre_modelo!r}); "
            f"renombra una para no mezclar sus salidas."
        )
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

        # El cableado fichero->filtro vive en `manifest.ROLES` y la carga en
        # `resources.py`, las dos con tests. Aqui solo se pide y se enseña.
        recursos = None
        if usar_manifiesto:
            recursos = load_from_manifest(
                PACKAGE_REFERENCE_DIR, target=gen_diana.strip() or None
            )

        secuencias = {nombre_modelo: _fasta_sequence(modelo)}
        genbanks = {nombre_modelo: gb_modelo}
        if diana:
            secuencias[nombre_diana] = _fasta_sequence(diana)
            genbanks[nombre_diana] = gb_diana
    except (ShmirDesignError, ValueError, OSError) as exc:
        # rule2-ok: frontera de la interfaz. El fallo se enseña entero al usuario y no
        # se pinta ningun resultado: no hay degradado silencioso.
        st.error(f"**PARA** — {exc}")
        return

    if recursos is not None:
        with st.expander(
            f"Ficheros de referencia conectados ({len(recursos.connected)})",
            expanded=not recursos.connected,
        ):
            st.code(recursos.format_text(), language=None)

    if not scaffold.verified:
        st.warning(
            "**ANDAMIO_NO_VERIFICADO** — las secuencias flanqueantes de este andamio no "
            "han sido contrastadas contra la publicación original. El aviso viaja "
            "también en cada fila del TSV de oligos y no se puede silenciar."
        )

    # Dos botones, y ninguno de los dos calcula nada por su cuenta: fijan que se pidio.
    # Sin esto la pagina lanzaba el diseño entero en cuanto se subia un FASTA, asi que
    # una corrida de minutos —manifiesto conectado y accesibilidad— empezaba sin avisar
    # y la estimacion no habria servido de nada: llegaba cuando ya estaba corriendo.
    acciones = st.columns([1, 1, 4])
    with acciones[0]:
        if st.button(
            "Estimar coste",
            help=(
                "Mide una invocacion real de cada filtro caro y multiplica. No diseña "
                "nada: sirve para saber si esto son segundos o minutos."
            ),
        ):
            st.session_state["accion"] = "estimar"
    with acciones[1]:
        if st.button("Diseñar", type="primary"):
            st.session_state["accion"] = "diseñar"

    accion = st.session_state.get("accion")
    if accion is None:
        st.info(
            "Todo listo. **Estimar coste** dice cuanto va a tardar sin diseñar nada; "
            "**Diseñar** lanza la corrida."
        )
        return

    try:
        # La anatomia se resuelve UNA vez por especie: si el mRNA no coincide con una
        # referencia verificada, aqui es donde se piden las coordenadas del 3'UTR.
        anatomias = {
            nombre: anatomia(secuencia, nombre, genbanks[nombre])
            for nombre, secuencia in secuencias.items()
        }
        # El codon de parada es aviso duro, igual que en el CLI: un CDS corrido corre
        # tambien el 3'UTR y con el todos los tercios.
        avisos_anatomia = {
            nombre: check_boundaries(secuencias[nombre], anat)
            for nombre, (_, anat) in anatomias.items()
        }
        for nombre, avisos in avisos_anatomia.items():
            for aviso in avisos:
                st.warning(f"**{nombre}** — {aviso}")

        if accion == "estimar":
            for nombre, (_, anat) in anatomias.items():
                st.subheader(f"{nombre} — estimacion")
                st.code(
                    cost_text(
                        _utr3(secuencias[nombre], anat),
                        resources=recursos,
                        accessibility=accesibilidad,
                        thresholds=umbrales,
                    ),
                    language=None,
                )
            return
        # La decision de si hay algo que comparar vive en presentation.py, con test:
        # la pagina no decide nada.
        conservacion = conservation_for(
            {
                nombre: _utr3(secuencias[nombre], anat)
                for nombre, (_, anat) in anatomias.items()
            },
            min_length=min_bloque,
            thresholds=umbrales,
        )
        if conservacion is None:
            st.info(
                "Una sola especie: no hay bloques conservados que buscar. Sube una "
                "segunda para compararlas."
            )

        ficheros: dict[str, str] = {}
        for nombre, (transcrito, anat) in anatomias.items():
            ficheros.update(
                bloque_especie(
                    nombre, transcrito, secuencias[nombre], anat, umbrales, config,
                    seeds, mask, scaffold, conservacion, recursos, accesibilidad,
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


def _modal_blast(seleccion, nombre: str) -> None:
    """El modal de especificidad. NO decide nada: todo viene de `presentation`.

    La pagina no ordena, no marca en rojo y no elige ningun estado — recibe filas con un
    booleano `modificado` y avisos con un booleano `bloquea`. Si aqui empieza a haber una
    condicion sobre datos, se mueve a `presentation.py` (regla 6).
    """
    if not st.checkbox(
        f"Especificidad (BLAST) — {nombre}",
        key=f"blast_{nombre}",
        help=(
            "Prepara la consulta y recoge el resultado. Este software NO lanza el "
            "BLAST: el navegador no puede llamar a NCBI (CORS) y el backend no tiene "
            "red saliente."
        ),
    ):
        return

    st.caption(blast_executor_text())
    st.caption(BLAST_MODAL_NOTE)

    filas = blast_candidate_rows(seleccion, species=nombre)
    todos = st.checkbox("Todos", key=f"blast_todos_{nombre}", value=True)
    solo_panel = st.checkbox(
        "Sólo los del panel", key=f"blast_panel_{nombre}", value=False
    )
    guias = st.checkbox("Guías", key=f"blast_guias_{nombre}", value=True)
    pasajeras = st.checkbox("Pasajeras", key=f"blast_pas_{nombre}", value=True)

    marcados = []
    for fila in filas:
        if solo_panel and not fila["panel"]:
            continue
        if st.checkbox(
            f"3utr:{fila['start']}  asim {fila['asimetria']}  {fila['veredicto']}",
            key=f"blast_c_{nombre}_{fila['start']}",
            value=todos,
        ):
            marcados.append(fila["start"])

    st.subheader("Ajustes")
    valores = {}
    for ajuste in blast_setting_rows(DEFAULT_BLAST):
        etiqueta = ajuste["ajuste"]
        if ajuste["modificado"]:
            etiqueta = f":red[{etiqueta}]"
        valores[ajuste["ajuste"]] = st.text_input(
            etiqueta,
            value=ajuste["valor"],
            key=f"blast_s_{nombre}_{ajuste['ajuste']}",
            help=f"por defecto: {ajuste['por_defecto']}",
        )

    params = blast_params_from_form(valores)
    for fila in blast_setting_rows(params):
        if fila["modificado"]:
            st.markdown(
                f":red[**{fila['ajuste']} = {fila['valor']}**] "
                f"(por defecto {fila['por_defecto']})"
            )

    for aviso in blast_warnings(params):
        (st.error if aviso["bloquea"] else st.warning)(aviso["texto"])

    ruta = f"{nombre}_consulta.fasta"
    st.code(blast_command_text(params, query_path=ruta, out_path=f"{nombre}_blast.tsv"))

    if marcados and (guias or pasajeras):
        consulta = blast_query(
            seleccion, species=nombre, starts=tuple(marcados),
            guides=guias, passengers=pasajeras,
        )
        st.caption(consulta.describe())
        st.download_button(
            "Descargar el FASTA de consulta",
            data=consulta.text,
            file_name=ruta,
            key=f"blast_dl_{nombre}",
        )
        st.file_uploader(
            "Soltar aquí el resultado (-outfmt 6)",
            key=f"blast_up_{nombre}",
            help=(
                "Se valida contra el md5 del FASTA de consulta y contra los nombres del "
                "panel antes de almacenarse. Un resultado de otra corrida se rechaza."
            ),
        )
    else:
        st.info(
            "Marca al menos un candidato y guía o pasajera para generar la consulta."
        )
