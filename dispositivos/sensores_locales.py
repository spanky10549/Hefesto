"""
Sensores reales de la máquina donde corre FOCUS.

Cada sensor sabe dos cosas:
    detectar()  → (True, "") si se puede leer, o (False, "por qué no")
    leer()      → el valor de ahorita

    Sensor      En Windows                   En la Raspberry Pi / Linux
    ─────────   ──────────────────────────   ───────────────────────────
    wifi        sí (netsh)                   sí (/proc/net/wireless)
    temp_cpu    casi nunca (Windows no deja) sí (sin instalar nada)
    ruido       sí, con pip install          sí, con pip install
                sounddevice + micrófono      sounddevice + micrófono

Para agregar un sensor nuevo (por ejemplo un DHT22 en los pines de la
Raspberry Pi) se crea otra clase con detectar() y leer() y se agrega a
SENSORES. Nada más cambia.
"""

import math
import os
import platform
import re
import subprocess


ES_WINDOWS = platform.system() == "Windows"


class Sensor:
    id = ""
    tipo = ""
    descripcion = ""
    sensible = False      # True: SIEMPRE pide autorización (micrófono, cámara...)
    propios = None        # rangos o límites propios para que ÉTER lo interprete

    def detectar(self):
        raise NotImplementedError

    def leer(self):
        raise NotImplementedError


# ==========================================
# WIFI
# ==========================================

def senal_de_netsh(texto):
    """
    Saca el % de señal de lo que imprime 'netsh wlan show interfaces'.
    Funciona con Windows en español ('Señal') o en inglés ('Signal').
    Devuelve None si no está conectado.
    """
    # La "ñ" puede llegar rara según la codificación, por eso "Se.{1,2}al"
    encontrado = re.search(r"^\s*(?:Se.{1,2}al|Signal)\s*:\s*(\d+)\s*%", texto, re.MULTILINE)
    return int(encontrado.group(1)) if encontrado else None


def senal_de_proc(texto):
    """
    Saca el % de señal de /proc/net/wireless (Linux y Raspberry Pi).
    La calidad viene de 0 a 70; se convierte a porcentaje.
    """
    for linea in texto.splitlines()[2:]:       # las 2 primeras son encabezados
        partes = linea.split()
        if len(partes) >= 3 and partes[0].endswith(":"):
            calidad = float(partes[2].rstrip("."))
            return round(min(calidad / 70 * 100, 100))
    return None


class Wifi(Sensor):
    id = "wifi"
    tipo = "señal_wifi"
    descripcion = "Señal del WiFi donde está la computadora"

    def _senal(self):
        if ES_WINDOWS:
            resultado = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            # La consola de Windows usa la codificación cp850 para la "ñ"
            texto = resultado.stdout.decode("cp850", errors="replace")
            return senal_de_netsh(texto)

        if os.path.exists("/proc/net/wireless"):
            with open("/proc/net/wireless", encoding="utf-8") as archivo:
                return senal_de_proc(archivo.read())

        return None

    def detectar(self):
        try:
            senal = self._senal()
        except (OSError, subprocess.SubprocessError) as error:
            return False, f"no pude preguntar por el WiFi ({error})"

        if senal is None:
            return False, "no hay WiFi o no estás conectado a una red"
        return True, ""

    def leer(self):
        return self._senal()


# ==========================================
# TEMPERATURA DEL PROCESADOR
# ==========================================

class TemperaturaCPU(Sensor):
    id = "temp_cpu"
    tipo = "temperatura"
    descripcion = "Temperatura del procesador"
    # 31 °C en un procesador no es "calor": tiene sus propios rangos.
    propios = {
        "rangos": [[50, "fresco"], [70, "normal"], [85, "caliente"], [None, "muy caliente"]],
        "limites": [None, 85],
        "cambio_brusco": 15,
    }

    def _temperatura(self):
        try:
            import psutil
            lecturas = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        except Exception:
            lecturas = {}

        # Raspberry Pi: "cpu_thermal"; PCs con Linux: "coretemp" o "k10temp"
        for nombre in ("cpu_thermal", "coretemp", "k10temp", "acpitz"):
            if lecturas.get(nombre):
                return round(lecturas[nombre][0].current, 1)

        ruta = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as archivo:
                return round(int(archivo.read().strip()) / 1000, 1)

        return None

    def detectar(self):
        if ES_WINDOWS:
            return False, "Windows no deja leer la temperatura del procesador sin programas extra"
        try:
            temperatura = self._temperatura()
        except (OSError, ValueError) as error:
            return False, f"no pude leerla ({error})"
        if temperatura is None:
            return False, "esta computadora no reporta la temperatura del procesador"
        return True, ""

    def leer(self):
        return self._temperatura()


# ==========================================
# RUIDO (MICRÓFONO)
# ==========================================

def decibeles(muestras):
    """
    Qué tan fuerte suena, en dBFS: 0 es lo máximo que capta el micrófono
    y entre más negativo, más silencio (-60 es casi nada).
    Se calcula con la raíz cuadrática media (RMS) del sonido.
    """
    if len(muestras) == 0:
        return -100.0
    rms = math.sqrt(sum(float(m) * float(m) for m in muestras) / len(muestras))
    return round(20 * math.log10(max(rms, 1e-10)), 1)


class Ruido(Sensor):
    id = "ruido"
    tipo = "ruido"
    descripcion = "Nivel de ruido del cuarto (micrófono; solo mide el volumen, no graba)"
    sensible = True
    SEGUNDOS = 0.5
    FRECUENCIA = 16000

    def detectar(self):
        try:
            import sounddevice
        except ImportError:
            return False, "falta instalar sounddevice (pip install sounddevice)"
        except OSError:
            return False, "falta la librería de audio PortAudio"

        try:
            sounddevice.query_devices(kind="input")
        except Exception:
            return False, "no encontré ningún micrófono"

        return True, ""

    def leer(self):
        import sounddevice

        audio = sounddevice.rec(
            int(self.SEGUNDOS * self.FRECUENCIA), samplerate=self.FRECUENCIA,
            channels=1, dtype="float32",
        )
        sounddevice.wait()
        # Solo se calcula el volumen; el audio se descarta en este momento.
        return decibeles(audio[:, 0])


SENSORES = [Wifi(), TemperaturaCPU(), Ruido()]