"""
Pruebas de ÉTER: interpretación, lecturas, anomalías, sensores en
silencio, la estación simulada y el mapa compartido con el rover.
"""

from datetime import datetime, timedelta

import pytest

from gaia import Gaia, Inteligencia, OK, RECHAZADO
from gaia.mensajes import crear_orden
from eter import Eter
from eter.interpretacion import etiqueta, anormalidades
import eter.servicio as servicio
from dispositivos.estacion import EstacionSimulada
from rover.robot import Rover


# ==========================================
# INTERPRETACIÓN (funciones puras)
# ==========================================

@pytest.mark.parametrize("tipo, valor, esperado", [
    ("temperatura", 10, "frío"),
    ("temperatura", 22, "templado"),
    ("temperatura", 28, "cálido"),
    ("temperatura", 31, "calor"),
    ("humedad", 45, "normal"),
    ("luz", 5, "oscuro"),
    ("distancia", 20, "muy cerca"),
    ("distancia", 500, "lejos"),
    ("movimiento", True, "hay movimiento"),
    ("movimiento", False, "sin movimiento"),
    ("radiacion", 3, None),          # tipo que no conoce
    ("temperatura", "mucho", None),  # valor que no es número
])
def test_etiqueta(tipo, valor, esperado):
    assert etiqueta(tipo, valor) == esperado


def test_rangos_propios_del_dispositivo():
    """31 °C es calor en un cuarto, pero frío para un procesador."""
    procesador = {"rangos": [(50, "frío"), (80, "normal"), (None, "caliente")]}
    assert etiqueta("temperatura", 31, procesador) == "frío"


def test_anormalidades():
    assert anormalidades("temperatura", 24) == []
    assert anormalidades("temperatura", 45) == ["muy alto"]
    assert anormalidades("temperatura", 0) == ["muy bajo"]
    assert anormalidades("temperatura", 30, anterior=24) == ["cambio brusco"]
    assert anormalidades("temperatura", 26, anterior=24) == []
    assert anormalidades("distancia", 2) == ["muy bajo"]
    assert anormalidades("movimiento", True) == []


# ==========================================
# LECTURAS
# ==========================================

class Reloj:
    """Un reloj que se puede adelantar a mano."""
    def __init__(self):
        self.momento = datetime(2026, 11, 12, 15, 0, 0)

    def __call__(self):
        return self.momento

    def adelantar(self, segundos):
        self.momento += timedelta(seconds=segundos)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def gaia(reloj):
    g = Gaia()
    g.registrar(Eter(ahora=reloj))
    return g


def leer(gaia, **lectura):
    return gaia.pedir("hefesto", "eter", "lectura", **lectura)


def test_lectura_se_interpreta(gaia):
    r = leer(gaia, sensor="t1", tipo="temperatura", lugar="cuarto", valor=31)
    assert r["estado"] == OK
    assert r["datos"]["etiqueta"] == "calor"
    assert r["datos"]["unidad"] == "°C"
    assert r["datos"]["raro"] == []


def test_lectura_sin_sensor_o_valor(gaia):
    assert leer(gaia, valor=3)["estado"] == RECHAZADO
    assert leer(gaia, sensor="t1")["estado"] == RECHAZADO


def test_recuerda_tipo_y_lugar(gaia):
    leer(gaia, sensor="t1", tipo="temperatura", lugar="cocina", valor=20)
    r = leer(gaia, sensor="t1", valor=21)["datos"]
    assert (r["tipo"], r["lugar"]) == ("temperatura", "cocina")


def test_entorno_por_lugar(gaia):
    leer(gaia, sensor="t1", tipo="temperatura", lugar="cuarto", valor=20)
    leer(gaia, sensor="t2", tipo="temperatura", lugar="cocina", valor=25)
    sensores = gaia.pedir("hefesto", "eter", "entorno", lugar="cocina")["datos"]["sensores"]
    assert [s["sensor"] for s in sensores] == ["t2"]


# ==========================================
# ANOMALÍAS
# ==========================================

def test_avisa_anomalia(gaia):
    avisos = []
    gaia.suscribir("anomalia_entorno", avisos.append)

    leer(gaia, sensor="t1", tipo="temperatura", valor=24)
    leer(gaia, sensor="t1", valor=45)

    assert len(avisos) == 1
    assert set(avisos[0]["datos"]["motivos"]) == {"muy alto", "cambio brusco"}


def test_no_repite_el_aviso(gaia):
    avisos = []
    gaia.suscribir("anomalia_entorno", avisos.append)
    for _ in range(4):
        leer(gaia, sensor="t1", tipo="temperatura", valor=45)
    assert len(avisos) == 1


def test_sensor_en_silencio(gaia, reloj):
    leer(gaia, sensor="t1", tipo="temperatura", valor=24)
    assert gaia.pedir("hefesto", "eter", "anomalias")["datos"]["anomalias"] == []

    reloj.adelantar(servicio.SILENCIO_SEGUNDOS + 1)

    (anomalia,) = gaia.pedir("hefesto", "eter", "anomalias")["datos"]["anomalias"]
    assert "sin datos recientes" in anomalia["raro"]


# ==========================================
# DISPOSITIVOS (quien sepa "leer")
# ==========================================

def test_estacion_lee_sus_sensores():
    lecturas = EstacionSimulada(semilla=1).leer({})["lecturas"]
    assert {l["tipo"] for l in lecturas} == {"temperatura", "humedad", "luz"}
    assert all(l["lugar"] == "cuarto" for l in lecturas)


def test_estacion_cambia_poco_a_poco():
    estacion = EstacionSimulada(semilla=2)
    antes = estacion.leer({})["lecturas"][0]["valor"]
    despues = estacion.leer({})["lecturas"][0]["valor"]
    assert abs(despues - antes) <= 0.4


def test_simular_un_valor():
    estacion = EstacionSimulada(semilla=3)
    estacion.simular({"sensor": "temp_cuarto", "valor": 45})
    assert estacion.leer({})["lecturas"][0]["valor"] == 45


def test_simular_mal():
    from gaia import Rechazo
    with pytest.raises(Rechazo):
        EstacionSimulada().simular({"sensor": "radar", "valor": 1})


def test_actualizar_pide_a_todos_los_que_saben_leer(gaia):
    gaia.registrar(EstacionSimulada("estacion_1", lugar="cuarto", semilla=1))
    gaia.registrar(EstacionSimulada("estacion_2", lugar="cocina", semilla=2))

    r = gaia.pedir("hefesto", "eter", "actualizar")["datos"]
    assert r["dispositivos"] == ["estacion_1", "estacion_2"]
    assert r["lecturas"] == 6


def test_un_dispositivo_nuevo_se_toma_solo(gaia):
    """Cualquier cosa que sepa 'leer' sirve, sin tocar a ÉTER."""
    class SensorDeMovimiento(Inteligencia):
        nombre = "pir_puerta"
        def __init__(self):
            self.acciones = {"leer": lambda d: {"lecturas": [
                {"sensor": "pir", "tipo": "movimiento", "lugar": "puerta", "valor": True}
            ]}}

    gaia.registrar(SensorDeMovimiento())
    gaia.pedir("hefesto", "eter", "actualizar")

    (sensor,) = gaia.pedir("hefesto", "eter", "entorno")["datos"]["sensores"]
    assert sensor["etiqueta"] == "hay movimiento"


def test_dispositivo_que_falla(gaia):
    class Roto(Inteligencia):
        nombre = "roto"
        def __init__(self):
            self.acciones = {"leer": lambda d: 1 / 0}

    gaia.registrar(Roto())
    r = gaia.pedir("hefesto", "eter", "actualizar")["datos"]
    assert r["fallaron"] == ["roto"]


def test_dispositivo_aislado_no_se_consulta(gaia):
    gaia.registrar(EstacionSimulada())
    gaia.aislar("estacion_1")
    assert gaia.pedir("hefesto", "eter", "actualizar")["datos"]["dispositivos"] == []


# ==========================================
# MAPA COMPARTIDO
# ==========================================

def test_reportar_y_ver_el_mapa(gaia):
    r = gaia.pedir("hefesto", "eter", "reportar_obstaculos",
                   obstaculos=[[2, 0], [2, 1]], origen="rover_1")["datos"]
    assert r == {"nuevos": 2, "total": 2}

    r = gaia.pedir("hefesto", "eter", "reportar_obstaculos",
                   obstaculos=[[2, 1], [5, 4]], origen="rover_2")["datos"]
    assert r == {"nuevos": 1, "total": 3}

    mapa = gaia.pedir("hefesto", "eter", "mapa")["datos"]["obstaculos"]
    assert [o["casilla"] for o in mapa] == [[2, 0], [2, 1], [5, 4]]
    assert mapa[2]["origen"] == "rover_2"


@pytest.mark.parametrize("obstaculos", ["nada", [[1]], [["a", "b"]], [[True, 1]]])
def test_obstaculos_invalidos(gaia, obstaculos):
    r = gaia.pedir("hefesto", "eter", "reportar_obstaculos", obstaculos=obstaculos)
    assert r["estado"] == RECHAZADO


def test_el_mapa_sobrevive_al_apagado(tmp_path):
    ruta = str(tmp_path / "mapa.json")
    Eter(ruta_mapa=ruta).reportar_obstaculos({"obstaculos": [[3, 3]], "origen": "rover_1"})

    otro = Eter(ruta_mapa=ruta)
    assert otro.mapa({})["obstaculos"][0]["casilla"] == [3, 3]


def test_las_pruebas_no_tocan_el_mapa_real(tmp_path):
    assert servicio.ARCHIVO_MAPA.startswith(str(tmp_path.parent))


# ==========================================
# EL ROVER CON EL MAPA COMPARTIDO
# ==========================================

def ir(robot, x, y, conocidos=()):
    datos = {"x": x, "y": y, "obstaculos_conocidos": [list(c) for c in conocidos]}
    robot.orden_actual = crear_orden("gaia", "rover_1", "ir_a", datos)
    return robot.ir_a(datos)


def test_rover_reporta_lo_que_descubre():
    r = ir(Rover(obstaculos={(1, 0)}), 2, 0)
    assert r["descubiertos"] == [[1, 0]]


def test_rover_usa_el_mapa_y_no_se_topa():
    r = ir(Rover(obstaculos={(1, 0)}), 2, 0, conocidos=[(1, 0)])
    assert r["llego"] is True
    assert r["descubiertos"] == []
    assert not any("encontré" in d for d in r["decisiones"])
    assert any("mapa compartido" in d for d in r["decisiones"])


def test_rover_ignora_casillas_raras_del_mapa():
    r = ir(Rover(obstaculos=set()), 1, 0, conocidos=[(99, 99)])
    assert r["llego"] is True


def test_un_rover_reiniciado_aprovecha_lo_que_vio_el_anterior(tmp_path):
    """
    El primer rover descubre la pared. Se 'reinicia' (rover nuevo, sin
    memoria), pero ÉTER guardó el mapa y el nuevo llega sin toparse.
    """
    ruta = str(tmp_path / "mapa.json")
    pared = {(2, 0), (2, 1), (2, 2)}

    primero = ir(Rover(obstaculos=pared), 3, 0)
    Eter(ruta_mapa=ruta).reportar_obstaculos({"obstaculos": primero["descubiertos"], "origen": "rover_1"})

    eter = Eter(ruta_mapa=ruta)        # también ÉTER se apagó y prendió
    conocidos = [tuple(o["casilla"]) for o in eter.mapa({})["obstaculos"]]

    segundo = ir(Rover(obstaculos=pared), 3, 0, conocidos=conocidos)

    assert segundo["llego"] is True
    assert segundo["descubiertos"] == []
    assert segundo["casillas"] <= primero["casillas"]


def test_eter_y_dispositivo_local_en_el_ecosistema():
    from gaia import crear_ecosistema
    directorio = crear_ecosistema().directorio()
    assert "eter" in directorio
    assert "leer" in directorio["dispositivo_local"]["acciones"]
    assert "estacion_1" not in directorio      # la simulada viene apagada