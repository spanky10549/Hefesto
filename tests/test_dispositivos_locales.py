"""
Pruebas del dispositivo local: detección de sensores reales, estados
(activo, desactivado, pendiente), autorización y avisos.

Se usan sensores de mentira que se pueden "conectar" y "desconectar"
a voluntad, para simular que instalaste algo o se cayó el WiFi.
"""

import pytest

from gaia import Gaia, OK, RECHAZADO
from dispositivos.local import DispositivoLocal, ACTIVO, DESACTIVADO, PENDIENTE
from dispositivos.sensores_locales import (
    Sensor, senal_de_netsh, senal_de_proc, decibeles, TemperaturaCPU, Wifi, Ruido,
)
from eter import Eter


class Falso(Sensor):
    def __init__(self, id, tipo="temperatura", disponible=True, valor=20, sensible=False, propios=None):
        self.id = id
        self.tipo = tipo
        self.descripcion = f"sensor {id}"
        self.disponible = disponible
        self.valor = valor
        self.sensible = sensible
        self.propios = propios
        self.truena = False

    def detectar(self):
        return (True, "") if self.disponible else (False, f"{self.id} no está conectado")

    def leer(self):
        if self.truena:
            raise OSError("se desconectó")
        return self.valor


@pytest.fixture
def ruta(tmp_path):
    return str(tmp_path / "estados.json")


def estados(dispositivo):
    return {s["sensor"]: s["estado"] for s in dispositivo.listar({})["sensores"]}


# ==========================================
# LECTORES (funciones puras)
# ==========================================

NETSH_ES = """
Hay 1 interfaz en el sistema:

    Nombre                 : Wi-Fi
    Estado                 : conectado
    SSID                   : MiCasa
    Señal                  : 87%
    Perfil                 : MiCasa
"""

NETSH_EN = """
    Name                   : Wi-Fi
    State                  : connected
    Signal                 : 64%
"""

NETSH_DESCONECTADO = """
    Nombre                 : Wi-Fi
    Estado                 : desconectado
"""

PROC = """Inter-| sta-|   Quality        |   Discarded packets
 face | tus | link level noise |  nwid  crypt   frag  retry   misc
 wlan0: 0000   54.  -56.  -256        0      0      0      0     0
"""


def test_netsh_espanol():
    assert senal_de_netsh(NETSH_ES) == 87


def test_netsh_ingles():
    assert senal_de_netsh(NETSH_EN) == 64


def test_netsh_con_la_ene_rara():
    """Si la consola cambia la 'ñ' por otro símbolo, igual la encuentra."""
    assert senal_de_netsh(NETSH_ES.replace("ñ", "�")) == 87
    assert senal_de_netsh(NETSH_ES.replace("ñ", "Ã±")) == 87


def test_netsh_desconectado():
    assert senal_de_netsh(NETSH_DESCONECTADO) is None


def test_proc_wireless():
    assert senal_de_proc(PROC) == 77          # 54 de 70


def test_proc_sin_wifi():
    assert senal_de_proc(PROC.splitlines()[0] + "\n" + PROC.splitlines()[1]) is None


def test_decibeles():
    assert decibeles([1.0, -1.0]) == 0.0         # lo máximo
    assert decibeles([0.01, -0.01]) == -40.0
    assert decibeles([0.0, 0.0]) == -200.0       # silencio total
    assert decibeles([]) == -100.0


def test_el_microfono_siempre_pide_permiso():
    assert Ruido.sensible is True
    assert Wifi.sensible is False


def test_temperatura_del_procesador_trae_sus_propios_rangos():
    assert TemperaturaCPU.propios["rangos"][0] == [50, "fresco"]


def test_sensores_reales_no_truenan_al_detectar():
    """En cualquier compu: detectan algo o explican por qué no."""
    for sensor in (Wifi(), TemperaturaCPU(), Ruido()):
        disponible, motivo = sensor.detectar()
        assert disponible or motivo


# ==========================================
# PRIMERA VEZ
# ==========================================

def test_primera_vez(ruta):
    d = DispositivoLocal([
        Falso("wifi"),
        Falso("temp", disponible=False),
        Falso("micro", sensible=True),
    ], ruta)

    assert estados(d) == {"wifi": ACTIVO, "temp": DESACTIVADO, "micro": PENDIENTE}


def test_desactivado_dice_por_que(ruta):
    d = DispositivoLocal([Falso("temp", disponible=False)], ruta)
    (ficha,) = d.listar({})["sensores"]
    assert ficha["motivo"] == "temp no está conectado"


# ==========================================
# LO QUE APARECE DESPUÉS
# ==========================================

def test_aparece_despues_queda_pendiente_y_avisa(ruta):
    temp = Falso("temp", disponible=False)
    g = Gaia()
    d = DispositivoLocal([temp], ruta)
    g.registrar(d)
    avisos = []
    g.suscribir("sensor_detectado", avisos.append)

    temp.disponible = True          # "instalaste" algo
    r = g.pedir("hefesto", "dispositivo_local", "detectar")["datos"]

    assert r["cambios"] == [{"sensor": "temp", "antes": DESACTIVADO, "ahora": PENDIENTE}]
    assert len(avisos) == 1
    assert avisos[0]["datos"]["sensor"] == "temp"


def test_pendiente_no_se_lee(ruta):
    temp = Falso("temp", disponible=False)
    d = DispositivoLocal([temp], ruta)
    temp.disponible = True
    assert d.leer({})["lecturas"] == []


def test_autorizar(ruta):
    temp = Falso("temp", disponible=False, valor=33)
    d = DispositivoLocal([temp], ruta)
    temp.disponible = True
    d.detectar({})

    d.autorizar({"sensor": "temp"})

    assert estados(d) == {"temp": ACTIVO}
    assert d.leer({})["lecturas"][0]["valor"] == 33


def test_no_se_autoriza_lo_que_no_existe(ruta):
    g = Gaia()
    g.registrar(DispositivoLocal([Falso("temp", disponible=False)], ruta))
    r = g.pedir("hefesto", "dispositivo_local", "autorizar", sensor="temp")
    assert r["estado"] == RECHAZADO
    assert "no está conectado" in r["detalle"]


def test_sensor_desconocido(ruta):
    g = Gaia()
    g.registrar(DispositivoLocal([Falso("temp")], ruta))
    assert g.pedir("hefesto", "dispositivo_local", "autorizar", sensor="radar")["estado"] == RECHAZADO


def test_desactivar_a_mano(ruta):
    d = DispositivoLocal([Falso("wifi")], ruta)
    d.desactivar({"sensor": "wifi"})
    assert estados(d) == {"wifi": PENDIENTE}
    assert d.leer({})["lecturas"] == []


# ==========================================
# LO QUE SE PIERDE
# ==========================================

def test_se_pierde_y_avisa(ruta):
    wifi = Falso("wifi")
    g = Gaia()
    g.registrar(DispositivoLocal([wifi], ruta))
    perdidos = []
    g.suscribir("sensor_perdido", perdidos.append)

    wifi.disponible = False
    g.pedir("hefesto", "dispositivo_local", "detectar")

    assert len(perdidos) == 1
    assert perdidos[0]["datos"]["estado"] == DESACTIVADO


def test_si_ya_estaba_autorizado_regresa_solo(ruta):
    wifi = Falso("wifi")
    d = DispositivoLocal([wifi], ruta)

    wifi.disponible = False
    d.detectar({})
    wifi.disponible = True
    d.detectar({})

    assert estados(d) == {"wifi": ACTIVO}


def test_si_falla_al_leer_se_desactiva(ruta):
    wifi = Falso("wifi")
    d = DispositivoLocal([wifi], ruta)
    wifi.truena = True

    assert d.leer({})["lecturas"] == []
    assert estados(d) == {"wifi": DESACTIVADO}


def test_detectar_que_truena_no_tumba_nada(ruta):
    roto = Falso("roto")
    roto.detectar = lambda: 1 / 0
    d = DispositivoLocal([roto], ruta)
    assert estados(d) == {"roto": DESACTIVADO}


# ==========================================
# RECORDAR ENTRE SESIONES
# ==========================================

def test_recuerda_las_autorizaciones(ruta):
    micro = Falso("micro", sensible=True)
    DispositivoLocal([micro], ruta).autorizar({"sensor": "micro"})

    otra_sesion = DispositivoLocal([micro], ruta)
    assert estados(otra_sesion) == {"micro": ACTIVO}


def test_en_otra_sesion_lo_nuevo_queda_pendiente(ruta):
    """Si el archivo ya existe, un sensor nuevo ya no se autoriza solo."""
    DispositivoLocal([Falso("wifi")], ruta)
    otra_sesion = DispositivoLocal([Falso("wifi"), Falso("temp")], ruta)
    assert estados(otra_sesion) == {"wifi": ACTIVO, "temp": PENDIENTE}


# ==========================================
# CON ÉTER
# ==========================================

def test_eter_lee_el_dispositivo_local(ruta):
    procesador = {"rangos": [[50, "fresco"], [70, "normal"], [None, "caliente"]], "limites": [None, 85]}
    g = Gaia()
    g.registrar(Eter())
    g.registrar(DispositivoLocal([
        Falso("temp_cpu", valor=62, propios=procesador),
        Falso("wifi", tipo="señal_wifi", valor=25),
    ], ruta))

    g.pedir("hefesto", "eter", "actualizar")
    sensores = {s["sensor"]: s for s in g.pedir("hefesto", "eter", "entorno")["datos"]["sensores"]}

    assert sensores["temp_cpu"]["etiqueta"] == "normal"       # con los rangos del procesador
    assert sensores["wifi"]["etiqueta"] == "débil"
    assert sensores["wifi"]["unidad"] == "%"


def test_ruido_se_interpreta():
    from eter.interpretacion import etiqueta
    assert etiqueta("ruido", -60) == "silencio"
    assert etiqueta("ruido", -20) == "plática"
    assert etiqueta("ruido", -3) == "mucho ruido"


def test_las_pruebas_no_tocan_los_estados_reales(tmp_path):
    import dispositivos.local
    assert dispositivos.local.ARCHIVO_ESTADOS.startswith(str(tmp_path.parent))