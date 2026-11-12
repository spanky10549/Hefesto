"""
Pruebas de POSEIDON: firma, revisión de mensajes (firma, fecha y
repetición), la clave secreta y el reporte de sospechosos.
"""

from datetime import datetime, timedelta

import pytest

from gaia import Gaia, OK
from gaia.mensajes import crear_orden, crear_evento
from poseidon import Poseidon, Guardia, MensajeSospechoso, cargar_clave
from poseidon.firma import firmar, firma_valida
import poseidon.firma


CLAVE = "clave-de-prueba"


# ==========================================
# FIRMA
# ==========================================

def test_firmar_agrega_la_firma_sin_cambiar_el_original():
    orden = crear_orden("gaia", "rover_1", "ir_a", {"x": 1, "y": 2})
    firmada = firmar(orden, CLAVE)
    assert "firma" in firmada
    assert "firma" not in orden
    assert len(firmada["firma"]) == 64      # SHA-256 en hexadecimal


def test_firma_valida():
    assert firma_valida(firmar(crear_orden("a", "b", "c"), CLAVE), CLAVE)


def test_otra_clave_no_sirve():
    firmada = firmar(crear_orden("a", "b", "c"), CLAVE)
    assert not firma_valida(firmada, "otra-clave")


def test_cambiar_una_letra_rompe_la_firma():
    firmada = firmar(crear_orden("a", "rover_1", "ir_a", {"x": 1}), CLAVE)
    firmada["datos"]["x"] = 9
    assert not firma_valida(firmada, CLAVE)


def test_el_orden_de_los_campos_no_importa():
    orden = crear_orden("a", "b", "c", {"x": 1, "y": 2})
    al_reves = dict(reversed(list(orden.items())))
    assert firmar(orden, CLAVE)["firma"] == firmar(al_reves, CLAVE)["firma"]


def test_sin_firma():
    assert not firma_valida(crear_orden("a", "b", "c"), CLAVE)


# ==========================================
# GUARDIA
# ==========================================

def test_mensaje_bueno_pasa_y_sale_sin_firma():
    guardia = Guardia(CLAVE)
    orden = crear_orden("a", "b", "c")
    revisado = guardia.revisar(guardia.sellar(orden))
    assert revisado == orden


def test_firma_falsa():
    with pytest.raises(MensajeSospechoso, match="firma"):
        Guardia(CLAVE).revisar(firmar(crear_orden("a", "b", "c"), "clave-del-intruso"))


def test_mensaje_repetido():
    guardia = Guardia(CLAVE)
    firmada = guardia.sellar(crear_orden("a", "b", "c"))
    guardia.revisar(firmada)
    with pytest.raises(MensajeSospechoso, match="repetido"):
        guardia.revisar(firmada)


def test_mensaje_viejo():
    """Una orden grabada hace 5 minutos y mandada otra vez."""
    en_5_minutos = lambda: datetime.now() + timedelta(minutes=5)
    guardia = Guardia(CLAVE, ahora=en_5_minutos)
    with pytest.raises(MensajeSospechoso, match="viejo"):
        guardia.revisar(guardia.sellar(crear_orden("a", "b", "c")))


def test_mensaje_del_futuro():
    hace_5_minutos = lambda: datetime.now() - timedelta(minutes=5)
    guardia = Guardia(CLAVE, ahora=hace_5_minutos)
    with pytest.raises(MensajeSospechoso):
        guardia.revisar(guardia.sellar(crear_orden("a", "b", "c")))


def test_dentro_de_la_ventana_pasa():
    en_30_segundos = lambda: datetime.now() + timedelta(seconds=30)
    guardia = Guardia(CLAVE, ahora=en_30_segundos)
    guardia.revisar(guardia.sellar(crear_orden("a", "b", "c")))


def test_fecha_ilegible():
    guardia = Guardia(CLAVE)
    orden = {**crear_orden("a", "b", "c"), "fecha": "ayer"}
    with pytest.raises(MensajeSospechoso, match="fecha"):
        guardia.revisar(guardia.sellar(orden))


# ==========================================
# CLAVE SECRETA
# ==========================================

def test_crea_la_clave_si_no_existe(tmp_path):
    ruta = tmp_path / "clave.txt"
    clave = cargar_clave(str(ruta))
    assert len(clave) == 64
    assert ruta.read_text().strip() == clave


def test_reutiliza_la_clave(tmp_path):
    ruta = str(tmp_path / "clave.txt")
    assert cargar_clave(ruta) == cargar_clave(ruta)


def test_cada_clave_nueva_es_distinta(tmp_path):
    assert cargar_clave(str(tmp_path / "a.txt")) != cargar_clave(str(tmp_path / "b.txt"))


def test_las_pruebas_no_tocan_la_clave_real(tmp_path):
    assert poseidon.firma.ARCHIVO_CLAVE.startswith(str(tmp_path.parent))


# ==========================================
# POSEIDON EN GAIA
# ==========================================

def test_reporte_vacio():
    g = Gaia()
    g.registrar(Poseidon())
    r = g.pedir("hefesto", "poseidon", "reporte")["datos"]
    assert r == {"sospechosos": 0, "por_motivo": {}, "ultimo": None}


def test_reporte_cuenta_por_motivo():
    g = Gaia()
    g.registrar(Poseidon())
    for motivo in ("firma inválida", "firma inválida", "mensaje repetido"):
        g.publicar(crear_evento("red", "mensaje_sospechoso", {"motivo": motivo, "origen": "x"}))

    r = g.pedir("hefesto", "poseidon", "reporte")["datos"]
    assert r["sospechosos"] == 3
    assert r["por_motivo"] == {"firma inválida": 2, "mensaje repetido": 1}
    assert r["ultimo"]["motivo"] == "mensaje repetido"