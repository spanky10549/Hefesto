"""
MINERVA — Rutinas.

Tareas que la persona le enseña a MINERVA con sus propias palabras:

    enseña la rutina "checa todo": revisa los recursos, revisa los errores y revisa el entorno

Después basta con decir "checa todo". Así MINERVA aprende tareas nuevas
sin tocar el código, igual que HEFESTO aprende conceptos.

Reglas:
    - Cada paso tiene que entenderse (o ser otra rutina que ya existe).
    - Una rutina puede usar otras, pero sin círculos: si "A" usa "B",
      "B" no puede usar "A" (se repetirían para siempre).
    - El nombre no puede ser algo que MINERVA ya entiende ("revisa los
      recursos"), porque la rutina lo taparía.

Se guardan en minerva_rutinas.json.
"""

import os
from datetime import datetime

from memoria.almacenamiento import cargar_json, guardar_json

from minerva.planeador import dividir_tarea, interpretar, nombre_de_rutina, procesar
from minerva.condiciones import partir_plan_b, es_plan_b, es_detenerse, separar_condicion


ARCHIVO_RUTINAS = "minerva_rutinas.json"


def acciones_de(pasos, nombres=()):
    """
    Lo que cada paso manda a hacer, sin su condición ni su "si falla":
        ["si hay errores revisa los incidentes", "define X y si falla calcula Y"]
        → ["revisa los incidentes", "define X", "calcula Y"]
    """
    acciones = []
    for paso in pasos:
        for parte in partir_plan_b(paso):
            alternativa = es_plan_b(parte)
            resto = alternativa if alternativa is not None else separar_condicion(parte, nombres)[1]
            if resto.strip() and not es_detenerse(resto):
                acciones.append(resto)
    return acciones


class ErrorRutina(Exception):
    """La rutina no se puede guardar; el texto dice por qué."""


class Rutinas:

    def __init__(self, ruta=None, ahora=None):
        self.ruta = ruta or ARCHIVO_RUTINAS
        self.ahora = ahora or datetime.now
        self.rutinas = cargar_json(self.ruta, {}) if os.path.exists(self.ruta) else {}

    def _guardar(self):
        guardar_json(self.ruta, self.rutinas)

    def _nombres(self):
        return [r["nombre"] for r in self.rutinas.values()]

    def todas(self):
        """{nombre para comparar: {"nombre", "pasos", "creada"}}"""
        return self.rutinas

    def _usa(self, nombre, buscada, visitadas=()):
        """¿La rutina 'nombre' usa (directa o indirectamente) a 'buscada'?"""
        if nombre == buscada:
            return True
        if nombre in visitadas or nombre not in self.rutinas:
            return False
        return any(
            self._usa(nombre_de_rutina(accion), buscada, visitadas + (nombre,))
            for accion in acciones_de(self.rutinas[nombre]["pasos"], self._nombres())
        )

    def ensenar(self, nombre, texto_pasos):
        nombre = (nombre or "").strip(" \"'«»")
        clave = nombre_de_rutina(nombre)
        if not clave:
            raise ErrorRutina("la rutina necesita un nombre")
        if interpretar(nombre) is not None:
            raise ErrorRutina(f"\"{nombre}\" ya es algo que sé hacer; ponle otro nombre a la rutina")

        pasos = dividir_tarea(texto_pasos or "")
        if not pasos:
            raise ErrorRutina("la rutina necesita al menos un paso")

        nombres = self._nombres() + [nombre]
        for accion in acciones_de(pasos, nombres):
            otra = nombre_de_rutina(accion)
            if (otra in self.rutinas or otra == clave) and self._usa(otra, clave):
                raise ErrorRutina(
                    f"\"{accion}\" haría un círculo: esa rutina terminaría llamándose a sí misma"
                )

        # Para revisar, se incluye la rutina nueva como si ya existiera (vacía):
        # así "si hay errores <ella misma>" no se lee como parte de la condición.
        provisional = {**self.rutinas, clave: {"nombre": nombre, "pasos": []}}
        no_entendidos = [d for d, paso in procesar(pasos, provisional) if paso is None]

        if no_entendidos:
            raise ErrorRutina("no entendí estos pasos: " + "; ".join(f"\"{p}\"" for p in no_entendidos))

        reemplazada = clave in self.rutinas
        self.rutinas[clave] = {
            "nombre": nombre,
            "pasos": pasos,
            "creada": self.ahora().isoformat(timespec="seconds"),
        }
        self._guardar()
        return {**self.rutinas[clave], "reemplazada": reemplazada}

    def olvidar(self, nombre):
        clave = nombre_de_rutina(nombre or "")
        if clave not in self.rutinas:
            raise ErrorRutina(f"no conozco la rutina \"{nombre}\"")

        usuarias = [r["nombre"] for c, r in self.rutinas.items() if c != clave and self._usa(c, clave)]
        rutina = self.rutinas.pop(clave)
        self._guardar()
        return {"nombre": rutina["nombre"], "la_usaban": usuarias}

    def listar(self):
        return sorted(self.rutinas.values(), key=lambda r: r["nombre"].lower())