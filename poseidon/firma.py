"""
POSEIDON — Firma de mensajes.

Cuando los mensajes viajan por la red, cualquiera en tu WiFi podría
mandarle órdenes al rover. Para evitarlo, cada mensaje lleva una FIRMA:

    firma = HMAC-SHA256(clave secreta, contenido del mensaje)

    - Solo quien tiene la clave puede calcular una firma válida.
    - Si alguien cambia UNA letra del mensaje, la firma ya no coincide.

La clave vive en el archivo poseidon_clave.txt. GAIA y el rover la leen
del mismo archivo. NUNCA se sube a GitHub (va en el .gitignore): quien
la tenga puede darle órdenes a tus robots.

HMAC es un estándar real (lo usan bancos y servicios web); Python lo
trae en las librerías hmac y hashlib, no hay que instalar nada.
"""

import hashlib
import hmac
import json
import os
import secrets


ARCHIVO_CLAVE = "poseidon_clave.txt"


def cargar_clave(ruta=None):
    """
    Lee la clave secreta. Si no existe, la crea: 64 caracteres al azar
    generados con 'secrets', que está hecho para claves (random no).
    """
    ruta = ruta or ARCHIVO_CLAVE

    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as archivo:
            clave = archivo.read().strip()
        if clave:
            return clave

    clave = secrets.token_hex(32)
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(clave + "\n")
    return clave


def _contenido(mensaje):
    """
    El mensaje convertido a bytes SIEMPRE de la misma forma
    (llaves ordenadas, sin espacios), sin contar la firma.
    Si el orden cambiara, la misma información daría otra firma.
    """
    sin_firma = {campo: valor for campo, valor in mensaje.items() if campo != "firma"}
    texto = json.dumps(sin_firma, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return texto.encode("utf-8")


def calcular_firma(mensaje, clave):
    return hmac.new(clave.encode("utf-8"), _contenido(mensaje), hashlib.sha256).hexdigest()


def firmar(mensaje, clave):
    """Devuelve una copia del mensaje con su firma."""
    return {**mensaje, "firma": calcular_firma(mensaje, clave)}


def firma_valida(mensaje, clave):
    """
    True si la firma corresponde al mensaje.
    compare_digest compara sin dar pistas por el tiempo que tarda
    (comparar letra por letra y salir en la primera diferente deja
    adivinar la firma midiendo cuánto tarda la respuesta).
    """
    firma = mensaje.get("firma")
    if not isinstance(firma, str):
        return False
    return hmac.compare_digest(firma, calcular_firma(mensaje, clave))