"""
MINERVA — Planeador.

Convierte una tarea escrita en español en una lista de pasos:

    "investiga qué es una raspberry pi, calcula 5 × 35 y revisa los recursos"

    1. apollo       → definir   {"concepto": "raspberry pi"}
    2. calculadora  → calcular  {"operacion": "5 × 35"}
    3. artemis      → estado    {}

Funciona con reglas: cada regla dice con qué palabras empieza una
parte de la tarea y a qué inteligencia le toca. No sabe si esas
inteligencias existen; eso lo revisa MINERVA (servicio.py).

Funciones puras: reciben texto y devuelven datos.
"""

import re
import unicodedata


# ==========================================
# TEXTO SIMPLE PARA COMPARAR
# ==========================================

def simple(texto):
    """
    'Investiga ¿QUÉ es?' → 'investiga  que es '

    Quita acentos y signos, y pasa a minúsculas, PERO conserva el largo
    del texto: cada letra se cambia por otra, nunca se borra. Así una
    posición en el texto simple es la misma en el original, y se puede
    recortar el original (con sus acentos) donde se encontró algo.
    """
    resultado = []

    for letra in texto.lower():
        if letra == "ñ":
            resultado.append(letra)
        elif letra in "¿?¡!":
            resultado.append(" ")
        else:
            resultado.append(unicodedata.normalize("NFD", letra)[0])

    return "".join(resultado)


ARTICULOS = ("el ", "la ", "los ", "las ", "un ", "una ", "unos ", "unas ")


def quitar_articulo(texto):
    """'una raspberry pi' → 'raspberry pi'"""
    texto = texto.strip()
    for articulo in ARTICULOS:
        if simple(texto).startswith(articulo):
            return texto[len(articulo):].strip()
    return texto


# ==========================================
# DIVIDIR LA TAREA
# ==========================================

# Palabras con las que empieza cada parte de una tarea.
VERBOS = (
    "investiga", "investigar", "averigua", "averiguar", "define", "definir",
    "busca", "buscar", "dime", "explicame", "que es", "que son",
    "calcula", "calcular", "resuelve", "resolver", "cuanto es", "cuanto son",
    "revisa", "revisar", "checa", "checar", "mide", "medir", "que paso",
)

# Lo que sobra en las orillas de cada parte: "¿Qué es X?" → "Qué es X"
SOBRANTES = " .¿?¡!"

CONECTORES = ("y luego ", "luego ", "despues ", "y despues ", "primero ", "tambien ", "por favor ", "y ")

# " y " seguido de un verbo de tarea: "calcula 5 + 3 y revisa..." se divide,
# pero "define agua y hielo" o "calcula 2 y 3" no.
_Y_ANTES_DE_VERBO = re.compile(
    r"\s+y\s+(?=(?:luego\s+|despues\s+)?(?:" + "|".join(VERBOS) + r")\b)"
)


def _cortes(texto_simple):
    """Las posiciones (inicio, fin) de cada separador encontrado."""
    cortes = [(m.start(), m.end()) for m in re.finditer(r"[,;]", texto_simple)]
    cortes += [(m.start(), m.end()) for m in _Y_ANTES_DE_VERBO.finditer(texto_simple)]
    return sorted(cortes)


def dividir_tarea(texto):
    """
    'investiga qué es X, calcula 2 + 2 y luego revisa los recursos'
        → ['investiga qué es X', 'calcula 2 + 2', 'revisa los recursos']
    """
    texto_simple = simple(texto)
    partes, inicio = [], 0

    for corte_inicio, corte_fin in _cortes(texto_simple):
        partes.append(texto[inicio:corte_inicio])
        inicio = corte_fin
    partes.append(texto[inicio:])

    limpias = []
    for parte in partes:
        parte = parte.strip(SOBRANTES)
        # Quitar "luego", "y después"... del inicio
        cambio = True
        while cambio:
            cambio = False
            for conector in CONECTORES:
                if simple(parte).startswith(conector):
                    parte = parte[len(conector):].strip(SOBRANTES)
                    cambio = True
        if parte:
            limpias.append(parte)

    return limpias


# ==========================================
# INTERPRETAR CADA PARTE
# ==========================================

def _despues_de(prefijos, parte):
    """Si 'parte' empieza con algún prefijo, devuelve lo que sigue (original)."""
    parte_simple = simple(parte)
    for prefijo in sorted(prefijos, key=len, reverse=True):
        if parte_simple == prefijo or parte_simple.startswith(prefijo + " "):
            return parte[len(prefijo):].strip(" ¿?¡!:")
    return None


PREFIJOS_DEFINIR = (
    "investiga que es", "investiga que son", "investiga sobre", "investiga",
    "investigar que es", "investigar que son", "investigar sobre", "investigar",
    "averigua que es", "averiguar que es", "define", "definir",
    "busca informacion sobre", "busca informacion de",
    "buscar informacion sobre", "buscar informacion de",
    "dime que es", "explicame que es", "que es", "que son",
)

PREFIJOS_CALCULAR = (
    "calcula", "calcular", "resuelve", "resolver", "cuanto es", "cuanto son",
)

VERBOS_REVISAR = ("revisa", "revisar", "checa", "checar", "mide", "medir")


def interpretar(parte):
    """
    Una parte de la tarea → un paso, o None si no la entiende.
        {"para": "apollo", "accion": "definir", "datos": {"concepto": "..."}}
    """
    parte = parte.strip(SOBRANTES)
    parte_simple = simple(parte)

    # Calcular va antes que definir: "cuánto es" no debe tomarse como "qué es"
    operacion = _despues_de(PREFIJOS_CALCULAR, parte)
    if operacion:
        return {"para": "calculadora", "accion": "calcular", "datos": {"operacion": operacion}}

    # "revisa los recursos", "checa cómo está la compu", "revisa los errores"
    palabras = parte_simple.split()
    if palabras and palabras[0] in VERBOS_REVISAR:
        if any(clave in parte_simple for clave in ("error", "registro", "problema")):
            return {"para": "tabris", "accion": "resumen", "datos": {"dia": "hoy"}}
        if any(clave in parte_simple for clave in ("recurso", "compu", "memoria", "ram", "disco", "bateria")):
            return {"para": "artemis", "accion": "estado", "datos": {}}

    if parte_simple.strip().startswith("que paso"):
        return {"para": "tabris", "accion": "resumen", "datos": {"dia": "hoy"}}

    concepto = _despues_de(PREFIJOS_DEFINIR, parte)
    if concepto:
        return {"para": "apollo", "accion": "definir", "datos": {"concepto": quitar_articulo(concepto)}}

    return None


def planear(tarea):
    """
    La tarea completa → plan con pasos numerados y lo que no se entendió.
    """
    pasos, no_entendidos = [], []

    for parte in dividir_tarea(tarea):
        paso = interpretar(parte)

        if paso is None:
            no_entendidos.append(parte)
            continue

        pasos.append({
            "numero": len(pasos) + 1,
            "descripcion": parte,
            **paso,
            "si_falla": "continuar",
        })

    return {"tarea": tarea, "pasos": pasos, "no_entendidos": no_entendidos}