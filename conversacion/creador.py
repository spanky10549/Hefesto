"""
El creador de FOCUS.

FOCUS sabe quién lo está construyendo, y puede comprobar que eres tú con
una clave secreta.

La clave NUNCA se guarda como texto. Se guarda su "hash":

    hash = PBKDF2-HMAC-SHA256(clave, sal, 200 000 vueltas)

    - Es de un solo sentido: con el hash no se puede sacar la clave.
    - La "sal" son bytes al azar, distintos para cada clave: así dos claves
      iguales dan hashes distintos y no sirven tablas de hashes ya hechas.
    - Las 200 000 vueltas lo hacen lento a propósito: probar millones de
      claves para adivinarla tardaría muchísimo.

Es lo mismo que hacen las páginas web serias con tus contraseñas.
Se guarda en focus_creador.json (que NO se sube a GitHub).
"""

import hashlib
import hmac
import os
import secrets

from memoria.almacenamiento import cargar_json, guardar_json


ARCHIVO_CREADOR = "focus_creador.json"

NOMBRE_CREADOR = "spanky"
VUELTAS = 200_000
MINIMO_CARACTERES = 6
MAX_INTENTOS = 3


def calcular_hash(clave, sal_hex, vueltas=VUELTAS):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal_hex), vueltas).hex()


class Creador:

    def __init__(self, ruta=None, nombre=NOMBRE_CREADOR):
        self.ruta = ruta or ARCHIVO_CREADOR
        self.nombre = nombre
        datos = cargar_json(self.ruta, {}) if os.path.exists(self.ruta) else {}
        self.sal = datos.get("sal")
        self.hash = datos.get("hash")
        self.vueltas = datos.get("vueltas", VUELTAS)
        self.nombre = datos.get("nombre", nombre)

    def configurado(self):
        return bool(self.sal and self.hash)

    def establecer(self, clave):
        """Guarda una clave nueva. Devuelve un texto con el problema, o None si salió bien."""
        if len(clave) < MINIMO_CARACTERES:
            return f"la clave necesita al menos {MINIMO_CARACTERES} caracteres"
        self.sal = secrets.token_hex(16)
        self.vueltas = VUELTAS
        self.hash = calcular_hash(clave, self.sal, self.vueltas)
        guardar_json(self.ruta, {
            "nombre": self.nombre, "sal": self.sal, "hash": self.hash, "vueltas": self.vueltas,
        })
        return None

    def verificar(self, clave):
        if not self.configurado():
            return False
        # compare_digest: compara sin dar pistas por el tiempo que tarda (como POSEIDON)
        return hmac.compare_digest(calcular_hash(clave, self.sal, self.vueltas), self.hash)