"""
Calculadora de HEFESTO.

Resuelve operaciones paso a paso y explica el orden:

    3 + 4 × 2
      Paso 1: 4 × 2 = 8   (multiplicaciones y divisiones antes que sumas y restas)
      Paso 2: 3 + 8 = 11

NO usa eval(): eval ejecuta cualquier código de Python, y alguien podría
escribir algo que borre archivos. Aquí hay un analizador propio que
solo entiende números y operaciones.

Cómo funciona, en tres etapas (igual que un compilador en miniatura):
  1. Tokens:  "3 + 4 × 2"  →  [3, +, 4, ×, 2]
  2. Árbol:   respetando la prioridad de las operaciones
                    +
                   / \\
                  3   ×
                     / \\
                    4   2
  3. Resolver: reduce el árbol una operación a la vez, de lo más
     profundo a lo más alto, y anota cada paso.

Usa fracciones exactas (fractions.Fraction): 1/3 × 3 da 1, no 0.9999999.
"""

import math
import re
from fractions import Fraction

from apollo.lenguaje import quitar_acentos


class ErrorCalculo(Exception):
    """La operación no se puede resolver (mal escrita, división entre cero...)."""


# ==========================================
# 1. TOKENS
# ==========================================

UNIDADES = {
    "cero": 0, "uno": 1, "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
}

DECENAS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90,
}

# Frases en español → símbolos. Las más largas primero.
PALABRAS = [
    ("raiz cuadrada de", " √ "), ("raiz de", " √ "),
    ("dividido entre", " / "), ("dividido por", " / "),
    ("multiplicado por", " * "), ("elevado a la", " ^ "), ("elevado a", " ^ "),
    ("al cuadrado", " ^ 2 "), ("al cubo", " ^ 3 "),
    ("entre", " / "), ("sobre", " / "),
    ("mas", " + "), ("menos", " - "), ("por", " * "),
]


def palabras_a_numeros(texto):
    """'treinta y dos más uno' → '32 más 1'"""

    def decena_y_unidad(m):
        return str(DECENAS[m.group(1)] + UNIDADES[m.group(2)])

    patron_compuesto = r"\b(" + "|".join(DECENAS) + r") y (" + "|".join(UNIDADES) + r")\b"
    texto = re.sub(patron_compuesto, decena_y_unidad, texto)

    for palabra, valor in list(DECENAS.items()) + list(UNIDADES.items()) + [("cien", 100)]:
        texto = re.sub(rf"\b{palabra}\b", str(valor), texto)

    return texto


def tokenizar(texto):
    """
    Convierte el texto en una lista de piezas: números (Fraction) y
    símbolos ('+', '-', '*', '/', '^', '√', '(', ')').
    """
    texto = quitar_acentos(texto.lower())
    texto = palabras_a_numeros(texto)

    for palabra, simbolo in PALABRAS:
        texto = re.sub(rf"\b{palabra}\b", simbolo, texto)

    # Símbolos de teclado y de cuaderno.
    # Los distintos "menos": el tipográfico (−), el guion largo (–) y el del teclado (-).
    texto = texto.replace("−", "-").replace("–", "-")

    texto = (texto.replace("×", "*").replace("·", "*").replace("÷", "/")
                  .replace("**", "^").replace("[", "(").replace("]", ")"))

    # "2 x 3" → multiplicación (solo una x suelta entre números).
    texto = re.sub(r"(?<=[\d)\s])x(?=[\s\d(])", "*", texto)

    # "3,5" sin espacios → 3.5
    texto = re.sub(r"(\d),(\d)", r"\1.\2", texto)

    tokens = []
    posicion = 0

    for m in re.finditer(r"\s*(?:(\d+(?:\.\d+)?|\.\d+)|([-+*/^√()]))", texto):

        if m.start() != posicion:
            break                          # algo que no es número ni operación

        numero, simbolo = m.groups()
        tokens.append(Fraction(numero) if numero else simbolo)
        posicion = m.end()

    resto = texto[posicion:].strip()

    if resto:
        raise ErrorCalculo(f"No entiendo esta parte: '{resto}'")

    if not tokens:
        raise ErrorCalculo("No encontré ninguna operación.")

    return tokens


# ==========================================
# 2. ÁRBOL (análisis por descenso recursivo)
# ==========================================
# Cada nivel de la gramática es una prioridad, de menor a mayor:
#   suma:     termino (('+' | '-') termino)*
#   termino:  factor  (('*' | '/') factor)*
#   factor:   ('-' | '√') factor  |  potencia
#   potencia: atomo ('^' factor)?          ← a la derecha: 2^3^2 = 2^9
#   atomo:    número  |  '(' suma ')'
#
# Un nodo es un número (Fraction/float) o una tupla:
#   (operador, izquierda, derecha)  para + - * / ^
#   (operador, valor)               para el menos de un número y la raíz

class Analizador:

    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def ver(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def tomar(self):
        token = self.ver()
        self.i += 1
        return token

    def analizar(self):
        arbol = self.suma()
        if self.ver() is not None:
            raise ErrorCalculo(f"Sobra algo al final: '{self.ver()}'")
        return arbol

    def suma(self):
        nodo = self.termino()
        while self.ver() in ("+", "-"):
            nodo = (self.tomar(), nodo, self.termino())
        return nodo

    def termino(self):
        nodo = self.factor()
        while self.ver() in ("*", "/"):
            nodo = (self.tomar(), nodo, self.factor())
        return nodo

    def factor(self):
        if self.ver() == "-":
            self.tomar()
            return ("neg", self.factor())
        if self.ver() == "+":
            self.tomar()
            return self.factor()
        if self.ver() == "√":
            self.tomar()
            return ("√", self.factor())
        return self.potencia()

    def potencia(self):
        base = self.atomo()
        if self.ver() == "^":
            self.tomar()
            return ("^", base, self.factor())
        return base

    def atomo(self):
        token = self.tomar()

        if isinstance(token, Fraction):
            return token

        if token == "(":
            nodo = self.suma()
            if self.tomar() != ")":
                raise ErrorCalculo("Falta cerrar un paréntesis.")
            return nodo

        if token is None:
            raise ErrorCalculo("La operación está incompleta.")

        raise ErrorCalculo(f"No esperaba '{token}' ahí.")


# ==========================================
# MOSTRAR NÚMEROS Y EXPRESIONES
# ==========================================

SIMBOLOS = {"+": "+", "-": "−", "*": "×", "/": "÷", "^": "^"}
PRIORIDAD = {"+": 1, "-": 1, "*": 2, "/": 2, "neg": 3, "√": 3, "^": 4}


def es_numero(nodo):
    return isinstance(nodo, (Fraction, float))


def decimal_exacto(fraccion):
    """¿Se puede escribir exacto con decimales? (5/2 = 2.5 sí; 1/3 no)."""
    d = fraccion.denominator
    for primo in (2, 5):
        while d % primo == 0:
            d //= primo
    return d == 1


def mostrar_numero(valor):
    """8 → '8', 5/2 → '2.5', 1/3 → '1/3', √2 → '1.41421', −6 → '−6'"""
    if isinstance(valor, Fraction):
        if valor.denominator == 1:
            texto = str(valor.numerator)
        elif decimal_exacto(valor):
            texto = f"{float(valor):.10g}"
        else:
            texto = f"{valor.numerator}/{valor.denominator}"   # exacto: 1/3
    elif valor == int(valor) and abs(valor) < 1e15:
        texto = str(int(valor))
    else:
        texto = f"{valor:.6g}"

    return texto.replace("-", "−")


def es_fraccion_visible(valor):
    return isinstance(valor, Fraction) and valor.denominator != 1 and not decimal_exacto(valor)


def mostrar(nodo, prioridad_padre=0, lado=None):
    """Escribe el árbol como texto, con paréntesis solo donde hacen falta."""
    if es_numero(nodo):
        texto = mostrar_numero(nodo)
        # Dentro de otra operación van entre paréntesis:
        #   un negativo a la derecha: 3 × (−2)    y una fracción: (1/3) × 3
        if prioridad_padre and (
            (nodo < 0 and (lado == "der" or prioridad_padre >= PRIORIDAD["^"]))
            or es_fraccion_visible(nodo)
        ):
            return f"({texto})"
        return texto

    operador = nodo[0]
    prioridad = PRIORIDAD[operador]

    if operador == "neg":
        texto = "−" + mostrar(nodo[1], prioridad)
    elif operador == "√":
        texto = "√" + mostrar(nodo[1], prioridad)
    else:
        izquierda = mostrar(nodo[1], prioridad, "izq")
        derecha = mostrar(nodo[2], prioridad + (0 if operador == "^" else 0.5), "der")
        texto = f"{izquierda} {SIMBOLOS[operador]} {derecha}"

    necesita = prioridad < prioridad_padre or (
        prioridad == prioridad_padre and operador == "^" and lado == "izq"
    )

    return f"({texto})" if necesita else texto


# ==========================================
# 3. RESOLVER PASO A PASO
# ==========================================

MAX_EXPONENTE = 1000


def aplicar(nodo):
    """Resuelve un nodo cuyos hijos ya son números."""
    operador = nodo[0]

    if operador == "neg":
        return -nodo[1]

    if operador == "√":
        valor = nodo[1]
        if valor < 0:
            raise ErrorCalculo("No hay raíz cuadrada real de un número negativo.")
        if isinstance(valor, Fraction):
            n, d = math.isqrt(valor.numerator), math.isqrt(valor.denominator)
            if n * n == valor.numerator and d * d == valor.denominator:
                return Fraction(n, d)          # raíz exacta: √(9/4) = 3/2
        return math.sqrt(valor)

    a, b = nodo[1], nodo[2]

    if operador == "+":
        return a + b
    if operador == "-":
        return a - b
    if operador == "*":
        return a * b
    if operador == "/":
        if b == 0:
            raise ErrorCalculo("No se puede dividir entre cero.")
        return a / b
    if operador == "^":
        if abs(b) > MAX_EXPONENTE:
            raise ErrorCalculo(f"El exponente es demasiado grande (máximo {MAX_EXPONENTE}).")
        if a == 0 and b < 0:
            raise ErrorCalculo("No se puede dividir entre cero (0 a una potencia negativa).")
        if isinstance(b, Fraction) and b.denominator == 1 and isinstance(a, Fraction):
            return a ** int(b)
        if a < 0:
            raise ErrorCalculo("Esa potencia no da un número real.")
        return float(a) ** float(b)

    raise ErrorCalculo(f"Operación desconocida: {operador}")


def _reducibles(nodo, ruta=(), padre=None):
    """
    Todas las operaciones que ya se pueden resolver (sus hijos ya son
    números), de izquierda a derecha, con su ruta en el árbol.
    """
    if es_numero(nodo):
        return []

    hijos = nodo[1:]

    if all(es_numero(h) for h in hijos):
        return [(ruta, nodo, padre)]

    encontrados = []
    for i, hijo in enumerate(hijos, start=1):
        encontrados += _reducibles(hijo, ruta + (i,), nodo)
    return encontrados


def _siguiente(arbol):
    """
    Qué operación resolver ahora, como se enseña en la escuela:
      1. Lo que está entre paréntesis.
      2. Potencias y raíces.
      3. Multiplicaciones y divisiones.
      4. Sumas y restas.
    Si empatan, la de más a la izquierda.
    """
    candidatos = _reducibles(arbol)

    def prioridad(candidato):
        _, nodo, padre = candidato
        entre_parentesis = padre is not None and PRIORIDAD[nodo[0]] < PRIORIDAD[padre[0]]
        return (entre_parentesis, PRIORIDAD[nodo[0]])

    mejor = max(prioridad(c) for c in candidatos)

    return next(ruta for ruta, *_ in [c for c in candidatos if prioridad(c) == mejor])


def _obtener(nodo, ruta):
    for i in ruta:
        nodo = nodo[i]
    return nodo


def _reemplazar(nodo, ruta, valor):
    if not ruta:
        return valor
    i = ruta[0]
    hijos = list(nodo)
    hijos[i] = _reemplazar(nodo[i], ruta[1:], valor)
    return tuple(hijos)


def _operadores(nodo):
    if es_numero(nodo):
        return set()
    return {nodo[0]}.union(*(_operadores(h) for h in nodo[1:]))


def _razon(arbol, ruta, operacion):
    """Por qué esta operación va ahora (para explicar el orden)."""
    padre = _obtener(arbol, ruta[:-1]) if ruta else None
    operador = operacion[0]

    if padre is not None and not es_numero(padre) and PRIORIDAD[operador] < PRIORIDAD[padre[0]]:
        return "primero lo que está entre paréntesis"

    if operador in ("^", "√"):
        return "las potencias y raíces van primero"

    if operador in ("*", "/") and _operadores(arbol) & {"+", "-"}:
        return "multiplicaciones y divisiones antes que sumas y restas"

    if len(_operadores(arbol) - {"neg"}) > 1 or _cuenta_operaciones(arbol) > 1:
        return "de izquierda a derecha"

    return None


def _cuenta_operaciones(nodo):
    if es_numero(nodo):
        return 0
    return 1 + sum(_cuenta_operaciones(h) for h in nodo[1:])


def calcular(texto):
    """
    Resuelve una operación escrita en texto.

    Devuelve:
        {"expresion": "3 + 4 × 2", "resultado": Fraction(11),
         "resultado_texto": "11",
         "pasos": [{"operacion": "4 × 2 = 8", "razon": "...", "queda": "3 + 8"}, ...]}

    Lanza ErrorCalculo si no se puede.
    """
    arbol = Analizador(tokenizar(texto)).analizar()

    expresion = mostrar(arbol)
    pasos = []

    while not es_numero(arbol):

        ruta = _siguiente(arbol)
        operacion = _obtener(arbol, ruta)
        valor = aplicar(operacion)

        # El menos de un número ("−3") no es un paso que valga la pena explicar.
        if operacion[0] == "neg":
            arbol = _reemplazar(arbol, ruta, valor)
            continue

        razon = _razon(arbol, ruta, operacion)
        arbol = _reemplazar(arbol, ruta, valor)

        pasos.append({
            "operacion": f"{mostrar(operacion)} = {mostrar_numero(valor)}",
            "razon": razon,
            "queda": mostrar(arbol),
        })

    resultado_texto = mostrar_numero(arbol)

    # Si quedó una fracción como 1/3, también su aproximación: 1/3 (≈ 0.333333)
    if es_fraccion_visible(arbol):
        resultado_texto += f" (≈ {float(arbol):.6g})"

    return {
        "expresion": expresion,
        "resultado": arbol,
        "resultado_texto": resultado_texto,
        "pasos": pasos,
    }


# ==========================================
# ¿ES UNA OPERACIÓN?
# ==========================================

PREFIJOS_CALCULO = (
    "cuanto es ", "cuanto da ", "cuanto son ", "calcula ", "resuelve ",
    "cuanto es la ", "cuanto vale "
)


def extraer_operacion(comando):
    """
    Si el comando pide un cálculo, devuelve la operación; si no, None.

        "¿cuánto es 3 + 4 × 2?"   → "3 + 4 × 2"
        "3+4"                     → "3+4"
        "qué sabes de perro"      → None
    """
    texto = quitar_acentos(comando.lower()).replace("¿", "").replace("?", "").strip()

    for prefijo in sorted(PREFIJOS_CALCULO, key=len, reverse=True):
        if texto.startswith(prefijo):
            return comando.strip().replace("¿", "").replace("?", "")[len(prefijo):].strip()

    # Algo que solo tiene números y signos de operación: "3+4*2", "(2+3)^2"
    if re.fullmatch(r"[\d\s.,+\-−–*/^×÷·()√]+", texto) and re.search(r"\d", texto) \
            and re.search(r"[+\-−–*/^×÷·√]", texto):
        return comando.strip()

    return None