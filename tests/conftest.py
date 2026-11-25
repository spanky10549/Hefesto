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
    # ...ni tu perfil de la plática...
    import conversacion.perfil
    monkeypatch.setattr(conversacion.perfil, "ARCHIVO_PERFIL", str(tmp_path / "conversacion_perfil.json"))
    # ...ni lo que sabe HEFESTO (la base de datos de APOLLO)
    import apollo.conocimiento
    monkeypatch.setattr(apollo.conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json"))
    import conversacion.frases
    monkeypatch.setattr(conversacion.frases, "ARCHIVO_FRASES", str(tmp_path / "conversacion_frases.json"))
    # ...ni la clave del creador...
    import conversacion.creador
    monkeypatch.setattr(conversacion.creador, "ARCHIVO_CREADOR", str(tmp_path / "focus_creador.json"))
    # ...ni la clave secreta de POSEIDON en la carpeta real.
    monkeypatch.setattr(
        poseidon.firma, "ARCHIVO_CLAVE", str(tmp_path / "poseidon_clave.txt")
    )


class HefestoDePrueba:
    """
    Sustituye al puente con HEFESTO.py en las pruebas: el HEFESTO de
    verdad carga su red neuronal y escribe memoria.json en la carpeta
    real. Este solo anota qué le pasaron y dice que no entendió.
    """

    def __init__(self, gaia=None):
        self.recibidos = []

    def pasar(self, comando):
        self.recibidos.append(comando)
        return {"entendio": False, "salir": False, "lineas": []}


@pytest.fixture(autouse=True)
def sin_hefesto_real(monkeypatch):
    import conversacion.platica
    monkeypatch.setattr(conversacion.platica, "PuenteHefesto", HefestoDePrueba)