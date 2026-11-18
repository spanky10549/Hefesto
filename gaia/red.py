"""
GAIA — Red.

Hasta ahora todas las inteligencias vivían dentro del mismo programa.
Aquí GAIA aprende a hablar con inteligencias que corren en OTRO programa
(o en otra máquina, como el rover en una Raspberry Pi o un ESP32).

Cómo viaja un mensaje (protocolo):
    - Se abre una conexión TCP con la otra máquina (host + puerto).
    - Se manda el mensaje como UNA línea de JSON, firmado por POSEIDON.
    - Se recibe la respuesta, también una línea de JSON firmada.
    - Se cierra la conexión.

InteligenciaRemota es un "representante": para GAIA es una inteligencia
más (tiene nombre, acciones y atiende órdenes), pero en vez de hacer el
trabajo, lo manda por la red y espera la respuesta. Por eso GAIA, TABRIS,
HADES y MINERVA funcionan con ella sin cambiar nada.
"""

import json
import socket

from gaia.inteligencia import Inteligencia
from gaia.mensajes import (
    OK, RECHAZADO, Rechazo, MensajeInvalido,
    crear_orden, crear_evento, validar,
)
from poseidon.guardia import MensajeSospechoso


TIEMPO_ESPERA = 10      # segundos máximos para conectar y recibir respuesta
MAX_BYTES = 1_000_000   # un mensaje más grande que esto se rechaza


class ErrorDeRed(ConnectionError):
    """No se pudo hablar con la otra máquina."""


def mandar_linea(host, puerto, mensaje, tiempo_espera=TIEMPO_ESPERA):
    """Manda un diccionario como línea de JSON y devuelve el diccionario que contesten."""
    datos = (json.dumps(mensaje, ensure_ascii=False) + "\n").encode("utf-8")

    try:
        with socket.create_connection((host, puerto), timeout=tiempo_espera) as conexion:
            conexion.sendall(datos)
            # makefile permite leer "hasta el salto de línea" como si fuera un archivo
            with conexion.makefile("rb") as entrada:
                linea = entrada.readline(MAX_BYTES)
    except OSError as error:   # conexión rechazada, tiempo agotado, red caída...
        raise ErrorDeRed(f"no pude hablar con {host}:{puerto} ({error})") from error

    if not linea:
        raise ErrorDeRed(f"{host}:{puerto} cerró la conexión sin responder")

    try:
        return json.loads(linea.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ErrorDeRed(f"{host}:{puerto} respondió algo que no es JSON") from error


class InteligenciaRemota(Inteligencia):

    def __init__(self, nombre, host, puerto, guardia, tiempo_espera=TIEMPO_ESPERA):
        self.nombre = nombre
        self.descripcion = f"(remota en {host}:{puerto})"
        self.host = host
        self.puerto = puerto
        self.guardia = guardia
        self.tiempo_espera = tiempo_espera
        self.acciones = {}      # se llenan al conectar con lo que diga la otra máquina

    # ==========================================
    # HABLAR POR LA RED
    # ==========================================

    def _revisar_privacidad(self, orden):
        """
        Antes de que algo salga por la red, DEMETER revisa que no lleve
        archivos protegidos. Si DEMETER existe pero no pudo revisar, no
        sale nada: en privacidad, ante la duda, mejor no compartir.
        """
        if self.gaia is None or "demeter" not in self.gaia.inteligencias:
            return

        r = self.gaia.pedir("gaia", "demeter", "revisar_salida", destino=self.nombre, mensaje=orden)

        if r["estado"] != OK:
            raise Rechazo(f"DEMETER no pudo revisar el mensaje ({r.get('detalle')}); no lo mandé")

        if not r["datos"]["puede_salir"]:
            zonas = ", ".join(sorted({b["zona"] for b in r["datos"]["bloqueos"]}))
            raise Rechazo(
                f"DEMETER no dejó que salga hacia {self.nombre}: lleva archivos de una zona protegida ({zonas})"
            )

    def _intercambiar(self, orden):
        """Manda una orden firmada y devuelve la respuesta ya revisada."""
        if orden["accion"] != "presentarse":
            self._revisar_privacidad(orden)

        respuesta = mandar_linea(self.host, self.puerto, self.guardia.sellar(orden), self.tiempo_espera)

        try:
            respuesta = validar(self.guardia.revisar(respuesta))
        except (MensajeSospechoso, MensajeInvalido) as error:
            if self.gaia is not None:
                self.gaia.publicar(crear_evento("poseidon", "mensaje_sospechoso", {
                    "origen": f"{self.host}:{self.puerto}",
                    "motivo": str(error),
                }))
            raise ErrorDeRed(f"respuesta sospechosa de {self.nombre}: {error}") from error

        if respuesta.get("responde_a") != orden["id"]:
            raise ErrorDeRed(f"{self.nombre} respondió a otra orden")

        return respuesta

    def conectar(self):
        """
        Saluda a la otra máquina y le pregunta quién es y qué sabe hacer.
        Devuelve True si contestó bien.
        """
        orden = crear_orden("gaia", self.nombre, "presentarse")

        try:
            respuesta = self._intercambiar(orden)
        except ErrorDeRed:
            return False

        if respuesta["estado"] != OK:
            return False

        ficha = respuesta["datos"]
        self.descripcion = f"{ficha.get('descripcion', '')} (remota en {self.host}:{self.puerto})"
        self.acciones = {accion: None for accion in ficha.get("acciones", [])}
        return True

    # ==========================================
    # COMO CUALQUIER INTELIGENCIA
    # ==========================================

    def atender(self, orden):
        """Manda la orden completa (con objetivo, restricciones y plan B)."""
        respuesta = self._intercambiar(orden)

        if respuesta["estado"] == OK:
            return respuesta["datos"]
        if respuesta["estado"] == RECHAZADO:
            raise Rechazo(respuesta.get("detalle") or "rechazado")

        # Error o desconocido del otro lado: para GAIA es un fallo.
        raise ErrorDeRed(f"{self.nombre}: {respuesta.get('detalle')}")

    def reiniciar(self):
        """HADES la usa para recuperarla: volver a saludar."""
        return self.conectar()