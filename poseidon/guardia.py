"""
POSEIDON — Guardia.

Revisa cada mensaje que llega por la red antes de dejarlo pasar:

    1. ¿Tiene una firma válida?        si no: alguien sin la clave lo mandó
                                        o lo cambiaron en el camino
    2. ¿Es reciente?                    si no: puede ser una grabación vieja
    3. ¿Ya lo había recibido antes?     si sí: alguien lo está repitiendo

Los puntos 2 y 3 evitan el "ataque de repetición": alguien graba una
orden válida ("avanza 5 metros") y la vuelve a mandar después. La firma
seguiría siendo válida, pero la fecha delata que es vieja y el id que
ya se usó.

La usan los dos lados: GAIA al recibir respuestas y el rover al
recibir órdenes.
"""

from collections import deque
from datetime import datetime

from poseidon.firma import firmar, firma_valida


# Un mensaje con más de esto de antigüedad (o de "futuro") se rechaza.
VENTANA_SEGUNDOS = 60

# Cuántos ids recientes recordar para detectar repeticiones.
MAX_IDS_RECORDADOS = 1000


class MensajeSospechoso(Exception):
    """El mensaje no pasó la revisión. El texto dice por qué."""


class Guardia:

    def __init__(self, clave, ventana=VENTANA_SEGUNDOS, ahora=None):
        self.clave = clave
        self.ventana = ventana
        # 'ahora' se puede cambiar en las pruebas para simular el paso del tiempo.
        self.ahora = ahora or datetime.now
        self.ids_vistos = deque(maxlen=MAX_IDS_RECORDADOS)

    def sellar(self, mensaje):
        """Firma un mensaje que va a salir."""
        return firmar(mensaje, self.clave)

    def revisar(self, mensaje):
        """
        Revisa un mensaje que llegó. Lanza MensajeSospechoso si algo
        está mal; si todo está bien, lo devuelve sin la firma.
        """
        if not firma_valida(mensaje, self.clave):
            raise MensajeSospechoso("firma inválida")

        try:
            fecha = datetime.fromisoformat(mensaje["fecha"])
        except (KeyError, TypeError, ValueError):
            raise MensajeSospechoso("fecha ilegible")

        diferencia = abs((self.ahora() - fecha).total_seconds())
        if diferencia > self.ventana:
            raise MensajeSospechoso(f"mensaje viejo o del futuro ({diferencia:.0f} s)")

        if mensaje.get("id") in self.ids_vistos:
            raise MensajeSospechoso("mensaje repetido")

        self.ids_vistos.append(mensaje.get("id"))

        return {campo: valor for campo, valor in mensaje.items() if campo != "firma"}