"""
Pruebas de las fuentes del conocimiento (#16): cada dato sabe de dónde
salió (tú, el creador, un documento, WordNet) y cuándo.
"""

import random
import sqlite3
from datetime import date

import pytest

import apollo.conocimiento as apollo
from apollo import fuentes
from apollo.fuentes import USUARIO, WORDNET, documento, creador, describir, describir_fecha
from apollo.razonamiento import responder, con_fuentes, hechos_con_fuente
from apollo.importador import importar
from apollo.lector import guardar_hechos
from conversacion.intenciones import entender


@pytest.fixture(autouse=True)
def diccionario_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(apollo, "ARCHIVO_DICCIONARIO", str(tmp_path / "diccionario_hefesto.json"))
    apollo._bases_listas.clear()


def fuente(sujeto, tipo, objeto, negada=False):
    dato = apollo.fuente_de(sujeto, tipo, objeto, negada)
    return dato["fuente"] if dato else None


# ==========================================
# SE ANOTA AL APRENDER
# ==========================================

def test_relacion_de_usuario_por_defecto():
    apollo.aprender_relacion("sensor", "mide", "temperatura")
    assert fuente("sensor", "mide", "temperatura") == USUARIO


def test_la_fecha_es_hoy():
    apollo.aprender_relacion("sensor", "mide", "temperatura")
    assert apollo.fuente_de("sensor", "mide", "temperatura")["fecha"] == date.today().isoformat()


def test_categoria_sinonimo_y_negada():
    apollo.aprender_palabra("pingüino", "un ave", fuente=creador("spanky"))
    apollo.aprender_sinonimo("pingüino", "pingu", fuente=documento("aves.txt"))
    apollo.aprender_relacion("pingüino", "puede", "volar", negada=True, fuente=WORDNET)

    assert fuente("pingüino", "es", "ave") == "creador:spanky"        # "un ave" = "ave"
    assert fuente("pingüino", "sinonimo", "pingu") == "documento:aves.txt"
    assert fuente("pingüino", "puede", "volar", negada=True) == WORDNET
    assert fuente("pingüino", "puede", "volar") is None                # la afirmativa no existe


def test_se_encuentra_por_sinonimo_y_sin_importar_plural_ni_acentos():
    apollo.aprender_palabra("raspberry pi", "computadora")
    apollo.aprender_sinonimo("raspberry pi", "rpi")
    apollo.aprender_relacion("raspberry pi", "usa", "sensores", fuente=documento("rpi.txt"))
    assert fuente("rpi", "usa", "sensor") == "documento:rpi.txt"
    assert fuente("Raspberry Pi", "usan", "Sensores") == "documento:rpi.txt"


def test_ya_sabia_no_cambia_la_fuente():
    apollo.aprender_relacion("sensor", "mide", "temperatura", fuente=documento("a.txt"))
    apollo.aprender_relacion("sensor", "mide", "temperatura", fuente=USUARIO)
    assert fuente("sensor", "mide", "temperatura") == "documento:a.txt"


def test_contradiccion_no_anota_hasta_reemplazar():
    apollo.aprender_relacion("pingüino", "puede", "volar")
    r = apollo.aprender_relacion("pingüino", "puede", "volar", negada=True, fuente=creador("spanky"))
    assert r["estado"] == "contradiccion"
    assert fuente("pingüino", "puede", "volar", negada=True) is None

    apollo.aprender_relacion("pingüino", "puede", "volar", negada=True, reemplazar=True, fuente=creador("spanky"))
    assert fuente("pingüino", "puede", "volar", negada=True) == "creador:spanky"


def test_olvidar_y_volver_a_aprender_gana_la_nueva():
    apollo.aprender_relacion("sensor", "mide", "humedad", fuente=documento("viejo.txt"))
    apollo.olvidar_relacion("sensor", "mide", "humedad")
    apollo.aprender_relacion("sensor", "mide", "humedad")
    assert fuente("sensor", "mide", "humedad") == USUARIO


def test_documentos_y_wordnet():
    guardar_hechos([{"tipo": "relacion", "sujeto": "aves", "relacion": "pueden",
                     "objeto": "volar", "negada": False}], fuente=documento("aves.txt"))
    importar([{"palabra": "gorrión", "asociaciones": ["ave"],
               "relaciones": [{"relacion": "come", "objetivo": "semillas"}]}])

    assert fuente("ave", "puede", "volar") == "documento:aves.txt"
    assert fuente("gorrión", "es", "ave") == WORDNET
    assert fuente("gorrión", "come", "semillas") == WORDNET


def test_importar_no_cambia_lo_que_ya_sabia():
    apollo.aprender_palabra("gorrión", "ave")
    importar([{"palabra": "gorrión", "asociaciones": ["ave", "animal"]}])
    assert fuente("gorrión", "es", "ave") == USUARIO
    assert fuente("gorrión", "es", "animal") == WORDNET


def test_ordenar_el_diccionario_no_pierde_fuentes():
    apollo.aprender_relacion("aves", "pueden", "volar", fuente=documento("aves.txt"))
    apollo.ordenar_diccionario()
    assert fuente("ave", "puede", "volar") == "documento:aves.txt"


# ==========================================
# RAZONAMIENTO
# ==========================================

def test_cada_paso_de_la_cadena_trae_su_fuente():
    apollo.aprender_palabra("pingüino", "ave")
    apollo.aprender_relacion("ave", "tiene", "plumas", fuente=documento("aves.txt"))

    respuesta, cadena = responder("pingüino", "tiene", "plumas")
    pasos = con_fuentes(cadena)
    assert respuesta == "sí"
    assert [p["fuente"]["fuente"] for p in pasos] == [USUARIO, "documento:aves.txt"]


def test_paso_negado():
    apollo.aprender_relacion("pingüino", "puede", "volar", negada=True, fuente=creador("spanky"))
    _, cadena = responder("pingüino", "puede", "volar")
    assert con_fuentes(cadena)[0]["fuente"]["fuente"] == "creador:spanky"


def test_hechos_con_fuente():
    apollo.aprender_palabra("pingüino", "ave")
    apollo.aprender_sinonimo("pingüino", "pingu")
    apollo.aprender_relacion("pingüino", "puede", "nadar", fuente=documento("mar.txt"))

    hechos = {(h["tipo"], h["objeto"]): h["fuente"]["fuente"] for h in hechos_con_fuente("pingu")}
    assert hechos == {("es", "ave"): USUARIO, ("sinonimo", "pingu"): USUARIO,
                      ("puede", "nadar"): "documento:mar.txt"}


# ==========================================
# LO VIEJO (antes de las fuentes)
# ==========================================

def test_base_version_2_gana_la_tabla_sin_perder_nada(tmp_path):
    """Una base de antes de las fuentes: se le agrega la tabla y lo viejo queda 'sin fuente'."""
    from memoria.base_datos import ESQUEMA
    ruta = tmp_path / "diccionario_hefesto.db"
    conexion = sqlite3.connect(ruta)
    conexion.executescript(ESQUEMA)
    conexion.execute("INSERT INTO conceptos VALUES (1, 'sensor', 'sensor', 0)")
    conexion.execute("INSERT INTO relaciones VALUES (1, 'mide', 'temperatura', 'temperatura', 0, 0)")
    conexion.execute("PRAGMA user_version = 2")
    conexion.commit()
    conexion.close()

    assert apollo.buscar_relaciones("sensor") == [{"relacion": "mide", "objetivo": "temperatura"}]
    assert apollo.fuente_de("sensor", "mide", "temperatura") is None
    assert describir(None).startswith("lo aprendí antes")

    apollo.aprender_relacion("sensor", "mide", "humedad")      # y ya se pueden anotar
    assert fuente("sensor", "mide", "humedad") == USUARIO


# ==========================================
# EN ESPAÑOL
# ==========================================

HOY = date(2026, 11, 24)


@pytest.mark.parametrize("fecha, esperado", [
    ("2026-11-24", "hoy"),
    ("2026-11-23", "ayer"),
    ("2026-11-03", "el 3 de noviembre"),
    ("2025-01-15", "el 15 de enero de 2025"),
    ("no-es-fecha", ""),
])
def test_describir_fecha(fecha, esperado):
    assert describir_fecha(fecha, HOY) == esperado


@pytest.mark.parametrize("fuente, esperado", [
    (USUARIO, "me lo dijiste tú hoy"),
    ("creador:spanky", "me lo dijo spanky, mi creador, hoy"),
    ("documento:aves.txt", "lo leí en aves.txt hoy"),
    (WORDNET, "viene de WordNet (lo importé hoy)"),
])
def test_describir(fuente, esperado):
    assert describir({"fuente": fuente, "fecha": "2026-11-24"}, HOY) == esperado


# ==========================================
# INTENCIONES
# ==========================================

@pytest.mark.parametrize("texto, frase", [
    ("¿de dónde sacaste que el pingüino no puede volar?", "el pingüino no puede volar"),
    ("¿cómo sabes que la raspberry pi necesita electricidad?", "la raspberry pi necesita electricidad"),
    ("¿quién te enseñó que el sensor mide la temperatura?", "el sensor mide la temperatura"),
    ("¿quién te dijo eso?", None),
    ("¿y cómo lo sabes?", None),
    ("¿de dónde lo sacaste?", None),
])
def test_intencion_de_donde(texto, frase):
    assert entender(texto) == {"intencion": "de_donde", "frase": frase}


@pytest.mark.parametrize("texto, concepto", [
    ("fuentes del pingüino", "pingüino"),
    ("tus fuentes sobre la raspberry pi", "raspberry pi"),
    ("¿quién te enseñó sobre los pingüinos?", "pingüinos"),
    ("¿de dónde sabes lo que sabes del sensor?", "sensor"),
])
def test_intencion_fuentes(texto, concepto):
    assert entender(texto) == {"intencion": "fuentes", "concepto": concepto}


# ==========================================
# EN LA PLÁTICA
# ==========================================

CLAVE = "clave-de-prueba-123"


@pytest.fixture
def platica(tmp_path):
    from gaia import crear_ecosistema
    from conversacion.platica import Platica
    from conversacion.personalidad import Voz
    from conversacion.creador import Creador
    return Platica(crear_ecosistema(), voz=Voz(random.Random(0)), creador=Creador(str(tmp_path / "c.json")))


def di(platica, texto):
    return "\n".join(platica.responder(texto))


def test_quien_te_dijo_eso_despues_de_ensenar(platica):
    di(platica, "el pingüino es un ave")
    assert di(platica, "¿de dónde sacaste eso?") == "Me lo dijiste tú hoy."


def test_lo_deducido_explica_cada_paso(platica):
    guardar_hechos([{"tipo": "relacion", "sujeto": "aves", "relacion": "pueden",
                     "objeto": "volar", "negada": False}], fuente=documento("aves.txt"))
    di(platica, "el pingüino es un ave")
    di(platica, "¿el pingüino puede volar?")
    respuesta = di(platica, "¿quién te dijo eso?")
    assert "lo deduje" in respuesta
    assert "el pingüino es ave (me lo dijiste tú hoy)" in respuesta
    assert "el ave puede volar (lo leí en aves.txt hoy)" in respuesta


def test_lo_que_ensena_el_creador_queda_a_su_nombre(platica):
    di(platica, "soy spanky")
    di(platica, CLAVE)
    di(platica, CLAVE)
    di(platica, "el pingüino no puede volar")
    assert di(platica, "¿cómo lo sabes?") == "Me lo dijo spanky, mi creador, hoy."


def test_sabe_lo_contrario(platica):
    di(platica, "el pingüino no puede volar")
    respuesta = di(platica, "¿de dónde sacaste que el pingüino puede volar?")
    assert respuesta.startswith("Ojo")
    assert "el pingüino no puede volar (me lo dijiste tú hoy)" in respuesta


def test_no_lo_sabe(platica):
    assert "nadie me lo ha dicho" in di(platica, "¿cómo sabes que el gato es un ave?")


def test_eso_sin_nada_antes(platica):
    assert "Todavía no" in di(platica, "¿quién te dijo eso?")


def test_fuentes_de_un_concepto(platica):
    di(platica, "el pingüino es un ave")
    apollo.aprender_relacion("pingüino", "puede", "nadar", fuente=documento("mar.txt"))
    respuesta = di(platica, "fuentes del pingüino")
    assert respuesta.startswith("Esto sé del pingüino")
    assert "es ave (me lo dijiste tú hoy)" in respuesta
    assert "puede nadar (lo leí en mar.txt hoy)" in respuesta


def test_fuentes_de_algo_desconocido(platica):
    assert di(platica, "fuentes del dragón") == "No sé nada de dragón."