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


# ==========================================
# ACTUALIZAR UNA BASE DE LA VERSIÓN ANTERIOR
# ==========================================

def crear_base_version_1(ruta):
    """Una base como la que creó la primera versión (sin columnas normalizadas)."""
    conexion = sqlite3.connect(ruta)
    conexion.executescript("""
        CREATE TABLE conceptos (id INTEGER PRIMARY KEY, palabra TEXT, normalizado TEXT, orden INTEGER);
        CREATE TABLE asociaciones (concepto_id INTEGER, texto TEXT, orden INTEGER);
        CREATE TABLE sinonimos (concepto_id INTEGER, texto TEXT, orden INTEGER);
        CREATE TABLE relaciones (concepto_id INTEGER, relacion TEXT, objetivo TEXT,
                                 negada INTEGER, orden INTEGER);
        INSERT INTO conceptos VALUES (1, 'raspberry pi', 'raspberry pi', 0);
        INSERT INTO asociaciones VALUES (1, 'una computadora', 0);
        INSERT INTO sinonimos VALUES (1, 'rpi', 0);
        INSERT INTO relaciones VALUES (1, 'se comunica con', 'sensores', 0, 0);
    """)
    conexion.commit()
    conexion.close()


def test_actualiza_base_vieja_sin_perder_nada(carpeta):
    crear_base_version_1(carpeta / "diccionario_hefesto.db")
    apollo._bases_listas.clear()

    assert apollo.buscar_entrada("rpi")["palabra"] == "raspberry pi"
    assert apollo.buscar_relaciones("rpi") == [
        {"relacion": "se comunica con", "objetivo": "sensores"}
    ]

    conexion = sqlite3.connect(carpeta / "diccionario_hefesto.db")
    version = conexion.execute("PRAGMA user_version").fetchone()[0]
    conexion.close()
    assert version == 2


# ==========================================
# CONSULTAS DIRECTAS
# ==========================================

def test_inversas_por_sinonimo(carpeta):
    apollo.aprender_palabra("sensor", "un dispositivo")
    apollo.aprender_sinonimo("sensor", "detector")
    apollo.aprender_relacion("raspberry pi", "se comunica con", "detector")

    from apollo import razonamiento
    assert razonamiento.relaciones_inversas("sensores") == [
        {"sujeto": "raspberry pi", "relacion": "se comunica con"}
    ]


def test_existe_concepto_por_objetivo(carpeta):
    apollo.aprender_relacion("sensor", "mide", "temperatura")

    assert apollo.existe_concepto("la temperatura")
    assert not apollo.existe_concepto("unicornio")


# ==========================================
# ESCRIBIR SOLO LO QUE CAMBIA
# ==========================================

def ids_de_conceptos(carpeta):
    conexion = sqlite3.connect(carpeta / "diccionario_hefesto.db")
    filas = conexion.execute("SELECT id, palabra FROM conceptos ORDER BY orden").fetchall()
    conexion.close()
    return filas


def test_aprender_no_reescribe_lo_demas(carpeta):
    apollo.aprender_relacion("sensor", "mide", "luz")
    apollo.aprender_relacion("motor", "mueve", "ruedas")
    antes = ids_de_conceptos(carpeta)

    apollo.aprender_relacion("sensor", "detecta", "movimiento")

    # Los conceptos conservan su id: no se borraron y volvieron a crear.
    assert ids_de_conceptos(carpeta) == antes


def test_lo_nuevo_va_al_final(carpeta):
    apollo.aprender_relacion("sensor", "mide", "luz")
    apollo.aprender_relacion("motor", "mueve", "ruedas")
    apollo.aprender_relacion("sensor", "detecta", "movimiento")

    assert [p for _, p in ids_de_conceptos(carpeta)] == ["sensor", "motor"]
    assert [r["objetivo"] for r in apollo.buscar_relaciones("sensor")] == [
        "luz", "movimiento"
    ]


def test_reemplazar_es_todo_o_nada(carpeta):
    apollo.aprender_relacion("sensor", "pertenece a", "rover")

    apollo.aprender_relacion("sensor", "pertenece a", "dron", reemplazar=True)

    assert apollo.buscar_relaciones("sensor") == [
        {"relacion": "pertenece a", "objetivo": "dron"}
    ]