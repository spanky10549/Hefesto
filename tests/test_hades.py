"""
Pruebas de HADES y de la cuarentena de GAIA: incidentes, aislamiento
tras errores seguidos, recuperación y que todo quede registrado.
"""

import pytest

from gaia import Gaia, Inteligencia, OK, RECHAZADO, ERROR
from gaia.mensajes import EVENTO
from tabris import Tabris
from tabris.registro import Registro
from hades import Hades
import tabris.servicio as servicio_tabris


class Fragil(Inteligencia):
    """Truena cuando está 'rota'. Reiniciarla la arregla (si se deja)."""
    nombre = "fragil"

    def __init__(self):
        self.rota = False
        self.se_deja_arreglar = True
        self.acciones = {"trabajar": self.trabajar}

    def trabajar(self, datos):
        if self.rota:
            raise RuntimeError("engrane roto")
        return {"hecho": True}

    def reiniciar(self):
        if self.se_deja_arreglar:
            self.rota = False
            return True
        return False


@pytest.fixture
def ruta(tmp_path):
    return str(tmp_path / "registro.jsonl")


@pytest.fixture
def gaia(ruta):
    g = Gaia()
    g.registrar(Tabris(ruta))
    g.registrar(Hades())
    g.registrar(Fragil())
    return g


def fragil(gaia):
    return gaia.inteligencias["fragil"]


def tronar(gaia, veces):
    fragil(gaia).rota = True
    for _ in range(veces):
        gaia.pedir("hefesto", "fragil", "trabajar")


def incidentes(gaia, **filtro):
    return gaia.pedir("hefesto", "hades", "incidentes", **filtro)["datos"]["incidentes"]


LIMITE = servicio_tabris.LIMITE_ERRORES_SEGUIDOS


# ==========================================
# CUARENTENA EN GAIA
# ==========================================

def test_aislada_no_recibe_ordenes(gaia):
    gaia.aislar("fragil")
    respuesta = gaia.pedir("hefesto", "fragil", "trabajar")
    assert respuesta["estado"] == RECHAZADO
    assert "aislada" in respuesta["detalle"]


def test_liberar(gaia):
    gaia.aislar("fragil")
    gaia.liberar("fragil")
    assert gaia.pedir("hefesto", "fragil", "trabajar")["estado"] == OK


def test_directorio_dice_quien_esta_aislada(gaia):
    gaia.aislar("fragil")
    assert gaia.directorio()["fragil"]["aislada"] is True
    assert gaia.directorio()["tabris"]["aislada"] is False


def test_hades_no_se_puede_aislar(gaia):
    with pytest.raises(ValueError):
        gaia.aislar("hades")


def test_no_se_aisla_a_quien_no_existe(gaia):
    with pytest.raises(ValueError):
        gaia.aislar("fantasma")


def test_aislar_dos_veces_avisa_una(gaia):
    avisos = []
    gaia.suscribir("aislamiento", avisos.append)
    gaia.aislar("fragil")
    gaia.aislar("fragil")
    assert len(avisos) == 1


def test_retirar_quita_la_cuarentena(gaia):
    gaia.aislar("fragil")
    gaia.retirar("fragil")
    assert not gaia.esta_aislada("fragil")


def test_reiniciar(gaia):
    assert gaia.reiniciar("fragil") is True
    assert gaia.reiniciar("fantasma") is False

    fragil(gaia).se_deja_arreglar = False
    assert gaia.reiniciar("fragil") is False


def test_reiniciar_que_truena_no_tumba_a_gaia(gaia, monkeypatch):
    monkeypatch.setattr(fragil(gaia), "reiniciar", lambda: 1 / 0)
    assert gaia.reiniciar("fragil") is False


# ==========================================
# INCIDENTES
# ==========================================

def test_sin_fallos_no_hay_incidentes(gaia):
    gaia.pedir("hefesto", "fragil", "trabajar")
    assert incidentes(gaia) == []


def test_un_fallo_abre_un_incidente(gaia):
    tronar(gaia, 1)
    (incidente,) = incidentes(gaia)
    assert incidente["inteligencia"] == "fragil"
    assert incidente["estado"] == "abierto"
    assert incidente["fallos"] == 1
    assert "engrane roto" in incidente["ultimo_detalle"]


def test_varios_fallos_van_al_mismo_incidente(gaia):
    tronar(gaia, 2)
    (incidente,) = incidentes(gaia)
    assert incidente["fallos"] == 2


# ==========================================
# AISLAMIENTO AUTOMÁTICO
# ==========================================

def test_antes_del_limite_no_aisla(gaia):
    tronar(gaia, LIMITE - 1)
    assert not gaia.esta_aislada("fragil")


def test_al_llegar_al_limite_aisla(gaia):
    tronar(gaia, LIMITE)
    assert gaia.esta_aislada("fragil")
    assert incidentes(gaia)[0]["estado"] == "aislado"


def test_aislada_ya_no_truena(gaia):
    """Después del aislamiento, las órdenes se rechazan sin ejecutarse."""
    tronar(gaia, LIMITE)
    respuesta = gaia.pedir("hefesto", "fragil", "trabajar")
    assert respuesta["estado"] == RECHAZADO
    assert incidentes(gaia)[0]["fallos"] == LIMITE   # no sumó otro fallo


# ==========================================
# RECUPERACIÓN
# ==========================================

def test_recuperar(gaia):
    tronar(gaia, LIMITE)

    r = gaia.pedir("hefesto", "hades", "recuperar", inteligencia="fragil")

    assert r["estado"] == OK
    assert r["datos"] == {
        "recuperada": True, "inteligencia": "fragil",
        "estaba_aislada": True, "incidentes_cerrados": 1,
    }
    assert not gaia.esta_aislada("fragil")
    assert gaia.pedir("hefesto", "fragil", "trabajar")["estado"] == OK
    assert incidentes(gaia, abiertos=True) == []
    assert incidentes(gaia)[0]["cerrado"] is not None


def test_recuperacion_fallida(gaia):
    tronar(gaia, LIMITE)
    fragil(gaia).se_deja_arreglar = False

    r = gaia.pedir("hefesto", "hades", "recuperar", inteligencia="fragil")["datos"]

    assert r["recuperada"] is False
    assert gaia.esta_aislada("fragil")
    assert incidentes(gaia, abiertos=True)[0]["estado"] == "aislado"


def test_recuperar_a_quien_estaba_bien(gaia):
    r = gaia.pedir("hefesto", "hades", "recuperar", inteligencia="fragil")["datos"]
    assert r["recuperada"] is True
    assert r["estaba_aislada"] is False
    assert r["incidentes_cerrados"] == 0


def test_recuperar_a_quien_no_existe(gaia):
    r = gaia.pedir("hefesto", "hades", "recuperar", inteligencia="fantasma")
    assert r["estado"] == RECHAZADO


def test_recuperar_sin_nombre(gaia):
    assert gaia.pedir("hefesto", "hades", "recuperar")["estado"] == RECHAZADO


def test_si_vuelve_a_fallar_se_aisla_otra_vez(gaia):
    """TABRIS reinicia su cuenta al liberarla, así que puede volver a avisar."""
    tronar(gaia, LIMITE)
    gaia.pedir("hefesto", "hades", "recuperar", inteligencia="fragil")

    tronar(gaia, LIMITE)

    assert gaia.esta_aislada("fragil")
    assert len(incidentes(gaia)) == 2   # el viejo cerrado y uno nuevo


# ==========================================
# QUE QUEDE REGISTRADO (TABRIS)
# ==========================================

def test_todo_queda_en_el_registro(gaia, ruta):
    tronar(gaia, LIMITE)
    gaia.pedir("hefesto", "hades", "recuperar", inteligencia="fragil")

    eventos = [m["accion"] for m in Registro(ruta).leer() if m["tipo"] == EVENTO]

    for esperado in ("fallo", "anomalia", "aislamiento", "liberacion", "recuperacion"):
        assert esperado in eventos


def test_orden_de_lo_que_pasa(gaia, ruta):
    """Primero la anomalía, luego el aislamiento; al recuperar, la liberación."""
    tronar(gaia, LIMITE)
    gaia.pedir("hefesto", "hades", "recuperar", inteligencia="fragil")

    eventos = [m["accion"] for m in Registro(ruta).leer()
               if m["tipo"] == EVENTO and m["accion"] != "fallo"]
    eventos = [e for e in eventos if e != "registro"]

    assert eventos == ["anomalia", "aislamiento", "liberacion", "recuperacion"]


# ==========================================
# EN EL ECOSISTEMA REAL
# ==========================================

def test_hades_esta_en_el_ecosistema():
    from gaia import crear_ecosistema
    directorio = crear_ecosistema().directorio()
    assert "hades" in directorio
    assert directorio["hades"]["acciones"] == ["incidentes", "recuperar"]