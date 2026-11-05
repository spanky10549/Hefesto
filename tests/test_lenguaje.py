"""
Pruebas del módulo de lenguaje de APOLLO.
"""

import pytest

from apollo.lenguaje import (
    quitar_acentos,
    singularizar,
    limpiar_concepto,
    normalizar_concepto,
    normalizar_relacion,
)


# ==========================================
# ACENTOS
# ==========================================

def test_quita_acentos():
    assert quitar_acentos("batería") == "bateria"


def test_conserva_la_enie():
    assert quitar_acentos("señal") == "señal"


# ==========================================
# PLURALES
# ==========================================
# parametrize = la misma prueba con muchos ejemplos.

@pytest.mark.parametrize("plural, singular", [
    ("sensores", "sensor"),
    ("computadoras", "computadora"),
    ("redes", "red"),
    ("neuronales", "neuronal"),
    ("luces", "luz"),
    ("leyes", "ley"),
    ("chips", "chip"),
    ("variables", "variable"),
    ("paquetes", "paquete"),
    ("baterias", "bateria"),
    ("motores", "motor"),
    ("imagenes", "imagen"),
])
def test_singulariza_plurales(plural, singular):
    assert singularizar(plural) == singular


@pytest.mark.parametrize("palabra", [
    "gps", "gas", "lunes", "virus", "analisis", "ros", "sensor", "pi",
])
def test_no_cambia_palabras_que_no_son_plurales(palabra):
    assert singularizar(palabra) == palabra


# ==========================================
# CONCEPTOS
# ==========================================

@pytest.mark.parametrize("texto", [
    "batería",
    "bateria",
    "Las Baterías",
    "  la   batería ",
    "¿batería?",
])
def test_formas_distintas_dan_el_mismo_concepto(texto):
    assert normalizar_concepto(texto) == "bateria"


def test_normaliza_conceptos_de_varias_palabras():
    assert normalizar_concepto("Las Redes Neuronales") == "red neuronal"


def test_limpiar_conserva_acentos():
    assert limpiar_concepto("¿La Batería?") == "batería"


# ==========================================
# RELACIONES
# ==========================================

@pytest.mark.parametrize("forma, oficial", [
    ("mide", "mide"),
    ("miden", "mide"),
    ("medir", "mide"),
    ("se comunican con", "se comunica con"),
    ("Está formada por", "está formado por"),
    ("son", "es"),
])
def test_conjugaciones_dan_la_misma_relacion(forma, oficial):
    assert normalizar_relacion(forma) == oficial


# ==========================================
# ERRORES DE ESCRITURA
# ==========================================

from apollo.lenguaje import distancia_edicion


@pytest.mark.parametrize("a, b, distancia", [
    ("sensor", "sensor", 0),     # iguales
    ("gato", "pato", 1),         # cambiar una letra
    ("sensr", "sensor", 1),      # falta una letra
    ("sensoor", "sensor", 1),    # sobra una letra
    ("sensro", "sensor", 1),     # dos letras intercambiadas
    ("casa", "perro", 5),
])
def test_distancia_edicion(a, b, distancia):
    assert distancia_edicion(a, b) == distancia


# ==========================================
# CONTRACCIONES
# ==========================================

from apollo.lenguaje import expandir_contracciones


def test_expande_al_y_del():
    assert expandir_contracciones("pertenece al rover") == "pertenece a el rover"
    assert expandir_contracciones("depende del motor") == "depende de el motor"


def test_no_rompe_palabras_que_contienen_al():
    assert expandir_contracciones("sensor ambiental") == "sensor ambiental"


# ==========================================
# PREGUNTAS GENERADAS
# ==========================================

from apollo.lenguaje import preguntas_de_relacion


def test_genera_preguntas_de_cada_relacion():
    preguntas = dict(preguntas_de_relacion())

    assert preguntas["qué mide"] == "mide"
    assert preguntas["qué tiene"] == "tiene"
    assert preguntas["con qué se comunica"] == "se comunica con"
    assert preguntas["a qué pertenece"] == "pertenece a"
    assert preguntas["de qué depende"] == "depende de"