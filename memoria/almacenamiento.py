import copy
import json
import os


class ErrorAlmacenamiento(Exception):
    """Error al leer o escribir un archivo de HEFESTO."""


def cargar_json(ruta, valor_inicial):
    """Carga un JSON. Si no existe, lo crea con valor_inicial."""

    if not os.path.exists(ruta):
        datos = copy.deepcopy(valor_inicial)
        guardar_json(ruta, datos)
        return datos

    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            return json.load(archivo)

    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ErrorAlmacenamiento(
            f"El archivo {ruta} está dañado: {error}"
        ) from error

    except OSError as error:
        raise ErrorAlmacenamiento(
            f"No pude leer {ruta}: {error}"
        ) from error


def guardar_json(ruta, datos):
    """Guarda un JSON de forma atómica (sin riesgo de dejarlo a medias)."""

    ruta_temporal = ruta + ".tmp"

    try:
        with open(ruta_temporal, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, indent=4, ensure_ascii=False)
            archivo.flush()
            os.fsync(archivo.fileno())

        os.replace(ruta_temporal, ruta)

    except (OSError, TypeError, ValueError) as error:
        raise ErrorAlmacenamiento(
            f"No pude guardar {ruta}: {error}"
        ) from error
    