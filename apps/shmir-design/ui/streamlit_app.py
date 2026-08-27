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

import datetime
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
from shmir_design.seed_scan import DEFAULTS as SEED_DEFAULTS  # noqa: E402
from shmir_design.offtarget import DEFAULTS as OFFTARGET_DEFAULTS  # noqa: E402
from shmir_design.masking import RepeatMask  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402
from shmir_design.presentation import (  # noqa: E402
    WHY_A_RUN_FINGERPRINT,
    BLAST_MODAL_NOTE,
    anatomy_payload,
    load_stores,
    run_fingerprint,
    intron_geometry_text,
    stored_runs_note,
    upload_path,
    variant_proposal_for,
    reference_delete,
    reference_delete_plan,
    reference_download,
    reference_manager_rows,
    reference_preview,
    reference_replace_plan,
    library_delete,
    library_file,
    library_note,
    library_rows,
    library_save,
    project_create,
    project_list,
    project_open,
    project_rows,
    projects_root,
    save_blast_run,
    save_offtarget_run,
    save_seed_run,
    save_selection,
    save_splice_run,
    splice_run_from_scan,
    selected_starts,
    splice_construction_rows,
    splice_context_note,
    splice_constructions,
    splice_exclusive_rows,
    splice_executor_text,
    splice_folding_rows,
    splice_highlights,
    splice_intron_rows,
    splice_module_of,
    splice_query_text,
    splice_result_rows,
    splice_scan_from_result,
    splice_warning_rows,
    WHY_NO_GLOBAL_TOGGLE,
    accept_reference_upload,
    reference_panel_rows,
    reference_panel_summary,
    species_choice_note,
    species_default,
    species_needs_name,
    species_options,
    steps_rows,
    blast_candidate_rows,
    blast_command_text,
    blast_defaults_for,
    front_help_rows,
    informe_documento,
    informe_files,
    informe_state_text,
    obtencion_rows,
    offtarget_catalog_from_upload,
    offtarget_control_rows,
    offtarget_highlights,
    offtarget_limitation_rows,
    offtarget_params_from_form,
    offtarget_placeholder,
    offtarget_result_rows,
    offtarget_route_text,
    offtarget_run,
    offtarget_run_from_scan,
    offtarget_self_count_rows,
    offtarget_setting_rows,
    offtarget_upload_rows,
    offtarget_upper_bound,
    seed_highlights,
    selection_warnings,
    site_table_rows,
    vector_note,
    seed_load_placeholder,
    seed_preview_rows,
    seed_setting_rows,
    seed_source_text,
    seed_params_from_form,
    seed_result_rows,
    seed_run,
    seed_run_from_scan,
    blast_params_from_form,
    blast_run_from_upload,
    blast_executor_text,
    blast_query,
    blast_setting_rows,
    blast_warnings,
    anatomy_reliability,
    anatomy_rows,
    candidate_rows,
    cost_text,
    map_svg,
    page_run,
    block_rows,
    conservation_for,
    output_bundle,
    status_light,
    window_rows,
)
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.filters import FilterState  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES,
    extract_3utr,
    sequence_md5,
)
from shmir_design.resources import load_from_manifest  # noqa: E402
from shmir_design.trabajo import (  # noqa: E402
    WHY_A_WORKING_DIR,
    is_declared,
    reference_dir,
)
from shmir_design.species import resolve as resolve_species  # noqa: E402
from shmir_design.resolve import check_boundaries, resolve_anatomy  # noqa: E402
from shmir_design.scaffold import SGEP_SCAFFOLD, load_scaffold  # noqa: E402
from shmir_design.seeds import BOOTSTRAP_SEEDS, parse_seed_table  # noqa: E402
from shmir_design.selection import (  # noqa: E402
    DEFAULT_CANDIDATES,
    DEFAULT_MIN_SPACING,
    SelectionConfig,
    default_config,
)

COLORES = {"verde": ("#2f7d5d", "🟢"), "ambar": ("#b58900", "🟠")}


def _hoy() -> str:
    """La fecha de hoy como valor POR DEFECTO del campo, no como dato.

    La biblioteca no es procedencia: es una comodidad para no volver a buscar el mismo
    fichero. La fecha sirve para reconocerlo en la lista y se puede cambiar. Donde la
    fecha SI es procedencia —las corridas de los cuatro modales— se teclea, y ahi no hay
    ningun valor por defecto a proposito.
    """
    return datetime.date.today().isoformat()


def _panel_biblioteca(ranura: str, subido, *, ayuda: str = ""):
    """Un hueco del paso 2 con su biblioteca: guardar, elegir uno guardado, borrar.

    Devuelve LO QUE HAY QUE USAR: lo subido si se subió algo, y si no el elegido de la
    biblioteca. La página no decide nada aquí — las filas vienen montadas de
    `presentation` y el fichero guardado llega con la MISMA forma que uno subido, así
    que aguas abajo nadie se entera de por dónde vino.
    """
    filas = library_rows(ranura)
    with st.expander(f"📁 Guardados ({len(filas)})", expanded=False):
        st.caption(library_note())
        if subido is not None:
            fecha = st.text_input(
                "Fecha", value=_hoy(), key=f"bib_fecha_{ranura}",
                help="La que queda registrada junto al fichero.",
            )
            if st.button(f"Guardar «{subido.name}»", key=f"bib_add_{ranura}"):
                try:
                    fila = library_save(ranura, subido, date=fecha)
                except (ShmirDesignError, ValueError) as exc:
                    # rule2-ok: frontera de la interfaz. El motivo se enseña entero.
                    st.error(f"**NO se guardó** — {exc}")
                else:
                    st.success(f"Guardado: {fila['etiqueta']}")
                    st.rerun()
        if not filas:
            st.info("Nada guardado todavía en este hueco.")
            return subido

        elegido = st.selectbox(
            "Usar uno guardado",
            [f["id"] for f in filas],
            index=None,
            placeholder="ninguno",
            format_func=lambda i: next(f["etiqueta"] for f in filas if f["id"] == i),
            key=f"bib_pick_{ranura}",
            help=ayuda or None,
        )
        for fila in filas:
            if st.button(f"Borrar {fila['nombre']}", key=f"bib_del_{ranura}_{fila['id']}"):
                try:
                    ido = library_delete(ranura, fila["id"])
                except ShmirDesignError as exc:
                    # rule2-ok: frontera de la interfaz.
                    st.error(f"**NO se borró** — {exc}")
                else:
                    st.warning(f"Borrado: {ido}")
                    st.rerun()

    if subido is not None:
        return subido
    if elegido:
        return library_file(ranura, elegido)
    return None


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
        f"(md5 `{md5}`). No hay detección de ORF en el núcleo, así que la anatomía la "
        f"declaras tu — y hasta que la declares no se tila nada."
    )
    if genbank_file is not None:
        ruta = upload_path(tempfile.mkdtemp(), genbank_file.name)
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
        help="1-based e inclusivas, como las escribe GenBank. El codón de parada se "
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
        f"{etiqueta} — fin del CDS (incluye el codón de parada)",
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
        # `default_config` y no `SelectionConfig`: la cuota de inmunes va emparejada
        # con su frontera y `SelectionConfig` a secas no la lleva. Sin esto, la página
        # daba un panel con TRES inmunes mientras el golden daba cuatro — o sea, lo que
        # se revisa y lo que se ve dejaban de ser lo mismo.
        default_config(n_candidates=int(candidatos), min_spacing=int(espaciado)),
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
                   scaffold, conservacion, recursos, accesibilidad,
                   proyecto=None) -> dict[str, str]:
    st.subheader(f"{nombre}")
    # El camino de la corrida vive en `presentation.page_run`, no aquí. Esta página lo
    # rehacía a mano —tilaba y seleccionaba por su cuenta— y por eso se quedó sin la
    # tabla de APA medido que el CLI sí aplica: el mismo mRNA daba un panel por consola y
    # otro por navegador. Es la lección de `resolve.py`, y la cazó el análisis de
    # ALCANZABILIDAD: `page_run` existía, estaba testado y **nadie lo llamaba**.
    corrida = page_run(
        species=nombre, sequence=secuencia, anatomy=anat, thresholds=umbrales,
        config=config, seeds=seeds, mask=mask, accessibility=accesibilidad,
        resources=recursos,
    )
    tiling, seleccion, utr3 = corrida.tiling, corrida.selection, corrida.utr3

    semaforo(status_light(seleccion))

    st.markdown("**Anatomía del transcrito**")
    st.dataframe(
        anatomy_rows(transcrito, utr3_length=len(utr3), anatomy=anat), hide_index=True
    )

    st.markdown("**Mapa del 3'UTR**")
    st.html(map_svg(tiling, seleccion, conservation=conservacion, species=nombre))

    # La frontera del 3'UTR: de una ANOTACION o de una declaracion. No es lo mismo, y
    # lo que cuelga de ella no puede salir igual en los dos casos.
    fiabilidad = anatomy_reliability(anat)
    (st.success if fiabilidad["fiable"] else st.warning)(fiabilidad["texto"])

    st.markdown("**Candidatos** — un estado por filtro, en columnas separadas")
    filas = candidate_rows(seleccion)
    if filas:
        st.dataframe(filas, hide_index=True)
    else:
        st.info("Ningún candidato con estos umbrales.")

    # ── Todos los sitios elegibles, con UNA COLUMNA POR FRENTE ───────────────────
    # Es la vista que impide que vuelva a pasar lo de `offtarget_seed`: un frente sin
    # columna no se ve, y lo que no se ve no existe. Las columnas se derivan de los
    # frentes que el informe conoce, asi que uno nuevo aparece solo.
    with st.expander(
        f"Todos los sitios elegibles, con una columna por frente — {nombre}",
        expanded=False,
    ):
        clave = f"marcados_{nombre}"
        marcados = st.session_state.get(clave)
        st.caption(
            "La selección de la app viene marcada. Se puede cambiar a mano: los avisos "
            "de abajo se recalculan con lo que esté marcado."
        )
        st.dataframe(
            site_table_rows(tiling, seleccion, species=nombre, selected=marcados),
            hide_index=True,
        )
        for aviso in selection_warnings(tiling, seleccion, selected=marcados):
            (st.error if aviso["rojo"] else st.warning)(aviso["texto"])

    st.markdown("**Frentes** — y cómo cerrar los que están en NOT_RUN")
    for fila in front_help_rows(tiling, seleccion, species=nombre):
        etiqueta = "NOT_RUN" if fila["abierto"] else "CERRADO"
        with st.expander(f"{etiqueta} · {fila['frente']}", expanded=False):
            st.caption(fila["motivo"])
            st.code(fila["ficha"]["texto"], language=None)
            st.link_button(
                f"↗ {fila['ficha']['fuente']}", fila["ficha"]["url"],
                disabled=not fila["ficha"]["url"].startswith("http"),
            )

    # LO GUARDADO SE RELEE. `load_stores` estaba importado y no se llamaba desde ningún
    # sitio: al reabrir un proyecto volvía la selección y **los cuatro frentes salían de
    # nuevo NOT_RUN**, así que la persistencia servía para la mitad de lo que dice servir.
    # Es el mismo patrón que `store.save_*` y que `page_run`, tercera vez en dos días.
    if proyecto is not None:
        st.caption(stored_runs_note(load_stores(proyecto)))

    _modal_blast(seleccion, nombre, proyecto)
    _modal_seed(seleccion, nombre, tiling.mature, proyecto)
    _modal_offtarget(seleccion, nombre, tiling.mature, utr3, proyecto)
    _modal_empalme(seleccion, nombre, utr3, _casete_de(tiling), proyecto)
    _guardar_seleccion(proyecto, seleccion, nombre)

    with st.expander(f"Todas las ventanas de {nombre} ({len(tiling.windows)})"):
        st.dataframe(window_rows(tiling), hide_index=True)

    bloques = st.checkbox(
        f"Generar los bloques listos para pedir de {nombre}",
        key=f"bloques_{nombre}",
        help=(
            "Módulo NheI-SacI de 149 nt y cassette MluI-AgeI de 318 pb, con y sin "
            "brazos de homologia, más la hoja de pedido."
        ),
    )
    if bloques and seleccion.selection.chosen:
        aviso_vector = vector_note(nombre)
        if not aviso_vector["aplica"]:
            st.error(aviso_vector["texto"])
        else:
            st.caption(aviso_vector["texto"])
        st.dataframe(block_rows(seleccion, scaffold, species=nombre), hide_index=True)
        st.caption(
            "XhoI y EcoRI van DENTRO del módulo, heredadas de SGEP, y en el plásmido "
            "final no son únicas: el clonaje va por NheI/SacI o por síntesis. "
            "`modulo_seguro = no` significa que no se ha confirmado que la horquilla "
            "sobreviva dentro del intrón."
        )

    st.markdown("**Informe** — parcial o completo, en cualquier momento")
    documento = informe_documento(
        seleccion, tiling, species=nombre,
        generated=st.session_state.get("fecha_informe", "sin fecha declarada"),
        anatomy_source=anat.source.value if hasattr(anat, "source") else str(anat),
    )
    (st.warning if documento.state == "PARCIAL" else st.success)(
        informe_state_text(documento)
    )
    for entregable in informe_files(documento, stem=nombre):
        st.download_button(
            entregable["nombre"],
            data=entregable["datos"],
            file_name=entregable["nombre"],
            mime=entregable["mime"],
            key=f"inf_{nombre}_{entregable['nombre']}",
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



def _panel_proyecto(especie: str, secuencia: str, anat):
    """El proyecto: crear uno nuevo o abrir el de antes. Devuelve el almacén o `None`.

    Sin esto, los cuatro modales calculaban, pintaban y **al cerrar la pestaña no quedaba
    nada**: la capa de persistencia estaba entera y nadie escribía en ella. Un veredicto
    tiene que sobrevivir a la app que lo escribió.

    La página no decide nada: `presentation` crea, abre, lista y comprueba el md5.
    """
    # Las claves llevan la ESPECIE: `main()` llama a este panel una vez por especie, y
    # con dos, Streamlit aborta la página entera con `StreamlitDuplicateElementKey` —
    # que el `except` de `main()` no captura, porque no es un error nuestro.
    st.sidebar.header(f"Proyecto — {especie}")
    raiz = projects_root()
    existentes = project_list(raiz)

    if st.sidebar.checkbox(
        "Guardar esta corrida en un proyecto",
        key=f"pr_activo_{especie}",
        help="Las corridas de los modales y la selección quedan en un log de texto que "
             "se lee con `cat` y sobrevive a cerrar la pestaña.",
    ) is False:
        st.sidebar.caption(
            "Sin proyecto, lo que calculen los modales se pierde al cerrar la pestaña."
        )
        return None

    opciones = ["— crear uno nuevo —"] + [f["slug"] for f in existentes]
    elegido = st.sidebar.selectbox("Proyecto", opciones, key=f"pr_slug_{especie}")
    fecha = st.sidebar.text_input(
        "Fecha (AAAA-MM-DD)", "", key=f"pr_fecha_{especie}",
        help="Va en cada registro del log. Sin ella no es auditable.",
    )
    try:
        if elegido == opciones[0]:
            nombre = st.sidebar.text_input("Nombre del proyecto nuevo", "", key=f"pr_nuevo_{especie}")
            if not nombre or not fecha:
                st.sidebar.caption("Hace falta un nombre y una fecha para crearlo.")
                return None
            if not st.sidebar.button("Crear proyecto", key=f"pr_crear_{especie}"):
                return None
            payload, fuente = anatomy_payload(anat)
            almacen = project_create(
                raiz, slug=nombre, date=fecha, sequence=secuencia, species=especie,
                anatomy=payload, anatomy_source=fuente,
            )
        else:
            # El md5 se comprueba: seguir apuntando corridas de OTRA secuencia en este
            # log lo dejaría coherente de forma y nada lo delataría.
            almacen = project_open(raiz, elegido, expect_md5=sequence_md5(secuencia))
    except (ShmirDesignError, ValueError, OSError) as exc:
        # rule2-ok: frontera de la interfaz. El fallo se enseña entero.
        st.sidebar.error(f"**PARA** — {exc}")
        return None

    st.sidebar.success(f"Proyecto **{almacen.project.slug}** — {len(almacen.records())} registro(s)")
    if not almacen.project.reliable:
        st.sidebar.warning(almacen.project.why_unreliable)
    with st.sidebar.expander("Historial"):
        for fila in project_rows(almacen):
            st.write(f"{fila['n']}. `{fila['tipo']}` {fila['fecha']} — {fila['resumen']}")
    return almacen



def _fila_presente(fila, directorio) -> None:
    """Las CUATRO acciones de un fichero que está. Ninguna escondida tras un menú."""
    nombre = fila["nombre"]
    botones = st.columns(4)
    with botones[0]:
        ver = st.button("Ver", key=f"g_ver_{nombre}", width="stretch")
    with botones[1]:
        cambiar = st.toggle("Reemplazar", key=f"g_rep_{nombre}")
    with botones[2]:
        quitar = st.toggle("Borrar", key=f"g_del_{nombre}")
    with botones[3]:
        try:
            st.download_button(
                "Descargar", data=reference_download(nombre, directory=directorio),
                file_name=nombre, key=f"g_dl_{nombre}", width="stretch",
            )
        except ShmirDesignError as exc:
            # rule2-ok: frontera de la interfaz. El motivo entero, sin degradado.
            st.error(f"{exc}")

    if ver:
        vista = reference_preview(nombre, directory=directorio)
        st.caption(vista["cabecera"])
        st.code(vista["texto"])

    if cambiar:
        subido = st.file_uploader(
            f"Fichero nuevo para {nombre}", type=fila["extensiones"],
            key=f"g_up_{nombre}",
        )
        if subido is not None:
            plan = reference_replace_plan(
                nombre, directory=directorio, payload=subido.getvalue(),
                species=fila["especie"],
            )
            (st.warning if plan["invalida"] else st.info)(plan["texto"])
            fecha = st.text_input("Fecha", "", key=f"g_fecha_{nombre}")
            origen = st.text_input("De dónde salió", "", key=f"g_org_{nombre}")
            if st.button(f"Confirmar reemplazo de {nombre}", key=f"g_ok_{nombre}"):
                try:
                    hecho = accept_reference_upload(
                        fila["especie"], directory=directorio, filename=nombre,
                        payload=subido.getvalue(), date=fecha,
                        origin=origen or "reemplazado por la interfaz",
                    )
                except (ShmirDesignError, ValueError, OSError) as exc:
                    # rule2-ok: no se ha escrito nada y el motivo se enseña entero.
                    st.error(f"**RECHAZADO** — {exc}")
                else:
                    st.success(hecho["texto"])
                    st.rerun()

    if quitar:
        plan = reference_delete_plan(
            nombre, directory=directorio, species=fila["especie"]
        )
        st.warning(plan["texto"])
        if st.button(f"Confirmar borrado de {nombre}", key=f"g_okdel_{nombre}"):
            try:
                ido = reference_delete(nombre, directory=directorio)
            except (ShmirDesignError, OSError) as exc:
                # rule2-ok: frontera de la interfaz.
                st.error(f"**NO se borró** — {exc}")
            else:
                st.warning(ido)
                st.rerun()


def _fila_ausente(fila, directorio) -> None:
    """Subir, con la ficha de obtención desplegable justo debajo."""
    nombre = fila["nombre"]
    subido = st.file_uploader(
        f"Subir {nombre}", type=fila["extensiones"], key=f"g_new_{nombre}"
    )
    fecha = st.text_input("Fecha de descarga (AAAA-MM-DD)", "", key=f"g_nf_{nombre}")
    origen = st.text_input("De dónde salió", "", key=f"g_no_{nombre}")
    if subido is not None and st.button(f"Validar y registrar {nombre}", key=f"g_nb_{nombre}"):
        try:
            hecho = accept_reference_upload(
                fila["especie"], directory=directorio, filename=nombre,
                payload=subido.getvalue(), date=fecha,
                origin=origen or "subido por la interfaz",
            )
        except (ShmirDesignError, ValueError, OSError) as exc:
            # rule2-ok: el fichero NO se ha escrito y el motivo se enseña entero.
            st.error(f"**RECHAZADO** — {exc}")
        else:
            st.success(hecho["texto"])
            st.rerun()
    with st.expander(f"Cómo se consigue {nombre}", expanded=False):
        st.caption(fila["ficha"]["texto"])


def _panel_referencias(especie: str) -> None:
    """El GESTOR de ficheros de referencia. UNA tabla: presentes y ausentes juntos.

    Antes eran dos listas en dos sitios y había que mirar dos veces para saber en qué
    punto estabas. Y sobre lo que ya estaba no se podía hacer nada: el fichero entraba y
    dejaba de ser tuyo.

    La página no valida, no calcula ningún md5, no decide qué botones tocan y no sabe qué
    invalida qué: todo eso está en `gestor.py`, con tests. Aquí sólo se pinta.
    """
    st.header("Ficheros de referencia")
    if not especie:
        st.caption(
            "Elige una especie: los ficheros que hacen falta —y cómo se llaman— "
            "dependen de ella."
        )
        return

    directorio = reference_dir()
    resumen = reference_panel_summary(especie, directory=directorio)
    st.caption(
        f"{resumen['cerrables']} de {resumen['total']} frentes cerrables con lo que hay."
    )
    if is_declared():
        st.caption(f"Se guardan en `{directorio}`. {WHY_A_WORKING_DIR}")

    filas = reference_manager_rows(especie, directory=directorio)
    if filas and filas[0]["aviso_manifiesto"]:
        st.error(f"**Manifiesto ilegible** — {filas[0]['aviso_manifiesto']}")

    frente_actual = ""
    for fila in filas:
        if fila["frente"] != frente_actual:
            frente_actual = fila["frente"]
            st.subheader(frente_actual or "sin frente")
        with st.container(border=True):
            st.markdown(f"{fila['marca']} **{fila['nombre']}** — {fila['resumen']}")
            if fila["estado"] == "presente":
                _fila_presente(fila, directorio)
            else:
                _fila_ausente(fila, directorio)


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
        "comprobar desde este entorno y **ningun código las llama**: se abren a mano. "
        "El score que devuelva miRarchitect entra por `tools/import_scores.py`, nunca "
        "calculado aquí."
    )
    st.divider()

    umbrales, config, min_bloque = panel_umbrales()

    # ── PASO 1 · ESPECIE ────────────────────────────────────────────────────────
    #
    # Desplegable, no caja de texto. Y SIN valor por defecto: uno preseleccionado
    # —«modelo»— parece configurado y deja la colision de seed y la especificidad rotas
    # sin decir por que. Las opciones salen de `species.SPECIES`; la pagina no tiene
    # ninguna lista propia.
    st.subheader("1) Especie")
    opciones = species_options()
    elegida = st.selectbox(
        "Especie del diseño",
        [o["valor"] for o in opciones],
        index=species_default(),
        placeholder="elige una — no hay valor por defecto",
        format_func=lambda v: next(o["etiqueta"] for o in opciones if o["valor"] == v),
        help=(
            "Determina el prefijo de miRBase, el taxid y el ensamblaje. Ninguno de los "
            "tres se deduce del nombre."
        ),
    )
    nombre_modelo = elegida or ""
    if elegida is not None and species_needs_name(elegida):
        # Que frentes quedan cerrados se dice AL ELEGIR la opcion, no despues de
        # teclear un nombre: la pregunta que se esta contestando es «¿me sirve esta app
        # para mi especie?», y contestarla tarde es no contestarla.
        generico = species_choice_note(elegida)
        st.warning(generico["texto"])
        for cerrado in generico["cerrados"]:
            st.caption(f"· {cerrado}")
        st.caption(f"**Como declararla:** {generico['como_declararla']}")
        nombre_modelo = st.text_input(
            "Nombre científico de la especie",
            "",
            help="Se usa para nombrar sus ficheros. No la declara: eso se hace en species.py.",
        )
    if nombre_modelo and not species_needs_name(elegida or ""):
        nota = species_choice_note(nombre_modelo)
        if nota["bloquea"]:
            st.warning(nota["texto"])
            for cerrado in nota["cerrados"]:
                st.caption(f"· {cerrado}")
            st.caption(f"**Como declararla:** {nota['como_declararla']}")
        else:
            st.success(nota["texto"])


    st.sidebar.header("Otros ajustes")
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

    if not nombre_modelo:
        st.info(
            "Elige una especie para seguir. Sin ella no se sabe que ficheros hacen falta "
            "ni se puede comprobar que los que hay son de esta especie."
        )
        return

    # ── PASO 2 · SECUENCIA ──────────────────────────────────────────────────────
    st.subheader("2) Secuencia")
    columnas = st.columns(2)
    with columnas[0]:
        modelo = _panel_biblioteca(
            "mrna_diseno",
            st.file_uploader("mRNA — especie del diseño", type=["fa", "fasta", "txt"]),
        )
        gb_modelo = _panel_biblioteca(
            "genbank_diseno",
            st.file_uploader(
                "GenBank de la especie del diseño (.gb, PREFERENTE)",
                type=["gb", "gbk", "genbank"],
                help="El CDS anotado del RefSeq. Es la via más fiable de resolver la "
                     "anatomía: sin el, las coordenadas del CDS las tecleas tu y los "
                     "tercios salen NO_FIABLE.",
            ),
        )
    with columnas[1]:
        opciones_diana = [o for o in opciones if o["valor"] != nombre_modelo]
        nombre_diana = st.selectbox(
            "Segunda especie (opcional, para bloques conservados)",
            [o["valor"] for o in opciones_diana],
            index=None,
            placeholder="ninguna",
            format_func=lambda v: next(
                o["etiqueta"] for o in opciones_diana if o["valor"] == v
            ),
        )
        diana = _panel_biblioteca(
            "mrna_segunda",
            st.file_uploader(
                "mRNA — segunda especie (opcional)", type=["fa", "fasta", "txt"]
            ),
        )
        gb_diana = _panel_biblioteca(
            "genbank_segunda",
            st.file_uploader(
                "GenBank de la segunda especie (.gb, opcional)",
                type=["gb", "gbk", "genbank"],
                help="Lo mismo para la segunda especie.",
            ),
        )

    # ── PASO 3 · FICHEROS DE REFERENCIA ─────────────────────────────────────────
    #
    # El recuento va AQUI, antes de ejecutar nada: es lo que permite decidir si se sigue
    # o se va a buscar un fichero primero.
    st.subheader("3) Ficheros de referencia")
    pasos = steps_rows(
        species=nombre_modelo,
        sequence_loaded=modelo is not None,
        directory=reference_dir(),
    )
    st.info(pasos[2]["detalle"])
    # UNA sola tabla. Antes esto eran DOS sitios —la lista de frentes abiertos aquí y el
    # panel de subida en la barra lateral— y había que mirar dos veces para saber en qué
    # punto estabas. El gestor los junta: presentes y ausentes, ordenados por frente, con
    # lo que se puede hacer con cada uno en su propia fila.
    st.caption(WHY_NO_GLOBAL_TOGGLE)
    _panel_referencias(nombre_modelo)

    if not modelo:
        st.info(
            "Sube al menos un FASTA de mRNA para seguir. Con dos se buscan además los "
            "bloques conservados entre ellos."
        )
        return
    if diana and not nombre_diana:
        st.error(
            "**PARA** — has subido una segunda secuencia sin decir de que especie es. "
            "Sin especie no se puede comprobar que sus ficheros sean los suyos."
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
            ruta = upload_path(tempfile.mkdtemp(), scaffold_file.name)
            ruta.write_bytes(scaffold_file.getvalue())
            scaffold = load_scaffold(ruta)

        # El cableado fichero->filtro vive en `manifest.ROLES` y la carga en
        # `resources.py`, las dos con tests. Ya no hay casilla que lo active: si un
        # fichero esta y es valido, se usa. Ignorar uno se hace POR FICHERO y con el
        # motivo escrito (`deposito.Ignored`), que viaja al veredicto.
        # `species=` no es cosmetico: sin el, el manifiesto conecta cada fichero por su
        # ROL sin mirar que especie se esta diseñando, y `rmsk_mouse.out` cabe de sobra
        # en un transcrito humano sin salirse de rango. Es el mismo agujero que cierra
        # `RepeatMask.query_length` un nivel mas abajo.
        recursos = load_from_manifest(
            reference_dir(),
            target=gen_diana.strip() or None,
            species=resolve_species(nombre_modelo),
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

    # ── PASO 4 · DISEÑAR ────────────────────────────────────────────────────────
    #
    # Dos botones, y ninguno de los dos calcula nada por su cuenta: fijan que se pidio.
    # Sin esto la pagina lanzaba el diseño entero en cuanto se subia un FASTA, asi que
    # una corrida de minutos —manifiesto conectado y accesibilidad— empezaba sin avisar
    # y la estimacion no habria servido de nada: llegaba cuando ya estaba corriendo.
    st.subheader("4) Diseñar")
    st.caption(pasos[3]["detalle"])
    acciones = st.columns([1, 1, 4])
    with acciones[0]:
        if st.button(
            "Estimar coste",
            help=(
                "Mide una invocación real de cada filtro caro y multiplica. No diseña "
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
                st.subheader(f"{nombre} — estimación")
                st.code(
                    # La MISMA secuencia y la MISMA anatomia que la corrida. Pasarle el
                    # 3'UTR mientras `bloque_especie` tila el transcrito entero hacia que
                    # la estimacion contara 1221 ventanas y el resultado 2170, las dos
                    # cifras en la misma pantalla. Ver `WHY_THE_ESTIMATE_NEEDS_ANATOMY`.
                    cost_text(
                        secuencias[nombre],
                        anatomy=anat,
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

        # El proyecto: uno por especie analizada. Se abre AQUI, con la anatomia ya
        # resuelta, porque el proyecto la guarda — y sin ella el propio proyecto sale
        # marcado NO_FIABLE, que es informacion y no un fallo.
        proyectos = {
            nombre: _panel_proyecto(nombre, secuencias[nombre], anat)
            for nombre, (_, anat) in anatomias.items()
        }

        ficheros: dict[str, str] = {}
        for nombre, (transcrito, anat) in anatomias.items():
            ficheros.update(
                bloque_especie(
                    nombre, transcrito, secuencias[nombre], anat, umbrales, config,
                    seeds, mask, scaffold, conservacion, recursos, accesibilidad,
                    proyectos.get(nombre),
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




def _guardar_corrida(proyecto, nombre: str, *, construir, guardar, clave: str) -> None:
    """Guarda la corrida de un modal en el log del proyecto.

    Es el mismo formulario para los cuatro: sin fecha y sin quién la corrió el registro
    no es auditable, así que los dos son obligatorios y el núcleo aborta sin ellos.
    """
    if proyecto is None:
        st.caption(
            "Sin proyecto abierto esta corrida NO se guarda: al cerrar la pestaña se "
            "pierde. Actívalo en la barra lateral."
        )
        return
    columnas = st.columns([2, 2, 3])
    with columnas[0]:
        fecha = st.text_input("Fecha", "", key=f"{clave}_gf_{nombre}")
    with columnas[1]:
        quien = st.text_input("Quién la corrió", "", key=f"{clave}_gq_{nombre}")
    with columnas[2]:
        if st.button("Guardar en el proyecto", key=f"{clave}_gb_{nombre}"):
            try:
                guardar(proyecto, construir(fecha, quien))
            except (ShmirDesignError, ValueError, OSError) as exc:
                # rule2-ok: frontera de la interfaz. Nada se guarda y se dice por qué.
                st.error(f"**PARA** — {exc}")
            else:
                st.success("Guardada en el log del proyecto.")



def _guardar_seleccion(proyecto, seleccion, nombre: str) -> None:
    """La selección manual, al log. Antes se recalculaba en pantalla y se perdía."""
    if proyecto is None:
        return
    st.markdown("**Guardar la selección en el proyecto**")
    guardada = selected_starts(proyecto)
    if guardada:
        st.caption(f"Última selección guardada: {', '.join(str(s) for s in guardada)}")
    columnas = st.columns([2, 2, 3])
    with columnas[0]:
        fecha = st.text_input("Fecha", "", key=f"sel_fecha_{nombre}")
    with columnas[1]:
        quien = st.text_input("Quién", "", key=f"sel_quien_{nombre}")
    with columnas[2]:
        if st.button("Guardar selección", key=f"sel_btn_{nombre}"):
            try:
                save_selection(
                    proyecto,
                    starts=[c.start for c in seleccion.selection.chosen],
                    date=fecha, by=quien,
                )
            except (ShmirDesignError, ValueError, OSError) as exc:
                # rule2-ok: frontera de la interfaz, el motivo se enseña entero.
                st.error(f"**PARA** — {exc}")
            else:
                st.success("Guardada. Una nueva no pisa la vieja: la sucede.")



def _modal_blast(seleccion, nombre: str, proyecto=None) -> None:
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
    for ajuste in blast_setting_rows(blast_defaults_for(nombre)):
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
        subido = st.file_uploader(
            "Soltar aquí el resultado (-outfmt 6)",
            key=f"blast_up_{nombre}",
            help=(
                "Se valida contra el md5 del FASTA de consulta y contra los nombres del "
                "panel antes de almacenarse. Un resultado de otra corrida se rechaza."
            ),
        )
        if subido is not None:
            st.markdown("**Procedencia de la corrida** — sin ella no hay veredicto")
            campos = st.columns(4)
            with campos[0]:
                md5_declarado = st.text_input(
                    "md5 del FASTA de consulta", "", key=f"blast_md5_{nombre}"
                )
            with campos[1]:
                base_nombre = st.text_input("Base", "", key=f"blast_bn_{nombre}")
            with campos[2]:
                base_version = st.text_input("Versión", "", key=f"blast_bv_{nombre}")
            with campos[3]:
                base_md5 = st.text_input("md5 de la base", "", key=f"blast_bm_{nombre}")
            remota = st.checkbox(
                "Fue `-remote` (exploración, NUNCA veredicto)", key=f"blast_rm_{nombre}",
                help="La base de NCBI cambia entre corridas, así que un resultado remoto "
                     "no es reproducible y no cierra el frente.",
            )
            _guardar_corrida(
                proyecto, nombre,
                construir=lambda fecha, quien: blast_run_from_upload(
                    raw=_read_upload(subido), query=consulta, params=params,
                    declared_query_md5=md5_declarado,
                    panel_names=consulta.names,
                    database={
                        "nombre": base_nombre, "version": base_version,
                        "md5": base_md5, "remota": remota,
                    },
                    date=fecha, uploaded_by=quien,
                    run_id=f"{nombre}-blast-{fecha}",
                ),
                guardar=save_blast_run, clave="blast",
            )
    else:
        st.info(
            "Marca al menos un candidato y guía o pasajera para generar la consulta."
        )


def _modal_seed(seleccion, nombre: str, maduros, proyecto=None) -> None:
    """Colision de seed. Este SI ejecuta: es subcadena contra `mature.fa`.

    Como el de BLAST, la pagina no decide nada: recibe filas con `modificado`, `fijo` y
    `comparte`, y bloques con `activo`. Toda la logica esta en `presentation.py`.
    """
    if not st.checkbox(
        f"Colisión de seed — {nombre}",
        key=f"seed_{nombre}",
        help=(
            "Búsqueda de subcadena contra mature.fa, que ya está cargado y verificado. "
            "No hay red de por medio ni comando que copiar."
        ),
    ):
        return

    st.caption(seed_source_text(maduros))

    st.subheader("Lo que se va a comparar")
    st.dataframe(
        seed_preview_rows(seleccion, species=nombre, params=SEED_DEFAULTS),
        hide_index=True,
    )
    st.caption(
        "Las filas con algo en «comparte» tienen el mismo heptámero: no son dos "
        "apuestas independientes en este eje."
    )

    valores = {}
    st.subheader("Ajustes")
    for ajuste in seed_setting_rows(SEED_DEFAULTS):
        if ajuste["fijo"]:
            st.caption(f"{ajuste['ajuste']} = {ajuste['valor']} (fijo)")
            continue
        valores[ajuste["ajuste"]] = st.selectbox(
            ajuste["ajuste"],
            options=ajuste["opciones"],
            key=f"seed_s_{nombre}_{ajuste['ajuste']}",
            help=f"por defecto: {ajuste['por_defecto']}",
        )

    params = seed_params_from_form(valores)
    for fila in seed_setting_rows(params):
        if fila["modificado"]:
            st.markdown(
                f":red[**{fila['ajuste']} = {fila['valor']}**] "
                f"(por defecto {fila['por_defecto']})"
            )

    starts = [c.start for c in seleccion.selection.chosen]
    # La HUELLA del panel y los ajustes. Ver `WHY_A_RUN_FINGERPRINT`: sin ella, cambiar
    # la selección o un ajuste dejaba en pantalla el resultado viejo y lo ofrecía para
    # guardar — una corrida con una procedencia que no era la suya.
    huella = run_fingerprint(tuple(starts), params)
    if st.button(f"Buscar colisiones — {nombre}", key=f"seed_go_{nombre}"):
        # El scan se guarda en `session_state` para que sobreviva al rerun que provoca
        # el boton de guardar. Es ESTADO, no una decision: la pagina sigue sin decidir.
        st.session_state[f"seed_scan_{nombre}"] = (huella, seed_run(
            seleccion, mature=maduros, params=params, species=nombre,
            starts=tuple(starts), guides=True, passengers=True,
        ))
    guardado = st.session_state.get(f"seed_scan_{nombre}")
    scan = guardado[1] if guardado and guardado[0] == huella else None
    if guardado and guardado[0] != huella:
        st.info(WHY_A_RUN_FINGERPRINT)
    if scan is not None:
        destacados = seed_highlights(scan)
        st.warning(destacados["tasa_base"]["texto"])
        if destacados["mir30"]["activo"]:
            st.error(destacados["mir30"]["texto"])
        st.info(destacados["pasajeras"]["texto"])
        st.dataframe(seed_result_rows(scan), hide_index=True)
        st.download_button(
            "Descargar el bloque para el documento",
            data=scan.export_block(),
            file_name=f"{nombre}_colision_seed.txt",
            key=f"seed_dl_{nombre}",
        )
        _guardar_corrida(
            proyecto, nombre,
            construir=lambda fecha, quien: seed_run_from_scan(
                scan, date=fecha, ran_by=quien, run_id=f"{nombre}-seed-{fecha}"
            ),
            guardar=save_seed_run, clave="seed",
        )

    hueco = seed_load_placeholder(None)
    st.warning(hueco["texto"])



def _casete_de(tiling):
    """La secuencia del casete, si se cargó. `None` si no: no se inventa contexto."""
    base = getattr(tiling, "transgene_db", None)
    registros = getattr(base, "records", None) if base is not None else None
    return registros[0].sequence if registros else None


def _modal_empalme(seleccion, nombre: str, diana: str, casete, proyecto=None) -> None:
    """CUARTO modal: predicción de sitios de splicing sobre el cassette montado.

    Es distinto de los otros tres en dos cosas, y las dos se pintan aquí arriba:

    1. **La unidad no es el candidato**: es el par candidato × intrón. Diez candidatos y
       tres intrones son treinta consultas.
    2. **SpliceAI no fue entrenado para esto**, así que sus puntuaciones absolutas no son
       interpretables y lo único que vale es la comparación relativa contra el donante
       legítimo del mismo intrón. Eso va ANTES del botón, no al pie.

    La página sigue sin decidir nada: recibe filas con `avisa`, bloques con `activo` y
    textos ya montados.
    """
    if not st.checkbox(
        f"Predicción de sitios de splicing — {nombre}",
        key=f"sp_{nombre}",
        help=(
            "Sobre el cassette montado, no sobre la guía. Desempate y alerta, nunca "
            "filtro: no puede excluir a ningún candidato."
        ),
    ):
        return

    # Los avisos van ARRIBA. Ninguno es opcional.
    for aviso in splice_warning_rows():
        st.warning(aviso["texto"])

    st.caption("**Intrones del registro.** La unidad de este modal es el par candidato × intrón.")
    for fila in splice_intron_rows():
        if fila["estado"] is FilterState.PASS:
            st.write(f"✅ **{fila['intron']}** — {fila['descripcion']}")
        else:
            st.write(f"⬜ **{fila['intron']}** — NOT_RUN. {fila['motivo']}")
            with st.expander(f"Cómo se resuelve «{fila['intron']}»"):
                st.caption(obtencion_rows(fila["ficha"], species=nombre)["texto"])

    # La GEOMETRIA de cada intron: el desglose pieza a pieza y donde cabe el modulo.
    # Va aqui porque es lo que hay que mirar ANTES de montar nada — un total que nadie
    # puede descomponer escondia 65 nt de espaciadores de novo, y el sitio de insercion
    # no se emitia en ninguna parte. La pagina no calcula: pide el texto ya montado.
    with st.expander("Geometría de los intrones — desglose y sitio de inserción"):
        st.code(intron_geometry_text(), language=None)

    # La variante que la app DISEÑA, para esta guía. Se enseña aquí porque es donde se
    # decide con qué intrón se consulta: uno que se propone y nadie ve no existe.
    with st.expander("Variante propuesta — mvm_sin_criptico", expanded=False):
        st.text(variant_proposal_for(seleccion))

    disponibles = [f["intron"] for f in splice_intron_rows() if f["estado"] is FilterState.PASS]
    elegidos = st.multiselect(
        "Intrones a consultar", disponibles, default=disponibles,
        key=f"sp_intrones_{nombre}",
    )
    if not elegidos:
        st.info("Elige al menos un intrón: sin intrón no hay cassette que montar.")
        return

    # El contexto exónico sale del CASETE si está cargado; si no, de las dos piezas de
    # 5 nt, que para un modelo entrenado con ventana de 10.000 es casi nada. La app lo
    # dice en vez de rellenarlo.
    contexto = st.number_input(
        "Contexto exónico a cada lado (nt)", min_value=0, max_value=5000, value=0,
        step=50, key=f"sp_ctx_{nombre}",
        help="Del casete, si está cargado. Cambia el resultado, así que viaja con la "
             "consulta. 0 = lo que dan las piezas del plásmido.",
    )
    try:
        construcciones = splice_constructions(
            seleccion, target=diana, intron_names=elegidos, scaffold=SGEP_SCAFFOLD,
            cassette=casete, context_nt=contexto,
        )
    except (ShmirDesignError, ValueError) as exc:
        # rule2-ok: frontera de la interfaz. El fallo se enseña entero.
        st.error(f"**PARA** — {exc}")
        return

    st.caption(
        f"**{len(construcciones)} consulta(s)** = {len(construcciones) // len(elegidos)} "
        f"candidato(s) × {len(elegidos)} intrón(es)."
    )
    st.caption(splice_context_note(construcciones))
    st.dataframe(splice_construction_rows(construcciones), width="stretch")

    st.download_button(
        "Descargar el FASTA de construcciones",
        splice_query_text(construcciones),
        f"construcciones_{nombre}.fa",
        "text/plain",
        key=f"sp_fasta_{nombre}",
    )
    st.caption(splice_executor_text())

    st.subheader("Accesibilidad estructural del intrón")
    st.caption(
        "Análisis APARTE: da un número propio, no prestado de un modelo entrenado para "
        "otra cosa. Corre entero aquí."
    )
    st.dataframe(
        splice_folding_rows(
            construcciones,
            module_of=lambda c: splice_module_of(
                c, target=diana, scaffold=SGEP_SCAFFOLD
            ),
        ),
        width="stretch",
    )

    st.subheader("Subir el resultado de SpliceAI")
    subido = st.file_uploader(
        "Resultado (TSV)", type=["tsv", "txt"], key=f"sp_res_{nombre}"
    )
    if subido is None:
        return
    try:
        scan = splice_scan_from_result(
            _read_upload(subido), constructions=construcciones
        )
    except (ShmirDesignError, ValueError) as exc:
        # rule2-ok: el resultado se RECHAZA entero y se dice por qué.
        st.error(f"**RECHAZADO** — {exc}")
        return

    for bloque in splice_highlights(scan).values():
        if bloque["activo"]:
            st.info(bloque["texto"])
    st.dataframe(splice_result_rows(scan), width="stretch")

    st.subheader("Qué guías introducen crípticos que las otras no")
    st.dataframe(splice_exclusive_rows(scan), width="stretch")

    _guardar_corrida(
        proyecto, nombre,
        construir=lambda fecha, quien: splice_run_from_scan(
            scan, raw=_read_upload(subido), date=fecha, ran_by=quien,
            run_id=f"{nombre}-{fecha}", executor=splice_executor_text(),
        ),
        guardar=save_splice_run, clave="sp",
    )


def _modal_offtarget(seleccion, nombre: str, maduros, diana: str,
                     proyecto=None) -> None:
    """Carga de off-targets por seed. El fichero NO lo tenemos: se sube aquí.

    Es el tercer modal y el que cierra `offtarget_seed`. Como los otros dos, la página
    no decide nada: recibe filas con `avisa`, `modificado` y `anomalo`, y bloques con
    `activo`. Lo que sí tiene de propio es la SUBIDA con su procedencia — sin ensamblaje
    y sin fecha de la tabla el conteo no es reproducible, y `Provenance` aborta.
    """
    if not st.checkbox(
        f"Carga de off-targets por seed — {nombre}",
        key=f"ot_{nombre}",
        help=(
            "Cuenta cuántos 3'UTR del transcriptoma llevan un sitio para esta seed. "
            "Cuatro clases separadas, con percentil contra una nula de la misma "
            "composición. Es DESEMPATE, nunca filtro."
        ),
    ):
        return

    st.caption(offtarget_route_text())

    st.subheader("Procedencia del fichero")
    st.caption(
        "Los seis campos son obligatorios: sin ensamblaje, tabla y fecha, el conteo no "
        "es reproducible — la misma regla que la versión de miRBase y la biblioteca de "
        "Dfam."
    )
    formulario = {}
    for campo, ayuda in (
        ("source", "de dónde se descargó"),
        ("assembly", "mm39, mm10…"),
        ("table", "NCBI RefSeq / RefSeq All"),
        ("table_date", "fecha de la tabla, no la de hoy"),
        ("representative", "criterio de representante por gen"),
        ("version", "cómo se llama esta versión en el manifiesto"),
    ):
        formulario[campo] = st.text_input(
            campo, key=f"ot_p_{nombre}_{campo}", help=ayuda
        )

    subido = st.file_uploader(
        "Soltar aquí `transcriptoma_3utr.fa`",
        key=f"ot_up_{nombre}",
        help=(
            "Se valida al recibirlo: que sea FASTA, cuántas secuencias, longitud total, "
            "md5 y si hay varias isoformas por gen. Si algo no cuadra, se rechaza."
        ),
    )
    if subido is None:
        st.warning(offtarget_placeholder(None)["texto"])
        return

    crudo = _read_upload(subido)
    for fila in offtarget_upload_rows(crudo):
        if fila["avisa"]:
            st.warning(f"{fila['campo']}: {fila['valor']}")
        else:
            st.caption(f"{fila['campo']}: {fila['valor']}")

    catalogo = offtarget_catalog_from_upload(crudo, form=formulario)
    st.success(offtarget_placeholder(catalogo)["texto"])

    st.subheader("Ajustes")
    valores = {}
    for ajuste in offtarget_setting_rows(OFFTARGET_DEFAULTS):
        if ajuste["fijo"]:
            st.caption(f"{ajuste['ajuste']} = {ajuste['valor']} (fijo)")
            continue
        valores[ajuste["ajuste"]] = st.selectbox(
            ajuste["ajuste"],
            options=ajuste["opciones"],
            key=f"ot_s_{nombre}_{ajuste['ajuste']}",
            help=f"por defecto: {ajuste['por_defecto']}",
        )

    params = offtarget_params_from_form(valores)
    for fila in offtarget_setting_rows(params):
        if fila["modificado"]:
            st.markdown(
                f":red[**{fila['ajuste']} = {fila['valor']}**] "
                f"(por defecto {fila['por_defecto']})"
            )

    st.subheader("Lo que este número NO es")
    for limitacion in offtarget_limitation_rows():
        st.warning(
            f"**{limitacion['titulo']}** [{limitacion['direccion']}] — "
            f"{limitacion['texto']}"
        )
    st.error(offtarget_upper_bound()["texto"])

    starts = [c.start for c in seleccion.selection.chosen]
    huella = run_fingerprint(tuple(starts), params)
    if st.button(f"Contar off-targets — {nombre}", key=f"ot_go_{nombre}"):
        # Mismo motivo que en el modal de seed: el scan tiene que sobrevivir al rerun.
        # Y con la misma HUELLA, por el mismo motivo: ver `WHY_A_RUN_FINGERPRINT`.
        st.session_state[f"ot_scan_{nombre}"] = (huella, offtarget_run(
            seleccion, catalog=catalogo, mature=maduros, params=params,
            species=nombre, starts=tuple(starts), guides=True, passengers=True,
            target=diana, target_label=f"3'UTR de {nombre}",
        ))
    guardado = st.session_state.get(f"ot_scan_{nombre}")
    scan = guardado[1] if guardado and guardado[0] == huella else None
    if guardado and guardado[0] != huella:
        st.info(WHY_A_RUN_FINGERPRINT)
    if scan is not None:
        destacados = offtarget_highlights(scan)
        st.error(destacados["limite_superior"]["texto"])
        st.warning(destacados["uso"]["texto"])
        if destacados["isoformas"]["activo"]:
            st.warning(destacados["isoformas"]["texto"])

        st.markdown("**Una columna por clase — nunca sumadas**")
        st.dataframe(offtarget_result_rows(scan), hide_index=True)
        st.caption(destacados["nula"]["texto"])

        st.markdown("**Controles biológicos** — referencia de magnitud")
        st.dataframe(offtarget_control_rows(scan), hide_index=True)
        st.caption(destacados["controles"]["texto"])

        st.markdown("**Autoconteo sobre la propia diana** — esperado: 1")
        st.dataframe(offtarget_self_count_rows(scan), hide_index=True)
        if destacados["autoconteo"]["activo"]:
            st.error(destacados["autoconteo"]["texto"])

        st.download_button(
            "Descargar el bloque para el documento",
            data=scan.export_block(),
            file_name=f"{nombre}_carga_offtarget.txt",
            key=f"ot_dl_{nombre}",
        )
        _guardar_corrida(
            proyecto, nombre,
            construir=lambda fecha, quien: offtarget_run_from_scan(
                scan, date=fecha, ran_by=quien, run_id=f"{nombre}-ot-{fecha}"
            ),
            guardar=save_offtarget_run, clave="ot",
        )
