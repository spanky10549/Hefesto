"""
Pruebas de definir(): que junte todo lo que sabe, directo y deducido.
"""

import pytest

from apollo import conocimiento as apollo
from apollo.definicion import definir
from conversacion.redaccion import redactar_definicion


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


@pytest.fixture
def mundo():
    apollo.aprender_palabra("ave", "un animal")
    apollo.aprender_relacion("animal", "necesita", "agua")
    apollo.aprender_relacion("aves", "pueden", "volar")
    apollo.aprender_relacion("aves", "tienen", "plumas")
    apollo.aprender_palabra("pingüino", "un ave")
    apollo.aprender_palabra("gorrión", "un ave")
    apollo.aprender_relacion("pingüino", "puede", "nadar")
    apollo.aprender_relacion("pingüino", "puede", "volar", negada=True)


def test_junta_lo_directo(mundo):
    d = definir("pingüino")

    assert d["categorias"] == ["ave"]
    assert d["hace"] == {"puede": ["nadar"]}
    assert d["no_hace"] == {"puede": ["volar"]}


def test_junta_lo_deducido(mundo):
    d = definir("pingüino")

    assert ("animal", "ave") in d["categorias_deducidas"]
    assert ("ave", "tiene", "plumas") in d["hereda"]
    assert ("animal", "necesita", "agua") in d["hereda"]


def test_no_hereda_lo_que_tiene_negado(mundo):
    heredado = [objetivo for _, _, objetivo in definir("pingüino")["hereda"]]

    assert "volar" not in heredado


def test_ejemplos_de_una_categoria(mundo):
    assert definir("aves")["ejemplos"] == ["pingüino", "gorrión"]


def test_por_sinonimo():
    apollo.aprender_palabra("raspberry pi", "una computadora")
    apollo.aprender_sinonimo("raspberry pi", "rpi")

    d = definir("rpi")

    assert d["concepto"] == "raspberry pi"
    assert d["sinonimos"] == ["rpi"]


def test_desconocido():
    assert definir("unicornio")["conocido"] is False


def test_definicion_completa_redactada(mundo):
    texto = redactar_definicion(definir("pingüino"))

    assert texto == (
        "Pingüino: Es un ave. Como es ave, también es un animal. "
        "Puede nadar, pero no puede volar. "
        "Por ser ave, tiene plumas. Por ser animal, necesita agua."
    )