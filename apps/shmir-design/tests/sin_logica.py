"""La comprobacion de la regla 6 sobre el TEXTO de la pagina, en un solo sitio.

Estaba copiada en tres tests con la misma lista de prohibiciones, y la copia tenia un
fallo: se buscaba `"int("` como SUBCADENA, asi que `run_fingerprint(` la contiene y el
guardia saltaba sobre una llamada que no convierte nada. Un guardia que salta donde no
hay nada que guardar se acaba desactivando, que es justo lo contrario de lo que hace
falta aqui. Se busca la llamada como TOKEN: `\\b` delante del nombre.
"""

import re

# Cada patron es la LLAMADA, no el nombre suelto: lo que la regla 6 prohibe en la
# pagina es convertir, comparar y ordenar datos, no nombrar.
PROHIBIDO_EN_LA_PAGINA = (
    r"\bint\(",
    r"\bfloat\(",
    r"\.upper\(\)",
    r"\.lower\(\)",
    r"\bsorted\(",
)


def comprobar_sin_logica(caso, region: str) -> None:
    """Aborta el test si `region` (el texto de un modal o panel) decide algo."""
    for prohibido in PROHIBIDO_EN_LA_PAGINA:
        encontrado = re.search(prohibido, region)
        caso.assertIsNone(
            encontrado,
            f"la pagina usa {prohibido}: {region[max(0, encontrado.start() - 60):encontrado.end() + 20]!r}"
            if encontrado
            else prohibido,
        )
