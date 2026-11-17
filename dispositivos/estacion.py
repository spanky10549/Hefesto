"""
Estación de sensores simulada.

Hace como si fuera un ESP32 con sensores de temperatura, humedad y luz
en tu cuarto. Los valores cambian poco a poco, como en la realidad.

Lo importante es su "contrato": sabe hacer la acción "leer" y devuelve

    {"lecturas": [{"sensor": "temp_cuarto", "tipo": "temperatura",
                   "lugar": "cuarto", "valor": 24.3}, ...]}

Cualquier dispositivo real (un ESP32, tu dispositivo con cámara) solo
tiene que cumplir ese mismo contrato y ÉTER lo va a entender, sin
cambiar nada en ÉTER.

Acciones:
    leer     {}                     → las lecturas de todos sus sensores
    simular  {"sensor", "valor"}    → fuerza un valor (para probar alertas)
"""

import random

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo


# id: (tipo, valor inicial, cuánto puede moverse por lectura, mínimo, máximo)
SENSORES = {
    "temp_cuarto": ("temperatura", 24.0, 0.4, 10, 35),
    "humedad_cuarto": ("humedad", 45.0, 2.0, 20, 80),
    "luz_cuarto": ("luz", 250.0, 30.0, 0, 800),
}


class EstacionSimulada(Inteligencia):

    descripcion = "Estación de sensores simulada (temperatura, humedad y luz)."

    def __init__(self, nombre="estacion_1", lugar="cuarto", semilla=None):
        self.nombre = nombre
        self.lugar = lugar
        # Con semilla, los "números al azar" salen siempre iguales (útil en pruebas).
        self.azar = random.Random(semilla)
        self.valores = {sensor: inicial for sensor, (_, inicial, _, _, _) in SENSORES.items()}
        self.forzados = {}

        self.acciones = {"leer": self.leer, "simular": self.simular}

    def _siguiente(self, sensor):
        if sensor in self.forzados:
            return self.forzados.pop(sensor)

        _, _, paso, minimo, maximo = SENSORES[sensor]
        nuevo = self.valores[sensor] + self.azar.uniform(-paso, paso)
        return round(min(max(nuevo, minimo), maximo), 1)

    def leer(self, datos):
        lecturas = []
        for sensor, (tipo, *_resto) in SENSORES.items():
            self.valores[sensor] = self._siguiente(sensor)
            lecturas.append({
                "sensor": sensor,
                "tipo": tipo,
                "lugar": self.lugar,
                "valor": self.valores[sensor],
            })
        return {"lecturas": lecturas}

    def simular(self, datos):
        sensor, valor = datos.get("sensor"), datos.get("valor")
        if sensor not in SENSORES:
            raise Rechazo(f"no tengo el sensor '{sensor}'; tengo: {', '.join(SENSORES)}")
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            raise Rechazo("'valor' debe ser un número")

        self.forzados[sensor] = valor
        return {"sensor": sensor, "proxima_lectura": valor}