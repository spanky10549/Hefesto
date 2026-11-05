"""
APOLLO — Gestión del conocimiento de FOCUS.

Administra conceptos, asociaciones, sinónimos y relaciones,
y busca conexiones entre conceptos.
"""

from memoria.almacenamiento import (
    cargar_json,
    guardar_json,
    ErrorAlmacenamiento
)

from apollo.lenguaje import (
    normalizar_texto,
    quitar_acentos,
    quitar_signos,
    expandir_contracciones,
    limpiar_concepto,
    normalizar_concepto,
    normalizar_relacion,
    formas_de_relacion,
    distancia_edicion,
    tolerancia,
    FORMAS_RELACION
)


# ==========================================
# ARCHIVO DEL DICCIONARIO
# ==========================================

ARCHIVO_DICCIONARIO = "diccionario_hefesto.json"

DICCIONARIO_INICIAL = {"palabras": []}


def cargar_diccionario():
    diccionario = cargar_json(ARCHIVO_DICCIONARIO, DICCIONARIO_INICIAL)

    if not isinstance(diccionario, dict) or not isinstance(
        diccionario.get("palabras"), list
    ):
        raise ErrorAlmacenamiento(
            "El diccionario no tiene la estructura esperada."
        )

    return diccionario


def guardar_diccionario(diccionario):
    guardar_json(ARCHIVO_DICCIONARIO, diccionario)


# ==========================================
# UTILIDADES
# ==========================================

def buscar_entrada(palabra, diccionario=None):
    """Busca un concepto por su nombre principal o por un sinónimo."""

    # Si no recibe un diccionario, carga uno.
    if diccionario is None:
        diccionario = cargar_diccionario()

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
# APRENDER PALABRA
# ==========================================

def aprender_palabra(palabra, asociacion):

    diccionario = cargar_diccionario()

    palabra = limpiar_concepto(palabra)
    asociacion = asociacion.strip()

    if not palabra or not asociacion:
        print("HEFESTO: No puedo aprender términos vacíos.")
        return

    for entrada in diccionario["palabras"]:

        if normalizar_concepto(entrada.get("palabra", "")) == normalizar_concepto(palabra):

            entrada.setdefault("asociaciones", [])

            # Evitar asociaciones duplicadas.
            if asociacion not in entrada["asociaciones"]:

                entrada["asociaciones"].append(asociacion)

                guardar_diccionario(diccionario)

                print(
                    f"HEFESTO: Aprendí que {palabra} "
                    f"está relacionado con {asociacion}."
                )

            else:
                print("HEFESTO: Ya conocía esa asociación.")

            return

    nueva_palabra = {
        "palabra": palabra,
        "asociaciones": [asociacion]
    }

    diccionario["palabras"].append(nueva_palabra)

    guardar_diccionario(diccionario)

    print(
        f"HEFESTO: Aprendí la palabra {palabra} "
        f"y su asociación con {asociacion}."
    )


def aprender_sinonimo(palabra, sinonimo):
    diccionario = cargar_diccionario()

    palabra = limpiar_concepto(palabra)
    sinonimo = limpiar_concepto(sinonimo)

    if not palabra or not sinonimo:
        print("HEFESTO: No puedo aprender términos vacíos.")
        return

    if normalizar_concepto(palabra) == normalizar_concepto(sinonimo):
        print("HEFESTO: Ambos términos son iguales.")
        return

    # Buscar DENTRO del mismo diccionario que vamos a guardar.
    entrada = buscar_entrada(palabra, diccionario)

    if entrada is None:
        print(f"HEFESTO: No conozco el concepto '{palabra}'.")
        return

    if buscar_entrada(sinonimo, diccionario) is not None:
        print(f"HEFESTO: '{sinonimo}' ya está registrado.")
        return

    if "sinonimos" not in entrada:
        entrada["sinonimos"] = []

    entrada["sinonimos"].append(sinonimo)

    guardar_diccionario(diccionario)

    print(
        f"HEFESTO: Aprendí que '{sinonimo}' "
        f"es sinónimo de '{entrada['palabra']}'."
    )


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


def aprender_relacion(sujeto, relacion, objeto, negada=False):
    """
    Aprende 'sujeto relación objeto'.
    Con negada=True aprende lo contrario: 'sujeto NO relación objeto'.

    Detecta contradicciones:
    - Lo opuesto ya estaba guardado ("sí mide" vs "no mide").
    - Una relación única ya tenía otro objetivo ("pertenece a").
    En ambos casos pregunta si debe reemplazar lo anterior.
    """

    diccionario = cargar_diccionario()

    # Guardamos la versión limpia (con acentos) y comparamos
    # con la versión normalizada (sin acentos ni plurales).
    sujeto = limpiar_concepto(sujeto)
    relacion = normalizar_relacion(relacion)
    objeto = limpiar_concepto(objeto)

    sujeto_norm = normalizar_concepto(sujeto)
    objeto_norm = normalizar_concepto(objeto)

    no = "NO " if negada else ""

    if not sujeto or not objeto or not relacion:
        print("HEFESTO: La relación contiene datos vacíos.")
        return

    if relacion not in RELACIONES_VALIDAS:
        print(
            f"HEFESTO: Todavía no reconozco la relación "
            f"'{relacion}'. No la guardaré."
        )
        return

    if sujeto_norm == objeto_norm:
        print(
            "HEFESTO: El sujeto y el objeto son iguales. "
            "Revisa esa relación."
        )
        return

    palabras = diccionario.get("palabras", [])

    entrada_sujeto = None

    for entrada in palabras:

        if not isinstance(entrada, dict):
            continue

        if buscar_entrada(sujeto, {"palabras": [entrada]}) is not None:

            entrada_sujeto = entrada
            break

    if entrada_sujeto is None:

        entrada_sujeto = {
            "palabra": sujeto,
            "asociaciones": [],
            "relaciones": []
        }

        palabras.append(entrada_sujeto)

    relaciones = entrada_sujeto.get("relaciones", [])

    if not isinstance(relaciones, list):
        relaciones = []

    entrada_sujeto["relaciones"] = relaciones

    a_reemplazar = []

    for existente in relaciones:

        if not isinstance(existente, dict):
            continue

        objetivo_existente = existente.get("objetivo")
        relacion_existente = existente.get("relacion")

        if not isinstance(objetivo_existente, str):
            continue

        if not isinstance(relacion_existente, str):
            continue

        if normalizar_relacion(relacion_existente) != relacion:
            continue

        mismo_objetivo = normalizar_concepto(objetivo_existente) == objeto_norm
        mismo_sentido = es_negada(existente) == negada

        # 1. Ya lo sabía exactamente igual.
        if mismo_objetivo and mismo_sentido:
            print("HEFESTO: Ya conocía esa relación.")
            return

        # 2. Contradicción directa: antes dijiste lo contrario.
        if mismo_objetivo and not mismo_sentido:

            antes = "NO " if es_negada(existente) else ""

            print(
                f"HEFESTO: Esto contradice algo que ya sé: "
                f"{sujeto} {antes}{relacion} {objetivo_existente}."
            )

            a_reemplazar.append(existente)

        # 3. Relación única con otro objetivo (pertenece a).
        elif relacion in RELACIONES_UNICAS and not negada and not es_negada(existente):

            print(
                f"HEFESTO: Esto contradice algo que ya sé: "
                f"{sujeto} {relacion} {objetivo_existente}, "
                f"y algo solo puede '{relacion}' una cosa."
            )

            a_reemplazar.append(existente)

    if a_reemplazar:

        respuesta = input(
            "¿Reemplazo lo que sabía por lo nuevo? (s/n): "
        ).strip().lower()

        if respuesta != "s":
            print("HEFESTO: Me quedo con lo que ya sabía.")
            return

        for existente in a_reemplazar:
            relaciones.remove(existente)

    nueva = {"relacion": relacion, "objetivo": objeto}

    if negada:
        nueva["negada"] = True

    relaciones.append(nueva)

    guardar_diccionario(diccionario)

    print(
        f"HEFESTO: Aprendí la relación "
        f"{sujeto} → {no}{relacion} → {objeto}."
    )


def buscar_relaciones(sujeto, objeto=None, negadas=False):
    """
    Relaciones de un concepto.

    Por defecto devuelve solo las afirmativas ("mide").
    Con negadas=True devuelve solo las negativas ("NO mide").
    """

    diccionario = cargar_diccionario()

    sujeto = normalizar_concepto(sujeto)

    # Si el sujeto es un sinónimo, usar el nombre principal.
    entrada_sinonimo = buscar_entrada(sujeto, diccionario)

    if entrada_sinonimo is not None:
        sujeto = normalizar_concepto(
            entrada_sinonimo.get("palabra", sujeto)
        )

    relaciones_encontradas = []

    if objeto is not None:
        objeto = normalizar_concepto(objeto)

    for entrada in diccionario.get("palabras", []):

        if not isinstance(entrada, dict):
            continue

        palabra_guardada = normalizar_concepto(
            entrada.get("palabra", "")
        )

        if palabra_guardada == sujeto:

            relaciones = entrada.get("relaciones", [])

            if not isinstance(relaciones, list):
                continue

            relaciones_validas = [
                relacion
                for relacion in relaciones
                if isinstance(relacion, dict)
                and isinstance(relacion.get("objetivo"), str)
                and isinstance(relacion.get("relacion"), str)
                and es_negada(relacion) == negadas
            ]

            if objeto is not None:

                relaciones_validas = [
                    relacion
                    for relacion in relaciones_validas
                    if normalizar_concepto(
                        relacion["objetivo"]
                    ) == objeto
                ]

            # Puede haber entradas antiguas repetidas
            # ("sensor" y "sensores"): se juntan sus relaciones.
            for relacion in relaciones_validas:
                if relacion not in relaciones_encontradas:
                    relaciones_encontradas.append(relacion)

    return relaciones_encontradas


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
        diccionario = cargar_diccionario()

    nombres = []

    for entrada in diccionario["palabras"]:

        if not isinstance(entrada, dict):
            continue

        nombres.append(entrada.get("palabra", ""))
        nombres.extend(entrada.get("sinonimos", []))

        for relacion in entrada.get("relaciones", []):
            if isinstance(relacion, dict):
                nombres.append(relacion.get("objetivo", ""))

    # Quitar vacíos y repetidos (comparando normalizado).
    unicos = {}

    for nombre in nombres:
        if isinstance(nombre, str) and nombre.strip():
            unicos.setdefault(normalizar_concepto(nombre), nombre)

    return unicos


def existe_concepto(texto):
    """Indica si Hefesto conoce este concepto con esa escritura."""
    return normalizar_concepto(texto) in nombres_conocidos()


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

def _entradas_del_concepto(concepto, diccionario):
    """Entradas del diccionario de un concepto (incluye datos repetidos antiguos)."""
    entrada = buscar_entrada(concepto, diccionario)
    principal = entrada.get("palabra", concepto) if entrada else concepto
    buscado = normalizar_concepto(principal)

    return [
        e for e in diccionario["palabras"]
        if isinstance(e, dict)
        and normalizar_concepto(e.get("palabra", "")) == buscado
    ]


def olvidar_relacion(sujeto, relacion, objeto, negada=False):
    """
    Borra 'sujeto relación objeto' (o 'sujeto NO relación objeto'
    si negada=True).
    Devuelve cuántas relaciones borró (0 si no la conocía).
    """
    diccionario = cargar_diccionario()

    relacion = normalizar_relacion(relacion)
    objeto_norm = normalizar_concepto(objeto)
    borradas = 0

    for entrada in _entradas_del_concepto(sujeto, diccionario):

        antes = entrada.get("relaciones", [])

        despues = [
            r for r in antes
            if not (
                isinstance(r, dict)
                and normalizar_relacion(r.get("relacion", "")) == relacion
                and normalizar_concepto(r.get("objetivo", "")) == objeto_norm
                and es_negada(r) == negada
            )
        ]

        borradas += len(antes) - len(despues)
        entrada["relaciones"] = despues

    if borradas:
        guardar_diccionario(diccionario)

    return borradas


def olvidar_categoria(concepto, categoria):
    """
    Borra 'concepto es categoría' (guardado como asociación o como relación 'es').
    Devuelve cuántas borró.
    """
    diccionario = cargar_diccionario()

    categoria_norm = normalizar_concepto(categoria)
    borradas = 0

    for entrada in _entradas_del_concepto(concepto, diccionario):

        asociaciones = entrada.get("asociaciones", [])

        restantes = [
            a for a in asociaciones
            if not (isinstance(a, str) and normalizar_concepto(a) == categoria_norm)
        ]

        borradas += len(asociaciones) - len(restantes)
        entrada["asociaciones"] = restantes

    if borradas:
        guardar_diccionario(diccionario)

    return borradas + olvidar_relacion(concepto, "es", categoria)


def olvidar_sinonimo(a, b):
    """
    Borra que a y b son sinónimos (en cualquier orden).
    Devuelve True si lo borró.
    """
    diccionario = cargar_diccionario()

    for concepto, sinonimo in ((a, b), (b, a)):

        sinonimo_norm = normalizar_concepto(sinonimo)

        for entrada in _entradas_del_concepto(concepto, diccionario):

            sinonimos = entrada.get("sinonimos", [])

            restantes = [
                s for s in sinonimos
                if normalizar_concepto(s) != sinonimo_norm
            ]

            if len(restantes) != len(sinonimos):
                entrada["sinonimos"] = restantes
                guardar_diccionario(diccionario)
                return True

    return False


def olvidar_concepto(concepto):
    """
    Borra todo lo que Hefesto sabe DE un concepto (su entrada completa).

    Devuelve (nombre borrado, cuántas relaciones de otros conceptos
    todavía lo mencionan), o (None, 0) si no lo conocía.
    """
    diccionario = cargar_diccionario()

    entradas = _entradas_del_concepto(concepto, diccionario)

    if not entradas:
        return None, 0

    nombre = entradas[0].get("palabra", concepto)

    diccionario["palabras"] = [
        e for e in diccionario["palabras"] if e not in entradas
    ]

    guardar_diccionario(diccionario)

    # ¿Quién más lo sigue mencionando?
    nombre_norm = normalizar_concepto(nombre)
    menciones = sum(
        1
        for e in diccionario["palabras"]
        if isinstance(e, dict)
        for r in e.get("relaciones", [])
        if isinstance(r, dict)
        and normalizar_concepto(r.get("objetivo", "")) == nombre_norm
    )

    return nombre, menciones


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