"""
APOLLO — Razonamiento.

Deduce conocimiento que nadie le enseñó directamente a HEFESTO:

- Herencia: si la Raspberry Pi ES una computadora y las computadoras
  NECESITAN electricidad, entonces la Raspberry Pi necesita electricidad.
- Relaciones inversas: si el sensor mide la temperatura, sabe
  responder qué mide la temperatura.
- Preguntas de sí o no, explicando cómo llegó a la respuesta.
- Excepciones: si las aves pueden volar pero el pingüino NO,
  lo más específico gana.

Cada conclusión viene con su "cadena": los pasos que la justifican.
"""

from apollo.conocimiento import (
    cargar_diccionario,
    buscar_entrada,
    buscar_relaciones,
    es_negada
)

from apollo.lenguaje import (
    forma_singular,
    limpiar_concepto,
    normalizar_concepto,
    normalizar_relacion
)


# ==========================================
# UTILIDADES
# ==========================================

def nombre_principal(concepto, diccionario):
    """Si 'concepto' es un sinónimo, devuelve el nombre principal."""
    entrada = buscar_entrada(concepto, diccionario)

    if entrada is not None:
        return entrada.get("palabra", concepto)

    return concepto


def mismo_concepto(a, b, diccionario):
    """'rpi' y 'Raspberry Pi' son el mismo concepto; 'sensores' y 'sensor' también."""
    return (
        normalizar_concepto(nombre_principal(a, diccionario))
        == normalizar_concepto(nombre_principal(b, diccionario))
    )


def entradas_de(concepto, diccionario):
    """
    Todas las entradas del diccionario que corresponden al concepto.
    Puede haber más de una en datos antiguos ('sensor' y 'sensores').
    """
    buscado = normalizar_concepto(nombre_principal(concepto, diccionario))

    return [
        entrada
        for entrada in diccionario["palabras"]
        if isinstance(entrada, dict)
        and normalizar_concepto(entrada.get("palabra", "")) == buscado
    ]


def paso(origen, relacion, destino):
    return {"origen": origen, "relacion": relacion, "destino": destino}


# ==========================================
# CATEGORÍAS ("ES")
# ==========================================

def categorias_directas(concepto, diccionario=None):
    """
    A qué categorías pertenece un concepto, según lo que se le enseñó.

    'aprende que la raspberry pi es una computadora' se guarda como
    asociación; aquí se interpreta como: raspberry pi → es → computadora.
    """
    if diccionario is None:
        diccionario = cargar_diccionario()

    categorias = []

    for entrada in entradas_de(concepto, diccionario):

        for asociacion in entrada.get("asociaciones", []):
            if isinstance(asociacion, str):
                categorias.append(forma_singular(asociacion))

        for relacion in entrada.get("relaciones", []):
            if (
                isinstance(relacion, dict)
                and isinstance(relacion.get("objetivo"), str)
                and normalizar_relacion(relacion.get("relacion", "")) == "es"
                and not es_negada(relacion)
            ):
                categorias.append(forma_singular(relacion["objetivo"]))

    # Quitar vacíos y repetidos.
    unicas = {}

    for categoria in categorias:
        if categoria:
            unicas.setdefault(normalizar_concepto(categoria), categoria)

    return list(unicas.values())


def ancestros(concepto, diccionario=None):
    """
    Todas las categorías de un concepto, directas e indirectas,
    cada una con la cadena que lo demuestra.

    raspberry pi → es → computadora → es → máquina
        [("computadora", [paso1]), ("máquina", [paso1, paso2])]

    Recorre el grafo por niveles (búsqueda en anchura), así que
    siempre encuentra la cadena más corta y no se traba con ciclos.
    """
    if diccionario is None:
        diccionario = cargar_diccionario()

    origen = nombre_principal(concepto, diccionario)

    visitados = {normalizar_concepto(origen)}
    pendientes = [(origen, [])]
    resultado = []

    while pendientes:

        actual, cadena = pendientes.pop(0)

        for categoria in categorias_directas(actual, diccionario):

            clave = normalizar_concepto(nombre_principal(categoria, diccionario))

            if clave in visitados:
                continue

            visitados.add(clave)

            nueva_cadena = cadena + [paso(actual, "es", categoria)]

            resultado.append((categoria, nueva_cadena))
            pendientes.append((categoria, nueva_cadena))

    return resultado


# ==========================================
# HERENCIA DE RELACIONES
# ==========================================

def relaciones_inferidas(concepto, diccionario=None):
    """
    Relaciones que un concepto hereda de sus categorías.

    Devuelve una lista de:
        {"relacion": ..., "objetivo": ..., "cadena": [pasos]}
    """
    if diccionario is None:
        diccionario = cargar_diccionario()

    def claves(relaciones):
        return {
            (normalizar_relacion(r["relacion"]), normalizar_concepto(r["objetivo"]))
            for r in relaciones
        }

    # Lo que el concepto ya sabe (sí o no) no se hereda:
    # si el pingüino NO puede volar, no hereda "puede volar" de ave.
    vistas = (
        claves(buscar_relaciones(concepto))
        | claves(buscar_relaciones(concepto, negadas=True))
    )

    inferidas = []

    # ancestros() va del más cercano al más lejano, así que
    # lo más específico siempre se revisa primero.
    for categoria, cadena in ancestros(concepto, diccionario):

        negaciones_categoria = claves(buscar_relaciones(categoria, negadas=True))

        for relacion in buscar_relaciones(categoria):

            verbo = normalizar_relacion(relacion["relacion"])

            if verbo == "es":
                continue    # las categorías ya las cubre ancestros()

            clave = (verbo, normalizar_concepto(relacion["objetivo"]))

            if clave in vistas:
                continue

            vistas.add(clave)

            inferidas.append({
                "relacion": verbo,
                "objetivo": relacion["objetivo"],
                "cadena": cadena + [
                    paso(categoria, verbo, relacion["objetivo"])
                ]
            })

        # Las negaciones de esta categoría bloquean a las más lejanas.
        vistas |= negaciones_categoria

    return inferidas


# ==========================================
# RELACIONES INVERSAS
# ==========================================

def relaciones_inversas(objeto, diccionario=None):
    """
    Quién tiene una relación HACIA este concepto.

    Si 'sensor → mide → temperatura', entonces para 'temperatura':
        [{"sujeto": "sensor", "relacion": "mide"}]
    """
    if diccionario is None:
        diccionario = cargar_diccionario()

    encontradas = []
    vistas = set()

    for entrada in diccionario["palabras"]:

        if not isinstance(entrada, dict):
            continue

        sujeto = entrada.get("palabra", "")

        candidatos = [
            (normalizar_relacion(r.get("relacion", "")), r.get("objetivo"))
            for r in entrada.get("relaciones", [])
            if isinstance(r, dict) and not es_negada(r)
        ]

        candidatos += [
            ("es", asociacion)
            for asociacion in entrada.get("asociaciones", [])
        ]

        for verbo, destino in candidatos:

            if not isinstance(destino, str):
                continue

            if not mismo_concepto(limpiar_concepto(destino), objeto, diccionario):
                continue

            clave = (normalizar_concepto(sujeto), verbo)

            if clave in vistas:
                continue

            vistas.add(clave)
            encontradas.append({"sujeto": sujeto, "relacion": verbo})

    return encontradas


# ==========================================
# PREGUNTAS DE SÍ O NO
# ==========================================

def verificar(sujeto, relacion, objeto, diccionario=None):
    """
    ¿Es cierto que 'sujeto relación objeto'?

    Devuelve la cadena de pasos que lo demuestra, o None si
    Hefesto no tiene información para confirmarlo.
    """
    if diccionario is None:
        diccionario = cargar_diccionario()

    relacion = normalizar_relacion(relacion)

    # 1. ¿Es una categoría? (directa o heredada)
    if relacion == "es":

        for categoria, cadena in ancestros(sujeto, diccionario):
            if mismo_concepto(categoria, objeto, diccionario):
                return cadena

        return None

    # 2. ¿Lo sabe directamente?
    for directa in buscar_relaciones(sujeto):
        if (
            normalizar_relacion(directa["relacion"]) == relacion
            and mismo_concepto(directa["objetivo"], objeto, diccionario)
        ):
            return [paso(sujeto, relacion, directa["objetivo"])]

    # 3. ¿Lo puede deducir por herencia?
    for inferida in relaciones_inferidas(sujeto, diccionario):
        if (
            inferida["relacion"] == relacion
            and mismo_concepto(inferida["objetivo"], objeto, diccionario)
        ):
            return inferida["cadena"]

    return None


# ==========================================
# RESPONDER CON SÍ, NO O NO SÉ
# ==========================================

SI = "sí"
NO = "no"
NO_SE = "no sé"


def _busca_en(relaciones, verbo, objeto, diccionario):
    """La primera relación de la lista con ese verbo y objetivo."""
    for r in relaciones:
        if (
            normalizar_relacion(r["relacion"]) == verbo
            and mismo_concepto(r["objetivo"], objeto, diccionario)
        ):
            return r
    return None


def responder(sujeto, relacion, objeto, diccionario=None):
    """
    Responde '¿sujeto relación objeto?' con SI, NO o NO_SE,
    junto con la cadena de pasos que lo justifica.

    Regla de las excepciones: gana lo más específico.
      1. Lo que se sabe del propio sujeto.
      2. Lo que se sabe de su categoría más cercana.
      3. Lo de categorías más lejanas.
    """
    if diccionario is None:
        diccionario = cargar_diccionario()

    verbo = normalizar_relacion(relacion)

    # Categorías: "¿el pingüino es un ave?"
    if verbo == "es":

        negada = _busca_en(
            buscar_relaciones(sujeto, negadas=True), "es", objeto, diccionario
        )

        if negada is not None:
            return NO, [paso(sujeto, "NO es", negada["objetivo"])]

        cadena = verificar(sujeto, "es", objeto, diccionario)

        return (SI, cadena) if cadena else (NO_SE, [])

    # 1. El propio sujeto, y luego 2-3. sus categorías, de cerca a lejos.
    niveles = [(sujeto, [])] + ancestros(sujeto, diccionario)

    for concepto, cadena in niveles:

        negada = _busca_en(
            buscar_relaciones(concepto, negadas=True), verbo, objeto, diccionario
        )

        if negada is not None:
            return NO, cadena + [paso(concepto, f"NO {verbo}", negada["objetivo"])]

        afirmada = _busca_en(
            buscar_relaciones(concepto), verbo, objeto, diccionario
        )

        if afirmada is not None:
            return SI, cadena + [paso(concepto, verbo, afirmada["objetivo"])]

    return NO_SE, []