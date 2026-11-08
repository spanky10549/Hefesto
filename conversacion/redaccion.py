"""
Redacción en español.

Convierte los datos de una definición en frases naturales:

    Pingüino: es un ave. Puede nadar, pero no puede volar.
    Por ser ave, tiene plumas.

Funciones puras: reciben datos y devuelven texto.
"""

from apollo.lenguaje import quitar_acentos


# ==========================================
# GÉNERO Y ARTÍCULOS
# ==========================================

# Palabras que no siguen la regla de la terminación.
MASCULINAS = {
    "dia", "mapa", "problema", "sistema", "programa", "planeta", "clima",
    "tema", "idioma", "esquema", "diagrama", "teorema", "algoritmo",
    "sofa", "tranvia", "cometa", "poeta", "pijama"
}

FEMENINAS = {
    "mano", "foto", "moto", "radio", "flor", "red", "luz", "voz", "piel",
    "sal", "miel", "ley", "nariz", "raiz", "imagen", "carne", "nave",
    "llave", "clase", "fuente", "gente", "noche", "nube", "torre", "calle",
    "parte", "muerte", "suerte", "leche", "frase", "base", "placa", "tos"
}

TERMINACIONES_FEMENINAS = ("a", "cion", "sion", "dad", "tad", "tud", "umbre", "ez", "is")


def es_femenino(concepto, pista=None):
    """
    Adivina el género por la primera palabra (la que manda):
    'computadora de placa única' → femenino.

    'pista' es otra palabra del mismo género, como su categoría. Se usa
    cuando la palabra no da señales claras: 'raspberry pi' no termina en
    -a ni en -o, pero si es una computadora, es "la" Raspberry Pi.

    No es perfecto: el español tiene muchas excepciones.
    """
    palabra = quitar_acentos(concepto.split()[0]) if concepto.split() else ""

    if palabra in MASCULINAS:
        return False
    if palabra in FEMENINAS:
        return True

    # "análisis", "virus"... terminan en -is/-us pero son masculinas.
    if palabra in ("analisis", "virus", "lunes", "martes", "jueves", "viernes"):
        return False

    if palabra.endswith(TERMINACIONES_FEMENINAS):
        return True

    if palabra.endswith(("o", "or", "on", "an", "en", "ma")):
        return False

    # Sin señales claras: preguntarle a la pista.
    if pista:
        return es_femenino(pista)

    return False


A_TONICA = ("ave", "agua", "aguila", "alma", "arma", "aula", "hambre", "hacha")


def un(concepto, pista=None):
    """'ave' → 'un ave', 'computadora' → 'una computadora'."""
    # "un ave", "un águila": femeninas con a tónica inicial usan "un".
    if quitar_acentos(concepto).startswith(A_TONICA):
        return f"un {concepto}"

    return f"{'una' if es_femenino(concepto, pista) else 'un'} {concepto}"


def el(concepto, pista=None):
    """'sensor' → 'el sensor', 'temperatura' → 'la temperatura'."""
    if quitar_acentos(concepto).startswith(A_TONICA):
        return f"el {concepto}"

    return f"{'la' if es_femenino(concepto, pista) else 'el'} {concepto}"


# ==========================================
# LISTAS
# ==========================================

def unir(elementos, conjuncion="y"):
    """
    ['luz'] → 'luz'
    ['luz', 'sonido'] → 'luz y sonido'
    ['padres', 'hijos'] → 'padres e hijos'

    "y" se vuelve "e" antes de "i"/"hi", menos con "hie" (agua y hielo).
    "o" se vuelve "u" antes de "o"/"ho" (siete u ocho).
    """
    elementos = list(elementos)

    if not elementos:
        return ""
    if len(elementos) == 1:
        return elementos[0]

    ultimo = elementos[-1]
    inicio = quitar_acentos(ultimo.lower())

    if conjuncion == "y" and inicio.startswith(("i", "hi")) and not inicio.startswith(("ie", "hie")):
        conjuncion = "e"
    elif conjuncion == "o" and inicio.startswith(("o", "ho")):
        conjuncion = "u"

    return f"{', '.join(elementos[:-1])} {conjuncion} {ultimo}"


def oracion(texto):
    """Primera letra en mayúscula y punto al final."""
    texto = texto.strip()
    if not texto:
        return ""
    texto = texto[0].upper() + texto[1:]
    return texto if texto.endswith((".", "!", "?")) else texto + "."


# ==========================================
# DEFINICIÓN
# ==========================================

PREPOSICIONES_FINALES = ("con", "a", "de", "por")


def accion(verbo, objetivos, pistas):
    """
    'tiene', ['plumas', 'pico']     → 'tiene plumas y pico'
    'se comunica con', ['sensor']   → 'se comunica con el sensor'
    """
    if verbo.split()[-1] in PREPOSICIONES_FINALES:
        objetivos = [el(o, pistas.get(o)) for o in objetivos]

    texto = f"{verbo} {unir(objetivos)}"

    # "a el" → "al", "de el" → "del"
    return texto.replace(" a el ", " al ").replace(" de el ", " del ")


def redactar_definicion(datos):
    """
    Convierte el resultado de apollo.definicion.definir() en un párrafo.
    """
    concepto = datos["concepto"]
    pistas = datos.get("pistas_genero", {})

    if not datos["conocido"]:
        return f"Todavía no sé qué es {concepto}."

    frases = []

    # Otros nombres
    if datos["sinonimos"]:
        frases.append(oracion(f"también se le llama {unir(datos['sinonimos'], 'o')}"))

    # Qué es, y lo que es por consecuencia: "como es ave, también es un animal"
    if datos["categorias"]:
        frases.append(oracion(f"es {unir(un(c) for c in datos['categorias'])}"))

    por_via = {}
    for categoria, via in datos["categorias_deducidas"]:
        por_via.setdefault(via, []).append(categoria)

    for via, categorias in por_via.items():
        frases.append(oracion(f"como es {via}, también es {unir(un(c) for c in categorias)}"))

    # Lo que sí y lo que no, juntos por verbo: "puede nadar, pero no puede volar"
    verbos = list(datos["hace"]) + [v for v in datos["no_hace"] if v not in datos["hace"]]

    for verbo in verbos:
        si = datos["hace"].get(verbo, [])
        no = datos["no_hace"].get(verbo, [])

        partes = []
        if si:
            partes.append(accion(verbo, si, pistas))
        if no:
            partes.append("no " + accion(verbo, no, pistas))

        frases.append(oracion(", pero ".join(partes)))

    # Lo que hereda, agrupado por categoría: "por ser ave, tiene plumas y puede volar"
    por_categoria = {}
    for via, verbo, objetivo in datos["hereda"]:
        por_categoria.setdefault(via, {}).setdefault(verbo, []).append(objetivo)

    for via, grupos in por_categoria.items():
        acciones = unir(accion(verbo, objetivos, pistas) for verbo, objetivos in grupos.items())
        frases.append(oracion(f"por ser {via}, {acciones}"))

    # Ejemplos: "ejemplos de ave: pingüino y gorrión"
    if datos["ejemplos"]:
        frases.append(oracion(f"ejemplos de {concepto}: {unir(datos['ejemplos'])}"))

    # Quién lo menciona: "la raspberry pi se comunica con el sensor"
    for sujeto, verbo in datos["lo_mencionan"]:

        quien = el(sujeto, pistas.get(sujeto))

        if verbo.split()[-1] in PREPOSICIONES_FINALES:
            frase = f"{quien} {accion(verbo, [concepto], pistas)}"
        else:
            frase = f"{quien} {verbo} {el(concepto, pistas.get(concepto))}"

        frases.append(oracion(frase))

    titulo = concepto[0].upper() + concepto[1:]

    return f"{titulo}: " + " ".join(frases)