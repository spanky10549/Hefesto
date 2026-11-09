"""
GAIA — Núcleo de coordinación.

GAIA no sabe definir palabras ni calcular: sabe QUIÉN puede hacerlo
y le entrega el mensaje. Así ninguna inteligencia depende de otra
directamente, y agregar una nueva no obliga a tocar las demás.

    gaia = Gaia()
    gaia.registrar(Apollo())

    respuesta = gaia.pedir("hefesto", "apollo", "definir", concepto="ave")
    respuesta["estado"]   → "ok"
    respuesta["datos"]    → lo que devolvió APOLLO

Además:
    - Nunca se cae por culpa de otra: si una inteligencia truena,
      responde ERROR y avisa con el evento "fallo" (semilla de HADES).
    - Guarda un historial de todo lo que pasa (semilla de TABRIS).
    - Cada mensaje se pasa por JSON, igual que si viajara por la red.
      Si algo no se puede mandar por WiFi, se nota desde ahora.
"""

from collections import deque

from gaia.mensajes import (
    ORDEN, OK, RECHAZADO, ERROR, DESCONOCIDO,
    Rechazo, MensajeInvalido,
    crear_orden, crear_respuesta, crear_evento,
    validar, a_json, de_json,
)


MAX_HISTORIAL = 500


class Gaia:

    nombre = "gaia"

    def __init__(self, max_historial=MAX_HISTORIAL):
        self.inteligencias = {}
        self.suscripciones = {}          # {nombre del evento: [funciones]}
        self.historial = deque(maxlen=max_historial)

    # ==========================================
    # DIRECTORIO
    # ==========================================

    def registrar(self, inteligencia):
        """Conecta una inteligencia al ecosistema."""
        nombre = inteligencia.nombre

        if not nombre:
            raise ValueError("la inteligencia necesita un nombre")
        if nombre in self.inteligencias or nombre == self.nombre:
            raise ValueError(f"ya hay una inteligencia llamada '{nombre}'")

        inteligencia.gaia = self
        self.inteligencias[nombre] = inteligencia

        self.publicar(crear_evento(self.nombre, "registro", inteligencia.presentarse()))

    def retirar(self, nombre):
        """Desconecta una inteligencia (por ejemplo, un robot que se apagó)."""
        inteligencia = self.inteligencias.pop(nombre, None)
        if inteligencia is not None:
            inteligencia.gaia = None
            self.publicar(crear_evento(self.nombre, "retiro", {"nombre": nombre}))

    def directorio(self):
        """Quién está conectado y qué sabe hacer cada quien."""
        return {
            nombre: inteligencia.presentarse()
            for nombre, inteligencia in sorted(self.inteligencias.items())
        }

    def quien_sabe(self, accion):
        """Las inteligencias que saben hacer una acción."""
        return sorted(
            nombre for nombre, inteligencia in self.inteligencias.items()
            if inteligencia.sabe(accion)
        )

    # ==========================================
    # ÓRDENES Y RESPUESTAS
    # ==========================================

    def enviar(self, orden):
        """
        Entrega una orden y devuelve la respuesta. Nunca lanza excepciones
        por culpa de la inteligencia: todo sale como estado de la respuesta.
        """
        # Como si viajara por la red: si no se puede convertir a JSON, no sale.
        orden = de_json(a_json(validar(orden)))

        if orden["tipo"] != ORDEN:
            raise MensajeInvalido("enviar() solo acepta órdenes; los eventos van con publicar()")

        self._anotar(orden)

        inteligencia = self.inteligencias.get(orden["para"])

        if inteligencia is None:
            respuesta = crear_respuesta(
                orden, DESCONOCIDO,
                detalle=f"no conozco a ninguna inteligencia llamada '{orden['para']}'"
            )

        elif not inteligencia.sabe(orden["accion"]):
            respuesta = crear_respuesta(
                orden, DESCONOCIDO,
                detalle=f"{orden['para']} no sabe hacer '{orden['accion']}'"
            )

        else:
            respuesta = self._ejecutar(inteligencia, orden)

        self._anotar(respuesta)
        return respuesta

    def pedir(self, de, para, accion, **datos):
        """
        Atajo para lo más común:
            gaia.pedir("hefesto", "apollo", "definir", concepto="ave")
        """
        return self.enviar(crear_orden(de, para, accion, datos))

    def _ejecutar(self, inteligencia, orden):
        try:
            datos = inteligencia.atender(orden)
            if datos is None:
                datos = {}
            if not isinstance(datos, dict):
                raise TypeError(f"{inteligencia.nombre} debe devolver un diccionario")

            respuesta = crear_respuesta(orden, OK, datos)
            a_json(respuesta)   # que también la respuesta pueda viajar por la red
            return respuesta

        except Rechazo as rechazo:
            return crear_respuesta(orden, RECHAZADO, detalle=str(rechazo))

        except Exception as error:
            detalle = f"{type(error).__name__}: {error}"

            # Semilla de HADES: aislar el fallo y avisar, sin caerse.
            self.publicar(crear_evento(self.nombre, "fallo", {
                "inteligencia": inteligencia.nombre,
                "accion": orden["accion"],
                "orden": orden["id"],
                "detalle": detalle,
            }))

            return crear_respuesta(orden, ERROR, detalle=detalle)

    # ==========================================
    # EVENTOS
    # ==========================================

    def suscribir(self, evento, funcion):
        """
        Llama a 'funcion(mensaje)' cada vez que pase ese evento.
        Con "*" escucha todos.
        """
        self.suscripciones.setdefault(evento, []).append(funcion)

    def publicar(self, evento):
        """Avisa a todos los interesados. Si uno truena, los demás siguen."""
        evento = de_json(a_json(validar(evento)))
        self._anotar(evento)

        interesados = (
            self.suscripciones.get(evento["accion"], [])
            + self.suscripciones.get("*", [])
        )

        for funcion in interesados:
            try:
                funcion(evento)
            except Exception:
                # Un oyente roto no debe tumbar a GAIA. (HADES lo atenderá.)
                pass

    # ==========================================
    # HISTORIAL (semilla de TABRIS)
    # ==========================================

    def _anotar(self, mensaje):
        self.historial.append(mensaje)

    def ultimos(self, cantidad=10, tipo=None):
        """Los últimos mensajes, opcionalmente de un tipo."""
        mensajes = [m for m in self.historial if tipo is None or m["tipo"] == tipo]
        return mensajes[-cantidad:]
