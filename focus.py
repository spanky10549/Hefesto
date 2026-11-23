"""
FOCUS — la puerta de entrada.

    python focus.py      → platicas con FOCUS de forma natural
    python HEFESTO.py    → el modo de comandos exactos (sigue igual)

Al arrancar:
    1. ELEUTHIA aplica una restauración pendiente (si pediste una).
    2. GAIA conecta a las inteligencias.
    3. ELEUTHIA hace el respaldo del día (si toca).
    4. Platicamos.
"""

import os
from getpass import getpass

from eleuthia.respaldos import aplicar_restauracion_pendiente, ArchivoOcupado
from gaia import crear_ecosistema, OK
from conversacion.platica import Platica
from conversacion.personalidad import NOMBRE


def decir(lineas):
    for i, linea in enumerate(lineas):
        print(f"{NOMBRE}: {linea}" if i == 0 else f"{' ' * (len(NOMBRE) + 2)}{linea}")


def iniciar():
    print("\n================================")
    print("             FOCUS")
    print("================================")

    try:
        restaurados = aplicar_restauracion_pendiente(os.getcwd())
        if restaurados:
            print(f"ELEUTHIA: Restauré el respaldo ({len(restaurados)} archivos).")
    except ArchivoOcupado as ocupados:
        print(f"ELEUTHIA: No pude terminar de restaurar ({ocupados}); lo intento la próxima vez.")

    gaia = crear_ecosistema()
    platica = Platica(gaia)

    respaldo = gaia.pedir("focus", "eleuthia", "respaldo_al_dia")
    if respaldo["estado"] == OK and respaldo["datos"]["hecho"]:
        print("ELEUTHIA: Guardé el respaldo del día.")

    print()
    decir([platica.voz.di("bienvenida"), "(Para salir: adiós)"])

    while not platica.terminada:
        try:
            if platica.espera_clave:
                # getpass: lo que escribes no se ve en pantalla (ni queda en el historial)
                texto = getpass("\nTú (clave): ")
            else:
                texto = input("\nTú: ")
        except (KeyboardInterrupt, EOFError):
            print()
            decir([platica.voz.di("despedida", nombre=platica.perfil.nombre)])
            break

        decir(platica.responder(texto) or ["…"])


if __name__ == "__main__":
    iniciar()