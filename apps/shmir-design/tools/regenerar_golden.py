#!/usr/bin/env python3
"""Regenera el informe de referencia (`tests/golden/`) que fija la salida ENTERA.

El test `tests/test_informe_golden.py` compara el informe COMPLETO contra el fichero de
esta carpeta. No comprueba que aparezcan unos fragmentos: comprueba que no falte ni
sobre NADA. Es la contramedida a un borrado real de 127 lineas —el bloque del TECHO y
los inmunes enteros— que ningun test de presencia detecto, porque cada test miraba lo
que el se esperaba y nadie miraba el conjunto.

Uso:

    python3 tools/regenerar_golden.py

Solo se regenera A MANO y el diff entra en la revision: si el fichero cambia sin que
nadie haya tocado el informe a proposito, eso es exactamente lo que hay que ver.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GOLDEN = RAIZ / "tests" / "golden" / "raton_informe.txt"
FICHA = RAIZ / "tests" / "golden" / "ficha_raton_200.txt"
DOCUMENTO = RAIZ / "tests" / "golden" / "informe_documento.md"
PAGINA = RAIZ / "tests" / "golden" / "pagina_raton.txt"

#: La fecha del documento va FIJADA: si saliera la de hoy, el golden
#: cambiaria cada dia y el diff dejaria de significar nada.
FECHA_GOLDEN = "2026-08-26"

#: LA CORRIDA QUE SE FIJA VA CON LA CONFIGURACION POR DEFECTO. SIN EXCEPCIONES.
#:
#: Principio nº 18. Aqui habia `--inmunes 4`, `--candidates 10`, `--min-block 22` y
#: `--sin-manifiesto`, todos tecleados — asi que la unica corrida del CLI que alguien
#: miraba llevaba una configuracion que ningun usuario usa. Con `--inmunes 4` puesto, el
#: golden coincidia con la pagina mientras el CLI por defecto daba OTRO panel (errata
#: nº 32): el artefacto de verificacion validaba una configuracion FANTASMA.
#:
#: De los cuatro, tres eran ademas INERTES —`--candidates 10` es el defecto, `--min-block
#: 22` da lo mismo que 15 en este par, y `--sin-manifiesto` no cambia nada habiendo
#: manifiesto—, o sea que llevaban ahi sin hacer nada y sin que nadie lo supiera. El unico
#: con efecto era `--inmunes 4`, que es el que rompio.
#:
#: Si hace falta una variante, se genera un golden ADICIONAL que declare en su nombre que
#: configuracion lleva. Nunca uno solo con parametros puestos a mano.
#:
#: Solo ficheros VERSIONADOS: el golden tiene que poder regenerarse con un clon limpio.
ARGV = [
    "--fasta", "data/reference/NM_011170.3.fa",
    "--name", "raton",
    "--genbank", "data/reference/NM_011170.3.gb",
    "--fasta-b", "data/reference/NM_000311.5.fa",
    "--name-b", "humano",
    "--genbank-b", "data/reference/NM_000311.5.gb",
]

#: LAS VARIANTES, cada una con su ARGV COMPLETO y su nombre diciendo QUE lleva. Ninguna
#: es «el golden con unos ajustes»: son artefactos distintos que fijan caminos distintos.
VARIANTES = {
    # El analisis de convergencia con la fuente externa esta APAGADO por defecto, asi
    # que sin esta variante su bloque no lo lee ningun golden.
    "raton_informe__con_convergencia.txt": ARGV + [
        "--convergencia", "data/reference/mirarchitect_prnp_export_buena.csv",
    ],
    # LA FORMA NORMAL DE CORRER, y hasta hoy ningun golden la leia. Conecta por rol todo
    # lo que este en OK: `mature.fa`, la mascara con su resumen, el casete y la tabla de
    # PolyA_DB. Es la corrida que mas se parece a la de un usuario, y es justo la que
    # abortaba con un `KeyError: polyadb`.
    #
    # VA CON UNA SOLA ESPECIE, y no es un descuido: el manifiesto conecta `rmsk_mouse.out`
    # POR SU ROL, sin mirar que se esta diseñando, asi que con la segunda especie dentro
    # `RepeatMask.query_length` aborta —«se corrio sobre 2191 nt y se le esta dando una de
    # 2435»—. El guardia hace exactamente lo que debe; lo que dice el aborto es que
    # `--usar-manifiesto` con dos especies NO es una combinacion viable hoy, y eso es
    # informacion, no un problema del golden.
    "raton_informe__con_usar_manifiesto__una_especie.txt": [
        "--fasta", "data/reference/NM_011170.3.fa",
        "--name", "raton",
        "--genbank", "data/reference/NM_011170.3.gb",
        "--usar-manifiesto",
    ],
}


#: SOBRE QUE SE GENERA CADA GOLDEN, en su propia cabecera. Sale de que al arreglar el
#: marco del aviso de multiplexado cambio UN golden y no cambiaron los otros tres — y esa
#: lectura, «el que no cambia confirma donde estaba el fallo tanto como el que cambia»,
#: solo se pudo hacer ABRIENDO ESTE FICHERO.
#:
#: Un artefacto de verificacion que no declara sobre que corre no permite interpretar su
#: SILENCIO: un golden que no cambia puede significar «el fallo no esta ahi» o «desde ahi
#: no se puede ver», y son cosas distintas. La cabecera contesta eso sin salir del fichero.
#:
#: LAS DOS CONFIGURACIONES SON REALES y por eso conviven. El transcrito entero es lo que
#: tilan la pagina y el CLI; el 3'UTR pelado es la via «lo que subo YA es el 3'UTR», que la
#: app soporta. No es el caso de `--inmunes 4`, que era una configuracion FANTASMA que
#: ningun usuario usaba: aqui mover los goldens al transcrito PERDERIA cobertura en vez de
#: ganar nada. Se añaden variantes, que es la regla ya escrita de este fichero.
CONFIGURACION = {
    "raton_informe.txt": (
        "el CLI de diseño sobre el TRANSCRITO ENTERO de las dos especies "
        "(NM_011170.3 + NM_000311.5, con sus .gb), configuracion POR DEFECTO"
    ),
    "raton_informe__con_convergencia.txt": (
        "lo mismo sobre el TRANSCRITO ENTERO, más --convergencia: sin esta variante el "
        "bloque de convergencia no lo lee ningún golden"
    ),
    "raton_informe__con_usar_manifiesto__una_especie.txt": (
        "el CLI sobre el TRANSCRITO ENTERO del raton con --usar-manifiesto, que es LA "
        "FORMA NORMAL DE CORRER; con una sola especie a propósito"
    ),
    "pagina_raton.txt": (
        "el camino de la PAGINA entero sobre el TRANSCRITO ENTERO del raton, con la "
        "anatomía del fixture verificado"
    ),
    "ficha_raton_200.txt": (
        "la ficha de un candidato sobre el 3'UTR PELADO del raton, que es la via «lo "
        "que subo YA es el 3'UTR»"
    ),
    "ficha_raton__transcrito.txt": (
        "la MISMA ficha sobre el TRANSCRITO ENTERO, que es lo que tilan la pagina y el "
        "CLI: sin ella, esta salida no se leia nunca en el marco de uso"
    ),
    "informe_documento.md": (
        "el informe-documento sobre el 3'UTR PELADO del raton, que es la via «lo que "
        "subo YA es el 3'UTR»"
    ),
    "informe_documento__transcrito.md": (
        "el MISMO documento sobre el TRANSCRITO ENTERO, que es lo que tilan la pagina y "
        "el CLI: sin ella, esta salida no se leia nunca en el marco de uso"
    ),
}


def cabecera(nombre: str) -> str:
    """La cabecera que declara sobre que se genera ese golden.

    No se transcribe en ningun sitio: la escribe el generador y la LEE el test, las dos
    de `CONFIGURACION`, asi que no puede describir una entrada y generarse con otra
    (principio nº 13).
    """
    if nombre not in CONFIGURACION:
        raise SystemExit(
            f"El golden {nombre!r} no declara sobre que se genera. Añadelo a "
            f"`CONFIGURACION`: sin eso, que no cambie no se puede interpretar."
        )
    texto = f"GOLDEN — se genera con: {CONFIGURACION[nombre]}."
    if nombre.endswith(".md"):
        return f"<!-- {texto} -->\n\n"
    return f"# {texto}\n\n"


def generar(destino: Path, argv: list[str] | None = None) -> str:
    """Corre el diseño de verdad y devuelve el informe del raton.

    `argv` COMPLETO, no unos extras sobre el de por defecto: una variante es otro
    artefacto, no el mismo con ajustes. Ver el principio nº 18.
    """
    with tempfile.TemporaryDirectory() as tmp:
        proceso = subprocess.run(
            [sys.executable, "tools/design.py", *(argv or ARGV), "--out", tmp],
            cwd=RAIZ, capture_output=True, text=True,
        )
        if proceso.returncode != 0:
            raise SystemExit(
                f"El diseño fallo con código {proceso.returncode}; no se regenera el "
                f"golden con una salida incompleta.\n{proceso.stdout}\n{proceso.stderr}"
            )
        return cabecera(destino.name) + (
            Path(tmp) / "raton_informe.txt"
        ).read_text(encoding="utf-8")


def generar_ficha() -> str:
    """La ficha de `3utr:200`, con la misma disciplina que el informe: entera.

    Se fija la del `200` porque es el candidato que mas cosas reune a la vez: inmune al
    truncamiento, marcado en el esterico, sin techo, con un hexamero promovido por medida
    a 14 nt y sin ninguna corrida de BLAST — o sea, con `NOT_RUN` visible.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.dossier import build_dossier
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(REFERENCES["NM_011170.3"])
    # La tabla de PolyA_DB la resuelve `tile_utr` del FICHERO del gestor: aqui no se
    # pasa nada. Pasarla a mano era lo que hacia que el golden se generara con la
    # constante mientras la app leia el fichero — dos caminos, y el golden dejaba
    # de comprobar el de verdad.
    informe = tile_utr(utr3)
    # `default_config()`, NO un `SelectionConfig` a mano: el panel de 10 y la cuota de 4
    # son las constantes del proyecto, y tecleadas aqui el golden dejaba de enterarse si
    # alguien las cambiaba. Es `--inmunes 4` con otra forma (principio nº 18).
    seleccion = select_from_report(informe, default_config())
    return cabecera("ficha_raton_200.txt") + build_dossier(
        species="raton", tiling=informe, selection=seleccion, start=200,
        # Con `target` la ficha puede contar los sitios de esta seed en su PROPIA diana,
        # que es lo que descubrio que cuatro del panel tienen un segundo sitio.
        target=utr3,
    ).render()


def generar_documento() -> str:
    """El informe-documento entero, en su fuente markdown.

    Hoy sale PARCIAL porque hay frentes abiertos, y eso es parte de lo que fija: el dia
    que se cierre uno, el golden lo enseñara en el diff.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.informe_doc import build_document
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(REFERENCES["NM_011170.3"])
    # La tabla de PolyA_DB la resuelve `tile_utr` del FICHERO del gestor: aqui no se
    # pasa nada. Pasarla a mano era lo que hacia que el golden se generara con la
    # constante mientras la app leia el fichero — dos caminos, y el golden dejaba
    # de comprobar el de verdad.
    informe = tile_utr(utr3)
    # `default_config()`, NO un `SelectionConfig` a mano: el panel de 10 y la cuota de 4
    # son las constantes del proyecto, y tecleadas aqui el golden dejaba de enterarse si
    # alguien las cambiaba. Es `--inmunes 4` con otra forma (principio nº 18).
    seleccion = select_from_report(informe, default_config())
    return cabecera("informe_documento.md") + build_document(
        species="mouse", tiling=informe, selection=seleccion,
        generated=FECHA_GOLDEN,
        anatomy_source="lo tilado ES el 3'UTR (fixture verificado por md5)",
        dossier_starts=(200,), target=utr3,
    ).markdown()


def _tilado_del_transcrito():
    """El transcrito ENTERO con su anatomia, que es lo que tilan la pagina y el CLI.

    Una sola fuente para las dos variantes: con dos copias, una podria quedarse con otra
    anatomia y las dos saldrian con la forma correcta.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.anatomy import Anatomy, RegionSource
    from shmir_design.reference import REFERENCES, load_reference
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    referencia = REFERENCES["NM_011170.3"]
    secuencia = load_reference(referencia)
    anatomia = Anatomy.from_cds(
        cds=referencia.cds,
        length=len(secuencia),
        source=RegionSource.FIXTURE_VERIFICADO,
    )
    informe = tile_utr(secuencia, anatomy=anatomia)
    return secuencia, anatomia, informe, select_from_report(informe, default_config())


def generar_ficha_transcrito() -> str:
    """La MISMA ficha, sobre el transcrito entero.

    No sustituye a `generar_ficha`: la acompaña. El 3'UTR pelado es una via real de la
    app —«lo que subo YA es el 3'UTR»— y moverla habria PERDIDO esa cobertura; el
    transcrito es lo que tilan la pagina y el CLI, y hasta hoy esta salida no se leia
    nunca en ese marco. Es la regla ya escrita: una variante ADICIONAL cuyo nombre dice
    que lleva, nunca un golden con parametros puestos a mano.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.dossier import build_dossier

    secuencia, _anatomia, informe, seleccion = _tilado_del_transcrito()
    # El candidato es el MISMO sitio que en la otra variante (`3utr:200`), en su marco:
    # lo CONVIERTE la anatomia en vez de teclear 1149 (principio nº 13). Tecleado, el
    # dia que cambie el CDS las dos variantes describirian sitios distintos.
    inicio = _anatomia.transcript_position(200)
    return cabecera("ficha_raton__transcrito.txt") + build_dossier(
        species="raton", tiling=informe, selection=seleccion, start=inicio,
        target=secuencia,
    ).render()


def generar_documento_transcrito() -> str:
    """El MISMO documento, sobre el transcrito entero. Ver `generar_ficha_transcrito`."""
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.informe_doc import build_document

    secuencia, anatomia, informe, seleccion = _tilado_del_transcrito()
    inicio = anatomia.transcript_position(200)
    return cabecera("informe_documento__transcrito.md") + build_document(
        species="mouse", tiling=informe, selection=seleccion,
        generated=FECHA_GOLDEN,
        anatomy_source="CDS del fixture verificado por md5 (transcrito entero)",
        dossier_starts=(inicio,), target=secuencia, anatomy=anatomia,
    ).markdown()


def generar_pagina() -> str:
    """El camino de la PAGINA, entero, con lo que el usuario sube: el `.gb` murino.

    Es el golden que faltaba. Los otros tres fijan salidas del nucleo; este fija la
    juntura entre piezas —anatomia, tilado, estimacion, mapa, semaforo, informe— que es
    donde aparecieron los tres fallos de la primera ejecucion real con 2.767 tests en
    verde.

    Solo ficheros VERSIONADOS, como los demas: sin manifiesto, para que se regenere con
    un clon limpio.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.anatomy import Anatomy, RegionSource
    from shmir_design.presentation import page_snapshot
    from shmir_design.reference import REFERENCES, load_reference
    from shmir_design.selection import default_config

    referencia = REFERENCES["NM_011170.3"]
    secuencia = load_reference(referencia)
    return cabecera("pagina_raton.txt") + page_snapshot(
        species="raton",
        sequence=secuencia,
        anatomy=Anatomy.from_cds(
            cds=referencia.cds,
            length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        ),
        generated=FECHA_GOLDEN,
        # Igual que los otros dos: la configuracion del proyecto, no una tecleada.
        config=default_config(),
    )


def escribir(destino: Path, contenido: str) -> None:
    antes = destino.read_text(encoding="utf-8") if destino.is_file() else ""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    lineas = len(contenido.splitlines())
    estado = "Sin cambios" if antes == contenido else "REGENERADO"
    print(f"{estado}: {destino} ({lineas} lineas).")


def main() -> int:
    # UNA tabla: destino -> como se produce. Con cuatro bloques copiados, la variante
    # nueva se olvida en uno y su golden deja de regenerarse sin que nadie lo note.
    artefactos = [
        *[(GOLDEN.parent / n, lambda a=a, n=n: generar(GOLDEN.parent / n, a))
          for n, a in VARIANTES.items()],
        (GOLDEN, lambda: generar(GOLDEN)),
        (FICHA, generar_ficha),
        (GOLDEN.parent / "ficha_raton__transcrito.txt", generar_ficha_transcrito),
        (DOCUMENTO, generar_documento),
        (GOLDEN.parent / "informe_documento__transcrito.md",
         generar_documento_transcrito),
        (PAGINA, generar_pagina),
    ]
    faltan = {p.name for p in (d for d, _ in artefactos)} ^ set(CONFIGURACION)
    if faltan:
        raise SystemExit(
            f"Estos goldens no cuadran entre lo que se genera y lo que declara "
            f"`CONFIGURACION`: {', '.join(sorted(faltan))}. Se aborta: una entrada "
            f"huerfana describe algo que ya no existe, y uno sin entrada sale mudo."
        )
    for destino, producir in artefactos:
        escribir(destino, producir())
    print(
        "Revisa los diffs ANTES de commitear: es para lo que existen. Y cada fichero "
        "declara en su cabecera sobre que se genera, para que un golden que NO cambia "
        "se pueda interpretar."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
