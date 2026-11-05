"""
APOLLO — Lenguaje.

Herramientas para que HEFESTO entienda que distintas formas de
escribir algo significan lo mismo:

- "Batería", "bateria", "las baterías"  → "bateria"
- "mide", "miden", "medir"              → "mide"
"""

import re
import unicodedata


# ==========================================
# TEXTO BÁSICO
# ==========================================

SIGNOS = "¿?¡!.,;:\"'()"


def normalizar_texto(texto):
    """Minúsculas y espacios limpios. Se usa para leer comandos."""
    return " ".join(texto.strip().lower().split())


def quitar_acentos(texto):
    """Convierte 'batería' en 'bateria'. Conserva la ñ."""
    resultado = []

    for letra in texto:
        if letra in "ñÑ":
            resultado.append(letra)
            continue

        descompuesta = unicodedata.normalize("NFD", letra)
        resultado.append(
            "".join(c for c in descompuesta if unicodedata.category(c) != "Mn")
        )

    return "".join(resultado)


def quitar_signos(texto):
    """Quita signos de puntuación: '¿sensor?' → 'sensor'."""
    for signo in SIGNOS:
        texto = texto.replace(signo, " ")
    return texto


def expandir_contracciones(texto):
    """
    'pertenece al rover' → 'pertenece a el rover'
    'depende del motor'  → 'depende de el motor'

    Así 'pertenece a' se reconoce y el artículo 'el' se quita después.
    """
    texto = re.sub(r"\bal\b", "a el", texto)
    return re.sub(r"\bdel\b", "de el", texto)


# ==========================================
# ARTÍCULOS
# ==========================================

ARTICULOS = {
    "el", "la", "los", "las",
    "un", "una", "unos", "unas",
    "lo"
}


def quitar_articulo_inicial(texto):
    """'el sensor' → 'sensor'. Solo quita el artículo del inicio."""
    palabras = texto.split()

    while len(palabras) > 1 and palabras[0] in ARTICULOS:
        palabras = palabras[1:]

    return " ".join(palabras)


# ==========================================
# PLURALES
# ==========================================

# Palabras que terminan en "s" pero NO son plurales.
NO_SON_PLURALES = {
    "gps", "ros", "os", "gas", "mas", "menos", "tres", "seis", "dos",
    "lunes", "martes", "miercoles", "jueves", "viernes",
    "virus", "campus", "bus", "plus", "bonus", "corpus", "atlas",
    "tesis", "crisis", "analisis", "sintesis", "dosis",
    "cosmos", "caos", "pues", "antes", "despues", "entonces",
    "ademas", "mientras", "tras", "jamas", "interes", "ingles",
    "frances", "portugues", "es", "pies", "mes", "res"
}

VOCALES = "aeiou"

# Consonantes tras las que un singular suele llevar "-es" en plural:
# sensor → sensores, red → redes, neuronal → neuronales.
CONSONANTES_CON_ES = "rlndjy"


def singularizar(palabra):
    """Convierte una palabra en plural a su singular (reglas básicas)."""

    if len(palabra) <= 3 or palabra in NO_SON_PLURALES:
        return palabra

    if not palabra.endswith("s") or palabra.endswith(("is", "us", "ss")):
        return palabra

    # luces → luz, voces → voz
    if palabra.endswith("ces") and len(palabra) > 4:
        return palabra[:-3] + "z"

    # sensores → sensor, redes → red, leyes → ley
    if palabra.endswith("es"):
        raiz = palabra[:-2]
        if (
            len(raiz) >= 2
            and raiz[-1] in CONSONANTES_CON_ES
            and raiz[-2] in VOCALES
        ):
            return raiz

    # computadoras → computadora, chips → chip, variables → variable
    return palabra[:-1]


# ==========================================
# SINGULAR PARA MOSTRAR (CON ACENTOS)
# ==========================================

# Después de estas palabras, lo que sigue es un complemento y no se toca:
# "sensores de temperatura" → "sensor de temperatura".
PREPOSICIONES = {"de", "del", "con", "para", "a", "en", "por", "sin", "sobre"}

VOCALES_CON_ACENTO = "áéíóú"


def singular_con_acentos(palabra):
    """
    Como singularizar, pero conserva acentos y los corrige donde el
    singular los gana o los pierde:

        máquinas  → máquina
        camiones  → camión     (gana acento)
        imágenes  → imagen     (pierde acento)
        pingüinos → pingüino
    """
    base = quitar_acentos(palabra)
    singular = singularizar(base)

    if singular == base:
        return palabra

    if base.startswith(singular):
        # Caso normal: solo se quitó el final ("s" o "es").
        resultado = palabra[:len(singular)]
    else:
        # luces → luz: cambió la última letra.
        resultado = palabra[:len(singular) - 1] + singular[-1]

    # -iones → -ión
    if resultado.endswith("ion"):
        resultado = resultado[:-3] + "ión"

    # imágenes → imagen, exámenes → examen, jóvenes → joven
    elif resultado.endswith("en") and any(v in resultado for v in VOCALES_CON_ACENTO):
        resultado = quitar_acentos(resultado)

    return resultado


def forma_singular(concepto):
    """
    Pasa un concepto a singular para guardarlo y mostrarlo bonito.

        "Las Aves"                → "ave"
        "redes neuronales"        → "red neuronal"
        "sensores de temperatura" → "sensor de temperatura"
        "cámaras de fotos"        → "cámara de fotos"
    """
    palabras = limpiar_concepto(concepto).split()

    for i, palabra in enumerate(palabras):

        if quitar_acentos(palabra) in PREPOSICIONES:
            break   # lo demás es complemento

        palabras[i] = singular_con_acentos(palabra)

    return " ".join(palabras)


# ==========================================
# NORMALIZAR CONCEPTOS
# ==========================================

def limpiar_concepto(texto):
    """
    Limpieza ligera para GUARDAR un concepto: conserva acentos
    y plurales para que se vea bonito, pero quita signos,
    espacios de más y el artículo inicial.
    """
    texto = quitar_signos(normalizar_texto(texto))
    return quitar_articulo_inicial(normalizar_texto(texto))


def normalizar_concepto(texto):
    """
    Normalización completa para COMPARAR conceptos.

    'Las Baterías' y 'bateria' dan el mismo resultado: 'bateria'.
    """
    texto = quitar_acentos(limpiar_concepto(texto))

    return " ".join(singularizar(palabra) for palabra in texto.split())


# ==========================================
# VERBOS DE RELACIÓN
# ==========================================

# Forma oficial de cada relación → maneras de escribirla.
# Todas sin acentos, porque se comparan sin acentos.
FORMAS_RELACION = {
    "es": ["es", "son", "ser"],
    "puede": ["puede", "pueden", "poder"],
    "tiene": ["tiene", "tienen", "tener"],
    "mide": ["mide", "miden", "medir"],
    "controla": ["controla", "controlan", "controlar"],
    "mueve": ["mueve", "mueven", "mover"],
    "contiene": ["contiene", "contienen", "contener"],
    "utiliza": ["utiliza", "utilizan", "utilizar"],
    "usa": ["usa", "usan", "usar"],
    "necesita": ["necesita", "necesitan", "necesitar"],
    "produce": ["produce", "producen", "producir"],
    "detecta": ["detecta", "detectan", "detectar"],
    "conecta": ["conecta", "conectan", "conectar"],
    "conecta con": ["conecta con", "conectan con", "conectarse con"],
    "se comunica con": [
        "se comunica con", "se comunican con", "comunicarse con"
    ],
    "funciona con": ["funciona con", "funcionan con", "funcionar con"],
    "pertenece a": ["pertenece a", "pertenecen a", "pertenecer a"],
    "depende de": ["depende de", "dependen de", "depender de"],
    "forma parte de": ["forma parte de", "forman parte de"],
    "recibe señal de": ["recibe señal de", "reciben señal de"],
    "está compuesto por": [
        "esta compuesto por", "esta compuesta por",
        "estan compuestos por", "estan compuestas por"
    ],
    "está formado por": [
        "esta formado por", "esta formada por",
        "estan formados por", "estan formadas por"
    ],
}

# Índice inverso: "miden" → "mide", "esta formada por" → "está formado por".
_FORMA_A_RELACION = {
    forma: oficial
    for oficial, formas in FORMAS_RELACION.items()
    for forma in formas
}


def normalizar_relacion(texto):
    """
    Devuelve la forma oficial de una relación.

    'miden' → 'mide', 'Está formada por' → 'está formado por'.
    Si no la reconoce, devuelve el texto limpio.
    """
    limpio = quitar_acentos(normalizar_texto(texto))
    return _FORMA_A_RELACION.get(limpio, normalizar_texto(texto))


def formas_de_relacion(incluir_es=False):
    """
    Lista (forma, oficial) ordenada de la más larga a la más corta,
    para buscar primero 'conecta con' antes que 'conecta'.
    """
    pares = [
        (forma, oficial)
        for forma, oficial in _FORMA_A_RELACION.items()
        if incluir_es or oficial != "es"
    ]

    return sorted(pares, key=lambda par: len(par[0]), reverse=True)


# ==========================================
# ERRORES DE ESCRITURA
# ==========================================

def distancia_edicion(a, b):
    """
    Cuántos cambios de una letra se necesitan para convertir a en b.

    Cuenta como 1 cambio: agregar, quitar o cambiar una letra,
    o intercambiar dos letras vecinas ('sensro' → 'sensor').

    Es la distancia de Levenshtein con transposiciones
    (variante de Damerau).
    """

    filas = len(a) + 1
    columnas = len(b) + 1

    # tabla[i][j] = distancia entre los primeros i caracteres de a
    #               y los primeros j caracteres de b.
    tabla = [[0] * columnas for _ in range(filas)]

    for i in range(filas):
        tabla[i][0] = i          # quitar i letras

    for j in range(columnas):
        tabla[0][j] = j          # agregar j letras

    for i in range(1, filas):
        for j in range(1, columnas):

            costo = 0 if a[i - 1] == b[j - 1] else 1

            tabla[i][j] = min(
                tabla[i - 1][j] + 1,          # quitar
                tabla[i][j - 1] + 1,          # agregar
                tabla[i - 1][j - 1] + costo   # cambiar (o igual)
            )

            # Intercambio de dos letras vecinas.
            if (
                i > 1 and j > 1
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                tabla[i][j] = min(tabla[i][j], tabla[i - 2][j - 2] + 1)

    return tabla[-1][-1]


def tolerancia(texto):
    """Cuántos errores se aceptan según el largo de la palabra."""
    largo = len(texto)

    if largo <= 3:
        return 0
    if largo <= 5:
        return 1
    if largo <= 10:
        return 2
    return 3


# ==========================================
# CÓMO SE PREGUNTA POR CADA RELACIÓN
# ==========================================

PREPOSICIONES_FINALES = ("con", "a", "de", "por")


def preguntas_de_relacion():
    """
    Todas las formas de preguntar por una relación, generadas
    a partir de FORMAS_RELACION:

        mide            → "qué mide"
        se comunica con → "con qué se comunica", "dime con qué se comunica"
        pertenece a     → "a qué pertenece", "qué pertenece a"
        depende de      → "de qué depende"

    Devuelve pares (inicio de la pregunta, relación oficial), del más
    largo al más corto. Si se agrega un verbo nuevo a FORMAS_RELACION,
    sus preguntas aparecen solas.
    """
    preguntas = []

    for relacion in FORMAS_RELACION:

        if relacion == "es":
            continue

        for que in ("qué", "que"):

            preguntas.append((f"{que} {relacion}", relacion))

            *verbo, preposicion = relacion.split()

            if verbo and preposicion in PREPOSICIONES_FINALES:
                verbo = " ".join(verbo)

                preguntas.append((f"{preposicion} {que} {verbo}", relacion))
                preguntas.append((f"dime {preposicion} {que} {verbo}", relacion))

                if preposicion == "con":
                    preguntas.append(
                        (f"con {que} dispositivo {verbo}", relacion)
                    )

    return sorted(preguntas, key=lambda par: len(par[0]), reverse=True)