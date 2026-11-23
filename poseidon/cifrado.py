"""
POSEIDON — Cifrado.

Firmar NO es cifrar:
    - la firma evita que alguien CAMBIE o FALSIFIQUE un mensaje,
    - el cifrado evita que alguien lo LEA.

Aquí cada mensaje se mete en un "sobre" cerrado:

    {"cifrado": true, "alg": "aes-gcm", "nonce": "9f3a…", "datos": "kQ8x…"}

Regla de oro de la seguridad: NO inventar tu propio cifrado. Por eso:

    "aes-gcm"   AES-256-GCM, el estándar de HTTPS y los bancos.
                Necesita: python -m pip install cryptography
    "hmac-ctr"  Plan B con lo que trae Python de fábrica, por si Windows
                bloquea la librería. HMAC-SHA256 como generador de llave
                en modo contador, y otro HMAC para detectar cambios
                ("cifrar y luego autenticar"). Es una construcción
                conocida, pero AES-GCM es mejor: úsalo si puedes.

De la clave de POSEIDON se sacan dos llaves distintas: una para cifrar y
otra para autenticar. Usar la misma llave para dos cosas es mala idea.

El "nonce" son 12 bytes al azar distintos en cada mensaje: así el mismo
mensaje cifrado dos veces se ve diferente, y nadie nota que se repitió.
"""

import base64
import hashlib
import hmac
import json
import secrets


try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAY_AES = True
except Exception:          # no está instalada, o Windows la bloqueó
    HAY_AES = False

AES_GCM = "aes-gcm"
HMAC_CTR = "hmac-ctr"

# Datos extra que se autentican pero no se cifran: atan el sobre a FOCUS.
ETIQUETA = b"FOCUS-POSEIDON-v1"


class SobreInvalido(Exception):
    """El sobre no se pudo abrir: clave equivocada, alguien lo cambió, o no es un sobre."""


def algoritmo_preferido():
    return AES_GCM if HAY_AES else HMAC_CTR


def _llaves(clave):
    """De una clave salen dos llaves independientes (una para cifrar, otra para autenticar)."""
    base = clave.encode("utf-8")
    cifrar = hmac.new(base, b"focus:cifrar", hashlib.sha256).digest()
    autenticar = hmac.new(base, b"focus:autenticar", hashlib.sha256).digest()
    return cifrar, autenticar


def _flujo(llave, nonce, largo):
    """Bytes "al azar" que solo puede repetir quien tiene la llave y el nonce."""
    salida = bytearray()
    contador = 0
    while len(salida) < largo:
        salida += hmac.new(llave, nonce + contador.to_bytes(4, "big"), hashlib.sha256).digest()
        contador += 1
    return bytes(salida[:largo])


def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def cifrar(mensaje, clave, alg=None):
    """Diccionario → sobre cerrado (también es un diccionario, listo para JSON)."""
    alg = alg or algoritmo_preferido()
    texto = json.dumps(mensaje, ensure_ascii=False).encode("utf-8")
    nonce = secrets.token_bytes(12)
    llave_cifrar, llave_autenticar = _llaves(clave)

    if alg == AES_GCM:
        if not HAY_AES:
            raise SobreInvalido("este equipo no tiene la librería cryptography para AES-GCM")
        datos = AESGCM(llave_cifrar).encrypt(nonce, texto, ETIQUETA)   # trae su propia etiqueta
        sobre = {"cifrado": True, "alg": AES_GCM, "nonce": nonce.hex(),
                 "datos": base64.b64encode(datos).decode("ascii")}

    elif alg == HMAC_CTR:
        datos = _xor(texto, _flujo(llave_cifrar, nonce, len(texto)))
        etiqueta = hmac.new(llave_autenticar, ETIQUETA + nonce + datos, hashlib.sha256).hexdigest()
        sobre = {"cifrado": True, "alg": HMAC_CTR, "nonce": nonce.hex(),
                 "datos": base64.b64encode(datos).decode("ascii"), "etiqueta": etiqueta}
    else:
        raise SobreInvalido(f"algoritmo desconocido: {alg}")

    return sobre


def es_sobre(mensaje):
    return isinstance(mensaje, dict) and mensaje.get("cifrado") is True


def descifrar(sobre, clave):
    """Sobre → diccionario original. Lanza SobreInvalido si no se puede abrir."""
    if not es_sobre(sobre):
        raise SobreInvalido("no es un sobre cifrado")

    try:
        nonce = bytes.fromhex(sobre["nonce"])
        datos = base64.b64decode(sobre["datos"], validate=True)
    except (KeyError, ValueError, TypeError):
        raise SobreInvalido("sobre mal formado")

    llave_cifrar, llave_autenticar = _llaves(clave)
    alg = sobre.get("alg")

    if alg == AES_GCM:
        if not HAY_AES:
            raise SobreInvalido("este equipo no tiene la librería cryptography para AES-GCM")
        try:
            texto = AESGCM(llave_cifrar).decrypt(nonce, datos, ETIQUETA)
        except Exception:
            raise SobreInvalido("no se pudo abrir: clave equivocada o el mensaje fue alterado")

    elif alg == HMAC_CTR:
        esperada = hmac.new(llave_autenticar, ETIQUETA + nonce + datos, hashlib.sha256).hexdigest()
        # Primero se revisa la etiqueta: si alguien cambió algo, ni se intenta descifrar.
        if not hmac.compare_digest(esperada, str(sobre.get("etiqueta", ""))):
            raise SobreInvalido("no se pudo abrir: clave equivocada o el mensaje fue alterado")
        texto = _xor(datos, _flujo(llave_cifrar, nonce, len(datos)))
    else:
        raise SobreInvalido(f"algoritmo desconocido: {alg}")

    try:
        return json.loads(texto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SobreInvalido("el contenido no es un mensaje válido")