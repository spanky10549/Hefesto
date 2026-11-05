"""
Pruebas de olvidar en APOLLO.
"""

import pytest

from apollo import conocimiento as apollo


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


# ==========================================
# RELACIONES
# ==========================================

def test_olvidar_relacion():
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    assert apollo.olvidar_relacion("sensor", "mide", "temperatura") == 1
    assert apollo.buscar_relaciones("sensor") == []


def test_olvidar_relacion_escrita_distinto():
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    borradas = apollo.olvidar_relacion("los sensores", "miden", "la temperatura")

    assert borradas == 1


def test_olvidar_solo_borra_lo_indicado():
    apollo.aprender_relacion("sensor", "mide", "temperatura")
    apollo.aprender_relacion("sensor", "detecta", "movimiento")

    apollo.olvidar_relacion("sensor", "mide", "temperatura")

    assert apollo.buscar_relaciones("sensor") == [
        {"relacion": "detecta", "objetivo": "movimiento"}
    ]


def test_olvidar_algo_que_no_sabia():
    assert apollo.olvidar_relacion("sensor", "mide", "presión") == 0


def test_olvidar_por_sinonimo():
    apollo.aprender_relacion("raspberry pi", "usa", "python")
    apollo.aprender_sinonimo("raspberry pi", "rpi")

    assert apollo.olvidar_relacion("rpi", "usa", "python") == 1


# ==========================================
# CATEGORÍAS
# ==========================================

def test_olvidar_categoria():
    apollo.aprender_palabra("raspberry pi", "una computadora")

    assert apollo.olvidar_categoria("raspberry pi", "computadoras") == 1
    assert apollo.buscar_palabra("raspberry pi") == []


# ==========================================
# SINÓNIMOS
# ==========================================

def test_olvidar_sinonimo_en_cualquier_orden():
    apollo.aprender_palabra("raspberry pi", "una computadora")
    apollo.aprender_sinonimo("raspberry pi", "rpi")

    assert apollo.olvidar_sinonimo("rpi", "raspberry pi") is True
    assert apollo.buscar_entrada("rpi") is None


# ==========================================
# CONCEPTOS COMPLETOS
# ==========================================

def test_olvidar_concepto():
    apollo.aprender_relacion("sensor", "mide", "temperatura")
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensor")

    nombre, menciones = apollo.olvidar_concepto("sensores")

    assert nombre == "sensor"
    assert menciones == 1                 # la raspberry pi aún lo menciona
    assert apollo.buscar_relaciones("sensor") == []


def test_olvidar_concepto_desconocido():
    assert apollo.olvidar_concepto("unicornio") == (None, 0)