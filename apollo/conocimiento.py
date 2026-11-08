"""
APOLLO — Gestión del conocimiento de FOCUS.

Administra conceptos, asociaciones, sinónimos y relaciones,
y busca conexiones entre conceptos.
"""

import os

from memoria.base_datos import (
    preparar_base,
    cargar_diccionario_sql,
    guardar_diccionario_sql,
    buscar_concepto_sql,
    entradas_por_clave_sql,
    relaciones_sql,
    inversas_sql,
    nombres_sql,
    existe_sql,
    buscar_id_sql,
    ids_por_clave_sql,
    filas_sql,
    crear_concepto_sql,
    agregar_texto_sql,
    agregar_relacion_sql,
    borrar_filas_sql,
    borrar_conceptos_sql,
    contar_menciones_sql
)

from memoria.almacenamiento import cargar_json, ErrorAlmacenamiento

from apollo.lenguaje import (
    normalizar_texto,
    quitar_acentos,
    quitar_signos,
    expandir_contracciones,
    limpiar_concepto,
    forma_singular,
    normalizar_concepto,
    normalizar_relacion,
    formas_de_relacion,
    distancia_edicion,
    tolerancia,
    FORMAS_RELACION
)


# ==========================================
# DÓNDE SE GUARDA EL DICCIONARIO
# ==========================================
# El diccionario vive en una base de datos SQLite (diccionario_hefesto.db).
# El JSON de antes (diccionario_hefesto.json) solo se usa una vez:
# si existe y todavía no hay base de datos, se pasa a ella.

ARCHIVO_DICCIONARIO = "diccionario_hefesto.json"

DICCIONARIO_INICIAL = {"palabras": []}


def ruta_base_datos():
    """'diccionario_hefesto.json' → 'diccionario_hefesto.db'"""
    return os.path.splitext(ARCHIVO_DICCIONARIO)[0] + ".db"


def migrar_desde_json():
    """
    Si hay un diccionario en JSON y todavía no hay base de datos,
    lo copia a la base de datos. El JSON no se borra.
    Devuelve True si migró algo.
    """
    if os.path.exists(ruta_base_datos()) or not os.path.exists(ARCHIVO_DICCIONARIO):
        return False

    diccionario = cargar_json(ARCHIVO_DICCIONARIO, DICCIONARIO_INICIAL)

    if not isinstance(diccionario, dict) or not isinstance(
        diccionario.get("palabras"), list
    ):
        raise ErrorAlmacenamiento(
            "El diccionario JSON no tiene la estructura esperada."
        )

    preparar_base(ruta_base_datos(), normalizar_concepto)
    guardar_diccionario_sql(ruta_base_datos(), diccionario, normalizar_concepto)
    return True


_bases_listas = set()


def base():
    """
    Ruta de la base de datos, ya lista: migra el JSON viejo y actualiza
    la versión de las tablas la primera vez que se usa.
    """
    ruta = ruta_base_datos()

    if ruta not in _bases_listas or not os.path.exists(ruta):
        migrar_desde_json()
        preparar_base(ruta, normalizar_concepto)
        _bases_listas.add(ruta)

    return ruta


def cargar_diccionario():
    """Todo el diccionario. Lo usan aprender y olvidar, que lo modifican completo."""
    return cargar_diccionario_sql(base())


def guardar_diccionario(diccionario):
    guardar_diccionario_sql(base(), diccionario, normalizar_concepto)


def entradas_del_concepto(concepto):
    """Las entradas de un concepto (o de su nombre principal, si es sinónimo)."""
    entrada = buscar_entrada(concepto)
    principal = entrada["palabra"] if entrada else concepto
    return entradas_por_clave_sql(base(), normalizar_concepto(principal))


# ==========================================
# UTILIDADES
# ==========================================

def buscar_entrada(palabra, diccionario=None):
    """Busca un concepto por su nombre principal o por un sinónimo."""

    # Sin diccionario en mano, le pregunta directo a la base de datos.
    if diccionario is None:
        return buscar_concepto_sql(base(), normalizar_concepto(palabra))

    palabra = normalizar_concepto(palabra)

    for entrada in diccionario["palabras"]:
        principal = normalizar_concepto(
            entrada.get("palabra", "")
        )

        sinonimos = [
            normalizar_concepto(s)
            for s in entrada.get("sinonimos", [])
        ]

        if palabra == principal or palabra in sinonimos:
            return entrada

    return None


# ==========================================
# RESULTADOS
# ==========================================
# Las funciones de aprender y olvidar NO imprimen ni preguntan nada:
# devuelven un resultado y quien las llama (HEFESTO, GAIA...) decide
# cómo comunicarlo. Así APOLLO sirve a cualquier inteligencia.
#
# Un resultado es un diccionario con un "estado" y datos extra:
#     {"estado": "aprendida", "sujeto": "sensor", ...}

def resultado(estado, **datos):
    return {"estado": estado, **datos}


# ==========================================
# APRENDER PALABRA
# ==========================================

def aprender_palabra(palabra, asociacion):
    """
    Aprende 'palabra es asociación' (por ejemplo, 'raspberry pi es una computadora').

    Estados posibles:
        "nueva"     aprendió una palabra que no conocía
        "asociada"  la palabra ya existía y ganó una asociación
        "ya_sabia"  ya conocía esa asociación
        "vacio"     faltan datos
    """

    palabra = forma_singular(palabra)
    asociacion = asociacion.strip()

    if not palabra or not asociacion:
        return resultado("vacio")

    datos = {"palabra": palabra, "asociacion": asociacion}

    # ¿Ya existe un concepto con ese nombre? (el primero, si hay repetidos)
    existentes = ids_por_clave_sql(base(), normalizar_concepto(palabra))

    if existentes:

        concepto_id = existentes[0][0]

        ya_estaba = any(
            normalizado == normalizar_concepto(asociacion)
            for _, _, normalizado in filas_sql(base(), "asociaciones", [concepto_id])
        )

        if ya_estaba:
            return resultado("ya_sabia", **datos)

        agregar_texto_sql(base(), "asociaciones", concepto_id, asociacion, normalizar_concepto)

        return resultado("asociada", **datos)

    concepto_id = crear_concepto_sql(base(), palabra, normalizar_concepto)
    agregar_texto_sql(base(), "asociaciones", concepto_id, asociacion, normalizar_concepto)

    return resultado("nueva", **datos)


def aprender_sinonimo(palabra, sinonimo):
    """
    Aprende que 'sinonimo' es otro nombre de 'palabra'.

    Estados posibles:
        "aprendido"      lo guardó
        "ya_sabia"       ya eran el mismo concepto
        "ya_registrado"  ese nombre ya es otro concepto
        "desconocido"    no conoce el concepto principal
        "iguales"        los dos términos son el mismo
        "vacio"          faltan datos
    """
    palabra = limpiar_concepto(palabra)
    sinonimo = limpiar_concepto(sinonimo)

    if not palabra or not sinonimo:
        return resultado("vacio")

    datos = {"palabra": palabra, "sinonimo": sinonimo}

    if normalizar_concepto(palabra) == normalizar_concepto(sinonimo):
        return resultado("iguales", **datos)

    concepto = buscar_id_sql(base(), normalizar_concepto(palabra))

    if concepto is None:
        return resultado("desconocido", **datos)

    otro = buscar_id_sql(base(), normalizar_concepto(sinonimo))

    if otro is not None and otro[0] == concepto[0]:
        return resultado("ya_sabia", **datos)     # ya eran el mismo concepto

    if otro is not None:
        return resultado("ya_registrado", **datos)

    agregar_texto_sql(base(), "sinonimos", concepto[0], sinonimo, normalizar_concepto)

    return resultado("aprendido", palabra=concepto[1], sinonimo=sinonimo)


# ==========================================
# BUSCAR PALABRA
# ==========================================

def buscar_palabra(palabra):
    entrada = buscar_entrada(palabra)

    if entrada is not None:
        return entrada.get("asociaciones", [])

    return []


# ==========================================
# RELACIONES
# ==========================================

# Las relaciones que Hefesto acepta salen del módulo de lenguaje.
RELACIONES_VALIDAS = set(FORMAS_RELACION)


# Relaciones que solo admiten UN objetivo: algo pertenece a un solo lugar.
# Si se aprende otro, es una contradicción y se pregunta si reemplazar.
# Las demás (mide, detecta, usa...) pueden tener muchos objetivos.
RELACIONES_UNICAS = {"pertenece a"}


def es_negada(relacion):
    """Una relación guardada con "negada": True significa 'NO'."""
    return isinstance(relacion, dict) and bool(relacion.get("negada", False))


def aprender_relacion(sujeto, relacion, objeto, negada=False, reemplazar=False):
    """
    Aprende 'sujeto relación objeto'.
    Con negada=True aprende lo contrario: 'sujeto NO relación objeto'.

    Si contradice algo que ya sabía, NO guarda nada y devuelve el estado
    "contradiccion" con la lista de conflictos. Quien la llamó decide
    (por ejemplo, preguntándote) y, si quiere reemplazar, vuelve a
    llamarla con reemplazar=True.

    Estados posibles:
        "aprendida"           la guardó (y "reemplazadas" dice qué quitó)
        "ya_sabia"            ya la conocía
        "contradiccion"       choca con "conflictos"; no guardó nada
        "relacion_invalida"   no conoce ese verbo
        "mismo_concepto"      sujeto y objeto son lo mismo
        "vacio"               faltan datos

    Hay dos tipos de contradicción:
    - Lo opuesto ya estaba guardado ("sí mide" contra "no mide").
    - Una relación única ya tenía otro objetivo ("pertenece a").
    """

    # Guardamos la versión limpia (con acentos) y comparamos
    # con la versión normalizada (sin acentos ni plurales).
    # El sujeto siempre en singular ("las aves" → "ave").
    # El objeto solo si es una categoría ("son máquinas" → "máquina");
    # en lo demás se respeta ("tiene plumas" se queda así).
    sujeto = forma_singular(sujeto)
    relacion = normalizar_relacion(relacion)
    objeto = forma_singular(objeto) if relacion == "es" else limpiar_concepto(objeto)

    if not sujeto or not objeto or not relacion:
        return resultado("vacio")

    datos = {
        "sujeto": sujeto,
        "relacion": relacion,
        "objeto": objeto,
        "negada": negada
    }

    if relacion not in RELACIONES_VALIDAS:
        return resultado("relacion_invalida", **datos)

    objeto_norm = normalizar_concepto(objeto)

    if normalizar_concepto(sujeto) == objeto_norm:
        return resultado("mismo_concepto", **datos)

    # El concepto del sujeto (por nombre o sinónimo); si no existe, se crea.
    concepto = buscar_id_sql(base(), normalizar_concepto(sujeto))
    concepto_id = concepto[0] if concepto else None

    conflictos = []   # (rowid, objetivo, negada)

    if concepto_id is not None:

        for rowid, relacion_guardada, objetivo, objetivo_norm, negada_guardada in filas_sql(
            base(), "relaciones", [concepto_id]
        ):

            if normalizar_relacion(relacion_guardada) != relacion:
                continue

            mismo_objetivo = objetivo_norm == objeto_norm
            mismo_sentido = bool(negada_guardada) == negada

            # 1. Ya lo sabía exactamente igual.
            if mismo_objetivo and mismo_sentido:
                return resultado("ya_sabia", **datos)

            # 2. Lo opuesto, o 3. una relación única con otro objetivo.
            contradice = (
                (mismo_objetivo and not mismo_sentido)
                or (
                    relacion in RELACIONES_UNICAS
                    and not negada
                    and not negada_guardada
                )
            )

            if contradice:
                conflictos.append((rowid, objetivo, bool(negada_guardada)))

    if conflictos and not reemplazar:

        return resultado(
            "contradiccion",
            conflictos=[
                {
                    "sujeto": sujeto,
                    "relacion": relacion,
                    "objeto": objetivo,
                    "negada": negada_guardada
                }
                for _, objetivo, negada_guardada in conflictos
            ],
            **datos
        )

    if concepto_id is None:
        concepto_id = crear_concepto_sql(base(), sujeto, normalizar_concepto)

    # Borrar los conflictos (si se pidió reemplazar) y agregar la nueva,
    # todo en una sola transacción.
    agregar_relacion_sql(
        base(), concepto_id, relacion, objeto, negada, normalizar_concepto,
        borrar_rowids=[rowid for rowid, _, _ in conflictos]
    )

    return resultado("aprendida", reemplazadas=len(conflictos), **datos)


def buscar_relaciones(sujeto, objeto=None, negadas=False):
    """
    Relaciones de un concepto, consultando directo la base de datos.

    Por defecto devuelve solo las afirmativas ("mide").
    Con negadas=True devuelve solo las negativas ("NO mide").
    Con objeto, solo las que apuntan a ese objeto.
    """

    # Si el sujeto es un sinónimo, usar el nombre principal.
    entrada = buscar_entrada(sujeto)
    principal = entrada["palabra"] if entrada else sujeto

    filas = relaciones_sql(base(), normalizar_concepto(principal), negadas)

    objeto = normalizar_concepto(objeto) if objeto is not None else None

    encontradas = []

    for relacion, objetivo in filas:

        if objeto is not None and normalizar_concepto(objetivo) != objeto:
            continue

        nueva = {"relacion": relacion, "objetivo": objetivo}

        if negadas:
            nueva["negada"] = True

        # Puede haber entradas antiguas repetidas
        # ("sensor" y "sensores"): se juntan sin duplicar.
        if nueva not in encontradas:
            encontradas.append(nueva)

    return encontradas


def buscar_inversas(objeto):
    """
    Quién apunta a este concepto: [(sujeto, relacion), ...].
    Incluye lo que apunta a sus sinónimos.
    """
    entrada = buscar_entrada(objeto)

    if entrada:
        claves = {normalizar_concepto(entrada["palabra"])}
        claves |= {normalizar_concepto(s) for s in entrada.get("sinonimos", [])}
    else:
        claves = {normalizar_concepto(objeto)}

    return inversas_sql(base(), claves)


def buscar_camino(origen, destino, visitados=None):
    origen = normalizar_concepto(origen)
    destino = normalizar_concepto(destino)

    if visitados is None:
        visitados = set()

    if origen in visitados:
        return None

    if origen == destino:
        return []

    visitados = visitados | {origen}
    relaciones = buscar_relaciones(origen)

    # Priorizar primero las conexiones directas.
    for relacion in relaciones:
        siguiente = normalizar_concepto(
            relacion.get("objetivo", "")
        )

        if siguiente == destino:
            return [
                {
                    "origen": origen,
                    "relacion": relacion["relacion"],
                    "destino": siguiente
                }
            ]

    # Si no hay conexión directa, buscar rutas indirectas.
    for relacion in relaciones:
        siguiente = normalizar_concepto(
            relacion.get("objetivo", "")
        )

        if not siguiente:
            continue

        camino_restante = buscar_camino(
            siguiente,
            destino,
            visitados
        )

        if camino_restante is not None:
            return [
                {
                    "origen": origen,
                    "relacion": relacion["relacion"],
                    "destino": siguiente
                }
            ] + camino_restante

    return None


def separar_origen_destino(texto):
    """Divide 'origen destino' aunque cada parte tenga varias palabras."""

    # Si el usuario usa "|", ese es el separador.
    if "|" in texto:
        origen, destino = texto.split("|", 1)
        return limpiar_concepto(origen), limpiar_concepto(destino)

    palabras = texto.split()

    if len(palabras) < 2:
        return None, None

    diccionario = cargar_diccionario()

    # Probar cada forma de dividir la frase y elegir la que
    # tenga un origen y un destino que Hefesto ya conoce.
    mejor = None

    for i in range(1, len(palabras)):
        origen = " ".join(palabras[:i])
        destino = " ".join(palabras[i:])

        origen_conocido = buscar_entrada(origen, diccionario) is not None
        destino_conocido = concepto_conocido(destino, diccionario)

        if origen_conocido and destino_conocido:
            return origen, destino

        if origen_conocido and mejor is None:
            mejor = (origen, destino)

    if mejor is not None:
        return mejor

    # Segundo intento: aceptar partes con errores de escritura
    # que se parezcan a conceptos conocidos.
    for i in range(1, len(palabras)):
        origen = " ".join(palabras[:i])
        destino = " ".join(palabras[i:])

        origen_parecido = sugerir_concepto(origen) is not None
        destino_parecido = (
            concepto_conocido(destino, diccionario)
            or sugerir_concepto(destino) is not None
        )

        if origen_parecido and destino_parecido:
            return origen, destino

    # Si no reconoce nada, usar la primera palabra como origen.
    return palabras[0], " ".join(palabras[1:])


def concepto_conocido(concepto, diccionario):
    """Indica si un concepto existe como palabra o como destino de una relación."""

    if buscar_entrada(concepto, diccionario) is not None:
        return True

    concepto = normalizar_concepto(concepto)

    for entrada in diccionario["palabras"]:
        for relacion in entrada.get("relaciones", []):
            if (
                isinstance(relacion, dict)
                and isinstance(relacion.get("objetivo"), str)
                and normalizar_concepto(relacion["objetivo"]) == concepto
            ):
                return True

    return False


def extraer_relacion(frase, incluir_es=False):
    """
    Encuentra 'sujeto relación objeto' en una frase.

    'Los sensores miden la temperatura'
        → ('sensores', 'mide', 'temperatura')

    Con incluir_es=True también reconoce 'X es Y'
    (se usa para preguntas como '¿la raspberry pi es una computadora?').
    """

    frase = expandir_contracciones(normalizar_texto(quitar_signos(frase)))

    # Buscamos sin acentos, pero recortamos de la frase original
    # para conservar los acentos en lo que se guarda.
    frase_sin_acentos = quitar_acentos(frase)

    if len(frase_sin_acentos) != len(frase):
        frase = frase_sin_acentos

    for forma, oficial in formas_de_relacion(incluir_es):

        separador = f" {forma} "
        posicion = frase_sin_acentos.find(separador)

        if posicion == -1:
            continue

        sujeto = limpiar_concepto(frase[:posicion])
        objeto = limpiar_concepto(frase[posicion + len(separador):])

        if sujeto and objeto:
            return sujeto, oficial, objeto

    return None


# ==========================================
# CONCEPTOS CONOCIDOS Y SUGERENCIAS
# ==========================================

def nombres_conocidos(diccionario=None):
    """Todos los nombres que Hefesto conoce: conceptos, sinónimos y objetivos."""

    if diccionario is None:
        filas = nombres_sql(base())
    else:
        filas = []
        for entrada in diccionario["palabras"]:
            if not isinstance(entrada, dict):
                continue
            nombres = [entrada.get("palabra", "")] + list(entrada.get("sinonimos", []))
            nombres += [
                r.get("objetivo", "") for r in entrada.get("relaciones", [])
                if isinstance(r, dict)
            ]
            filas += [(normalizar_concepto(n), n) for n in nombres if isinstance(n, str)]

    # Quitar vacíos y repetidos.
    unicos = {}

    for normalizado, original in filas:
        if normalizado and original.strip():
            unicos.setdefault(normalizado, original)

    return unicos


def existe_concepto(texto):
    """Indica si Hefesto conoce este concepto con esa escritura."""
    return existe_sql(base(), normalizar_concepto(texto))


def sugerir_concepto(texto):
    """
    Si texto parece un error de escritura de un concepto conocido,
    devuelve ese concepto. Si no, devuelve None.

    'raspbery pi' → 'raspberry pi'
    """

    buscado = normalizar_concepto(texto)
    conocidos = nombres_conocidos()

    if not buscado or buscado in conocidos:
        return None

    mejor = None
    mejor_distancia = tolerancia(buscado) + 1

    for normalizado, original in conocidos.items():

        distancia = distancia_edicion(buscado, normalizado)

        if distancia < mejor_distancia:
            mejor = original
            mejor_distancia = distancia

    return mejor


# ==========================================
# OLVIDAR
# ==========================================
# A diferencia de las funciones de aprender, estas NO imprimen:
# devuelven qué borraron y HEFESTO decide cómo decírtelo.
# Así APOLLO puede usarse desde cualquier otra inteligencia.

def _ids_del_concepto(concepto):
    """
    [(id, palabra), ...] de un concepto, buscando por nombre o sinónimo.
    Incluye entradas repetidas de datos antiguos ("sensor" y "sensores").
    """
    encontrado = buscar_id_sql(base(), normalizar_concepto(concepto))
    principal = encontrado[1] if encontrado else concepto

    return ids_por_clave_sql(base(), normalizar_concepto(principal))


def olvidar_relacion(sujeto, relacion, objeto, negada=False):
    """
    Borra 'sujeto relación objeto' (o 'sujeto NO relación objeto'
    si negada=True).
    Devuelve cuántas relaciones borró (0 si no la conocía).
    """
    relacion = normalizar_relacion(relacion)
    objeto_norm = normalizar_concepto(objeto)

    ids = [cid for cid, _ in _ids_del_concepto(sujeto)]

    a_borrar = [
        rowid
        for rowid, relacion_guardada, _, objetivo_norm, negada_guardada
        in filas_sql(base(), "relaciones", ids)
        if normalizar_relacion(relacion_guardada) == relacion
        and objetivo_norm == objeto_norm
        and bool(negada_guardada) == negada
    ]

    return borrar_filas_sql(base(), "relaciones", a_borrar)


def olvidar_categoria(concepto, categoria):
    """
    Borra 'concepto es categoría' (guardado como asociación o como relación 'es').
    Devuelve cuántas borró.
    """
    categoria_norm = normalizar_concepto(categoria)

    ids = [cid for cid, _ in _ids_del_concepto(concepto)]

    a_borrar = [
        rowid
        for rowid, _, normalizado in filas_sql(base(), "asociaciones", ids)
        if normalizado == categoria_norm
    ]

    borradas = borrar_filas_sql(base(), "asociaciones", a_borrar)

    return borradas + olvidar_relacion(concepto, "es", categoria)


def olvidar_sinonimo(a, b):
    """
    Borra que a y b son sinónimos (en cualquier orden).
    Devuelve True si lo borró.
    """
    for concepto, sinonimo in ((a, b), (b, a)):

        sinonimo_norm = normalizar_concepto(sinonimo)
        ids = [cid for cid, _ in _ids_del_concepto(concepto)]

        a_borrar = [
            rowid
            for rowid, _, normalizado in filas_sql(base(), "sinonimos", ids)
            if normalizado == sinonimo_norm
        ]

        if a_borrar:
            borrar_filas_sql(base(), "sinonimos", a_borrar)
            return True

    return False


def olvidar_concepto(concepto):
    """
    Borra todo lo que Hefesto sabe DE un concepto (su entrada completa).

    Devuelve (nombre borrado, cuántas relaciones de otros conceptos
    todavía lo mencionan), o (None, 0) si no lo conocía.
    """
    conceptos = _ids_del_concepto(concepto)

    if not conceptos:
        return None, 0

    nombre = conceptos[0][1]

    borrar_conceptos_sql(base(), [cid for cid, _ in conceptos])

    # ¿Quién más lo sigue mencionando?
    return nombre, contar_menciones_sql(base(), normalizar_concepto(nombre))


# ==========================================
# NEGACIÓN
# ==========================================

def extraer_relacion_con_negacion(frase, incluir_es=False):
    """
    Como extraer_relacion, pero también entiende el 'no'.

    'el pingüino no puede volar'
        → ('pingüino', 'puede', 'volar', True)
    'el sensor mide la temperatura'
        → ('sensor', 'mide', 'temperatura', False)
    """

    frase = expandir_contracciones(normalizar_texto(quitar_signos(frase)))
    frase_sin_acentos = quitar_acentos(frase)

    for forma, oficial in formas_de_relacion(incluir_es):

        separador = f" no {forma} "
        posicion = frase_sin_acentos.find(separador)

        if posicion == -1:
            continue

        sujeto = limpiar_concepto(frase[:posicion])
        objeto = limpiar_concepto(frase[posicion + len(separador):])

        if sujeto and objeto:
            return sujeto, oficial, objeto, True

    resultado = extraer_relacion(frase, incluir_es)

    if resultado is None:
        return None

    return resultado + (False,)


# ==========================================
# ORDENAR EL DICCIONARIO
# ==========================================

def _unir_sin_repetir(destino, nuevos, clave):
    """Agrega a 'destino' los elementos de 'nuevos' que no estén (según 'clave')."""
    vistos = {clave(x) for x in destino}

    for x in nuevos:
        if clave(x) not in vistos:
            destino.append(x)
            vistos.add(clave(x))


def ordenar_diccionario():
    """
    Pone el diccionario en orden:
    - Une las entradas repetidas del mismo concepto ("sensor" y "sensores").
    - Pasa los nombres de los conceptos a singular ("aves" → "ave").
    - Quita asociaciones, sinónimos y relaciones duplicadas.

    No borra conocimiento: solo lo junta. Devuelve un resultado con
    "unidas" (entradas que se juntaron) y "renombradas" (cambios de nombre).
    """
    diccionario = cargar_diccionario()

    grupos = {}       # concepto normalizado → entrada final
    orden = []
    unidas = 0
    renombradas = []

    for entrada in diccionario["palabras"]:

        if not isinstance(entrada, dict) or not entrada.get("palabra"):
            continue

        clave = normalizar_concepto(entrada["palabra"])

        if clave not in grupos:

            nombre = forma_singular(entrada["palabra"])

            if nombre != entrada["palabra"]:
                renombradas.append((entrada["palabra"], nombre))

            grupos[clave] = {
                "palabra": nombre,
                "asociaciones": [],
                "sinonimos": [],
                "relaciones": []
            }
            orden.append(clave)

        else:
            unidas += 1

        final = grupos[clave]

        _unir_sin_repetir(
            final["asociaciones"],
            [a for a in entrada.get("asociaciones", []) if isinstance(a, str)],
            normalizar_concepto
        )
        _unir_sin_repetir(
            final["sinonimos"],
            [x for x in entrada.get("sinonimos", []) if isinstance(x, str)],
            normalizar_concepto
        )
        _unir_sin_repetir(
            final["relaciones"],
            [r for r in entrada.get("relaciones", []) if isinstance(r, dict)],
            lambda r: (
                normalizar_relacion(r.get("relacion", "")),
                normalizar_concepto(r.get("objetivo", "")),
                es_negada(r)
            )
        )

    # Las categorías ("es") también van en singular.
    for final in grupos.values():
        for r in final["relaciones"]:
            if normalizar_relacion(r.get("relacion", "")) == "es":
                r["objetivo"] = forma_singular(r["objetivo"])

        # No guardar listas vacías de más.
        for campo in ("sinonimos", "relaciones"):
            if not final[campo]:
                del final[campo]

    diccionario["palabras"] = [grupos[clave] for clave in orden]

    guardar_diccionario(diccionario)

    return resultado("ordenado", unidas=unidas, renombradas=renombradas)