"""
Base de datos SQLite para el diccionario de HEFESTO.

SQLite guarda todo en un solo archivo (.db) y viene incluido en Python,
así que no hay que instalar nada.

El diccionario se guarda en cuatro tablas:

    conceptos      id | palabra | normalizado | orden
    asociaciones   concepto_id | texto | orden
    sinonimos      concepto_id | texto | orden
    relaciones     concepto_id | relacion | objetivo | negada | orden

"orden" conserva el orden en que se aprendieron las cosas.

Por ahora este módulo carga y guarda el diccionario completo, con la
misma forma que tenía el JSON, para que el resto de HEFESTO no note
el cambio. Más adelante APOLLO podrá hacerle consultas directas.
"""

import sqlite3

from memoria.almacenamiento import ErrorAlmacenamiento


ESQUEMA = """
CREATE TABLE IF NOT EXISTS conceptos (
    id          INTEGER PRIMARY KEY,
    palabra     TEXT NOT NULL,
    normalizado TEXT NOT NULL,
    orden       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS asociaciones (
    concepto_id INTEGER NOT NULL REFERENCES conceptos(id) ON DELETE CASCADE,
    texto       TEXT NOT NULL,
    orden       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sinonimos (
    concepto_id INTEGER NOT NULL REFERENCES conceptos(id) ON DELETE CASCADE,
    texto       TEXT NOT NULL,
    orden       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS relaciones (
    concepto_id INTEGER NOT NULL REFERENCES conceptos(id) ON DELETE CASCADE,
    relacion    TEXT NOT NULL,
    objetivo    TEXT NOT NULL,
    negada      INTEGER NOT NULL DEFAULT 0,
    orden       INTEGER NOT NULL
);

-- Índices: como el índice de un libro, para encontrar rápido sin leer todo.
CREATE INDEX IF NOT EXISTS idx_conceptos_normalizado ON conceptos(normalizado);
CREATE INDEX IF NOT EXISTS idx_relaciones_concepto ON relaciones(concepto_id);
CREATE INDEX IF NOT EXISTS idx_relaciones_objetivo ON relaciones(objetivo);
"""


def conectar(ruta):
    """Abre la base de datos y se asegura de que existan las tablas."""
    try:
        conexion = sqlite3.connect(ruta)
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(ESQUEMA)
        return conexion
    except sqlite3.Error as error:
        raise ErrorAlmacenamiento(
            f"No pude abrir la base de datos {ruta}: {error}"
        ) from error


def guardar_diccionario_sql(ruta, diccionario, normalizar):
    """
    Guarda el diccionario completo en la base de datos.

    'normalizar' es la función que convierte una palabra a su forma de
    comparación (se recibe desde APOLLO para no depender de él).

    Todo ocurre en una TRANSACCIÓN: o se guarda completo o no se guarda
    nada. Si algo falla a la mitad, la base queda como estaba.
    """
    conexion = conectar(ruta)

    try:
        with conexion:   # inicia la transacción; confirma al salir sin errores

            conexion.execute("DELETE FROM conceptos")   # borra en cascada lo demás

            for orden, entrada in enumerate(diccionario.get("palabras", [])):

                if not isinstance(entrada, dict) or not entrada.get("palabra"):
                    continue

                cursor = conexion.execute(
                    "INSERT INTO conceptos (palabra, normalizado, orden) VALUES (?, ?, ?)",
                    (entrada["palabra"], normalizar(entrada["palabra"]), orden)
                )
                concepto_id = cursor.lastrowid

                for i, texto in enumerate(entrada.get("asociaciones", [])):
                    if isinstance(texto, str):
                        conexion.execute(
                            "INSERT INTO asociaciones VALUES (?, ?, ?)",
                            (concepto_id, texto, i)
                        )

                for i, texto in enumerate(entrada.get("sinonimos", [])):
                    if isinstance(texto, str):
                        conexion.execute(
                            "INSERT INTO sinonimos VALUES (?, ?, ?)",
                            (concepto_id, texto, i)
                        )

                for i, relacion in enumerate(entrada.get("relaciones", [])):
                    if (
                        isinstance(relacion, dict)
                        and isinstance(relacion.get("relacion"), str)
                        and isinstance(relacion.get("objetivo"), str)
                    ):
                        conexion.execute(
                            "INSERT INTO relaciones VALUES (?, ?, ?, ?, ?)",
                            (
                                concepto_id,
                                relacion["relacion"],
                                relacion["objetivo"],
                                1 if relacion.get("negada") else 0,
                                i
                            )
                        )

    except sqlite3.Error as error:
        raise ErrorAlmacenamiento(
            f"No pude guardar en la base de datos {ruta}: {error}"
        ) from error

    finally:
        conexion.close()


def cargar_diccionario_sql(ruta):
    """
    Carga el diccionario completo desde la base de datos, con la misma
    forma que tenía el JSON: {"palabras": [{"palabra": ..., ...}, ...]}
    """
    conexion = conectar(ruta)

    try:
        conceptos = conexion.execute(
            "SELECT id, palabra FROM conceptos ORDER BY orden"
        ).fetchall()

        def lista(tabla, columnas, concepto_id):
            return conexion.execute(
                f"SELECT {columnas} FROM {tabla} WHERE concepto_id = ? ORDER BY orden",
                (concepto_id,)
            ).fetchall()

        palabras = []

        for concepto_id, palabra in conceptos:

            relaciones = []

            for relacion, objetivo, negada in lista(
                "relaciones", "relacion, objetivo, negada", concepto_id
            ):
                nueva = {"relacion": relacion, "objetivo": objetivo}
                if negada:
                    nueva["negada"] = True
                relaciones.append(nueva)

            palabras.append({
                "palabra": palabra,
                "asociaciones": [t for (t,) in lista("asociaciones", "texto", concepto_id)],
                "sinonimos": [t for (t,) in lista("sinonimos", "texto", concepto_id)],
                "relaciones": relaciones
            })

        return {"palabras": palabras}

    except sqlite3.Error as error:
        raise ErrorAlmacenamiento(
            f"No pude leer la base de datos {ruta}: {error}"
        ) from error

    finally:
        conexion.close()