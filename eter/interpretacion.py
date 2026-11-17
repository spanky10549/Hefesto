"""
ÉTER — Interpretación.

Convierte números en significado: 31 °C en un cuarto es "calor".
Funciones puras: reciben una lectura y devuelven qué significa.

Cada tipo de sensor tiene:
    unidad         cómo se mide
    rangos         [(hasta, etiqueta)]: el primero cuyo "hasta" sea mayor
                   que el valor; None es "lo que sea más alto"
    limites        (mínimo, máximo) normales; fuera de eso es anormal
    cambio_brusco  cuánto puede cambiar entre dos lecturas sin ser raro

Un dispositivo puede mandar sus propios rangos y límites: 31 °C en un
procesador no es calor, así que su sensor diría otros números.
"""


TIPOS = {
    "temperatura": {
        "unidad": "°C",
        "rangos": [(15, "frío"), (25, "templado"), (30, "cálido"), (None, "calor")],
        "limites": (5, 38),
        "cambio_brusco": 5,
    },
    "humedad": {
        "unidad": "%",
        "rangos": [(30, "seco"), (60, "normal"), (None, "húmedo")],
        "limites": (15, 85),
        "cambio_brusco": 20,
    },
    "luz": {
        "unidad": "lux",
        "rangos": [(10, "oscuro"), (300, "penumbra"), (None, "iluminado")],
        "limites": None,
        "cambio_brusco": None,
    },
    "distancia": {
        "unidad": "cm",
        "rangos": [(30, "muy cerca"), (100, "cerca"), (None, "lejos")],
        "limites": (5, None),          # menos de 5 cm: algo pegado al sensor
        "cambio_brusco": None,
    },
    "señal_wifi": {
        "unidad": "%",
        "rangos": [(30, "débil"), (70, "aceptable"), (None, "buena")],
        "limites": (20, None),
        "cambio_brusco": 40,
    },
    "ruido": {
        # dBFS: 0 es lo máximo que capta el micrófono; entre más negativo, más silencio
        "unidad": "dBFS",
        "rangos": [(-50, "silencio"), (-30, "tranquilo"), (-15, "plática"), (None, "mucho ruido")],
        "limites": (None, -5),
        "cambio_brusco": None,
    },
    "movimiento": {
        "unidad": "",
        "rangos": None,                # sí / no
        "limites": None,
        "cambio_brusco": None,
    },
}


def ficha(tipo, propios=None):
    """La ficha del tipo, con lo que el dispositivo quiera cambiar encima."""
    base = TIPOS.get(tipo, {"unidad": "", "rangos": None, "limites": None, "cambio_brusco": None})
    return {**base, **(propios or {})}


def etiqueta(tipo, valor, propios=None):
    """
    etiqueta("temperatura", 31)  → "calor"
    etiqueta("movimiento", True) → "hay movimiento"
    Si no sabe interpretar ese tipo, devuelve None.
    """
    if tipo == "movimiento":
        return "hay movimiento" if valor else "sin movimiento"

    rangos = ficha(tipo, propios)["rangos"]
    if not rangos or not isinstance(valor, (int, float)):
        return None

    for hasta, nombre in rangos:
        if hasta is None or valor < hasta:
            return nombre

    return None


def anormalidades(tipo, valor, anterior=None, propios=None):
    """
    Lo raro de una lectura: ["muy alto"], ["cambio brusco"], [].
    'anterior' es el valor de la lectura pasada, para notar cambios bruscos.
    """
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return []

    datos = ficha(tipo, propios)
    raro = []

    if datos["limites"]:
        minimo, maximo = datos["limites"]
        if minimo is not None and valor < minimo:
            raro.append("muy bajo")
        if maximo is not None and valor > maximo:
            raro.append("muy alto")

    if datos["cambio_brusco"] is not None and isinstance(anterior, (int, float)):
        if abs(valor - anterior) >= datos["cambio_brusco"]:
            raro.append("cambio brusco")

    return raro