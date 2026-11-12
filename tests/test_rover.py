"""
Pruebas del rover: el mapa, sus decisiones, el servidor y la red.

Las pruebas de red encienden un rover de verdad en un hilo aparte
(en un puerto libre que elige el sistema), así que prueban la
conexión real, igual que con dos terminales.
"""

import json
import threading

import pytest

from gaia import Gaia, OK, RECHAZADO, ERROR
from gaia.mensajes import crear_orden
from gaia.red import InteligenciaRemota, mandar_linea, ErrorDeRed
from poseidon import Poseidon, Guardia
from poseidon.firma import firmar
from tabris import Tabris
from hades import Hades
from rover import mundo
from rover.robot import Rover
from rover.servidor import ServidorRover, procesar
import tabris.servicio as servicio_tabris


CLAVE = "clave-de-prueba"


# ==========================================
# EL MAPA
# ==========================================

def test_ruta_sin_obstaculos():
    camino = mundo.ruta((0, 0), (2, 1), set())
    assert len(camino) == 3
    assert camino[-1] == (2, 1)


def test_ruta_al_mismo_lugar():
    assert mundo.ruta((3, 3), (3, 3), set()) == []


def test_ruta_rodea_obstaculos():
    pared = {(1, 0), (1, 1)}
    camino = mundo.ruta((0, 0), (2, 0), pared)
    assert not set(camino) & pared
    assert camino[-1] == (2, 0)


def test_sin_camino():
    encerrado = {(1, 0), (0, 1)}
    assert mundo.ruta((0, 0), (5, 5), encerrado) is None


def test_vecinos_no_salen_del_mapa():
    assert sorted(mundo.vecinos((0, 0))) == [(0, 1), (1, 0)]


# ==========================================
# LAS DECISIONES DEL ROVER
# ==========================================

def ir(robot, x, y, **orden):
    robot.orden_actual = crear_orden("gaia", "rover_1", "ir_a", {"x": x, "y": y}, **orden)
    return robot.ir_a({"x": x, "y": y})


def test_llega_sin_obstaculos():
    robot = Rover(obstaculos=set())
    r = ir(robot, 3, 2)
    assert r["llego"] is True
    assert r["posicion"] == [3, 2]
    assert r["casillas"] == 5
    assert r["bateria"] == 100 - 5 * 2


def test_descubre_un_obstaculo_y_lo_rodea():
    robot = Rover(obstaculos={(1, 0)})
    r = ir(robot, 2, 0)
    assert r["llego"] is True
    assert any("obstáculo en (1, 0)" in d for d in r["decisiones"])
    assert (1, 0) in robot.conocidos
    assert [1, 0] not in r["recorrido"]


def test_recuerda_los_obstaculos():
    robot = Rover(obstaculos={(1, 0)})
    ir(robot, 2, 0)
    ir(robot, 0, 0)
    r = ir(robot, 2, 0)
    assert not any("obstáculo" in d for d in r["decisiones"])   # ya lo sabía


def test_plan_b_detenerse():
    robot = Rover(obstaculos={(1, 0)})
    r = ir(robot, 2, 0, si_falla="detenerse")
    assert r["llego"] is False
    assert r["motivo"] == "obstaculo"
    assert r["posicion"] == [0, 0]


def test_freno_por_bateria():
    robot = Rover(obstaculos=set())
    robot.bateria = 20
    r = ir(robot, 9, 0, restricciones={"bateria_minima": 10})
    assert r["llego"] is False
    assert r["motivo"] == "bateria"
    assert r["bateria"] >= 10
    assert any("batería" in d for d in r["decisiones"])


def test_destino_encerrado():
    robot = Rover(obstaculos={(4, 5), (6, 5), (5, 4), (5, 6)})
    r = ir(robot, 5, 5)
    assert r["llego"] is False
    assert r["motivo"] == "sin_camino"


def test_destino_que_es_obstaculo():
    robot = Rover(obstaculos={(3, 0)})
    r = ir(robot, 3, 0)
    assert r["llego"] is False


def test_ya_estaba_ahi():
    r = ir(Rover(obstaculos=set()), 0, 0)
    assert r["llego"] is True
    assert r["decisiones"] == ["ya estaba ahí"]


def test_lleva_el_objetivo():
    r = ir(Rover(obstaculos=set()), 1, 0, objetivo="explorar la cocina")
    assert r["objetivo"] == "explorar la cocina"


@pytest.mark.parametrize("datos", [{"x": 99, "y": 0}, {"x": -1, "y": 0}, {"x": "dos", "y": 1}, {"x": 1}, {"x": True, "y": 1}])
def test_destinos_invalidos(datos):
    from gaia import Rechazo
    with pytest.raises(Rechazo):
        Rover().ir_a(datos)


def test_recargar_y_estado():
    robot = Rover(obstaculos={(1, 0)})
    ir(robot, 2, 0)
    robot.recargar({})
    estado = robot.estado({})
    assert estado["bateria"] == 100
    assert estado["obstaculos_conocidos"] == [[1, 0]]
    json.dumps(estado)


# ==========================================
# PROCESAR (el servidor sin red)
# ==========================================

def linea(mensaje):
    return json.dumps(mensaje)


def test_procesar_orden_firmada():
    guardia = Guardia(CLAVE)
    orden = crear_orden("gaia", "rover_1", "estado")
    respuesta = json.loads(procesar(Rover(), guardia, linea(guardia.sellar(orden)), mostrar=lambda t: None))
    revisada = Guardia(CLAVE).revisar(respuesta)
    assert revisada["estado"] == OK
    assert revisada["responde_a"] == orden["id"]


def test_procesar_rechaza_sin_firma():
    vistos = []
    robot = Rover(obstaculos=set())
    orden = crear_orden("intruso", "rover_1", "ir_a", {"x": 5, "y": 5})

    respuesta = json.loads(procesar(robot, Guardia(CLAVE), linea(orden), mostrar=vistos.append))

    assert respuesta == {"rechazado": True}
    assert robot.posicion == (0, 0)          # no se movió
    assert "POSEIDON" in vistos[0]


def test_procesar_rechaza_clave_equivocada():
    robot = Rover(obstaculos=set())
    falsa = firmar(crear_orden("intruso", "rover_1", "ir_a", {"x": 5, "y": 5}), "clave-del-intruso")
    procesar(robot, Guardia(CLAVE), linea(falsa), mostrar=lambda t: None)
    assert robot.posicion == (0, 0)


def test_procesar_basura():
    respuesta = procesar(Rover(), Guardia(CLAVE), "esto no es json", mostrar=lambda t: None)
    assert json.loads(respuesta) == {"rechazado": True}


# ==========================================
# POR LA RED DE VERDAD
# ==========================================

@pytest.fixture
def servidor():
    """Un rover encendido en un hilo, en un puerto libre."""
    srv = ServidorRover(Rover(obstaculos={(1, 0)}), Guardia(CLAVE), puerto=0, mostrar=lambda t: None)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def remoto(servidor, clave=CLAVE):
    return InteligenciaRemota("rover_1", "127.0.0.1", servidor.puerto, Guardia(clave), tiempo_espera=3)


@pytest.fixture
def gaia(servidor):
    g = Gaia()
    g.registrar(Poseidon())
    r = remoto(servidor)
    assert r.conectar()
    g.registrar(r)
    return g


def test_conectar_trae_sus_acciones(servidor):
    r = remoto(servidor)
    assert r.conectar() is True
    assert set(r.acciones) == {"estado", "ir_a", "recargar"}
    assert "remota" in r.descripcion


def test_orden_por_la_red(gaia):
    orden = crear_orden("hefesto", "rover_1", "ir_a", {"x": 2, "y": 0},
                        objetivo="llegar", restricciones={"bateria_minima": 10})
    respuesta = gaia.enviar(orden)

    assert respuesta["estado"] == OK
    assert respuesta["datos"]["llego"] is True
    assert respuesta["datos"]["objetivo"] == "llegar"
    assert any("obstáculo" in d for d in respuesta["datos"]["decisiones"])


def test_rechazo_viaja_por_la_red(gaia):
    r = gaia.pedir("hefesto", "rover_1", "ir_a", x=50, y=50)
    assert r["estado"] == RECHAZADO
    assert "fuera del mapa" in r["detalle"]


def test_clave_equivocada_no_conecta(servidor):
    assert remoto(servidor, clave="clave-del-intruso").conectar() is False


def test_respuesta_sospechosa_avisa_a_poseidon(servidor):
    """GAIA con otra clave: el rover no obedece y POSEIDON lo reporta."""
    g = Gaia()
    g.registrar(Poseidon())
    r = remoto(servidor, clave="otra-clave")
    r.acciones = {"estado": None}       # registrarla sin conectar
    g.registrar(r)

    respuesta = g.pedir("hefesto", "rover_1", "estado")

    assert respuesta["estado"] == ERROR
    assert g.pedir("hefesto", "poseidon", "reporte")["datos"]["sospechosos"] == 1


def test_sin_rover_encendido():
    r = InteligenciaRemota("rover_1", "127.0.0.1", 1, Guardia(CLAVE), tiempo_espera=1)
    assert r.conectar() is False
    with pytest.raises(ErrorDeRed):
        mandar_linea("127.0.0.1", 1, {"hola": 1}, tiempo_espera=1)


def test_rover_apagado_hades_lo_aisla_y_lo_recupera():
    """
    El rover se apaga a media misión: TABRIS ve los errores, HADES lo aísla.
    Se vuelve a encender y HADES lo recupera.
    """
    robot = Rover(obstaculos=set())
    srv = ServidorRover(robot, Guardia(CLAVE), puerto=0, mostrar=lambda t: None)
    puerto = srv.puerto
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()

    g = Gaia()
    g.registrar(Tabris())
    g.registrar(Hades())
    r = InteligenciaRemota("rover_1", "127.0.0.1", puerto, Guardia(CLAVE), tiempo_espera=2)
    assert r.conectar()
    g.registrar(r)

    # Se apaga
    srv.shutdown()
    srv.server_close()

    for _ in range(servicio_tabris.LIMITE_ERRORES_SEGUIDOS):
        assert g.pedir("hefesto", "rover_1", "estado")["estado"] == ERROR

    assert g.esta_aislada("rover_1")

    # Mientras sigue apagado, recuperarlo no funciona
    assert g.pedir("hefesto", "hades", "recuperar", inteligencia="rover_1")["datos"]["recuperada"] is False

    # Se vuelve a encender en el mismo puerto
    srv2 = ServidorRover(robot, Guardia(CLAVE), puerto=puerto, mostrar=lambda t: None)
    hilo2 = threading.Thread(target=srv2.serve_forever, daemon=True)
    hilo2.start()
    try:
        r = g.pedir("hefesto", "hades", "recuperar", inteligencia="rover_1")["datos"]
        assert r["recuperada"] is True
        assert g.pedir("hefesto", "rover_1", "estado")["estado"] == OK
    finally:
        srv2.shutdown()
        srv2.server_close()


def test_poseidon_esta_en_el_ecosistema():
    from gaia import crear_ecosistema
    assert "poseidon" in crear_ecosistema().directorio()