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
    BLAST_MODAL_NOTE,
    arms_rows,
    arms_warning,
    control_choices,
    control_panel,
    cassette_sequence,
    anatomy_payload,
    load_stores,
    cached_run,
    run_fingerprint,
    intron_geometry_text,
    stored_runs_note,
    upload_path,
    anatomy_source_label,
    chosen_starts,
    obsolete_rows,
    has_selection,
    project_banner,
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
    project_target,
    PROJECT_NEW_OPTION,
    upload_allowed,
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
    REFINEMENT_FRAMING,
    WHY_TWO_MOMENTS,
    design_files_rows,
    refinement_panel,
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
    front_card_rows,
    verdicts_changed,
    folding_capability,
    check_can_emit_dna,
    front_progress,
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
    blast_readiness,
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
    step_plain,
    species_plain,
    semaforo_plain,
    APP_PURPOSE,
    WHAT_YOU_NEED,
    CANDIDATES_ARE_NOT_THE_END,
    BUTTON_DESIGN,
    BUTTON_ESTIMATE,
    BUTTON_CONTINUE,
    window_rows,
)
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.filters import OBSOLETO_NOTE, FilterState  # noqa: E402
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
    """Titular corto, que hacer, y el detalle PLEGADO.

    Era un parrafo de siete lineas que empezaba por «Faltan 4 de 10 filtros» y metia
    dentro las tres cuentas de ventanas. Todo cierto, y nadie lo lee entero: lo primero
    que se ve tiene que caber de un vistazo. El texto lo arma `semaforo_plain`, no esta
    funcion — aqui no se decide nada (regla 6).
    """
    color, emoji = COLORES[luz.color]
    llano = semaforo_plain(luz)
    st.markdown(
        f'<div style="border-left:8px solid {color};background:#faf8f3;'
        f'padding:18px 22px;border-radius:8px;margin-bottom:16px">'
        f'<div style="font-size:1.25rem;font-weight:700;color:{color}">'
        f"{emoji} {llano['titular']}</div>"
        f'<div style="color:#4a443a;margin-top:8px;font-size:1.02rem">'
        f"{llano['que_hacer']}</div></div>",
        unsafe_allow_html=True,
    )
    with st.expander("Las cifras de la corrida"):
        st.caption(llano["detalle"])


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

    # ── AQUI TERMINA EL PRIMER TRAMO, y hasta ahora no lo decia ─────────────────
    #
    # La lista de candidatos venia seguida de todo lo demas, asi que se leia como el
    # resultado. No lo es: es la mitad del camino, y la segunda mitad es la que decide
    # cuales sobreviven.
    st.divider()
    st.info(CANDIDATES_ARE_NOT_THE_END)
    if st.button(BUTTON_CONTINUE, type="primary", key=f"seguir_{nombre}"):
        st.session_state[f"tramo2_{nombre}"] = True
    if not st.session_state.get(f"tramo2_{nombre}"):
        return {}

    _tarjetas_de_comprobacion(corrida, nombre, tiling, seleccion)

    # EL INFORME VA AQUI, justo debajo de los frentes. Estaba mas abajo, detras del
    # generador de bloques, y ahi es lo ultimo que se ve: quien acaba de leer que le
    # falta por cerrar es cuando quiere llevarselo. Es el MISMO documento que emite el
    # CLI —`informe_documento` + `informe_files`—, no uno nuevo: dos documentos para lo
    # mismo divergen, y el que se descarga acaba en una libreta de laboratorio.
    st.markdown("**Informe** — parcial o completo, en cualquier momento")
    documento = informe_documento(
        seleccion, tiling, species=nombre,
        generated=st.session_state.get("fecha_informe", "sin fecha declarada"),
        anatomy_source=anatomy_source_label(anat),
        anatomy=anat,
        # LOS ALMACENES. Sin ellos las fichas del documento se construian con uno vacio
        # y decia `NOT_RUN` de frentes cerrados — sobre el artefacto que defiende la
        # seleccion. Con proyecto cerrado va `None`, que es la verdad: no hay corridas
        # que leer, y la huella del registro lo dice con 0 corridas.
        stores=load_stores(proyecto) if proyecto is not None else None,
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

    # LO GUARDADO SE RELEE. `load_stores` estaba importado y no se llamaba desde ningún
    # sitio: al reabrir un proyecto volvía la selección y **los cuatro frentes salían de
    # nuevo NOT_RUN**, así que la persistencia servía para la mitad de lo que dice servir.
    # Es el mismo patrón que `store.save_*` y que `page_run`, tercera vez en dos días.
    if proyecto is not None:
        st.caption(stored_runs_note(load_stores(proyecto)))

    _modal_blast(seleccion, nombre, proyecto, tiling)
    _modal_seed(seleccion, nombre, tiling.mature, proyecto)
    _modal_offtarget(seleccion, nombre, tiling.mature, utr3, proyecto)
    _modal_empalme(seleccion, nombre, utr3, cassette_sequence(tiling), proyecto)
    _guardar_seleccion(proyecto, seleccion, nombre)

    with st.expander(f"Todas las ventanas de {nombre} ({len(tiling.windows)})"):
        st.dataframe(window_rows(tiling), hide_index=True)

    _panel_controles(seleccion, nombre, tiling, utr3)

    bloques = st.checkbox(
        f"Generar los bloques listos para pedir de {nombre}",
        key=f"bloques_{nombre}",
        help=(
            "Módulo NheI-SacI de 149 nt y cassette MluI-AgeI de 318 pb, con y sin "
            "brazos de homologia, más la hoja de pedido."
        ),
    )
    if bloques and has_selection(seleccion):
        # SIN MOTOR DE PLEGADO NO SE EMITE ADN. La pasajera de este modulo se elige
        # plegando, y sin plegado se elegiria con la regla que este proyecto descarto
        # por escrito — y esto se manda a sintetizar. Ver `check_can_emit_dna`.
        try:
            check_can_emit_dna()
        except ShmirDesignError as exc:
            # rule2-ok: frontera de la interfaz. No se emite nada y se dice por que.
            st.error(f"**PARA** — {exc}")
            return ficheros
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

    return output_bundle(
        species=nombre,
        tiling=tiling,
        selection=seleccion,
        scaffold=scaffold,
        transcript=transcrito,
        conservation=conservacion,
        blocks=bloques,
    )



def _tarjetas_de_comprobacion(corrida, nombre: str, tiling, seleccion) -> None:
    """Una tarjeta por comprobacion, con su color y su estado.

    Sustituye a la lista de «Frentes — y como cerrar los que estan en NOT_RUN», que
    nombraba diez frentes por su nombre interno y pedia al lector que supiera lo que es
    un frente. Las tarjetas se DERIVAN igual que aquella lista —una escrita a mano
    dejaria fuera a la numero once— y el color lo pone `presentation.CARD_STATES`.
    """
    _cabecera_paso(4, step_plain(5))
    progreso = front_progress(front_card_rows(corrida, species=nombre))
    st.progress(progreso["fraccion"], text=progreso["texto"])

    tarjetas = front_card_rows(corrida, species=nombre)
    motivos = {f["frente"]: f for f in front_help_rows(tiling, seleccion, species=nombre)}
    columnas = st.columns(2)
    for indice, tarjeta in enumerate(tarjetas):
        with columnas[indice % 2]:
            with st.container(border=True):
                st.markdown(
                    f":{tarjeta['color']}[●] **{tarjeta['titulo']}**"
                )
                st.caption(tarjeta["en_cristiano"])
                detalle = motivos.get(tarjeta["frente"])
                if detalle is not None:
                    with st.expander("Cómo se hace"):
                        st.caption(detalle["motivo"])
                        st.code(detalle["ficha"]["texto"], language=None)
                        st.link_button(
                            f"↗ {detalle['ficha']['fuente']}",
                            detalle["ficha"]["url"],
                            disabled=not detalle["ficha"]["url"].startswith("http"),
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
        # Y se OLVIDA lo recordado: volver a marcar la casilla no puede reabrir solo un
        # proyecto que se cerró a proposito.
        plan = project_target(
            active=False, chosen="", new_name="", date="", clicked=False,
            remembered=st.session_state.get(f"pr_abierto_{especie}", ""),
        )
        st.session_state[f"pr_abierto_{especie}"] = plan["recordar"]
        st.sidebar.caption(plan["aviso"])
        return None

    opciones = [PROJECT_NEW_OPTION] + [f["slug"] for f in existentes]
    elegido = st.sidebar.selectbox("Proyecto", opciones, key=f"pr_slug_{especie}")
    fecha = st.sidebar.text_input(
        "Fecha (AAAA-MM-DD)", "", key=f"pr_fecha_{especie}",
        help="Va en cada registro del log. Sin ella no es auditable.",
    )
    # LOS WIDGETS SE PINTAN SIEMPRE Y LA DECISION SE TOMA DESPUES. Antes el botón de
    # crear estaba dentro de un `if` que devolvía `None`, y un botón de Streamlit vale
    # `True` UN SOLO rerun: al escribir en cualquier campo, el proyecto desaparecía.
    # Ver `WHY_THE_PROJECT_IS_REMEMBERED` y errata nº 42.
    nombre_nuevo = ""
    pulsado = False
    if elegido == PROJECT_NEW_OPTION:
        nombre_nuevo = st.sidebar.text_input(
            "Nombre del proyecto nuevo", "", key=f"pr_nuevo_{especie}"
        )
        pulsado = st.sidebar.button("Crear proyecto", key=f"pr_crear_{especie}")

    clave_abierto = f"pr_abierto_{especie}"
    plan = project_target(
        active=True, chosen=elegido, new_name=nombre_nuevo, date=fecha,
        clicked=pulsado, remembered=st.session_state.get(clave_abierto, ""),
    )
    # Se recuerda el SLUG, no el almacén: `WHY_THE_SLUG_AND_NOT_THE_STORE`.
    st.session_state[clave_abierto] = plan["recordar"]
    if plan["accion"] == "ninguna":
        st.sidebar.caption(plan["aviso"])
        return None

    try:
        if plan["accion"] == "crear":
            payload, fuente = anatomy_payload(anat)
            almacen = project_create(
                raiz, slug=plan["slug"], date=fecha, sequence=secuencia, species=especie,
                anatomy=payload, anatomy_source=fuente,
            )
        else:
            # El md5 se comprueba: seguir apuntando corridas de OTRA secuencia en este
            # log lo dejaría coherente de forma y nada lo delataría. Y se comprueba en
            # CADA rerun, que es por lo que se recuerda el slug y no el almacén.
            almacen = project_open(
                raiz, plan["slug"], expect_md5=sequence_md5(secuencia)
            )
    except (ShmirDesignError, ValueError, OSError) as exc:
        # rule2-ok: frontera de la interfaz. El fallo se enseña entero.
        st.sidebar.error(f"**PARA** — {exc}")
        return None

    cartel = project_banner(almacen)
    st.sidebar.success(cartel["titulo"])
    if not cartel["fiable"]:
        st.sidebar.warning(cartel["aviso"])
    with st.sidebar.expander("Historial"):
        for fila in project_rows(almacen):
            st.write(f"{fila['n']}. `{fila['tipo']}` {fila['fecha']} — {fila['resumen']}")

    # ¿Siguen valiendo? Se DERIVA comparando el md5 que cada corrida guardó con el del
    # fichero de hoy. La página no compara nada: pide las filas ya resueltas.
    filas = obsolete_rows(almacen, directory=reference_dir())
    caducadas = [f for f in filas if f["estado"] is FilterState.OBSOLETO]
    if caducadas:
        st.sidebar.error(
            f"**{len(caducadas)} corrida(s) OBSOLETA(s)** — un fichero que consumieron "
            f"ha cambiado debajo."
        )
    if filas:
        with st.sidebar.expander("¿Siguen valiendo las corridas guardadas?"):
            st.caption(OBSOLETO_NOTE)
            for fila in filas:
                st.write(f"`{fila['tipo']}` {fila['fecha']} — **{fila['estado']}**")
                for motivo in fila["motivos"]:
                    st.caption(f"  {motivo}")
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


def _deposito_opcional(especie: str) -> None:
    """El deposito, alcanzable antes de diseñar — pero como acceso SECUNDARIO.

    El paso 5 solo aparece despues de haber diseñado, y esa es la decision. Pero dejar
    el gestor SOLO ahi dentro quitaba la unica via de subir un fichero a quien acaba de
    abrir la app, y este proyecto tiene decidido que **todo se sube por la interfaz**
    porque quien la usa no conoce el arbol del repositorio.

    Va COLAPSADO y con el titulo diciendo que no hace falta para diseñar: asi se puede
    depositar antes, sin que la pantalla vuelva a leerse como una lista de requisitos.
    """
    with st.expander(
        "Depositar ficheros de referencia (no hace falta ninguno para diseñar)",
        expanded=False,
    ):
        _panel_refinamiento(especie)


def _panel_refinamiento(especie: str) -> None:
    """PASO 5. Los ficheros que deciden que candidatos CAEN, DESPUES de los resultados.

    Antes esto era el paso 3 y se pedia entero antes de diseñar, como si los siete
    frentes sirvieran para lo mismo. No sirven: para obtener candidatos no hace falta
    ninguno. Ver `presentation.WHY_TWO_MOMENTS`.

    La pagina no decide nada aqui (regla 6): el estado de cada fila, su color, el orden
    y si va colapsada salen de `presentation.refinement_panel`, con tests. Si el color
    lo eligiera la pagina segun un umbral, eso seria logica sin test — y un panel que
    pinta en ambar algo que no hace falta manda a buscar un fichero que ya sobra.
    """
    if not especie:
        st.caption(
            "Elige una especie: los ficheros que hacen falta —y cómo se llaman— "
            "dependen de ella."
        )
        return

    directorio = reference_dir()
    panel = refinement_panel(especie, directory=directorio)

    # La frase de encuadre, EN LA SECCION y no en un tooltip: lo que hace falta para
    # leer bien la lista no puede estar detras de un gesto.
    st.info(panel["frase"])
    st.progress(panel["progreso"]["fraccion"], text=panel["progreso"]["texto"])
    st.caption(
        " · ".join(
            f"{e['marca']} **{e['estado']}** {e['significa']}" for e in panel["leyenda"]
        )
    )
    st.caption(WHY_NO_GLOBAL_TOGGLE)
    if is_declared():
        st.caption(f"Se guardan en `{directorio}`. {WHY_A_WORKING_DIR}")

    filas = panel["filas"]
    if filas and filas[0]["aviso_manifiesto"]:
        st.error(f"**Manifiesto ilegible** — {filas[0]['aviso_manifiesto']}")

    for fila in filas:
        titular = (
            f"{fila['marca']} **{fila['nombre']}** · {fila['frentes_texto']} — "
            f"{fila['por_que']}"
        )
        if fila["colapsada"]:
            # UNA LINEA, pero CON SUS BOTONES: colapsar es no ocupar sitio, no dejar de
            # poder ver, reemplazar, borrar o descargar lo que ya esta.
            with st.expander(titular, expanded=False):
                st.caption(fila["resumen"])
                if fila["presente"]:
                    _fila_presente(fila, directorio)
                else:
                    st.caption(fila["si_no_llega"])
            continue
        with st.container(border=True):
            st.markdown(titular)
            st.caption(fila["si_no_llega"])
            _fila_ausente(fila, directorio)


def _estilo() -> None:
    """Tipografia y aire. La pagina se leia como una consola: letra de 14 px, todo

    pegado y las explicaciones en `caption`, que es el tamaño mas pequeño que hay.
    Nada de esto DECIDE nada —son medidas, no criterios— asi que puede vivir aqui.
    """
    st.markdown(
        """
        <style>
          .block-container { max-width: 1180px; padding-top: 2.2rem; }
          html, body, [class*="css"] { font-size: 17px; line-height: 1.65; }
          h1 { font-size: 2.1rem; letter-spacing: -0.5px; margin-bottom: .2rem; }
          h2 { font-size: 1.55rem; margin-top: 2.6rem; margin-bottom: .4rem; }
          h3 { font-size: 1.2rem; margin-top: 1.6rem; }
          /* Las explicaciones dejan de ser letra pequeña: son la mitad del producto. */
          [data-testid="stCaptionContainer"] p { font-size: .97rem; color: #55504a; }
          [data-testid="stVerticalBlockBorderWrapper"] { padding: .35rem .2rem; }
          div[data-testid="stExpander"] { border-radius: 8px; }
          .stButton button { padding: .55rem 1.1rem; font-size: 1rem; }
          .sd-lede { font-size: 1.12rem; color: #3d3831; max-width: 46rem; }
          .sd-paso { color: #8a8178; font-size: .82rem; letter-spacing: .12em;
                     text-transform: uppercase; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _cabecera_paso(numero: int, guia) -> None:
    """El encabezado de un paso: numero pequeño, titulo llano grande, y por que."""
    st.markdown(f'<div class="sd-paso">Paso {numero}</div>', unsafe_allow_html=True)
    st.header(guia["titulo"], anchor=False)
    st.markdown(f'<div class="sd-lede">{guia["que_se_pide"]}</div>',
                unsafe_allow_html=True)
    st.caption(guia["por_que"])


def main() -> None:
    st.set_page_config(page_title="shmir-design", layout="wide")
    _estilo()
    st.title("shmir-design")

    # EL INICIO, que no existia. Sin el, la primera pantalla es un formulario sin
    # pregunta: quien entra no sabe si esta herramienta hace lo que necesita.
    st.markdown(f'<div class="sd-lede">{APP_PURPOSE}</div>', unsafe_allow_html=True)
    st.info(WHAT_YOU_NEED)

    # Los servicios externos bajan a un desplegable. Arriba del todo eran tres botones
    # sin contexto delante de alguien que todavia no sabe que hace la app.
    # LA CAPACIDAD DEL ENTORNO, arriba y visible. No es un fichero que falte —eso se
    # consigue— sino algo que se instala en la imagen, y confundirlos manda al usuario a
    # buscar un fichero que no existe.
    plegado = folding_capability()
    if not plegado["disponible"]:
        st.warning(plegado["texto"])

    with st.expander("Servicios externos con los que contrastar un diseño"):
        enlaces = st.columns(len(EXTERNAL_TOOLS) + 2)
        # zip-ok: se piden DOS columnas de mas que herramientas, a proposito, para que
        # los botones no se estiren a todo el ancho. Las dos ultimas quedan vacias.
        for columna, herramienta in zip(enlaces, EXTERNAL_TOOLS):
            with columna:
                st.link_button(
                    f"↗ {herramienta.name}", herramienta.url, help=herramienta.tooltip,
                    width="stretch",
                )
        st.caption(
            "Sus direcciones no se han podido comprobar desde este entorno y **ningun "
            "código las llama**: se abren a mano. El score que devuelva miRarchitect "
            "entra por `tools/import_scores.py`, nunca calculado aquí."
        )
    st.divider()

    umbrales, config, min_bloque = panel_umbrales()

    # ── PASO 1 · ESPECIE ────────────────────────────────────────────────────────
    #
    # Desplegable, no caja de texto. Y SIN valor por defecto: uno preseleccionado
    # —«modelo»— parece configurado y deja la colision de seed y la especificidad rotas
    # sin decir por que. Las opciones salen de `species.SPECIES`; la pagina no tiene
    # ninguna lista propia.
    _cabecera_paso(1, step_plain(1))
    opciones = species_options()
    # El desplegable, ESTRECHO, y la nota a su derecha. A todo lo ancho, la frase que
    # explica que pasa con esa especie caia debajo y a 14 px.
    izquierda, derecha = st.columns([2, 3])
    with izquierda:
        elegida = st.selectbox(
            "Especie",
            [o["valor"] for o in opciones],
            index=species_default(),
            placeholder="elige una",
            format_func=lambda v: next(
                o["etiqueta"] for o in opciones if o["valor"] == v
            ),
            label_visibility="collapsed",
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
        llano = species_plain(nombre_modelo)
        with derecha:
            # LO LLANO DELANTE, el detalle tecnico un clic mas adentro. No se sustituye:
            # los tres identificadores deciden contra que catalogos se comprueba, y
            # borrarlos seria perder la procedencia.
            (st.warning if llano["bloquea"] else st.success)(llano["texto"])
            with st.expander("Qué identificadores se van a usar"):
                st.caption(llano["detalle"])
        if nota["bloquea"]:
            for cerrado in nota["cerrados"]:
                st.caption(f"· {cerrado}")
            st.caption(f"**Como declararla:** {nota['como_declararla']}")


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
            "Elige una especie para continuar. Sin saberla no se puede comprobar nada: "
            "los catálogos con los que se contrasta un diseño son distintos en cada "
            "animal."
        )
        return

    # ── PASO 2 · SECUENCIA ──────────────────────────────────────────────────────
    _cabecera_paso(2, step_plain(2))
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

    # ── PASO 3 · FICHEROS DE REFERENCIA, LOS DE DISEÑAR ─────────────────────────
    #
    # SOLO lo imprescindible para OBTENER candidatos, que hoy es nada. Los que deciden
    # cuales CAEN van en el paso 5, DESPUES del boton: pedirlos todos aqui hacia creer
    # que sin ellos no se puede empezar, y eso es falso — se puede diseñar hoy y refinar
    # mañana. Ver `presentation.WHY_TWO_MOMENTS`.
    pasos = steps_rows(
        species=nombre_modelo,
        sequence_loaded=modelo is not None,
        directory=reference_dir(),
        designed=st.session_state.get("accion") == "diseñar",
    )
    # EL PASO DE «FICHEROS DE REFERENCIA PARA DISEÑAR» YA NO ESTA AQUI, y no es una
    # supresion: es que su lista esta VACIA —para obtener candidatos no hace falta
    # ningun fichero— y un paso vacio delante del boton hace creer que falta algo. Lo
    # que si hace falta para refinar se pide DESPUES, en su sitio. Es la doctrina de los
    # dos momentos (`WHY_TWO_MOMENTS`) aplicada tambien a la pantalla, no solo al texto.

    if not modelo:
        st.info(
            "Sube la secuencia del mensajero que quieres apagar y podrás continuar. Si "
            "subes también la de otra especie, se buscan además los tramos idénticos "
            "entre las dos — que son los sitios donde un mismo shmiR valdría para las "
            "dos."
        )
        _deposito_opcional(nombre_modelo)
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
    _cabecera_paso(3, step_plain(3))
    acciones = st.columns([2, 2, 3])
    with acciones[0]:
        if st.button(BUTTON_DESIGN, type="primary", width="stretch"):
            st.session_state["accion"] = "diseñar"
    with acciones[1]:
        if st.button(
            BUTTON_ESTIMATE,
            width="stretch",
            help=(
                "Cronometra una pasada de los criterios más lentos y multiplica. No "
                "busca nada: sólo dice si esto son segundos o minutos."
            ),
        ):
            st.session_state["accion"] = "estimar"

    accion = st.session_state.get("accion")
    if accion is None:
        st.info(
            "Todo listo. **Estimar coste** dice cuanto va a tardar sin diseñar nada; "
            "**Diseñar** lanza la corrida."
        )
        _deposito_opcional(nombre_modelo)
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
                "Con una sola especie no hay nada que comparar. Si subes la secuencia de "
                "otra, se buscan los tramos idénticos entre las dos: son los únicos "
                "sitios donde un mismo shmiR podría servir para las dos."
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

    # ── PASO 5 · REFINAMIENTO ───────────────────────────────────────────────────
    #
    # AQUI ABAJO y no arriba: los candidatos de mas arriba son PROVISIONALES, y cada
    # fichero de esta seccion puede tumbar alguno. Puesto antes del boton se leia como
    # una lista de requisitos para empezar.
    quinto = pasos[4]
    if quinto["visible"]:
        st.divider()
        st.subheader(f"5) {quinto['titulo']}")
        st.caption(quinto["detalle"])
        _panel_refinamiento(nombre_modelo)





def _guardar_corrida(proyecto, nombre: str, *, construir, guardar, clave: str,
                     tiling=None, seleccion=None) -> None:
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
            # QUE VEREDICTOS CAMBIA. «Guardada en el log» se lee como «hecho», y
            # durante dias fue un guardado que no cambiaba ninguno porque nadie
            # consultaba el almacen. O la confirmacion dice que cambio, o dice que no
            # cambio nada — y el CERO es la señal que faltaba.
            antes = load_stores(proyecto)
            try:
                guardar(proyecto, construir(fecha, quien))
            except (ShmirDesignError, ValueError, OSError) as exc:
                # rule2-ok: frontera de la interfaz. Nada se guarda y se dice por qué.
                st.error(f"**PARA** — {exc}")
            else:
                if tiling is None or seleccion is None:
                    st.success("Guardada en el log del proyecto.")
                    return
                resumen = verdicts_changed(
                    tiling, seleccion, species=nombre,
                    before=antes, after=load_stores(proyecto),
                )
                (st.success if resumen["cambiados"] else st.warning)(resumen["texto"])



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
                    starts=chosen_starts(seleccion),
                    date=fecha, by=quien,
                )
            except (ShmirDesignError, ValueError, OSError) as exc:
                # rule2-ok: frontera de la interfaz, el motivo se enseña entero.
                st.error(f"**PARA** — {exc}")
            else:
                st.success("Guardada. Una nueva no pisa la vieja: la sucede.")



def _modal_blast(seleccion, nombre: str, proyecto=None, tiling=None) -> None:
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

    # ANTES de nada, no despues de guardar: detras de este modal hay una descarga de
    # decenas de GB y horas de BLAST. `presentation` decide (regla 6).
    for aviso in blast_readiness(species=nombre, directory=reference_dir()):
        (st.error if aviso["bloquea"] else st.warning)(aviso["texto"])

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
        # SIN PROYECTO NO SE ACEPTA EL FICHERO. Antes se aceptaba y se avisaba en gris de
        # que no se guardaba nada — detras de este fichero hay una descarga de decenas de
        # GB y una corrida de horas, asi que dejarlo soltar era una trampa (errata nº 42).
        veredicto = upload_allowed(proyecto)
        if not veredicto["permitido"]:
            st.error(veredicto["motivo"])
            return
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
                ),
                guardar=save_blast_run, clave="blast",
                tiling=tiling, seleccion=seleccion,
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

    starts = chosen_starts(seleccion)
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
    # La pagina NO decide si lo cacheado sirve: lo decide `cached_run`. Estaba aqui,
    # copiado en los dos modales, y por tanto sin test y pudiendo divergir.
    cacheado = cached_run(st.session_state.get(f"seed_scan_{nombre}"), huella)
    scan = cacheado["resultado"]
    if cacheado["caducado"]:
        st.info(cacheado["aviso"])
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
                scan, date=fecha, ran_by=quien
            ),
            guardar=save_seed_run, clave="seed",
        )

    hueco = seed_load_placeholder(None)
    st.warning(hueco["texto"])



def _panel_controles(seleccion, nombre: str, tiling, diana: str) -> None:
    """Los dos controles del experimento y los seis brazos.

    La pagina NO decide nada aqui: elige `control_panel` que candidato se controla, con
    que ficheros y que columnas salen (regla 6). Lo unico que vive en esta funcion es
    que widget se pinta.

    Va detras de los resultados y no en un paso propio porque un control se construye
    SOBRE un candidato: sin panel no hay nada que controlar.
    """
    if not has_selection(seleccion):
        return
    with st.expander(f"Controles del experimento — {nombre}"):
        opciones = control_choices(seleccion)
        elegido = st.selectbox(
            "¿Para qué candidato?",
            options=[o["inicio"] for o in opciones],
            format_func=lambda inicio: f"3utr:{inicio}",
            key=f"ctrl_sitio_{nombre}",
            help=(
                "Las dos construcciones se derivan de LA GUÍA de ese candidato, así que "
                "cambiarlo las cambia enteras. Cualquiera del panel vale: la elección "
                "es tuya."
            ),
        )
        st.markdown("**Los seis brazos** — aviso, no impedimento")
        marcados = st.multiselect(
            "Brazos que vas a montar",
            options=[fila["brazo"] for fila in arms_rows()],
            default=[fila["brazo"] for fila in arms_rows()],
            key=f"ctrl_brazos_{nombre}",
        )
        aviso = arms_warning(marcados)
        if aviso is not None:
            st.error(aviso["texto"])
        st.dataframe(arms_rows(marcados), hide_index=True)

        if not st.button(
            f"Construir los controles de 3utr:{elegido}", key=f"ctrl_ir_{nombre}"
        ):
            st.caption(
                "No se construye nada al abrir el panel: cada construcción pliega "
                "horquillas y eso tarda. El botón es el que pide el trabajo."
            )
            return
        panel = control_panel(
            seleccion, start=elegido, target=diana,
            target_label=f"3'UTR de {nombre}", species=nombre,
            mature=getattr(tiling, "mature", None),
            transgene_db=getattr(tiling, "transgene_db", None),
        )
        for texto in panel["avisos"]:
            st.warning(texto)
        st.markdown(f"**shmiR scrambled** — derivado de {panel['origen']}")
        st.dataframe(panel["scrambled"], hide_index=True)
        st.markdown("**shmiR con la seed rota** — las DOS versiones")
        st.dataframe(panel["comparacion"], hide_index=True)
        for cambios, filas in panel["seed_mismatch"].items():
            st.caption(f"{cambios} cambios")
            st.dataframe(filas, hide_index=True)
        for ficha in panel["fichas"]:
            st.code(ficha, language="text")




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
    veredicto = upload_allowed(proyecto)
    if not veredicto["permitido"]:
        st.error(veredicto["motivo"])
        return
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
            executor=splice_executor_text(),
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

    st.caption(offtarget_route_text(nombre))

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

    veredicto = upload_allowed(proyecto)
    if not veredicto["permitido"]:
        st.error(veredicto["motivo"])
        return
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

    starts = chosen_starts(seleccion)
    huella = run_fingerprint(tuple(starts), params)
    if st.button(f"Contar off-targets — {nombre}", key=f"ot_go_{nombre}"):
        # Mismo motivo que en el modal de seed: el scan tiene que sobrevivir al rerun.
        # Y con la misma HUELLA, por el mismo motivo: ver `WHY_A_RUN_FINGERPRINT`.
        st.session_state[f"ot_scan_{nombre}"] = (huella, offtarget_run(
            seleccion, catalog=catalogo, mature=maduros, params=params,
            species=nombre, starts=tuple(starts), guides=True, passengers=True,
            target=diana, target_label=f"3'UTR de {nombre}",
        ))
    # La pagina NO decide si lo cacheado sirve: lo decide `cached_run`. Estaba aqui,
    # copiado en los dos modales, y por tanto sin test y pudiendo divergir.
    cacheado = cached_run(st.session_state.get(f"ot_scan_{nombre}"), huella)
    scan = cacheado["resultado"]
    if cacheado["caducado"]:
        st.info(cacheado["aviso"])
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
                scan, date=fecha, ran_by=quien
            ),
            guardar=save_offtarget_run, clave="ot",
        )


# LA LLAMADA VA AL FINAL DEL MODULO, y no es estilo. Streamlit ejecuta este fichero como
# `__main__`, asi que `main()` corre EN EL SITIO DONDE ESTA ESTA LINEA: todo lo que se
# defina por debajo todavia no existe. Estuvo a mitad del fichero, con los cuatro modales
# definidos despues, y la pagina reventaba con `NameError: _modal_blast` al pulsar
# Diseñar — pero solo en ese camino, que es el unico que llama a un modal.
# `tests/test_orden_del_modulo.py` lo impide.
if __name__ == "__main__":
    main()
