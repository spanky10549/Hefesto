"""
HADES — Gestión de fallos y recuperación (v1).

TABRIS detecta y documenta; HADES responde. Escucha dos avisos:

    fallo     GAIA lo publica cuando una inteligencia truena.
              → HADES abre un incidente (o suma el fallo a uno abierto).

    anomalia  TABRIS lo publica cuando alguien falla varias veces seguidas.
              → HADES la aísla: GAIA deja de entregarle órdenes, para que
                el problema no se extienda.

Después, alguien (tú, desde HEFESTO) le pide que la recupere:
HADES le pide que se reinicie y, si funciona, la libera y cierra
sus incidentes.

Acciones:
    incidentes  {"abiertos"?: True}  → la lista de incidentes
    recuperar   {"inteligencia"}     → intenta reiniciarla y liberarla
"""

from datetime import datetime

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, crear_evento


ABIERTO = "abierto"
AISLADO = "aislado"        # abierto, y la inteligencia está en cuarentena
RESUELTO = "resuelto"


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


class Hades(Inteligencia):

    nombre = "hades"
    descripcion = "Atiende fallos: abre incidentes, aísla a quien falla seguido y la recupera."

    def __init__(self):
        self.incidentes = []
        self.acciones = {
            "incidentes": self.listar,
            "recuperar": self.recuperar,
        }

    # ==========================================
    # ESCUCHAR
    # ==========================================

    def al_conectarse(self):
        self.gaia.suscribir("fallo", self.atender_fallo)
        self.gaia.suscribir("anomalia", self.atender_anomalia)

    def _abierto_de(self, inteligencia):
        """El incidente sin resolver de una inteligencia, si tiene."""
        for incidente in self.incidentes:
            if incidente["inteligencia"] == inteligencia and incidente["estado"] != RESUELTO:
                return incidente
        return None

    def atender_fallo(self, evento):
        """Un fallo nuevo: se anota en su incidente, o se abre uno."""
        datos = evento["datos"]
        quien = datos["inteligencia"]

        incidente = self._abierto_de(quien)

        if incidente is None:
            incidente = {
                "numero": len(self.incidentes) + 1,
                "inteligencia": quien,
                "estado": ABIERTO,
                "fallos": 0,
                "ultimo_detalle": None,
                "abierto": _ahora(),
                "cerrado": None,
            }
            self.incidentes.append(incidente)

        incidente["fallos"] += 1
        incidente["ultimo_detalle"] = datos.get("detalle")

    def atender_anomalia(self, evento):
        """Falla demasiado seguido: a cuarentena."""
        quien = evento["datos"]["inteligencia"]

        try:
            self.gaia.aislar(quien, motivo="falló varias veces seguidas")
        except ValueError:
            return   # no existe o no se puede aislar (como HADES misma)

        incidente = self._abierto_de(quien)
        if incidente is not None:
            incidente["estado"] = AISLADO

    # ==========================================
    # ACCIONES
    # ==========================================

    def listar(self, datos):
        incidentes = self.incidentes
        if datos.get("abiertos"):
            incidentes = [i for i in incidentes if i["estado"] != RESUELTO]

        return {"incidentes": [dict(i) for i in incidentes]}

    def recuperar(self, datos):
        quien = datos.get("inteligencia")
        if not isinstance(quien, str) or not quien:
            raise Rechazo("falta 'inteligencia'")

        if quien not in self.gaia.inteligencias:
            raise Rechazo(f"no conozco a '{quien}'")

        estaba_aislada = self.gaia.esta_aislada(quien)

        if not self.gaia.reiniciar(quien):
            self.gaia.publicar(crear_evento(self.nombre, "recuperacion_fallida", {
                "inteligencia": quien
            }))
            return {"recuperada": False, "inteligencia": quien, "estaba_aislada": estaba_aislada}

        self.gaia.liberar(quien)

        cerrados = 0
        for incidente in self.incidentes:
            if incidente["inteligencia"] == quien and incidente["estado"] != RESUELTO:
                incidente["estado"] = RESUELTO
                incidente["cerrado"] = _ahora()
                cerrados += 1

        self.gaia.publicar(crear_evento(self.nombre, "recuperacion", {
            "inteligencia": quien, "incidentes_cerrados": cerrados
        }))

        return {
            "recuperada": True,
            "inteligencia": quien,
            "estaba_aislada": estaba_aislada,
            "incidentes_cerrados": cerrados,
        }