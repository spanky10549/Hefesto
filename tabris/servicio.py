"""
TABRIS — Supervisión y registro de eventos (v1).

Observa todo lo que pasa por GAIA y lo guarda. Según el plan de FOCUS,
TABRIS NO repara nada: identifica, documenta y le avisa a GAIA.

Lo que hace en esta versión:
    - Guarda cada orden, respuesta y evento en un archivo (.jsonl).
    - Responde preguntas sobre lo que pasó: resumen y búsqueda.
    - Detecta una anomalía sencilla: si una inteligencia falla varias
      veces seguidas, publica el evento "anomalia" para que GAIA
      (y más adelante HADES) se entere.

Acciones:
    resumen  {"dia"?: "hoy" | "2026-11-09"}
        → cuántos mensajes, errores y rechazos hubo, por inteligencia
    buscar   {"inteligencia"?, "accion"?, "estado"?, "tipo"?, "cantidad"?}
        → los últimos mensajes que coincidan
"""

from datetime import date

from gaia.inteligencia import Inteligencia
from gaia.mensajes import RESPUESTA, ORDEN, EVENTO, ERROR, RECHAZADO, crear_evento

from tabris.registro import Registro


ARCHIVO_REGISTRO = "tabris_registro.jsonl"

# Cuántos errores seguidos de la misma inteligencia cuentan como anomalía.
LIMITE_ERRORES_SEGUIDOS = 3

MAX_RESULTADOS = 100


class Tabris(Inteligencia):

    nombre = "tabris"
    descripcion = "Supervisa el ecosistema: registra todo y detecta fallos repetidos."

    def __init__(self, ruta=None):
        # Se lee ARCHIVO_REGISTRO aquí y no en la firma para que las
        # pruebas puedan cambiarlo por un archivo temporal.
        self.registro = Registro(ruta or ARCHIVO_REGISTRO)
        self.errores_seguidos = {}      # {inteligencia: cuántos errores van}

        self.acciones = {
            "resumen": self.resumen,
            "buscar": self.buscar,
        }

    # ==========================================
    # OBSERVAR
    # ==========================================

    def al_conectarse(self):
        """En cuanto GAIA la registra, empieza a ver todos los mensajes."""
        self.gaia.observar(self.observar)

    def observar(self, mensaje):
        self.registro.anotar(mensaje)

        if mensaje["tipo"] == RESPUESTA:
            self._revisar_respuesta(mensaje)

        # Si la liberaron, empieza de cero: que pueda volver a avisar.
        elif mensaje["tipo"] == EVENTO and mensaje["accion"] == "liberacion":
            self.errores_seguidos[mensaje["datos"]["inteligencia"]] = 0

    def _revisar_respuesta(self, respuesta):
        """Cuenta errores seguidos; al llegar al límite, avisa una vez."""
        quien = respuesta["de"]

        if respuesta["estado"] != ERROR:
            self.errores_seguidos[quien] = 0
            return

        self.errores_seguidos[quien] = self.errores_seguidos.get(quien, 0) + 1

        if self.errores_seguidos[quien] == LIMITE_ERRORES_SEGUIDOS:
            self.gaia.publicar(crear_evento(self.nombre, "anomalia", {
                "inteligencia": quien,
                "errores_seguidos": LIMITE_ERRORES_SEGUIDOS,
                "ultimo_detalle": respuesta.get("detalle"),
            }))

    # ==========================================
    # RESPONDER PREGUNTAS
    # ==========================================

    def resumen(self, datos):
        dia = datos.get("dia")
        if dia == "hoy":
            dia = date.today().isoformat()

        resumen = {
            "dia": dia,
            "mensajes": 0,
            "ordenes": 0,
            "errores": 0,
            "rechazos": 0,
            "por_inteligencia": {},    # {nombre: órdenes que recibió}
            "ultimo_error": None,
        }

        for mensaje in self.registro.leer():

            # "2026-11-09T22:30:00" empieza con "2026-11-09"
            if dia and not mensaje.get("fecha", "").startswith(dia):
                continue

            resumen["mensajes"] += 1

            if mensaje["tipo"] == ORDEN:
                resumen["ordenes"] += 1
                para = mensaje["para"]
                resumen["por_inteligencia"][para] = resumen["por_inteligencia"].get(para, 0) + 1

            elif mensaje["tipo"] == RESPUESTA:
                if mensaje.get("estado") == ERROR:
                    resumen["errores"] += 1
                    resumen["ultimo_error"] = {
                        "inteligencia": mensaje["de"],
                        "accion": mensaje["accion"],
                        "detalle": mensaje.get("detalle"),
                        "fecha": mensaje.get("fecha"),
                    }
                elif mensaje.get("estado") == RECHAZADO:
                    resumen["rechazos"] += 1

        return resumen

    def buscar(self, datos):
        inteligencia = datos.get("inteligencia")
        accion = datos.get("accion")
        estado = datos.get("estado")
        tipo = datos.get("tipo")

        cantidad = datos.get("cantidad", 10)
        if not isinstance(cantidad, int) or cantidad < 1:
            cantidad = 10
        cantidad = min(cantidad, MAX_RESULTADOS)

        def coincide(mensaje):
            if inteligencia and inteligencia not in (mensaje["de"], mensaje["para"]):
                return False
            if accion and mensaje["accion"] != accion:
                return False
            if estado and mensaje.get("estado") != estado:
                return False
            if tipo and mensaje["tipo"] != tipo:
                return False
            return True

        mensajes = self.registro.buscar(coincide, cantidad)
        return {"mensajes": mensajes, "cantidad": len(mensajes)}