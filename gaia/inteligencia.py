"""
GAIA — Inteligencia.

El molde que comparten todas las inteligencias de FOCUS. Cada una:

    - tiene un nombre ("apollo", "minerva", "rover_1"),
    - dice qué acciones sabe hacer,
    - recibe los datos de una orden y devuelve un diccionario.

Ejemplo:

    class Saludador(Inteligencia):
        nombre = "saludador"
        descripcion = "Saluda a quien se lo pida."

        def __init__(self):
            self.acciones = {"saludar": self.saludar}

        def saludar(self, datos):
            return {"texto": f"Hola, {datos['nombre']}"}

Una inteligencia NO conoce a las demás: solo responde lo que le piden.
Si necesita ayuda de otra, se la pide a GAIA (ver self.gaia).
"""


class Inteligencia:

    nombre = ""
    descripcion = ""

    # {nombre de la acción: función que recibe 'datos' y devuelve un dict}
    acciones = {}

    # GAIA la llena al registrarla, para que pueda pedir cosas a otras.
    gaia = None

    def presentarse(self):
        """Lo que GAIA y las demás necesitan saber de ella."""
        return {
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "acciones": sorted(self.acciones),
        }

    def al_conectarse(self):
        """
        GAIA la llama justo después de registrarla. Sirve para preparar
        lo que necesite ya conectada, como suscribirse a eventos.
        Por defecto no hace nada.
        """

    def sabe(self, accion):
        return accion in self.acciones

    def atender(self, orden):
        """Ejecuta la acción que pide la orden y devuelve sus datos."""
        return self.acciones[orden["accion"]](orden["datos"])