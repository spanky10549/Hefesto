"""
Pruebas de usar el resultado de un paso en otro: "guárdalo como",
"el resultado" / "eso", y que funcione dentro de rutinas.
"""

import pytest

from gaia import Gaia, Inteligencia, OK, RECHAZADO
from gaia.tareas import ejecutar_plan, sustituir, valor_de, SinValor
from minerva.planeador import planear, interpretar, separar_guardado
from calculo.servicio import Calculadora


# ==========================================
# ENTENDER "GUÁRDALO COMO"
# ==========================================

@pytest.mark.parametrize("parte, resto, nombre", [
    ("calcula 5 × 35 y guárdalo como piezas", "calcula 5 × 35", "piezas"),
    ("calcula 5 × 35, guárdalo como 'piezas'", "calcula 5 × 35", "piezas"),
    ("calcula 2 + 2 y guarda el resultado como Total Final", "calcula 2 + 2", "total final"),
    ("calcula 5 × 35", "calcula 5 × 35", None),
])
def test_separar_guardado(parte, resto, nombre):
    assert separar_guardado(parte) == (resto, nombre)


def test_el_paso_lleva_su_nombre():
    paso = interpretar("calcula 5 × 35 y guárdalo como piezas")
    assert paso["datos"] == {"operacion": "5 × 35"}
    assert paso["guardar_como"] == "piezas"


def test_eso_divide_la_tarea():
    plan = planear("investiga qué es un pingüino y luego define eso")
    assert [p["datos"] for p in plan["pasos"]] == [{"concepto": "pingüino"}, {"concepto": "eso"}]


# ==========================================
# SUSTITUIR
# ==========================================

def test_sustituir_nombres():
    assert sustituir({"operacion": "piezas × 2"}, {"piezas": "175"}, None) == {"operacion": "175 × 2"}


def test_sustituir_el_resultado_y_eso():
    assert sustituir("el resultado + 1", {}, "350") == "350 + 1"
    assert sustituir("define eso", {}, "ave") == "define ave"


def test_no_cambia_pedazos_de_palabras():
    """'total' no se cambia dentro de 'totalmente'; 'eso' no dentro de 'peso'."""
    assert sustituir("totalmente total", {"total": "9"}, None) == "totalmente 9"
    assert sustituir("el peso", {}, "5") == "el peso"


def test_nombres_largos_primero():
    guardados = {"piezas": "1", "piezas grandes": "2"}
    assert sustituir("piezas grandes + piezas", guardados, None) == "2 + 1"


def test_fracciones_entre_parentesis_en_cuentas():
    """2 × 1/3 sería (2 × 1) ÷ 3 = 2/3 de todos modos, pero 1 ÷ 1/3 no: hacen falta paréntesis."""
    assert sustituir("1 ÷ x", {"x": "1/3"}, None, para_calcular=True) == "1 ÷ (1/3)"
    assert sustituir("define x", {"x": "1/3"}, None) == "define 1/3"


def test_el_resultado_sin_paso_anterior():
    with pytest.raises(SinValor):
        sustituir("el resultado + 1", {}, None)


def test_sustituir_respeta_lo_que_no_es_texto():
    assert sustituir({"x": 3, "lista": ["piezas"]}, {"piezas": "7"}, None) == {"x": 3, "lista": ["7"]}


# ==========================================
# VALOR DE CADA PASO
# ==========================================

def test_valor_de_un_calculo():
    assert valor_de({"para": "calculadora", "accion": "calcular"}, {"resultado": "175"}) == "175"


def test_valor_de_una_definicion():
    paso = {"para": "apollo", "accion": "definir"}
    assert valor_de(paso, {"categorias": ["ave"]}) == "ave"
    assert valor_de(paso, {"categorias": []}) is None


def test_pasos_sin_valor():
    assert valor_de({"para": "eter", "accion": "entorno"}, {"sensores": []}) is None


# ==========================================
# EJECUTAR (con la calculadora de verdad)
# ==========================================

class Sin(Inteligencia):
    """Una inteligencia que hace algo pero no deja un valor."""
    nombre = "eter"

    def __init__(self):
        self.acciones = {"entorno": lambda d: {"sensores": []}}


@pytest.fixture
def gaia():
    g = Gaia()
    g.registrar(Calculadora())
    g.registrar(Sin())
    return g


def ejecutar(gaia, tarea):
    return ejecutar_plan(gaia, planear(tarea))


def test_guardar_y_usar(gaia):
    r = ejecutar(gaia, "calcula 5 × 35 y guárdalo como piezas, calcula piezas × 2")
    assert r["completada"] is True
    assert r["guardados"] == {"piezas": "175"}
    assert r["resultados"][0]["guardado"] == {"nombre": "piezas", "valor": "175"}
    assert r["resultados"][1]["datos"]["resultado"] == "350"


def test_el_resultado_encadenado(gaia):
    r = ejecutar(gaia, "calcula 5 × 35 y luego calcula el resultado + 1 y calcula el resultado × 2")
    assert [x["datos"]["resultado"] for x in r["resultados"]] == ["175", "176", "352"]


def test_fracciones_exactas(gaia):
    r = ejecutar(gaia, "calcula 1/3 y guárdalo como tercio, calcula 1 ÷ tercio")
    assert r["resultados"][1]["datos"]["resultado"] == "3"


def test_sin_resultado_anterior(gaia):
    r = ejecutar(gaia, "calcula el resultado + 1")
    assert r["resultados"][0]["estado"] == RECHAZADO
    assert "el resultado" in r["resultados"][0]["detalle"]


def test_un_paso_sin_valor_no_borra_el_anterior(gaia):
    """'revisa el entorno' no deja valor: 'el resultado' sigue siendo el del cálculo."""
    r = ejecutar(gaia, "calcula 2 + 2, revisa el entorno y calcula el resultado × 10")
    assert r["resultados"][2]["datos"]["resultado"] == "40"


def test_guardar_algo_que_no_deja_valor(gaia):
    r = ejecutar(gaia, "revisa el entorno y guárdalo como clima")
    assert r["resultados"][0]["estado"] == OK
    assert "no dejó un valor" in r["resultados"][0]["detalle"]
    assert r["guardados"] == {}


def test_nombre_que_no_existe_llega_tal_cual(gaia):
    """Si nadie guardó 'piezas', la calculadora recibe la palabra y la rechaza."""
    r = ejecutar(gaia, "calcula piezas × 2")
    assert r["resultados"][0]["estado"] == RECHAZADO


def test_en_una_rutina(gaia):
    from minerva.rutinas import Rutinas
    import tempfile, os
    rutinas = Rutinas(os.path.join(tempfile.mkdtemp(), "r.json"))
    rutinas.ensenar("presupuesto", "calcula 120 × 3 y guárdalo como total, calcula total ÷ 4")

    r = ejecutar_plan(gaia, planear("presupuesto", rutinas.todas()))
    assert r["resultados"][1]["datos"]["resultado"] == "90"


def test_con_apollo_define_eso(tmp_path, monkeypatch):
    import apollo.conocimiento as conocimiento
    monkeypatch.setattr(conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json"))
    from apollo.servicio import Apollo

    g = Gaia()
    g.registrar(Apollo())
    g.pedir("hefesto", "apollo", "aprender_relacion", sujeto="pingüino", relacion="es", objeto="ave")

    r = ejecutar_plan(g, planear("investiga qué es un pingüino y luego define eso"))
    assert r["resultados"][1]["datos"]["concepto"] == "ave"