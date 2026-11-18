"""
DEMETER — Rutas.

Saber si un archivo está DENTRO de una carpeta parece fácil, pero tiene trampas:

    - "C:/Users/Juan/Fotos2/a.jpg" empieza igual que "C:/Users/Juan/Fotos",
      pero NO está dentro. Comparar el texto con startswith fallaría.
    - "fotos/../Documentos/x.txt" parece estar en fotos, pero sale de ahí.
    - En Windows, "C:\\Fotos" y "c:\\fotos" son la misma carpeta.

Por eso aquí se limpia la ruta (realpath + normcase) y se compara por
carpetas completas (commonpath), no por letras.
"""

import os
from pathlib import Path


def limpiar(ruta):
    """Ruta absoluta, sin '..', sin atajos y en minúsculas si es Windows."""
    return os.path.normcase(os.path.realpath(os.path.expanduser(str(ruta))))


def esta_dentro(ruta, carpeta):
    """True si 'ruta' es 'carpeta' o algo dentro de ella."""
    ruta, carpeta = limpiar(ruta), limpiar(carpeta)
    try:
        return os.path.commonpath([ruta, carpeta]) == carpeta
    except ValueError:
        # En Windows, rutas en discos distintos (C: y D:) no tienen nada en común.
        return False


# Carpetas personales que se protegen solas la primera vez.
# En Windows en español se VEN como "Imágenes", pero por dentro se llaman
# "Pictures"; y si usas OneDrive, pueden estar dentro de OneDrive.
CARPETAS_PERSONALES = [
    ("Imágenes", ["Pictures", "Imágenes"]),
    ("Videos", ["Videos", "Vídeos"]),
    ("Documentos", ["Documents", "Documentos"]),
    ("Música", ["Music", "Música"]),
    ("Escritorio", ["Desktop", "Escritorio"]),
]


def carpetas_personales(inicio=None):
    """[(nombre, ruta)] de las carpetas personales que existen en esta compu."""
    inicio = Path(inicio or Path.home())
    bases = [inicio, inicio / "OneDrive"]
    encontradas = []

    for nombre, posibles in CARPETAS_PERSONALES:
        for base in bases:
            for carpeta in posibles:
                ruta = base / carpeta
                if ruta.is_dir() and all(r != str(ruta) for _, r in encontradas):
                    encontradas.append((nombre if base == inicio else f"{nombre} (OneDrive)", str(ruta)))

    return encontradas