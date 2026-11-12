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
"""

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, OK

from minerva.planeador import planear


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

    def __init__(self):
        self.acciones = {"planear": self.planear}

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