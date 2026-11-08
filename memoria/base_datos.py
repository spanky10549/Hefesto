"""
Base de datos SQLite para el diccionario de HEFESTO.

SQLite guarda todo en un solo archivo (.db) y viene incluido en Python,
así que no hay que instalar nada.

El diccionario se guarda en cuatro tablas:

    conceptos      id | palabra | normalizado | orden
    asociaciones   concepto_id | texto | normalizado | orden
    sinonimos      concepto_id | texto | normalizado | orden
    relaciones     concepto_id | relacion | objetivo | objetivo_normalizado
                   | negada | orden

"orden" conserva el orden en que se aprendieron las cosas.
Las columnas "normalizado" guardan la forma de comparar ("Las Baterías"
→ "bateria"), para poder buscar directo con SQL.

Hay dos formas de usarla:
- Cargar o guardar el diccionario completo (lo que hacen aprender y olvidar).
- Consultas directas (buscar un concepto, sus relaciones...), que solo
  leen lo necesario y son rápidas aunque haya miles de conceptos.
"""

import sqlite3

from memoria.almacenamiento import ErrorAlmacenamiento


VERSION_ESQUEMA = 2

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
    normalizado TEXT NOT NULL,
    orden       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sinonimos (
    concepto_id INTEGER NOT NULL REFERENCES conceptos(id) ON DELETE CASCADE,
    texto       TEXT NOT NULL,
    normalizado TEXT NOT NULL,
    orden       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS relaciones (
    concepto_id          INTEGER NOT NULL REFERENCES conceptos(id) ON DELETE CASCADE,
    relacion             TEXT NOT NULL,
    objetivo             TEXT NOT NULL,
    objetivo_normalizado TEXT NOT NULL,
    negada               INTEGER NOT NULL DEFAULT 0,
    orden                INTEGER NOT NULL
);

-- Índices: como el índice de un libro, para encontrar rápido sin leer todo.
CREATE INDEX IF NOT EXISTS idx_conceptos_normalizado ON conceptos(normalizado);
CREATE INDEX IF NOT EXISTS idx_asociaciones_concepto ON asociaciones(concepto_id);
CREATE INDEX IF NOT EXISTS idx_asociaciones_normalizado ON asociaciones(normalizado);
CREATE INDEX IF NOT EXISTS idx_sinonimos_concepto ON sinonimos(concepto_id);
CREATE INDEX IF NOT EXISTS idx_sinonimos_normalizado ON sinonimos(normalizado);
CREATE INDEX IF NOT EXISTS idx_relaciones_concepto ON relaciones(concepto_id);
CREATE INDEX IF NOT EXISTS idx_relaciones_objetivo ON relaciones(objetivo_normalizado);
"""


def conectar(ruta):
    """Abre la base de datos."""
    try:
        conexion = sqlite3.connect(ruta)
        conexion.execute("PRAGMA foreign_keys = ON")
        return conexion
    except sqlite3.Error as error:
        raise ErrorAlmacenamiento(
            f"No pude abrir la base de datos {ruta}: {error}"
        ) from error


def preparar_base(ruta, normalizar):
    """
    Deja la base lista para usarse:
    - Si es nueva, crea las tablas.
    - Si es de una versión anterior (sin columnas normalizadas), la
      actualiza sin perder nada: la lee completa y la vuelve a guardar.

    La versión se guarda dentro del propio archivo (PRAGMA user_version).
    """
    conexion = conectar(ruta)

    try:
        version = conexion.execute("PRAGMA user_version").fetchone()[0]
        hay_tablas = conexion.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'conceptos'"
        ).fetchone() is not None

        if version >= VERSION_ESQUEMA:
            return

        diccionario = _leer_todo(conexion) if hay_tablas else {"palabras": []}

        with conexion:
            for tabla in ("relaciones", "sinonimos", "asociaciones", "conceptos"):
                conexion.execute(f"DROP TABLE IF EXISTS {tabla}")

            conexion.executescript(ESQUEMA)

        _escribir_todo(conexion, diccionario, normalizar)
        conexion.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")

    except sqlite3.Error as error:
        raise ErrorAlmacenamiento(
            f"No pude preparar la base de datos {ruta}: {error}"
        ) from error

    finally:
        conexion.close()


def _escribir_todo(conexion, diccionario, normalizar):
    """Reemplaza todo el contenido por el diccionario dado, en una transacción."""
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
                        "INSERT INTO asociaciones VALUES (?, ?, ?, ?)",
                        (concepto_id, texto, normalizar(texto), i)
                    )

            for i, texto in enumerate(entrada.get("sinonimos", [])):
                if isinstance(texto, str):
                    conexion.execute(
                        "INSERT INTO sinonimos VALUES (?, ?, ?, ?)",
                        (concepto_id, texto, normalizar(texto), i)
                    )

            for i, relacion in enumerate(entrada.get("relaciones", [])):
                if (
                    isinstance(relacion, dict)
                    and isinstance(relacion.get("relacion"), str)
                    and isinstance(relacion.get("objetivo"), str)
                ):
                    conexion.execute(
                        "INSERT INTO relaciones VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            concepto_id,
                            relacion["relacion"],
                            relacion["objetivo"],
                            normalizar(relacion["objetivo"]),
                            1 if relacion.get("negada") else 0,
                            i
                        )
                    )


def _entrada(conexion, concepto_id, palabra):
    """Arma un concepto con la forma de siempre: {"palabra", "asociaciones", ...}"""

    def lista(tabla, columnas):
        return conexion.execute(
            f"SELECT {columnas} FROM {tabla} WHERE concepto_id = ? ORDER BY orden",
            (concepto_id,)
        ).fetchall()

    relaciones = []

    for relacion, objetivo, negada in lista("relaciones", "relacion, objetivo, negada"):
        nueva = {"relacion": relacion, "objetivo": objetivo}
        if negada:
            nueva["negada"] = True
        relaciones.append(nueva)

    return {
        "palabra": palabra,
        "asociaciones": [t for (t,) in lista("asociaciones", "texto")],
        "sinonimos": [t for (t,) in lista("sinonimos", "texto")],
        "relaciones": relaciones
    }


def _leer_todo(conexion):
    conceptos = conexion.execute(
        "SELECT id, palabra FROM conceptos ORDER BY orden"
    ).fetchall()

    return {"palabras": [_entrada(conexion, cid, palabra) for cid, palabra in conceptos]}


def _con_conexion(ruta, accion, mensaje):
    """Abre, ejecuta la acción, traduce errores y siempre cierra."""
    conexion = conectar(ruta)
    try:
        return accion(conexion)
    except sqlite3.Error as error:
        raise ErrorAlmacenamiento(f"{mensaje} {ruta}: {error}") from error
    finally:
        conexion.close()


# ==========================================
# DICCIONARIO COMPLETO
# ==========================================

def guardar_diccionario_sql(ruta, diccionario, normalizar):
    """
    Guarda el diccionario completo. Todo ocurre en una TRANSACCIÓN:
    o se guarda completo o no se guarda nada.
    """
    _con_conexion(
        ruta,
        lambda c: _escribir_todo(c, diccionario, normalizar),
        "No pude guardar en la base de datos"
    )


def cargar_diccionario_sql(ruta):
    """Carga el diccionario completo: {"palabras": [{"palabra": ..., ...}, ...]}"""
    return _con_conexion(ruta, _leer_todo, "No pude leer la base de datos")


# ==========================================
# CONSULTAS DIRECTAS (rápidas)
# ==========================================
# Reciben las palabras ya normalizadas ("bateria", no "Las Baterías").

def buscar_concepto_sql(ruta, clave):
    """
    El primer concepto que se llama así o tiene ese sinónimo.
    Devuelve la entrada completa, o None.
    """
    def accion(conexion):
        fila = conexion.execute("""
            SELECT id, palabra FROM conceptos c
            WHERE c.normalizado = ?
               OR EXISTS (SELECT 1 FROM sinonimos s
                          WHERE s.concepto_id = c.id AND s.normalizado = ?)
            ORDER BY c.orden
            LIMIT 1
        """, (clave, clave)).fetchone()

        return _entrada(conexion, *fila) if fila else None

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def entradas_por_clave_sql(ruta, clave):
    """Todas las entradas de un concepto (puede haber repetidas en datos viejos)."""
    def accion(conexion):
        filas = conexion.execute(
            "SELECT id, palabra FROM conceptos WHERE normalizado = ? ORDER BY orden",
            (clave,)
        ).fetchall()
        return [_entrada(conexion, cid, palabra) for cid, palabra in filas]

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def relaciones_sql(ruta, clave, negadas=False):
    """Las relaciones de un concepto, afirmativas o negadas, en orden."""
    def accion(conexion):
        return conexion.execute("""
            SELECT r.relacion, r.objetivo
            FROM relaciones r JOIN conceptos c ON c.id = r.concepto_id
            WHERE c.normalizado = ? AND r.negada = ?
            ORDER BY c.orden, r.orden
        """, (clave, 1 if negadas else 0)).fetchall()

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def inversas_sql(ruta, claves):
    """
    Quién apunta a alguno de estos conceptos: relaciones afirmativas
    cuyo objetivo es uno de ellos, y asociaciones ("es") hacia ellos.
    Devuelve (sujeto, relacion) en orden.
    """
    claves = list(claves)
    if not claves:
        return []

    marcas = ", ".join("?" for _ in claves)

    def accion(conexion):
        return conexion.execute(f"""
            SELECT palabra, relacion FROM (
                SELECT c.palabra, r.relacion, c.orden AS o1, 0 AS o2, r.orden AS o3
                FROM relaciones r JOIN conceptos c ON c.id = r.concepto_id
                WHERE r.negada = 0 AND r.objetivo_normalizado IN ({marcas})
              UNION ALL
                SELECT c.palabra, 'es', c.orden, 1, a.orden
                FROM asociaciones a JOIN conceptos c ON c.id = a.concepto_id
                WHERE a.normalizado IN ({marcas})
            )
            ORDER BY o1, o2, o3
        """, claves + claves).fetchall()

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def nombres_sql(ruta):
    """Todos los nombres conocidos: (normalizado, original), en orden."""
    def accion(conexion):
        return conexion.execute("""
            SELECT normalizado, nombre FROM (
                SELECT c.normalizado, c.palabra AS nombre, c.orden AS o1, 0 AS o2, 0 AS o3
                FROM conceptos c
              UNION ALL
                SELECT s.normalizado, s.texto, c.orden, 1, s.orden
                FROM sinonimos s JOIN conceptos c ON c.id = s.concepto_id
              UNION ALL
                SELECT r.objetivo_normalizado, r.objetivo, c.orden, 2, r.orden
                FROM relaciones r JOIN conceptos c ON c.id = r.concepto_id
            )
            ORDER BY o1, o2, o3
        """).fetchall()

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def existe_sql(ruta, clave):
    """¿Hay algún concepto, sinónimo u objetivo con ese nombre?"""
    def accion(conexion):
        return conexion.execute("""
            SELECT EXISTS (SELECT 1 FROM conceptos WHERE normalizado = ?)
                OR EXISTS (SELECT 1 FROM sinonimos WHERE normalizado = ?)
                OR EXISTS (SELECT 1 FROM relaciones WHERE objetivo_normalizado = ?)
        """, (clave, clave, clave)).fetchone()[0] == 1

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


# ==========================================
# CAMBIOS PEQUEÑOS (rápidos)
# ==========================================
# En lugar de reescribir todo el diccionario, estas funciones solo
# insertan o borran las filas que cambian. Cada una es una transacción.

TABLAS_HIJAS = ("asociaciones", "sinonimos", "relaciones")


def buscar_id_sql(ruta, clave):
    """(id, palabra) del primer concepto con ese nombre o sinónimo, o None."""
    def accion(conexion):
        return conexion.execute("""
            SELECT id, palabra FROM conceptos c
            WHERE c.normalizado = ?
               OR EXISTS (SELECT 1 FROM sinonimos s
                          WHERE s.concepto_id = c.id AND s.normalizado = ?)
            ORDER BY c.orden
            LIMIT 1
        """, (clave, clave)).fetchone()

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def ids_por_clave_sql(ruta, clave):
    """[(id, palabra), ...] de los conceptos que se llaman exactamente así."""
    def accion(conexion):
        return conexion.execute(
            "SELECT id, palabra FROM conceptos WHERE normalizado = ? ORDER BY orden",
            (clave,)
        ).fetchall()

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def filas_sql(ruta, tabla, ids):
    """
    Las filas de una tabla hija para esos conceptos, con su rowid
    (el número interno de fila que SQLite le da a cada una):

        asociaciones / sinonimos → (rowid, texto, normalizado)
        relaciones               → (rowid, relacion, objetivo,
                                    objetivo_normalizado, negada)
    """
    assert tabla in TABLAS_HIJAS
    ids = list(ids)
    if not ids:
        return []

    # "t." indica la tabla: "conceptos" también tiene "normalizado".
    columnas = (
        "t.relacion, t.objetivo, t.objetivo_normalizado, t.negada"
        if tabla == "relaciones" else "t.texto, t.normalizado"
    )
    marcas = ", ".join("?" for _ in ids)

    def accion(conexion):
        return conexion.execute(f"""
            SELECT t.rowid, {columnas}
            FROM {tabla} t JOIN conceptos c ON c.id = t.concepto_id
            WHERE t.concepto_id IN ({marcas})
            ORDER BY c.orden, t.orden
        """, ids).fetchall()

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")


def _siguiente_orden(conexion, tabla, concepto_id=None):
    if concepto_id is None:
        fila = conexion.execute(f"SELECT MAX(orden) FROM {tabla}").fetchone()
    else:
        fila = conexion.execute(
            f"SELECT MAX(orden) FROM {tabla} WHERE concepto_id = ?", (concepto_id,)
        ).fetchone()
    return 0 if fila[0] is None else fila[0] + 1


def crear_concepto_sql(ruta, palabra, normalizar):
    """Crea un concepto vacío al final y devuelve su id."""
    def accion(conexion):
        with conexion:
            cursor = conexion.execute(
                "INSERT INTO conceptos (palabra, normalizado, orden) VALUES (?, ?, ?)",
                (palabra, normalizar(palabra), _siguiente_orden(conexion, "conceptos"))
            )
            return cursor.lastrowid

    return _con_conexion(ruta, accion, "No pude guardar en la base de datos")


def agregar_texto_sql(ruta, tabla, concepto_id, texto, normalizar):
    """Agrega una asociación o un sinónimo al final de un concepto."""
    assert tabla in ("asociaciones", "sinonimos")

    def accion(conexion):
        with conexion:
            conexion.execute(
                f"INSERT INTO {tabla} VALUES (?, ?, ?, ?)",
                (concepto_id, texto, normalizar(texto),
                 _siguiente_orden(conexion, tabla, concepto_id))
            )

    _con_conexion(ruta, accion, "No pude guardar en la base de datos")


def agregar_relacion_sql(ruta, concepto_id, relacion, objetivo, negada,
                         normalizar, borrar_rowids=()):
    """
    Agrega una relación al final de un concepto. Si se pasan
    borrar_rowids, primero borra esas relaciones: todo en UNA
    transacción, para que un reemplazo nunca quede a medias.
    """
    def accion(conexion):
        with conexion:
            for rowid in borrar_rowids:
                conexion.execute("DELETE FROM relaciones WHERE rowid = ?", (rowid,))

            conexion.execute(
                "INSERT INTO relaciones VALUES (?, ?, ?, ?, ?, ?)",
                (concepto_id, relacion, objetivo, normalizar(objetivo),
                 1 if negada else 0,
                 _siguiente_orden(conexion, "relaciones", concepto_id))
            )

    _con_conexion(ruta, accion, "No pude guardar en la base de datos")


def borrar_filas_sql(ruta, tabla, rowids):
    """Borra filas concretas de una tabla hija. Devuelve cuántas borró."""
    assert tabla in TABLAS_HIJAS
    rowids = list(rowids)

    def accion(conexion):
        with conexion:
            for rowid in rowids:
                conexion.execute(f"DELETE FROM {tabla} WHERE rowid = ?", (rowid,))
        return len(rowids)

    return _con_conexion(ruta, accion, "No pude borrar de la base de datos")


def borrar_conceptos_sql(ruta, ids):
    """Borra conceptos completos (sus asociaciones, sinónimos y relaciones se van en cascada)."""
    ids = list(ids)

    def accion(conexion):
        with conexion:
            for concepto_id in ids:
                conexion.execute("DELETE FROM conceptos WHERE id = ?", (concepto_id,))

    _con_conexion(ruta, accion, "No pude borrar de la base de datos")


def contar_menciones_sql(ruta, clave):
    """Cuántas relaciones apuntan a este concepto."""
    def accion(conexion):
        return conexion.execute(
            "SELECT COUNT(*) FROM relaciones WHERE objetivo_normalizado = ?", (clave,)
        ).fetchone()[0]

    return _con_conexion(ruta, accion, "No pude consultar la base de datos")