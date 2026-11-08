"""
Pruebas de la redacción en español (funciones puras, sin diccionario).
"""

import pytest

from conversacion.redaccion import es_femenino, un, el, unir, oracion, redactar_definicion


# ==========================================
# GÉNERO Y ARTÍCULOS
# ==========================================

@pytest.mark.parametrize("concepto, articulo", [
    ("computadora", "una computadora"),
    ("sensor", "un sensor"),
    ("ave", "un ave"),                    # a tónica: "un ave", no "una ave"
    ("canción", "una canción"),
    ("problema", "un problema"),          # excepción
    ("mano", "una mano"),                 # excepción
    ("computadora de placa única", "una computadora de placa única"),
])
def test_articulo_indefinido(concepto, articulo):
    assert un(concepto) == articulo


def test_articulo_definido():
    assert el("temperatura") == "la temperatura"
    assert el("sensor") == "el sensor"
    assert el("agua") == "el agua"


def test_pista_de_genero_para_palabras_ambiguas():
    # "raspberry pi" no da señales, pero si es una computadora, es "la".
    assert el("raspberry pi") == "el raspberry pi"
    assert el("raspberry pi", pista="computadora") == "la raspberry pi"


def test_la_pista_no_gana_a_una_terminacion_clara():
    assert es_femenino("sensor", pista="computadora") is False


# ==========================================
# LISTAS Y ORACIONES
# ==========================================

@pytest.mark.parametrize("elementos, texto", [
    ([], ""),
    (["luz"], "luz"),
    (["luz", "sonido"], "luz y sonido"),
    (["luz", "sonido", "movimiento"], "luz, sonido y movimiento"),
    (["padres", "hijos"], "padres e hijos"),     # y → e antes de "i"/"hi"
    (["agua", "hielo"], "agua y hielo"),         # pero no antes de "hie" (suena "ye")
])
def test_unir(elementos, texto):
    assert unir(elementos) == texto


def test_unir_con_o():
    assert unir(["siete", "ocho"], "o") == "siete u ocho"


def test_oracion():
    assert oracion("puede volar") == "Puede volar."


# ==========================================
# DEFINICIÓN COMPLETA
# ==========================================

def datos(**cambios):
    base = {
        "concepto": "pingüino", "conocido": True, "sinonimos": [],
        "categorias": [], "categorias_deducidas": [], "hace": {},
        "no_hace": {}, "hereda": [], "ejemplos": [], "lo_mencionan": [],
        "pistas_genero": {},
    }
    base.update(cambios)
    return base


def test_redacta_la_excepcion_con_pero():
    texto = redactar_definicion(datos(
        categorias=["ave"],
        hace={"puede": ["nadar"]},
        no_hace={"puede": ["volar"]},
        hereda=[("ave", "tiene", "plumas")],
    ))

    assert texto == (
        "Pingüino: Es un ave. Puede nadar, pero no puede volar. "
        "Por ser ave, tiene plumas."
    )


def test_redacta_preposiciones_con_articulo():
    texto = redactar_definicion(datos(
        concepto="sensor",
        hace={"pertenece a": ["rover"]},
        lo_mencionan=[("raspberry pi", "se comunica con")],
        pistas_genero={"raspberry pi": "computadora"},
    ))

    assert "Pertenece al rover." in texto
    assert "La raspberry pi se comunica con el sensor." in texto


def test_concepto_desconocido():
    assert redactar_definicion(datos(conocido=False, concepto="unicornio")) == (
        "Todavía no sé qué es unicornio."
    )


# ==========================================
# RESUMIR CUANDO HAY MUCHO (WordNet)
# ==========================================

def test_resume_cadenas_largas_de_categorias():
    texto = redactar_definicion(datos(
        concepto="perro",
        categorias=["cánido"],
        categorias_deducidas=[
            ("mamífero", "cánido"), ("vertebrado", "mamífero"), ("animal", "vertebrado"),
            ("organismo", "animal"), ("ser", "organismo"),
        ],
    ))

    assert "Por eso también es un mamífero, un vertebrado, un animal, un organismo, entre otras cosas." in texto


def test_recorta_listas_de_ejemplos():
    texto = redactar_definicion(datos(
        concepto="árbol",
        ejemplos=[f"árbol{i}" for i in range(20)],
    ))

    assert "y 12 más." in texto