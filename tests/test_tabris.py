"""
Pruebas de TABRIS: registro en archivo, observar a GAIA,
resumen, búsqueda y detección de fallos repetidos.
"""

import json
import pytest

from gaia import Gaia, Inteligencia, OK, ERROR
from gaia.mensajes import crear_orden, crear_evento, ORDEN, RESPUESTA, EVENTO
from tabris import Tabris
from tabris.registro import Registro
import tabris.servicio as servicio


class Eco(Inteligencia):
    nombre = "eco"

    def __init__(self):
        self.acciones = {
            "repetir": lambda datos: {"texto": datos.get("texto", "")},
            "tronar": lambda datos: 1 / 0,
        }


@pytest.fixture
def ruta(tmp_path):
    return str(tmp_path / "registro.jsonl")


@pytest.fixture
def gaia(ruta):
    g = Gaia()
    g.registrar(Tabris(ruta))
    g.registrar(Eco())
    return g


# ==========================================
# REGISTRO
# ==========================================

def test_registro_vacio(ruta):
    assert list(Registro(ruta).leer()) == []


def test_anotar_y_leer(ruta):
    registro = Registro(ruta)
    registro.anotar(crear_orden("a", "b", "c", {"x": "pingüino"}))
    registro.anotar(crear_evento("a", "aviso"))

    mensajes = list(registro.leer())
    assert [m["tipo"] for m in mensajes] == [ORDEN, EVENTO]
    assert mensajes[0]["datos"]["x"] == "pingüino"


def test_una_linea_por_mensaje(ruta):
    registro = Registro(ruta)
    for _ in range(3):
        registro.anotar(crear_evento("a", "aviso"))

    with open(ruta, encoding="utf-8") as archivo:
        assert len(archivo.readlines()) == 3


def test_lineas_danadas_se_saltan(ruta):
    registro = Registro(ruta)
    registro.anotar(crear_evento("a", "uno"))
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write('{"esto se cortó a la mit\n\n')
    registro.anotar(crear_evento("a", "dos"))

    assert [m["accion"] for m in registro.leer()] == ["uno", "dos"]


def test_buscar_los_ultimos(ruta):
    registro = Registro(ruta)
    for numero in range(10):
        registro.anotar(crear_evento("a", f"evento_{numero}"))

    ultimos = registro.buscar(cantidad=3)
    assert [m["accion"] for m in ultimos] == ["evento_7", "evento_8", "evento_9"]


def test_buscar_con_filtro(ruta):
    registro = Registro(ruta)
    registro.anotar(crear_evento("a", "si"))
    registro.anotar(crear_evento("a", "no"))
    registro.anotar(crear_evento("a", "si"))

    assert len(registro.buscar(lambda m: m["accion"] == "si")) == 2


# ==========================================
# OBSERVAR A GAIA
# ==========================================

def test_ve_su_propio_registro_y_el_de_los_demas(gaia, ruta):
    registros = [m["datos"]["nombre"] for m in Registro(ruta).leer()
                 if m["accion"] == "registro"]
    assert registros == ["tabris", "eco"]


def test_guarda_orden_y_respuesta(gaia, ruta):
    gaia.pedir("hefesto", "eco", "repetir", texto="hola")

    *_, orden, respuesta = Registro(ruta).leer()
    assert orden["tipo"] == ORDEN and orden["para"] == "eco"
    assert respuesta["tipo"] == RESPUESTA and respuesta["responde_a"] == orden["id"]


def test_el_registro_sobrevive_al_apagado(ruta):
    """Lo que vio una GAIA lo puede leer la TABRIS de otra sesión."""
    primera = Gaia()
    primera.registrar(Tabris(ruta))
    primera.registrar(Eco())
    primera.pedir("hefesto", "eco", "repetir")

    segunda = Gaia()
    segunda.registrar(Tabris(ruta))
    resumen = segunda.pedir("hefesto", "tabris", "resumen")["datos"]
    assert resumen["por_inteligencia"]["eco"] == 1


def test_si_tabris_falla_el_ecosistema_sigue(gaia, monkeypatch):
    tabris = gaia.inteligencias["tabris"]
    monkeypatch.setattr(tabris.registro, "anotar", lambda m: 1 / 0)

    assert gaia.pedir("hefesto", "eco", "repetir", texto="sigo")["estado"] == OK


# ==========================================
# RESUMEN
# ==========================================

def test_resumen(gaia):
    gaia.pedir("hefesto", "eco", "repetir")
    gaia.pedir("hefesto", "eco", "tronar")
    gaia.pedir("hefesto", "calculadora", "calcular")   # no existe en esta GAIA

    r = gaia.pedir("hefesto", "tabris", "resumen")["datos"]

    assert r["ordenes"] == 4   # las 3 de arriba + esta misma
    assert r["errores"] == 1
    assert r["por_inteligencia"] == {"eco": 2, "calculadora": 1, "tabris": 1}
    assert r["ultimo_error"]["inteligencia"] == "eco"
    assert "ZeroDivisionError" in r["ultimo_error"]["detalle"]


def test_resumen_de_hoy(gaia):
    gaia.pedir("hefesto", "eco", "repetir")
    r = gaia.pedir("hefesto", "tabris", "resumen", dia="hoy")["datos"]
    assert r["ordenes"] == 2
    assert len(r["dia"]) == 10        # "2026-11-09"


def test_resumen_de_otro_dia(gaia):
    gaia.pedir("hefesto", "eco", "repetir")
    r = gaia.pedir("hefesto", "tabris", "resumen", dia="1999-01-01")["datos"]
    assert r["mensajes"] == 0


# ==========================================
# BUSCAR
# ==========================================

def test_buscar_errores(gaia):
    gaia.pedir("hefesto", "eco", "repetir")
    gaia.pedir("hefesto", "eco", "tronar")

    r = gaia.pedir("hefesto", "tabris", "buscar", estado=ERROR)["datos"]
    assert r["cantidad"] == 1
    assert r["mensajes"][0]["accion"] == "tronar"


def test_buscar_por_inteligencia(gaia):
    gaia.pedir("hefesto", "eco", "repetir")
    r = gaia.pedir("hefesto", "tabris", "buscar", inteligencia="eco", tipo=ORDEN)["datos"]
    assert r["cantidad"] == 1


@pytest.mark.parametrize("cantidad, esperado", [(2, 2), (-5, 10), ("mucho", 10), (10_000, 100)])
def test_buscar_cantidad(gaia, cantidad, esperado):
    for _ in range(60):
        gaia.pedir("hefesto", "eco", "repetir")
    r = gaia.pedir("hefesto", "tabris", "buscar", cantidad=cantidad)["datos"]
    assert r["cantidad"] == esperado


def test_la_respuesta_puede_viajar_por_la_red(gaia):
    gaia.pedir("hefesto", "eco", "tronar")
    respuesta = gaia.pedir("hefesto", "tabris", "buscar")
    assert respuesta["estado"] == OK
    json.dumps(respuesta)


# ==========================================
# ANOMALÍAS
# ==========================================

def test_anomalia_tras_errores_seguidos(gaia):
    anomalias = []
    gaia.suscribir("anomalia", anomalias.append)

    for _ in range(servicio.LIMITE_ERRORES_SEGUIDOS - 1):
        gaia.pedir("hefesto", "eco", "tronar")
    assert anomalias == []

    gaia.pedir("hefesto", "eco", "tronar")
    assert len(anomalias) == 1
    assert anomalias[0]["de"] == "tabris"
    assert anomalias[0]["datos"]["inteligencia"] == "eco"


def test_avisa_una_sola_vez(gaia):
    anomalias = []
    gaia.suscribir("anomalia", anomalias.append)
    for _ in range(10):
        gaia.pedir("hefesto", "eco", "tronar")
    assert len(anomalias) == 1


def test_un_acierto_reinicia_la_cuenta(gaia):
    anomalias = []
    gaia.suscribir("anomalia", anomalias.append)

    gaia.pedir("hefesto", "eco", "tronar")
    gaia.pedir("hefesto", "eco", "tronar")
    gaia.pedir("hefesto", "eco", "repetir")     # salió bien: vuelve a 0
    gaia.pedir("hefesto", "eco", "tronar")
    gaia.pedir("hefesto", "eco", "tronar")

    assert anomalias == []


def test_la_anomalia_queda_registrada(gaia, ruta):
    for _ in range(servicio.LIMITE_ERRORES_SEGUIDOS):
        gaia.pedir("hefesto", "eco", "tronar")

    assert any(m["accion"] == "anomalia" for m in Registro(ruta).leer())


# ==========================================
# EN EL ECOSISTEMA REAL
# ==========================================

def test_tabris_esta_en_el_ecosistema():
    from gaia import crear_ecosistema
    assert "tabris" in crear_ecosistema().directorio()


def test_no_escribe_en_la_carpeta_real(tmp_path):
    """El conftest cambia el archivo por uno temporal en todas las pruebas."""
    assert servicio.ARCHIVO_REGISTRO.startswith(str(tmp_path.parent))