"""
ÉTER — Percepción del entorno (v1).

Los dispositivos MIDEN; ÉTER ENTIENDE y RECUERDA el entorno.

    - Recibe lecturas de cualquier dispositivo: le pregunta a GAIA quién
      sabe hacer "leer" y les pide sus lecturas a todos. Hoy contesta la
      estación simulada; mañana el ESP32 o tu dispositivo con cámara.
    - Interpreta cada lectura (31 °C en el cuarto → "calor").
    - Detecta condiciones anormales (muy alto, cambio brusco, un sensor
      que dejó de mandar datos) y avisa con el evento "anomalia_entorno".
    - Guarda un mapa compartido: lo que descubre un robot lo sabe el
      siguiente (o el mismo, aunque lo reinicien).

Acciones:
    actualizar           {}                          pide lecturas a quien sepa "leer"
    lectura              {"sensor","tipo","lugar","valor", "rangos"?, "limites"?}
    entorno              {"lugar"?}                  lo último de cada sensor
    anomalias            {}                          lo raro ahorita
    reportar_obstaculos  {"obstaculos": [[x, y]], "origen"}
    mapa                 {}                          obstáculos conocidos
                                                     (se guardan en eter_mapa.json)
"""

import os
from datetime import datetime

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, OK, crear_evento

from eter.interpretacion import ficha, etiqueta, anormalidades
from memoria.almacenamiento import cargar_json, guardar_json


# El mapa compartido se guarda aquí para que sobreviva aunque se apague todo.
ARCHIVO_MAPA = "eter_mapa.json"


# Si un sensor no manda nada en este tiempo, algo le pasó.
SILENCIO_SEGUNDOS = 300


class Eter(Inteligencia):

    nombre = "eter"
    descripcion = "Percibe el entorno: interpreta sensores, detecta lo anormal y guarda el mapa compartido."

    def __init__(self, ahora=None, ruta_mapa=None):
        self.ahora = ahora or datetime.now
        self.sensores = {}        # {id: {"tipo", "lugar", "valor", "fecha", "propios", "raro"}}
        self.ruta_mapa = ruta_mapa or ARCHIVO_MAPA
        self.obstaculos = self._cargar_mapa()   # {(x, y): {"origen", "fecha"}}

        self.acciones = {
            "actualizar": self.actualizar,
            "lectura": self.lectura,
            "entorno": self.entorno,
            "anomalias": self.anomalias,
            "reportar_obstaculos": self.reportar_obstaculos,
            "mapa": self.mapa,
        }

    # ==========================================
    # LECTURAS
    # ==========================================

    def actualizar(self, datos):
        """Le pide sus lecturas a todos los dispositivos que sepan 'leer'."""
        dispositivos = [n for n in self.gaia.quien_sabe("leer") if not self.gaia.esta_aislada(n)]
        recibidas, fallaron = 0, []

        for dispositivo in dispositivos:
            respuesta = self.gaia.pedir(self.nombre, dispositivo, "leer")

            if respuesta["estado"] != OK:
                fallaron.append(dispositivo)
                continue

            for lectura in respuesta["datos"].get("lecturas", []):
                try:
                    self.lectura(lectura)
                    recibidas += 1
                except Rechazo:
                    pass   # una lectura mal hecha no detiene a las demás

        return {"dispositivos": dispositivos, "lecturas": recibidas, "fallaron": fallaron}

    def lectura(self, datos):
        """Una lectura nueva. Si el sensor no se conocía, se registra solo."""
        sensor = datos.get("sensor")
        valor = datos.get("valor")

        if not isinstance(sensor, str) or not sensor:
            raise Rechazo("falta 'sensor'")
        if valor is None:
            raise Rechazo("falta 'valor'")

        anterior = self.sensores.get(sensor, {})
        tipo = datos.get("tipo") or anterior.get("tipo") or "desconocido"
        propios = {
            campo: datos[campo] for campo in ("rangos", "limites", "cambio_brusco") if campo in datos
        } or anterior.get("propios")

        raro = anormalidades(tipo, valor, anterior.get("valor"), propios)

        self.sensores[sensor] = {
            "tipo": tipo,
            "lugar": datos.get("lugar") or anterior.get("lugar") or "sin lugar",
            "valor": valor,
            "fecha": self.ahora(),
            "propios": propios,
            "raro": raro,
        }

        # Avisar solo lo que no se había avisado ya
        nuevo = [r for r in raro if r not in anterior.get("raro", [])]
        if nuevo and self.gaia is not None:
            self.gaia.publicar(crear_evento(self.nombre, "anomalia_entorno", {
                "sensor": sensor, "tipo": tipo, "valor": valor, "motivos": nuevo,
            }))

        return self._describir(sensor)

    # ==========================================
    # CONSULTAS
    # ==========================================

    def _describir(self, sensor):
        s = self.sensores[sensor]
        edad = (self.ahora() - s["fecha"]).total_seconds()
        raro = list(s["raro"])
        if edad > SILENCIO_SEGUNDOS:
            raro.append("sin datos recientes")

        return {
            "sensor": sensor,
            "tipo": s["tipo"],
            "lugar": s["lugar"],
            "valor": s["valor"],
            "unidad": ficha(s["tipo"], s["propios"])["unidad"],
            "etiqueta": etiqueta(s["tipo"], s["valor"], s["propios"]),
            "hace_segundos": round(edad),
            "raro": raro,
        }

    def entorno(self, datos):
        lugar = datos.get("lugar")
        sensores = [
            self._describir(sensor) for sensor in sorted(self.sensores)
            if not lugar or self.sensores[sensor]["lugar"] == lugar
        ]
        return {"sensores": sensores}

    def anomalias(self, datos):
        return {"anomalias": [s for s in self.entorno({})["sensores"] if s["raro"]]}

    # ==========================================
    # MAPA COMPARTIDO
    # ==========================================

    def _cargar_mapa(self):
        """
        JSON no tiene tuplas ni acepta listas como llaves, así que en el
        archivo cada obstáculo se guarda como {"casilla": [x, y], ...}.
        """
        if not os.path.exists(self.ruta_mapa):
            return {}

        guardado = cargar_json(self.ruta_mapa, {"obstaculos": []})
        return {
            tuple(o["casilla"]): {"origen": o.get("origen"), "fecha": o.get("fecha")}
            for o in guardado.get("obstaculos", [])
        }

    def _guardar_mapa(self):
        guardar_json(self.ruta_mapa, self.mapa({}))

    def reportar_obstaculos(self, datos):
        obstaculos = datos.get("obstaculos")
        if not isinstance(obstaculos, list):
            raise Rechazo("'obstaculos' debe ser una lista de [x, y]")

        nuevos = 0
        for casilla in obstaculos:
            if (not isinstance(casilla, list) or len(casilla) != 2
                    or not all(isinstance(n, int) and not isinstance(n, bool) for n in casilla)):
                raise Rechazo(f"casilla inválida: {casilla}")

            clave = tuple(casilla)
            if clave not in self.obstaculos:
                self.obstaculos[clave] = {
                    "origen": datos.get("origen", "desconocido"),
                    "fecha": self.ahora().isoformat(timespec="seconds"),
                }
                nuevos += 1

        if nuevos:
            self._guardar_mapa()

        return {"nuevos": nuevos, "total": len(self.obstaculos)}

    def mapa(self, datos):
        return {
            "obstaculos": [
                {"casilla": list(casilla), **info}
                for casilla, info in sorted(self.obstaculos.items())
            ]
        }