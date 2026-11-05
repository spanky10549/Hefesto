"""
Pruebas automáticas de APOLLO.

Cada prueba usa un diccionario temporal y vacío, así que
NUNCA toca el diccionario real de HEFESTO.

Para correrlas, desde la carpeta Cerebro:
    python -m pytest
"""

import pytest

from apollo import conocimiento as apollo


# ==========================================
# PREPARACIÓN: diccionario temporal
# ==========================================

@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


# ==========================================
# NORMALIZACIÓN
# ==========================================

def test_normalizar_quita_espacios_y_mayusculas():
    assert apollo.normalizar_concepto("  Raspberry   PI ") == "raspberry pi"


# ==========================================
# ASOCIACIONES
# ==========================================

def test_aprender_palabra_y_buscarla():
    apollo.aprender_palabra("raspberry pi", "una computadora")

    assert apollo.buscar_palabra("raspberry pi") == ["una computadora"]


def test_no_duplica_asociaciones():
    apollo.aprender_palabra("sensor", "un dispositivo")
    apollo.aprender_palabra("sensor", "un dispositivo")

    assert apollo.buscar_palabra("sensor") == ["un dispositivo"]


# ==========================================
# SINÓNIMOS
# ==========================================

def test_sinonimo_se_guarda_en_el_archivo():
    # Esta prueba habría detectado el bug original de los sinónimos.
    apollo.aprender_palabra("raspberry pi", "una computadora")
    apollo.aprender_sinonimo("raspberry pi", "frambuesa")

    entrada = apollo.buscar_entrada("frambuesa")

    assert entrada is not None
    assert entrada["palabra"] == "raspberry pi"


def test_no_acepta_sinonimo_de_concepto_desconocido():
    apollo.aprender_sinonimo("algo inexistente", "otro nombre")

    assert apollo.buscar_entrada("otro nombre") is None


# ==========================================
# RELACIONES
# ==========================================

def test_aprender_y_buscar_relacion():
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensor")

    relaciones = apollo.buscar_relaciones("raspberry pi")

    assert relaciones == [
        {"relacion": "se comunica con", "objetivo": "sensor"}
    ]


def test_rechaza_relacion_no_valida():
    apollo.aprender_relacion("sensor", "baila con", "motor")

    assert apollo.buscar_relaciones("sensor") == []


def test_buscar_relaciones_por_sinonimo():
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensor")
    apollo.aprender_sinonimo("raspberry pi", "rpi")

    relaciones = apollo.buscar_relaciones("rpi")

    assert relaciones[0]["objetivo"] == "sensor"


# ==========================================
# CAMINOS ENTRE CONCEPTOS
# ==========================================

def test_camino_indirecto():
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensor")
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    camino = apollo.buscar_camino("raspberry pi", "temperatura")

    assert [paso["destino"] for paso in camino] == ["sensor", "temperatura"]


def test_camino_inexistente_devuelve_none():
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    assert apollo.buscar_camino("temperatura", "sensor") is None


def test_camino_con_ciclo_no_se_traba():
    apollo.aprender_relacion("a", "depende de", "b")
    apollo.aprender_relacion("b", "depende de", "a")

    assert apollo.buscar_camino("a", "z") is None


# ==========================================
# INTERPRETACIÓN DE FRASES
# ==========================================

def test_extraer_relacion_de_una_frase():
    resultado = apollo.extraer_relacion("el sensor mide la temperatura")

    assert resultado == ("sensor", "mide", "temperatura")


def test_separar_origen_destino_de_varias_palabras():
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensor")
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    origen, destino = apollo.separar_origen_destino("raspberry pi temperatura")

    assert (origen, destino) == ("raspberry pi", "temperatura")


def test_separar_origen_destino_con_barra():
    origen, destino = apollo.separar_origen_destino("raspberry pi | temperatura")

    assert (origen, destino) == ("raspberry pi", "temperatura")


# ==========================================
# NORMALIZACIÓN EN ACCIÓN
# ==========================================

def test_plural_y_singular_son_el_mismo_concepto():
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    assert apollo.buscar_relaciones("sensores")[0]["objetivo"] == "temperatura"


def test_acentos_no_importan():
    apollo.aprender_relacion("batería", "produce", "energía")

    assert apollo.buscar_relaciones("bateria")[0]["objetivo"] == "energía"


def test_frase_en_plural_se_entiende():
    resultado = apollo.extraer_relacion("Los sensores miden la temperatura.")

    assert resultado == ("sensores", "mide", "temperatura")


def test_frase_conserva_acentos():
    resultado = apollo.extraer_relacion("la batería produce energía")

    assert resultado == ("batería", "produce", "energía")


def test_no_duplica_relacion_escrita_distinto():
    apollo.aprender_relacion("sensor", "mide", "temperatura")
    apollo.aprender_relacion("los sensores", "miden", "la temperatura")

    assert len(apollo.buscar_relaciones("sensor")) == 1


def test_camino_con_plurales():
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensores")
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    camino = apollo.buscar_camino("raspberry pi", "temperatura")

    assert camino is not None
    assert len(camino) == 2


# ==========================================
# SUGERENCIAS POR ERRORES DE ESCRITURA
# ==========================================

def test_sugiere_concepto_mal_escrito():
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensor")

    assert apollo.sugerir_concepto("raspbery pi") == "raspberry pi"
    assert apollo.sugerir_concepto("sensro") == "sensor"


def test_no_sugiere_si_ya_lo_conoce():
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    assert apollo.sugerir_concepto("sensores") is None


def test_no_sugiere_algo_muy_distinto():
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    assert apollo.sugerir_concepto("bicicleta") is None


def test_separar_origen_destino_con_errores_de_escritura():
    apollo.aprender_relacion("raspberry pi", "se comunica con", "sensor")
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    origen, destino = apollo.separar_origen_destino("raspberri pi temperatur")

    assert (origen, destino) == ("raspberri pi", "temperatur")