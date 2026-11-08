"""
Contexto de conversación de HEFESTO.

Recuerda de qué se está hablando, y qué se preguntó, para entender
preguntas incompletas:

    Tú: qué sabes del pingüino
    Tú: ¿y puede nadar?        → ¿pingüino puede nadar?
    Tú: ¿y qué tiene?          → qué tiene pingüino
    Tú: qué más sabes de él    → qué sabes de pingüino
    Tú: ¿y el gorrión también? → qué tiene gorrión   (repite la pregunta)

Son funciones puras: reciben texto y devuelven texto, sin imprimir
ni preguntar nada. Por eso se pueden probar fácilmente.
"""

import re

from apollo.lenguaje import (
    normalizar_texto,
    limpiar_concepto,
    expandir_contracciones,
    formas_de_relacion,
    preguntas_de_relacion
)

from apollo.conocimiento import extraer_relacion_con_negacion


PRONOMBRES = {"él", "el", "ella", "ellos", "ellas", "eso", "esto", "esa", "ese"}

PREFIJOS_SABER = ("qué sabes de ", "que sabes de ")

PREFIJOS_DEFINIR = (
    "define ", "qué es ", "que es ", "qué son ", "que son ",
    "qué significa ", "que significa "
)

PREFIJOS_INVERSA = ("quién ", "quien ", "qué cosa ", "que cosa ")

# Si un "y ..." empieza con esto, es un comando y no un cambio de tema.
COMANDOS = (
    "aprende", "olvida", "recuerda", "camino", "qué", "que",
    "quién", "quien", "con ", "dime", "cómo", "como", "cuál", "cual",
    "a qué", "a que", "de qué", "de que", "por qué", "por que"
)


def _sin_signos_de_pregunta(texto):
    return normalizar_texto(texto.replace("¿", "").replace("?", ""))


def _empieza_con_verbo(texto):
    """
    Si el texto empieza con un verbo de relación ('puede nadar',
    'no tiene alas'), devuelve True.
    """
    resto = texto[3:] if texto.startswith("no ") else texto

    return any(
        resto == forma or resto.startswith(forma + " ")
        for forma, _ in formas_de_relacion(incluir_es=True)
    )


def _verbo_sin_objeto(texto):
    """
    'qué tiene', 'a qué pertenece', 'con qué se comunica':
    pregunta por una relación pero sin decir de quién.
    """
    return any(texto == inicio for inicio, _ in preguntas_de_relacion())


# ==========================================
# 1. COMPLETAR PREGUNTAS INCOMPLETAS
# ==========================================

def _quitar_tambien(texto):
    """'el gorrión también' → ('el gorrión', True)"""
    palabras = texto.split()
    tambien = False

    for extremo in (0, -1):
        if palabras and palabras[extremo] in ("también", "tambien"):
            palabras.pop(extremo)
            tambien = True

    return " ".join(palabras), tambien


def _es_solo_un_concepto(texto):
    """'el gorrión', 'del sensor': un concepto suelto, sin verbo ni comando."""
    return bool(
        texto
        and not texto.startswith(COMANDOS)
        and not _empieza_con_verbo(texto)
        and not _verbo_sin_objeto(texto)
        and extraer_relacion_con_negacion(texto, incluir_es=True) is None
    )


def aplicar_contexto(comando, tema, plantilla=None):
    """
    Si el comando depende de la conversación, lo completa.

    'tema' es de qué se está hablando; 'plantilla' es la última
    pregunta con un hueco para el tema (ver crear_plantilla).

    Devuelve (comando_completo, uso_contexto):
        - comando_completo: el texto a procesar.
        - uso_contexto: True si se completó con la conversación, False si
          no hizo falta, o None si hacía falta un tema y no hay ninguno.
    """
    texto = _sin_signos_de_pregunta(comando)
    era_pregunta = "?" in comando or "¿" in comando

    # "¿y ...?" siempre es una continuación.
    seguimiento = texto.startswith("y ")

    if seguimiento:
        texto = texto[2:].strip()

    # "también" puede ir al inicio o al final: "¿y el gorrión también?"
    texto, tambien = _quitar_tambien(texto)
    seguimiento = seguimiento or tambien

    # ¿Hace falta el tema?
    completado = None

    palabras = texto.split()

    # "qué sabes de él", "qué más sabes de eso"
    texto_sin_mas = texto.replace(" más ", " ").replace(" mas ", " ")

    if texto_sin_mas in ("qué sabes", "que sabes", "qué más", "que mas"):
        completado = "qué sabes de {tema}"

    # "¿y qué es?", "defínelo"
    elif texto in tuple(p.strip() for p in PREFIJOS_DEFINIR) + ("defínelo", "definelo"):
        completado = "define {tema}"

    elif texto_sin_mas.startswith(PREFIJOS_SABER) and palabras[-1] in PRONOMBRES:
        completado = "qué sabes de {tema}"

    # "qué tiene", "con qué se comunica"
    elif _verbo_sin_objeto(texto):
        completado = texto + " {tema}"

    # "¿y puede nadar?", "¿no tiene alas?"
    elif (seguimiento or era_pregunta) and _empieza_con_verbo(texto):
        completado = "¿{tema} " + texto + "?"

    # "¿y el gorrión (también)?" → la misma pregunta, con otro sujeto.
    # Si no hay pregunta anterior, cambia de tema: "qué sabes de gorrión".
    elif seguimiento and _es_solo_un_concepto(texto):

        nuevo = limpiar_concepto(expandir_contracciones(texto))

        if nuevo.startswith("de "):
            nuevo = limpiar_concepto(nuevo[3:])

        if plantilla:
            return plantilla.format(tema=nuevo), True

        return f"qué sabes de {nuevo}", False

    if completado is None:
        return comando, False

    if not tema:
        return comando, None

    return completado.format(tema=tema), True


# ==========================================
# 2. DETECTAR DE QUÉ SE ESTÁ HABLANDO
# ==========================================

def detectar_tema(comando):
    """
    Devuelve el concepto principal del comando, o None.

    'qué sabes de los pingüinos'       → 'pingüinos'
    '¿el pingüino puede volar?'        → 'pingüino'
    'aprende que el sensor mide luz'   → 'sensor'
    'quién mide la temperatura'        → 'temperatura'
    """
    texto = expandir_contracciones(_sin_signos_de_pregunta(comando))

    # qué sabes de X, define X, qué es X
    for prefijo in PREFIJOS_SABER + PREFIJOS_DEFINIR:
        if texto.startswith(prefijo):
            return limpiar_concepto(texto[len(prefijo):]) or None

    # quién mide X
    for prefijo in PREFIJOS_INVERSA:
        if texto.startswith(prefijo):
            resto = texto[len(prefijo):]
            for forma, _ in formas_de_relacion(incluir_es=True):
                if resto.startswith(forma + " "):
                    return limpiar_concepto(resto[len(forma):]) or None

    # qué mide X, con qué se comunica X, a qué pertenece X
    for inicio, _ in preguntas_de_relacion():
        if texto.startswith(inicio + " "):
            return limpiar_concepto(texto[len(inicio):]) or None

    # aprende que X ..., olvida que X ...
    for prefijo in ("aprende que ", "olvida que "):
        if texto.startswith(prefijo):
            texto = texto[len(prefijo):]
            break

    # X es sinónimo de Y → X
    if " sinónimo de " in texto or " sinonimo de " in texto:
        return limpiar_concepto(texto.split(" es ", 1)[0]) or None

    # Frase con relación: '¿el pingüino puede volar?', 'el sensor mide luz'
    resultado = extraer_relacion_con_negacion(texto, incluir_es=True)

    if resultado:
        return resultado[0]

    return None


# ==========================================
# 3. RECORDAR QUÉ SE PREGUNTÓ
# ==========================================

ARTICULOS = r"(?:(?:el|la|los|las|un|una|unos|unas)\s+)?"


def crear_plantilla(comando, tema):
    """
    Convierte el comando en una plantilla con un hueco donde va el tema,
    para poder repetirlo con otro sujeto:

        '¿el pingüino puede volar?' + 'pingüino' → '¿{tema} puede volar?'
        'qué tiene el ave'          + 'ave'      → 'qué tiene {tema}'

    Devuelve None si no se puede (o si no conviene repetirlo, como
    'olvida' o 'recuerda').
    """
    if not tema:
        return None

    texto = expandir_contracciones(normalizar_texto(comando))

    if texto.startswith(("olvida", "recuerda")):
        return None

    # Las llaves del texto se duplican para que format() no las confunda.
    texto = texto.replace("{", "{{").replace("}", "}}")

    patron = r"\b" + ARTICULOS + re.escape(tema) + r"\b"

    plantilla, cambios = re.subn(patron, "{tema}", texto, count=1)

    return plantilla if cambios else None