"""
GAIA — Mensajes.

Las inteligencias de FOCUS no se llaman directamente: se mandan
mensajes. Un mensaje es un diccionario sencillo que se puede convertir
a JSON, así que el mismo formato sirve dentro de Python, por WiFi o
para hablar con la mini IA de un robot.

    {
        "id": "a3f9...",
        "tipo": "orden",
        "de": "hefesto",
        "para": "apollo",
        "accion": "definir",
        "datos": {"concepto": "pingüino"},
        "objetivo": None,          # para qué sirve la orden
        "restricciones": {},       # límites que no se pueden romper
        "si_falla": None,          # plan B
        "fecha": "2026-11-08T22:30:00"
    }

Tipos de mensaje:
    orden      alguien pide que se haga algo
    respuesta  el resultado de una orden (lleva "responde_a" y "estado")
    evento     un aviso para quien le interese ("fallo", "aprendí algo")
"""

import json
import uuid
from datetime import datetime


ORDEN = "orden"
RESPUESTA = "respuesta"
EVENTO = "evento"

TIPOS = (ORDEN, RESPUESTA, EVENTO)

# Estados de una respuesta
OK = "ok"                    # se hizo
RECHAZADO = "rechazado"      # la inteligencia no pudo o no quiso hacerlo
ERROR = "error"              # algo se rompió por dentro
DESCONOCIDO = "desconocido"  # no existe ese destino o esa acción

ESTADOS = (OK, RECHAZADO, ERROR, DESCONOCIDO)

CAMPOS_OBLIGATORIOS = ("id", "tipo", "de", "para", "accion", "datos", "fecha")


class MensajeInvalido(Exception):
    """El mensaje no tiene la forma correcta."""


class Rechazo(Exception):
    """
    Una inteligencia la lanza cuando no puede cumplir una orden por una
    razón esperada: "no se puede dividir entre cero", "no conozco eso".
    No es un error del programa; GAIA lo devuelve como estado RECHAZADO.
    """


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


def crear_orden(de, para, accion, datos=None, objetivo=None,
                restricciones=None, si_falla=None):
    """
    crear_orden("hefesto", "apollo", "definir", {"concepto": "ave"})
    """
    return {
        "id": uuid.uuid4().hex,
        "tipo": ORDEN,
        "de": de,
        "para": para,
        "accion": accion,
        "datos": datos or {},
        "objetivo": objetivo,
        "restricciones": restricciones or {},
        "si_falla": si_falla,
        "fecha": _ahora(),
    }


def crear_respuesta(orden, estado, datos=None, detalle=None):
    """
    La respuesta va de vuelta a quien preguntó y dice a qué orden responde.
    'detalle' explica un rechazo o un error con palabras.
    """
    if estado not in ESTADOS:
        raise MensajeInvalido(f"estado desconocido: {estado}")

    return {
        "id": uuid.uuid4().hex,
        "tipo": RESPUESTA,
        "de": orden["para"],
        "para": orden["de"],
        "accion": orden["accion"],
        "datos": datos or {},
        "responde_a": orden["id"],
        "estado": estado,
        "detalle": detalle,
        "fecha": _ahora(),
    }


def crear_evento(de, nombre, datos=None):
    """
    Un aviso que no va dirigido a nadie en particular:
    crear_evento("gaia", "fallo", {"inteligencia": "apollo"})
    """
    return {
        "id": uuid.uuid4().hex,
        "tipo": EVENTO,
        "de": de,
        "para": "*",
        "accion": nombre,
        "datos": datos or {},
        "fecha": _ahora(),
    }


def validar(mensaje):
    """Revisa que el mensaje tenga todo lo necesario. Lanza MensajeInvalido si no."""
    if not isinstance(mensaje, dict):
        raise MensajeInvalido("un mensaje debe ser un diccionario")

    faltan = [campo for campo in CAMPOS_OBLIGATORIOS if campo not in mensaje]
    if faltan:
        raise MensajeInvalido(f"faltan campos: {', '.join(faltan)}")

    if mensaje["tipo"] not in TIPOS:
        raise MensajeInvalido(f"tipo desconocido: {mensaje['tipo']}")

    for campo in ("de", "para", "accion"):
        if not isinstance(mensaje[campo], str) or not mensaje[campo]:
            raise MensajeInvalido(f"'{campo}' debe ser un texto no vacío")

    if not isinstance(mensaje["datos"], dict):
        raise MensajeInvalido("'datos' debe ser un diccionario")

    if mensaje["tipo"] == RESPUESTA and mensaje.get("estado") not in ESTADOS:
        raise MensajeInvalido("una respuesta necesita un estado válido")

    return mensaje


def a_json(mensaje):
    """Mensaje → texto. Falla si algo no se puede mandar por la red."""
    try:
        return json.dumps(mensaje, ensure_ascii=False)
    except TypeError as error:
        raise MensajeInvalido(f"no se puede convertir a JSON: {error}") from error


def de_json(texto):
    """Texto → mensaje, revisado."""
    try:
        mensaje = json.loads(texto)
    except json.JSONDecodeError as error:
        raise MensajeInvalido(f"JSON inválido: {error}") from error

    return validar(mensaje)
