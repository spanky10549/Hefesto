"""
Configuración común de las pruebas.

pytest carga este archivo solo. Lo que hay aquí aplica a TODAS las pruebas.
"""

import pytest


@pytest.fixture(autouse=True)
def archivos_temporales(tmp_path, monkeypatch):
    """
    'autouse=True' hace que se aplique sin pedirlo: ninguna prueba
    escribe en el registro real de TABRIS ni crea la clave real de POSEIDON.
    """
    import tabris.servicio
    import poseidon.firma
    monkeypatch.setattr(
        tabris.servicio, "ARCHIVO_REGISTRO", str(tmp_path / "tabris_registro.jsonl")
    )
    # Tampoco se crea la clave secreta de POSEIDON en la carpeta real.
    monkeypatch.setattr(
        poseidon.firma, "ARCHIVO_CLAVE", str(tmp_path / "poseidon_clave.txt")
    )