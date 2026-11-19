"""
MINERVA — Planificación (v1).

Decide CÓMO abordar una tarea; no la ejecuta. Según el plan de FOCUS,
MINERVA planea, GAIA reparte y HEFESTO integra los resultados.

Para cada tarea:
    1. La parte en pasos y decide a quién le toca cada uno (planeador.py).
    2. Revisa con GAIA que esa inteligencia esté conectada, sepa hacerlo
       y no esté aislada por HADES.
    3. Le pregunta a ARTEMIS si alcanzan los recursos.
    4. Dice si el plan es viable y por qué no, si no lo es.

Acciones:
    planear  {"tarea": "investiga qué es X, calcula 2 + 2 y revisa los recursos"}

    Laboratorio de innovación (laboratorio.py):
    proyectos          {}
    crear_proyecto     {"nombre", "meta"}
    proyecto           {"nombre"}                 el árbol, el avance y la siguiente sugerida
    agregar_capacidad  {"proyecto", "nombre", "padre"?, "estado"?, "notas"?}
    marcar             {"proyecto", "capacidad", "estado", "notas"?}
    quitar_capacidad   {"proyecto", "capacidad"}
    estrategias        {"proyecto", "capacidad"}  ideas para llenar el hueco
    siguiente          {"proyecto"}
    cargar_focus       {}                         el mapa del propio FOCUS
"""

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, OK

from minerva.planeador import planear
from minerva.laboratorio import Laboratorio, ErrorLaboratorio, cargar_plantilla_focus, ESTADOS


# Cuánta RAM (en MB) calcula MINERVA que usa cada tipo de paso.
# Son estimaciones a ojo; cuando haya tareas pesadas (como mover un robot
# o entrenar la red neuronal) aquí se pondrán números reales.
COSTO_RAM_MB = {
    ("apollo", "definir"): 20,
    ("calculadora", "calcular"): 5,
    ("artemis", "estado"): 5,
    ("tabris", "resumen"): 10,
}
COSTO_POR_DEFECTO_MB = 10


class Minerva(Inteligencia):

    nombre = "minerva"
    descripcion = "Planea: divide una tarea en pasos y decide a quién le toca cada uno."

    def __init__(self, laboratorio=None):
        self.laboratorio = laboratorio or Laboratorio()
        self.acciones = {
            "planear": self.planear,
            # Laboratorio de innovación
            "proyectos": self.proyectos,
            "crear_proyecto": self.crear_proyecto,
            "proyecto": self.ver_proyecto,
            "agregar_capacidad": self.agregar_capacidad,
            "marcar": self.marcar,
            "quitar_capacidad": self.quitar_capacidad,
            "estrategias": self.estrategias,
            "siguiente": self.siguiente,
            "cargar_focus": self.cargar_focus,
        }

    # ==========================================
    # LABORATORIO DE INNOVACIÓN
    # ==========================================

    def _lab(self, funcion, *args, **kwargs):
        """Llama al laboratorio y convierte sus errores en rechazos."""
        try:
            return funcion(*args, **kwargs)
        except ErrorLaboratorio as error:
            raise Rechazo(str(error)) from error

    def _experimentos(self, proyecto, capacidad=None):
        """Los experimentos que ELEUTHIA tiene de este proyecto (si ELEUTHIA está)."""
        if self.gaia is None or "eleuthia" not in self.gaia.inteligencias:
            return []
        r = self.gaia.pedir(self.nombre, "eleuthia", "experimentos", proyecto=proyecto, capacidad=capacidad)
        return r["datos"]["experimentos"] if r["estado"] == OK else []

    def proyectos(self, datos):
        return {"proyectos": self.laboratorio.resumen()}

    def crear_proyecto(self, datos):
        p = self._lab(self.laboratorio.crear_proyecto, datos.get("nombre"), datos.get("meta"))
        return {"nombre": p["nombre"], "meta": p["meta"]}

    def ver_proyecto(self, datos):
        arbol = self._lab(self.laboratorio.arbol, datos.get("nombre"))
        sugerida = self._siguiente(arbol["nombre"])
        return {**arbol, "siguiente": sugerida}

    def agregar_capacidad(self, datos):
        estado = datos.get("estado") or "falta"
        return self._lab(
            self.laboratorio.agregar, datos.get("proyecto"), datos.get("nombre"),
            datos.get("padre"), estado, datos.get("notas", ""),
        )

    def marcar(self, datos):
        return self._lab(
            self.laboratorio.marcar, datos.get("proyecto"), datos.get("capacidad"),
            datos.get("estado"), datos.get("notas"),
        )

    def quitar_capacidad(self, datos):
        return {"quitadas": self._lab(self.laboratorio.quitar, datos.get("proyecto"), datos.get("capacidad"))}

    def estrategias(self, datos):
        proyecto = self._lab(self.laboratorio.proyecto, datos.get("proyecto"))["nombre"]
        numero = datos.get("capacidad")
        experimentos = self._experimentos(proyecto, numero)
        return self._lab(self.laboratorio.estrategias, proyecto, numero, experimentos)

    def _siguiente(self, proyecto):
        fallos = {}
        for e in self._experimentos(proyecto):
            if e.get("resultado") == "falló" and e.get("capacidad") is not None:
                fallos[e["capacidad"]] = fallos.get(e["capacidad"], 0) + 1
        return self._lab(self.laboratorio.siguiente, proyecto, fallos)

    def siguiente(self, datos):
        proyecto = self._lab(self.laboratorio.proyecto, datos.get("proyecto"))["nombre"]
        return {"siguiente": self._siguiente(proyecto)}

    def cargar_focus(self, datos):
        """Crea el proyecto FOCUS con el mapa de dónde va el ecosistema."""
        p = self._lab(cargar_plantilla_focus, self.laboratorio)
        return {"nombre": p["nombre"], "capacidades": len(p["capacidades"])}

    def planear(self, datos):
        tarea = datos.get("tarea")
        if not isinstance(tarea, str) or not tarea.strip():
            raise Rechazo("falta 'tarea'")

        plan = planear(tarea)

        if not plan["pasos"]:
            raise Rechazo("no entendí ninguna parte de la tarea")

        self._revisar_responsables(plan)
        plan["recursos"] = self._revisar_recursos(plan)

        problemas = [p for p in plan["pasos"] if p["aviso"]]

        plan["viable"] = not problemas and plan["recursos"]["alcanza"] is not False
        return plan

    def _revisar_responsables(self, plan):
        """Marca cada paso con un aviso si nadie puede hacerlo ahorita."""
        directorio = self.gaia.directorio()

        for paso in plan["pasos"]:
            ficha = directorio.get(paso["para"])

            if ficha is None:
                paso["aviso"] = f"{paso['para']} no está conectada"
            elif paso["accion"] not in ficha["acciones"]:
                paso["aviso"] = f"{paso['para']} no sabe hacer '{paso['accion']}'"
            elif ficha["aislada"]:
                paso["aviso"] = f"{paso['para']} está aislada por HADES"
            else:
                paso["aviso"] = None

    def _revisar_recursos(self, plan):
        """Suma lo que costaría el plan y le pregunta a ARTEMIS si alcanza."""
        ram_mb = sum(
            COSTO_RAM_MB.get((p["para"], p["accion"]), COSTO_POR_DEFECTO_MB)
            for p in plan["pasos"]
        )

        respuesta = self.gaia.pedir(self.nombre, "artemis", "alcanza", ram_mb=ram_mb)

        if respuesta["estado"] != OK:
            # Sin ARTEMIS no se sabe; no se detiene el plan por eso.
            return {"ram_mb": ram_mb, "alcanza": None, "faltan": {}}

        return {
            "ram_mb": ram_mb,
            "alcanza": respuesta["datos"]["alcanza"],
            "faltan": respuesta["datos"]["faltan"],
        }