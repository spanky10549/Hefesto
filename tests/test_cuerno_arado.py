"""
Pruebas de CUERNO ARADO: análisis de enlaces (trampas típicas de
phishing), extraer links de un mensaje, listas propias y avisos.
"""

import pytest

from gaia import Gaia, OK, RECHAZADO
from cuerno_arado import CuernoArado
from cuerno_arado.analisis import (
    analizar, extraer_enlaces, dominio_registrable, sin_disfraz, distancia,
)
from poseidon import Poseidon
import cuerno_arado.servicio as servicio


def riesgo(url, **listas):
    return analizar(url, **listas)["riesgo"]


# ==========================================
# AYUDANTES
# ==========================================

@pytest.mark.parametrize("host, dominio", [
    ("www.paypal.com", "paypal.com"),
    ("paypal.com.inicio-seguro.xyz", "inicio-seguro.xyz"),
    ("www.mercadolibre.com.mx", "mercadolibre.com.mx"),
    ("portal.sat.gob.mx", "sat.gob.mx"),
])
def test_dominio_registrable(host, dominio):
    assert dominio_registrable(host) == dominio


def test_sin_disfraz():
    assert sin_disfraz("paypa1") == "paypal"
    assert sin_disfraz("rnercadolibre") == "mercadolibre"
    assert sin_disfraz("g00gle") == "google"


def test_distancia():
    assert distancia("steamcomunity", "steamcommunity") == 1
    assert distancia("gato", "gato") == 0


def test_extraer_enlaces_de_un_sms():
    sms = ("BBVA: tu cuenta fue BLOQUEADA. Entra ya a https://bbva-mx-seguro.com/login, "
           "o visita www.ejemplo.com. Gracias.")
    assert extraer_enlaces(sms) == ["https://bbva-mx-seguro.com/login", "www.ejemplo.com"]


def test_enlace_con_un_solo_punto():
    assert extraer_enlaces("revisa github.com/spanky porfa") == ["github.com/spanky"]


def test_texto_sin_enlaces():
    assert extraer_enlaces("hola, ¿cómo estás? son las 3.30") == []


# ==========================================
# SITIOS NORMALES Y OFICIALES (sin falsas alarmas)
# ==========================================

@pytest.mark.parametrize("url", [
    "https://www.paypal.com/signin",
    "https://www.mercadolibre.com.mx/ofertas",
    "https://steamcommunity.com/id/juan",
    "https://fonts.googleapis.com/css",
    "https://youtu.be/abc123",
    "https://github.com/spanky",
    "https://docs.python.org/3/",
    "https://sat.gob.mx",
    "tec.mx",
])
def test_sin_falsas_alarmas(url):
    assert riesgo(url) == "bajo"


def test_reconoce_el_sitio_oficial():
    assert analizar("https://www.paypal.com")["oficial_de"] == "paypal"


# ==========================================
# TRAMPAS
# ==========================================

@pytest.mark.parametrize("url, pista", [
    ("https://paypa1.com", "se parece mucho a paypal"),
    ("https://rnercadolibre.com.mx", "se parece mucho a mercadolibre"),
    ("https://steamcomunity.com/gift", "steamcommunity.com"),
    ("https://epicgarnes.com", "se parece mucho a epicgames"),
    ("http://paypal.com.inicio-seguro.xyz/verifica", "menciona a paypal"),
    ("https://bbva-mx-seguro.com", "menciona a bbva"),
    ("https://www.google.com@malo.ru/login", "@"),
    ("www.xn--pypal-4ve.com", "otros alfabetos"),
    ("https://descargas.ejemplo.com/juego.exe", "programa"),
    ("javascript:alert(1)", "javascript"),
])
def test_trampas_de_riesgo_alto(url, pista):
    r = analizar(url)
    assert r["riesgo"] == "alto"
    assert any(pista in razon for razon in r["razones"])


def test_ip_y_http():
    r = analizar("http://185.23.4.1/banco")
    assert r["riesgo"] == "alto"
    assert len(r["razones"]) == 2


def test_acortador_es_riesgo_medio():
    assert riesgo("https://bit.ly/3xyz") == "medio"


def test_gancho_de_videojuegos():
    assert riesgo("https://free-robux-gana.click") == "alto"


def test_el_arroba_dice_a_donde_lleva_de_verdad():
    r = analizar("https://www.google.com@malo.ru/login")
    assert r["dominio"] == "malo.ru"


# ==========================================
# LISTAS
# ==========================================

def test_listas_mandan():
    assert riesgo("https://bit.ly/x", confiables={"bit.ly"}) == "bajo"
    assert riesgo("https://github.com", bloqueados={"github.com"}) == "alto"


@pytest.fixture
def gaia(tmp_path):
    g = Gaia()
    g.registrar(CuernoArado(str(tmp_path / "listas.json")))
    g.registrar(Poseidon())
    return g


def test_confiar_acepta_un_link_completo(gaia):
    r = gaia.pedir("hefesto", "cuerno_arado", "confiar", dominio="https://www.miescuela.edu.mx/inicio")
    assert r["datos"]["dominio"] == "miescuela.edu.mx"


def test_bloquear_quita_de_confiables(gaia):
    gaia.pedir("hefesto", "cuerno_arado", "confiar", dominio="raro.com")
    gaia.pedir("hefesto", "cuerno_arado", "bloquear", dominio="raro.com")
    assert gaia.pedir("hefesto", "cuerno_arado", "listas")["datos"] == {
        "confiables": [], "bloqueados": ["raro.com"]
    }


def test_olvidar(gaia):
    gaia.pedir("hefesto", "cuerno_arado", "bloquear", dominio="raro.com")
    r = gaia.pedir("hefesto", "cuerno_arado", "olvidar", dominio="raro.com")["datos"]
    assert r["estaba"] is True
    assert gaia.pedir("hefesto", "cuerno_arado", "listas")["datos"]["bloqueados"] == []


def test_dominio_invalido(gaia):
    assert gaia.pedir("hefesto", "cuerno_arado", "confiar", dominio="hola")["estado"] == RECHAZADO


def test_las_listas_sobreviven(tmp_path):
    ruta = str(tmp_path / "listas.json")
    CuernoArado(ruta).bloquear({"dominio": "raro.com"})
    assert CuernoArado(ruta).bloqueados == {"raro.com"}


# ==========================================
# EN EL ECOSISTEMA
# ==========================================

def test_revisar_texto(gaia):
    r = gaia.pedir("hefesto", "cuerno_arado", "revisar_texto",
                   texto="mira https://github.com y también https://paypa1.com/login")["datos"]
    assert [e["riesgo"] for e in r["enlaces"]] == ["bajo", "alto"]
    assert r["riesgo"] == "alto"


def test_sin_url(gaia):
    assert gaia.pedir("hefesto", "cuerno_arado", "revisar")["estado"] == RECHAZADO


def test_enlace_peligroso_avisa_a_poseidon(gaia):
    avisos = []
    gaia.suscribir("enlace_peligroso", avisos.append)

    gaia.pedir("hefesto", "cuerno_arado", "revisar", url="https://paypa1.com")
    gaia.pedir("hefesto", "cuerno_arado", "revisar", url="https://github.com")   # este no

    assert len(avisos) == 1
    reporte = gaia.pedir("hefesto", "poseidon", "reporte")["datos"]
    assert reporte["por_motivo"] == {"enlace peligroso": 1}


def test_queda_en_la_bitacora(tmp_path):
    from eleuthia import Eleuthia
    g = Gaia()
    g.registrar(CuernoArado(str(tmp_path / "listas.json")))
    g.registrar(Eleuthia(str(tmp_path), str(tmp_path / "bitacora.jsonl")))

    g.pedir("hefesto", "cuerno_arado", "revisar", url="https://paypa1.com")

    (entrada,) = g.pedir("hefesto", "eleuthia", "bitacora")["datos"]["entradas"]
    assert "paypa1.com" in entrada["texto"]


def test_las_pruebas_no_tocan_las_listas_reales(tmp_path):
    assert servicio.ARCHIVO_LISTAS.startswith(str(tmp_path.parent))


def test_las_12_inteligencias_estan_conectadas():
    """¡El esqueleto completo de FOCUS!"""
    from gaia import crear_ecosistema
    directorio = crear_ecosistema().directorio()
    for nombre in ("apollo", "minerva", "artemis", "eter", "demeter", "eleuthia",
                   "tabris", "hades", "poseidon", "cuerno_arado"):
        assert nombre in directorio
    # HEFESTO es quien habla contigo y GAIA quien coordina: no se registran a sí mismas.