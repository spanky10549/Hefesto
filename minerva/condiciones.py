"""
MINERVA — Condiciones.

Entiende condiciones escritas en español y las convierte en datos que
GAIA puede revisar al ejecutar el plan:

    "piezas es mayor que 100"      → {"izq": "piezas", "op": ">", "der": "100"}
    "la ram está arriba de 90"     → {"izq": "la ram", "op": ">", "der": "90"}
    "el resultado es igual a 4"    → {"izq": "el resultado", "op": "=", "der": "4"}
    "hay errores"                  → {"izq": "errores", "op": ">", "der": "0"}
    "no hay incidentes"            → {"izq": "incidentes", "op": "=", "der": "0"}

Funciones puras: texto entra, datos salen.
"""

import re

from minerva.planeador import simple, VERBOS

# Donde empieza un paso dentro de una condición sin coma:
# "si piezas > 100 calcula piezas ÷ 2" → se corta antes de "calcula"
_VERBO = re.compile(r"\s(?=(?:" + "|".join(sorted(VERBOS, key=len, reverse=True)) + r")\b)")


# Frases de comparación → operador. Las largas primero ("mayor o igual que"
# antes que "mayor que"), para que no se corte a la mitad.
COMPARACIONES = [
    ("mayor o igual que", ">="), ("mayor o igual a", ">="), ("al menos", ">="),
    ("menor o igual que", "<="), ("menor o igual a", "<="), ("a lo mucho", "<="),
    ("mayor que", ">"), ("mayor a", ">"), ("mas de", ">"), ("arriba de", ">"),
    ("encima de", ">"), ("pasa de", ">"), ("supera", ">"), ("supera a", ">"),
    ("menor que", "<"), ("menor a", "<"), ("menos de", "<"), ("abajo de", "<"),
    ("debajo de", "<"), ("baja de", "<"),
    ("diferente de", "!="), ("distinto de", "!="), ("distinto a", "!="),
    ("igual a", "="), ("igual que", "="),
    (">=", ">="), ("<=", "<="), ("!=", "!="), (">", ">"), ("<", "<"), ("=", "="),
]

SIMBOLOS = {">": "es mayor que", "<": "es menor que", ">=": "es al menos",
            "<=": "es a lo mucho", "=": "es igual a", "!=": "es diferente de"}

_RELLENO = r"(?:es |esta |sea |este |son |estan )?"


def _limpiar(texto):
    return " ".join(texto.strip(" ,.¿?¡!").split())


def entender(texto):
    """Una condición en español → {"izq", "op", "der", "texto"}, o None si no la entiende."""
    original = _limpiar(texto)
    t = simple(original)
    t = " ".join(t.split())

    # "hay errores" / "no hay incidentes"
    hay = re.match(r"^(no )?hay (.+)$", t)
    if hay:
        izq = hay.group(2).strip()
        op = "=" if hay.group(1) else ">"
        return {"izq": izq, "op": op, "der": "0", "texto": original}

    for frase, op in COMPARACIONES:
        frase_simple = re.escape(frase)
        # Para símbolos no hacen falta espacios: "piezas>100"
        separador = r"\s*" if not frase[0].isalpha() else r"\s+"
        patron = rf"^(.+?){separador}{_RELLENO}{frase_simple}{separador}(?:el |la |los |las |a )?(.+)$"
        encontrado = re.match(patron, t)
        if encontrado:
            izq = _limpiar(encontrado.group(1))
            der = _limpiar(encontrado.group(2))
            # "piezas es" → "piezas"
            izq = re.sub(r"\s+(es|esta|sea|este|son|estan)$", "", izq)
            if izq and der:
                return {"izq": izq, "op": op, "der": der, "texto": original}

    return None


def describir(condicion):
    """{"izq": "piezas", "op": ">", "der": "100"} → 'piezas es mayor que 100'"""
    return f"{condicion['izq']} {SIMBOLOS[condicion['op']]} {condicion['der']}"


# ==========================================
# DENTRO DE UNA TAREA
# ==========================================

_PLAN_B = re.compile(r"^(?:y\s+|o\s+)?si (?:falla|no se puede|no funciona|no sale)\b,?\s*")
_PLAN_B_EN_MEDIO = re.compile(r"[\s,]+(?:y\s+|o\s+)?si (?:falla|no se puede|no funciona|no sale)\b,?\s*")
_ENTONCES = re.compile(r"^si (.+?)\s+entonces\s+(.+)$")
_SOLO_SI = re.compile(r"^(.+?)\s+(?:solo\s+)?si\s+(.+)$")

DETENERSE = {"detente", "para", "detenerse", "cancela todo", "cancela", "no sigas", "alto"}


def partir_plan_b(parte):
    """
    'define tensor y si falla calcula 2 + 2' → ['define tensor', 'si falla calcula 2 + 2']
    (simple() conserva el largo, así que se puede cortar el original en el mismo lugar)
    """
    encontrado = _PLAN_B_EN_MEDIO.search(simple(parte))
    if not encontrado or encontrado.start() == 0:
        return [parte]
    return [parte[:encontrado.start()], parte[encontrado.start():].strip(" ,")]


def es_plan_b(parte):
    """'si falla, calcula 2 + 2' → 'calcula 2 + 2'; si no es plan B → None."""
    encontrado = _PLAN_B.match(simple(parte).strip())
    if not encontrado:
        return None
    inicio = len(parte) - len(parte.lstrip())
    return parte[inicio + encontrado.end():].strip(" ,.")


def es_detenerse(texto):
    return simple(texto).strip(" .!") in DETENERSE


def _corte_de_paso(extras):
    """Dónde empieza un paso: un verbo conocido o el nombre de una rutina."""
    if not extras:
        return _VERBO
    nombres = sorted(set(VERBOS) | {simple(e) for e in extras}, key=len, reverse=True)
    return re.compile(r"\s(?=(?:" + "|".join(re.escape(n) for n in nombres) + r")\b)")


def separar_condicion(parte, extras=()):
    """
    Busca una condición en la parte. Devuelve (condicion, resto):
        'si piezas > 100'                    → ({...}, '')          (aplica a lo que sigue)
        'si piezas > 100 entonces calcula X' → ({...}, 'calcula X')
        'calcula X si piezas > 100'          → ({...}, 'calcula X')
        'calcula X'                          → (None, 'calcula X')

    'extras' son nombres de rutinas: "si hay errores buenos días" se corta
    antes de "buenos días" aunque no empiece con un verbo.
    """
    t = simple(parte).strip()

    if t.startswith("si ") and not _PLAN_B.match(t):
        con_entonces = _ENTONCES.match(t)
        if con_entonces:
            corte = con_entonces.start(2) + (len(parte) - len(parte.lstrip()))
            condicion = entender(parte.strip()[3:con_entonces.end(1)])
            if condicion:
                return condicion, parte[corte:].strip()

        # "si piezas > 100 calcula piezas ÷ 2" (sin coma ni "entonces")
        sin_si = parte.strip()[3:]
        verbo = _corte_de_paso(extras).search(simple(sin_si))
        if verbo:
            condicion = entender(sin_si[:verbo.start()])
            if condicion:
                return condicion, sin_si[verbo.end():].strip()

        condicion = entender(sin_si)
        if condicion:
            return condicion, ""

    al_final = _SOLO_SI.match(t)
    if al_final:
        condicion = entender(parte.strip()[al_final.start(2):])
        if condicion:
            return condicion, parte.strip()[:al_final.end(1)]

    return None, parte