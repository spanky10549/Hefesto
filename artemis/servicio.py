"""
ARTEMIS — Administración de recursos (v1).

Sabe cuánta CPU, RAM, disco y batería hay, avisa cuando algo se está
acabando y responde si alcanza para una tarea. Según el plan de FOCUS,
informa a GAIA y apoya a MINERVA (que va a preguntarle "¿alcanza?"
antes de planear algo pesado).

Acciones:
    estado   {}                              → la medición y sus alertas
    alcanza  {"ram_mb"?, "disco_mb"?}        → si hay suficiente, y cuánto falta

Eventos que publica:
    recursos_bajos  cuando aparece una alerta nueva (no repite la misma)
"""

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, crear_evento

from artemis.medidor import medir, FaltaPsutil


MB = 1024 * 1024

# A partir de qué porcentaje de uso se avisa.
LIMITE_CPU = 90
LIMITE_RAM = 90
LIMITE_DISCO = 90

# Batería: avisar cuando quede esto o menos y no esté conectada.
LIMITE_BATERIA = 15


def revisar(medicion):
    """
    Las alertas de una medición: [{"recurso": "ram", "texto": "..."}].
    Función pura: no mide nada, solo revisa números (fácil de probar).
    """
    alertas = []

    if medicion["cpu"]["porcentaje"] >= LIMITE_CPU:
        alertas.append({"recurso": "cpu", "texto": "el procesador está casi al máximo"})

    if medicion["ram"]["porcentaje"] >= LIMITE_RAM:
        alertas.append({"recurso": "ram", "texto": "queda poca memoria RAM"})

    if medicion["disco"]["porcentaje"] >= LIMITE_DISCO:
        alertas.append({"recurso": "disco", "texto": "el disco está casi lleno"})

    bateria = medicion.get("bateria")
    if bateria and not bateria["conectada"] and bateria["porcentaje"] <= LIMITE_BATERIA:
        alertas.append({"recurso": "bateria", "texto": "la batería está por acabarse"})

    return alertas


class Artemis(Inteligencia):

    nombre = "artemis"
    descripcion = "Administra recursos: CPU, RAM, disco y batería; avisa cuando escasean."

    def __init__(self, medidor=None):
        # 'medidor' se puede cambiar por uno de mentira en las pruebas,
        # para simular una compu con la RAM llena sin llenarla de verdad.
        self.medidor = medidor or medir
        self.alertas_avisadas = set()

        self.acciones = {
            "estado": self.estado,
            "alcanza": self.alcanza,
        }

    def _medir(self):
        try:
            return self.medidor()
        except FaltaPsutil as error:
            raise Rechazo(str(error)) from error

    def _avisar_nuevas(self, alertas):
        """Publica 'recursos_bajos' solo si hay alertas que no se habían avisado."""
        actuales = {a["recurso"] for a in alertas}
        nuevas = actuales - self.alertas_avisadas

        # Lo que ya se resolvió se olvida, para poder avisar si vuelve a pasar.
        self.alertas_avisadas = actuales

        if nuevas and self.gaia is not None:
            self.gaia.publicar(crear_evento(self.nombre, "recursos_bajos", {
                "alertas": [a for a in alertas if a["recurso"] in nuevas]
            }))

    def estado(self, datos):
        medicion = self._medir()
        alertas = revisar(medicion)
        self._avisar_nuevas(alertas)
        return {**medicion, "alertas": alertas}

    def alcanza(self, datos):
        pedido = {}
        for campo in ("ram_mb", "disco_mb"):
            valor = datos.get(campo, 0)
            if not isinstance(valor, (int, float)) or valor < 0:
                raise Rechazo(f"'{campo}' debe ser un número positivo")
            pedido[campo] = valor

        medicion = self._medir()

        hay = {
            "ram_mb": medicion["ram"]["disponible"] / MB,
            "disco_mb": medicion["disco"]["libre"] / MB,
        }

        faltan = {
            campo: round(pedido[campo] - hay[campo])
            for campo in pedido
            if pedido[campo] > hay[campo]
        }

        return {
            "alcanza": not faltan,
            "faltan": faltan,
            "hay": {campo: round(valor) for campo, valor in hay.items()},
        }