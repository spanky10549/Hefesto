"""
Resumir resultados.

Cuando GAIA ejecuta un plan, cada paso devuelve datos distintos según
la inteligencia que lo hizo. Aquí se convierten en una frase corta
para que HEFESTO los presente juntos.

Funciones puras: reciben datos y devuelven texto.
"""

from conversacion.redaccion import redactar_definicion


def _definicion(datos):
    return redactar_definicion(datos)


def _calculo(datos):
    return f"{datos['expresion']} = {datos['resultado_texto']}"


def _recursos(datos):
    texto = (
        f"CPU al {datos['cpu']['porcentaje']:.0f} %, "
        f"RAM al {datos['ram']['porcentaje']:.0f} %, "
        f"disco al {datos['disco']['porcentaje']:.0f} %"
    )
    if datos.get("alertas"):
        texto += ". Ojo: " + "; ".join(a["texto"] for a in datos["alertas"])
    return texto + "."


def _registro(datos):
    return (
        f"hoy van {datos['mensajes']} mensajes, "
        f"{datos['errores']} errores y {datos['rechazos']} rechazos."
    )


NOMBRES_DE_SENSOR = {"señal_wifi": "señal del WiFi", "temperatura": "temperatura", "ruido": "ruido"}


def _entorno(datos):
    if not datos["sensores"]:
        return "no hay sensores activos."
    partes = []
    for s in datos["sensores"]:
        nombre = NOMBRES_DE_SENSOR.get(s["tipo"], s["tipo"])
        sentido = f" ({s['etiqueta']})" if s.get("etiqueta") else ""
        aviso = " ⚠" if s.get("raro") else ""
        partes.append(f"{nombre} {s['valor']} {s['unidad']}{sentido}{aviso}".replace("  ", " "))
    return "; ".join(partes) + "."


def _seguridad(datos):
    if not datos["sospechosos"]:
        return "ningún mensaje sospechoso."
    return f"{datos['sospechosos']} mensaje(s) sospechoso(s)."


def _incidentes(datos):
    if not datos["incidentes"]:
        return "ningún incidente abierto."
    return "incidentes abiertos: " + ", ".join(i["inteligencia"].upper() for i in datos["incidentes"]) + "."


def _respaldo(datos):
    return f"guardé {datos['nombre']} ({len(datos['archivos'])} archivos)."


# (inteligencia, acción) → cómo resumir lo que devolvió
RESUMIDORES = {
    ("eter", "entorno"): _entorno,
    ("poseidon", "reporte"): _seguridad,
    ("hades", "incidentes"): _incidentes,
    ("eleuthia", "respaldar"): _respaldo,
    ("apollo", "definir"): _definicion,
    ("calculadora", "calcular"): _calculo,
    ("artemis", "estado"): _recursos,
    ("tabris", "resumen"): _registro,
}


def resumir(para, accion, datos):
    """Una frase con lo importante del resultado de un paso."""
    resumidor = RESUMIDORES.get((para, accion))

    if resumidor is None:
        return "listo."

    try:
        return resumidor(datos)
    except (KeyError, TypeError):
        return "listo (pero no supe resumir lo que devolvió)."