"""El casete del transgen, y el artefacto que hay que no cometer con el.

El filtro del transgen (`specificity.filter_transgene`) pregunta si una guia apaga la
propia construccion terapeutica. La pregunta solo tiene sentido si lo que se le pasa es
lo que la celula va a TRANSCRIBIR Y MADURAR.

Si el casete lleva ya el modulo del shmiR y se pasa el GENOMA —con el intron dentro—,
cada guia encuentra su propia horquilla ahi y sale FAIL. El panel entero se cae por un
artefacto que parece un resultado, y el motivo escrito («la guia toca el casete») es
literalmente cierto. Por eso se detecta y se avisa.

Se detecta POR SECUENCIA, no por el nombre del fichero: se busca el loop de los andamios
conocidos. Un nombre puede decir «parental» y traer otra cosa.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Loops de los andamios que este proyecto conoce, en ADN. Si alguno aparece en el
#: casete, el casete lleva un modulo de shmiR/shRNA dentro.
KNOWN_LOOPS = {
    "miR-E / SGEP": "TAGTGAAGCCACAGATGTA",
    "miR-30a": "CTGTGAAGCCACAGATGGG",
}


@dataclass(frozen=True)
class ScaffoldModuleWarning:
    carries: bool
    found: tuple[tuple[str, str], ...]
    records: tuple[str, ...]

    def describe(self) -> str:
        if not self.carries:
            return (
                "El casete NO lleva ningún loop de andamio conocido: es un PARENTAL, "
                "sin módulo de shmiR. El filtro del transgén se puede leer tal cual — "
                "un FAIL aquí es un impacto real contra la construcción, no contra la "
                "propia horquilla del candidato."
            )
        detalle = "; ".join(
            f"{nombre} ({loop}) en {registro}"
            for (nombre, loop), registro in zip(self.found, self.records)
        )
        return (
            f"AVISO DURO — el casete YA LLEVA un módulo de shmiR: {detalle}. "
            f"Si lo que se ha pasado es el GENOMA (con el intrón dentro), toda guía da "
            f"impacto contra SU PROPIA HORQUILLA y el filtro tumba el panel entero por "
            f"un artefacto — con un motivo que además es literalmente cierto, así que "
            f"no se ve. Lo que hay que pasar en ese caso es el TRANSCRITO MADURO, sin "
            f"el intrón. Revisa este veredicto antes de usarlo."
        )


def carries_scaffold_module(database) -> ScaffoldModuleWarning:
    """¿El casete contiene el loop de algun andamio conocido?"""
    if database is None:
        raise ValueError(
            "No hay casete que mirar; se aborta en vez de decir que no lleva módulo."
        )
    encontrados: list[tuple[str, str]] = []
    registros: list[str] = []
    for nombre, secuencia in database.records.items():
        limpia = secuencia.upper().replace("U", "T")
        for andamio, loop in KNOWN_LOOPS.items():
            if loop in limpia:
                encontrados.append((andamio, loop))
                registros.append(nombre)
    return ScaffoldModuleWarning(
        carries=bool(encontrados),
        found=tuple(encontrados),
        records=tuple(registros),
    )
