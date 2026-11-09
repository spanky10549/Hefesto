"""
APOLLO como inteligencia de FOCUS.

Envuelve las funciones de APOLLO para que se puedan pedir por mensajes
a través de GAIA. El conocimiento sigue viviendo en apollo/; este
archivo solo traduce "mensaje → función → diccionario".

Acciones:
    definir            {"concepto"}                     → la definición en datos
    responder          {"sujeto", "relacion", "objeto"} → sí / no / no sé, con la cadena
    aprender_relacion  {"sujeto", "relacion", "objeto", "negada"?, "reemplazar"?}
    existe             {"concepto"}                     → {"existe": True/False}
    sugerir            {"concepto"}                     → {"sugerencia": ... o None}
"""

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo

from apollo.definicion import definir
from apollo.razonamiento import responder
from apollo.conocimiento import aprender_relacion, existe_concepto, sugerir_concepto


def _texto(datos, campo):
    """Saca un texto obligatorio de los datos, o rechaza la orden."""
    valor = datos.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise Rechazo(f"falta '{campo}'")
    return valor


class Apollo(Inteligencia):

    nombre = "apollo"
    descripcion = "Base de conocimiento compartida: conceptos, relaciones y razonamiento."

    def __init__(self):
        self.acciones = {
            "definir": self.definir,
            "responder": self.responder,
            "aprender_relacion": self.aprender_relacion,
            "existe": self.existe,
            "sugerir": self.sugerir,
        }

    def definir(self, datos):
        return definir(_texto(datos, "concepto"))

    def responder(self, datos):
        respuesta, cadena = responder(
            _texto(datos, "sujeto"),
            _texto(datos, "relacion"),
            _texto(datos, "objeto"),
        )
        return {"respuesta": respuesta, "cadena": cadena}

    def aprender_relacion(self, datos):
        return aprender_relacion(
            _texto(datos, "sujeto"),
            _texto(datos, "relacion"),
            _texto(datos, "objeto"),
            negada=bool(datos.get("negada", False)),
            reemplazar=bool(datos.get("reemplazar", False)),
        )

    def existe(self, datos):
        return {"existe": existe_concepto(_texto(datos, "concepto"))}

    def sugerir(self, datos):
        return {"sugerencia": sugerir_concepto(_texto(datos, "concepto"))}
