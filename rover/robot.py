"""
ROVER — La mini IA del robot.

Recibe órdenes CON SU OBJETIVO, no solo movimientos. Si algo sale mal
en el camino, no se detiene: evalúa la situación y decide.

Niveles de decisión (los que platicamos para FOCUS):
    - Encuentra un obstáculo → lo anota y recalcula la ruta (plan B:
      "buscar otra ruta"), sin preguntarle a nadie.
    - No hay ningún camino → se queda donde está y lo reporta.
    - Peligro real (la batería bajaría de lo permitido) → freno de
      seguridad: se detiene aunque no haya llegado. Este nivel no se
      puede desactivar desde una orden.

Acciones:
    estado    {}            → posición, batería y obstáculos que conoce
    ir_a      {"x", "y"}    → intenta llegar; reporta sus decisiones
    recargar  {}            → batería al 100 %

Restricciones que entiende (en la orden):
    bateria_minima  nunca bajar de este porcentaje (por defecto 10)

Plan B que entiende (si_falla):
    "buscar otra ruta"  (por defecto) recalcula al encontrar obstáculos
    "detenerse"         se detiene en el primer obstáculo
"""

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo

from rover import mundo


COSTO_POR_CASILLA = 2       # % de batería por cada casilla que avanza
BATERIA_MINIMA = 10         # % por defecto
MAX_INTENTOS = 200          # para no quedarse dando vueltas para siempre


class Rover(Inteligencia):

    nombre = "rover_1"
    descripcion = "Mini IA de un rover: se mueve en el mapa y decide cómo esquivar obstáculos."

    def __init__(self, obstaculos=None, ancho=mundo.ANCHO, alto=mundo.ALTO):
        self.ancho = ancho
        self.alto = alto
        self.obstaculos = set(mundo.OBSTACULOS if obstaculos is None else obstaculos)

        self.posicion = (0, 0)
        self.bateria = 100
        self.conocidos = set()      # obstáculos que ya descubrió
        self.orden_actual = None

        self.acciones = {
            "estado": self.estado,
            "ir_a": self.ir_a,
            "recargar": self.recargar,
        }

    def atender(self, orden):
        """Guarda la orden completa para que ir_a vea restricciones y plan B."""
        self.orden_actual = orden
        return super().atender(orden)

    # ==========================================
    # ACCIONES
    # ==========================================

    def estado(self, datos):
        return {
            "posicion": list(self.posicion),
            "bateria": self.bateria,
            "obstaculos_conocidos": sorted([list(c) for c in self.conocidos]),
            "mapa": [self.ancho, self.alto],
        }

    def recargar(self, datos):
        self.bateria = 100
        return {"bateria": self.bateria}

    def ir_a(self, datos):
        destino = self._destino(datos)

        orden = self.orden_actual or {}
        restricciones = orden.get("restricciones") or {}
        minima = restricciones.get("bateria_minima", BATERIA_MINIMA)
        plan_b = orden.get("si_falla") or "buscar otra ruta"

        decisiones = []
        recorrido = []
        motivo = None

        for _ in range(MAX_INTENTOS):

            if self.posicion == destino:
                break

            camino = mundo.ruta(self.posicion, destino, self.conocidos, self.ancho, self.alto)

            if camino is None:
                motivo = "sin_camino"
                decisiones.append(f"no encontré ningún camino libre; me quedé en {self._texto(self.posicion)}")
                break

            if not decisiones:
                decisiones.append(f"planeé una ruta de {len(camino)} casillas")

            siguiente = camino[0]

            # El "sensor": la casilla de enfrente tiene un obstáculo que no conocía.
            if siguiente in self.obstaculos:
                self.conocidos.add(siguiente)

                if plan_b == "detenerse":
                    motivo = "obstaculo"
                    decisiones.append(f"encontré un obstáculo en {self._texto(siguiente)}; me detuve como pide la orden")
                    break

                decisiones.append(f"encontré un obstáculo en {self._texto(siguiente)}; recalculé la ruta")
                continue

            # Freno de seguridad: no se puede desactivar desde la orden.
            if self.bateria - COSTO_POR_CASILLA < minima:
                motivo = "bateria"
                decisiones.append(
                    f"me detuve en {self._texto(self.posicion)} para no bajar de {minima} % de batería"
                )
                break

            self.posicion = siguiente
            self.bateria -= COSTO_POR_CASILLA
            recorrido.append(list(siguiente))

        llego = self.posicion == destino
        if llego and not decisiones:
            decisiones.append("ya estaba ahí")

        return {
            "llego": llego,
            "motivo": None if llego else motivo,
            "posicion": list(self.posicion),
            "destino": list(destino),
            "casillas": len(recorrido),
            "recorrido": recorrido,
            "bateria": self.bateria,
            "decisiones": decisiones,
            "objetivo": orden.get("objetivo"),
        }

    # ==========================================
    # AYUDANTES
    # ==========================================

    def _destino(self, datos):
        x, y = datos.get("x"), datos.get("y")

        if not isinstance(x, int) or not isinstance(y, int) or isinstance(x, bool) or isinstance(y, bool):
            raise Rechazo("necesito 'x' y 'y' como números enteros")

        if not mundo.dentro((x, y), self.ancho, self.alto):
            raise Rechazo(
                f"({x}, {y}) está fuera del mapa (va de 0 a {self.ancho - 1} y de 0 a {self.alto - 1})"
            )

        return (x, y)

    @staticmethod
    def _texto(casilla):
        return f"({casilla[0]}, {casilla[1]})"