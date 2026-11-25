"""
Pruebas de comprension.py y frases.py: entender aunque no lo digas
"bien" (abreviaciones, faltas, varias cosas, "otra vez", "mándalo",
"¿quisiste decir…?") y aprender tu forma de decir las cosas.
"""

import random

import pytest

from conversacion.comprension import (
    expandir_abreviaciones, corregir, corregir_palabra, vocabulario,
    partir, resolver_referencias, sugerir,
)
from conversacion.frases import Frases, llave
from conversacion.intenciones import entender


# ==========================================
# ABREVIACIONES Y ORTOGRAFÍA
# ==========================================

def test_abreviaciones():
    assert expandir_abreviaciones("q ta haciendo") == "que esta haciendo"
    assert expandir_abreviaciones("xq no") == "por que no"


@pytest.mark.parametrize("texto, esperado", [
    ("dnde ta el rober", "donde esta el rover"),
    ("q sensroes tengo", "que sensores tengo"),
    ("como esta la conpu", "como esta la compu"),
    ("hubo erores hoy", "hubo errores hoy"),
    ("haz un respaldoo", "haz un respaldo"),
])
def test_corregir(texto, esperado):
    assert corregir(texto) == esperado


def test_las_palabras_cortas_no_se_tocan():
    assert corregir_palabra("mpa", vocabulario()) == "mpa"


def test_no_inventa_si_nada_se_parece():
    assert corregir_palabra("xilofonista", vocabulario()) == "xilofonista"


def test_conceptos_extra_entran_al_vocabulario():
    assert corregir("el tensr", extra=["tensor"]) == "el tensor"


# ==========================================
# PARTIR EN VARIAS COSAS
# ==========================================

@pytest.mark.parametrize("texto, partes", [
    ("revisa la compu y luego haz un respaldo", ["revisa la compu", "haz un respaldo"]),
    ("conecta el rover, después muéstrame el mapa", ["conecta el rover", "muéstrame el mapa"]),
    ("haz un respaldo y también muéstrame la bitácora", ["haz un respaldo", "muéstrame la bitácora"]),
    ("hola", ["hola"]),
])
def test_partir(texto, partes):
    assert partir(texto) == partes


# ==========================================
# REFERENCIAS
# ==========================================

@pytest.mark.parametrize("texto, cosa, esperado", [
    ("mándalo a 5 5", "rover", "manda el rover a 5 5"),
    ("llévalo a (2, 3)", "rover", "lleva el rover a (2, 3)"),
    ("recárgalo", "rover", "recarga el rover"),
    ("¿y dónde está?", "rover", "donde esta el rover"),
    ("y ahora a 1 1", "rover", "manda el rover a 1 1"),
    ("apágalo", "ruido", "apaga el sensor de ruido"),
    ("mándalo a 5 5", None, None),          # sin saber de qué hablamos, no se adivina
    ("hola", "rover", None),
])
def test_referencias(texto, cosa, esperado):
    assert resolver_referencias(texto, cosa) == esperado


# ==========================================
# ¿QUISISTE DECIR?
# ==========================================

@pytest.mark.parametrize("texto, esperado", [
    ("que sensore traes", "¿qué sensores tengo?"),
    ("donde quedo el robot", "¿dónde está el rover?"),
    ("como esta mi computadora", "¿cómo está la compu?"),
])
def test_sugerir(texto, esperado):
    assert sugerir(texto) == esperado


@pytest.mark.parametrize("texto", ["xyz", "cuál es tu color favorito", ""])
def test_no_sugiere_si_nada_se_parece(texto):
    assert sugerir(texto) is None


# ==========================================
# FRASES APRENDIDAS
# ==========================================

def test_frases_se_guardan(tmp_path):
    ruta = str(tmp_path / "frases.json")
    Frases(ruta).aprender("Checa TODO", "¿cómo está la compu?")
    otra = Frases(ruta)
    assert otra.significado("checa todo!") == "¿cómo está la compu?"
    assert otra.olvidar("checa todo") is True
    assert otra.significado("checa todo") is None
    assert otra.olvidar("checa todo") is False


def test_llave():
    assert llave("¿Cómo   anda la Máquina?") == "como anda la maquina"


# ==========================================
# INTENCIONES NUEVAS
# ==========================================

@pytest.mark.parametrize("texto, intencion", [
    ("otra vez", "otra_vez"),
    ("hazlo de nuevo", "otra_vez"),
    ("¿y ahora?", "otra_vez"),
    ("jajaja", "risa"),
    ("xd", "risa"),
    ("ok", "acuerdo"),
    ("perfecto", "acuerdo"),
    ("mis frases", "listar_frases"),
])
def test_intenciones_cortas(texto, intencion):
    assert entender(texto)["intencion"] == intencion


def test_intencion_ensenar_frase():
    i = entender('cuando diga "checa todo", quiero decir ¿cómo está la compu?')
    assert i == {"intencion": "ensenar_frase", "dicho": "checa todo", "significa": "cómo está la compu"}


def test_intencion_olvidar_frase():
    assert entender("olvida la frase checa todo") == {"intencion": "olvidar_frase", "dicho": "checa todo"}


# ==========================================
# EN LA PLÁTICA
# ==========================================

class HefestoDeJuguete:
    ENTIENDE = ("rover", "conecta", "recursos", "respalda", "autoriza", "desactiva", "sensores", "mapa")

    def __init__(self):
        self.recibidos = []

    def pasar(self, comando):
        self.recibidos.append(comando)
        ok = comando.split()[0] in self.ENTIENDE
        return {"entendio": ok, "salir": False, "lineas": [f"[{comando}]"] if ok else []}


@pytest.fixture
def platica(tmp_path):
    from gaia import crear_ecosistema
    from conversacion.platica import Platica
    from conversacion.personalidad import Voz
    from conversacion.creador import Creador
    return Platica(crear_ecosistema(), voz=Voz(random.Random(0)), creador=Creador(str(tmp_path / "c.json")),
                   puente=HefestoDeJuguete(), frases=Frases(str(tmp_path / "frases.json")))


def di(platica, texto):
    return "\n".join(platica.responder(texto))


def test_corrige_y_avisa(platica):
    respuesta = di(platica, "dnde ta el rober?")
    assert respuesta == "(Entendí: donde esta el rover)\n[rover estado]"


def test_no_corrige_lo_que_ya_se_entendia(platica):
    """'el tensor es…' se aprende tal cual: no se 'corrige' a 'sensor'."""
    di(platica, "el tensor es un objeto matemático")
    assert "tensor" in di(platica, "¿qué es un tensor?").lower()


def test_referencia_al_rover(platica):
    di(platica, "¿dónde está el rover?")
    assert di(platica, "mándalo a 5 5") == "[rover ve a 5 5]"
    assert di(platica, "¿y dónde está?") == "[rover estado]"


def test_referencia_a_un_sensor(platica):
    di(platica, "activa el micrófono")
    assert di(platica, "apágalo") == "[desactiva ruido]"


def test_otra_vez(platica):
    di(platica, "¿cómo está la compu?")
    assert di(platica, "otra vez") == "Va, otra vez: ¿cómo está la compu?\n[recursos]"


def test_otra_vez_sin_nada(platica):
    assert "Todavía no" in di(platica, "otra vez")


def test_varias_cosas(platica):
    respuesta = di(platica, "conecta el rover, después muéstrame el mapa")
    assert platica.hefesto.recibidos == ["conecta el rover", "mapa"]
    assert "▸ conecta el rover" in respuesta and "▸ muéstrame el mapa" in respuesta


def test_varias_cosas_solo_si_todas_se_entienden(platica):
    di(platica, "conecta el rover y luego baila salsa")
    assert "conecta el rover" not in platica.hefesto.recibidos


def test_quisiste_decir_si_y_lo_aprende(platica):
    assert di(platica, "que sensore traes") == "¿Quisiste decir «¿qué sensores tengo?»? (sí / no)"
    respuesta = di(platica, "sí")
    assert "Ya me lo aprendí" in respuesta and "[sensores]" in respuesta

    platica.hefesto.recibidos.clear()
    assert di(platica, "que sensore traes") == "[sensores]"        # ya no pregunta


def test_quisiste_decir_no(platica):
    di(platica, "que sensore traes")
    assert "cuando diga" in di(platica, "no")
    assert platica.frases.todas() == []


def test_ensenar_una_frase(platica):
    assert "voy a entender" in di(platica, "cuando diga checa todo, quiero decir revisa la compu")
    assert di(platica, "checa todo") == "[recursos]"
    assert "«checa todo»" in di(platica, "mis frases")


def test_no_aprende_una_frase_que_tampoco_entiende(platica):
    assert "tampoco lo entiendo" in di(platica, "cuando diga hola, quiero decir baila salsa")
    assert platica.frases.todas() == []


def test_reacciones_cortas(platica):
    from conversacion.personalidad import FRASES
    assert di(platica, "jajaja") in FRASES["risa"]
    assert di(platica, "ok") in FRASES["acuerdo"]