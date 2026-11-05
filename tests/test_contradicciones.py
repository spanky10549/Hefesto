"""
Pruebas de negación, contradicciones y excepciones.
"""

import pytest

from apollo import conocimiento as apollo
from apollo import razonamiento
from apollo.razonamiento import SI, NO, NO_SE


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


def responder_con(monkeypatch, respuesta):
    """Simula que el usuario contesta 's' o 'n' a una pregunta."""
    monkeypatch.setattr("builtins.input", lambda _: respuesta)


# ==========================================
# ENTENDER EL "NO"
# ==========================================

def test_extrae_negacion():
    resultado = apollo.extraer_relacion_con_negacion("el pingüino no puede volar")

    assert resultado == ("pingüino", "puede", "volar", True)


def test_extrae_afirmacion():
    resultado = apollo.extraer_relacion_con_negacion("las aves pueden volar")

    assert resultado == ("aves", "puede", "volar", False)


def test_negacion_no_se_mezcla_con_afirmaciones():
    apollo.aprender_relacion("pingüino", "puede", "volar", negada=True)

    assert apollo.buscar_relaciones("pingüino") == []
    assert len(apollo.buscar_relaciones("pingüino", negadas=True)) == 1


# ==========================================
# CONTRADICCIONES
# ==========================================

def test_contradiccion_reemplaza_si_aceptas(monkeypatch):
    apollo.aprender_relacion("sensor", "mide", "presión")

    responder_con(monkeypatch, "s")
    apollo.aprender_relacion("sensor", "mide", "presión", negada=True)

    assert apollo.buscar_relaciones("sensor") == []
    assert len(apollo.buscar_relaciones("sensor", negadas=True)) == 1


def test_contradiccion_conserva_si_rechazas(monkeypatch):
    apollo.aprender_relacion("sensor", "mide", "presión")

    responder_con(monkeypatch, "n")
    apollo.aprender_relacion("sensor", "mide", "presión", negada=True)

    assert len(apollo.buscar_relaciones("sensor")) == 1
    assert apollo.buscar_relaciones("sensor", negadas=True) == []


def test_relacion_unica_detecta_contradiccion(monkeypatch):
    apollo.aprender_relacion("sensor", "pertenece a", "rover")

    responder_con(monkeypatch, "s")
    apollo.aprender_relacion("sensor", "pertenece a", "dron")

    objetivos = [r["objetivo"] for r in apollo.buscar_relaciones("sensor")]
    assert objetivos == ["dron"]


def test_relacion_multiple_no_pregunta(monkeypatch):
    def no_deberia_preguntar(_):
        raise AssertionError("No debía preguntar nada")

    monkeypatch.setattr("builtins.input", no_deberia_preguntar)

    apollo.aprender_relacion("sensor", "mide", "temperatura")
    apollo.aprender_relacion("sensor", "mide", "humedad")

    assert len(apollo.buscar_relaciones("sensor")) == 2


# ==========================================
# EXCEPCIONES: GANA LO MÁS ESPECÍFICO
# ==========================================

@pytest.fixture
def aves():
    apollo.aprender_relacion("ave", "puede", "volar")
    apollo.aprender_relacion("ave", "tiene", "plumas")
    apollo.aprender_palabra("pingüino", "un ave")
    apollo.aprender_palabra("gorrión", "un ave")
    apollo.aprender_relacion("pingüino", "puede", "volar", negada=True)


def test_regla_general(aves):
    respuesta, _ = razonamiento.responder("gorrión", "puede", "volar")

    assert respuesta == SI


def test_la_excepcion_gana(aves):
    respuesta, cadena = razonamiento.responder("pingüino", "puede", "volar")

    assert respuesta == NO
    assert len(cadena) == 1        # lo sabe directamente


def test_la_excepcion_no_bloquea_lo_demas(aves):
    respuesta, _ = razonamiento.responder("pingüino", "tiene", "plumas")

    assert respuesta == SI


def test_no_hereda_lo_que_tiene_negado(aves):
    objetivos = [
        r["objetivo"] for r in razonamiento.relaciones_inferidas("pingüino")
    ]

    assert "plumas" in objetivos
    assert "volar" not in objetivos


def test_no_sabe_lo_que_no_le_dijeron(aves):
    respuesta, _ = razonamiento.responder("pingüino", "puede", "nadar")

    assert respuesta == NO_SE


def test_negacion_heredada():
    apollo.aprender_relacion("máquina", "puede", "pensar", negada=True)
    apollo.aprender_palabra("tostadora", "una máquina")

    respuesta, cadena = razonamiento.responder("tostadora", "puede", "pensar")

    assert respuesta == NO
    assert len(cadena) == 2


def test_negacion_de_categoria():
    apollo.aprender_relacion("pingüino", "es", "mamífero", negada=True)

    respuesta, _ = razonamiento.responder("pingüino", "es", "mamífero")

    assert respuesta == NO


def test_entiende_contracciones():
    resultado = apollo.extraer_relacion("el sensor pertenece al rover")

    assert resultado == ("sensor", "pertenece a", "rover")