"""
Pruebas de la base de datos SQLite y de la migración desde JSON.
"""

import json
import os
import sqlite3

import pytest

from apollo import conocimiento as apollo


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    """Cada prueba trabaja en su propia carpeta temporal."""
    monkeypatch.setattr(
        apollo, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json")
    )
    return tmp_path


DICCIONARIO_VIEJO = {
    "palabras": [
        {"palabra": "raspberry pi", "asociaciones": ["una computadora"],
         "sinonimos": ["rpi", "frambuesa"],
         "relaciones": [{"relacion": "se comunica con", "objetivo": "sensor"}]},
        {"palabra": "pingüino", "asociaciones": ["un ave"],
         "relaciones": [{"relacion": "puede", "objetivo": "volar", "negada": True}]},
    ]
}


def escribir_json_viejo(carpeta):
    (carpeta / "diccionario_hefesto.json").write_text(
        json.dumps(DICCIONARIO_VIEJO, ensure_ascii=False), encoding="utf-8"
    )


# ==========================================
# MIGRACIÓN
# ==========================================

def test_migra_el_json_la_primera_vez(carpeta):
    escribir_json_viejo(carpeta)

    diccionario = apollo.cargar_diccionario()

    assert os.path.exists(carpeta / "diccionario_hefesto.db")
    assert [e["palabra"] for e in diccionario["palabras"]] == ["raspberry pi", "pingüino"]


def test_la_migracion_no_pierde_nada(carpeta):
    escribir_json_viejo(carpeta)

    apollo.cargar_diccionario()

    assert apollo.buscar_entrada("frambuesa")["palabra"] == "raspberry pi"
    assert apollo.buscar_relaciones("rpi") == [
        {"relacion": "se comunica con", "objetivo": "sensor"}
    ]
    assert apollo.buscar_relaciones("pingüino", negadas=True) == [
        {"relacion": "puede", "objetivo": "volar", "negada": True}
    ]


def test_no_borra_el_json(carpeta):
    escribir_json_viejo(carpeta)

    apollo.cargar_diccionario()

    assert os.path.exists(carpeta / "diccionario_hefesto.json")


def test_migra_solo_una_vez(carpeta):
    escribir_json_viejo(carpeta)
    apollo.cargar_diccionario()
    apollo.aprender_relacion("sensor", "mide", "luz")

    # Aunque el JSON siga ahí, ya manda la base de datos.
    assert apollo.migrar_desde_json() is False
    assert apollo.buscar_relaciones("sensor") != []


def test_sin_json_empieza_vacio(carpeta):
    assert apollo.cargar_diccionario() == {"palabras": []}


# ==========================================
# LA BASE DE DATOS POR DENTRO
# ==========================================

def test_se_puede_consultar_con_sql(carpeta):
    apollo.aprender_relacion("los sensores", "miden", "la temperatura")
    apollo.aprender_relacion("el sensor", "detecta", "movimiento")

    conexion = sqlite3.connect(carpeta / "diccionario_hefesto.db")
    filas = conexion.execute("""
        SELECT c.palabra, r.relacion, r.objetivo
        FROM relaciones r JOIN conceptos c ON c.id = r.concepto_id
        ORDER BY r.orden
    """).fetchall()
    conexion.close()

    assert filas == [
        ("sensor", "mide", "temperatura"),
        ("sensor", "detecta", "movimiento"),
    ]


def test_guarda_el_concepto_normalizado(carpeta):
    apollo.aprender_palabra("Las Baterías", "fuente de energía")

    conexion = sqlite3.connect(carpeta / "diccionario_hefesto.db")
    [(palabra, normalizado)] = conexion.execute(
        "SELECT palabra, normalizado FROM conceptos"
    ).fetchall()
    conexion.close()

    assert (palabra, normalizado) == ("batería", "bateria")