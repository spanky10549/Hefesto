"""
Pruebas de condiciones y plan B: entenderlas (MINERVA), revisarlas al
ejecutar (GAIA, con datos guardados y del sistema) y usarlas en rutinas.
"""

from fractions import Fraction

import pytest

from gaia import Gaia, Inteligencia, OK, RECHAZADO
from gaia.tareas import ejecutar_plan, cumple, SinValor, SALTADO, PENDIENTE
from minerva.condiciones import entender, separar_condicion, partir_plan_b, es_plan_b, describir
from minerva.planeador import planear
from minerva.rutinas import Rutinas, ErrorRutina
from calculo.servicio import Calculadora


# ==========================================
# ENTENDER CONDICIONES
# ==========================================

@pytest.mark.parametrize("texto, izq, op, der", [
    ("piezas es mayor que 100", "piezas", ">", "100"),
    ("piezas > 100", "piezas", ">", "100"),
    ("piezas>100", "piezas", ">", "100"),
    ("la RAM está arriba de 90", "la ram", ">", "90"),
    ("el disco es menor o igual que 50", "el disco", "<=", "50"),
    ("la batería baja de 20", "la bateria", "<", "20"),
    ("el resultado es igual a 4", "el resultado", "=", "4"),
    ("total es diferente de 0", "total", "!=", "0"),
    ("piezas es al menos 10", "piezas", ">=", "10"),
    ("hay errores", "errores", ">", "0"),
    ("no hay incidentes", "incidentes", "=", "0"),
])
def test_entender(texto, izq, op, der):
    c = entender(texto)
    assert (c["izq"], c["op"], c["der"]) == (izq, op, der)


def test_no_es_condicion():
    assert entender("calcula 2 + 2") is None


def test_describir():
    assert describir({"izq": "piezas", "op": ">", "der": "100"}) == "piezas es mayor que 100"


@pytest.mark.parametrize("parte, resto", [
    ("si piezas > 100 entonces calcula piezas ÷ 2", "calcula piezas ÷ 2"),
    ("si piezas es mayor que 100 calcula piezas ÷ 2", "calcula piezas ÷ 2"),
    ("calcula piezas ÷ 2 si piezas > 100", "calcula piezas ÷ 2"),
    ("si piezas > 100", ""),
])
def test_separar_condicion(parte, resto):
    condicion, sobra = separar_condicion(parte)
    assert condicion["izq"] == "piezas"
    assert sobra == resto


def test_sin_condicion():
    assert separar_condicion("define si") == (None, "define si")


def test_plan_b():
    assert partir_plan_b("define tensor y si falla calcula 2 + 2") == ["define tensor", "y si falla calcula 2 + 2"]
    assert es_plan_b("si falla, calcula 2 + 2") == "calcula 2 + 2"
    assert es_plan_b("Si no funciona revisa los recursos") == "revisa los recursos"
    assert es_plan_b("si falla") == ""
    assert es_plan_b("calcula 2") is None


# ==========================================
# PLANEAR
# ==========================================

def test_condicion_en_el_plan():
    plan = planear("calcula 5 × 35 y guárdalo como piezas, si piezas > 100 calcula piezas ÷ 2")
    assert "condicion" not in plan["pasos"][0]
    assert plan["pasos"][1]["condicion"]["izq"] == "piezas"


def test_condicion_sola_aplica_a_lo_que_sigue():
    plan = planear("si hay errores, revisa los incidentes")
    assert plan["pasos"][0]["para"] == "hades"
    assert plan["pasos"][0]["condicion"]["izq"] == "errores"


def test_condicion_sin_paso():
    plan = planear("calcula 2, si hay errores")
    assert plan["no_entendidos"] == ["si hay errores"]


def test_plan_b_en_el_plan():
    plan = planear("define tensor y si falla calcula 2 + 2")
    (paso,) = plan["pasos"]
    assert paso["si_falla"] == "plan b"
    assert paso["alternativa"]["para"] == "calculadora"


def test_si_falla_detente_con_comas():
    plan = planear("calcula 5 ÷ 0, si falla, detente, calcula 1 + 1")
    assert [p["si_falla"] for p in plan["pasos"]] == ["detener", "continuar"]
    assert plan["no_entendidos"] == []


def test_plan_b_sin_paso_antes():
    assert planear("si falla calcula 2")["no_entendidos"] == ["si falla calcula 2"]


def test_plan_b_que_no_entiende():
    plan = planear("calcula 2 y si falla baila salsa")
    assert plan["no_entendidos"] == ["y si falla baila salsa"]


# ==========================================
# REVISAR CONDICIONES (GAIA)
# ==========================================

class Sistema(Inteligencia):
    """Hace de ARTEMIS, TABRIS y HADES con números que se pueden cambiar."""

    def __init__(self, nombre, acciones):
        self.nombre = nombre
        self.acciones = acciones


@pytest.fixture
def gaia():
    g = Gaia()
    g.registrar(Calculadora())
    g.datos = {"ram": 76, "errores": 0, "incidentes": []}
    g.registrar(Sistema("artemis", {"estado": lambda d: {
        "ram": {"porcentaje": g.datos["ram"]}, "disco": {"porcentaje": 40},
        "cpu": {"porcentaje": 9}, "bateria": None}}))
    g.registrar(Sistema("tabris", {"resumen": lambda d: {"errores": g.datos["errores"]}}))
    g.registrar(Sistema("hades", {"incidentes": lambda d: {"incidentes": g.datos["incidentes"]}}))
    return g


def condicion(texto):
    return entender(texto)


def test_cumple_con_numeros(gaia):
    assert cumple(condicion("piezas > 100"), {"piezas": "175"}, None, gaia)[0] is True
    assert cumple(condicion("piezas > 100"), {"piezas": "9"}, None, gaia)[0] is False


def test_cumple_con_el_resultado(gaia):
    assert cumple(condicion("el resultado es igual a 4"), {}, "4", gaia)[0] is True


def test_cumple_con_fracciones(gaia):
    assert cumple(condicion("tercio < 1"), {"tercio": "1/3"}, None, gaia)[0] is True


def test_cumple_con_datos_del_sistema(gaia):
    assert cumple(condicion("la ram está arriba de 90"), {}, None, gaia)[0] is False
    gaia.datos["ram"] = 95
    se_cumple, texto = cumple(condicion("la ram está arriba de 90"), {}, None, gaia)
    assert se_cumple is True and "(vale 95)" in texto


def test_hay_errores_y_no_hay_incidentes(gaia):
    assert cumple(condicion("hay errores"), {}, None, gaia)[0] is False
    assert cumple(condicion("no hay incidentes"), {}, None, gaia)[0] is True
    gaia.datos["errores"] = 3
    assert cumple(condicion("hay errores"), {}, None, gaia)[0] is True


def test_valor_desconocido(gaia):
    with pytest.raises(SinValor, match="piezas"):
        cumple(condicion("piezas > 3"), {}, None, gaia)


def test_bateria_que_no_existe(gaia):
    with pytest.raises(SinValor):
        cumple(condicion("la batería baja de 20"), {}, None, gaia)


def test_comparar_textos(gaia):
    assert cumple(condicion("el resultado es igual a ave"), {}, "ave", gaia)[0] is True
    with pytest.raises(SinValor):
        cumple(condicion("el resultado > 3"), {}, "ave", gaia)


# ==========================================
# EJECUTAR
# ==========================================

def ejecutar(gaia, tarea, rutinas=None):
    return ejecutar_plan(gaia, planear(tarea, rutinas))


def test_condicion_que_se_cumple(gaia):
    r = ejecutar(gaia, "calcula 5 × 35 y guárdalo como piezas, si piezas es mayor que 100 calcula piezas ÷ 2")
    assert r["resultados"][1]["estado"] == OK
    assert r["resultados"][1]["datos"]["resultado"] == "175/2"


def test_condicion_que_no_se_cumple(gaia):
    r = ejecutar(gaia, "calcula 3 × 3 y guárdalo como piezas, si piezas > 100 calcula piezas ÷ 2")
    assert r["resultados"][1]["estado"] == SALTADO
    assert "vale 9" in r["resultados"][1]["detalle"]
    assert r["completada"] is True        # saltar no es fallar


def test_condicion_que_no_se_puede_revisar(gaia):
    r = ejecutar(gaia, "si piezas > 3 calcula 2")
    assert r["resultados"][0]["estado"] == RECHAZADO
    assert r["completada"] is False


def test_condicion_con_el_sistema(gaia):
    r = ejecutar(gaia, "si la ram está arriba de 90, calcula 1 + 1")
    assert r["resultados"][0]["estado"] == SALTADO
    gaia.datos["ram"] = 99
    r = ejecutar(gaia, "si la ram está arriba de 90, calcula 1 + 1")
    assert r["resultados"][0]["estado"] == OK


def test_plan_b_cuando_falla(gaia):
    r = ejecutar(gaia, "calcula 5 ÷ 0 y si falla calcula 2 + 2")
    (paso,) = r["resultados"]
    assert paso["estado"] == RECHAZADO
    assert paso["plan_b"]["estado"] == OK
    assert paso["plan_b"]["datos"]["resultado"] == "4"
    assert r["completada"] is True


def test_plan_b_no_se_usa_si_sale_bien(gaia):
    r = ejecutar(gaia, "calcula 1 + 1 y si falla calcula 2 + 2")
    assert "plan_b" not in r["resultados"][0]


def test_el_resultado_del_plan_b_sigue(gaia):
    r = ejecutar(gaia, "calcula 5 ÷ 0 y si falla calcula 10, calcula el resultado + 1")
    assert r["resultados"][1]["datos"]["resultado"] == "11"


def test_detenerse(gaia):
    r = ejecutar(gaia, "calcula 5 ÷ 0, si falla, detente, calcula 1 + 1")
    assert [x["estado"] for x in r["resultados"]] == [RECHAZADO, PENDIENTE]


def test_plan_b_cuando_apollo_no_lo_conoce(tmp_path, monkeypatch):
    import apollo.conocimiento as conocimiento
    monkeypatch.setattr(conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json"))
    from apollo.servicio import Apollo

    g = Gaia()
    g.registrar(Apollo())
    g.registrar(Calculadora())

    r = ejecutar_plan(g, planear("define tensor y si falla calcula 2 + 2"))
    (paso,) = r["resultados"]
    assert paso["estado"] == OK and paso["logrado"] is False
    assert paso["plan_b"]["datos"]["resultado"] == "4"


# ==========================================
# EN RUTINAS
# ==========================================

def test_rutina_con_condiciones(gaia, tmp_path):
    rutinas = Rutinas(str(tmp_path / "r.json"))
    rutinas.ensenar("vigila", "si hay errores calcula 1 + 1, si no hay errores calcula 2 + 2")

    r = ejecutar(gaia, "vigila", rutinas.todas())
    assert [x["estado"] for x in r["resultados"]] == [SALTADO, OK]


def test_rutina_con_plan_b(gaia, tmp_path):
    rutinas = Rutinas(str(tmp_path / "r.json"))
    rutinas.ensenar("segura", "calcula 5 ÷ 0 y si falla calcula 2 + 2")
    r = ejecutar(gaia, "segura", rutinas.todas())
    assert r["resultados"][0]["plan_b"]["estado"] == OK


def test_rutina_con_condicion_que_no_entiende(tmp_path):
    rutinas = Rutinas(str(tmp_path / "r.json"))
    with pytest.raises(ErrorRutina):
        rutinas.ensenar("rara", "si hay errores baila salsa")


def test_circulo_escondido_en_una_condicion(tmp_path):
    rutinas = Rutinas(str(tmp_path / "r.json"))
    rutinas.ensenar("a", "revisa los recursos")
    rutinas.ensenar("b", "si hay errores a")
    with pytest.raises(ErrorRutina, match="círculo"):
        rutinas.ensenar("a", "b")