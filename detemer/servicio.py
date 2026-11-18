"""
DEMETER — Privacidad y permisos (v1).

Protege lo que vive en el dispositivo (fotos, videos, documentos) y
controla qué sale de él.

    ZONAS PROTEGIDAS  carpetas que nadie de FOCUS toca sin permiso.
                      La primera vez se protegen solas tus carpetas
                      personales (Imágenes, Videos, Documentos...).
                      La carpeta de FOCUS siempre es libre: son los
                      archivos de las propias inteligencias.

    SOLICITUDES       antes de tocar un archivo, la inteligencia pregunta:
                      ¿quién?, ¿qué archivo?, ¿para qué? (leer, escribir,
                      compartir). DEMETER responde:
                          permitir   hay una regla que lo permite (o no está protegido)
                          negar      hay una regla que lo prohíbe
                          preguntar  no hay regla: que decida la persona

    REGLAS            "siempre" o "nunca", por inteligencia, zona y
                      operación. Se guardan en demeter_permisos.json.

    LO QUE SALE       revisar_salida: si un mensaje que va por la red
                      menciona un archivo protegido, no sale sin permiso
                      de "compartir".

DEMETER solo DECIDE: nunca mueve, cambia ni borra archivos.

Acciones:
    solicitar       {"inteligencia", "ruta", "operacion"}
    revisar_salida  {"destino", "mensaje"}
    conceder        {"inteligencia", "zona", "operacion", "decision": "permitir"|"negar"}
    revocar         {"zona"}                      borra las reglas de esa zona
    zonas           {}
    proteger        {"ruta", "nombre"?}
    desproteger     {"nombre"}
    permisos        {}
"""

import os

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, crear_evento
from memoria.almacenamiento import cargar_json, guardar_json

from demeter.rutas import limpiar, esta_dentro, carpetas_personales


ARCHIVO_PERMISOS = "demeter_permisos.json"

PERMITIR = "permitir"
NEGAR = "negar"
PREGUNTAR = "preguntar"

OPERACIONES = ("leer", "escribir", "compartir")


class Demeter(Inteligencia):

    nombre = "demeter"
    descripcion = "Protege la privacidad: zonas protegidas, permisos de acceso y lo que se comparte."

    def __init__(self, ruta_permisos=None, carpeta_focus=None, zonas_iniciales=None):
        self.ruta = ruta_permisos or ARCHIVO_PERMISOS
        self.carpeta_focus = limpiar(carpeta_focus or os.getcwd())

        if os.path.exists(self.ruta):
            guardado = cargar_json(self.ruta, {})
            self.zonas = guardado.get("zonas", [])
            self.reglas = guardado.get("reglas", [])
        else:
            iniciales = carpetas_personales() if zonas_iniciales is None else zonas_iniciales
            self.zonas = [{"nombre": nombre, "ruta": ruta} for nombre, ruta in iniciales]
            self.reglas = []
            self._guardar()

        self.acciones = {
            "solicitar": self.solicitar,
            "revisar_salida": self.revisar_salida,
            "conceder": self.conceder,
            "revocar": self.revocar,
            "zonas": self.listar_zonas,
            "proteger": self.proteger,
            "desproteger": self.desproteger,
            "permisos": self.listar_permisos,
        }

    def _guardar(self):
        guardar_json(self.ruta, {"zonas": self.zonas, "reglas": self.reglas})

    # ==========================================
    # DECIDIR
    # ==========================================

    def zona_de(self, ruta):
        """La zona protegida donde está un archivo, o None. Gana la más específica."""
        if esta_dentro(ruta, self.carpeta_focus):
            return None

        dentro = [z for z in self.zonas if esta_dentro(ruta, z["ruta"])]
        if not dentro:
            return None
        return max(dentro, key=lambda z: len(limpiar(z["ruta"])))

    def decidir(self, inteligencia, ruta, operacion):
        """(decision, zona, motivo)"""
        zona = self.zona_de(ruta)

        if zona is None:
            if esta_dentro(ruta, self.carpeta_focus):
                return PERMITIR, None, "es un archivo de FOCUS"
            return PERMITIR, None, "no está en una zona protegida"

        for regla in self.reglas:
            if (regla["inteligencia"] == inteligencia and regla["zona"] == zona["nombre"]
                    and regla["operacion"] == operacion):
                motivo = "lo autorizaste" if regla["decision"] == PERMITIR else "lo prohibiste"
                return regla["decision"], zona["nombre"], motivo

        return PREGUNTAR, zona["nombre"], "está en una zona protegida y no hay una regla"

    def _operacion(self, datos):
        operacion = datos.get("operacion", "leer")
        if operacion not in OPERACIONES:
            raise Rechazo(f"operación desconocida: '{operacion}' (usa {', '.join(OPERACIONES)})")
        return operacion

    def _texto(self, datos, campo):
        valor = datos.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise Rechazo(f"falta '{campo}'")
        return valor.strip()

    def solicitar(self, datos):
        inteligencia = self._texto(datos, "inteligencia")
        ruta = self._texto(datos, "ruta")
        operacion = self._operacion(datos)

        decision, zona, motivo = self.decidir(inteligencia, ruta, operacion)

        if decision == NEGAR and self.gaia is not None:
            self.gaia.publicar(crear_evento(self.nombre, "acceso_negado", {
                "inteligencia": inteligencia, "zona": zona, "operacion": operacion,
            }))

        return {"decision": decision, "zona": zona, "motivo": motivo, "operacion": operacion}

    # ==========================================
    # LO QUE SALE POR LA RED
    # ==========================================

    @staticmethod
    def _textos(valor):
        """Todos los textos que hay dentro de un mensaje, aunque estén anidados."""
        if isinstance(valor, str):
            yield valor
        elif isinstance(valor, dict):
            for v in valor.values():
                yield from Demeter._textos(v)
        elif isinstance(valor, list):
            for v in valor:
                yield from Demeter._textos(v)

    def revisar_salida(self, datos):
        """
        ¿Puede salir este mensaje hacia 'destino'? Busca textos que sean
        rutas dentro de una zona protegida.
        """
        destino = self._texto(datos, "destino")
        mensaje = datos.get("mensaje", {})

        bloqueos = []
        for texto in self._textos(mensaje.get("datos", {}) if isinstance(mensaje, dict) else mensaje):
            if os.sep not in texto and "/" not in texto:
                continue   # no parece ruta
            decision, zona, _ = self.decidir(destino, texto, "compartir")
            if zona is not None and decision != PERMITIR:
                bloqueos.append({"ruta": texto, "zona": zona})

        if bloqueos and self.gaia is not None:
            self.gaia.publicar(crear_evento(self.nombre, "salida_bloqueada", {
                "destino": destino, "zonas": sorted({b["zona"] for b in bloqueos}),
            }))

        return {"puede_salir": not bloqueos, "bloqueos": bloqueos}

    # ==========================================
    # REGLAS
    # ==========================================

    def _zona_por_nombre(self, nombre):
        for zona in self.zonas:
            if zona["nombre"].lower() == str(nombre).lower():
                return zona
        raise Rechazo(f"no hay una zona llamada '{nombre}'")

    def conceder(self, datos):
        inteligencia = self._texto(datos, "inteligencia")
        zona = self._zona_por_nombre(self._texto(datos, "zona"))
        operacion = self._operacion(datos)
        decision = datos.get("decision")
        if decision not in (PERMITIR, NEGAR):
            raise Rechazo("'decision' debe ser 'permitir' o 'negar'")

        self.reglas = [
            r for r in self.reglas
            if not (r["inteligencia"] == inteligencia and r["zona"] == zona["nombre"]
                    and r["operacion"] == operacion)
        ]
        self.reglas.append({
            "inteligencia": inteligencia, "zona": zona["nombre"],
            "operacion": operacion, "decision": decision,
        })
        self._guardar()
        return {"regla": self.reglas[-1]}

    def revocar(self, datos):
        zona = self._zona_por_nombre(self._texto(datos, "zona"))
        antes = len(self.reglas)
        self.reglas = [r for r in self.reglas if r["zona"] != zona["nombre"]]
        self._guardar()
        return {"borradas": antes - len(self.reglas)}

    def listar_permisos(self, datos):
        return {"reglas": list(self.reglas)}

    # ==========================================
    # ZONAS
    # ==========================================

    def listar_zonas(self, datos):
        return {"zonas": list(self.zonas), "carpeta_focus": self.carpeta_focus}

    def proteger(self, datos):
        ruta = self._texto(datos, "ruta")
        if not os.path.isdir(os.path.expanduser(ruta)):
            raise Rechazo(f"no existe la carpeta '{ruta}'")
        if esta_dentro(ruta, self.carpeta_focus):
            raise Rechazo("la carpeta de FOCUS no se puede proteger: es donde trabajan las inteligencias")

        nombre = (datos.get("nombre") or os.path.basename(os.path.normpath(ruta))).strip()
        if any(z["nombre"].lower() == nombre.lower() for z in self.zonas):
            raise Rechazo(f"ya hay una zona llamada '{nombre}'")

        zona = {"nombre": nombre, "ruta": os.path.abspath(os.path.expanduser(ruta))}
        self.zonas.append(zona)
        self._guardar()
        return {"zona": zona}

    def desproteger(self, datos):
        zona = self._zona_por_nombre(self._texto(datos, "nombre"))
        self.zonas.remove(zona)
        self.reglas = [r for r in self.reglas if r["zona"] != zona["nombre"]]
        self._guardar()
        return {"zona": zona}