"""
Pruebas de la calculadora (funciones puras, sin diccionario).
"""

from fractions import Fraction

import pytest

from calculo.aritmetica import calcular, extraer_operacion, tokenizar, ErrorCalculo


def resultado(texto):
    return calcular(texto)["resultado"]


# ==========================================
# ORDEN DE LAS OPERACIONES
# ==========================================

@pytest.mark.parametrize("texto, esperado", [
    ("2 + 2", 4),
    ("3 + 4 × 2", 11),          # multiplicación primero
    ("(3 + 4) × 2", 14),        # paréntesis primero
    ("8 / 2 * 4", 16),          # de izquierda a derecha
    ("10 - 4 - 3", 3),          # de izquierda a derecha
    ("2 ^ 3 ^ 2", 512),         # potencias de derecha a izquierda: 2^9
    ("-2 ^ 2", -4),             # la potencia va antes que el menos
    ("(-2) ^ 2", 4),
    ("2 - -3", 5),
    ("((1 + 2) * (3 + 4)) ^ 2", 441),
])
def test_orden_de_operaciones(texto, esperado):
    assert resultado(texto) == esperado


def test_fracciones_exactas():
    assert resultado("1 / 3 * 3") == 1          # no 0.9999999
    assert resultado("10 / 4") == Fraction(5, 2)


def test_raices():
    assert resultado("raíz de 16") == 4
    assert resultado("√(9/4)") == Fraction(3, 2)
    assert abs(resultado("√2") - 1.41421356) < 1e-6


# ==========================================
# ESPAÑOL Y SÍMBOLOS
# ==========================================

@pytest.mark.parametrize("texto, esperado", [
    ("tres más cuatro por dos", 11),
    ("treinta y dos entre ocho", 4),
    ("diez menos tres", 7),
    ("cinco al cuadrado", 25),
    ("dos elevado a diez", 1024),
    ("raíz cuadrada de 16 más 2 al cuadrado", 8),
    ("2 x 3", 6),
    ("6 ÷ 2 · 3", 9),
    ("3,5 + 1.5", 5),
    ("2**3", 8),
])
def test_entiende_espanol_y_simbolos(texto, esperado):
    assert resultado(texto) == esperado


# ==========================================
# PASOS Y EXPLICACIONES
# ==========================================

def test_explica_los_pasos_como_en_la_escuela():
    pasos = calcular("3 + 4 * 2 - 6 / 3")["pasos"]

    assert [p["operacion"] for p in pasos] == [
        "4 × 2 = 8", "6 ÷ 3 = 2", "3 + 8 = 11", "11 − 2 = 9"
    ]
    assert pasos[0]["razon"] == "multiplicaciones y divisiones antes que sumas y restas"
    assert pasos[0]["queda"] == "3 + 8 − 6 ÷ 3"


def test_explica_los_parentesis():
    pasos = calcular("(3 + 4) * 2")["pasos"]

    assert pasos[0]["razon"] == "primero lo que está entre paréntesis"


def test_muestra_fracciones_y_aproximacion():
    r = calcular("10 / 3")

    assert r["resultado_texto"] == "10/3 (≈ 3.33333)"


# ==========================================
# ERRORES
# ==========================================

@pytest.mark.parametrize("texto, mensaje", [
    ("5 / 0", "dividir entre cero"),
    ("3 +", "incompleta"),
    ("(2 + 3", "paréntesis"),
    ("hola", "No entiendo"),
    ("raíz de -4", "negativo"),
    ("2 ^ 100000", "demasiado grande"),
])
def test_errores_claros(texto, mensaje):
    with pytest.raises(ErrorCalculo, match=mensaje):
        calcular(texto)


def test_no_usa_eval():
    # Si usara eval(), esto intentaría ejecutar código de Python.
    with pytest.raises(ErrorCalculo):
        tokenizar("__import__('os').getcwd()")


# ==========================================
# ¿ES UN CÁLCULO?
# ==========================================

@pytest.mark.parametrize("comando, operacion", [
    ("¿Cuánto es 3 + 4 × 2?", "3 + 4 × 2"),
    ("calcula (2+3)^2", "(2+3)^2"),
    ("3+4*2", "3+4*2"),
    ("qué sabes de perro", None),
    ("aprende [0,1] = 1", None),
    ("xor", None),
])
def test_extraer_operacion(comando, operacion):
    assert extraer_operacion(comando) == operacion


def test_entiende_el_menos_tipografico():
    # El que Hefesto usa al mostrar resultados: copiar y pegar debe funcionar.
    assert resultado("3 + 4 × 2 − 6 ÷ 3") == 9
    assert resultado("10 – 4") == 6
    assert extraer_operacion("8 − 3") == "8 − 3"