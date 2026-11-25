"""
Pruebas de FOCUS hablando con HEFESTO:
    traductor.py   frases a tu manera → comandos exactos
    puente.py      pasarle el comando a HEFESTO y escuchar lo que imprime
    platica.py     cuándo se usa HEFESTO, y que lo delicado pregunte antes
"""

import random

import pytest

from conversacion.traductor import traducir, es_delicado
from conversacion.intenciones import entender
from conversacion.puente import PuenteHefesto, _limpiar
from conversacion.personalidad import Voz
from conversacion.creador import Creador
from conversacion.platica import Platica


# ==========================================
# TRADUCTOR
# ==========================================

@pytest.mark.parametrize("texto, comando", [
    # rover
    ("¿dónde está el rover?", "rover estado"),
    ("¿cómo va el rover?", "rover estado"),
    ("conecta el rover", "conecta el rover"),
    ("manda el rover a 3, 4", "rover ve a 3 4"),
    ("lleva el rover a (5,2)", "rover ve a 5 2"),
    ("rover, ve a 3 y 4", "rover ve a 3 4"),
    ("recarga el rover", "rover recarga"),
    # sensores y entorno
    ("¿qué sensores tengo?", "sensores"),
    ("activa el micrófono", "autoriza ruido"),
    ("apaga el wifi", "desactiva wifi"),
    ("activa el sensor de temperatura", "autoriza temp_cpu"),
    ("¿cómo está el entorno?", "entorno"),
    ("muéstrame el mapa", "mapa"),
    # sistema
    ("¿quién está conectado?", "ecosistema"),
    ("¿qué pasó hoy?", "qué pasó hoy"),
    ("¿hubo errores hoy?", "errores"),
    ("¿hay problemas?", "incidentes"),
    ("¿cómo está la compu?", "recursos"),
    ("¿cuánta ram queda?", "recursos"),
    ("¿hubo algo sospechoso?", "seguridad"),
    ("recupera a tabris", "recupera tabris"),
    # documentos y recuerdos
    ("lee el archivo Notas.txt", "lee Notas.txt"),      # respeta mayúsculas
    ("léete ejemplo.txt", "lee ejemplo.txt"),
    ("¿qué recuerdas?", "recuerdos"),
    ("¿de qué hablábamos?", "de qué hablamos"),
    ("hablemos de otra cosa", "cambiemos de tema"),
    # laboratorio
    ("¿qué proyectos tengo?", "proyectos"),
    ("carga el proyecto focus", "carga el proyecto focus"),
    ("abre el proyecto FOCUS", "proyecto FOCUS"),
    ("crea un proyecto llamado Dron", "nuevo proyecto Dron"),
    ("marca la 8 como terminada", "marca 8 como existe"),
    ("marca la 3 como en proceso", "marca 3 como a medias"),
    ("la 13 ya está lista", "marca 13 como existe"),
    ("dame ideas para la 8", "estrategias 8"),
    ("¿qué sigue?", "qué sigue"),
    ("¿qué me recomiendas?", "qué sigue"),
    # respaldos y bitácora
    ("haz un respaldo", "respalda"),
    ("¿qué respaldos tengo?", "respaldos"),
    ("vuelve al respaldo 2", "restaura 2"),
    ("muéstrame la bitácora", "bitácora"),
    ("anota en la bitácora que probé el sensor", "anota probé el sensor"),
    # privacidad y web
    ("¿qué carpetas proteges?", "zonas protegidas"),
    ("deja de proteger fotos", "desprotege fotos"),
    ("confía en github.com", "confía en github.com"),
    # olvidar
    ("olvida todo sobre el pingüino", "olvida todo sobre el pingüino"),
    ("ya no es cierto que el pingüino puede volar", "olvida que el pingüino puede volar"),
    # tareas
    ("¿cómo harías para revisar los recursos?", "planea revisar los recursos"),
])
def test_traduce(texto, comando):
    from conversacion.intenciones import limpiar
    assert traducir(limpiar(texto))["comando"] == comando


@pytest.mark.parametrize("texto", [
    "activa la alarma",          # no es un sensor que exista
    "marca la 8 como bonita",    # no es un estado
    "el tensor es un objeto matemático",
    "hola",
])
def test_no_traduce(texto):
    assert traducir(texto) is None


def test_delicados():
    assert es_delicado("olvida que el pingüino es un ave")
    assert es_delicado("restaura 2")
    assert es_delicado("quita la capacidad 22")
    assert not es_delicado("respalda")
    assert not es_delicado("rover estado")


def test_las_intenciones_de_siempre_ganan():
    """El traductor no se come lo que la plática ya sabía hacer."""
    assert entender("hola")["intencion"] == "saludo"
    assert entender("¿qué es un perro?")["intencion"] == "definir"
    assert entender("crea una rutina llamada x, que revise los recursos")["intencion"] == "crear_rutina"
    assert entender("borra la rutina x")["intencion"] == "borrar_rutina"
    assert entender("olvida que me gusta el café")["intencion"] == "ya_no_me_gusta"


def test_intencion_hefesto():
    i = entender("oye, ¿dónde anda el rover?")
    assert i == {"intencion": "hefesto", "comando": "rover estado", "delicado": False}


# ==========================================
# PUENTE
# ==========================================

def test_limpiar_quita_el_nombre_y_lineas_vacias():
    assert _limpiar("HEFESTO: Hola\n\n  sigue\nELEUTHIA: listo\n") == ["Hola", "  sigue", "ELEUTHIA: listo"]


def hefesto_falso():
    """Lo mismo que HEFESTO.preparar_hefesto, pero de juguete."""
    arranques = []

    def preparar():
        arranques.append(1)
        print("HEFESTO ONLINE")              # al arrancar: no debe llegar a la plática

        def procesar(comando):
            if comando == "salir":
                print("HEFESTO: Apagando sistema...")
                return "salir"
            if comando == "rover estado":
                print("HEFESTO: El rover está en (0, 0).")
                return None
            print("HEFESTO: Todavía no sé procesar ese comando.")
            return "no_entendi"
        return procesar

    return preparar, arranques


def test_puente_captura_lo_que_imprime(capsys):
    preparar, arranques = hefesto_falso()
    puente = PuenteHefesto(preparar=preparar)

    r = puente.pasar("rover estado")
    assert r == {"entendio": True, "salir": False, "lineas": ["El rover está en (0, 0)."]}
    assert capsys.readouterr().out == ""      # nada se imprimió en pantalla


def test_puente_arranca_una_sola_vez_y_hasta_que_se_usa():
    preparar, arranques = hefesto_falso()
    puente = PuenteHefesto(preparar=preparar)
    assert arranques == []
    puente.pasar("rover estado")
    puente.pasar("rover estado")
    assert arranques == [1]


def test_puente_pregunta_a_la_mitad(monkeypatch, capsys):
    """
    Un comando que pregunta algo (como 'restaura'): lo que dijo antes y
    la pregunta salen en pantalla, la respuesta se lee del teclado, y
    lo que dice después regresa a la plática.
    """
    import io

    def preparar():
        def procesar(comando):
            print("HEFESTO: Voy a restaurar el respaldo 2.")
            respuesta = input("  ¿Seguro? (sí / no): ")
            print(f"HEFESTO: Dijiste {respuesta}.")
        return procesar

    monkeypatch.setattr("sys.stdin", io.StringIO("sí\n"))
    r = PuenteHefesto(preparar=preparar).pasar("restaura 2")

    pantalla = capsys.readouterr().out
    assert "Voy a restaurar el respaldo 2." in pantalla
    assert "¿Seguro? (sí / no): " in pantalla
    assert r["lineas"] == ["Dijiste sí."]


def test_puente_deja_input_como_estaba():
    import builtins
    original = builtins.input
    preparar, _ = hefesto_falso()
    PuenteHefesto(preparar=preparar).pasar("rover estado")
    assert builtins.input is original


def test_puente_no_entendio_y_salir():
    preparar, _ = hefesto_falso()
    puente = PuenteHefesto(preparar=preparar)
    assert puente.pasar("asdf")["entendio"] is False
    assert puente.pasar("salir")["salir"] is True


# ==========================================
# EN LA PLÁTICA
# ==========================================

class HefestoQueSabe:
    """Entiende unos cuantos comandos y anota todo lo que le pasan."""

    RESPUESTAS = {
        "rover estado": ["El rover está en (0, 0)."],
        "xor": ["[0,1] → 1"],
        "olvida que el pingüino es un ave": ["Olvidé que pingüino es ave."],
        "restaura 2": ["Listo: lo restauro al volver a arrancar."],
        "salir": [],
    }

    def __init__(self):
        self.recibidos = []

    def pasar(self, comando):
        self.recibidos.append(comando)
        if comando not in self.RESPUESTAS:
            return {"entendio": False, "salir": False, "lineas": ["Todavía no sé procesar ese comando."]}
        return {"entendio": True, "salir": comando == "salir", "lineas": self.RESPUESTAS[comando]}


@pytest.fixture
def platica(tmp_path, monkeypatch):
    import apollo.conocimiento as conocimiento
    monkeypatch.setattr(conocimiento, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json"))
    from gaia import crear_ecosistema
    return Platica(crear_ecosistema(), voz=Voz(random.Random(0)),
                   creador=Creador(str(tmp_path / "c.json")), puente=HefestoQueSabe())


def di(platica, texto):
    return "\n".join(platica.responder(texto))


def test_frase_natural_llega_como_comando(platica):
    assert di(platica, "¿dónde anda el rover?") == "El rover está en (0, 0)."
    assert platica.hefesto.recibidos == ["rover estado"]


def test_comando_exacto_de_hefesto(platica):
    """Lo que la plática no entiende, se lo pregunta a HEFESTO tal cual."""
    assert di(platica, "xor") == "[0,1] → 1"


def test_si_hefesto_tampoco_entiende(platica):
    from conversacion.personalidad import FRASES
    assert di(platica, "asdfgh") in FRASES["no_entendi"]
    assert platica.hefesto.recibidos == ["asdfgh"]


def test_la_platica_contesta_primero(platica):
    """Lo que la plática ya sabe hacer no molesta a HEFESTO."""
    di(platica, "hola")
    di(platica, "cuánto es 2 + 2")
    assert platica.hefesto.recibidos == []


def test_lo_delicado_pregunta_antes(platica):
    respuesta = di(platica, "olvida que el pingüino es un ave")
    assert "olvida que el pingüino es un ave" in respuesta
    assert platica.hefesto.recibidos == []          # todavía no
    assert di(platica, "sí") == "Olvidé que pingüino es ave."
    assert platica.hefesto.recibidos == ["olvida que el pingüino es un ave"]


def test_lo_delicado_se_puede_cancelar(platica):
    di(platica, "deja de proteger fotos")
    di(platica, "no")
    assert platica.hefesto.recibidos == []


def test_si_hefesto_ya_pregunta_focus_no_pregunta_otra_vez(platica):
    """'restaura' ya pregunta "¿Volver a…?" en HEFESTO: FOCUS se lo pasa directo."""
    assert di(platica, "vuelve al respaldo 2") == "Listo: lo restauro al volver a arrancar."
    assert platica.hefesto.recibidos == ["restaura 2"]


def test_lo_delicado_solo_el_creador(platica):
    di(platica, "soy spanky")
    di(platica, "clave-de-prueba-123")
    di(platica, "clave-de-prueba-123")
    di(platica, "cierra sesión")

    assert "solo lo puede hacer mi creador" in di(platica, "vuelve al respaldo 2")
    assert platica.hefesto.recibidos == []


def test_si_hefesto_se_apaga_termina_la_platica(platica):
    # "salir" dicho normal lo atiende la plática (despedida); esto es si HEFESTO es el que se apaga
    platica._mandar("salir")
    assert platica.terminada is True