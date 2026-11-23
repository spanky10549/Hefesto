"""
Lo que FOCUS recuerda de ti: tu nombre y lo que te gusta.

Se guarda en conversacion_perfil.json (y ELEUTHIA lo respalda).
Solo guarda lo que tú le dices; nunca adivina.
"""

import os

from memoria.almacenamiento import cargar_json, guardar_json


ARCHIVO_PERFIL = "conversacion_perfil.json"


class Perfil:

    def __init__(self, ruta=None):
        self.ruta = ruta or ARCHIVO_PERFIL
        datos = cargar_json(self.ruta, {}) if os.path.exists(self.ruta) else {}
        self.nombre = datos.get("nombre")
        self.gustos = list(datos.get("gustos", []))

    def _guardar(self):
        guardar_json(self.ruta, {"nombre": self.nombre, "gustos": self.gustos})

    def poner_nombre(self, nombre):
        self.nombre = " ".join(nombre.strip(" .,!¡").split()).title() or None
        self._guardar()
        return self.nombre

    def agregar_gusto(self, gusto):
        gusto = " ".join(gusto.strip(" .,!¡").split())
        if not gusto:
            return False
        if gusto.lower() in (g.lower() for g in self.gustos):
            return False
        self.gustos.append(gusto)
        self._guardar()
        return True

    def quitar_gusto(self, gusto):
        antes = len(self.gustos)
        self.gustos = [g for g in self.gustos if g.lower() != gusto.strip(" .").lower()]
        self._guardar()
        return len(self.gustos) < antes