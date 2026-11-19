"""
ELEUTHIA — Respaldos.

Guarda una copia del conocimiento de FOCUS en un .zip con fecha:

    respaldos/
        respaldo_2026-11-18_12-30-05.zip
        respaldo_2026-11-17_09-12-44.zip
        ...

Detalles importantes:
    - La base de datos de HEFESTO (.db) se copia con la función "backup"
      de SQLite, no copiando el archivo: así la copia sale completa aunque
      alguien esté escribiendo en ese momento.
    - La clave de POSEIDON NO se respalda: es un secreto, y un respaldo
      puede terminar copiado en otro lado (una USB, la nube).
    - Restaurar NO reemplaza archivos con FOCUS encendido (en Windows
      fallaría, y podría dejar todo a medias). Se deja "pendiente" y se
      aplica al arrancar, antes de abrir cualquier archivo.
"""

import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from contextlib import closing
from datetime import datetime


CARPETA_RESPALDOS = "respaldos"
CARPETA_PENDIENTE = "_por_restaurar"
MAX_RESPALDOS = 10

ARCHIVOS = [
    "diccionario_hefesto.db",      # todo lo que sabe HEFESTO (APOLLO)
    "diccionario_hefesto.json",    # el formato viejo, si todavía existe
    "memoria.json",                # identidad de HEFESTO
    "datos_aprendizaje.json",      # ejemplos de la red neuronal
    "hefesto_modelo_v2.npz",       # pesos de la red neuronal
    "conversacion.json",           # el tema de la conversación
    "eter_mapa.json",              # el mapa compartido
    "demeter_permisos.json",       # zonas protegidas y reglas
    "sensores_locales.json",       # qué sensores autorizaste
    "eleuthia_bitacora.jsonl",     # la bitácora y los experimentos
    "laboratorio.json",            # los proyectos del laboratorio de innovación
    "cuerno_arado_listas.json",    # tus sitios confiables y bloqueados
]


def _ahora():
    return datetime.now()


def nombre_respaldo(momento, etiqueta=None):
    nombre = "respaldo_" + momento.strftime("%Y-%m-%d_%H-%M-%S")
    return f"{nombre}_{etiqueta}.zip" if etiqueta else nombre + ".zip"


def _copiar_sqlite(origen, destino):
    # Ojo: "with sqlite3.connect(...)" NO cierra la conexión (solo guarda
    # los cambios). closing() sí la cierra; en Windows importa mucho,
    # porque un archivo abierto no se puede reemplazar.
    with closing(sqlite3.connect(origen)) as fuente, closing(sqlite3.connect(destino)) as copia:
        fuente.backup(copia)


def crear_respaldo(carpeta, destino=None, etiqueta=None, ahora=_ahora):
    """
    Respalda los ARCHIVOS que existan en 'carpeta'. Devuelve
    {"nombre", "archivos", "bytes"}. Borra los respaldos más viejos
    si hay más de MAX_RESPALDOS.
    """
    destino = destino or os.path.join(carpeta, CARPETA_RESPALDOS)
    os.makedirs(destino, exist_ok=True)

    # Dos respaldos en el mismo segundo tendrían el mismo nombre y uno
    # borraría al otro: se le agrega _2, _3... hasta que no choque.
    momento = ahora()
    nombre = nombre_respaldo(momento, etiqueta)
    numero = 2
    while os.path.exists(os.path.join(destino, nombre)):
        nombre = nombre_respaldo(momento, f"{etiqueta}_{numero}" if etiqueta else str(numero))
        numero += 1
    ruta_zip = os.path.join(destino, nombre)
    incluidos = []

    with tempfile.TemporaryDirectory() as temporal, \
            zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zip_:
        for archivo in ARCHIVOS:
            origen = os.path.join(carpeta, archivo)
            if not os.path.isfile(origen):
                continue

            if archivo.endswith(".db"):
                copia = os.path.join(temporal, archivo)
                _copiar_sqlite(origen, copia)
                zip_.write(copia, archivo)
            else:
                zip_.write(origen, archivo)
            incluidos.append(archivo)

    limpiar_viejos(destino)

    return {"nombre": nombre, "archivos": incluidos, "bytes": os.path.getsize(ruta_zip)}


def listar(destino):
    """Los respaldos, del más nuevo al más viejo."""
    if not os.path.isdir(destino):
        return []

    respaldos = []
    for nombre in os.listdir(destino):
        if nombre.startswith("respaldo_") and nombre.endswith(".zip"):
            ruta = os.path.join(destino, nombre)
            with zipfile.ZipFile(ruta) as zip_:
                archivos = zip_.namelist()
            respaldos.append({"nombre": nombre, "archivos": archivos, "bytes": os.path.getsize(ruta)})

    # Del más nuevo al más viejo; si son del mismo segundo, el último que se hizo primero.
    return sorted(respaldos, key=lambda r: os.path.getmtime(os.path.join(destino, r["nombre"])), reverse=True)


def limpiar_viejos(destino, maximo=MAX_RESPALDOS):
    for respaldo in listar(destino)[maximo:]:
        os.remove(os.path.join(destino, respaldo["nombre"]))


def ultimo(destino):
    respaldos = listar(destino)
    return respaldos[0] if respaldos else None


def fecha_de(nombre):
    """'respaldo_2026-11-18_12-30-05.zip' → datetime"""
    texto = nombre[len("respaldo_"):len("respaldo_") + 19]
    return datetime.strptime(texto, "%Y-%m-%d_%H-%M-%S")


# ==========================================
# RESTAURAR (en dos tiempos)
# ==========================================

def preparar_restauracion(destino, nombre):
    """
    Saca los archivos del respaldo a respaldos/_por_restaurar/.
    Todavía no reemplaza nada.
    """
    ruta_zip = os.path.join(destino, os.path.basename(nombre))
    if not os.path.isfile(ruta_zip):
        raise FileNotFoundError(nombre)

    pendiente = os.path.join(destino, CARPETA_PENDIENTE)
    shutil.rmtree(pendiente, ignore_errors=True)
    os.makedirs(pendiente)

    with zipfile.ZipFile(ruta_zip) as zip_:
        for archivo in zip_.namelist():
            # Solo los nombres esperados: un zip modificado no puede escribir
            # fuera de la carpeta (como "../../Windows/algo").
            if archivo in ARCHIVOS:
                zip_.extract(archivo, pendiente)

    return sorted(os.listdir(pendiente))


class ArchivoOcupado(Exception):
    """Windows no deja reemplazar un archivo que otro programa tiene abierto."""


INTENTOS = 10
ESPERA_SEGUNDOS = 0.3


def _reemplazar(origen, destino):
    """
    os.replace, pero con paciencia: en Windows un archivo puede estar
    ocupado un momento (un antivirus revisándolo, por ejemplo).
    """
    for intento in range(INTENTOS):
        try:
            os.replace(origen, destino)
            return
        except PermissionError:
            if intento == INTENTOS - 1:
                raise ArchivoOcupado(os.path.basename(destino))
            time.sleep(ESPERA_SEGUNDOS)


def aplicar_restauracion_pendiente(carpeta, destino=None):
    """
    Se llama al ARRANCAR, antes de abrir cualquier archivo. Si hay una
    restauración pendiente, reemplaza los archivos y la borra.
    Devuelve la lista de archivos restaurados (vacía si no había nada).

    Si algún archivo sigue ocupado, lanza ArchivoOcupado y deja pendiente
    lo que faltó, para intentarlo la próxima vez. Lo que sí se restauró
    ya no se repite.
    """
    destino = destino or os.path.join(carpeta, CARPETA_RESPALDOS)
    pendiente = os.path.join(destino, CARPETA_PENDIENTE)
    if not os.path.isdir(pendiente):
        return []

    restaurados, ocupados = [], []
    for archivo in sorted(os.listdir(pendiente)):
        if archivo not in ARCHIVOS:
            continue
        try:
            _reemplazar(os.path.join(pendiente, archivo), os.path.join(carpeta, archivo))
            restaurados.append(archivo)
        except ArchivoOcupado:
            ocupados.append(archivo)

    if ocupados:
        raise ArchivoOcupado(", ".join(ocupados))

    shutil.rmtree(pendiente, ignore_errors=True)
    return restaurados