"""Errores de shmir-design.

Regla 2: todo fallo se propaga con un mensaje que diga QUE fallo y QUE paso queda sin
ejecutar. Ninguna de estas excepciones se captura para silenciarla.
"""

from __future__ import annotations


class ShmirDesignError(Exception):
    """Raiz de los errores del proyecto."""


class MissingSequenceError(ShmirDesignError):
    """Falta una secuencia y el paso no puede continuar.

    Regla 1: aqui se aborta. Nunca se genera, completa ni reconstruye la secuencia
    ausente, ni se sustituye por una placeholder que pueda circular como si fuera dato.
    """


class InvalidSequenceError(ShmirDesignError):
    """La secuencia contiene caracteres que no son nucleotidos."""


class ChecksumMismatchError(ShmirDesignError):
    """Una secuencia descargada no coincide con su referencia verificada.

    Es la excepcion mas importante del proyecto: significa que la secuencia que hay
    delante NO es la que dice ser. El paso se aborta siempre; nunca se continua con
    "la que haya" ni se reintenta con otra fuente sin decirlo.
    """


class FetchError(ShmirDesignError):
    """Una descarga no se pudo completar o no llego en el formato esperado.

    Incluye el caso traicionero: NCBI responde 200 con un XML de error, asi que un
    codigo HTTP correcto no basta para dar la respuesta por buena.
    """
