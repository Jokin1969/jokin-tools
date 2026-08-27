#!/usr/bin/env python3
"""Las tildes del castellano que ve el usuario.

Los mensajes de la app —avisos, errores, motivos de filtro, textos de la interfaz— se
escribieron sin tildes. No es un detalle de estilo: es texto que se lee, se copia a un
correo y se pega en un informe que defiende una selección. «Ningun candidato esta
aprobado y la seleccion es PROVISIONAL» está mal escrito, y un informe mal escrito
resta credibilidad a lo que dice.

QUÉ MIRA Y QUÉ NO
-----------------

Solo **literales de cadena que son prosa**, y prosa se define aquí como «contiene al
menos un espacio». Es una heurística, y es la que hace que esto se pueda automatizar sin
romper nada:

  - `"seleccion"` a secas NO se toca. Es una etiqueta de `RECORD_KINDS`, una clave de
    diccionario o una cabecera de columna: cambiarla rompería el formato de un fichero
    que ya está escrito en disco;
  - `"la seleccion es PROVISIONAL"` sí. Nadie indexa por esa cadena.

Tampoco mira comentarios ni docstrings: son para quien lee el código, no para quien usa
la app, y meterlos aquí ahogaría el informe en ruido.

El vocabulario (`PALABRAS`) está **escrito a mano y es cerrado**. No se deduce con
reglas de acentuación: eso daría falsos positivos sobre nombres propios, siglas y
términos técnicos (`seed`, `pri-miR`, `Alu`) y el informe dejaría de leerse.

Uso:

    python3 tools/check_tildes.py [ruta ...]      # informe
    python3 tools/check_tildes.py --arreglar      # y las corrige

Python 3.11+, solo librería estándar (regla 6).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: Sin tilde → con tilde. Cerrado y escrito a mano; ver el docstring.
PALABRAS: dict[str, str] = {
    "analisis": "análisis",
    "anotacion": "anotación",
    "aqui": "aquí",
    "asi": "así",
    "asimetria": "asimetría",
    "automaticamente": "automáticamente",
    "biofisico": "biofísico",
    "biofisicos": "biofísicos",
    "biofisica": "biofísica",
    "biofisicas": "biofísicas",
    "cambiaria": "cambiaría",
    "canonica": "canónica",
    "canonico": "canónico",
    "canonicas": "canónicas",
    "canonicos": "canónicos",
    "cargo": "cargó",
    "codigo": "código",
    "codon": "codón",
    "colision": "colisión",
    "comparacion": "comparación",
    "comprobacion": "comprobación",
    "conversion": "conversión",
    "corrio": "corrió",
    "criptico": "críptico",
    "cripticos": "crípticos",
    "cuantas": "cuántas",
    "cuantos": "cuántos",
    "decision": "decisión",
    "declaracion": "declaración",
    "deduccion": "deducción",
    "deteccion": "detección",
    "dia": "día",
    "diagnostico": "diagnóstico",
    "direccion": "dirección",
    "electronico": "electrónico",
    "elegira": "elegirá",
    "eleccion": "elección",
    "energia": "energía",
    "ensamblo": "ensambló",
    "escision": "escisión",
    "especificacion": "especificación",
    "esta_": "está_",
    "estan": "están",
    "estara": "estará",
    "estimacion": "estimación",
    "expresion": "expresión",
    "extraccion": "extracción",
    "fraccion": "fracción",
    "geometrico": "geométrico",
    "geometrica": "geométrica",
    "habria": "habría",
    "haria": "haría",
    "identificacion": "identificación",
    "informacion": "información",
    "interpretacion": "interpretación",
    "invocacion": "invocación",
    "leccion": "lección",
    "libreria": "librería",
    "limite": "límite",
    "limites": "límites",
    "logica": "lógica",
    "mas_": "más_",
    "maquina": "máquina",
    "maximo": "máximo",
    "maxima": "máxima",
    "mascara": "máscara",
    "metrica": "métrica",
    "metricas": "métricas",
    "minimo": "mínimo",
    "minima": "mínima",
    "modulo": "módulo",
    "modulos": "módulos",
    "numerico": "numérico",
    "numero": "número",
    "numeros": "números",
    "ningun": "ningún",
    "opcion": "opción",
    "parametro": "parámetro",
    "parametros": "parámetros",
    "pasaria": "pasaría",
    "peticion": "petición",
    "plasmido": "plásmido",
    "podria": "podría",
    "polimorfica": "polimórfica",
    "polimorficas": "polimórficas",
    "posicion": "posición",
    "practica": "práctica",
    "prediccion": "predicción",
    "procesara": "procesará",
    "produccion": "producción",
    "proposito": "propósito",
    "puntuacion": "puntuación",
    "quimerico": "quimérico",
    "quiza": "quizá",
    "razon": "razón",
    "region": "región",
    "repeticion": "repetición",
    "seleccion": "selección",
    "selecciono": "seleccionó",
    "señalo": "señaló",
    "sera": "será",
    "seran": "serán",
    "seria": "sería",
    "serian": "serían",
    "sintesis": "síntesis",
    "solo_": "sólo_",
    "tambien": "también",
    "tendria": "tendría",
    "tendrian": "tendrían",
    "termino": "término",
    "traduccion": "traducción",
    "ultima": "última",
    "ultimas": "últimas",
    "ultimo": "último",
    "ultimos": "últimos",
    "unico": "único",
    "unica": "única",
    "unicos": "únicos",
    "unicas": "únicas",
    "validacion": "validación",
    "veran": "verán",
    "version": "versión",
    "acido": "ácido",
    "actuacion": "actuación",
    "ademas": "además",
    "agrupacion": "agrupación",
    "alineacion": "alineación",
    "ambiguedad": "ambigüedad",
    "anatomia": "anatomía",
    "aparicion": "aparición",
    "aplicacion": "aplicación",
    "aritmetica": "aritmética",
    "asignacion": "asignación",
    "asimetrias": "asimetrías",
    "atras": "atrás",
    "automatica": "automática",
    "automatico": "automático",
    "autorizacion": "autorización",
    "basica": "básica",
    "basico": "básico",
    "caracter": "carácter",
    "categoria": "categoría",
    "categorias": "categorías",
    "cientifica": "científica",
    "cientifico": "científico",
    "clasificacion": "clasificación",
    "combinacion": "combinación",
    "compañia": "compañía",
    "composicion": "composición",
    "conclusion": "conclusión",
    "condicion": "condición",
    "confirmacion": "confirmación",
    "conservacion": "conservación",
    "consideracion": "consideración",
    "construccion": "construcción",
    "contaminacion": "contaminación",
    "convencion": "convención",
    "correccion": "corrección",
    "correlacion": "correlación",
    "creacion": "creación",
    "cronometro": "cronómetro",
    "cuantificacion": "cuantificación",
    "degradacion": "degradación",
    "descripcion": "descripción",
    "despues": "después",
    "desviacion": "desviación",
    "detras": "detrás",
    "dificil": "difícil",
    "distribucion": "distribución",
    "division": "división",
    "duplicacion": "duplicación",
    "ejecucion": "ejecución",
    "electronica": "electrónica",
    "especifica": "específica",
    "especificas": "específicas",
    "especifico": "específico",
    "especificos": "específicos",
    "estadistica": "estadística",
    "estadistico": "estadístico",
    "estandar": "estándar",
    "evaluacion": "evaluación",
    "excepcion": "excepción",
    "exclusion": "exclusión",
    "funcion": "función",
    "generacion": "generación",
    "generica": "genérica",
    "generico": "genérico",
    "guia": "guía",
    "guias": "guías",
    "heuristica": "heurística",
    "heuristicas": "heurísticas",
    "hexamero": "hexámero",
    "hexameros": "hexámeros",
    "historico": "histórico",
    "identica": "idéntica",
    "identicas": "idénticas",
    "identico": "idéntico",
    "identicos": "idénticos",
    "implementacion": "implementación",
    "insercion": "inserción",
    "instalacion": "instalación",
    "integracion": "integración",
    "introduccion": "introducción",
    "intron": "intrón",
    "intronica": "intrónica",
    "intronico": "intrónico",
    "legitima": "legítima",
    "legitimo": "legítimo",
    "legitimos": "legítimos",
    "linea": "línea",
    "lineas": "líneas",
    "mecanico": "mecánico",
    "monotono": "monótono",
    "mutacion": "mutación",
    "normalizacion": "normalización",
    "nucleo": "núcleo",
    "nucleos": "núcleos",
    "nucleotido": "nucleótido",
    "nucleotidos": "nucleótidos",
    "numeracion": "numeración",
    "operacion": "operación",
    "optima": "óptima",
    "optimizacion": "optimización",
    "optimo": "óptimo",
    "ordenacion": "ordenación",
    "organizacion": "organización",
    "permutacion": "permutación",
    "poblacion": "población",
    "poliadenilacion": "poliadenilación",
    "ponderacion": "ponderación",
    "practico": "práctico",
    "precision": "precisión",
    "presentacion": "presentación",
    "proporcion": "proporción",
    "publica": "pública",
    "publicas": "públicas",
    "publico": "público",
    "publicos": "públicos",
    "quimico": "químico",
    "rapida": "rápida",
    "rapido": "rápido",
    "reaccion": "reacción",
    "recombinacion": "recombinación",
    "reconstruccion": "reconstrucción",
    "reduccion": "reducción",
    "representacion": "representación",
    "resolucion": "resolución",
    "restriccion": "restricción",
    "revision": "revisión",
    "separacion": "separación",
    "sintetica": "sintética",
    "sintetico": "sintético",
    "situacion": "situación",
    "sustitucion": "sustitución",
    "sustraccion": "sustracción",
    "teorica": "teórica",
    "teorico": "teórico",
    "tipica": "típica",
    "tipico": "típico",
    "transcripcion": "transcripción",
    "transgen": "transgén",
    "traslacion": "traslación",
    "utilizacion": "utilización",
    "vacia": "vacía",
    "vacias": "vacías",
    "vacio": "vacío",
    "vacios": "vacíos",
    "valido": "válido",
    "validos": "válidos",
    "variacion": "variación",
    "verificacion": "verificación",
    "violacion": "violación",
}

#: Las que llevan sufijo `_` en el mapa son las que NO se tocan automáticamente porque
#: dependen del contexto (`esta` puede ser demostrativo o verbo; `mas` puede ser
#: conjunción adversativa; `solo` adverbio o adjetivo). Se quedan documentadas y fuera.
PALABRAS = {k: v for k, v in PALABRAS.items() if not k.endswith("_")}

#: Ficheros que no se revisan. Los goldens son SALIDA: se regeneran, no se editan.
EXCLUIDOS = ("tests/golden/", "tools/check_tildes.py")

#: Caracteres que pueden rodear una palabra dentro de la prosa.
_BORDES = " \t\n.,;:()[]{}«»\"'¿?¡!/…—-→"


#: `esta` y `mas` NO se resuelven con el diccionario: dependen del contexto.
#:
#:   - «esta tabla» es un demostrativo y va sin tilde; «esta fuera» es el verbo y lleva.
#:     Meter `esta → está` en `PALABRAS` habria acentuado los 250 casos, demostrativos
#:     incluidos, y eso no es arreglar la ortografia: es cambiar unas faltas por otras.
#:   - `mas` adversativo («pero») va sin tilde. En prosa tecnica no aparece nunca, asi
#:     que aqui la regla es al reves: se acentua salvo que le siga una coma, que es como
#:     se escribe el adversativo.
#:
#: La regla de `esta` es POSITIVA y cerrada: solo se acentua delante de un participio
#: (`-ado/-ido` y sus femeninos y plurales) o de una de las palabras de `_TRAS_ESTA`.
#: Delante de cualquier otra cosa se deja como esta. Prefiere no tocar a tocar de mas:
#: un demostrativo acentuado es una falta nueva, y la que habia era una omision.
#: La lista se construyo LEYENDO las 88 palabras que siguen a `esta` en este codigo, una
#: a una, no con una regla de participios: «esta corrida», «esta medida», «esta entrada»
#: y «esta llamada» tienen forma de participio y son SUSTANTIVOS aqui —una corrida de
#: BLAST, una medida de PolyA_DB—, asi que la regla generica las habria acentuado todas.
#: Cerrada a proposito: si aparece un contexto nuevo, el informe lo enseña y se decide.
_TRAS_ESTA = (
    # preposiciones y adverbios de lugar: siempre verbo
    "a", "al", "en", "por", "entre", "fuera", "dentro", "aguas", "cerca", "lejos",
    "arriba", "abajo", "delante", "detras", "detrás", "aqui", "aquí", "ahi", "ahí",
    # adverbios que en este corpus siempre siguen al verbo
    "mal", "bien", "ya", "todavia", "todavía", "siempre", "también", "probablemente",
    "pero", "y", "cada", "disponible",
    # participios COMPROBADOS en este corpus (no derivados por regla)
    "abierto", "analizando", "anclado", "anotado", "aprobado", "autorizado",
    "buscando", "calculada", "completo", "contrastado", "diseñado", "inflado",
    "mirando", "optimizado", "prohibida", "prohibido", "repetido", "saturado",
    "calibrado", "cerrado", "comprobada", "comprobado", "condicionado", "conservada",
    "conservado", "contestada", "cubierto", "dando", "dañado", "declarada",
    "declarado", "definida", "derivada", "desplazada", "dicho", "escrito", "guardado",
    "hecho", "inflado", "instalado", "invertido", "medida", "medido", "muerto",
    "ordenado", "publicada", "puesto", "recortada", "registrado", "repetida",
    "resuelta", "resuelto", "rota", "roto", "saturado", "tecleada", "tocada", "vacia",
    "vacía", "vacio", "vacío", "visto", "vuelto",
)

#: Sin distinguir mayusculas —«esta MEDIDO», «el conteo esta INFLADO»— y admitiendo un
#: prefijo con guion, que es como aparece «esta codón-optimizado».
_ESTA = re.compile(
    r"\besta\b(?=\s+(?:[\wáéíóúñ]+-)?(?:" + "|".join(_TRAS_ESTA) + r")\b)",
    re.IGNORECASE,
)
_MAS = re.compile(r"\bmas\b(?!\s*,)", re.IGNORECASE)


def _contexto(texto: str) -> tuple[str, list[str]]:
    """Las dos que el diccionario no puede resolver. Ver `_TRAS_ESTA`."""
    cambiadas: list[str] = []
    nuevo, n = _ESTA.subn(lambda m: "está" if m.group(0).islower() else "ESTÁ", texto)
    if n:
        cambiadas.extend(["esta → está"] * n)
    nuevo, n = _MAS.subn(lambda m: "más" if m.group(0).islower() else "MÁS", nuevo)
    if n:
        cambiadas.extend(["mas → más"] * n)
    return nuevo, cambiadas


#: Con `--todo` la heuristica de prosa se apaga. Solo se usa en `tests/`, y solo porque
#: ahi un literal de una palabra es una EXPECTATIVA («que el texto diga poliadenilación»),
#: no una clave. En el codigo de la app sigue activa: una clave acentuada rompe un fichero
#: que ya esta escrito en disco.
SOLO_PROSA = True


def _es_prosa(texto: str) -> bool:
    """Prosa = una sola linea y con al menos un espacio.

    Lo de UNA SOLA LINEA no es cosmético: en este proyecto los mensajes largos se
    escriben concatenando trozos de una linea, y los literales de varias lineas son
    FIXTURES — un GenBank, un FASTA, un `-outfmt 6`. Sin esta condición, la primera
    pasada convirtió `VERSION     NM_011170.3` en `VERSIÓN` dentro del fixture de
    GenBank y el parser dejó de encontrar la versión del transcrito. Ortografía
    correcta, dato roto: exactamente el intercambio que este proyecto no acepta.
    """
    if "\n" in texto:
        return False
    return (" " in texto.strip()) if SOLO_PROSA else bool(texto.strip())


def _palabras_de(texto: str):
    """Trocea en palabras conservando los bordes, para poder recomponer.

    Una palabra precedida de `-` NO es palabra: es el final de una opción de la línea de
    órdenes. Sin esta comprobación, «hace falta --guia o --tabla» se convertía en
    «--guía», que ya no existe — el texto quedaba bien escrito y las instrucciones que
    daba, mal. Es exactamente el fallo que este proyecto llama diagnóstico equivocado:
    peor que no tocarlo.
    """
    palabra: list[str] = []
    anterior = ""
    inicio_guion = False
    for caracter in texto:
        if caracter in _BORDES:
            if palabra:
                yield "".join(palabra), not inicio_guion
                palabra = []
            yield caracter, False
            inicio_guion = False
        else:
            if not palabra:
                inicio_guion = anterior == "-"
            palabra.append(caracter)
        anterior = caracter
    if palabra:
        yield "".join(palabra), not inicio_guion


def _fuera_de_comillas(texto: str):
    """Trocea separando lo que va entre acentos graves. Eso es CODIGO, no prosa.

    `seleccion` entre comillas invertidas es un nombre —una clave de `RECORD_KINDS`, un
    campo, una función— y acentuarlo deja el texto señalando algo que no existe.
    """
    partes = []
    resto = texto
    while "`" in resto:
        antes, _, cola = resto.partition("`")
        dentro, cierra, despues = cola.partition("`")
        if not cierra:
            partes.append((antes + "`" + dentro, True))
            return partes
        partes.append((antes, True))
        partes.append(("`" + dentro + "`", False))
        resto = despues
    partes.append((resto, True))
    return partes


def corregir(texto: str) -> tuple[str, list[str]]:
    """Devuelve el texto con tildes y qué palabras se cambiaron."""
    if not _es_prosa(texto):
        return texto, []
    trozos = _fuera_de_comillas(texto)
    if len(trozos) > 1:
        salida, cambios = [], []
        for trozo, es_prosa in trozos:
            if not es_prosa:
                salida.append(trozo)
                continue
            arreglado, hechos = _corregir_prosa(trozo)
            salida.append(arreglado)
            cambios.extend(hechos)
        return "".join(salida), cambios
    return _corregir_prosa(texto)


def _corregir_prosa(texto: str) -> tuple[str, list[str]]:
    partes: list[str] = []
    cambiadas: list[str] = []
    for trozo, es_palabra in _palabras_de(texto):
        if not es_palabra:
            partes.append(trozo)
            continue
        # Se respeta la caja: MAYUSCULAS, Capitalizada o minúsculas.
        bajo = trozo.lower()
        arreglo = PALABRAS.get(bajo)
        if arreglo is None:
            partes.append(trozo)
            continue
        if trozo.isupper():
            arreglo = arreglo.upper()
        elif trozo[:1].isupper():
            arreglo = arreglo[:1].upper() + arreglo[1:]
        partes.append(arreglo)
        cambiadas.append(f"{trozo} → {arreglo}")
    salida, del_contexto = _contexto("".join(partes))
    return salida, cambiadas + del_contexto


def _docstrings(fuente: str, ruta: Path) -> set[tuple[int, int]]:
    """Dónde empieza cada docstring, para saltarlo.

    Los docstrings son para quien lee el código, no para quien usa la app. Meterlos aquí
    ahogaría el informe en ruido y taparía justo lo que se busca.
    """
    arbol = ast.parse(fuente, filename=str(ruta))
    sitios: set[tuple[int, int]] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(
            nodo, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        cuerpo = getattr(nodo, "body", [])
        if (
            cuerpo
            and isinstance(cuerpo[0], ast.Expr)
            and isinstance(cuerpo[0].value, ast.Constant)
            and isinstance(cuerpo[0].value.value, str)
        ):
            sitios.add((cuerpo[0].value.lineno, cuerpo[0].value.col_offset))
    return sitios


def _partes_literales(texto: str):
    """Trocea un literal en (trozo, es_texto).

    Dentro de una f-string, lo que hay entre llaves es CODIGO: acentuar ahi renombraria
    una variable y el fichero dejaria de compilar. Se separa y no se toca. Las llaves
    dobles `{{`/`}}` son una llave literal y siguen siendo texto.
    """
    partes = []
    buffer: list[str] = []
    i = 0
    profundidad = 0
    while i < len(texto):
        caracter = texto[i]
        if profundidad == 0 and caracter == "{" and texto[i : i + 2] == "{{":
            buffer.append("{{")
            i += 2
            continue
        if profundidad == 0 and caracter == "}" and texto[i : i + 2] == "}}":
            buffer.append("}}")
            i += 2
            continue
        if caracter == "{":
            if profundidad == 0:
                partes.append(("".join(buffer), True))
                buffer = []
            profundidad += 1
            buffer.append(caracter)
        elif caracter == "}" and profundidad:
            profundidad -= 1
            buffer.append(caracter)
            if profundidad == 0:
                partes.append(("".join(buffer), False))
                buffer = []
        else:
            buffer.append(caracter)
        i += 1
    if buffer:
        partes.append(("".join(buffer), profundidad == 0))
    return partes


def _arregla_literal(bruto: str) -> tuple[str, list[str]]:
    """Corrige un literal TAL COMO ESTA ESCRITO, comillas y prefijo incluidos.

    Se trabaja sobre el token del fuente y no sobre el valor del AST a proposito: la
    concatenacion implicita de cadenas adyacentes —que es como estan escritos casi todos
    los mensajes largos de este proyecto— produce un valor que NO aparece literalmente en
    el fichero, asi que buscarlo y sustituirlo no encuentra nada. Trozo a trozo si.
    """
    cambiadas: list[str] = []
    salida = []
    for trozo, es_texto in _partes_literales(bruto):
        if not es_texto:
            salida.append(trozo)
            continue
        arreglado, cambios = corregir(trozo)
        salida.append(arreglado)
        cambiadas.extend(cambios)
    return "".join(salida), cambiadas


def _literales(fuente: str, ruta: Path):
    """Los tokens de cadena del fichero, con su posicion. Sin docstrings."""
    import io
    import tokenize

    saltar = _docstrings(fuente, ruta)
    for token in tokenize.generate_tokens(io.StringIO(fuente).readline):
        if token.type != tokenize.STRING:
            continue
        if (token.start[0], token.start[1]) in saltar:
            continue
        yield token


def revisar(ruta: Path) -> list[tuple[int, str, list[str]]]:
    """Que palabras sin tilde hay en la prosa de este fichero."""
    fuente = ruta.read_text(encoding="utf-8")
    hallazgos = []
    for token in _literales(fuente, ruta):
        _, cambiadas = _arregla_literal(token.string)
        if cambiadas:
            hallazgos.append((token.start[0], token.string[:70], cambiadas))
    return hallazgos


def arreglar(ruta: Path) -> int:
    """Corrige el fichero en sitio. Devuelve cuantos literales cambiaron.

    Se reescribe sobre el TEXTO por posicion de token, no regenerando el AST:
    `ast.unparse` perderia comentarios, comillas y formato, que es exactamente lo que no
    se puede permitir en un fichero que otra persona va a leer.
    """
    fuente = ruta.read_text(encoding="utf-8")
    lineas = fuente.splitlines(keepends=True)
    ediciones = []
    for token in _literales(fuente, ruta):
        arreglado, cambiadas = _arregla_literal(token.string)
        if cambiadas and arreglado != token.string:
            ediciones.append((token.start, token.end, arreglado))
    if not ediciones:
        return 0
    # De atras hacia delante, para que las posiciones no se muevan.
    for (fila_i, col_i), (fila_f, col_f), texto in reversed(ediciones):
        if fila_i == fila_f:
            linea = lineas[fila_i - 1]
            lineas[fila_i - 1] = linea[:col_i] + texto + linea[col_f:]
        else:
            cabeza = lineas[fila_i - 1][:col_i]
            cola = lineas[fila_f - 1][col_f:]
            lineas[fila_i - 1 : fila_f] = [cabeza + texto + cola]
    ruta.write_text("".join(lineas), encoding="utf-8")
    return len(ediciones)


#: Las fichas de obtención viven en TOML y son texto que el usuario LEE entero: son la
#: respuesta a «este frente está en NOT_RUN, ¿y ahora qué?». Se revisan igual que el
#: código, con una diferencia: aquí las claves (`pregunta`, `validacion`) NO se tocan —
#: cambiarlas dejaría la ficha sin cargar—, así que solo se entra dentro de las comillas.
_TOML_CADENAS = re.compile(r'"""(?:.|\n)*?"""|"[^"\n]*"')


def arreglar_toml(ruta: Path) -> int:
    """Corrige la prosa de un TOML, solo DENTRO de las comillas."""
    fuente = ruta.read_text(encoding="utf-8")
    cambios = 0

    def _uno(match):
        nonlocal cambios
        bruto = match.group(0)
        lineas = bruto.split("\n")
        salida = []
        for linea in lineas:
            arreglada, hechos = _arregla_literal(linea)
            if hechos:
                cambios += 1
            salida.append(arreglada)
        return "\n".join(salida)

    nuevo = _TOML_CADENAS.sub(_uno, fuente)
    if nuevo != fuente:
        ruta.write_text(nuevo, encoding="utf-8")
    return cambios


def revisar_toml(ruta: Path) -> list[tuple[int, str, list[str]]]:
    fuente = ruta.read_text(encoding="utf-8")
    hallazgos = []
    for match in _TOML_CADENAS.finditer(fuente):
        linea_base = fuente[: match.start()].count("\n") + 1
        for salto, linea in enumerate(match.group(0).split("\n")):
            _, hechos = _arregla_literal(linea)
            if hechos:
                hallazgos.append((linea_base + salto, linea[:70], hechos))
    return hallazgos


def _ficheros(rutas) -> list[Path]:
    salida: list[Path] = []
    for raiz in rutas:
        camino = Path(raiz)
        candidatos = (
            sorted(camino.rglob("*.py")) if camino.is_dir() else [camino]
        )
        for fichero in candidatos:
            texto = str(fichero)
            if any(excluido in texto for excluido in EXCLUIDOS):
                continue
            if "__pycache__" in texto:
                continue
            salida.append(fichero)
    return salida


def main(argv: list[str]) -> int:
    global SOLO_PROSA
    if "--todo" in argv:
        SOLO_PROSA = False
    corrige = "--arreglar" in argv
    rutas = [a for a in argv if not a.startswith("--")] or [
        RAIZ / "shmir_design", RAIZ / "ui", RAIZ / "tools", RAIZ / "data" / "obtencion"
    ]
    ficheros = _ficheros(rutas)
    tomls = [
        t
        for raiz in rutas
        for t in (sorted(Path(raiz).rglob("*.toml")) if Path(raiz).is_dir() else [])
    ]
    if corrige:
        total = sum(arreglar(f) for f in ficheros) + sum(
            arreglar_toml(t) for t in tomls
        )
        print(f"check_tildes: {total} literal(es) corregido(s) en {len(ficheros)} fichero(s).")
        return 0

    total = 0
    for fichero in list(ficheros) + list(tomls):
        hallazgos = (
            revisar_toml(fichero)
            if fichero.suffix == ".toml"
            else revisar(fichero)
        )
        if not hallazgos:
            continue
        print(f"\n{fichero.relative_to(RAIZ)}")
        for linea, muestra, cambiadas in hallazgos:
            total += 1
            print(f"  :{linea}  {', '.join(sorted(set(cambiadas)))}")
            print(f"        {muestra!r}")
    if total:
        print(
            f"\ncheck_tildes: {total} literal(es) de prosa sin tildes. "
            f"Se corrigen con `python3 tools/check_tildes.py --arreglar` y se REVISA el "
            f"diff: el vocabulario es cerrado, pero el contexto no lo mira nadie."
        )
        return 1
    print(f"check_tildes: {len(ficheros)} fichero(s) sin prosa sin tildes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
