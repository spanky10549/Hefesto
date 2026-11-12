"""
GAIA — Ejecución de planes.

MINERVA dice qué hacer y en qué orden; GAIA reparte cada paso a quien
le toca, en orden, y junta los resultados para que HEFESTO los integre.

    resultado = ejecutar_plan(gaia, plan)
    resultado["resultados"] → [{"numero": 1, "estado": "ok", "datos": {...}}, ...]

Si un paso falla:
    si_falla = "continuar"  sigue con los demás (lo normal)
    si_falla = "detener"    los pasos que faltaban quedan "pendiente"

Los pasos que MINERVA marcó con aviso (nadie puede hacerlos) se
"omiten" en vez de mandarse a fallar.
"""

from gaia.mensajes import OK, crear_orden, crear_evento


OMITIDO = "omitido"
PENDIENTE = "pendiente"


def ejecutar_plan(gaia, plan, de="hefesto", al_terminar_paso=None):
    """
    Ejecuta los pasos del plan uno por uno.

    'al_terminar_paso(resultado)' es opcional: se llama después de cada
    paso, para ir mostrando el avance sin esperar a que acabe todo.
    """
    gaia.publicar(crear_evento(gaia.nombre, "tarea_iniciada", {
        "tarea": plan["tarea"], "pasos": len(plan["pasos"])
    }))

    resultados = []
    detenido = False

    for paso in plan["pasos"]:

        resultado = {
            "numero": paso["numero"],
            "descripcion": paso["descripcion"],
            "para": paso["para"],
            "accion": paso["accion"],
            "datos": {},
            "detalle": None,
        }

        if detenido:
            resultado["estado"] = PENDIENTE

        elif paso.get("aviso"):
            resultado["estado"] = OMITIDO
            resultado["detalle"] = paso["aviso"]

        else:
            orden = crear_orden(
                de, paso["para"], paso["accion"], paso["datos"],
                objetivo=plan["tarea"],
                si_falla=paso.get("si_falla"),
            )
            respuesta = gaia.enviar(orden)

            resultado["estado"] = respuesta["estado"]
            resultado["datos"] = respuesta["datos"]
            resultado["detalle"] = respuesta.get("detalle")

            if respuesta["estado"] != OK and paso.get("si_falla") == "detener":
                detenido = True

        resultados.append(resultado)

        if al_terminar_paso is not None:
            al_terminar_paso(resultado)

    completada = all(r["estado"] == OK for r in resultados)

    gaia.publicar(crear_evento(gaia.nombre, "tarea_terminada", {
        "tarea": plan["tarea"],
        "completada": completada,
        "bien": sum(1 for r in resultados if r["estado"] == OK),
        "total": len(resultados),
    }))

    return {"tarea": plan["tarea"], "completada": completada, "resultados": resultados}