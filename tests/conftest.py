"""
Configuración común de las pruebas.

pytest carga este archivo solo. Lo que hay aquí aplica a TODAS las pruebas.
"""

import pytest


@pytest.fixture(autouse=True)
def archivos_temporales(tmp_path, monkeypatch):
    """
    'autouse=True' hace que se aplique sin pedirlo: ninguna prueba
    escribe en el registro real de TABRIS, ni en el mapa real de ÉTER,
    ni crea la clave real de POSEIDON.
    """
    import tabris.servicio
    import poseidon.firma
    monkeypatch.setattr(
        tabris.servicio, "ARCHIVO_REGISTRO", str(tmp_path / "tabris_registro.jsonl")
    )
    # Ni el mapa de ÉTER...
    import eter.servicio
    monkeypatch.setattr(eter.servicio, "ARCHIVO_MAPA", str(tmp_path / "eter_mapa.json"))
    # ...ni los estados de los sensores locales...
    import dispositivos.local
    monkeypatch.setattr(dispositivos.local, "ARCHIVO_ESTADOS", str(tmp_path / "sensores_locales.json"))
    # ...ni los permisos de DEMETER...
    import demeter.servicio
    monkeypatch.setattr(demeter.servicio, "ARCHIVO_PERMISOS", str(tmp_path / "demeter_permisos.json"))
    # ...ni la bitácora de ELEUTHIA...
    import eleuthia.servicio
    monkeypatch.setattr(eleuthia.servicio, "ARCHIVO_BITACORA", str(tmp_path / "eleuthia_bitacora.jsonl"))
    # ...ni las listas de CUERNO ARADO...
    import cuerno_arado.servicio
    monkeypatch.setattr(cuerno_arado.servicio, "ARCHIVO_LISTAS", str(tmp_path / "cuerno_arado_listas.json"))
    # ...ni los proyectos del laboratorio...
    import minerva.laboratorio
    monkeypatch.setattr(minerva.laboratorio, "ARCHIVO_LABORATORIO", str(tmp_path / "laboratorio.json"))
    # ...ni las rutinas de MINERVA...
    import minerva.rutinas
    monkeypatch.setattr(minerva.rutinas, "ARCHIVO_RUTINAS", str(tmp_path / "minerva_rutinas.json"))
    # ...ni la clave secreta de POSEIDON en la carpeta real.
    monkeypatch.setattr(
        poseidon.firma, "ARCHIVO_CLAVE", str(tmp_path / "poseidon_clave.txt")
    )