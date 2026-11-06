"""
APOLLO — Lector de documentos.

Lee un texto normal y encuentra los hechos que HEFESTO puede aprender:

    "La Raspberry Pi es una computadora. Los sensores miden
     la temperatura y la humedad. El pingüino no puede volar."

    → raspberry pi → es → computadora
    → sensor → mide → temperatura
    → sensor → mide → humedad
    → pingüino → NO puede → volar

Leer y guardar son pasos separados: leer_texto() solo interpreta,
sin tocar el diccionario, para que alguien revise antes de guardar.
"""

import re

from apollo.conocimiento import (
    extraer_relacion_con_negacion,
    aprender_palabra,
    aprender_sinonimo,
    aprender_relacion
)

from apollo.lenguaje import limpiar_concepto, normalizar_texto, PREPOSICIONES


# Palabras que suelen abrir una oración pero no son parte del sujeto.
CONECTORES = (
    "además", "ademas", "también", "tambien", "pero", "sin embargo",
    "por otro lado", "por ejemplo", "asimismo", "y", "e", "o", "luego",
    "entonces", "finalmente", "por último", "por ultimo"
)

SEPARADORES_SINONIMO = (
    " es sinónimo de ", " es sinonimo de ",
    " también se llama ", " tambien se llama ",
    " también se conoce como ", " tambien se conoce como ",
    " significa ", " quiere decir ", " equivale a "
)


# ==========================================
# DIVIDIR EL TEXTO
# ==========================================

def dividir_oraciones(texto):
    """
    Corta el texto en oraciones: por punto, signos de exclamación o
    interrogación, punto y coma, o salto de línea.

    No corta números como 3.5, porque después del punto no hay espacio.
    """
    partes = re.split(r"(?<=[.!?;])\s+|\n+", texto)

    oraciones = []

    for parte in partes:
        parte = parte.strip().strip(".!?;¡¿").strip()
        if parte:
            oraciones.append(parte)

    return oraciones


# Palabras que unen dos ideas distintas en una misma oración:
# "Los pingüinos son aves, pero el pingüino no puede volar."
UNIONES_DE_IDEAS = re.compile(
    r",?\s+(?:pero|aunque|sin embargo|mientras que|sino que)\s+",
    re.IGNORECASE
)


def separar_ideas(oracion):
    """'A son B, pero C no puede D' → ['A son B', 'C no puede D']"""
    return [parte.strip(" ,") for parte in UNIONES_DE_IDEAS.split(oracion) if parte.strip(" ,")]


def quitar_conector(oracion):
    """'Además, los sensores miden luz' → 'los sensores miden luz'"""
    texto = normalizar_texto(oracion)

    cambio = True
    while cambio:
        cambio = False
        for conector in CONECTORES:
            for forma in (conector + ", ", conector + " "):
                if texto.startswith(forma):
                    texto = texto[len(forma):].strip()
                    cambio = True

    return texto


def dividir_objetos(objeto):
    """
    'la temperatura y la humedad' → ['temperatura', 'humedad']
    'luz, sonido y movimiento'    → ['luz', 'sonido', 'movimiento']
    """
    partes = re.split(r",\s*|\s+y\s+|\s+e\s+", objeto)
    return [limpiar_concepto(p) for p in partes if limpiar_concepto(p)]


# ==========================================
# INTERPRETAR UNA ORACIÓN
# ==========================================

def interpretar_oracion(oracion):
    """
    Convierte una oración en una lista de hechos. Lista vacía si no
    la entendió.

    Cada hecho es un diccionario:
        {"tipo": "relacion",  "sujeto", "relacion", "objeto", "negada"}
        {"tipo": "categoria", "sujeto", "objeto"}            (X es Y)
        {"tipo": "sinonimo",  "sujeto", "objeto"}            (X es sinónimo de Y)
    """
    texto = quitar_conector(oracion)

    # 1. Sinónimos
    for separador in SEPARADORES_SINONIMO:
        if separador in texto:
            a, b = texto.split(separador, 1)
            a, b = limpiar_concepto(a), limpiar_concepto(b)
            if a and b:
                return [{"tipo": "sinonimo", "sujeto": a, "objeto": b}]

    # 2. Relaciones (mide, usa, NO puede...) y categorías (es / son)
    # Las comas de una lista se vuelven "y" para no perderlas:
    # "luz, sonido y movimiento" → "luz y sonido y movimiento".
    resultado = extraer_relacion_con_negacion(
        texto.replace(",", " y "), incluir_es=True
    )

    if resultado is None:
        return []

    sujeto, relacion, objeto, negada = resultado

    # "El voltaje es de 3.5 V", "la reunión es en la sala": un "es"
    # seguido de preposición no es una categoría. Mejor no adivinar.
    if relacion == "es" and objeto.split()[0] in PREPOSICIONES:
        return []

    hechos = []

    for objeto_suelto in dividir_objetos(objeto):

        if relacion == "es" and not negada:
            hechos.append({
                "tipo": "categoria",
                "sujeto": sujeto,
                "objeto": objeto_suelto
            })
        else:
            hechos.append({
                "tipo": "relacion",
                "sujeto": sujeto,
                "relacion": relacion,
                "objeto": objeto_suelto,
                "negada": negada
            })

    return hechos


# ==========================================
# LEER UN TEXTO COMPLETO
# ==========================================

def leer_texto(texto):
    """
    Interpreta un texto completo SIN guardar nada.

    Devuelve:
        {"hechos": [...], "no_entendidas": [oraciones que no entendió]}
    """
    hechos = []
    no_entendidas = []

    oraciones = [
        idea
        for oracion in dividir_oraciones(texto)
        for idea in separar_ideas(oracion)
    ]

    for oracion in oraciones:

        encontrados = interpretar_oracion(oracion)

        if encontrados:
            for hecho in encontrados:
                hecho["oracion"] = oracion
                hechos.append(hecho)
        else:
            no_entendidas.append(oracion)

    return {"hechos": hechos, "no_entendidas": no_entendidas}


def leer_archivo(ruta):
    """
    Lee un archivo de texto (.txt, .md) y lo interpreta sin guardar.
    Lanza FileNotFoundError si no existe.
    """
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            texto = archivo.read()
    except UnicodeDecodeError:
        # Archivos viejos de Windows a veces vienen en otra codificación.
        with open(ruta, "r", encoding="latin-1") as archivo:
            texto = archivo.read()

    return leer_texto(texto)


# ==========================================
# GUARDAR LO LEÍDO
# ==========================================

def guardar_hechos(hechos):
    """
    Aprende una lista de hechos. Las contradicciones NO se guardan:
    se devuelven para que alguien decida.

    Devuelve una lista de (hecho, resultado de APOLLO).
    """
    resultados = []

    # Primero categorías y sinónimos, para que las relaciones
    # encuentren los conceptos ya creados.
    orden = {"categoria": 0, "sinonimo": 1, "relacion": 2}

    for hecho in sorted(hechos, key=lambda h: orden[h["tipo"]]):

        if hecho["tipo"] == "categoria":
            r = aprender_palabra(hecho["sujeto"], hecho["objeto"])

        elif hecho["tipo"] == "sinonimo":
            r = aprender_sinonimo(hecho["sujeto"], hecho["objeto"])

            # "RPi es sinónimo de Raspberry Pi": el conocido va al final.
            if r["estado"] == "desconocido":
                otro = aprender_sinonimo(hecho["objeto"], hecho["sujeto"])
                if otro["estado"] != "desconocido":
                    r = otro

        else:
            r = aprender_relacion(
                hecho["sujeto"], hecho["relacion"],
                hecho["objeto"], hecho["negada"]
            )

        resultados.append((hecho, r))

    return resultados