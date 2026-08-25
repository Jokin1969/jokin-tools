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
            f"se aborta la comprobacion de la regla 2 sobre este fichero."
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
                        "rastro; captura la excepcion concreta y propagala con "
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
                        "la excepcion concreta y propaga el fallo (regla 2)."
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
            "captura la excepcion concreta y relanzala con contexto"
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
            f"No se pudo leer {path} ({exc}); se aborta la comprobacion de la "
            f"regla 2: el analisis quedaria incompleto."
        ) from exc
    except UnicodeDecodeError as exc:
        raise RuleCheckError(
            f"{path} no es UTF-8 valido ({exc}); se aborta la comprobacion de la "
            f"regla 2 sobre este fichero."
        ) from exc

    try:
        return scan_source(source, str(path))
    except SyntaxError as exc:
        raise RuleCheckError(
            f"{path} no parsea como Python ({exc}); se aborta la comprobacion de la "
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
            f"\ncheck_rules: {len(violations)} violacion(es) de la regla 2 en "
            f"{checked} fichero(s).",
            file=sys.stderr,
        )
        return 1

    print(f"check_rules: {checked} fichero(s) sin violaciones de la regla 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
