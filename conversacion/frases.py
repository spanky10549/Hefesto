"""
Frases: tu forma de decir las cosas, aprendida.

Cuando FOCUS no entiende algo y te pregunta "¿quisiste decir…?", si le
dices que sí, se lo aprende. La próxima vez lo entiende directo:

    "como anda la maquina"  →  "¿cómo está la compu?"

También se lo puedes enseñar tú:
    cuando diga "checa todo", quiero decir "¿cómo está la compu?"

Se guarda en conversacion_frases.json (y ELEUTHIA lo respalda).
La llave es el texto simple (sin acentos, mayúsculas ni signos), así
"Cómo anda la máquina?" y "como anda la maquina" son la misma frase.
"""

import os

from memoria.almacenamiento import cargar_json, guardar_json
from minerva.planeador import simple


ARCHIVO_FRASES = "conversacion_frases.json"


def llave(texto):
    return " ".join(simple(texto).strip(" ,.¿?¡!").split())


class Frases:

    def __init__(self, ruta=None):
        self.ruta = ruta or ARCHIVO_FRASES
        self.frases = cargar_json(self.ruta, {}) if os.path.exists(self.ruta) else {}

    def _guardar(self):
        guardar_json(self.ruta, self.frases)

    def significado(self, texto):
        """Lo que quieres decir con 'texto', o None si no me lo has enseñado."""
        guardada = self.frases.get(llave(texto))
        return guardada["significa"] if guardada else None

    def aprender(self, dicho, significa):
        self.frases[llave(dicho)] = {"dicho": dicho.strip(), "significa": significa.strip()}
        self._guardar()

    def olvidar(self, dicho):
        if self.frases.pop(llave(dicho), None) is None:
            return False
        self._guardar()
        return True

    def todas(self):
        return [(f["dicho"], f["significa"]) for f in self.frases.values()]