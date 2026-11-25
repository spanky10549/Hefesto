"""
Comprensión: entender aunque no lo digas "bien".

Las intenciones (intenciones.py) y el traductor (traductor.py) buscan
frases con cierta forma. Aquí van los trucos para cuando no la tiene:

    abreviaciones    "q", "xq", "ta", "tmb"           → "que", "por que", "esta", "tambien"
    ortografía       "dnde ta el rober"               → "donde esta el rover"
    varias cosas     "revisa la compu y luego haz un respaldo"  → dos pedidos
    referencias      "mándalo a 5 5" (hablando del rover)       → "manda el rover a 5 5"
    ¿quisiste decir? lo que más se parece de lo que sí sé decir

Funciones puras: texto entra, texto sale. Quién decide usarlas es
platica.py, y SIEMPRE después de intentar con el texto tal cual: así
"tensor" no se "corrige" a "sensor" cuando me estás enseñando algo nuevo.
"""

import re
import inspect
from difflib import SequenceMatcher

from minerva.planeador import simple
from apollo.lenguaje import distancia_edicion, tolerancia
import conversacion.intenciones
import conversacion.traductor


# ==========================================
# ABREVIACIONES (como se escribe en el chat)
# ==========================================

ABREVIACIONES = {
    "q": "que", "k": "que", "ke": "que", "qe": "que",
    "xq": "por que", "pq": "por que", "porq": "por que", "pk": "por que", "porke": "por que",
    "ta": "esta", "tas": "estas", "tan": "estan", "toy": "estoy",
    "tmb": "tambien", "tb": "tambien", "tbn": "tambien", "tmbn": "tambien",
    "d": "de", "dnd": "donde", "dnde": "donde", "dond": "donde",
    "pa": "para", "pal": "para el", "xfa": "por favor", "plis": "por favor", "pls": "por favor",
    "msj": "mensaje", "info": "informacion", "compu": "compu", "cel": "celular",
    "aki": "aqui", "aca": "aqui", "ahi": "ahi", "aver": "a ver",
    "tons": "entonces", "entons": "entonces", "ps": "pues", "pos": "pues",
    "bn": "bien", "mb": "muy bien", "nd": "nada", "nada": "nada",
    "kmo": "como", "cmo": "como", "komo": "como",
    "qhubo": "que hubo", "kiubo": "que hubo", "quiubo": "que hubo",
}


def expandir_abreviaciones(texto):
    """'q ta haciendo el rover' → 'que esta haciendo el rover' (sin acentos ni signos)."""
    palabras = re.findall(r"[a-zñ0-9_.:/\-]+|[,]", simple(texto))
    return " ".join(ABREVIACIONES.get(p, p) for p in palabras)


# ==========================================
# ORTOGRAFÍA
# ==========================================

# Palabras comunes que no salen en los patrones pero se usan mucho.
COMUNES = """
el la los las un una unos unas de del al a en y o que como donde cuando cual cuanto cuanta
por para con sin mi mis tu tus su sus es son esta estan este esto eso ese esa hay ya no si
me te se lo le nos yo tu el ella hoy ahora luego despues tambien muy mas menos todo todos
quiero puedes puede haz dime dame muestrame oye bien mal gracias hola adios favor
""".split()


def _palabras_de(modulo):
    """Las palabras que aparecen en el código de un módulo (sus patrones y frases)."""
    return set(re.findall(r"[a-zñ]{3,}", simple(inspect.getsource(modulo))))


_VOCABULARIO = None


def vocabulario(extra=()):
    """
    Las palabras que FOCUS reconoce: las de sus patrones, más las comunes,
    más 'extra' (por ejemplo, los conceptos que APOLLO conoce).
    """
    global _VOCABULARIO
    if _VOCABULARIO is None:
        _VOCABULARIO = (
            _palabras_de(conversacion.intenciones)
            | _palabras_de(conversacion.traductor)
            | set(COMUNES)
        )
    return _VOCABULARIO | {simple(e) for e in extra}


def corregir_palabra(palabra, vocab):
    """
    La palabra del vocabulario más parecida, si está lo bastante cerca.
    'rober' → 'rover', 'sensroes' → 'sensores'. Las cortas (≤3) no se tocan.
    """
    if palabra in vocab or len(palabra) <= 3 or not palabra.isalpha():
        return palabra

    limite = tolerancia(palabra)

    def que_tan_lejos(candidata):
        # 1. menos cambios; si empatan: 2. que empiece con la misma letra
        # ("rober" → "rover", no "saber"); 3. la más corta ("respaldoo" → "respaldo").
        return (distancia_edicion(palabra, candidata), candidata[0] != palabra[0], len(candidata))

    # Las que tienen un largo muy distinto ni se comparan: imposible que estén cerca.
    cercanas = [c for c in vocab if abs(len(c) - len(palabra)) <= limite]
    if not cercanas:
        return palabra

    mejor = min(cercanas, key=que_tan_lejos)
    return mejor if distancia_edicion(palabra, mejor) <= limite else palabra


def corregir(texto, extra=()):
    """Abreviaciones + ortografía. Devuelve el texto corregido (simple, sin acentos)."""
    vocab = vocabulario(extra)
    palabras = expandir_abreviaciones(texto).split()
    return " ".join(corregir_palabra(p, vocab) for p in palabras)


# ==========================================
# VARIAS COSAS EN UNA FRASE
# ==========================================

CONECTORES = re.compile(
    r"\s*,?\s+(?:y luego|y despues|y ya despues|luego|despues|y tambien|y ademas|ademas|y)\s+"
    r"|\s*[,;]\s*(?=\w)"
)


def partir(texto):
    """
    'revisa la compu y luego haz un respaldo' → ['revisa la compu', 'haz un respaldo']
    Se corta en el texto simple y se recorta el original (conserva acentos).
    Si no hay conectores, devuelve [texto].
    """
    partes, inicio = [], 0
    for encontrado in CONECTORES.finditer(simple(texto)):
        partes.append(texto[inicio:encontrado.start()])
        inicio = encontrado.end()
    partes.append(texto[inicio:])
    return [p.strip(" ,.") for p in partes if p.strip(" ,.")]


# ==========================================
# REFERENCIAS ("mándalo", "¿dónde está?")
# ==========================================
#
# 'cosa' es de qué hablábamos: "rover", o el id de un sensor ("ruido").

def resolver_referencias(texto, cosa):
    """Devuelve el texto con la referencia resuelta, o None si no había nada que resolver."""
    if not cosa:
        return None
    t = simple(texto).strip(" ,.?!¿¡")

    if cosa == "rover":
        reglas = [
            (r"^(manda|lleva|mueve|envia)(?:lo|la)\s+(.+)$", r"\1 el rover \2"),
            (r"^(recarga|conecta)(?:lo|la)$", r"\1 el rover"),
            (r"^(?:y\s+)?(donde (?:esta|anda|quedo)|como (?:va|esta|anda))(?: ahora| ahorita)?$", r"\1 el rover"),
            (r"^(?:y\s+)?(?:ahora|luego)\s+(?:a|al punto|hacia)\s+(.+)$", r"manda el rover a \1"),
        ]
    else:
        reglas = [
            (r"^(activa|apaga|desactiva|autoriza|enciende|prende)(?:lo|la)$", r"\1 el sensor de " + cosa),
        ]

    for patron, reemplazo in reglas:
        if re.match(patron, t):
            return re.sub(patron, reemplazo, t)
    return None


# ==========================================
# ¿QUISISTE DECIR...?
# ==========================================
#
# Frases que FOCUS sabe entender, escritas como las diría una persona.
# Si algo no se entiende, se busca la más parecida de aquí.

EJEMPLOS = [
    # plática
    "hola", "¿qué puedes hacer?", "¿quién eres?", "¿cómo estás?", "¿quién te creó?",
    "¿cómo me llamo?", "¿qué me gusta?", "¿qué rutinas tengo?",
    # sistema
    "¿cómo está la compu?", "¿quién está conectado?", "¿qué pasó hoy?", "¿hubo errores hoy?",
    "¿hay problemas?", "¿hubo algo sospechoso?",
    # rover
    "conecta el rover", "¿dónde está el rover?", "manda el rover a 3 4", "recarga el rover",
    # entorno
    "¿qué sensores tengo?", "¿cómo está el entorno?", "muéstrame el mapa", "activa el micrófono",
    # laboratorio
    "¿qué proyectos tengo?", "¿qué sigue?", "carga el proyecto focus",
    # respaldos
    "haz un respaldo", "¿qué respaldos tengo?", "muéstrame la bitácora", "¿qué experimentos hay?",
    # privacidad y web
    "¿qué carpetas proteges?", "¿qué permisos hay?", "mis sitios",
    # conocimiento
    "¿qué recuerdas?", "¿de qué hablábamos?", "cambiemos de tema", "¿quién te dijo eso?",
]


def parecido(a, b):
    """0 a 1: qué tanto se parecen dos frases (sin acentos ni signos)."""
    return SequenceMatcher(None, simple(a).strip(" ¿?¡!"), simple(b).strip(" ¿?¡!")).ratio()


def sugerir(texto, minimo=0.6):
    """La frase de EJEMPLOS más parecida a 'texto', o None si ninguna se parece lo suficiente."""
    if len(simple(texto).strip()) < 3:
        return None
    mejor = max(EJEMPLOS, key=lambda e: parecido(texto, e))
    return mejor if parecido(texto, mejor) >= minimo else None