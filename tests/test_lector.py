"""
Pruebas del lector de documentos.
"""

import pytest

from apollo import conocimiento as apollo
from apollo.lector import (
    dividir_oraciones,
    separar_ideas,
    interpretar_oracion,
    leer_texto,
    leer_archivo,
    guardar_hechos,
)


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    """Antes de cada prueba, APOLLO usa un archivo nuevo y vacío."""
    archivo = tmp_path / "diccionario_prueba.json"
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(archivo))


# ==========================================
# DIVIDIR
# ==========================================

def test_divide_en_oraciones():
    texto = "El sensor mide luz. El motor mueve ruedas!\nLa batería produce calor; fin"

    assert dividir_oraciones(texto) == [
        "El sensor mide luz", "El motor mueve ruedas",
        "La batería produce calor", "fin",
    ]


def test_no_corta_numeros_decimales():
    assert dividir_oraciones("El voltaje es de 3.5 V. Listo.") == [
        "El voltaje es de 3.5 V", "Listo",
    ]


def test_separa_ideas_unidas_por_pero():
    assert separar_ideas("Los pingüinos son aves, pero no pueden volar") == [
        "Los pingüinos son aves", "no pueden volar",
    ]


# ==========================================
# INTERPRETAR
# ==========================================

def test_entiende_una_relacion():
    [hecho] = interpretar_oracion("Los sensores miden la temperatura")

    assert (hecho["tipo"], hecho["relacion"], hecho["objeto"]) == (
        "relacion", "mide", "temperatura"
    )


def test_entiende_listas():
    hechos = interpretar_oracion("El sensor detecta luz, sonido y movimiento")

    assert [h["objeto"] for h in hechos] == ["luz", "sonido", "movimiento"]


def test_entiende_categorias():
    [hecho] = interpretar_oracion("La Raspberry Pi es una computadora")

    assert hecho == {"tipo": "categoria", "sujeto": "raspberry pi", "objeto": "computadora"}


def test_entiende_negaciones():
    [hecho] = interpretar_oracion("Además, el pingüino no puede volar")

    assert hecho["negada"] is True
    assert hecho["sujeto"] == "pingüino"


def test_entiende_sinonimos():
    [hecho] = interpretar_oracion("RPi también se conoce como Raspberry Pi")

    assert hecho["tipo"] == "sinonimo"


@pytest.mark.parametrize("oracion", [
    "Hoy hace un día muy bonito",
    "El voltaje es de 3.5 V",
    "Focus será un ecosistema",
])
def test_no_adivina_lo_que_no_entiende(oracion):
    assert interpretar_oracion(oracion) == []


def test_leer_texto_separa_lo_entendido():
    lectura = leer_texto("El sensor mide luz. Hoy llueve mucho.")

    assert len(lectura["hechos"]) == 1
    assert lectura["no_entendidas"] == ["Hoy llueve mucho"]


def test_leer_texto_no_guarda_nada():
    leer_texto("El sensor mide luz.")

    assert apollo.buscar_relaciones("sensor") == []


def test_leer_archivo(tmp_path):
    archivo = tmp_path / "notas.txt"
    archivo.write_text("Las baterías producen energía.", encoding="utf-8")

    assert len(leer_archivo(str(archivo))["hechos"]) == 1


# ==========================================
# GUARDAR
# ==========================================

def test_guardar_aprende_todo():
    lectura = leer_texto(
        "Las computadoras necesitan electricidad. "
        "La Raspberry Pi es una computadora. "
        "RPi es sinónimo de Raspberry Pi."
    )

    guardar_hechos(lectura["hechos"])

    from apollo import razonamiento
    respuesta, _ = razonamiento.responder("rpi", "necesita", "electricidad")
    assert respuesta == "sí"


def test_guardar_no_pisa_lo_que_ya_sabe():
    apollo.aprender_relacion("pingüino", "puede", "volar")

    resultados = guardar_hechos(leer_texto("El pingüino no puede volar.")["hechos"])

    assert resultados[0][1]["estado"] == "contradiccion"
    assert len(apollo.buscar_relaciones("pingüino")) == 1


def test_leer_dos_veces_no_duplica():
    hechos = leer_texto("El sensor mide luz.")["hechos"]

    guardar_hechos(hechos)
    resultados = guardar_hechos(hechos)

    assert resultados[0][1]["estado"] == "ya_sabia"