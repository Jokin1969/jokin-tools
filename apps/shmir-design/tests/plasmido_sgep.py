"""El plásmido de SGEP para los tests, en UN SOLO SITIO.

Antes cada test montaba **un plásmido de relleno de A's con los dos contextos metidos en
sus coordenadas declaradas**. Eso probaba el COMPARADOR y no las coordenadas —principio
nº 18—, y con la comprobación derivando de la anotación ya no puede funcionar: un relleno
no tiene bloque FEATURES del que anclarse.

Ahora se usa el fichero de verdad, y las dos variantes adversarias se construyen A PARTIR
DE ÉL: cambiando una base o moviendo la anotación. Viven aquí y no copiadas en tres
ficheros por lo de siempre — dos copias del mismo fixture divergen igual que dos copias
de un dato.
"""

from pathlib import Path

from tests.ficheros_del_deposito import falta, hay

NOMBRE = "addgene_111170.gb"
RUTA = Path(__file__).resolve().parent.parent / "data" / "reference" / NOMBRE

#: Para `@unittest.skipUnless`. **NO es `RUTA.is_file()`**, que es lo que ponía aquí: un
#: fichero de 0 bytes pasa `is_file()` y no contiene nada, así que los tests que cuelgan
#: de esto correrían contra un GenBank vacío — y lo que sale de ahí no es un fallo de
#: fichero, es una horquilla que no pliega y una densidad de dianas de cero, o sea un
#: resultado con la forma correcta. Errata nº 15.
HAY = hay(NOMBRE)
FALTA = falta(NOMBRE)


def texto() -> str:
    """El GenBank tal cual."""
    return RUTA.read_text(encoding="utf-8")


def con_una_base_cambiada(posicion: int) -> str:
    """El mismo GenBank con UNA base distinta, reescribiendo su bloque ORIGIN.

    Se reescribe el bloque en vez de tocar el texto a mano porque el ORIGIN va en grupos
    de diez separados por espacios: un `replace` sobre la cadena entera no encuentra nada
    y el «control adversario» pasaría sin haber cambiado ni una base.
    """
    cabecera, origen = texto().split("ORIGIN", 1)
    secuencia = "".join(c for c in origen if c.isalpha()).upper()
    nueva = "A" if secuencia[posicion - 1] != "A" else "C"
    secuencia = secuencia[: posicion - 1] + nueva + secuencia[posicion:]
    lineas = []
    for i in range(0, len(secuencia), 60):
        trozo = secuencia[i : i + 60].lower()
        bloques = " ".join(trozo[j : j + 10] for j in range(0, len(trozo), 10))
        lineas.append(f"{i + 1:>9} {bloques}")
    return cabecera + "ORIGIN\n" + "\n".join(lineas) + "\n//\n"


def con_la_anotacion_movida() -> str:
    """El mismo GenBank con la feature del loop en otro sitio.

    La otra mitad del control: si la anotación deja de caer dentro del andamio localizado
    por secuencia, una de las dos vías está mal. Sin esto, el ancla sería decorativa.
    """
    return texto().replace(
        "     ncRNA           1801..1815", "     ncRNA           801..815", 1
    )
