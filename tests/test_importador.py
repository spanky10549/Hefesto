"""
Pruebas de importar conocimiento en bloque (como WordNet).
No necesitan internet ni WordNet: usan entradas de ejemplo.
"""

import pytest

from apollo import conocimiento as apollo
from apollo import razonamiento
from apollo.importador import importar


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


ENTRADAS = [
    {"palabra": "perro", "asociaciones": ["cánido"], "sinonimos": ["can"], "relaciones": []},
    {"palabra": "cánido", "asociaciones": ["mamífero"], "sinonimos": [], "relaciones": []},
    {"palabra": "mamífero", "asociaciones": ["animal"], "sinonimos": [], "relaciones": []},
    {"palabra": "pluma", "asociaciones": [], "sinonimos": [],
     "relaciones": [{"relacion": "forma parte de", "objetivo": "ave"}]},
]


def test_importa_conceptos_nuevos():
    r = importar(ENTRADAS)

    assert (r["nuevos"], r["ampliados"]) == (4, 0)
    assert apollo.buscar_entrada("can")["palabra"] == "perro"


def test_razona_con_lo_importado():
    importar(ENTRADAS)

    respuesta, cadena = razonamiento.responder("can", "es", "animal")

    assert respuesta == "sí"
    assert len(cadena) == 3


def test_se_mezcla_con_lo_que_ya_sabia():
    apollo.aprender_relacion("perro", "puede", "ladrar")
    apollo.aprender_palabra("pingüino", "un ave")

    r = importar(ENTRADAS)

    # "perro" ya existía: no se duplica, gana su categoría y su sinónimo.
    assert (r["nuevos"], r["ampliados"]) == (3, 1)
    assert apollo.buscar_entrada("can")["asociaciones"] == ["cánido"]
    assert apollo.buscar_relaciones("perro") == [{"relacion": "puede", "objetivo": "ladrar"}]

    # Y lo que le enseñaste se conecta con lo importado.
    respuesta, _ = razonamiento.responder("perro", "es", "animal")
    assert respuesta == "sí"


def test_amplia_sin_duplicar():
    importar(ENTRADAS)

    r = importar([
        {"palabra": "perro", "asociaciones": ["cánido", "mascota"],
         "sinonimos": ["can", "chucho"], "relaciones": []},
    ])

    assert (r["nuevos"], r["ampliados"]) == (0, 1)
    entrada = apollo.buscar_entrada("perro")
    assert entrada["asociaciones"] == ["cánido", "mascota"]
    assert entrada["sinonimos"] == ["can", "chucho"]


def test_importar_dos_veces_no_cambia_nada():
    importar(ENTRADAS)

    r = importar(ENTRADAS)

    assert (r["nuevos"], r["ampliados"]) == (0, 0)