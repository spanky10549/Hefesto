"""
La calculadora como herramienta de FOCUS.

Acciones:
    calcular  {"operacion": "3 + 4 × 2"}
        → {"expresion", "resultado", "resultado_texto", "pasos"}

El resultado exacto es una Fraction, que no se puede mandar por la red;
aquí se manda como texto ("11", "1/3") y quien lo necesite exacto lo
reconstruye con Fraction(resultado).
"""

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo

from calculo.aritmetica import calcular, ErrorCalculo


class Calculadora(Inteligencia):

    nombre = "calculadora"
    descripcion = "Resuelve operaciones exactas y explica cada paso."

    def __init__(self):
        self.acciones = {"calcular": self.calcular}

    def calcular(self, datos):
        operacion = datos.get("operacion")
        if not isinstance(operacion, str) or not operacion.strip():
            raise Rechazo("falta la operación")

        try:
            r = calcular(operacion)
        except ErrorCalculo as error:
            raise Rechazo(str(error)) from error

        return {**r, "resultado": str(r["resultado"])}
