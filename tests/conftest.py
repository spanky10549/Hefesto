"""
Configuración común de las pruebas.

pytest carga este archivo solo. Lo que hay aquí aplica a TODAS las pruebas.
"""

import pytest


@pytest.fixture(autouse=True)
def registro_temporal(tmp_path, monkeypatch):
    """
    'autouse=True' hace que se aplique sin pedirlo: ninguna prueba
    escribe en el registro real de TABRIS.
    """
    import tabris.servicio
    monkeypatch.setattr(
        tabris.servicio, "ARCHIVO_REGISTRO", str(tmp_path / "tabris_registro.jsonl")
    )