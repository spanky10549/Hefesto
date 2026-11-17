"""
El dispositivo local: los sensores REALES de la máquina donde corre FOCUS.

Al arrancar detecta qué sensores existen y los pone en uno de tres estados:

    activo        existe y está autorizado          → ÉTER lo lee
    desactivado   no existe o no se puede leer      → dice por qué
    pendiente     se detectó, falta autorización    → avisa y espera

Reglas de autorización:
    - La PRIMERA vez, lo que ya existe se autoriza solo... menos lo
      sensible (micrófono, cámara), que siempre pide permiso.
    - Lo que aparece DESPUÉS (instalaste algo, conectaste un sensor)
      queda pendiente hasta que lo autorices.
    - Si algo autorizado se pierde y regresa (el WiFi), vuelve solo.

Los estados se guardan en sensores_locales.json para recordarlos
entre sesiones.

Acciones:
    leer        {}             lecturas de los sensores activos
    sensores    {}             todos, con su estado y el motivo
    detectar    {}             vuelve a revisar; dice qué cambió
    autorizar   {"sensor"}
    desactivar  {"sensor"}     lo apaga aunque exista

Eventos:
    sensor_detectado  apareció uno nuevo y espera autorización
    sensor_perdido    uno activo dejó de funcionar
"""

import os
import platform

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, crear_evento
from memoria.almacenamiento import cargar_json, guardar_json

from dispositivos.sensores_locales import SENSORES


ARCHIVO_ESTADOS = "sensores_locales.json"

ACTIVO = "activo"
DESACTIVADO = "desactivado"
PENDIENTE = "pendiente"


class DispositivoLocal(Inteligencia):

    nombre = "dispositivo_local"

    def __init__(self, sensores=None, ruta_estados=None, lugar=None):
        self.sensores = {s.id: s for s in (SENSORES if sensores is None else sensores)}
        self.ruta = ruta_estados or ARCHIVO_ESTADOS
        self.lugar = lugar or platform.node() or "esta computadora"
        self.descripcion = f"Sensores reales de {self.lugar}."

        primera_vez = not os.path.exists(self.ruta)
        guardado = {} if primera_vez else cargar_json(self.ruta, {})

        # {id: {"autorizado": bool, "disponible": bool, "motivo": str}}
        self.estados = {}
        for sensor_id, sensor in self.sensores.items():
            disponible, motivo = self._detectar(sensor)
            if sensor_id in guardado:
                autorizado = guardado[sensor_id].get("autorizado", False)
            else:
                autorizado = primera_vez and disponible and not sensor.sensible
            self.estados[sensor_id] = {"autorizado": autorizado, "disponible": disponible, "motivo": motivo}

        self._guardar()

        self.acciones = {
            "leer": self.leer,
            "sensores": self.listar,
            "detectar": self.detectar,
            "autorizar": self.autorizar,
            "desactivar": self.desactivar,
        }

    # ==========================================
    # ESTADOS
    # ==========================================

    @staticmethod
    def _detectar(sensor):
        try:
            return sensor.detectar()
        except Exception as error:
            return False, f"falló al detectarlo ({type(error).__name__})"

    def estado(self, sensor_id):
        e = self.estados[sensor_id]
        if not e["disponible"]:
            return DESACTIVADO
        return ACTIVO if e["autorizado"] else PENDIENTE

    def _guardar(self):
        guardar_json(self.ruta, {
            sensor_id: {"autorizado": e["autorizado"]} for sensor_id, e in self.estados.items()
        })

    def _ficha(self, sensor_id):
        sensor = self.sensores[sensor_id]
        estado = self.estado(sensor_id)
        return {
            "sensor": sensor_id,
            "tipo": sensor.tipo,
            "descripcion": sensor.descripcion,
            "estado": estado,
            "motivo": self.estados[sensor_id]["motivo"] if estado == DESACTIVADO else None,
            "sensible": sensor.sensible,
        }

    def _avisar(self, evento, sensor_id):
        if self.gaia is not None:
            self.gaia.publicar(crear_evento(self.nombre, evento, self._ficha(sensor_id)))

    # ==========================================
    # ACCIONES
    # ==========================================

    def listar(self, datos):
        return {"lugar": self.lugar, "sensores": [self._ficha(s) for s in self.sensores]}

    def detectar(self, datos):
        """Vuelve a revisar cada sensor y avisa de lo que cambió."""
        cambios = []

        for sensor_id, sensor in self.sensores.items():
            antes = self.estado(sensor_id)
            disponible, motivo = self._detectar(sensor)
            self.estados[sensor_id].update(disponible=disponible, motivo=motivo)
            ahora = self.estado(sensor_id)

            if antes == ahora:
                continue

            cambios.append({"sensor": sensor_id, "antes": antes, "ahora": ahora})
            if ahora == PENDIENTE:
                self._avisar("sensor_detectado", sensor_id)
            elif antes == ACTIVO and ahora == DESACTIVADO:
                self._avisar("sensor_perdido", sensor_id)

        return {"cambios": cambios, "sensores": self.listar({})["sensores"]}

    def leer(self, datos):
        """Lee los sensores activos. Antes revisa si apareció o se perdió alguno."""
        self.detectar({})

        lecturas = []
        for sensor_id, sensor in self.sensores.items():
            if self.estado(sensor_id) != ACTIVO:
                continue
            try:
                valor = sensor.leer()
            except Exception as error:
                self.estados[sensor_id].update(disponible=False, motivo=f"falló al leer ({type(error).__name__})")
                self._avisar("sensor_perdido", sensor_id)
                continue
            if valor is None:
                continue

            lectura = {"sensor": sensor_id, "tipo": sensor.tipo, "lugar": self.lugar, "valor": valor}
            if sensor.propios:
                lectura.update(sensor.propios)
            lecturas.append(lectura)

        return {"lecturas": lecturas}

    def _sensor(self, datos):
        sensor_id = datos.get("sensor")
        if sensor_id not in self.sensores:
            raise Rechazo(f"no tengo el sensor '{sensor_id}'; tengo: {', '.join(self.sensores)}")
        return sensor_id

    def autorizar(self, datos):
        sensor_id = self._sensor(datos)

        if not self.estados[sensor_id]["disponible"]:
            raise Rechazo(f"'{sensor_id}' no está disponible: {self.estados[sensor_id]['motivo']}")

        self.estados[sensor_id]["autorizado"] = True
        self._guardar()
        return self._ficha(sensor_id)

    def desactivar(self, datos):
        sensor_id = self._sensor(datos)
        self.estados[sensor_id]["autorizado"] = False
        self._guardar()
        return self._ficha(sensor_id)