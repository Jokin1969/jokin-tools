"""Fixture del análisis de alcanzabilidad. No es código del proyecto.

Vive aquí y no se inventa como cadena dentro del test porque el análisis lee ficheros
reales: un fixture que no se parece al real no prueba nada — la lección del test de humo
de `/shmir`, donde una petición cruda pasaba mientras el navegador recibía un 403.
"""


def nadie_me_llama():
    """Pública y sin ningún llamador. Tiene que salir en el informe."""
    return 1


def si_me_llaman():
    """La llama `dos.py`. No sale."""
    return 2


def solo_me_llamo_yo():
    """Solo se usa dentro de este módulo: por fuera sigue estando muerta."""
    return _privada()


def _privada():
    """Privada: no entra en el análisis."""
    return 3


def solo_me_llama_un_test():
    """Tiene test y ningún caller. Es EXACTAMENTE el caso de `store.save_*`."""
    return 4


def estoy_justificada():
    """Sin llamador, pero declarada en `data/alcanzabilidad.toml` con su motivo."""
    return 5
