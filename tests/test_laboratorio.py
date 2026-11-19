"""
Pruebas del laboratorio de innovación (MINERVA): proyectos, árbol de
capacidades, estados calculados, avance, estrategias, la siguiente
sugerida y su conexión con los experimentos de ELEUTHIA.
"""

import pytest

from gaia import Gaia, OK, RECHAZADO
from minerva import Minerva
from minerva.laboratorio import (
    Laboratorio, ErrorLaboratorio, cargar_plantilla_focus, palabras_clave,
    EXISTE, A_MEDIAS, FALTA,
)
from eleuthia import Eleuthia
import minerva.laboratorio as laboratorio


@pytest.fixture
def lab(tmp_path):
    return Laboratorio(str(tmp_path / "lab.json"))


@pytest.fixture
def rover(lab):
    """Un proyecto chico: un rover con dos ramas."""
    lab.crear_proyecto("Rover", "un rover que explore solo")
    mover = lab.agregar("Rover", "Moverse")                                   # 1
    lab.agregar("Rover", "Motores", mover["id"], EXISTE)                     # 2
    lab.agregar("Rover", "Esquivar obstáculos", mover["id"], A_MEDIAS)       # 3
    ver = lab.agregar("Rover", "Ver el entorno")                             # 4
    lab.agregar("Rover", "Sensor de distancia", ver["id"], FALTA)            # 5
    lab.agregar("Rover", "Cámara", ver["id"], FALTA)                         # 6
    return lab


def proyecto(lab, nombre="Rover"):
    return lab.proyecto(nombre)


# ==========================================
# PROYECTOS
# ==========================================

def test_crear_y_buscar_sin_importar_acentos(lab):
    lab.crear_proyecto("Exploración", "meta")
    assert lab.proyecto("exploracion")["nombre"] == "Exploración"


def test_no_repetir_proyectos(lab):
    lab.crear_proyecto("Rover", "a")
    with pytest.raises(ErrorLaboratorio):
        lab.crear_proyecto("rover", "b")


def test_proyecto_sin_nombre(lab):
    with pytest.raises(ErrorLaboratorio):
        lab.crear_proyecto("  ", "meta")


def test_se_guarda(rover, tmp_path):
    otro = Laboratorio(str(tmp_path / "lab.json"))
    assert len(otro.proyecto("Rover")["capacidades"]) == 6


def test_borrar_proyecto(rover):
    rover.borrar_proyecto("rover")
    assert rover.resumen() == []


# ==========================================
# ÁRBOL Y ESTADOS
# ==========================================

def test_estados_calculados(rover):
    p = proyecto(rover)
    assert rover.estado_de(p, 1) == A_MEDIAS      # motores ✅ + esquivar 🟡
    assert rover.estado_de(p, 4) == FALTA         # todo ❌


def test_todo_existe_en_una_rama(rover):
    rover.marcar("Rover", 3, EXISTE)
    assert rover.estado_de(proyecto(rover), 1) == EXISTE


def test_avance(rover):
    # hojas: ✅ 🟡 ❌ ❌ → (1 + 0.5) / 4 = 37.5 → 38
    assert rover.avance(proyecto(rover)) == 38
    assert rover.avance(proyecto(rover), 1) == 75     # solo la rama "Moverse"


def test_avance_sin_capacidades(lab):
    lab.crear_proyecto("Vacío", "nada")
    assert lab.avance(lab.proyecto("Vacío")) == 0


def test_arbol_en_orden(rover):
    arbol = rover.arbol("Rover")
    assert [(c["id"], c["nivel"]) for c in arbol["capacidades"]] == [(1, 0), (2, 1), (3, 1), (4, 0), (5, 1), (6, 1)]
    assert arbol["capacidades"][0]["es_hoja"] is False
    assert arbol["avance"] == 38


def test_no_se_marca_una_capacidad_con_hijas(rover):
    with pytest.raises(ErrorLaboratorio, match="sub-capacidades"):
        rover.marcar("Rover", 1, EXISTE)


@pytest.mark.parametrize("args", [("Rover", 99, EXISTE), ("Rover", 2, "casi"), ("Nada", 2, EXISTE)])
def test_marcar_mal(rover, args):
    with pytest.raises(ErrorLaboratorio):
        rover.marcar(*args)


def test_agregar_con_padre_que_no_existe(rover):
    with pytest.raises(ErrorLaboratorio):
        rover.agregar("Rover", "algo", padre=99)


def test_quitar_rama_completa(rover):
    assert rover.quitar("Rover", 4) == [4, 5, 6]
    assert len(proyecto(rover)["capacidades"]) == 3


def test_los_numeros_no_se_reutilizan(rover):
    rover.quitar("Rover", 6)
    assert rover.agregar("Rover", "Nueva")["id"] == 7


# ==========================================
# ESTRATEGIAS
# ==========================================

def estrategias(lab, numero, experimentos=()):
    return [i["estrategia"] for i in lab.estrategias("Rover", numero, experimentos)["ideas"]]


def test_palabras_clave():
    assert palabras_clave("Sensor de la Cámara") == {"sensor", "camara"}


def test_hardware_sugiere_simular_y_enchufe(rover):
    ideas = estrategias(rover, 5)        # Sensor de distancia
    assert "simular" in ideas and "enchufe primero" in ideas


def test_a_medias_sugiere_aproximar(rover):
    assert "aproximar" in estrategias(rover, 3)


def test_lo_que_falta_sugiere_dividir_y_crear(rover):
    rover.agregar("Rover", "Planear rutas")       # 7, sin hardware
    ideas = estrategias(rover, 7)
    assert "dividir" in ideas and "crear desde cero" in ideas
    assert "simular" not in ideas


def test_combinar_con_lo_que_se_parece(rover):
    rover.agregar("Rover", "Motores con encoder")   # 7: comparte "motores" con #2
    ideas = rover.estrategias("Rover", 7)["ideas"]
    combinar = [i for i in ideas if i["estrategia"] == "combinar"]
    assert combinar and "#2 Motores" in combinar[0]["idea"]


def test_lo_que_ya_existe_solo_se_mejora(rover):
    assert estrategias(rover, 2) == ["mejorar"]


def test_rama_con_hijas_sugiere_trabajar_en_sus_partes(rover):
    (idea,) = rover.estrategias("Rover", 4)["ideas"]
    assert "Sensor de distancia" in idea["idea"] and "Cámara" in idea["idea"]


def test_no_repetir_lo_que_fallo(rover):
    fallido = {"intento": "sensor infrarrojo barato", "resultado": "falló",
               "aprendizaje": "con el sol no funciona"}
    ideas = rover.estrategias("Rover", 5, [fallido])["ideas"]
    (no_repetir,) = [i for i in ideas if i["estrategia"] == "no repetir"]
    assert "sensor infrarrojo barato" in no_repetir["idea"]
    assert "con el sol no funciona" in no_repetir["idea"]


# ==========================================
# SIGUIENTE SUGERIDA
# ==========================================

def test_primero_lo_que_va_a_medias(rover):
    assert rover.siguiente("Rover")["id"] == 3


def test_luego_lo_que_no_depende_de_hardware(rover):
    rover.marcar("Rover", 3, EXISTE)
    rover.agregar("Rover", "Planear rutas")       # 7
    assert rover.siguiente("Rover")["id"] == 7    # antes que el sensor o la cámara


def test_lo_que_mas_ha_fallado_va_despues(rover):
    rover.marcar("Rover", 3, EXISTE)
    assert rover.siguiente("Rover", {5: 3})["id"] == 6


def test_nada_pendiente(rover):
    for numero in (3, 5, 6):
        rover.marcar("Rover", numero, EXISTE)
    assert rover.siguiente("Rover") is None


# ==========================================
# EL PROYECTO FOCUS
# ==========================================

def test_plantilla_focus(lab):
    p = cargar_plantilla_focus(lab)
    arbol = lab.arbol("FOCUS")
    assert len(p["capacidades"]) == 21
    assert [c["nombre"] for c in arbol["capacidades"] if c["nivel"] == 0] == [
        "Nivel 3: el ecosistema en el mundo real",
        "Nivel 4: autónomo supervisado",
        "Nivel 5: cognitivo integrado",
    ]
    assert 0 < arbol["avance"] < 50


def test_plantilla_focus_solo_una_vez(lab):
    cargar_plantilla_focus(lab)
    with pytest.raises(ErrorLaboratorio):
        cargar_plantilla_focus(lab)


# ==========================================
# MINERVA Y ELEUTHIA (por mensajes)
# ==========================================

@pytest.fixture
def gaia(tmp_path):
    g = Gaia()
    g.registrar(Minerva(Laboratorio(str(tmp_path / "lab.json"))))
    g.registrar(Eleuthia(str(tmp_path), str(tmp_path / "bitacora.jsonl")))
    return g


def m(gaia, accion, **datos):
    return gaia.pedir("hefesto", "minerva", accion, **datos)


def test_flujo_completo(gaia):
    assert m(gaia, "crear_proyecto", nombre="Rover", meta="explorar")["estado"] == OK
    m(gaia, "agregar_capacidad", proyecto="Rover", nombre="Planear rutas")       # 1
    m(gaia, "agregar_capacidad", proyecto="Rover", nombre="Guardar el mapa")      # 2

    # Un experimento que falló en la #1
    gaia.pedir("hefesto", "eleuthia", "experimento", proyecto="Rover", capacidad=1,
               intento="ir siempre derecho", resultado="falló", aprendizaje="choca con todo")

    ideas = m(gaia, "estrategias", proyecto="rover", capacidad=1)["datos"]["ideas"]
    assert any("ir siempre derecho" in i["idea"] for i in ideas)

    # La que falló se deja para después: sugiere la #2
    assert m(gaia, "siguiente", proyecto="Rover")["datos"]["siguiente"]["id"] == 2

    m(gaia, "marcar", proyecto="Rover", capacidad=1, estado="existe")
    vista = m(gaia, "proyecto", nombre="Rover")["datos"]
    assert vista["avance"] == 50
    assert vista["siguiente"]["id"] == 2


def test_errores_se_vuelven_rechazos(gaia):
    assert m(gaia, "proyecto", nombre="Nada")["estado"] == RECHAZADO
    assert m(gaia, "marcar", proyecto="Nada", capacidad=1, estado="existe")["estado"] == RECHAZADO


def test_experimentos_por_capacidad(gaia):
    for capacidad in (1, 1, 2):
        gaia.pedir("hefesto", "eleuthia", "experimento", proyecto="P", capacidad=capacidad,
                   intento="x", resultado="falló")
    r = gaia.pedir("hefesto", "eleuthia", "experimentos", proyecto="P", capacidad=1)["datos"]
    assert len(r["experimentos"]) == 2


def test_capacidad_invalida_en_experimento(gaia):
    r = gaia.pedir("hefesto", "eleuthia", "experimento", proyecto="P", capacidad="uno",
                   intento="x", resultado="falló")
    assert r["estado"] == RECHAZADO


def test_cargar_focus_por_mensaje(gaia):
    assert m(gaia, "cargar_focus")["datos"]["capacidades"] == 21
    assert m(gaia, "cargar_focus")["estado"] == RECHAZADO      # ya existe


def test_las_pruebas_no_tocan_el_laboratorio_real(tmp_path):
    assert laboratorio.ARCHIVO_LABORATORIO.startswith(str(tmp_path.parent))