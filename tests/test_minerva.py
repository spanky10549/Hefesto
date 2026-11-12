"""
Pruebas de MINERVA (planear), de la ejecución de planes en GAIA
y del resumen de resultados.
"""

import pytest

from gaia import Gaia, Inteligencia, OK, RECHAZADO, ERROR
from gaia.tareas import ejecutar_plan, OMITIDO, PENDIENTE
from minerva import Minerva
from minerva.planeador import simple, dividir_tarea, interpretar, planear, quitar_articulo
from artemis import Artemis
from conversacion.resultados import resumir


# ==========================================
# TEXTO SIMPLE
# ==========================================

def test_simple_conserva_el_largo():
    texto = "¿Investiga QUÉ es el Pingüino?"
    assert len(simple(texto)) == len(texto)
    assert simple(texto) == " investiga que es el pinguino "


def test_quitar_articulo():
    assert quitar_articulo("una raspberry pi") == "raspberry pi"
    assert quitar_articulo("Los sensores") == "sensores"
    assert quitar_articulo("agua") == "agua"


# ==========================================
# DIVIDIR
# ==========================================

@pytest.mark.parametrize("tarea, partes", [
    ("investiga qué es X, calcula 2 + 2 y revisa los recursos",
     ["investiga qué es X", "calcula 2 + 2", "revisa los recursos"]),
    ("calcula 1 + 1 y luego revisa la compu",
     ["calcula 1 + 1", "revisa la compu"]),
    ("define agua y hielo", ["define agua y hielo"]),          # "y" sin verbo: no divide
    ("calcula 2 y 3; define ave", ["calcula 2 y 3", "define ave"]),
    ("¿Qué es un ave? y después revisa los errores",
     ["Qué es un ave", "revisa los errores"]),
    ("primero define ave, después calcula 3 × 3",
     ["define ave", "calcula 3 × 3"]),
    ("   ", []),
])
def test_dividir(tarea, partes):
    assert dividir_tarea(tarea) == partes


# ==========================================
# INTERPRETAR
# ==========================================

@pytest.mark.parametrize("parte, para, accion, datos", [
    ("investiga qué es una raspberry pi", "apollo", "definir", {"concepto": "raspberry pi"}),
    ("investigar sobre los sensores", "apollo", "definir", {"concepto": "sensores"}),
    ("¿Qué es el pingüino?", "apollo", "definir", {"concepto": "pingüino"}),
    ("define Batería", "apollo", "definir", {"concepto": "Batería"}),
    ("calcula 5 × 35", "calculadora", "calcular", {"operacion": "5 × 35"}),
    ("¿cuánto es 2^10?", "calculadora", "calcular", {"operacion": "2^10"}),
    ("revisa los recursos", "artemis", "estado", {}),
    ("checa cómo está la compu", "artemis", "estado", {}),
    ("revisar la memoria", "artemis", "estado", {}),
    ("revisa los errores", "tabris", "resumen", {"dia": "hoy"}),
    ("qué pasó hoy", "tabris", "resumen", {"dia": "hoy"}),
])
def test_interpretar(parte, para, accion, datos):
    paso = interpretar(parte)
    assert (paso["para"], paso["accion"], paso["datos"]) == (para, accion, datos)


@pytest.mark.parametrize("parte", ["baila salsa", "investiga", "calcula", "revisa la tarea"])
def test_no_entiende(parte):
    assert interpretar(parte) is None


def test_cuanto_es_no_es_que_es():
    """'cuánto es' termina en 'es', pero es un cálculo."""
    assert interpretar("cuánto es 3 + 3")["para"] == "calculadora"


def test_planear_numera_y_separa_lo_que_no_entiende():
    plan = planear("define ave, baila salsa y calcula 1 + 1")
    assert [p["numero"] for p in plan["pasos"]] == [1, 2]
    assert [p["para"] for p in plan["pasos"]] == ["apollo", "calculadora"]
    assert plan["no_entendidos"] == ["baila salsa"]
    assert all(p["si_falla"] == "continuar" for p in plan["pasos"])


# ==========================================
# MINERVA EN GAIA
# ==========================================

class Falsa(Inteligencia):
    """Hace de cualquier inteligencia: responde lo que se le configure."""

    def __init__(self, nombre, acciones, falla=False):
        self.nombre = nombre
        self.falla = falla
        self.recibidas = []
        self.acciones = {accion: self._hacer for accion in acciones}

    def _hacer(self, datos):
        self.recibidas.append(datos)
        if self.falla:
            raise RuntimeError("me caí")
        return {"hecho": True}


def ram_falsa(disponible_mb):
    mb = 1024 * 1024
    return lambda: {
        "cpu": {"porcentaje": 5, "nucleos": 4},
        "ram": {"total": 16 * 1024 * mb, "disponible": disponible_mb * mb, "porcentaje": 50},
        "disco": {"total": 500 * 1024 * mb, "libre": 100 * 1024 * mb, "porcentaje": 50},
        "bateria": None,
    }


@pytest.fixture
def gaia():
    g = Gaia()
    g.registrar(Minerva())
    g.registrar(Falsa("apollo", ["definir"]))
    g.registrar(Falsa("calculadora", ["calcular"]))
    g.registrar(Artemis(ram_falsa(8000)))
    return g


def pedir_plan(gaia, tarea):
    return gaia.pedir("hefesto", "minerva", "planear", tarea=tarea)


def test_plan_viable(gaia):
    r = pedir_plan(gaia, "define ave y calcula 2 + 2")
    assert r["estado"] == OK
    plan = r["datos"]
    assert plan["viable"] is True
    assert all(p["aviso"] is None for p in plan["pasos"])
    assert plan["recursos"] == {"ram_mb": 25, "alcanza": True, "faltan": {}}


def test_sin_tarea(gaia):
    assert gaia.pedir("hefesto", "minerva", "planear")["estado"] == RECHAZADO


def test_tarea_que_no_entiende(gaia):
    r = pedir_plan(gaia, "baila salsa")
    assert r["estado"] == RECHAZADO
    assert "no entendí" in r["detalle"]


def test_aviso_si_no_esta_conectada(gaia):
    gaia.retirar("calculadora")
    plan = pedir_plan(gaia, "define ave y calcula 2 + 2")["datos"]
    assert plan["viable"] is False
    assert "no está conectada" in plan["pasos"][1]["aviso"]


def test_aviso_si_esta_aislada(gaia):
    gaia.aislar("apollo")
    plan = pedir_plan(gaia, "define ave")["datos"]
    assert plan["viable"] is False
    assert "aislada" in plan["pasos"][0]["aviso"]


def test_aviso_si_no_sabe_hacerlo(gaia):
    gaia.retirar("apollo")
    gaia.registrar(Falsa("apollo", ["otra_cosa"]))
    plan = pedir_plan(gaia, "define ave")["datos"]
    assert "no sabe hacer" in plan["pasos"][0]["aviso"]


def test_no_alcanza_la_ram():
    g = Gaia()
    g.registrar(Minerva())
    g.registrar(Falsa("apollo", ["definir"]))
    g.registrar(Artemis(ram_falsa(10)))      # solo 10 MB libres

    plan = pedir_plan(g, "define ave")["datos"]
    assert plan["recursos"]["alcanza"] is False
    assert plan["recursos"]["faltan"] == {"ram_mb": 10}
    assert plan["viable"] is False


def test_sin_artemis_no_se_sabe_pero_sigue():
    g = Gaia()
    g.registrar(Minerva())
    g.registrar(Falsa("apollo", ["definir"]))

    plan = pedir_plan(g, "define ave")["datos"]
    assert plan["recursos"]["alcanza"] is None
    assert plan["viable"] is True


# ==========================================
# EJECUTAR EL PLAN (GAIA)
# ==========================================

def test_ejecutar_todo_bien(gaia):
    plan = pedir_plan(gaia, "define ave y calcula 2 + 2")["datos"]
    r = ejecutar_plan(gaia, plan)

    assert r["completada"] is True
    assert [x["estado"] for x in r["resultados"]] == [OK, OK]
    assert gaia.inteligencias["apollo"].recibidas == [{"concepto": "ave"}]
    assert gaia.inteligencias["calculadora"].recibidas == [{"operacion": "2 + 2"}]


def test_las_ordenes_llevan_el_objetivo(gaia):
    plan = pedir_plan(gaia, "define ave")["datos"]
    ejecutar_plan(gaia, plan)

    orden = gaia.ultimos(50, tipo="orden")[-1]
    assert orden["para"] == "apollo"
    assert orden["objetivo"] == "define ave"
    assert orden["si_falla"] == "continuar"


def test_si_falla_continua(gaia):
    gaia.retirar("apollo")
    gaia.registrar(Falsa("apollo", ["definir"], falla=True))

    plan = pedir_plan(gaia, "define ave y calcula 2 + 2")["datos"]
    r = ejecutar_plan(gaia, plan)

    assert r["completada"] is False
    assert [x["estado"] for x in r["resultados"]] == [ERROR, OK]


def test_si_falla_y_hay_que_detenerse(gaia):
    gaia.retirar("apollo")
    gaia.registrar(Falsa("apollo", ["definir"], falla=True))

    plan = pedir_plan(gaia, "define ave y calcula 2 + 2")["datos"]
    plan["pasos"][0]["si_falla"] = "detener"
    r = ejecutar_plan(gaia, plan)

    assert [x["estado"] for x in r["resultados"]] == [ERROR, PENDIENTE]
    assert gaia.inteligencias["calculadora"].recibidas == []


def test_pasos_con_aviso_se_omiten(gaia):
    gaia.aislar("apollo")
    plan = pedir_plan(gaia, "define ave y calcula 2 + 2")["datos"]
    r = ejecutar_plan(gaia, plan)

    assert [x["estado"] for x in r["resultados"]] == [OMITIDO, OK]
    assert gaia.inteligencias["apollo"].recibidas == []


def test_avisa_cada_paso(gaia):
    plan = pedir_plan(gaia, "define ave y calcula 2 + 2")["datos"]
    vistos = []
    ejecutar_plan(gaia, plan, al_terminar_paso=vistos.append)
    assert [v["numero"] for v in vistos] == [1, 2]


def test_eventos_de_tarea(gaia):
    eventos = []
    gaia.suscribir("tarea_iniciada", eventos.append)
    gaia.suscribir("tarea_terminada", eventos.append)

    plan = pedir_plan(gaia, "define ave y calcula 2 + 2")["datos"]
    ejecutar_plan(gaia, plan)

    assert [e["accion"] for e in eventos] == ["tarea_iniciada", "tarea_terminada"]
    assert eventos[1]["datos"] == {
        "tarea": "define ave y calcula 2 + 2", "completada": True, "bien": 2, "total": 2
    }


# ==========================================
# RESUMIR RESULTADOS
# ==========================================

def test_resumir_calculo():
    datos = {"expresion": "2 + 2", "resultado_texto": "4"}
    assert resumir("calculadora", "calcular", datos) == "2 + 2 = 4"


def test_resumir_recursos_con_alerta():
    datos = {
        "cpu": {"porcentaje": 10}, "ram": {"porcentaje": 95}, "disco": {"porcentaje": 40},
        "alertas": [{"recurso": "ram", "texto": "queda poca memoria RAM"}],
    }
    texto = resumir("artemis", "estado", datos)
    assert "RAM al 95 %" in texto and "queda poca memoria RAM" in texto


def test_resumir_desconocido():
    assert resumir("rover_1", "avanzar", {}) == "listo."


def test_resumir_datos_raros_no_truena():
    assert "no supe resumir" in resumir("calculadora", "calcular", {"otra": 1})


# ==========================================
# EN EL ECOSISTEMA REAL
# ==========================================

def test_tarea_completa_en_el_ecosistema_real(tmp_path, monkeypatch):
    import apollo.conocimiento as conocimiento
    monkeypatch.setattr(
        conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json")
    )
    from gaia import crear_ecosistema
    gaia = crear_ecosistema()

    gaia.pedir("hefesto", "apollo", "aprender_relacion",
               sujeto="pingüino", relacion="es", objeto="ave")

    plan = gaia.pedir("hefesto", "minerva", "planear",
                      tarea="investiga qué es un pingüino y calcula 1/3 + 1")["datos"]
    r = ejecutar_plan(gaia, plan)

    assert r["completada"] is True
    definicion, calculo = r["resultados"]
    assert "ave" in resumir("apollo", "definir", definicion["datos"])
    assert calculo["datos"]["resultado"] == "4/3"