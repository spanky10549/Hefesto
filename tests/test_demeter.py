"""
Pruebas de DEMETER: rutas (con sus trampas), zonas protegidas,
solicitudes, reglas, lo que sale por la red y que recuerde todo.
"""

import os
import threading

import pytest

from gaia import Gaia, OK, RECHAZADO
from demeter import Demeter, PERMITIR, NEGAR, PREGUNTAR
from demeter.rutas import esta_dentro, carpetas_personales
import demeter.servicio as servicio


# ==========================================
# RUTAS
# ==========================================

def test_dentro(tmp_path):
    fotos = tmp_path / "Fotos"
    assert esta_dentro(fotos / "vacaciones" / "playa.jpg", fotos)
    assert esta_dentro(fotos, fotos)


def test_trampa_del_nombre_parecido(tmp_path):
    """'Fotos2' empieza como 'Fotos', pero no está dentro."""
    assert not esta_dentro(tmp_path / "Fotos2" / "a.jpg", tmp_path / "Fotos")


def test_trampa_de_los_dos_puntos(tmp_path):
    """'Fotos/../Documentos' en realidad está en Documentos."""
    escondido = tmp_path / "Fotos" / ".." / "Documentos" / "x.txt"
    assert not esta_dentro(escondido, tmp_path / "Fotos")
    assert esta_dentro(escondido, tmp_path / "Documentos")


def test_carpetas_personales(tmp_path):
    (tmp_path / "Pictures").mkdir()
    (tmp_path / "Documents").mkdir()
    (tmp_path / "OneDrive" / "Desktop").mkdir(parents=True)

    nombres = [nombre for nombre, _ in carpetas_personales(tmp_path)]
    assert nombres == ["Imágenes", "Documentos", "Escritorio (OneDrive)"]


# ==========================================
# PREPARAR UN DEMETER DE PRUEBA
# ==========================================

@pytest.fixture
def casa(tmp_path):
    """Una 'computadora' de mentira con carpetas personales y la de FOCUS."""
    for carpeta in ("Fotos", "Videos", "FOCUS", "Libre"):
        (tmp_path / carpeta).mkdir()
    return tmp_path


@pytest.fixture
def demeter(casa):
    return Demeter(
        ruta_permisos=str(casa / "permisos.json"),
        carpeta_focus=str(casa / "FOCUS"),
        zonas_iniciales=[("Fotos", str(casa / "Fotos")), ("Videos", str(casa / "Videos"))],
    )


@pytest.fixture
def gaia(demeter):
    g = Gaia()
    g.registrar(demeter)
    return g


def solicitar(gaia, ruta, inteligencia="hefesto", operacion="leer"):
    return gaia.pedir("hefesto", "demeter", "solicitar",
                      inteligencia=inteligencia, ruta=str(ruta), operacion=operacion)


# ==========================================
# DECIDIR
# ==========================================

def test_zona_protegida_pregunta(gaia, casa):
    r = solicitar(gaia, casa / "Fotos" / "yo.jpg")["datos"]
    assert r["decision"] == PREGUNTAR
    assert r["zona"] == "Fotos"


def test_fuera_de_las_zonas_se_permite(gaia, casa):
    assert solicitar(gaia, casa / "Libre" / "nota.txt")["datos"]["decision"] == PERMITIR


def test_la_carpeta_de_focus_siempre_es_libre(gaia, casa):
    r = solicitar(gaia, casa / "FOCUS" / "documentos" / "ejemplo.txt")["datos"]
    assert r["decision"] == PERMITIR
    assert "FOCUS" in r["motivo"]


def test_focus_dentro_de_una_zona_sigue_libre(casa):
    """Si FOCUS vive dentro de Documentos, sus archivos siguen libres."""
    documentos = casa / "Documentos"
    (documentos / "FOCUS").mkdir(parents=True)
    d = Demeter(str(casa / "p.json"), str(documentos / "FOCUS"), [("Documentos", str(documentos))])

    assert d.decidir("hefesto", documentos / "FOCUS" / "a.txt", "leer")[0] == PERMITIR
    assert d.decidir("hefesto", documentos / "tarea.txt", "leer")[0] == PREGUNTAR


def test_gana_la_zona_mas_especifica(casa):
    (casa / "Fotos" / "Privadas").mkdir()
    d = Demeter(str(casa / "p.json"), str(casa / "FOCUS"), [
        ("Fotos", str(casa / "Fotos")),
        ("Privadas", str(casa / "Fotos" / "Privadas")),
    ])
    assert d.zona_de(casa / "Fotos" / "Privadas" / "x.jpg")["nombre"] == "Privadas"


@pytest.mark.parametrize("datos", [
    {"ruta": "x"},                                         # sin inteligencia
    {"inteligencia": "hefesto"},                           # sin ruta
    {"inteligencia": "hefesto", "ruta": "x", "operacion": "borrar"},
])
def test_solicitudes_incompletas(gaia, datos):
    assert gaia.pedir("hefesto", "demeter", "solicitar", **datos)["estado"] == RECHAZADO


# ==========================================
# REGLAS
# ==========================================

def conceder(gaia, decision, inteligencia="hefesto", zona="Fotos", operacion="leer"):
    return gaia.pedir("hefesto", "demeter", "conceder", inteligencia=inteligencia,
                      zona=zona, operacion=operacion, decision=decision)


def test_siempre(gaia, casa):
    conceder(gaia, PERMITIR)
    r = solicitar(gaia, casa / "Fotos" / "yo.jpg")["datos"]
    assert r["decision"] == PERMITIR
    assert r["motivo"] == "lo autorizaste"


def test_nunca_y_avisa(gaia, casa):
    negados = []
    gaia.suscribir("acceso_negado", negados.append)

    conceder(gaia, NEGAR)
    assert solicitar(gaia, casa / "Fotos" / "yo.jpg")["datos"]["decision"] == NEGAR
    assert negados[0]["datos"]["zona"] == "Fotos"


def test_la_regla_es_por_inteligencia_y_operacion(gaia, casa):
    conceder(gaia, PERMITIR, inteligencia="hefesto", operacion="leer")
    foto = casa / "Fotos" / "yo.jpg"
    assert solicitar(gaia, foto, inteligencia="minerva")["datos"]["decision"] == PREGUNTAR
    assert solicitar(gaia, foto, operacion="escribir")["datos"]["decision"] == PREGUNTAR


def test_cambiar_de_opinion(gaia, casa):
    conceder(gaia, PERMITIR)
    conceder(gaia, NEGAR)
    assert solicitar(gaia, casa / "Fotos" / "a.jpg")["datos"]["decision"] == NEGAR
    assert len(gaia.pedir("hefesto", "demeter", "permisos")["datos"]["reglas"]) == 1


def test_revocar(gaia, casa):
    conceder(gaia, PERMITIR)
    r = gaia.pedir("hefesto", "demeter", "revocar", zona="fotos")["datos"]     # sin importar mayúsculas
    assert r["borradas"] == 1
    assert solicitar(gaia, casa / "Fotos" / "a.jpg")["datos"]["decision"] == PREGUNTAR


def test_regla_en_zona_que_no_existe(gaia):
    assert conceder(gaia, PERMITIR, zona="Secretos")["estado"] == RECHAZADO


def test_decision_invalida(gaia):
    assert conceder(gaia, "tal vez")["estado"] == RECHAZADO


# ==========================================
# ZONAS
# ==========================================

def test_proteger_y_desproteger(gaia, casa):
    r = gaia.pedir("hefesto", "demeter", "proteger", ruta=str(casa / "Libre"))
    assert r["estado"] == OK
    assert solicitar(gaia, casa / "Libre" / "nota.txt")["datos"]["decision"] == PREGUNTAR

    gaia.pedir("hefesto", "demeter", "desproteger", nombre="Libre")
    assert solicitar(gaia, casa / "Libre" / "nota.txt")["datos"]["decision"] == PERMITIR


def test_no_se_protege_lo_que_no_existe(gaia, casa):
    assert gaia.pedir("hefesto", "demeter", "proteger", ruta=str(casa / "Nada"))["estado"] == RECHAZADO


def test_no_se_protege_la_carpeta_de_focus(gaia, casa):
    r = gaia.pedir("hefesto", "demeter", "proteger", ruta=str(casa / "FOCUS"))
    assert r["estado"] == RECHAZADO


def test_no_se_repiten_nombres(gaia, casa):
    (casa / "Otra" / "Fotos").mkdir(parents=True)
    r = gaia.pedir("hefesto", "demeter", "proteger", ruta=str(casa / "Otra" / "Fotos"))
    assert r["estado"] == RECHAZADO


def test_desproteger_borra_sus_reglas(gaia):
    conceder(gaia, PERMITIR)
    gaia.pedir("hefesto", "demeter", "desproteger", nombre="Fotos")
    assert gaia.pedir("hefesto", "demeter", "permisos")["datos"]["reglas"] == []


# ==========================================
# RECORDAR
# ==========================================

def test_recuerda_zonas_y_reglas(demeter, casa):
    demeter.conceder({"inteligencia": "hefesto", "zona": "Fotos", "operacion": "leer", "decision": PERMITIR})

    otra_sesion = Demeter(str(casa / "permisos.json"), str(casa / "FOCUS"), zonas_iniciales=[])
    assert [z["nombre"] for z in otra_sesion.zonas] == ["Fotos", "Videos"]
    assert otra_sesion.decidir("hefesto", casa / "Fotos" / "a.jpg", "leer")[0] == PERMITIR


def test_las_pruebas_no_tocan_los_permisos_reales(tmp_path):
    assert servicio.ARCHIVO_PERMISOS.startswith(str(tmp_path.parent))


# ==========================================
# LO QUE SALE POR LA RED
# ==========================================

def test_revisar_salida(gaia, casa):
    foto = str(casa / "Fotos" / "yo.jpg")
    r = gaia.pedir("hefesto", "demeter", "revisar_salida", destino="rover_1",
                   mensaje={"datos": {"archivos": [foto, "1/3 + 1"]}})["datos"]
    assert r["puede_salir"] is False
    assert r["bloqueos"] == [{"ruta": foto, "zona": "Fotos"}]


def test_salida_sin_rutas(gaia):
    r = gaia.pedir("hefesto", "demeter", "revisar_salida", destino="rover_1",
                   mensaje={"datos": {"x": 3, "y": 4, "operacion": "1/3"}})["datos"]
    assert r["puede_salir"] is True


def test_salida_con_permiso_de_compartir(gaia, casa):
    conceder(gaia, PERMITIR, inteligencia="rover_1", operacion="compartir")
    r = gaia.pedir("hefesto", "demeter", "revisar_salida", destino="rover_1",
                   mensaje={"datos": {"foto": str(casa / "Fotos" / "yo.jpg")}})["datos"]
    assert r["puede_salir"] is True


def test_el_rover_no_recibe_rutas_protegidas(casa):
    """Una orden con la ruta de una foto no sale por la red; las normales sí."""
    from gaia.red import InteligenciaRemota
    from poseidon import Guardia
    from rover.robot import Rover
    from rover.servidor import ServidorRover

    clave = "clave-de-prueba"
    robot = Rover(obstaculos=set())
    srv = ServidorRover(robot, Guardia(clave), puerto=0, mostrar=lambda t: None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    try:
        g = Gaia()
        g.registrar(Demeter(str(casa / "p.json"), str(casa / "FOCUS"), [("Fotos", str(casa / "Fotos"))]))
        bloqueos = []
        g.suscribir("salida_bloqueada", bloqueos.append)

        remoto = InteligenciaRemota("rover_1", "127.0.0.1", srv.puerto, Guardia(clave), tiempo_espera=3)
        assert remoto.conectar()
        g.registrar(remoto)

        r = g.pedir("hefesto", "rover_1", "ir_a", x=1, y=0, foto=str(casa / "Fotos" / "yo.jpg"))
        assert r["estado"] == RECHAZADO
        assert "DEMETER" in r["detalle"]
        assert robot.posicion == (0, 0)          # la orden ni llegó
        assert bloqueos[0]["datos"]["zonas"] == ["Fotos"]

        assert g.pedir("hefesto", "rover_1", "ir_a", x=1, y=0)["estado"] == OK
    finally:
        srv.shutdown()
        srv.server_close()


def test_demeter_en_el_ecosistema():
    from gaia import crear_ecosistema
    assert "demeter" in crear_ecosistema().directorio()