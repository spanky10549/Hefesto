"""
Pruebas del creador: la clave (hash con sal, nunca en texto), reconocer
al creador en la plática, cosas que solo él puede hacer, intentos
fallidos y que no se suba nada secreto.
"""

import json
import random

import pytest

from conversacion.creador import Creador, calcular_hash, MAX_INTENTOS
from conversacion.intenciones import entender
from conversacion.personalidad import Voz
from conversacion.platica import Platica
import conversacion.creador as modulo_creador


CLAVE = "clave-de-prueba-123"


# ==========================================
# LA CLAVE
# ==========================================

def test_guardar_y_verificar(tmp_path):
    c = Creador(str(tmp_path / "c.json"))
    assert c.configurado() is False
    assert c.establecer(CLAVE) is None
    assert c.verificar(CLAVE) is True
    assert c.verificar("otra") is False


def test_la_clave_nunca_se_guarda_en_texto(tmp_path):
    ruta = tmp_path / "c.json"
    Creador(str(ruta)).establecer(CLAVE)
    contenido = ruta.read_text(encoding="utf-8")
    assert CLAVE not in contenido
    assert set(json.loads(contenido)) == {"nombre", "sal", "hash", "vueltas"}


def test_misma_clave_distinto_hash(tmp_path):
    """La sal hace que la misma clave dé hashes distintos."""
    a, b = Creador(str(tmp_path / "a.json")), Creador(str(tmp_path / "b.json"))
    a.establecer(CLAVE)
    b.establecer(CLAVE)
    assert a.hash != b.hash


def test_se_recuerda(tmp_path):
    ruta = str(tmp_path / "c.json")
    Creador(ruta).establecer(CLAVE)
    assert Creador(ruta).verificar(CLAVE) is True


def test_clave_corta(tmp_path):
    assert "caracteres" in Creador(str(tmp_path / "c.json")).establecer("abc")


def test_hash_es_reproducible():
    assert calcular_hash("x", "00" * 16, 1000) == calcular_hash("x", "00" * 16, 1000)


def test_sin_configurar_nada_es_valido(tmp_path):
    assert Creador(str(tmp_path / "c.json")).verificar("") is False


def test_las_pruebas_no_tocan_la_clave_real(tmp_path):
    assert modulo_creador.ARCHIVO_CREADOR.startswith(str(tmp_path.parent))


# ==========================================
# INTENCIONES
# ==========================================

@pytest.mark.parametrize("texto, esperada", [
    ("soy spanky", "soy_creador"),
    ("Soy tu creador", "soy_creador"),
    ("¿quién te creó?", "quien_te_creo"),
    ("¿quién te está desarrollando?", "quien_te_creo"),
    ("cierra sesión", "cerrar_sesion"),
    ("cambia mi clave", "cambiar_clave"),
    ("soy juan", "mi_nombre"),          # otro nombre sigue siendo "me llamo"
])
def test_intenciones(texto, esperada):
    assert entender(texto)["intencion"] == esperada


# ==========================================
# EN LA PLÁTICA
# ==========================================

@pytest.fixture
def platica(tmp_path, monkeypatch):
    import apollo.conocimiento as conocimiento
    monkeypatch.setattr(conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json"))
    from gaia import crear_ecosistema
    return Platica(crear_ecosistema(), voz=Voz(random.Random(0)), creador=Creador(str(tmp_path / "c.json")))


def di(platica, texto):
    return "\n".join(platica.responder(texto))


def configurar(platica):
    di(platica, "soy spanky")
    di(platica, CLAVE)
    di(platica, CLAVE)


def test_quien_te_creo_sin_sesion(platica):
    assert "spanky" in di(platica, "¿quién te creó?")


def test_primera_vez_pide_y_confirma(platica):
    assert "Todavía no tenemos una clave" in di(platica, "soy spanky")
    assert platica.espera_clave is True
    assert "otra vez" in di(platica, CLAVE)
    assert "Guardé nuestra clave" in di(platica, CLAVE)
    assert platica.creador_presente is True
    assert platica.espera_clave is False


def test_primera_vez_no_coinciden(platica):
    di(platica, "soy spanky")
    di(platica, CLAVE)
    assert "No coinciden" in di(platica, "distinta-123")
    assert platica.creador.configurado() is False


def test_clave_corta_pide_otra(platica):
    di(platica, "soy spanky")
    assert "muy corta" in di(platica, "abc")
    assert platica.espera_clave is True


def test_reconoce_y_saluda_al_creador(platica):
    configurar(platica)
    di(platica, "cierra sesión")
    di(platica, "soy spanky")
    assert "Eres tú" in di(platica, CLAVE)
    from conversacion.personalidad import FRASES
    saludos_de_creador = [f.format(nombre=", spanky") for f in FRASES["saludo_creador"]]
    assert di(platica, "hola") in saludos_de_creador
    assert di(platica, "¿quién te creó?").startswith("Tú, spanky")


def test_clave_incorrecta_y_bitacora(platica):
    configurar(platica)
    di(platica, "cierra sesión")
    di(platica, "soy spanky")
    assert "esa no es la clave" in di(platica, "equivocada")
    assert platica.creador_presente is False

    entradas = platica.gaia.pedir("hefesto", "eleuthia", "bitacora")["datos"]["entradas"]
    assert any(e["tipo"] == "clave_incorrecta" for e in entradas)


def test_demasiados_intentos(platica):
    configurar(platica)
    di(platica, "cierra sesión")
    for _ in range(MAX_INTENTOS):
        di(platica, "soy spanky")
        di(platica, "equivocada")
    assert "demasiados intentos" in di(platica, "soy spanky")
    assert platica.espera_clave is False


def test_borrar_rutina_solo_el_creador(platica):
    di(platica, "crea una rutina llamada x, que revise los recursos")
    di(platica, "sí")
    configurar(platica)
    di(platica, "cierra sesión")

    assert "solo lo puede hacer mi creador" in di(platica, "borra la rutina x")

    di(platica, "soy spanky")
    di(platica, CLAVE)
    di(platica, "borra la rutina x")
    assert "olvidé" in di(platica, "sí")


def test_sin_clave_configurada_cualquiera_puede(platica):
    """Mientras no haya creador configurado, nada se bloquea."""
    di(platica, "crea una rutina llamada x, que revise los recursos")
    di(platica, "sí")
    di(platica, "borra la rutina x")
    assert "olvidé" in di(platica, "sí")


def test_cambiar_clave(platica):
    configurar(platica)
    di(platica, "cambia mi clave")
    di(platica, "nueva-clave-456")
    di(platica, "nueva-clave-456")
    assert platica.creador.verificar("nueva-clave-456") is True
    assert platica.creador.verificar(CLAVE) is False


def test_cambiar_clave_sin_sesion(platica):
    configurar(platica)
    di(platica, "cierra sesión")
    assert "solo lo puede hacer mi creador" in di(platica, "cambia mi clave")