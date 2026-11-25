"""
APOLLO — Fuentes del conocimiento.

Cada dato que aprende HEFESTO se anota con DE DÓNDE salió y CUÁNDO:

    "usuario"               me lo dijiste tú
    "creador:spanky"        me lo dijo mi creador (con su clave comprobada)
    "documento:aves.txt"    lo leí en un documento
    "wordnet"               viene de WordNet (importado en bloque)

Si un dato no tiene fuente es porque lo aprendió antes de que existiera
esto: se dice así, sin inventar.

Lo deducido no se anota: se calcula al momento con la cadena de
razonamiento, y cada paso de la cadena sí tiene su fuente.

¿Para qué sirve?
    - Saber cuánto confiar en algo: no es lo mismo que lo diga el
      creador a que venga de un documento que leyó una vez.
    - Corregir mejor (#17): si un documento le enseñó varias cosas
      mal, se sabe cuáles fueron.
"""

from datetime import date

from memoria.base_datos import anotar_fuentes_sql, fuente_sql
from apollo.lenguaje import normalizar_concepto, normalizar_relacion


USUARIO = "usuario"
WORDNET = "wordnet"

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def documento(nombre):
    return f"documento:{nombre}"


def creador(nombre):
    return f"creador:{nombre}"


def _hoy():
    return date.today()


# ==========================================
# ANOTAR Y CONSULTAR
# ==========================================

def _clave(sujeto, tipo, objeto):
    """Todo normalizado, para que 'Las Aves' y 'ave' sean lo mismo."""
    tipo = "sinonimo" if tipo == "sinonimo" else normalizar_relacion(tipo)
    return normalizar_concepto(sujeto), tipo, normalizar_concepto(objeto)


def anotar(ruta, datos, fuente):
    """
    datos = [(sujeto, tipo, objeto, negada), ...]
    tipo: "es", "sinonimo" o la relación ("mide", "puede"...).
    """
    fecha = _hoy().isoformat()
    filas = [(*_clave(s, t, o), bool(n), fuente or USUARIO, fecha) for s, t, o, n in datos]
    if filas:
        anotar_fuentes_sql(ruta, filas)


def consultar(ruta, sujeto, tipo, objeto, negada=False):
    """{"fuente", "fecha"} o None si no se anotó."""
    fila = fuente_sql(ruta, *_clave(sujeto, tipo, objeto), negada)
    return {"fuente": fila[0], "fecha": fila[1]} if fila else None


# ==========================================
# DECIRLO EN ESPAÑOL
# ==========================================

def describir_fecha(texto, hoy=None):
    """'2026-11-24' → 'hoy' / 'ayer' / 'el 3 de noviembre' / 'el 3 de noviembre de 2025'"""
    hoy = hoy or _hoy()
    try:
        dia = date.fromisoformat(texto)
    except (TypeError, ValueError):
        return ""
    if dia == hoy:
        return "hoy"
    if (hoy - dia).days == 1:
        return "ayer"
    fecha = f"el {dia.day} de {MESES[dia.month - 1]}"
    return fecha if dia.year == hoy.year else f"{fecha} de {dia.year}"


def describir(dato, hoy=None):
    """
    {"fuente", "fecha"} (o None) → frase corta:
        "me lo dijiste tú hoy"
        "lo leí en aves.txt el 3 de noviembre"
    """
    if not dato:
        return "lo aprendí antes de que anotara de dónde viene cada cosa"

    fuente = dato["fuente"]
    cuando = describir_fecha(dato.get("fecha"), hoy)
    cuando = f" {cuando}" if cuando else ""

    if fuente == USUARIO:
        return f"me lo dijiste tú{cuando}"
    if fuente.startswith("creador:"):
        return f"me lo dijo {fuente.split(':', 1)[1]}, mi creador,{cuando}" if cuando \
            else f"me lo dijo {fuente.split(':', 1)[1]}, mi creador"
    if fuente.startswith("documento:"):
        return f"lo leí en {fuente.split(':', 1)[1]}{cuando}"
    if fuente == WORDNET:
        return f"viene de WordNet (lo importé{cuando})"
    return f"viene de {fuente}{cuando}"