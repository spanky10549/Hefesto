"""
APOLLO como inteligencia de FOCUS.

Envuelve las funciones de APOLLO para que se puedan pedir por mensajes
a través de GAIA. El conocimiento sigue viviendo en apollo/; este
archivo solo traduce "mensaje → función → diccionario".

Acciones:
    definir            {"concepto"}                     → la definición en datos
    responder          {"sujeto", "relacion", "objeto"} → sí / no / no sé, con la cadena
                                                           (cada paso con su "fuente")
    aprender_relacion  {"sujeto", "relacion", "objeto", "negada"?, "reemplazar"?, "fuente"?}
    fuentes            {"concepto"}                     → lo que sabe de él y de dónde salió cada cosa
    existe             {"concepto"}                     → {"existe": True/False}
    sugerir            {"concepto"}                     → {"sugerencia": ... o None}
"""

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo

from apollo.definicion import definir
from apollo.razonamiento import responder, con_fuentes, hechos_con_fuente
from apollo.conocimiento import aprender_relacion, existe_concepto, sugerir_concepto, buscar_entrada
from apollo.fuentes import USUARIO


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
            "fuentes": self.fuentes,
        }

    def definir(self, datos):
        return definir(_texto(datos, "concepto"))

    def responder(self, datos):
        respuesta, cadena = responder(
            _texto(datos, "sujeto"),
            _texto(datos, "relacion"),
            _texto(datos, "objeto"),
        )
        return {"respuesta": respuesta, "cadena": con_fuentes(cadena)}

    def aprender_relacion(self, datos):
        return aprender_relacion(
            _texto(datos, "sujeto"),
            _texto(datos, "relacion"),
            _texto(datos, "objeto"),
            negada=bool(datos.get("negada", False)),
            reemplazar=bool(datos.get("reemplazar", False)),
            fuente=datos.get("fuente") or USUARIO,
        )

    def existe(self, datos):
        return {"existe": existe_concepto(_texto(datos, "concepto"))}

    def sugerir(self, datos):
        return {"sugerencia": sugerir_concepto(_texto(datos, "concepto"))}

    def fuentes(self, datos):
        concepto = _texto(datos, "concepto")
        entrada = buscar_entrada(concepto)
        return {"concepto": entrada["palabra"] if entrada else concepto,
                "conocido": entrada is not None,
                "hechos": hechos_con_fuente(concepto) if entrada else []}