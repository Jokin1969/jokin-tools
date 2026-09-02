"""Verificador de la regla 2 de shmir-design (ver `apps/shmir-design/CLAUDE.md`).

Falla si encuentra manejo de errores que se traga un fallo en lugar de propagarlo:

  BARE_EXCEPT       `except:` sin tipo de excepcion.
  SWALLOWED_EXCEPT  un `except` cuyo cuerpo no relanza nada.
  BROAD_SUPPRESS    `contextlib.suppress(Exception)` o `suppress(BaseException)`.

Un `except` de excepcion concreta puede tragarse el fallo solo si el bloque lleva un
comentario `# rule2-ok: <motivo>` que explique por que ningun paso queda sin ejecutar.
Esa marca no rescata a un `except` amplio ni a un `except` desnudo.

Uso:
    python3 apps/shmir-design/tools/check_rules.py [ruta ...]

Sin rutas analiza todo `apps/shmir-design/`. Codigos de salida: 0 limpio, 1 violaciones,
2 error de uso o fichero no analizable (nunca se ignora un fichero en silencio).

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import ast
import io
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

BROAD_NAMES = frozenset({"Exception", "BaseException"})
OK_MARKER = "rule2-ok"

# Nodos cuyo interior pertenece a otro ambito: un `raise` ahi dentro no propaga el
# fallo del `except` que lo contiene.
NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


@dataclass(frozen=True)
class Violation:
    code: str
    filename: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.filename}:{self.line}: {self.code}: {self.message}"


class RuleCheckError(Exception):
    """Un fichero no se pudo analizar; el analisis queda incompleto."""


def _handler_is_broad(handler: ast.ExceptHandler) -> bool:
    node = handler.type
    if node is None:
        return True
    candidates = node.elts if isinstance(node, ast.Tuple) else [node]
    return any(isinstance(c, ast.Name) and c.id in BROAD_NAMES for c in candidates)


def _inside_nested_scope(root: ast.stmt, target: ast.AST) -> bool:
    """True si `target` cuelga de una funcion/clase anidada dentro de `root`."""
    stack: list[tuple[ast.AST, bool]] = [(root, False)]
    while stack:
        node, nested = stack.pop()
        if node is target:
            return nested
        for child in ast.iter_child_nodes(node):
            stack.append((child, nested or isinstance(node, NESTED_SCOPES)))
    return False


def _raises_in_own_scope(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise) and not _inside_nested_scope(stmt, node):
                return True
    return False


def _is_broad_suppress(node: ast.AST) -> bool:
    if not isinstance(node, (ast.With, ast.AsyncWith)):
        return False
    for item in node.items:
        call = item.context_expr
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != "suppress":
            continue
        if any(isinstance(a, ast.Name) and a.id in BROAD_NAMES for a in call.args):
            return True
    return False


def _marked_lines(source: str) -> set[int]:
    """Lineas con un comentario `# rule2-ok: ...`."""
    marked: set[int] = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and OK_MARKER in token.string:
                marked.add(token.start[0])
    except tokenize.TokenError as exc:
        raise RuleCheckError(
            f"No se pudo tokenizar el fuente ({exc}); "
            f"se aborta la comprobación de la regla 2 sobre este fichero."
        ) from exc
    return marked


def _has_marker(handler: ast.ExceptHandler, marked: set[int]) -> bool:
    end = handler.end_lineno or handler.lineno
    return any(line in marked for line in range(handler.lineno, end + 1))


def scan_source(source: str, filename: str) -> list[Violation]:
    """Analiza `source` y devuelve las violaciones de la regla 2.

    Propaga `SyntaxError` si el fuente no parsea: un fichero que no se puede analizar
    no es un fichero limpio.
    """
    tree = ast.parse(source, filename=filename)
    marked = _marked_lines(source)
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if _is_broad_suppress(node):
            violations.append(
                Violation(
                    code="BROAD_SUPPRESS",
                    filename=filename,
                    line=node.lineno,
                    message=(
                        "`suppress(Exception)` descarta cualquier fallo sin dejar "
                        "rastro; captura la excepción concreta y propagala con "
                        "contexto (regla 2)."
                    ),
                )
            )
            continue

        if not isinstance(node, ast.ExceptHandler):
            continue

        if node.type is None:
            violations.append(
                Violation(
                    code="BARE_EXCEPT",
                    filename=filename,
                    line=node.lineno,
                    message=(
                        "`except:` sin tipo captura hasta lo que no esperabas; nombra "
                        "la excepción concreta y propaga el fallo (regla 2)."
                    ),
                )
            )
            continue

        if _raises_in_own_scope(node.body):
            continue

        broad = _handler_is_broad(node)
        if not broad and _has_marker(node, marked):
            continue

        detail = (
            "`except Exception` que no relanza" if broad else "el `except` no relanza nada"
        )
        hint = (
            "captura la excepción concreta y relanzala con contexto"
            if broad
            else (
                "relanza con contexto (`raise ... from exc`) o justifica el bloque con "
                f"un comentario `# {OK_MARKER}: <motivo>`"
            )
        )
        violations.append(
            Violation(
                code="SWALLOWED_EXCEPT",
                filename=filename,
                line=node.lineno,
                message=(
                    f"{detail}: el fallo desaparece y el paso queda sin ejecutar sin "
                    f"que nadie se entere; {hint} (regla 2)."
                ),
            )
        )

    violations.sort(key=lambda v: (v.line, v.code))
    return violations


def scan_file(path: Path) -> list[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuleCheckError(
            f"No se pudo leer {path} ({exc}); se aborta la comprobación de la "
            f"regla 2: el análisis quedaria incompleto."
        ) from exc
    except UnicodeDecodeError as exc:
        raise RuleCheckError(
            f"{path} no es UTF-8 válido ({exc}); se aborta la comprobación de la "
            f"regla 2 sobre este fichero."
        ) from exc

    try:
        return scan_source(source, str(path))
    except SyntaxError as exc:
        raise RuleCheckError(
            f"{path} no parsea como Python ({exc}); se aborta la comprobación de la "
            f"regla 2: un fichero no analizable no cuenta como limpio."
        ) from exc


def iter_python_files(targets: list[Path]):
    for target in targets:
        if target.is_dir():
            yield from sorted(target.rglob("*.py"))
        elif target.suffix == ".py":
            yield target
        else:
            raise RuleCheckError(
                f"{target} no es un fichero .py ni un directorio; no hay nada que "
                f"comprobar y no se ignora en silencio."
            )


def main(argv: list[str]) -> int:
    project_root = Path(__file__).resolve().parent.parent
    targets = [Path(a) for a in argv] or [project_root]

    missing = [t for t in targets if not t.exists()]
    if missing:
        print(
            "check_rules: no existen estas rutas: " + ", ".join(str(m) for m in missing),
            file=sys.stderr,
        )
        return 2

    violations: list[Violation] = []
    checked = 0
    try:
        for path in iter_python_files(targets):
            violations.extend(scan_file(path))
            checked += 1
    except RuleCheckError as exc:
        # rule2-ok: frontera CLI. El fallo no se pierde: se imprime completo en stderr
        # y sale con codigo 2, que distingue "analisis incompleto" de "sin violaciones".
        print(f"check_rules: {exc}", file=sys.stderr)
        return 2

    if violations:
        for violation in violations:
            print(violation.format())
        print(
            f"\ncheck_rules: {len(violations)} violación(es) de la regla 2 en "
            f"{checked} fichero(s).",
            file=sys.stderr,
        )
        return 1

    print(f"check_rules: {checked} fichero(s) sin violaciones de la regla 2.")

    # ── Alcanzabilidad ──────────────────────────────────────────────────────────
    #
    # Va aquí y no en su propio comando para que se vea SIEMPRE que se comprueban las
    # reglas: un informe que hay que acordarse de pedir es un informe que nadie pide.
    # No decide nada — ver `check_alcance.WHY_NOT_A_FAILURE`— salvo una cosa: una
    # excepción declarada que ya no hace falta SÍ aborta, porque una lista con entradas
    # muertas deja de leerse y tapa el siguiente hallazgo.
    if argv:
        return 0  # con rutas concretas se comprueba la regla 2 y nada más
    from check_alcance import analizar as analizar_alcance

    informe = analizar_alcance(project_root)
    print()
    print(informe.render())
    # ── Datos de una especie que viven en el codigo ─────────────────────────────
    #
    # Misma razon para ponerlo aqui: un informe que hay que acordarse de pedir es un
    # informe que nadie pide. Tampoco decide nada — la categoria la pone una persona en
    # `data/datos_en_codigo.toml`, y el test es quien exige que no falte ninguna.
    from auditar_datos import auditar as auditar_datos

    datos = auditar_datos()
    por_cat = datos["por_categoria"]
    print()
    print("  Datos de una especie que viven en el código:")
    for categoria, titulo in (
        ("dato", "DATO — deberían estar en un fichero del gestor"),
        ("declaracion", "DECLARACIÓN — van en código a propósito"),
        ("prosa", "PROSA — van pegadas a lo que explican"),
    ):
        print(f"    {len(por_cat.get(categoria, ())):3}  {titulo}")
    for fila in por_cat.get("dato", ()):
        print(f"         · {fila['simbolo']} → {fila['fichero']}")
    if datos["sin_clasificar"]:
        print(
            f"\n  SIN CLASIFICAR: {', '.join(sorted(datos['sin_clasificar']))}",
            file=sys.stderr,
        )

    # LOS GUARDIAS, Y CUANDO CORRE CADA UNO (2026-08-27). Va aqui por lo mismo: un
    # informe que hay que acordarse de pedir es un informe que nadie pide. Y lo que
    # senala —INGESTA + puede degradarse + nada lo revalida— son los SIGUIENTES en
    # fallar, asi que tiene que verse en cada tanda y no cuando alguien se acuerde.
    from auditar_guardias import auditar as auditar_guardias

    guardias = auditar_guardias()
    print()
    print("  Guardias, por cuándo corren:")
    for momento in ("INGESTA", "CADA_CORRIDA", "AL_EMITIR", "AL_ABRIR", "AL_CONSTRUIR"):
        print(f"    {len(guardias['momentos'][momento]):3}  {momento}")
    print(f"    {len(guardias['riesgo']):3}  ⚠  INGESTA + se degrada + NADA lo revalida")
    for fila in guardias["riesgo"]:
        print(f"         · {fila['guardia']}")
    print(f"    {len(guardias['solo_suite']):3}  ⚠  sólo los revalida la SUITE")
    for fila in guardias["solo_suite"]:
        print(f"         · {fila['guardia']}")
    for etiqueta, filas in (
        ("guardias sin cubrir", guardias["sin_cubrir"]),
        ("entradas fantasma", guardias["fantasmas"]),
        ("guardias que ya no abortan", guardias["mudos"]),
    ):
        if filas:
            print(f"\n  {etiqueta.upper()}: {', '.join(filas)}", file=sys.stderr)

    # LAS BANDERAS DE LOS CLI, Y CUALES SE RECORREN ENTERAS (2026-08-27). Va aqui por
    # lo mismo que las otras tres, y por una razon propia: es el hueco que ni la
    # alcanzabilidad ni el golden pueden ver —la alcanzabilidad busca simbolos sin
    # llamador y aqui hay llamada escrita; el golden lee la salida POR DEFECTO—. Ahi
    # vive el codigo llamado desde caminos que nadie recorre (principio nº 17).
    from auditar_banderas import auditar as auditar_banderas
    from auditar_banderas import render as render_banderas

    print(render_banderas(auditar_banderas()))

    # LOS ESTADOS DE LA INTERFAZ (2026-08-27). El de banderas cubre los CLI; este cubre
    # la PAGINA, que es donde vive lo que el usuario toca. El eje no son los widgets: son
    # las combinaciones de estado que PINTAN cosas distintas.
    from auditar_estados import auditar as auditar_estados
    from auditar_estados import render as render_estados

    print(render_estados(auditar_estados()))

    # LOS FIXTURES SINTETICOS DONDE EXISTE EL ARTEFACTO REAL (2026-08-29). Segunda mitad
    # del principio nº 18: un parametro tecleado y un fixture sintetico son la misma
    # enfermedad —los dos validan un camino que nadie recorre—. Va aqui por lo mismo que
    # los otros cuatro. No decide nada salvo lo que ya decide su test: fabricar esta
    # permitido, no decir POR QUE no.
    from auditar_fixtures import auditar as auditar_fixtures
    from auditar_fixtures import render as render_fixtures

    print(render_fixtures(auditar_fixtures()))

    # CONDICIONES QUE NO PUEDEN SER FALSAS (2026-08-29). Principio nº 19. A diferencia de
    # los otros cinco, este NO es un informe ni un trinquete: es un GUARDIA. Una rama que
    # no puede ejecutarse no es una decision, asi que el numero correcto es cero y
    # cualquier hallazgo aborta.
    from auditar_condiciones import auditar as auditar_condiciones
    from auditar_condiciones import render as render_condiciones

    condiciones = auditar_condiciones()
    print(render_condiciones(condiciones))

    if condiciones.hallazgos:
        print(
            f"\ncheck_rules: {len(condiciones.hallazgos)} condición(es) que no pueden "
            f"ser falsas.",
            file=sys.stderr,
        )
        return 1

    # SECUENCIAS EMPAREJADAS (2026-08-30). El otro lado del principio nº 19, y el que
    # NO lleva ninguna condicion: `zip` trunca al mas corto en silencio, asi que ninguna
    # busqueda de `if` lo encuentra y lo que sale no es un error sino un informe corto
    # que se lee como un resultado. Guardia tambien: o `strict=`, o el motivo escrito.
    from auditar_pares import auditar as auditar_pares
    from auditar_pares import render as render_pares

    pares = auditar_pares()
    print(render_pares(pares))

    if pares.mudos:
        print(
            f"\ncheck_rules: {len(pares.mudos)} `zip`/`map` de dos secuencias sin "
            f"declarar si van emparejadas.",
            file=sys.stderr,
        )
        return 1

    # CLAVES QUE UN TEST ESCRIBE Y ALGUIEN PRODUCE (2026-09-02). Principio nº 24 hecho
    # auditoria, y GUARDIA como los dos anteriores: un test que construye el diccionario
    # de entrada con la clave que el codigo va a buscar no puede fallar — coincide por
    # construccion. Tres erratas seguidas con esa anatomia (nº 44, nº 47 y nº 48).
    from auditar_claves import cargar_tabla as cargar_claves
    from auditar_claves import exenciones_caducadas, revisar as revisar_claves

    tabla_claves = cargar_claves()
    claves = revisar_claves(tabla=tabla_claves)
    caducadas = exenciones_caducadas(tabla=tabla_claves)
    print("\n── Claves que un test ESCRIBE y alguien PRODUCE ──\n")
    for productor in tabla_claves.get("productor", []):
        print(f"  {productor['nombre']}  [{productor['modo']}]")
    print()
    if claves or caducadas:
        for h in claves:
            print(f"  · {h['fichero']}:{h['linea']}  {h['clave']!r}  → {h['productor']}")
        for e in caducadas:
            print(f"  · EXENCIÓN CADUCADA: {e}")
    else:
        print("  0 — el número correcto. Ningún test pregunta por la clave que él mismo")
        print("      ha escrito.")
    print(
        "\n  Se le pide la clave al productor. Un test que la escribe coincide por\n"
        "  construcción: su verde no dice nada del emparejamiento real.\n"
    )
    if claves or caducadas:
        print(
            f"\ncheck_rules: {len(claves) + len(caducadas)} clave(s) que un test "
            f"escribe y alguien produce.",
            file=sys.stderr,
        )
        return 1

    # UNA MAGNITUD, UN SITIO QUE LA CALCULA (2026-09-02). La otra cara del principio
    # nº 24: los digestos y los identificadores son GUARDIA —dos sitios calculando el
    # mismo numero es un fallo— y las formulas repetidas entre modulos, TRINQUETE.
    from auditar_claves import digestos, revisar_magnitudes

    mag = revisar_magnitudes()
    print("\n── Una magnitud, un sitio que la calcula ──\n")
    print(f"  digestos declarados      {len(digestos())}")
    print(f"  identificadores a mano   {len(mag['identificadores'])} (el correcto es 0)")
    print(
        f"  constructores permisivos {len(mag['permisivos'])} sin declarar"
        f" (el correcto es 0)"
    )
    print(
        f"  fórmulas repetidas       {len(mag['formulas'])} de un techo de {mag['techo']}"
        f" — sólo puede bajar"
    )
    print()
    problemas = []
    for sitio in mag["sin_declarar"]:
        problemas.append(f"  · {sitio} calcula un digesto y no dice QUÉ magnitud")
    for sitio in mag["muertas"]:
        problemas.append(f"  · {sitio} está declarado y ya no calcula nada")
    for magnitud, sitios in mag["repetidas"].items():
        problemas.append(
            f"  · «{magnitud}» la calculan {len(sitios)} sitios: {', '.join(sitios)}"
        )
    for sitio in mag["identificadores"]:
        problemas.append(f"  · {sitio} construye un `*_id` a mano (errata nº 48)")
    for sitio in mag["permisivos"]:
        problemas.append(
            f"  · {sitio} hace `str(argumento)` y con eso construye algo, sin comprobar "
            f"el tipo (errata nº 50)"
        )
    for sitio in mag["permisivos_muertos"]:
        problemas.append(
            f"  · {sitio} está declarado como constructor permisivo y ya no lo es"
        )
    if mag["techo_roto"]:
        problemas.append(
            f"  · fórmulas repetidas: {len(mag['formulas'])} contra un techo de "
            f"{mag['techo']}. Si ha subido, alguien duplicó una; si ha bajado, el techo "
            f"está caducado y se actualiza en data/magnitudes.toml."
        )
    if problemas:
        print("\n".join(problemas))
        print(
            "\n  O uno DELEGA en el otro, o son números distintos y el motivo lo dice."
            "\n  Nada obliga a que dos cálculos del mismo número coincidan.\n"
        )
        print(
            f"\ncheck_rules: {len(problemas)} magnitud(es) calculada(s) por duplicado.",
            file=sys.stderr,
        )
        return 1
    print("  Ninguna magnitud se calcula dos veces sin decir por qué.\n")

    if informe.stale:
        print(
            f"\ncheck_rules: {len(informe.stale)} excepción(es) de alcanzabilidad que "
            f"ya no hacen falta.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
