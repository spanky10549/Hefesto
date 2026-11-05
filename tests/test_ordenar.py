"""
Pruebas de ordenar el diccionario y de guardar en singular.
"""

import pytest

from apollo import conocimiento as apollo
from apollo import razonamiento


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


def entradas():
    return apollo.cargar_diccionario()["palabras"]


# ==========================================
# GUARDAR EN SINGULAR
# ==========================================

def test_sujeto_se_guarda_en_singular():
    apollo.aprender_relacion("las aves", "pueden", "volar")

    assert entradas()[0]["palabra"] == "ave"


def test_objeto_normal_se_respeta():
    apollo.aprender_relacion("ave", "tiene", "plumas")

    assert apollo.buscar_relaciones("ave")[0]["objetivo"] == "plumas"


def test_categoria_se_guarda_en_singular():
    apollo.aprender_relacion("computadoras", "son", "máquinas")

    assert apollo.buscar_relaciones("computadora")[0]["objetivo"] == "máquina"


def test_la_explicacion_ya_no_dice_maquinas():
    apollo.aprender_palabra("raspberry pi", "una computadora")
    apollo.aprender_palabra("las computadoras", "máquinas")
    apollo.aprender_relacion("las máquinas", "producen", "calor")

    _, cadena = razonamiento.responder("raspberry pi", "produce", "calor")

    assert [paso["destino"] for paso in cadena] == ["computadora", "máquina", "calor"]


# ==========================================
# ORDENAR DATOS ANTIGUOS
# ==========================================

def guardar_tal_cual(palabras):
    """Simula un diccionario viejo, con plurales y repetidos."""
    apollo.guardar_diccionario({"palabras": palabras})


def test_une_entradas_repetidas():
    guardar_tal_cual([
        {"palabra": "sensor", "asociaciones": [], "relaciones": [
            {"relacion": "mide", "objetivo": "temperatura"}]},
        {"palabra": "sensores", "asociaciones": [], "relaciones": [
            {"relacion": "mide", "objetivo": "humedad"},
            {"relacion": "mide", "objetivo": "temperatura"}]},
    ])

    r = apollo.ordenar_diccionario()

    assert r["unidas"] == 1
    assert len(entradas()) == 1
    assert len(apollo.buscar_relaciones("sensor")) == 2   # sin duplicar temperatura


def test_pasa_nombres_a_singular():
    guardar_tal_cual([
        {"palabra": "máquinas", "asociaciones": [], "relaciones": [
            {"relacion": "produce", "objetivo": "calor"}]},
    ])

    r = apollo.ordenar_diccionario()

    assert r["renombradas"] == [("máquinas", "máquina")]
    assert entradas()[0]["palabra"] == "máquina"


def test_no_pierde_nada_al_ordenar():
    guardar_tal_cual([
        {"palabra": "raspberry pi", "asociaciones": ["una computadora"],
         "sinonimos": ["rpi"],
         "relaciones": [{"relacion": "usa", "objetivo": "python", "negada": True}]},
        {"palabra": "raspberry pi", "asociaciones": ["una placa"]},
    ])

    apollo.ordenar_diccionario()

    entrada = entradas()[0]
    assert entrada["asociaciones"] == ["una computadora", "una placa"]
    assert entrada["sinonimos"] == ["rpi"]
    assert entrada["relaciones"] == [
        {"relacion": "usa", "objetivo": "python", "negada": True}
    ]


def test_ordenar_dos_veces_no_cambia_nada():
    apollo.aprender_relacion("sensor", "mide", "luz")
    apollo.ordenar_diccionario()
    antes = entradas()

    r = apollo.ordenar_diccionario()

    assert entradas() == antes
    assert (r["unidas"], r["renombradas"]) == (0, [])