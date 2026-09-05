#!/usr/bin/env python3
"""Auditoria de las reglas de geometria: que dan sobre CADA intron del registro.

Sale de la errata nº 10. Su corolario dice que **un calculo solo se puede validar sobre
mas de un caso**, y `mvm_actual` fue el UNICO intron del registro durante meses: toda
regla de geometria escrita en ese periodo esta calibrada sobre un caso y no se distingue
de una que coincide con ese caso.

Esto NO arregla nada. Emite un informe: que mide cada regla, de donde sale su valor, y
que da sobre cada intron. Lo que se salga en el segundo caso es lo siguiente en caer.

Se vuelve a correr cuando entre un tercer intron, que es cuando volvera a servir.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design import spacers  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.hard_filters import gc_fraction  # noqa: E402
from shmir_design.introns import (  # noqa: E402
    BRANCH_WINDOW,
    INTRONS,
    MIN_INTRON_LENGTH,
    PPT_WINDOW,
    TYPICAL_DONOR_TO_BRANCH,
    donor_to_branch,
    get as get_intron,
    locate_elements,
)

#: EL MODULO, que es lo unico comun a los dos intrones. CUANTO se intercala en cada uno
#: NO es este numero: lo dice el propio intron (`Intron.inserted_length`), porque el que
#: se ensambla de piezas lleva ademas los dos espaciadores y el que llega entero no —
#: `_insert_module` aborta si se le piden. Aqui habia un `INSERTADO` global de
#: 149+20+45 aplicado a los DOS, y sobre el quimerico daba donante→punto 314-318 cuando
#: el intron que se monta lo tiene en 249-253 (errata nº 106).
MODULO = 149


def _secuencias():
    salida = {}
    for nombre, entrada in sorted(INTRONS.items()):
        try:
            salida[nombre] = entrada.require_sequence()
        except ShmirDesignError as exc:
            # rule2-ok: NO se traga nada. El motivo entero va al informe, que es la
            # salida de esta herramienta: un intron sin secuencia no se puede auditar y
            # eso es un HALLAZGO, no un fallo que esconder.
            salida[nombre] = None
            print(f"  · {nombre}: SIN SECUENCIA, no se audita. {exc}")
    return salida


def main() -> int:
    print(__doc__)
    print("=" * 78)
    secuencias = _secuencias()
    vivos = {n: s for n, s in secuencias.items() if s}
    if len(vivos) < 2:
        print(
            "\nSÓLO HAY UN INTRÓN CON SECUENCIA. Esta auditoría NO PUEDE DECIR NADA: es "
            "exactamente la situación que la errata nº 10 describe. Vuelve con el segundo."
        )
        return 0

    elementos = {n: locate_elements(s, name=n) for n, s in vivos.items()}
    nombres = list(vivos)
    ancho = max(len(n) for n in nombres)

    def fila(etiqueta, valores, origen):
        celdas = "  ".join(f"{str(valores[n]):>{max(ancho, 12)}}" for n in nombres)
        print(f"  {etiqueta:<32} {celdas}   [{origen}]")

    print(f"\n  {'regla':<32} " + "  ".join(f"{n:>{max(ancho, 12)}}" for n in nombres))
    print("  " + "-" * (34 + (max(ancho, 12) + 2) * len(nombres) + 20))

    fila("longitud del intrón vacío",
         {n: len(s) for n, s in vivos.items()}, "dato")
    fila(f"¿pasa MIN_INTRON_LENGTH={MIN_INTRON_LENGTH}?",
         {n: "sí" if len(s) >= MIN_INTRON_LENGTH else "NO" for n, s in vivos.items()},
         "SOSPECHOSA: 80 son dos menos que los 82 del MVM")
    fila(f"candidatos a punto (ventana {BRANCH_WINDOW[0]}-{BRANCH_WINDOW[1]})",
         {n: len(e.branch_candidates) for n, e in elementos.items()},
         "CALIBRADA contra los dos, 2026-08-27")
    fila("punto→aceptor (nt)",
         {n: _rango(e.branch_to_acceptor_range) for n, e in elementos.items()}, "dato")
    fila(f"tracto: longitud (ventana {PPT_WINDOW})",
         {n: len(e.ppt.sequence) for n, e in elementos.items()},
         "CORREGIDA por la errata nº 10")
    fila("tracto: hueco al aceptor",
         {n: e.acceptor.start - 1 - e.ppt.end for n, e in elementos.items()},
         "el que rompió la regla vieja")
    fila("GC del intrón",
         {n: f"{gc_fraction(s):.3f}" for n, s in vivos.items()}, "dato")
    fila(f"¿en la ventana {spacers.GC_MIN}-{spacers.GC_MAX}?",
         {n: "sí" if spacers.GC_MIN <= gc_fraction(s) <= spacers.GC_MAX else "NO"
          for n, s in vivos.items()},
         "esa ventana es de ESPACIADORES, no de intrones")
    fila("su donante está en la lista de prohibidos",
         {n: "sí" if s[:6] in spacers.DONORS_FORBIDDEN_IN_SPACERS else "no"
          for n, s in vivos.items()},
         "RIESGO — ver abajo")

    print("\n  RIESGOS (no son observaciones: son reglas que hoy aciertan por dónde se")
    print("  aplican y no por lo que dicen — el patrón del `.out` conectado por rol):")
    print("    · La lista de donantes prohibidos contiene GTAAGT y GTAAGG, que son los")
    print("      donantes LEGÍTIMOS del quimérico y del MVM. Sobre un espaciador es")
    print("      correcta; sobre secuencia de intrón daría el veredicto invertido.")
    print("      DESACTIVADO 2026-08-27: se llama `DONORS_FORBIDDEN_IN_SPACERS` y")
    print("      `spacer_rejections` ABORTA si lo que recibe no es un espaciador.")
    print("    · La ventana GC 0.28-0.45 es de ESPACIADORES. Que los dos intrones caigan")
    print("      dentro es casualidad, no validación: nadie la calibró sobre intrones.")

    print(f"\n  DONANTE→PUNTO con el módulo de {MODULO} nt dentro, y lo intercalado "
          f"DERIVADO de cada intrón\n  (rango típico "
          f"{TYPICAL_DONOR_TO_BRANCH[0]}-{TYPICAL_DONOR_TO_BRANCH[1]}):")
    for nombre, elem in elementos.items():
        insertado = get_intron(nombre).inserted_length(MODULO)
        print(f"    {nombre}: se intercalan {insertado} nt "
              f"({'módulo solo' if insertado == MODULO else 'módulo + los dos espaciadores'})")
        d = donor_to_branch(elem, name=nombre, inserted=insertado)
        if d is None:
            print(f"    {nombre}: sin candidatos, NO CALCULABLE")
            continue
        for linea in d.describe():
            print(f"    {linea}")

    from shmir_design.introns import THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES

    print(f"\n  LECTURA: {THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES}")
    return 0


def _rango(par):
    if par is None:
        return "—"
    return str(par[0]) if par[0] == par[1] else f"{par[0]}-{par[1]}"


if __name__ == "__main__":
    raise SystemExit(main())
