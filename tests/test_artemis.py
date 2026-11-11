"""
Pruebas de ARTEMIS. Casi todas usan un medidor de mentira para simular
situaciones (RAM llena, batería baja) sin provocarlas de verdad.
"""

import json
import pytest

from gaia import Gaia, OK, RECHAZADO
from artemis import Artemis
from artemis.servicio import revisar, MB, LIMITE_RAM, LIMITE_BATERIA
from artemis.medidor import medir, FaltaPsutil


GB = 1024 * MB


def medicion(cpu=10, ram=40, disco=50, bateria=None,
             ram_disponible=8 * GB, disco_libre=100 * GB):
    """Una medición inventada, con valores tranquilos por defecto."""
    return {
        "cpu": {"porcentaje": cpu, "nucleos": 4},
        "ram": {"total": 16 * GB, "disponible": ram_disponible, "porcentaje": ram},
        "disco": {"total": 500 * GB, "libre": disco_libre, "porcentaje": disco},
        "bateria": bateria,
    }


class MedidorFalso:
    """Devuelve la medición que le pongas; se puede cambiar entre llamadas."""
    def __init__(self, **valores):
        self.valores = valores

    def __call__(self):
        return medicion(**self.valores)


@pytest.fixture
def medidor():
    return MedidorFalso()


@pytest.fixture
def gaia(medidor):
    g = Gaia()
    g.registrar(Artemis(medidor))
    return g


def estado(gaia):
    return gaia.pedir("hefesto", "artemis", "estado")


# ==========================================
# REVISAR (función pura)
# ==========================================

def test_todo_tranquilo():
    assert revisar(medicion()) == []


@pytest.mark.parametrize("valores, recurso", [
    ({"cpu": 95}, "cpu"),
    ({"ram": LIMITE_RAM}, "ram"),
    ({"disco": 99}, "disco"),
    ({"bateria": {"porcentaje": LIMITE_BATERIA, "conectada": False}}, "bateria"),
])
def test_cada_alerta(valores, recurso):
    assert [a["recurso"] for a in revisar(medicion(**valores))] == [recurso]


def test_bateria_baja_pero_conectada_no_alerta():
    assert revisar(medicion(bateria={"porcentaje": 5, "conectada": True})) == []


def test_sin_bateria_no_alerta():
    assert revisar(medicion(bateria=None)) == []


def test_varias_alertas_a_la_vez():
    alertas = revisar(medicion(cpu=99, ram=99, disco=99))
    assert {a["recurso"] for a in alertas} == {"cpu", "ram", "disco"}


# ==========================================
# ESTADO
# ==========================================

def test_estado(gaia):
    r = estado(gaia)
    assert r["estado"] == OK
    assert r["datos"]["ram"]["porcentaje"] == 40
    assert r["datos"]["alertas"] == []


def test_estado_con_alerta(gaia, medidor):
    medidor.valores = {"ram": 97}
    assert estado(gaia)["datos"]["alertas"][0]["recurso"] == "ram"


def test_sin_psutil_es_rechazo():
    def sin_psutil():
        raise FaltaPsutil("instala psutil con: pip install psutil")

    g = Gaia()
    g.registrar(Artemis(sin_psutil))
    r = estado(g)
    assert r["estado"] == RECHAZADO
    assert "pip install psutil" in r["detalle"]


# ==========================================
# AVISOS (evento recursos_bajos)
# ==========================================

def test_avisa_una_alerta_nueva(gaia, medidor):
    avisos = []
    gaia.suscribir("recursos_bajos", avisos.append)

    medidor.valores = {"ram": 97}
    estado(gaia)

    assert len(avisos) == 1
    assert avisos[0]["datos"]["alertas"][0]["recurso"] == "ram"


def test_no_repite_la_misma_alerta(gaia, medidor):
    avisos = []
    gaia.suscribir("recursos_bajos", avisos.append)

    medidor.valores = {"ram": 97}
    for _ in range(5):
        estado(gaia)

    assert len(avisos) == 1


def test_avisa_solo_lo_nuevo(gaia, medidor):
    avisos = []
    gaia.suscribir("recursos_bajos", avisos.append)

    medidor.valores = {"ram": 97}
    estado(gaia)
    medidor.valores = {"ram": 97, "disco": 99}
    estado(gaia)

    assert [a["recurso"] for a in avisos[1]["datos"]["alertas"]] == ["disco"]


def test_si_se_resuelve_y_vuelve_avisa_otra_vez(gaia, medidor):
    avisos = []
    gaia.suscribir("recursos_bajos", avisos.append)

    medidor.valores = {"ram": 97}
    estado(gaia)
    medidor.valores = {}          # se liberó memoria
    estado(gaia)
    medidor.valores = {"ram": 97}  # se volvió a llenar
    estado(gaia)

    assert len(avisos) == 2


# ==========================================
# ALCANZA
# ==========================================

def alcanza(gaia, **pedido):
    return gaia.pedir("hefesto", "artemis", "alcanza", **pedido)


def test_alcanza(gaia):
    r = alcanza(gaia, ram_mb=1024, disco_mb=2048)["datos"]
    assert r["alcanza"] is True
    assert r["faltan"] == {}
    assert r["hay"] == {"ram_mb": 8192, "disco_mb": 102400}


def test_no_alcanza_la_ram(gaia):
    r = alcanza(gaia, ram_mb=10 * 1024)["datos"]
    assert r["alcanza"] is False
    assert r["faltan"] == {"ram_mb": 2048}


def test_no_alcanza_nada(gaia):
    r = alcanza(gaia, ram_mb=9 * 1024, disco_mb=101 * 1024)["datos"]
    assert set(r["faltan"]) == {"ram_mb", "disco_mb"}


def test_sin_pedir_nada_alcanza(gaia):
    assert alcanza(gaia)["datos"]["alcanza"] is True


@pytest.mark.parametrize("pedido", [{"ram_mb": -5}, {"disco_mb": "mucho"}])
def test_pedidos_invalidos(gaia, pedido):
    assert alcanza(gaia, **pedido)["estado"] == RECHAZADO


# ==========================================
# EL MEDIDOR DE VERDAD
# ==========================================

def test_medir_de_verdad():
    """Mide la computadora donde corren las pruebas."""
    pytest.importorskip("psutil")
    m = medir()

    assert 0 <= m["cpu"]["porcentaje"] <= 100
    assert m["cpu"]["nucleos"] >= 1
    assert m["ram"]["total"] > 0
    assert 0 < m["ram"]["disponible"] <= m["ram"]["total"]
    assert m["disco"]["total"] > 0
    assert m["bateria"] is None or 0 <= m["bateria"]["porcentaje"] <= 100

    json.dumps(m)   # se puede mandar por la red


def test_artemis_esta_en_el_ecosistema():
    from gaia import crear_ecosistema
    assert "artemis" in crear_ecosistema().directorio()