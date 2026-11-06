"""
Estado de la conversación entre sesiones.

Guarda de qué se estaba hablando (y la última pregunta) para que,
al volver a abrir HEFESTO, la conversación siga donde se quedó:

    (ayer)  Tú: qué sabes del pingüino
            Tú: salir
    (hoy)   HEFESTO: La última vez hablábamos de pingüino.
            Tú: ¿y qué tiene?          → qué tiene pingüino
"""

from datetime import datetime

from memoria.almacenamiento import cargar_json, guardar_json


ARCHIVO_CONVERSACION = "conversacion.json"

ESTADO_VACIO = {"tema": None, "plantilla": None, "fecha": None}


def cargar_estado():
    """Devuelve el estado guardado, o uno vacío si no hay o está dañado."""
    try:
        estado = cargar_json(ARCHIVO_CONVERSACION, ESTADO_VACIO)
    except Exception:
        # Si el archivo se daña no vale la pena detener a HEFESTO:
        # solo se pierde de qué estaban hablando.
        return dict(ESTADO_VACIO)

    if not isinstance(estado, dict):
        return dict(ESTADO_VACIO)

    return {clave: estado.get(clave) for clave in ESTADO_VACIO}


def guardar_estado(tema, plantilla):
    """Guarda el tema y la última pregunta, con la fecha y hora."""
    guardar_json(ARCHIVO_CONVERSACION, {
        "tema": tema,
        "plantilla": plantilla,
        "fecha": datetime.now().isoformat(timespec="minutes")
    })


def olvidar_estado():
    """Borra el tema guardado (para empezar una conversación nueva)."""
    guardar_json(ARCHIVO_CONVERSACION, dict(ESTADO_VACIO))


def describir_fecha(fecha_texto, ahora=None):
    """
    'hace un rato', 'hoy', 'ayer' o 'el 3 de noviembre'.
    Devuelve None si la fecha no se entiende.
    """
    try:
        fecha = datetime.fromisoformat(fecha_texto)
    except (TypeError, ValueError):
        return None

    ahora = ahora or datetime.now()
    dias = (ahora.date() - fecha.date()).days

    if dias == 0 and (ahora - fecha).total_seconds() < 3600:
        return "hace un rato"
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "ayer"

    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
        "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    return f"el {fecha.day} de {meses[fecha.month - 1]}"