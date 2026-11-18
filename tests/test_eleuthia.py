"""
Pruebas de ELEUTHIA: respaldos (con la base de datos de verdad),
restaurar en dos tiempos, bitácora automática y experimentos.
"""

import json
import os
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime, timedelta

import pytest

from gaia import Gaia, OK, RECHAZADO
from gaia.mensajes import crear_evento
from eleuthia import Eleuthia
from eleuthia import respaldos
import eleuthia.servicio as servicio


class Reloj:
    def __init__(self):
        self.momento = datetime(2026, 11, 18, 12, 0, 0)

    def __call__(self):
        return self.momento

    def adelantar(self, **tiempo):
        self.momento += timedelta(**tiempo)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def carpeta(tmp_path):
    """Una carpeta de FOCUS de mentira, con su base de datos y archivos."""
    # closing(): "with sqlite3.connect" solo guarda; closing además CIERRA.
    # En Windows, un archivo que se queda abierto no se puede reemplazar.
    with closing(sqlite3.connect(tmp_path / "diccionario_hefesto.db")) as c:
        c.execute("CREATE TABLE conceptos (palabra TEXT)")
        c.execute("INSERT INTO conceptos VALUES ('pingüino')")
        c.commit()
    (tmp_path / "eter_mapa.json").write_text('{"obstaculos": []}', encoding="utf-8")
    (tmp_path / "poseidon_clave.txt").write_text("secreto", encoding="utf-8")
    (tmp_path / "otro_archivo.txt").write_text("no es de FOCUS", encoding="utf-8")
    return tmp_path


@pytest.fixture
def gaia(carpeta, reloj):
    g = Gaia()
    g.registrar(Eleuthia(str(carpeta), str(carpeta / "bitacora.jsonl"), ahora=reloj))
    return g


def pedir(gaia, accion, **datos):
    return gaia.pedir("hefesto", "eleuthia", accion, **datos)


def palabras(ruta_db):
    with closing(sqlite3.connect(ruta_db)) as c:
        return [fila[0] for fila in c.execute("SELECT palabra FROM conceptos")]


# ==========================================
# RESPALDOS
# ==========================================

def test_respaldar(gaia, carpeta):
    r = pedir(gaia, "respaldar")["datos"]
    assert r["nombre"] == "respaldo_2026-11-18_12-00-00.zip"
    assert sorted(r["archivos"]) == ["diccionario_hefesto.db", "eter_mapa.json"]

    with zipfile.ZipFile(carpeta / "respaldos" / r["nombre"]) as z:
        assert "poseidon_clave.txt" not in z.namelist()     # el secreto no se respalda
        assert "otro_archivo.txt" not in z.namelist()


def test_la_base_de_datos_respaldada_funciona(gaia, carpeta, tmp_path_factory):
    nombre = pedir(gaia, "respaldar")["datos"]["nombre"]
    salida = tmp_path_factory.mktemp("abierto")
    with zipfile.ZipFile(carpeta / "respaldos" / nombre) as z:
        z.extract("diccionario_hefesto.db", salida)
    assert palabras(salida / "diccionario_hefesto.db") == ["pingüino"]


def test_dos_respaldos_en_el_mismo_segundo_no_se_pisan(gaia):
    primero = pedir(gaia, "respaldar")["datos"]["nombre"]
    segundo = pedir(gaia, "respaldar")["datos"]["nombre"]
    assert primero != segundo
    assert len(pedir(gaia, "respaldos")["datos"]["respaldos"]) == 2


def test_respaldo_con_etiqueta(gaia):
    assert pedir(gaia, "respaldar", etiqueta="antesdelcambio")["datos"]["nombre"].endswith("_antesdelcambio.zip")


def test_etiqueta_rara(gaia):
    assert pedir(gaia, "respaldar", etiqueta="../../hack")["estado"] == RECHAZADO


def test_nada_que_respaldar(tmp_path, reloj):
    g = Gaia()
    g.registrar(Eleuthia(str(tmp_path), str(tmp_path / "b.jsonl"), ahora=reloj))
    assert g.pedir("hefesto", "eleuthia", "respaldar")["estado"] == RECHAZADO


def test_solo_guarda_los_ultimos(gaia, reloj):
    for _ in range(respaldos.MAX_RESPALDOS + 3):
        pedir(gaia, "respaldar")
        reloj.adelantar(minutes=1)

    lista = pedir(gaia, "respaldos")["datos"]["respaldos"]
    assert len(lista) == respaldos.MAX_RESPALDOS
    assert lista[0]["nombre"] > lista[-1]["nombre"]       # el más nuevo primero


def test_respaldo_al_dia(gaia, reloj):
    assert pedir(gaia, "respaldo_al_dia")["datos"]["hecho"] is True
    reloj.adelantar(hours=5)
    assert pedir(gaia, "respaldo_al_dia")["datos"]["hecho"] is False
    reloj.adelantar(hours=20)
    assert pedir(gaia, "respaldo_al_dia")["datos"]["hecho"] is True


# ==========================================
# RESTAURAR
# ==========================================

def test_restaurar_en_dos_tiempos(gaia, carpeta, reloj):
    nombre = pedir(gaia, "respaldar")["datos"]["nombre"]

    # Algo daña el diccionario
    with closing(sqlite3.connect(carpeta / "diccionario_hefesto.db")) as c:
        c.execute("DELETE FROM conceptos")
        c.commit()
    reloj.adelantar(minutes=1)

    r = pedir(gaia, "restaurar", respaldo=nombre)["datos"]
    assert "diccionario_hefesto.db" in r["pendiente"]
    assert r["respaldo_de_seguridad"].endswith("_antes.zip")

    # Todavía no se reemplaza nada (FOCUS sigue encendido)
    assert palabras(carpeta / "diccionario_hefesto.db") == []

    # Al arrancar otra vez:
    restaurados = respaldos.aplicar_restauracion_pendiente(str(carpeta))
    assert "diccionario_hefesto.db" in restaurados
    assert palabras(carpeta / "diccionario_hefesto.db") == ["pingüino"]

    # Y ya no queda nada pendiente
    assert respaldos.aplicar_restauracion_pendiente(str(carpeta)) == []


def test_archivo_ocupado_queda_pendiente(gaia, carpeta, monkeypatch):
    """Si Windows no deja reemplazar un archivo, no truena: lo deja para después."""
    nombre = pedir(gaia, "respaldar")["datos"]["nombre"]
    pedir(gaia, "restaurar", respaldo=nombre)

    reemplazar_de_verdad = os.replace

    def ocupado(origen, destino):
        if destino.endswith(".db"):
            raise PermissionError("[WinError 5] Acceso denegado")
        reemplazar_de_verdad(origen, destino)

    monkeypatch.setattr(respaldos.os, "replace", ocupado)
    monkeypatch.setattr(respaldos, "ESPERA_SEGUNDOS", 0)

    with pytest.raises(respaldos.ArchivoOcupado, match="diccionario_hefesto.db"):
        respaldos.aplicar_restauracion_pendiente(str(carpeta))

    # El .db sigue pendiente; lo demás ya se restauró
    pendiente = os.listdir(carpeta / "respaldos" / respaldos.CARPETA_PENDIENTE)
    assert pendiente == ["diccionario_hefesto.db"]

    # Ya libre, la siguiente vez sí se termina
    monkeypatch.setattr(respaldos.os, "replace", reemplazar_de_verdad)
    assert respaldos.aplicar_restauracion_pendiente(str(carpeta)) == ["diccionario_hefesto.db"]


def test_restaurar_algo_que_no_existe(gaia):
    assert pedir(gaia, "restaurar", respaldo="respaldo_nada.zip")["estado"] == RECHAZADO


def test_un_zip_tramposo_no_escribe_afuera(carpeta):
    """Un respaldo modificado no puede sacar archivos de la carpeta."""
    destino = carpeta / "respaldos"
    destino.mkdir()
    with zipfile.ZipFile(destino / "respaldo_2026-01-01_00-00-00.zip", "w") as z:
        z.writestr("../../fuera.txt", "malo")
        z.writestr("eter_mapa.json", '{"obstaculos": [[1, 1]]}')

    archivos = respaldos.preparar_restauracion(str(destino), "respaldo_2026-01-01_00-00-00.zip")
    assert archivos == ["eter_mapa.json"]
    assert not (carpeta.parent / "fuera.txt").exists()


# ==========================================
# BITÁCORA
# ==========================================

def test_anotar_y_leer(gaia):
    pedir(gaia, "anotar", texto="hoy conecté el rover por primera vez")
    (entrada,) = pedir(gaia, "bitacora", dia="hoy")["datos"]["entradas"]
    assert entrada["texto"] == "hoy conecté el rover por primera vez"
    assert entrada["tipo"] == "nota"


def test_anotar_vacio(gaia):
    assert pedir(gaia, "anotar", texto="  ")["estado"] == RECHAZADO


def test_se_llena_sola_con_los_eventos(gaia):
    gaia.publicar(crear_evento("hefesto", "aprendizaje", {"texto": "Aprendí que el pingüino es un ave."}))
    gaia.publicar(crear_evento("hades", "recuperacion", {"inteligencia": "apollo", "incidentes_cerrados": 1}))
    gaia.publicar(crear_evento("gaia", "registro", {"nombre": "x"}))     # este no interesa

    textos = [e["texto"] for e in pedir(gaia, "bitacora")["datos"]["entradas"]]
    assert textos == ["Aprendí que el pingüino es un ave.", "HADES recuperó a APOLLO"]


def test_evento_con_datos_raros_no_truena(gaia):
    gaia.publicar(crear_evento("x", "tarea_terminada", {"nada": 1}))
    (entrada,) = pedir(gaia, "bitacora")["datos"]["entradas"]
    assert "tarea_terminada" in entrada["texto"]


def test_bitacora_por_dia(gaia, reloj):
    pedir(gaia, "anotar", texto="ayer")
    reloj.adelantar(days=1)
    pedir(gaia, "anotar", texto="hoy")
    assert [e["texto"] for e in pedir(gaia, "bitacora", dia="hoy")["datos"]["entradas"]] == ["hoy"]


def test_bitacora_sobrevive(carpeta, reloj):
    ruta = str(carpeta / "bitacora.jsonl")
    Eleuthia(str(carpeta), ruta, ahora=reloj).anotar({"texto": "no me olvides"})
    otra = Eleuthia(str(carpeta), ruta, ahora=reloj)
    assert otra.bitacora({})["entradas"][0]["texto"] == "no me olvides"


# ==========================================
# EXPERIMENTOS
# ==========================================

def experimento(gaia, **datos):
    base = {"proyecto": "FOCUS", "intento": "x", "resultado": "funcionó"}
    return pedir(gaia, "experimento", **{**base, **datos})


def test_experimentos(gaia):
    experimento(gaia, intento="WiFi con netsh", resultado="funcionó")
    experimento(gaia, intento="pip.exe en Windows", resultado="falló",
                aprendizaje="usar python -m pip")
    experimento(gaia, proyecto="Rover", intento="motores", resultado="a medias")

    r = pedir(gaia, "experimentos", proyecto="focus")["datos"]      # sin importar mayúsculas
    assert len(r["experimentos"]) == 2
    assert r["resumen"] == {"funcionó": 1, "falló": 1, "a medias": 0}
    assert r["experimentos"][1]["aprendizaje"] == "usar python -m pip"


def test_experimentos_no_ensucian_la_bitacora(gaia):
    experimento(gaia)
    assert pedir(gaia, "bitacora")["datos"]["entradas"] == []


@pytest.mark.parametrize("datos", [{"resultado": "más o menos"}, {"proyecto": ""}, {"intento": "  "}])
def test_experimentos_incompletos(gaia, datos):
    assert experimento(gaia, **datos)["estado"] == RECHAZADO


# ==========================================
# ECOSISTEMA
# ==========================================

def test_las_pruebas_no_tocan_la_bitacora_real(tmp_path):
    assert servicio.ARCHIVO_BITACORA.startswith(str(tmp_path.parent))


def test_eleuthia_en_el_ecosistema():
    from gaia import crear_ecosistema
    assert "eleuthia" in crear_ecosistema().directorio()