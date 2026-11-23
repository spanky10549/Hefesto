"""
Pruebas de la plática: entender intenciones (incluida "crea una rutina
llamada…"), normalizar pasos dichos a tu manera, confirmar antes de
cambiar algo, aprender preguntándote, seguir el hilo y recordarte.
"""

import random

import pytest

from conversacion.intenciones import entender, normalizar_pasos, limpiar, es_si, es_no
from conversacion.personalidad import Voz, FRASES
from conversacion.perfil import Perfil
from conversacion.platica import Platica
import conversacion.perfil as modulo_perfil


# ==========================================
# INTENCIONES (funciones puras)
# ==========================================

def intencion(texto, rutinas=()):
    return entender(texto, rutinas)["intencion"]


@pytest.mark.parametrize("texto, esperada", [
    ("hola", "saludo"),
    ("hefesto, hola", "saludo"),
    ("buenas noches", "saludo"),
    ("adiós", "despedida"),
    ("gracias!", "gracias"),
    ("Oye, ¿cómo andas?", "como_estas"),
    ("¿quién eres?", "quien_eres"),
    ("¿qué puedes hacer?", "que_puedes_hacer"),
    ("me llamo juan", "mi_nombre"),
    ("¿cómo me llamo?", "cual_es_mi_nombre"),
    ("me gusta Horizon", "me_gusta"),
    ("¿qué me gusta?", "que_me_gusta"),
    ("¿qué sabes de los pingüinos?", "definir"),
    ("explícame qué es un tensor", "definir"),
    ("¿el pingüino puede volar?", "pregunta"),
    ("¿cuánto es 5 × 35?", "calcular"),
    ("5*35+2", "calcular"),
    ("revisa https://paypa1.com", "revisar_links"),
    ("aprende que el sol es una estrella", "aprender"),
    ("¿qué rutinas tengo?", "listar_rutinas"),
    ("borra la rutina checa todo", "borrar_rutina"),
    ("encárgate de revisar los recursos", "tarea"),
    ("el tensor es un objeto matemático", "libre"),
])
def test_intenciones(texto, esperada):
    assert intencion(texto) == esperada


def test_el_nombre_de_una_rutina_es_una_tarea():
    assert intencion("Checa todo", ["checa todo"]) == "tarea"


def test_limpiar_muletillas():
    assert limpiar("Oye, hefesto, ¿qué es X?") == "qué es X"


def test_definir_quita_el_articulo():
    assert entender("¿qué sabes de los pingüinos?")["concepto"] == "pingüinos"


# ==========================================
# CREAR RUTINAS DICHO A TU MANERA
# ==========================================

@pytest.mark.parametrize("texto, nombre, pasos", [
    ("crea una rutina llamada comprobación de estados, que revise los recursos, los errores y el entorno",
     "comprobación de estados", "revisa los recursos, revisa los errores, revisa el entorno"),
    ("hazme una rutina que se llame buenos días y que haga un respaldo y revise los recursos",
     "buenos días", "haz un respaldo, revisa los recursos"),
    ("quiero que cuando te diga checa todo revises los recursos y los errores",
     "checa todo", "revisa los recursos, revisa los errores"),
    ("crea una rutina llamada guardia: que si hay errores revise los incidentes",
     "guardia", "si hay errores revisa los incidentes"),
])
def test_crear_rutina(texto, nombre, pasos):
    r = entender(texto)
    assert r["intencion"] == "crear_rutina"
    assert (r["nombre"], r["pasos"]) == (nombre, pasos)


def test_agregar_a_rutina():
    r = entender("agrega a la rutina checa todo que también respalde")
    assert (r["intencion"], r["nombre"], r["pasos"]) == ("agregar_a_rutina", "checa todo", "respalda")


@pytest.mark.parametrize("texto, esperado", [
    ("revise los recursos, los errores y el entorno", "revisa los recursos, revisa los errores, revisa el entorno"),
    ("que calcule 2 + 2", "calcula 2 + 2"),
    ("que haga revisar los recursos", "revisa los recursos"),
    ("define tensor y si falla calcula 2 + 2", "define tensor y si falla calcula 2 + 2"),
    ("checa todo y respalda", "checa todo, respalda"),
])
def test_normalizar_pasos(texto, esperado):
    assert normalizar_pasos(texto, ["checa todo"]) == esperado


def test_si_y_no():
    assert es_si("Sí") and es_si("dale") and es_si("va")
    assert es_no("nel") and es_no("No") and not es_si("tal vez")


# ==========================================
# PERSONALIDAD Y PERFIL
# ==========================================

def test_la_voz_varia_pero_es_reproducible():
    voz = Voz(random.Random(1))
    otra = Voz(random.Random(1))
    assert voz.di("saludo", nombre="Juan") == otra.di("saludo", nombre="Juan")
    assert ", Juan" in voz.di("saludo", nombre="Juan")


def test_todas_las_frases_se_pueden_armar():
    voz = Voz(random.Random(0))
    for situacion, frases in FRASES.items():
        for frase in frases:
            frase.format(nombre="", concepto="x", frase="y")


def test_perfil(tmp_path):
    ruta = str(tmp_path / "perfil.json")
    p = Perfil(ruta)
    p.poner_nombre("  juan  pérez ")
    assert p.agregar_gusto("Horizon") is True
    assert p.agregar_gusto("horizon") is False      # sin repetir
    otra = Perfil(ruta)
    assert otra.nombre == "Juan Pérez"
    assert otra.gustos == ["Horizon"]
    assert otra.quitar_gusto("HORIZON") is True


def test_las_pruebas_no_tocan_el_perfil_real(tmp_path):
    assert modulo_perfil.ARCHIVO_PERFIL.startswith(str(tmp_path.parent))


# ==========================================
# PLATICAR (con el ecosistema de verdad)
# ==========================================

@pytest.fixture
def platica(tmp_path, monkeypatch):
    import apollo.conocimiento as conocimiento
    monkeypatch.setattr(conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json"))
    from gaia import crear_ecosistema
    return Platica(crear_ecosistema(), voz=Voz(random.Random(0)))


def di(platica, texto):
    return "\n".join(platica.responder(texto))


def test_saludo_con_nombre(platica):
    di(platica, "me llamo juan")
    assert "Juan" in di(platica, "hola")
    assert di(platica, "¿cómo me llamo?") == "Te llamas Juan."


def test_como_estas_usa_datos_reales(platica):
    assert "RAM" in di(platica, "¿cómo andas?")


def test_aprende_preguntando(platica):
    assert "¿" in di(platica, "¿qué es un tensor?")          # no sabe y pregunta
    assert "tensor es objeto matemático" in di(platica, "es un objeto matemático")
    assert "Tensor" in di(platica, "¿qué es un tensor?")      # ya lo sabe


def test_otro_dia_me_lo_explicas(platica):
    di(platica, "¿qué es un tensor?")
    assert "otro día" in di(platica, "no sé")


def test_razona_y_sigue_el_hilo(platica):
    di(platica, "el pingüino es un ave")
    di(platica, "las aves pueden volar")
    assert di(platica, "¿el pingüino puede volar?").startswith("Sí, el pingüino puede volar. Lo deduje")
    di(platica, "el pingüino no puede volar")
    assert di(platica, "¿y puede volar?").startswith("No, el pingüino no puede volar")
    assert di(platica, "¿y puede nadar?").startswith("No lo sé")


def test_contradiccion_pregunta_antes(platica):
    di(platica, "la raspberry pi pertenece a juan")
    assert "choca" in di(platica, "la raspberry pi pertenece a angy")
    assert "corregí" in di(platica, "sí")


def test_crear_rutina_confirma_y_funciona(platica):
    respuesta = di(platica, "crea una rutina llamada comprobación de estados, que revise los recursos y los errores")
    assert "1. revisa los recursos" in respuesta and "(sí / no)" in respuesta
    assert "guardé" in di(platica, "sí")

    resultado = di(platica, "comprobación de estados")
    assert "[ARTEMIS]" in resultado and "[TABRIS]" in resultado


def test_decir_que_no_cancela(platica):
    di(platica, "crea una rutina llamada x, que revise los recursos")
    di(platica, "no")
    assert "Todavía no tienes rutinas" in di(platica, "¿qué rutinas tengo?")


def test_cambiar_de_tema_olvida_la_pregunta(platica):
    di(platica, "crea una rutina llamada x, que revise los recursos")
    assert "175" in di(platica, "¿cuánto es 5 × 35?")       # no era sí ni no
    assert "Todavía no tienes rutinas" in di(platica, "¿qué rutinas tengo?")


def test_rutina_con_condicion_dicha_a_tu_manera(platica):
    di(platica, "crea una rutina llamada guardia, que si hay errores revise los incidentes")
    assert "guardé" in di(platica, "sí")
    assert "[HADES] lo salté" in di(platica, "guardia")


def test_rutina_con_pasos_que_no_entiende(platica):
    di(platica, "crea una rutina llamada fiesta, que baile salsa")
    assert "No pude guardarla" in di(platica, "sí")


def test_agregar_y_borrar_rutina(platica):
    di(platica, "crea una rutina llamada checa todo, que revise los recursos")
    di(platica, "sí")
    di(platica, "agrega a la rutina checa todo que también revise los errores")
    assert "2 pasos" in di(platica, "sí")
    di(platica, "borra la rutina checa todo")
    assert "olvidé" in di(platica, "sí")


def test_tarea_dicha_directo(platica):
    resultado = di(platica, "revisa los recursos y los errores")
    assert "[ARTEMIS]" in resultado and "[TABRIS]" in resultado


def test_cuentas_y_links(platica):
    assert di(platica, "¿cuánto es 1/3 + 1?").startswith("1 ÷ 3 + 1 = 4/3")
    assert "🔴" in di(platica, "revisa https://paypa1.com/login")


def test_no_entiende(platica):
    assert di(platica, "baila salsa") in FRASES["no_entendi"]


def test_despedida_termina(platica):
    di(platica, "adiós")
    assert platica.terminada is True