"""
Pruebas del cifrado de POSEIDON: los dos algoritmos, que nadie pueda
leer ni cambiar un sobre, y que por la red de verdad no se vea nada.
"""

import base64
import json
import threading

import pytest

from gaia.mensajes import crear_orden
from poseidon.cifrado import (
    cifrar, descifrar, es_sobre, SobreInvalido, AES_GCM, HMAC_CTR, HAY_AES, algoritmo_preferido,
)
from poseidon import Guardia


CLAVE = "clave-de-prueba"

ALGORITMOS = [HMAC_CTR] + ([AES_GCM] if HAY_AES else [])


def orden():
    return crear_orden("gaia", "rover_1", "ir_a", {"x": 6, "y": 6}, objetivo="llegar a la cocina")


@pytest.mark.parametrize("alg", ALGORITMOS)
def test_ida_y_vuelta(alg):
    mensaje = orden()
    sobre = cifrar(mensaje, CLAVE, alg)
    assert es_sobre(sobre) and sobre["alg"] == alg
    assert descifrar(sobre, CLAVE) == mensaje


@pytest.mark.parametrize("alg", ALGORITMOS)
def test_no_se_puede_leer(alg):
    texto = json.dumps(cifrar(orden(), CLAVE, alg), ensure_ascii=False)
    for secreto in ("ir_a", "rover_1", "cocina", '"x"'):
        assert secreto not in texto


@pytest.mark.parametrize("alg", ALGORITMOS)
def test_mismo_mensaje_se_ve_distinto(alg):
    mensaje = orden()
    assert cifrar(mensaje, CLAVE, alg)["datos"] != cifrar(mensaje, CLAVE, alg)["datos"]


@pytest.mark.parametrize("alg", ALGORITMOS)
def test_otra_clave_no_abre(alg):
    with pytest.raises(SobreInvalido):
        descifrar(cifrar(orden(), CLAVE, alg), "otra-clave")


@pytest.mark.parametrize("alg", ALGORITMOS)
def test_cambiar_un_byte_se_nota(alg):
    sobre = cifrar(orden(), CLAVE, alg)
    datos = bytearray(base64.b64decode(sobre["datos"]))
    datos[5] ^= 1                         # un solo bit distinto
    sobre["datos"] = base64.b64encode(bytes(datos)).decode()
    with pytest.raises(SobreInvalido, match="alterado"):
        descifrar(sobre, CLAVE)


@pytest.mark.parametrize("alg", ALGORITMOS)
def test_cambiar_el_nonce_se_nota(alg):
    sobre = cifrar(orden(), CLAVE, alg)
    sobre["nonce"] = "00" * 12
    with pytest.raises(SobreInvalido):
        descifrar(sobre, CLAVE)


@pytest.mark.parametrize("sobre", [
    {"hola": 1},
    {"cifrado": True, "alg": "hmac-ctr"},
    {"cifrado": True, "alg": "rot13", "nonce": "00", "datos": ""},
    {"cifrado": True, "alg": "hmac-ctr", "nonce": "zz", "datos": "%%%"},
])
def test_sobres_mal_hechos(sobre):
    with pytest.raises(SobreInvalido):
        descifrar(sobre, CLAVE)


def test_algoritmo_preferido():
    assert algoritmo_preferido() == (AES_GCM if HAY_AES else HMAC_CTR)


def test_guardia_con_el_plan_b():
    """Aunque Windows bloqueara 'cryptography', el plan B funciona igual."""
    guardia = Guardia(CLAVE, alg=HMAC_CTR)
    mensaje = orden()
    sellado = guardia.sellar(mensaje)
    assert sellado["alg"] == HMAC_CTR
    assert Guardia(CLAVE).revisar(sellado) == mensaje


# ==========================================
# POR LA RED DE VERDAD: ¿QUÉ VE UN ESPÍA?
# ==========================================

def test_un_espia_en_la_red_no_ve_nada():
    """
    Un 'espía' se pone entre GAIA y el rover (como alguien en tu WiFi) y
    guarda todo lo que pasa. No debe poder leer ni la orden ni la respuesta.
    """
    import socket
    from gaia.red import InteligenciaRemota
    from rover.robot import Rover
    from rover.servidor import ServidorRover

    servidor = ServidorRover(Rover(obstaculos=set()), Guardia(CLAVE), puerto=0, mostrar=lambda t: None)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    capturado = []

    # El espía: recibe de GAIA, anota, reenvía al rover, anota la respuesta y la regresa.
    espia = socket.socket()
    espia.bind(("127.0.0.1", 0))
    espia.listen()

    def espiar():
        while True:
            try:
                conexion, _ = espia.accept()
            except OSError:
                return
            with conexion, socket.create_connection(("127.0.0.1", servidor.puerto)) as rover:
                pedido = conexion.makefile("rb").readline()
                capturado.append(pedido)
                rover.sendall(pedido)
                respuesta = rover.makefile("rb").readline()
                capturado.append(respuesta)
                conexion.sendall(respuesta)

    threading.Thread(target=espiar, daemon=True).start()

    try:
        remoto = InteligenciaRemota("rover_1", "127.0.0.1", espia.getsockname()[1], Guardia(CLAVE), tiempo_espera=3)
        assert remoto.conectar()
        datos = remoto.atender(crear_orden("hefesto", "rover_1", "ir_a", {"x": 3, "y": 2},
                                           objetivo="ir a la cocina"))
        assert datos["llego"] is True        # todo funcionó...

        todo = b"".join(capturado).decode("utf-8")
        for secreto in ("ir_a", "cocina", "llego", "posicion", "decisiones", "rover_1"):
            assert secreto not in todo        # ...y el espía no vio nada
        assert '"cifrado": true' in todo
    finally:
        espia.close()
        servidor.shutdown()
        servidor.server_close()