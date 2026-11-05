"""
Pruebas del razonamiento de APOLLO.
"""

import pytest

from apollo import conocimiento as apollo
from apollo import razonamiento


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


@pytest.fixture
def mundo():
    """Un pequeño mundo de conocimiento para razonar."""
    apollo.aprender_palabra("raspberry pi", "una computadora")
    apollo.aprender_palabra("computadora", "una máquina")
    apollo.aprender_relacion("computadora", "necesita", "electricidad")
    apollo.aprender_relacion("máquina", "produce", "calor")
    apollo.aprender_relacion("sensor", "mide", "temperatura")
    apollo.aprender_sinonimo("raspberry pi", "rpi")


# ==========================================
# CATEGORÍAS
# ==========================================

def test_categorias_directas(mundo):
    assert razonamiento.categorias_directas("raspberry pi") == ["computadora"]


def test_ancestros_incluye_categorias_indirectas(mundo):
    nombres = [categoria for categoria, _ in razonamiento.ancestros("raspberry pi")]

    assert nombres == ["computadora", "máquina"]


def test_ancestros_con_ciclo_no_se_traba():
    apollo.aprender_palabra("huevo", "una gallina")
    apollo.aprender_palabra("gallina", "un huevo")

    # huevo → gallina → huevo: al volver al origen se detiene.
    assert len(razonamiento.ancestros("huevo")) == 1


# ==========================================
# HERENCIA
# ==========================================

def test_hereda_relaciones_de_su_categoria(mundo):
    inferidas = razonamiento.relaciones_inferidas("raspberry pi")
    objetivos = [r["objetivo"] for r in inferidas]

    assert "electricidad" in objetivos
    assert "calor" in objetivos       # heredado de dos niveles arriba


def test_la_herencia_explica_su_cadena(mundo):
    inferidas = razonamiento.relaciones_inferidas("raspberry pi")
    electricidad = next(r for r in inferidas if r["objetivo"] == "electricidad")

    assert [p["destino"] for p in electricidad["cadena"]] == [
        "computadora",
        "electricidad",
    ]


def test_hereda_tambien_por_sinonimo(mundo):
    objetivos = [r["objetivo"] for r in razonamiento.relaciones_inferidas("rpi")]

    assert "electricidad" in objetivos


# ==========================================
# INVERSAS
# ==========================================

def test_relaciones_inversas(mundo):
    inversas = razonamiento.relaciones_inversas("temperatura")

    assert inversas == [{"sujeto": "sensor", "relacion": "mide"}]


def test_inversas_de_una_categoria(mundo):
    inversas = razonamiento.relaciones_inversas("computadoras")

    assert {"sujeto": "raspberry pi", "relacion": "es"} in inversas


# ==========================================
# SÍ O NO
# ==========================================

def test_verifica_relacion_directa(mundo):
    assert razonamiento.verificar("sensores", "miden", "temperatura") is not None


def test_verifica_relacion_deducida(mundo):
    cadena = razonamiento.verificar("rpi", "necesita", "electricidad")

    assert cadena is not None
    assert len(cadena) == 2


def test_verifica_categoria_indirecta(mundo):
    assert razonamiento.verificar("raspberry pi", "es", "una máquina") is not None


def test_no_afirma_lo_que_no_sabe(mundo):
    assert razonamiento.verificar("sensor", "necesita", "agua") is None
    assert razonamiento.verificar("computadora", "es", "raspberry pi") is None


def test_frase_de_pregunta_con_es():
    resultado = apollo.extraer_relacion(
        "¿la raspberry pi es una computadora?", incluir_es=True
    )

    assert resultado == ("raspberry pi", "es", "computadora")