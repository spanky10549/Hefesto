"""
ARTEMIS — Medidor.

Lee los recursos de la computadora donde corre FOCUS con la librería
psutil (pip install psutil). Funciona igual en Windows, Linux y en la
Raspberry Pi.

Solo mide y devuelve números; decidir si algo está mal es trabajo
de ARTEMIS (servicio.py).

    {
        "cpu":     {"porcentaje": 12.5, "nucleos": 8},
        "ram":     {"total": 17066827776, "disponible": 9123456789, "porcentaje": 46.5},
        "disco":   {"total": 511101108224, "libre": 210987654321, "porcentaje": 58.7},
        "bateria": {"porcentaje": 81, "conectada": False}   # o None si no tiene
    }

Las cantidades van en bytes: 1 GB = 1024 × 1024 × 1024 bytes.
"""

import os


class FaltaPsutil(Exception):
    """psutil no está instalado."""


def medir(ruta_disco=None):
    """Toma una foto de los recursos en este momento."""
    try:
        import psutil
    except ImportError as error:
        raise FaltaPsutil("instala psutil con: pip install psutil") from error

    # interval=0.3: mide la CPU durante 0.3 segundos. Sin eso, la primera
    # lectura siempre sale 0 porque no tiene con qué comparar.
    cpu = psutil.cpu_percent(interval=0.3)

    ram = psutil.virtual_memory()

    # El disco donde está la carpeta de FOCUS (en Windows, por ejemplo, C:\)
    disco = psutil.disk_usage(ruta_disco or os.path.abspath("."))

    # Las computadoras de escritorio y la Raspberry Pi no tienen batería.
    try:
        bateria = psutil.sensors_battery()
    except (AttributeError, NotImplementedError):
        bateria = None

    return {
        "cpu": {
            "porcentaje": cpu,
            "nucleos": psutil.cpu_count() or 1,
        },
        "ram": {
            "total": ram.total,
            "disponible": ram.available,
            "porcentaje": ram.percent,
        },
        "disco": {
            "total": disco.total,
            "libre": disco.free,
            "porcentaje": disco.percent,
        },
        "bateria": None if bateria is None else {
            "porcentaje": round(bateria.percent),
            "conectada": bool(bateria.power_plugged),
        },
    }