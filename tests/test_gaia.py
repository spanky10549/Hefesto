"""
Pruebas de GAIA: mensajes, entrega, fallos, eventos e historial,
y que APOLLO y la calculadora respondan por mensajes.
"""

import json
import pytest

from gaia import Gaia, Inteligencia, Rechazo, OK, RECHAZADO, ERROR, DESCONOCIDO
from gaia.mensajes import (
    crear_orden, crear_respuesta, crear_evento,
    validar, a_json, de_json, MensajeInvalido, ORDEN, RESPUESTA, EVENTO,
)


# ==========================================
# INTELIGENCIAS DE PRUEBA
# ==========================================

class Eco(Inteligencia):
    nombre = "eco"
    descripcion = "Repite lo que le dicen."

    def __init__(self):
        self.acciones = {
            "repetir": lambda datos: {"texto": datos.get("texto", "")},
            "rechazar": self.rechazar,
            "tronar": self.tronar,
            "nada": lambda datos: None,
            "lista": lambda datos: ["no", "es", "dict"],
            "conjunto": lambda datos: {"valores": {1, 2}},
        }

    def rechazar(self, datos):
        raise Rechazo("no quiero")

    def tronar(self, datos):
        return 1 / 0


class Preguntona(Inteligencia):
    """Le pide ayuda a otra inteligencia a través de GAIA."""
    nombre = "preguntona"

    def __init__(self):
        self.acciones = {"preguntar_a_eco": self.preguntar}

    def preguntar(self, datos):
        respuesta = self.gaia.pedir(self.nombre, "eco", "repetir", texto="hola")
        return {"eco_dijo": respuesta["datos"]["texto"]}


@pytest.fixture
def gaia():
    g = Gaia()
    g.registrar(Eco())
    return g


# ==========================================
# MENSAJES
# ==========================================

def test_orden_tiene_todo():
    orden = crear_orden("hefesto", "apollo", "definir", {"concepto": "ave"})
    assert validar(orden) is orden
    assert orden["tipo"] == ORDEN
    assert orden["datos"] == {"concepto": "ave"}
    assert orden["restricciones"] == {}
    assert len(orden["id"]) == 32


def test_ordenes_con_objetivo_y_plan_b():
    orden = crear_orden(
        "hefesto", "rover_1", "avanzar", {"cm": 50},
        objetivo="llegar a la cocina",
        restricciones={"bateria_minima": 20},
        si_falla="buscar otra ruta",
    )
    assert orden["objetivo"] == "llegar a la cocina"
    assert orden["restricciones"]["bateria_minima"] == 20
    assert orden["si_falla"] == "buscar otra ruta"


def test_cada_mensaje_tiene_id_distinto():
    assert crear_orden("a", "b", "c")["id"] != crear_orden("a", "b", "c")["id"]


def test_respuesta_va_de_regreso():
    orden = crear_orden("hefesto", "apollo", "definir")
    respuesta = crear_respuesta(orden, OK, {"x": 1})
    assert respuesta["tipo"] == RESPUESTA
    assert respuesta["de"] == "apollo"
    assert respuesta["para"] == "hefesto"
    assert respuesta["responde_a"] == orden["id"]
    validar(respuesta)


def test_respuesta_con_estado_inventado():
    with pytest.raises(MensajeInvalido):
        crear_respuesta(crear_orden("a", "b", "c"), "más o menos")


def test_evento_es_para_todos():
    evento = crear_evento("gaia", "fallo", {"x": 1})
    assert evento["tipo"] == EVENTO
    assert evento["para"] == "*"
    validar(evento)


@pytest.mark.parametrize("mensaje", [
    "no soy un dict",
    {},
    {**crear_orden("a", "b", "c"), "tipo": "chisme"},
    {**crear_orden("a", "b", "c"), "para": ""},
    {**crear_orden("a", "b", "c"), "datos": [1, 2]},
    {**crear_respuesta(crear_orden("a", "b", "c"), OK), "estado": None},
])
def test_mensajes_invalidos(mensaje):
    with pytest.raises(MensajeInvalido):
        validar(mensaje)


def test_ida_y_vuelta_por_json():
    orden = crear_orden("hefesto", "apollo", "definir", {"concepto": "pingüino"})
    texto = a_json(orden)
    assert "pingüino" in texto          # sin ü: legible
    assert de_json(texto) == orden


def test_json_roto():
    with pytest.raises(MensajeInvalido):
        de_json("{esto no es json")


def test_lo_que_no_viaja_por_la_red():
    with pytest.raises(MensajeInvalido):
        a_json(crear_orden("a", "b", "c", {"valores": {1, 2}}))


# ==========================================
# DIRECTORIO
# ==========================================

def test_registrar_y_directorio(gaia):
    ficha = gaia.directorio()["eco"]
    assert ficha["descripcion"] == "Repite lo que le dicen."
    assert "repetir" in ficha["acciones"]


def test_no_se_repiten_nombres(gaia):
    with pytest.raises(ValueError):
        gaia.registrar(Eco())


def test_nadie_se_llama_gaia(gaia):
    class Impostora(Inteligencia):
        nombre = "gaia"
    with pytest.raises(ValueError):
        gaia.registrar(Impostora())


def test_sin_nombre(gaia):
    with pytest.raises(ValueError):
        gaia.registrar(Inteligencia())


def test_quien_sabe(gaia):
    assert gaia.quien_sabe("repetir") == ["eco"]
    assert gaia.quien_sabe("volar") == []


def test_retirar(gaia):
    gaia.retirar("eco")
    assert "eco" not in gaia.directorio()
    assert gaia.pedir("hefesto", "eco", "repetir")["estado"] == DESCONOCIDO
    gaia.retirar("eco")   # retirar dos veces no truena


# ==========================================
# ENTREGA
# ==========================================

def test_pedir_bien(gaia):
    respuesta = gaia.pedir("hefesto", "eco", "repetir", texto="hola")
    assert respuesta["estado"] == OK
    assert respuesta["datos"] == {"texto": "hola"}
    assert respuesta["de"] == "eco"
    assert respuesta["para"] == "hefesto"


def test_destino_desconocido(gaia):
    respuesta = gaia.pedir("hefesto", "minerva", "planear")
    assert respuesta["estado"] == DESCONOCIDO
    assert "minerva" in respuesta["detalle"]


def test_accion_desconocida(gaia):
    respuesta = gaia.pedir("hefesto", "eco", "volar")
    assert respuesta["estado"] == DESCONOCIDO
    assert "volar" in respuesta["detalle"]


def test_rechazo(gaia):
    respuesta = gaia.pedir("hefesto", "eco", "rechazar")
    assert respuesta["estado"] == RECHAZADO
    assert respuesta["detalle"] == "no quiero"


def test_un_fallo_no_tumba_a_gaia(gaia):
    respuesta = gaia.pedir("hefesto", "eco", "tronar")
    assert respuesta["estado"] == ERROR
    assert "ZeroDivisionError" in respuesta["detalle"]

    # Y sigue funcionando
    assert gaia.pedir("hefesto", "eco", "repetir", texto="sigo")["estado"] == OK


def test_respuesta_vacia_es_dict(gaia):
    respuesta = gaia.pedir("hefesto", "eco", "nada")
    assert respuesta["estado"] == OK
    assert respuesta["datos"] == {}


def test_respuesta_que_no_es_dict(gaia):
    assert gaia.pedir("hefesto", "eco", "lista")["estado"] == ERROR


def test_respuesta_que_no_viaja_por_la_red(gaia):
    assert gaia.pedir("hefesto", "eco", "conjunto")["estado"] == ERROR


def test_orden_sin_json_no_sale(gaia):
    with pytest.raises(MensajeInvalido):
        gaia.pedir("hefesto", "eco", "repetir", texto={1, 2})


def test_enviar_solo_acepta_ordenes(gaia):
    with pytest.raises(MensajeInvalido):
        gaia.enviar(crear_evento("hefesto", "hola"))


def test_la_inteligencia_recibe_una_copia(gaia):
    """Como por la red: si la inteligencia cambia los datos, el original no cambia."""
    class Traviesa(Inteligencia):
        nombre = "traviesa"
        def __init__(self):
            self.acciones = {"cambiar": self.cambiar}
        def cambiar(self, datos):
            datos["lista"].append("extra")
            return {}

    gaia.registrar(Traviesa())
    orden = crear_orden("hefesto", "traviesa", "cambiar", {"lista": [1]})
    gaia.enviar(orden)
    assert orden["datos"]["lista"] == [1]


def test_inteligencias_que_se_piden_cosas(gaia):
    gaia.registrar(Preguntona())
    respuesta = gaia.pedir("hefesto", "preguntona", "preguntar_a_eco")
    assert respuesta["datos"] == {"eco_dijo": "hola"}


# ==========================================
# EVENTOS
# ==========================================

def test_evento_de_fallo(gaia):
    fallos = []
    gaia.suscribir("fallo", fallos.append)

    gaia.pedir("hefesto", "eco", "tronar")

    assert len(fallos) == 1
    assert fallos[0]["datos"]["inteligencia"] == "eco"
    assert fallos[0]["datos"]["accion"] == "tronar"


def test_evento_de_registro():
    g = Gaia()
    registros = []
    g.suscribir("registro", registros.append)
    g.registrar(Eco())
    assert registros[0]["datos"]["nombre"] == "eco"


def test_escuchar_todo(gaia):
    todos = []
    gaia.suscribir("*", todos.append)
    gaia.publicar(crear_evento("hefesto", "aprendi", {"concepto": "ave"}))
    gaia.publicar(crear_evento("hefesto", "otra_cosa"))
    assert [e["accion"] for e in todos] == ["aprendi", "otra_cosa"]


def test_oyente_roto_no_detiene_a_los_demas(gaia):
    escuchados = []
    gaia.suscribir("aviso", lambda e: 1 / 0)
    gaia.suscribir("aviso", escuchados.append)
    gaia.publicar(crear_evento("hefesto", "aviso"))
    assert len(escuchados) == 1


# ==========================================
# HISTORIAL
# ==========================================

def test_historial_guarda_orden_y_respuesta():
    g = Gaia()
    g.registrar(Eco())
    g.pedir("hefesto", "eco", "repetir", texto="hola")

    orden, respuesta = g.ultimos(2)
    assert orden["tipo"] == ORDEN
    assert respuesta["responde_a"] == orden["id"]


def test_historial_por_tipo(gaia):
    gaia.pedir("hefesto", "eco", "repetir")
    gaia.pedir("hefesto", "eco", "repetir")
    assert len(gaia.ultimos(10, tipo=ORDEN)) == 2


def test_historial_tiene_limite():
    g = Gaia(max_historial=5)
    g.registrar(Eco())
    for _ in range(10):
        g.pedir("hefesto", "eco", "repetir")
    assert len(g.historial) == 5


# ==========================================
# APOLLO Y CALCULADORA POR MENSAJES
# ==========================================

@pytest.fixture
def ecosistema(tmp_path, monkeypatch):
    import apollo.conocimiento as conocimiento
    monkeypatch.setattr(
        conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json")
    )
    from gaia import crear_ecosistema
    return crear_ecosistema()


def test_ecosistema_conectado(ecosistema):
    assert set(ecosistema.directorio()) == {"tabris", "hades", "apollo", "calculadora", "artemis"}


def test_calcular_por_mensaje(ecosistema):
    respuesta = ecosistema.pedir("hefesto", "calculadora", "calcular", operacion="1 / 3 + 1")
    assert respuesta["estado"] == OK
    assert respuesta["datos"]["resultado"] == "4/3"
    json.dumps(respuesta)   # se puede mandar por la red


def test_calcular_entre_cero_es_rechazo(ecosistema):
    respuesta = ecosistema.pedir("hefesto", "calculadora", "calcular", operacion="5 / 0")
    assert respuesta["estado"] == RECHAZADO


def test_calcular_sin_operacion(ecosistema):
    assert ecosistema.pedir("hefesto", "calculadora", "calcular")["estado"] == RECHAZADO


def test_apollo_aprende_y_responde(ecosistema):
    ecosistema.pedir("hefesto", "apollo", "aprender_relacion",
                     sujeto="ave", relacion="puede", objeto="volar")
    ecosistema.pedir("hefesto", "apollo", "aprender_relacion",
                     sujeto="pingüino", relacion="es", objeto="ave")

    respuesta = ecosistema.pedir("hefesto", "apollo", "responder",
                                 sujeto="pingüino", relacion="puede", objeto="volar")

    assert respuesta["estado"] == OK
    assert respuesta["datos"]["respuesta"] == "sí"
    assert len(respuesta["datos"]["cadena"]) == 2


def test_apollo_define_por_mensaje(ecosistema):
    from conversacion.redaccion import redactar_definicion

    ecosistema.pedir("hefesto", "apollo", "aprender_relacion",
                     sujeto="pingüino", relacion="es", objeto="ave")
    ecosistema.pedir("hefesto", "apollo", "aprender_relacion",
                     sujeto="ave", relacion="tiene", objeto="plumas")

    respuesta = ecosistema.pedir("hefesto", "apollo", "definir", concepto="pingüino")

    assert respuesta["estado"] == OK
    texto = redactar_definicion(respuesta["datos"])   # funciona aunque viajó por JSON
    assert "ave" in texto and "plumas" in texto


def test_apollo_rechaza_datos_incompletos(ecosistema):
    respuesta = ecosistema.pedir("hefesto", "apollo", "responder", sujeto="ave")
    assert respuesta["estado"] == RECHAZADO
    assert "relacion" in respuesta["detalle"]


def test_apollo_existe(ecosistema):
    assert ecosistema.pedir("hefesto", "apollo", "existe", concepto="dragón")["datos"] == {"existe": False}