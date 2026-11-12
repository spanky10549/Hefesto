"""
ROVER — Mundo simulado.

Un mapa de casillas, como un tablero. El rover empieza en (0, 0).

    y
    9 . . . . . . . . . .
    ...
    4 . . . . . # # # . .
    3 . . # . . . . . . .
    2 . . # . . . . . . .
    1 . . # . . . . . . .
    0 R . # . . . . . . .
      0 1 2 3 4 5 6 7 8 9  x

Los obstáculos (#) son REALES, pero el rover NO los conoce: los descubre
cuando intenta entrar a esa casilla, como si lo detectara con un sensor.

Cuando exista el rover físico, este archivo se cambia por los sensores
de verdad; el resto del rover se queda igual.
"""

from collections import deque


ANCHO = 10
ALTO = 10

OBSTACULOS = {
    (2, 0), (2, 1), (2, 2), (2, 3),     # una pared
    (5, 4), (6, 4), (7, 4),             # una barda
}


def dentro(casilla, ancho=ANCHO, alto=ALTO):
    x, y = casilla
    return 0 <= x < ancho and 0 <= y < alto


def vecinos(casilla, ancho=ANCHO, alto=ALTO):
    """Las casillas de arriba, abajo, izquierda y derecha (sin diagonales)."""
    x, y = casilla
    posibles = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return [c for c in posibles if dentro(c, ancho, alto)]


def ruta(inicio, destino, bloqueadas, ancho=ANCHO, alto=ALTO):
    """
    El camino más corto de 'inicio' a 'destino' sin pisar las bloqueadas.
    Devuelve la lista de casillas a pisar (sin la de inicio), o None si
    no hay forma de llegar.

    Es una búsqueda en anchura (BFS), la misma idea que usa APOLLO para
    subir por las categorías: explorar primero lo cercano. En un mapa
    de casillas, eso garantiza el camino más corto.
    """
    if inicio == destino:
        return []

    pendientes = deque([inicio])
    vino_de = {inicio: None}

    while pendientes:
        actual = pendientes.popleft()

        for siguiente in vecinos(actual, ancho, alto):
            if siguiente in vino_de or siguiente in bloqueadas:
                continue

            vino_de[siguiente] = actual

            if siguiente == destino:
                # Reconstruir el camino de atrás para adelante
                camino = [siguiente]
                while vino_de[camino[-1]] != inicio:
                    camino.append(vino_de[camino[-1]])
                return list(reversed(camino))

            pendientes.append(siguiente)

    return None