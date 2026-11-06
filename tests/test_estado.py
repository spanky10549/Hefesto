"""
Pruebas del estado de la conversación entre sesiones.
"""

from datetime import datetime

import pytest

from conversacion import estado


@pytest.fixture(autouse=True)
def archivo_temporal(tmp_path, monkeypatch):
    """Cada prueba usa su propio archivo de conversación."""
    monkeypatch.setattr(
        estado, "ARCHIVO_CONVERSACION", str(tmp_path / "conversacion.json")
    )


def test_sin_archivo_empieza_vacio():
    assert estado.cargar_estado()["tema"] is None


def test_guarda_y_recupera_el_tema():
    estado.guardar_estado("pingüino", "¿{tema} puede volar?")

    guardado = estado.cargar_estado()

    assert guardado["tema"] == "pingüino"
    assert guardado["plantilla"] == "¿{tema} puede volar?"
    assert guardado["fecha"] is not None


def test_olvidar_el_tema():
    estado.guardar_estado("pingüino", None)
    estado.olvidar_estado()

    assert estado.cargar_estado()["tema"] is None


def test_archivo_danado_no_detiene_a_hefesto(tmp_path, monkeypatch):
    archivo = tmp_path / "danado.json"
    archivo.write_text("{esto no es json", encoding="utf-8")
    monkeypatch.setattr(estado, "ARCHIVO_CONVERSACION", str(archivo))

    assert estado.cargar_estado()["tema"] is None


@pytest.mark.parametrize("fecha, esperado", [
    ("2026-11-05T21:40", "hace un rato"),
    ("2026-11-05T09:00", "hoy"),
    ("2026-11-04T18:00", "ayer"),
    ("2026-11-01T18:00", "el 1 de noviembre"),
    ("no es fecha", None),
    (None, None),
])
def test_describir_fecha(fecha, esperado):
    ahora = datetime(2026, 11, 5, 22, 0)

    assert estado.describir_fecha(fecha, ahora) == esperado