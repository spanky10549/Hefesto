"""
Pruebas de las rutinas de MINERVA: enseñar, validar (pasos que no
entiende, círculos, nombres que tapan comandos), anidar, olvidar y
usarlas en un plan. También los pasos nuevos que entiende el planeador.
"""

import pytest

from gaia import Gaia, OK, RECHAZADO
from minerva import Minerva
from minerva.planeador import planear, interpretar, nombre_de_rutina, expandir, MAX_PROFUNDIDAD
from minerva.rutinas import Rutinas, ErrorRutina
from minerva.laboratorio import Laboratorio
from conversacion.resultados import resumir
import minerva.rutinas as modulo_rutinas


@pytest.fixture
def rutinas(tmp_path):
    return Rutinas(str(tmp_path / "rutinas.json"))


# ==========================================
# PASOS NUEVOS QUE ENTIENDE EL PLANEADOR
# ==========================================

@pytest.mark.parametrize("parte, para, accion", [
    ("revisa los incidentes", "hades", "incidentes"),
    ("revisa el entorno", "eter", "entorno"),
    ("checa los sensores", "eter", "entorno"),
    ("entorno", "eter", "entorno"),
    ("revisa la seguridad", "poseidon", "reporte"),
    ("respalda", "eleuthia", "respaldar"),
    ("haz un respaldo", "eleuthia", "respaldar"),
])
def test_pasos_nuevos(parte, para, accion):
    paso = interpretar(parte)
    assert (paso["para"], paso["accion"]) == (para, accion)


def test_el_entorno_se_lee_antes():
    assert interpretar("revisa el entorno")["datos"] == {"actualizar": True}


def test_y_respalda_divide_la_tarea():
    plan = planear("revisa los recursos y respalda")
    assert [p["para"] for p in plan["pasos"]] == ["artemis", "eleuthia"]


# ==========================================
# NOMBRES
# ==========================================

@pytest.mark.parametrize("texto", [
    "checa todo", "Checa Todo", "haz la rutina checa todo", 'la rutina "Checa todo"', "  checa   todo. ",
])
def test_nombre_de_rutina(texto):
    assert nombre_de_rutina(texto) == "checa todo"


# ==========================================
# ENSEÑAR
# ==========================================

def test_ensenar(rutinas):
    r = rutinas.ensenar('"Checa todo"', "revisa los recursos, revisa los errores y revisa el entorno")
    assert r["nombre"] == "Checa todo"
    assert r["pasos"] == ["revisa los recursos", "revisa los errores", "revisa el entorno"]
    assert r["reemplazada"] is False


def test_volver_a_ensenar_la_reemplaza(rutinas):
    rutinas.ensenar("checa todo", "revisa los recursos")
    r = rutinas.ensenar("checa todo", "revisa los errores")
    assert r["reemplazada"] is True
    assert len(rutinas.listar()) == 1


def test_pasos_que_no_entiende(rutinas):
    with pytest.raises(ErrorRutina, match="baila salsa"):
        rutinas.ensenar("fiesta", "baila salsa y revisa los recursos")


def test_sin_pasos(rutinas):
    with pytest.raises(ErrorRutina):
        rutinas.ensenar("vacía", "  ")


def test_sin_nombre(rutinas):
    with pytest.raises(ErrorRutina):
        rutinas.ensenar('""', "revisa los recursos")


def test_el_nombre_no_puede_tapar_un_comando(rutinas):
    with pytest.raises(ErrorRutina, match="ya es algo que sé hacer"):
        rutinas.ensenar("revisa los recursos", "revisa los errores")


def test_usar_otra_rutina(rutinas):
    rutinas.ensenar("checa todo", "revisa los recursos y revisa los errores")
    r = rutinas.ensenar("buenos días", "checa todo y respalda")
    assert r["pasos"] == ["checa todo", "respalda"]


def test_circulo_directo(rutinas):
    with pytest.raises(ErrorRutina, match="círculo"):
        rutinas.ensenar("a", "a")


def test_circulo_indirecto(rutinas):
    rutinas.ensenar("a", "revisa los recursos")
    rutinas.ensenar("b", "a y revisa los errores")
    with pytest.raises(ErrorRutina, match="círculo"):
        rutinas.ensenar("a", "b")


def test_se_guardan(rutinas, tmp_path):
    rutinas.ensenar("checa todo", "revisa los recursos")
    assert "checa todo" in Rutinas(str(tmp_path / "rutinas.json")).todas()


# ==========================================
# OLVIDAR
# ==========================================

def test_olvidar(rutinas):
    rutinas.ensenar("checa todo", "revisa los recursos")
    assert rutinas.olvidar("Checa todo")["nombre"] == "checa todo"
    assert rutinas.listar() == []


def test_olvidar_avisa_quien_la_usaba(rutinas):
    rutinas.ensenar("checa todo", "revisa los recursos")
    rutinas.ensenar("buenos días", "checa todo y respalda")
    assert rutinas.olvidar("checa todo")["la_usaban"] == ["buenos días"]


def test_olvidar_una_que_no_existe(rutinas):
    with pytest.raises(ErrorRutina):
        rutinas.olvidar("nada")


# ==========================================
# PLANEAR CON RUTINAS
# ==========================================

def test_planear_expande_rutinas(rutinas):
    rutinas.ensenar("checa todo", "revisa los recursos y revisa los errores")
    plan = planear("checa todo y calcula 2 + 2", rutinas.todas())

    assert [p["para"] for p in plan["pasos"]] == ["artemis", "tabris", "calculadora"]
    assert plan["pasos"][0]["descripcion"] == "[checa todo] revisa los recursos"
    assert [p["numero"] for p in plan["pasos"]] == [1, 2, 3]


def test_rutinas_anidadas(rutinas):
    rutinas.ensenar("checa todo", "revisa los recursos y revisa los errores")
    rutinas.ensenar("buenos días", "checa todo y respalda")
    plan = planear("buenos días", rutinas.todas())

    assert [p["para"] for p in plan["pasos"]] == ["artemis", "tabris", "eleuthia"]
    assert plan["pasos"][0]["descripcion"] == "[buenos días] [checa todo] revisa los recursos"


def test_paso_que_era_una_rutina_olvidada(rutinas):
    rutinas.ensenar("checa todo", "revisa los recursos")
    rutinas.ensenar("buenos días", "checa todo y respalda")
    rutinas.olvidar("checa todo")

    plan = planear("buenos días", rutinas.todas())
    assert [p["para"] for p in plan["pasos"]] == ["eleuthia"]
    assert plan["no_entendidos"] == ["[buenos días] checa todo"]


def test_un_circulo_guardado_a_mano_no_cuelga_nada():
    """Aunque alguien edite el archivo y meta un círculo, expandir se detiene."""
    a_mano = {"a": {"nombre": "a", "pasos": ["b"]}, "b": {"nombre": "b", "pasos": ["a"]}}
    resultado = expandir("a", a_mano)
    assert resultado[-1][1] is None             # se detuvo, no siguió para siempre


# ==========================================
# MINERVA POR MENSAJES
# ==========================================

@pytest.fixture
def gaia(tmp_path):
    g = Gaia()
    g.registrar(Minerva(Laboratorio(str(tmp_path / "lab.json")), Rutinas(str(tmp_path / "r.json"))))
    return g


def m(gaia, accion, **datos):
    return gaia.pedir("hefesto", "minerva", accion, **datos)


def test_minerva_ensena_y_planea(gaia):
    assert m(gaia, "ensenar_rutina", nombre="checa todo", pasos="revisa los recursos")["estado"] == OK
    assert m(gaia, "es_rutina", texto="Checa todo")["datos"]["es_rutina"] is True
    assert m(gaia, "es_rutina", texto="otra cosa")["datos"]["es_rutina"] is False

    plan = m(gaia, "planear", tarea="checa todo")["datos"]
    assert plan["pasos"][0]["para"] == "artemis"


def test_minerva_rechaza_rutinas_malas(gaia):
    r = m(gaia, "ensenar_rutina", nombre="fiesta", pasos="baila salsa")
    assert r["estado"] == RECHAZADO
    assert "baila salsa" in r["detalle"]


def test_minerva_olvida(gaia):
    m(gaia, "ensenar_rutina", nombre="checa todo", pasos="revisa los recursos")
    m(gaia, "olvidar_rutina", nombre="checa todo")
    assert m(gaia, "rutinas")["datos"]["rutinas"] == []


# ==========================================
# RESUMIR LOS PASOS NUEVOS
# ==========================================

def test_resumir_entorno():
    datos = {"sensores": [{"tipo": "señal_wifi", "valor": 87, "unidad": "%", "etiqueta": "buena", "raro": []}]}
    assert resumir("eter", "entorno", datos) == "señal del WiFi 87 % (buena)."


def test_resumir_entorno_vacio():
    assert resumir("eter", "entorno", {"sensores": []}) == "no hay sensores activos."


def test_resumir_incidentes():
    assert resumir("hades", "incidentes", {"incidentes": [{"inteligencia": "apollo"}]}) == "incidentes abiertos: APOLLO."


def test_resumir_respaldo():
    texto = resumir("eleuthia", "respaldar", {"nombre": "respaldo_x.zip", "archivos": ["a", "b"]})
    assert texto == "guardé respaldo_x.zip (2 archivos)."


def test_las_pruebas_no_tocan_las_rutinas_reales(tmp_path):
    assert modulo_rutinas.ARCHIVO_RUTINAS.startswith(str(tmp_path.parent))