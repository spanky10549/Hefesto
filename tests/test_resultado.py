"""
Pruebas de los resultados que devuelve APOLLO al aprender.

APOLLO ya no imprime: devuelve {"estado": ..., ...}.
Estas pruebas revisan que cada caso dé el estado correcto,
y que APOLLO nunca escriba en pantalla.
"""

import pytest

from apollo import conocimiento as apollo


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


@pytest.fixture(autouse=True)
def apollo_no_habla(capsys):
    """Después de cada prueba, comprueba que APOLLO no imprimió nada."""
    yield
    assert capsys.readouterr().out == ""


# ==========================================
# PALABRAS
# ==========================================

def test_palabra_nueva():
    assert apollo.aprender_palabra("raspberry pi", "una computadora")["estado"] == "nueva"


def test_palabra_con_otra_asociacion():
    apollo.aprender_palabra("raspberry pi", "una computadora")

    r = apollo.aprender_palabra("la Raspberry Pi", "una placa")

    assert r["estado"] == "asociada"


def test_palabra_ya_sabida():
    apollo.aprender_palabra("raspberry pi", "una computadora")

    assert apollo.aprender_palabra("raspberry pi", "Una Computadora")["estado"] == "ya_sabia"


def test_palabra_vacia():
    assert apollo.aprender_palabra("", "algo")["estado"] == "vacio"


# ==========================================
# SINÓNIMOS
# ==========================================

def test_sinonimo_aprendido():
    apollo.aprender_palabra("raspberry pi", "una computadora")

    r = apollo.aprender_sinonimo("raspberry pi", "rpi")

    assert r == {"estado": "aprendido", "palabra": "raspberry pi", "sinonimo": "rpi"}


@pytest.mark.parametrize("palabra, sinonimo, estado", [
    ("unicornio", "uni", "desconocido"),
    ("raspberry pi", "Raspberry Pi", "iguales"),
    ("raspberry pi", "rpi", "ya_sabia"),
    ("rpi", "raspberry pi", "ya_sabia"),
    ("raspberry pi", "sensor", "ya_registrado"),
    ("", "rpi", "vacio"),
])
def test_sinonimo_casos(palabra, sinonimo, estado):
    apollo.aprender_palabra("raspberry pi", "una computadora")
    apollo.aprender_palabra("sensor", "un dispositivo")
    apollo.aprender_sinonimo("raspberry pi", "rpi")

    assert apollo.aprender_sinonimo(palabra, sinonimo)["estado"] == estado


# ==========================================
# RELACIONES
# ==========================================

def test_relacion_aprendida():
    r = apollo.aprender_relacion("los sensores", "miden", "la temperatura")

    assert r["estado"] == "aprendida"
    # El sujeto se guarda en singular.
    assert (r["sujeto"], r["relacion"], r["objeto"]) == ("sensor", "mide", "temperatura")


@pytest.mark.parametrize("sujeto, relacion, objeto, estado", [
    ("sensor", "baila con", "motor", "relacion_invalida"),
    ("sensor", "mide", "sensores", "mismo_concepto"),
    ("", "mide", "luz", "vacio"),
    ("sensor", "mide", "temperatura", "ya_sabia"),
])
def test_relacion_casos(sujeto, relacion, objeto, estado):
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    assert apollo.aprender_relacion(sujeto, relacion, objeto)["estado"] == estado