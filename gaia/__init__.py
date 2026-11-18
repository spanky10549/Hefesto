"""
GAIA: la inteligencia que coordina a las demás de FOCUS.

    from gaia import crear_ecosistema
    gaia = crear_ecosistema()
    gaia.pedir("hefesto", "calculadora", "calcular", operacion="2 + 3")
"""

from gaia.nucleo import Gaia
from gaia.inteligencia import Inteligencia
from gaia.mensajes import OK, RECHAZADO, ERROR, DESCONOCIDO, Rechazo


def crear_ecosistema():
    """GAIA con todas las inteligencias que existen hoy ya conectadas."""
    # Se importan aquí para que GAIA no dependa de ellas al cargarse.
    from apollo.servicio import Apollo
    from calculo.servicio import Calculadora
    from tabris import Tabris
    from hades import Hades
    from artemis import Artemis
    from minerva import Minerva
    from poseidon import Poseidon
    from demeter import Demeter
    from eleuthia import Eleuthia
    from cuerno_arado import CuernoArado
    from eter import Eter
    from dispositivos.local import DispositivoLocal

    gaia = Gaia()

    # TABRIS va primero para que vea llegar a todas las demás,
    # y HADES después para atender cualquier fallo desde el inicio.
    gaia.registrar(Tabris())
    gaia.registrar(Hades())
    gaia.registrar(Poseidon())
    gaia.registrar(CuernoArado())
    gaia.registrar(Demeter())
    gaia.registrar(Eleuthia())
    gaia.registrar(Apollo())
    gaia.registrar(Calculadora())
    gaia.registrar(Artemis())
    gaia.registrar(Minerva())
    gaia.registrar(Eter())

    # Los sensores reales de esta computadora (o de la Raspberry Pi)
    gaia.registrar(DispositivoLocal())
    return gaia