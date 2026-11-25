"""
Puente: FOCUS le pasa a HEFESTO lo que la plática sola no sabe hacer.

HEFESTO.py tiene un montón de comandos (rover, sensores, laboratorio,
respaldos, leer documentos, olvidar...). En vez de copiarlos todos a la
plática, FOCUS le pasa el comando a HEFESTO y "escucha" lo que imprime.

    puente = PuenteHefesto(gaia)
    puente.pasar("rover estado")
        → {"entendio": True, "salir": False, "lineas": ["El rover está en (0, 0)...", ...]}

Detalles:
    - HEFESTO arranca hasta la primera vez que se necesita (carga su red
      neuronal, y eso tarda un poquito).
    - Usa la MISMA GAIA que FOCUS: si no, habría dos ecosistemas con dos
      cuarentenas y dos registros distintos.
    - Lo que imprime se captura con redirect_stdout: los print() de
      HEFESTO van a parar a un texto en vez de a la pantalla.
    - Algunos comandos te preguntan algo a la mitad (restaura: "¿seguro?",
      lee: "¿qué guardo?"). Para esos, input() se cambia por preguntar():
      primero muestra lo que HEFESTO lleva dicho y luego sí pregunta.
      Sin esto, la pregunta se quedaba escondida y la pantalla esperando.
"""

import builtins
import io
import sys
from contextlib import redirect_stdout


PREFIJO = "HEFESTO:"


def _mostrar_en_pantalla(lineas):
    """Igual que decir() de focus.py: el nombre en la primera línea."""
    for i, linea in enumerate(lineas):
        print(f"{PREFIJO} {linea}" if i == 0 else f"{' ' * (len(PREFIJO) + 1)}{linea}")


def _limpiar(salida):
    """El texto que imprimió HEFESTO → líneas, sin el 'HEFESTO:' (FOCUS ya pone su nombre)."""
    lineas = []
    for linea in salida.splitlines():
        if not linea.strip():
            continue
        if linea.startswith(PREFIJO):
            linea = linea[len(PREFIJO):].strip()
        lineas.append(linea.rstrip())
    return lineas


class PuenteHefesto:

    def __init__(self, gaia=None, preparar=None, mostrar=None):
        """
        'preparar' se puede cambiar en las pruebas. Por defecto es
        HEFESTO.preparar_hefesto, que devuelve la función procesar().
        'mostrar' enseña líneas en pantalla antes de una pregunta.
        """
        self.gaia = gaia
        self._preparar = preparar
        self._mostrar = mostrar or _mostrar_en_pantalla
        self._procesar = None

    def _arrancar(self):
        if self._preparar is None:
            import HEFESTO                       # hasta aquí: no se carga si no se usa
            if self.gaia is not None:
                HEFESTO.usar_ecosistema(self.gaia)
            self._preparar = HEFESTO.preparar_hefesto
            self._salir, self._no_entendi = HEFESTO.SALIR, HEFESTO.NO_ENTENDI
        else:
            self._salir, self._no_entendi = "salir", "no_entendi"

        # Lo que imprime al arrancar (prueba XOR, "HEFESTO ONLINE"...) no le importa a la plática.
        with redirect_stdout(io.StringIO()):
            self._procesar = self._preparar()

    def pasar(self, comando):
        if self._procesar is None:
            self._arrancar()

        salida = io.StringIO()
        pantalla = sys.stdout             # la de verdad, antes de redirigir

        def preguntar(texto=""):
            # Lo que HEFESTO dijo antes de la pregunta, para que tenga sentido
            with redirect_stdout(pantalla):
                self._mostrar(_limpiar(salida.getvalue()))
            salida.seek(0)
            salida.truncate()

            pantalla.write(texto)
            pantalla.flush()
            linea = sys.stdin.readline()
            if not linea:                 # se cerró la entrada (Ctrl+Z / Ctrl+D)
                raise EOFError
            return linea.rstrip("\r\n")

        input_original = builtins.input
        builtins.input = preguntar
        try:
            with redirect_stdout(salida):
                resultado = self._procesar(comando)
        finally:
            builtins.input = input_original    # pase lo que pase, se deja como estaba

        return {
            "entendio": resultado != self._no_entendi,
            "salir": resultado == self._salir,
            "lineas": _limpiar(salida.getvalue()),
        }