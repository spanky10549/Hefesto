"""
POSEIDON — Protección de las comunicaciones (v1).

La firma y la revisión de mensajes viven en firma.py y guardia.py,
porque las usan tanto GAIA como el rover. POSEIDON, como inteligencia,
lleva la cuenta de lo sospechoso que pasa en la red: escucha el evento
"mensaje_sospechoso" (lo publica quien detecta algo raro) y lo reporta.

Acciones:
    reporte  {}  → cuántos mensajes sospechosos, por qué y el último
"""

from gaia.inteligencia import Inteligencia


class Poseidon(Inteligencia):

    nombre = "poseidon"
    descripcion = "Protege las comunicaciones: firma mensajes y reporta los sospechosos."

    def __init__(self):
        self.sospechosos = []
        self.acciones = {"reporte": self.reporte}

    def al_conectarse(self):
        self.gaia.suscribir("mensaje_sospechoso", self.anotar)

    def anotar(self, evento):
        self.sospechosos.append({
            "motivo": evento["datos"].get("motivo"),
            "origen": evento["datos"].get("origen"),
            "fecha": evento["fecha"],
        })

    def reporte(self, datos):
        por_motivo = {}
        for s in self.sospechosos:
            por_motivo[s["motivo"]] = por_motivo.get(s["motivo"], 0) + 1

        return {
            "sospechosos": len(self.sospechosos),
            "por_motivo": por_motivo,
            "ultimo": self.sospechosos[-1] if self.sospechosos else None,
        }