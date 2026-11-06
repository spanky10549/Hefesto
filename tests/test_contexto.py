"""
Pruebas del contexto de conversación.

No necesitan diccionario: son funciones que solo transforman texto.
"""

import pytest

from conversacion.contexto import aplicar_contexto, detectar_tema


# ==========================================
# DETECTAR EL TEMA
# ==========================================

@pytest.mark.parametrize("comando, tema", [
    ("qué sabes de los pingüinos", "pingüinos"),
    ("¿el pingüino puede volar?", "pingüino"),
    ("aprende que el sensor mide la luz", "sensor"),
    ("aprende que el pingüino no puede volar", "pingüino"),
    ("aprende que la raspberry pi es una computadora", "raspberry pi"),
    ("aprende que raspberry pi es sinónimo de rpi", "raspberry pi"),
    ("quién mide la temperatura", "temperatura"),
    ("qué mide el sensor", "sensor"),
    ("con qué se comunica la raspberry pi", "raspberry pi"),
])
def test_detecta_tema(comando, tema):
    assert detectar_tema(comando) == tema


@pytest.mark.parametrize("comando", ["ayuda", "estado", "xor", "recuerdos"])
def test_comandos_sin_tema(comando):
    assert detectar_tema(comando) is None


# ==========================================
# COMPLETAR PREGUNTAS
# ==========================================

@pytest.mark.parametrize("comando, esperado", [
    ("¿y puede nadar?", "¿pingüino puede nadar?"),
    ("y puede nadar", "¿pingüino puede nadar?"),
    ("¿puede nadar?", "¿pingüino puede nadar?"),
    ("¿y no tiene alas?", "¿pingüino no tiene alas?"),
    ("¿y es un ave?", "¿pingüino es un ave?"),
    ("¿y qué tiene?", "qué tiene pingüino"),
    ("qué mide", "que mide pingüino"),
    ("qué sabes de él", "qué sabes de pingüino"),
    ("¿qué más sabes?", "qué sabes de pingüino"),
])
def test_completa_con_el_tema(comando, esperado):
    completo, uso = aplicar_contexto(comando, "pingüino")

    assert uso is True
    assert normalizar(completo) == normalizar(esperado)


def normalizar(texto):
    return texto.replace("qué", "que")


@pytest.mark.parametrize("comando", [
    "qué sabes de pingüino",
    "aprende que el sensor mide luz",
    "¿el pingüino puede volar?",
    "ayuda",
])
def test_no_toca_comandos_completos(comando):
    assert aplicar_contexto(comando, "pingüino") == (comando, False)


def test_cambio_de_tema():
    completo, uso = aplicar_contexto("¿y del sensor?", "pingüino")

    assert completo == "qué sabes de sensor"
    assert uso is False


def test_sin_tema_avisa():
    assert aplicar_contexto("¿y puede nadar?", None) == ("¿y puede nadar?", None)


def test_pregunta_con_preposicion():
    completo, uso = aplicar_contexto("¿y a qué pertenece?", "sensor")

    assert uso is True
    assert completo == "a qué pertenece sensor"


def test_detecta_tema_con_preposicion():
    assert detectar_tema("a qué pertenece el sensor") == "sensor"
    assert detectar_tema("de qué depende el motor") == "motor"


# ==========================================
# DOS TEMAS: REPETIR LA PREGUNTA CON OTRO SUJETO
# ==========================================

from conversacion.contexto import crear_plantilla


@pytest.mark.parametrize("comando, tema, plantilla", [
    ("¿el pingüino puede volar?", "pingüino", "¿{tema} puede volar?"),
    ("qué tiene el ave", "ave", "qué tiene {tema}"),
    ("qué sabes de los pingüinos", "pingüinos", "qué sabes de {tema}"),
    ("a qué pertenece el sensor", "sensor", "a qué pertenece {tema}"),
    ("aprende que el pingüino puede nadar", "pingüino", "aprende que {tema} puede nadar"),
])
def test_crear_plantilla(comando, tema, plantilla):
    assert crear_plantilla(comando, tema) == plantilla


@pytest.mark.parametrize("comando, tema", [
    ("olvida que el sensor mide luz", "sensor"),
    ("recuerda el sensor es azul", "sensor"),
    ("ayuda", None),
])
def test_no_crea_plantilla_cuando_no_conviene(comando, tema):
    assert crear_plantilla(comando, tema) is None


@pytest.mark.parametrize("comando", [
    "¿y el gorrión también?",
    "¿y el gorrión?",
    "¿el gorrión también?",
    "¿también el gorrión?",
    "y los gorriones también",
])
def test_repite_la_pregunta_con_otro_sujeto(comando):
    completo, uso = aplicar_contexto(comando, "pingüino", "¿{tema} puede volar?")

    assert uso is True
    assert completo in ("¿gorrión puede volar?", "¿gorriones puede volar?")


def test_sin_pregunta_anterior_cambia_de_tema():
    completo, uso = aplicar_contexto("¿y el gorrión también?", "pingüino", None)

    assert (completo, uso) == ("qué sabes de gorrión", False)


def test_tambien_con_verbo_sigue_funcionando():
    completo, uso = aplicar_contexto("¿también puede nadar?", "pingüino", None)

    assert (completo, uso) == ("¿pingüino puede nadar?", True)