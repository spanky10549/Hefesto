"""
ROVER — Servidor.

El programa que corre "dentro" del robot. Espera órdenes por la red,
deja que POSEIDON las revise, se las pasa a la mini IA y contesta.

Para encenderlo, en otra terminal (con el .venv activo):

    python -m rover.servidor

Se apaga con Ctrl + C.

Si la orden no tiene una firma válida (alguien sin la clave), el rover
NO la ejecuta: la rechaza y lo anota en pantalla.
"""

import json
import socketserver
import threading

from gaia.mensajes import (
    OK, RECHAZADO, ERROR, DESCONOCIDO, ORDEN,
    Rechazo, MensajeInvalido, crear_respuesta, validar,
)
from poseidon.firma import cargar_clave
from poseidon.guardia import Guardia, MensajeSospechoso

from rover import HOST, PUERTO
from rover.robot import Rover


MAX_BYTES = 1_000_000


def procesar(robot, guardia, linea, mostrar=print):
    """
    Una línea recibida → la línea de respuesta (o None si no hay que contestar).
    Separado del servidor para poder probarlo sin red.
    """
    try:
        mensaje = json.loads(linea)
        orden = validar(guardia.revisar(mensaje))
    except (json.JSONDecodeError, UnicodeDecodeError, MensajeInvalido, MensajeSospechoso, TypeError) as error:
        mostrar(f"[POSEIDON] Mensaje rechazado: {error}")
        # Sin firma: el que mandó algo sospechoso no recibe nada útil.
        return json.dumps({"rechazado": True}) + "\n"

    if orden["tipo"] != ORDEN:
        mostrar("[POSEIDON] Mensaje rechazado: no es una orden")
        return json.dumps({"rechazado": True}) + "\n"

    mostrar(f"[{robot.nombre.upper()}] Orden de {orden['de']}: {orden['accion']} {orden['datos']}")

    if orden["accion"] == "presentarse":
        respuesta = crear_respuesta(orden, OK, robot.presentarse())

    elif not robot.sabe(orden["accion"]):
        respuesta = crear_respuesta(orden, DESCONOCIDO, detalle=f"no sé hacer '{orden['accion']}'")

    else:
        try:
            datos = robot.atender(orden) or {}
            respuesta = crear_respuesta(orden, OK, datos)
            for decision in datos.get("decisiones", []):
                mostrar(f"    → {decision}")
        except Rechazo as rechazo:
            respuesta = crear_respuesta(orden, RECHAZADO, detalle=str(rechazo))
            mostrar(f"    → rechazada: {rechazo}")
        except Exception as error:
            respuesta = crear_respuesta(orden, ERROR, detalle=f"{type(error).__name__}: {error}")
            mostrar(f"    → ERROR: {error}")

    return json.dumps(guardia.sellar(respuesta), ensure_ascii=False) + "\n"


class Manejador(socketserver.StreamRequestHandler):
    """Atiende una conexión: lee una línea, contesta una línea."""

    def handle(self):
        linea = self.rfile.readline(MAX_BYTES)
        if not linea:
            return

        servidor = self.server
        # Un candado: dos órdenes a la vez no pueden mover el rover al mismo tiempo.
        with servidor.candado:
            respuesta = procesar(servidor.robot, servidor.guardia, linea.decode("utf-8", "replace"), servidor.mostrar)

        if respuesta:
            self.wfile.write(respuesta.encode("utf-8"))


class ServidorRover(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, robot, guardia, host=HOST, puerto=PUERTO, mostrar=print):
        self.robot = robot
        self.guardia = guardia
        self.mostrar = mostrar
        self.candado = threading.Lock()
        super().__init__((host, puerto), Manejador)

    @property
    def puerto(self):
        return self.server_address[1]


def main():
    robot = Rover()
    guardia = Guardia(cargar_clave())

    with ServidorRover(robot, guardia) as servidor:
        print(f"{robot.nombre.upper()} ENCENDIDO. Esperando órdenes en {HOST}:{servidor.puerto}")
        print(f"Estoy en {tuple(robot.posicion)} con {robot.bateria} % de batería. Ctrl + C para apagarme.")
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print(f"\n{robot.nombre.upper()} apagado.")


if __name__ == "__main__":
    main()