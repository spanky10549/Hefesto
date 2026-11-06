import numpy as np
import os

from memoria.almacenamiento import (
    cargar_json,
    guardar_json,
    ErrorAlmacenamiento
)

from apollo.conocimiento import (
    cargar_diccionario,
    normalizar_concepto,
    normalizar_texto,
    normalizar_relacion,
    buscar_entrada,
    aprender_palabra,
    aprender_sinonimo,
    buscar_palabra,
    aprender_relacion,
    buscar_relaciones,
    buscar_camino,
    separar_origen_destino,
    extraer_relacion,
    RELACIONES_VALIDAS,
    existe_concepto,
    sugerir_concepto,
    olvidar_relacion,
    olvidar_categoria,
    olvidar_sinonimo,
    olvidar_concepto,
    extraer_relacion_con_negacion,
    ordenar_diccionario
)

from apollo.lenguaje import (
    formas_de_relacion,
    limpiar_concepto,
    expandir_contracciones,
    preguntas_de_relacion
)

from conversacion.contexto import aplicar_contexto, detectar_tema, crear_plantilla
from conversacion.estado import (
    cargar_estado,
    guardar_estado,
    olvidar_estado,
    describir_fecha
)

from apollo.razonamiento import (
    ancestros,
    relaciones_inferidas,
    relaciones_inversas,
    responder,
    SI,
    NO
)

# ==========================================
# FUNCIÓN DE ACTIVACIÓN
# ==========================================

def sigmoid(x):
    return 1 / (1 + np.exp(-x))


# ==========================================
# ARCHIVOS DE HEFESTO
# ==========================================

ARCHIVO_MEMORIA = "memoria.json"
ARCHIVO_DATOS = "datos_aprendizaje.json"

MEMORIA_INICIAL = {
    "identidad": {
        "nombre": "HEFESTO",
        "creador": "spanky"
    },
    "conocimientos": []
}

DATOS_INICIALES = {"datos": []}


def cargar_memoria():
    memoria = cargar_json(ARCHIVO_MEMORIA, MEMORIA_INICIAL)

    if not isinstance(memoria, dict) or not isinstance(
        memoria.get("conocimientos"), list
    ):
        raise ErrorAlmacenamiento(
            "La memoria no tiene la estructura esperada."
        )

    return memoria


def guardar_memoria(memoria):
    guardar_json(ARCHIVO_MEMORIA, memoria)


def cargar_datos_aprendizaje():
    datos = cargar_json(ARCHIVO_DATOS, DATOS_INICIALES)

    if not isinstance(datos, dict) or not isinstance(
        datos.get("datos"), list
    ):
        raise ErrorAlmacenamiento(
            "Los datos de aprendizaje no tienen la estructura esperada."
        )

    return datos


def guardar_datos_aprendizaje(datos):
    guardar_json(ARCHIVO_DATOS, datos)


# ==========================================
# CONOCIMIENTOS
# ==========================================

def aprender_conocimiento(tipo, tema, contenido):

    if not all(
        isinstance(valor, str) and valor.strip()
        for valor in (tipo, tema, contenido)
    ):
        print("HEFESTO: Los datos del conocimiento no son válidos.")
        return

    conocimiento = {
        "tipo": tipo.strip(),
        "tema": tema.strip(),
        "contenido": contenido.strip()
    }

    memoria = cargar_memoria()

    conocimientos = memoria.get("conocimientos", [])

    contenido_nuevo = normalizar_concepto(contenido)

    for existente in conocimientos:

        if not isinstance(existente, dict):
            continue

        contenido_existente = existente.get("contenido")

        if not isinstance(contenido_existente, str):
            continue

        if normalizar_concepto(contenido_existente) == contenido_nuevo:
            print("HEFESTO: Ese conocimiento ya existe.")
            return

    memoria["conocimientos"].append(conocimiento)

    guardar_memoria(memoria)

    print("HEFESTO: Conocimiento aprendido.")


# ==========================================
# CAMBIAR / ACTUALIZAR CONOCIMIENTO
# ==========================================

def actualizar_conocimiento(
    tipo,
    tema,
    contenido_nuevo,
    contenido_anterior
):
    memoria = cargar_memoria()

    for conocimiento in memoria.get("conocimientos", []):

        if not isinstance(conocimiento, dict):
            continue

        tipo_guardado = conocimiento.get("tipo", "")
        tema_guardado = conocimiento.get("tema", "")
        temas_guardados = conocimiento.get("temas", [])

        if isinstance(temas_guardados, str):
            temas_guardados = [temas_guardados]

        if not isinstance(temas_guardados, list):
            temas_guardados = []

        # Combinar el tema singular y los temas múltiples.
        temas = list(temas_guardados)

        if isinstance(tema_guardado, str) and tema_guardado:
            temas.append(tema_guardado)

        tema_normalizado = normalizar_concepto(tema)

        tema_encontrado = any(
            isinstance(t, str)
            and normalizar_concepto(t) == tema_normalizado
            for t in temas
        )

        contenido_guardado = conocimiento.get("contenido", "")

        if (
            isinstance(tipo_guardado, str)
            and normalizar_concepto(tipo_guardado)
                == normalizar_concepto(tipo)
            and tema_encontrado
            and isinstance(contenido_guardado, str)
            and normalizar_concepto(contenido_guardado)
                == normalizar_concepto(contenido_anterior)
        ):
            conocimiento["contenido"] = contenido_nuevo
            guardar_memoria(memoria)

            print("HEFESTO: Conocimiento actualizado.")
            return

    print("HEFESTO: No encontré ese conocimiento.")


# ==========================================
# TEMAS CONOCIDOS
# ==========================================

TEMAS = {

    "Focus": [
        "focus"
    ],

    "HEFESTO": [
        "hefesto"
    ],

    "Quantum Robotics": [
        "quantum",
        "quantum robotics"
    ],

    "Batería gravitacional": [
        "batería gravitacional",
        "bateria gravitacional"
    ],

    "Python": [
        "python"
    ],

    "Raspberry Pi": [
        "raspberry pi",
        "raspberry"
    ],

    "ESP32": [
        "esp32",
        "esp-wroom"
    ],

    "Arduino": [
        "arduino"
    ],

    "ROS": [
        "ros",
        "robot operating system"
    ],

    "Robótica": [
        "robótica",
        "robotica",
        "robot"
    ],

    "Programación": [
        "programación",
        "programacion",
        "código",
        "codigo",
        "programa",
        "programar",
        "programando",
        "programado",
        "programador",
        "programadores"
    ],

    "Inteligencia Artificial": [
        "inteligencia artificial",
        "ia",
        "machine learning",
        "aprendizaje automático",
        "aprendizaje automatico",
        "red neuronal"
    ],

    "Matemáticas": [
        "matemáticas",
        "matematicas",
        "matemática",
        "matematica"
    ],

    "Cálculo": [
        "cálculo",
        "calculo",
        "derivada",
        "derivadas",
        "integral",
        "integrales",
        "límite",
        "limite"
    ],

    "Física": [
        "física",
        "fisica",
        "fuerza",
        "velocidad",
        "aceleración",
        "aceleracion",
        "energía",
        "energia",
        "masa",
        "movimiento"
    ],

    "Electrónica": [
        "electrónica",
        "electronica",
        "voltaje",
        "corriente",
        "resistencia",
        "circuito",
        "circuitos",
        "amperaje",
        "potencia"
    ]
}


# ==========================================
# ANALIZAR CONOCIMIENTO
# ==========================================

def analizar_conocimiento(contenido):

    texto = contenido.lower()

    tipo = "sin_categoria"
    temas = []

    # =========================
    # CONSULTAR DICCIONARIO
    # =========================

    diccionario = cargar_diccionario()

    asociaciones_aprendidas = []

    for entrada in diccionario["palabras"]:

        palabra = entrada["palabra"].lower()

        if palabra in texto:

            for asociacion in entrada.get("asociaciones", []):

                if asociacion not in asociaciones_aprendidas:
                    asociaciones_aprendidas.append(asociacion)

    # =========================
    # AGREGAR TEMAS APRENDIDOS
    # =========================

    for asociacion in asociaciones_aprendidas:

        if asociacion not in temas:
            temas.append(asociacion)

    # =========================
    # DETECTAR TEMAS
    # =========================

    for nombre_tema, palabras in TEMAS.items():

        for palabra in palabras:

            if palabra in texto:
                temas.append(nombre_tema)
                break

    # =========================
    # DETECTAR TIPO
    # =========================

    palabras_hardware = [
        "cámara", "camara", "sensor", "raspberry", "esp32",
        "arduino", "motor", "motorreductor", "batería", "bateria",
        "pantalla", "display", "micrófono", "microfono", "altavoz",
        "bocina", "led", "botón", "boton", "cable", "resistencia",
        "capacitor", "transistor", "chip", "procesador", "placa",
        "microcontrolador", "servo", "encoder", "actuador",
        "relevador", "relay"
    ]

    palabras_software = [
        "python", "programa", "programación", "programacion",
        "código", "codigo", "software", "algoritmo", "función",
        "funcion", "variable", "clase", "script", "biblioteca",
        "librería", "libreria", "módulo", "modulo", "json",
        "numpy", "ros", "programando", "programado",
        "programador", "programadores"
    ]

    palabras_ia = [
        "inteligencia artificial", "ia", "neurona", "red neuronal",
        "machine learning", "aprendizaje automático",
        "aprendizaje automatico", "entrenamiento", "modelo",
        "predicción", "prediccion", "clasificación",
        "clasificacion", "dataset", "inferencia"
    ]

    palabras_fisica = [
        "voltaje", "tensión", "corriente", "amperaje", "amperios",
        "voltios", "resistencia", "potencia", "energía", "energia",
        "fuerza", "masa", "peso", "velocidad", "aceleración",
        "aceleracion", "distancia", "trabajo", "movimiento",
        "torque", "par", "frecuencia", "carga"
    ]

    palabras_matematicas = [
        "matemáticas", "matematicas", "ecuación", "ecuacion",
        "derivada", "integral", "límite", "limite", "vector",
        "matriz", "probabilidad", "estadística", "estadistica",
        "álgebra", "algebra", "geometría", "geometria",
        "trigonometría", "trigonometria"
    ]

    # =========================
    # ASIGNAR TIPO
    # =========================

    if any(palabra in texto for palabra in palabras_hardware):
        tipo = "hardware"

    elif any(palabra in texto for palabra in palabras_software):
        tipo = "software"

    elif any(palabra in texto for palabra in palabras_ia):
        tipo = "inteligencia_artificial"

    elif any(palabra in texto for palabra in palabras_fisica):
        tipo = "fisica_electronica"

    elif any(palabra in texto for palabra in palabras_matematicas):
        tipo = "matematicas"

    conocimiento = {
        "tipo": tipo,
        "temas": temas,
        "contenido": contenido
    }

    print("ANALIZADOR:", conocimiento)

    return conocimiento


# ==========================================
# GUARDAR CONOCIMIENTO
# ==========================================

def guardar_conocimiento(conocimiento):

    if not isinstance(conocimiento, dict):
        print("HEFESTO: Formato de conocimiento inválido.")
        return

    contenido_nuevo = conocimiento.get("contenido")

    if not isinstance(contenido_nuevo, str) or not contenido_nuevo.strip():
        print("HEFESTO: El contenido del conocimiento es inválido.")
        return

    memoria = cargar_memoria()
    conocimientos = memoria.get("conocimientos", [])

    contenido_normalizado = normalizar_concepto(contenido_nuevo)

    for existente in conocimientos:

        if not isinstance(existente, dict):
            continue

        contenido_existente = existente.get("contenido", "")

        if not isinstance(contenido_existente, str):
            continue

        if normalizar_concepto(contenido_existente) == contenido_normalizado:
            print("HEFESTO: Ese conocimiento ya existe.")
            return

    memoria["conocimientos"].append(conocimiento)
    guardar_memoria(memoria)

    print("HEFESTO: Conocimiento guardado.")


# ==========================================
# DATOS DE APRENDIZAJE
# ==========================================

def guardar_dato_aprendizaje(entrada, objetivo):

    datos = cargar_datos_aprendizaje()

    datos["datos"].append({
        "entrada": entrada,
        "objetivo": objetivo
    })

    guardar_datos_aprendizaje(datos)

    print("HEFESTO: Ejemplo de aprendizaje guardado.")


def preparar_datos_aprendizaje():

    datos = cargar_datos_aprendizaje()

    entradas = []
    objetivos = []

    for dato in datos["datos"]:
        entradas.append(dato["entrada"])
        objetivos.append(dato["objetivo"])

    return (
        np.array(entradas),
        np.array(objetivos)
    )


# ==========================================
# RED NEURONAL
# ==========================================

class RedNeuronal:

    # ======================================
    # CONSTRUCTOR
    # ======================================

    def __init__(self, entradas, ocultas, salidas, tasa):

        self.tasa = tasa

        self.pesos_ocultos = np.random.randn(ocultas, entradas)
        self.bias_ocultos = np.zeros(ocultas)

        self.pesos_salida = np.random.randn(salidas, ocultas)
        self.bias_salida = np.zeros(salidas)

    # ======================================
    # PREDICCIÓN
    # ======================================

    def predecir(self, entrada):

        entrada = np.array(entrada)

        resultado_oculto = (
            np.dot(entrada, self.pesos_ocultos.T)
            + self.bias_ocultos
        )

        activacion_oculta = sigmoid(resultado_oculto)

        resultado_salida = (
            np.dot(self.pesos_salida, activacion_oculta)
            + self.bias_salida
        )

        activacion_salida = sigmoid(resultado_salida)

        return activacion_salida

    # ======================================
    # APRENDER
    # ======================================

    def aprender(self, entradas, objetivos, epocas):

        print("Estoy aprendiendo...")

        self.crear_backup()

        error_final = self.entrenar(entradas, objetivos, epocas)

        self.guardar_modelo("hefesto_modelo_v2.npz")

        print("Error final:", error_final)
        print("He terminado de aprender.")

        return error_final

    # ======================================
    # ENTRENAMIENTO
    # ======================================

    def entrenar(self, entradas, objetivos, epocas):

        error_total = 0

        for epoca in range(epocas):

            error_total = 0

            for i in range(len(entradas)):

                entrada = entradas[i]
                objetivo = objetivos[i]

                # Propagación hacia adelante.
                resultado_oculto = (
                    np.dot(entrada, self.pesos_ocultos.T)
                    + self.bias_ocultos
                )

                activacion_oculta = sigmoid(resultado_oculto)

                resultado_salida = (
                    np.dot(self.pesos_salida, activacion_oculta)
                    + self.bias_salida
                )

                activacion_salida = sigmoid(resultado_salida)

                error = objetivo - activacion_salida

                error_total += np.sum(np.abs(error))

                # Retropropagación.
                delta_salida = activacion_salida - objetivo

                derivadas_ocultas = (
                    activacion_oculta
                    * (1 - activacion_oculta)
                )

                delta_oculta = (
                    self.pesos_salida.T @ delta_salida
                ) * derivadas_ocultas

                grad_pesos_salida = np.outer(
                    delta_salida,
                    activacion_oculta
                )
                grad_bias_salida = delta_salida

                grad_pesos_ocultos = np.outer(delta_oculta, entrada)
                grad_bias_ocultos = delta_oculta

                # Actualizar pesos.
                self.pesos_salida -= self.tasa * grad_pesos_salida
                self.bias_salida -= self.tasa * grad_bias_salida
                self.pesos_ocultos -= self.tasa * grad_pesos_ocultos
                self.bias_ocultos -= self.tasa * grad_bias_ocultos

            if epoca % 1000 == 0:
                print("Época:", epoca, "Error total:", error_total)

        return error_total

    # ======================================
    # EVALUACIÓN
    # ======================================

    def evaluar(self, entradas, objetivos):

        aciertos = 0

        for i in range(len(entradas)):

            prediccion = self.predecir(entradas[i])

            resultado = 1 if prediccion[0] >= 0.5 else 0

            print(
                entradas[i], "→", prediccion, "→", resultado,
                "→ objetivo:", objetivos[i]
            )

            if resultado == objetivos[i]:
                aciertos += 1

        precision = aciertos / len(entradas)

        print("\nHEFESTO: Evaluación completada.")
        print("Aciertos:", aciertos)
        print("Total:", len(entradas))
        print("Precisión:", precision * 100, "%")

    # ======================================
    # CALCULAR ERROR
    # ======================================

    def calcular_error(self, entradas, objetivos):

        errores = []

        for i in range(len(entradas)):

            prediccion = self.predecir(entradas[i])

            error = np.mean(np.abs(prediccion - objetivos[i]))

            errores.append(error)

        return np.mean(errores)

    # ======================================
    # GUARDAR MODELO
    # ======================================

    def guardar_modelo(self, archivo):

        np.savez(
            archivo,
            pesos_ocultos=self.pesos_ocultos,
            bias_ocultos=self.bias_ocultos,
            pesos_salida=self.pesos_salida,
            bias_salida=self.bias_salida
        )

        print("Modelo guardado correctamente.")

    # ======================================
    # CREAR BACKUP
    # ======================================

    def crear_backup(self):

        self.guardar_modelo("hefesto_modelo_v2_backup.npz")

        print("HEFESTO: Backup del modelo V2 creado.")

    # ======================================
    # CARGAR MODELO
    # ======================================

    def cargar_modelo(self, archivo):

        modelo = np.load(archivo)

        self.pesos_ocultos = modelo["pesos_ocultos"]
        self.bias_ocultos = modelo["bias_ocultos"]
        self.pesos_salida = modelo["pesos_salida"]
        self.bias_salida = modelo["bias_salida"]


# ==========================================
# DATOS XOR
# ==========================================

entradas = np.array([
    [0, 0],
    [0, 1],
    [1, 0],
    [1, 1]
])

objetivos = np.array([
    0,
    1,
    1,
    0
])


# ==========================================
# ENTENDER ERRORES DE ESCRITURA
# ==========================================

def resolver_concepto(texto):
    """
    Si Hefesto no conoce el concepto pero se parece a uno que sí,
    pregunta si era ese. Devuelve el concepto a usar.
    """

    if existe_concepto(texto):
        return texto

    sugerencia = sugerir_concepto(texto)

    if sugerencia is None:
        return texto

    respuesta = input(
        f"HEFESTO: No conozco '{texto}'. "
        f"¿Quisiste decir '{sugerencia}'? (s/n): "
    ).strip().lower()

    if respuesta == "s":
        return sugerencia

    return texto


# ==========================================
# APRENDER: CÓMO DECIRLO
# ==========================================
# APOLLO devuelve un resultado con un "estado"; aquí se traduce
# cada estado a una frase. Si mañana HEFESTO habla por voz o en
# una página web, solo cambia esta parte, no APOLLO.

def flecha(r):
    """'sensor → NO mide → humedad'"""
    no = "NO " if r.get("negada") else ""
    return f"{r['sujeto']} → {no}{r['relacion']} → {r['objeto']}"


MENSAJES = {
    # aprender_palabra
    "nueva": "Aprendí la palabra {palabra} y su asociación con {asociacion}.",
    "asociada": "Aprendí que {palabra} está relacionado con {asociacion}.",
    # aprender_sinonimo
    "aprendido": "Aprendí que '{sinonimo}' es sinónimo de '{palabra}'.",
    "ya_registrado": "'{sinonimo}' ya está registrado.",
    "desconocido": "No conozco el concepto '{palabra}'. Enséñamelo primero.",
    "iguales": "Ambos términos son iguales.",
    # aprender_relacion
    "aprendida": "Aprendí la relación {flecha}.",
    "relacion_invalida": "Todavía no reconozco la relación '{relacion}'. No la guardaré.",
    "mismo_concepto": "El sujeto y el objeto son iguales. Revisa esa relación.",
    # comunes
    "ya_sabia": "Ya lo sabía.",
    "vacio": "No puedo aprender términos vacíos.",
}


def anunciar(r):
    """Dice en voz de HEFESTO el resultado de aprender algo."""
    datos = dict(r)

    if "relacion" in r and "sujeto" in r:
        datos["flecha"] = flecha(r)

    plantilla = MENSAJES.get(r["estado"], "Listo ({estado}).")
    print("HEFESTO: " + plantilla.format(**datos))


def aprender_relacion_conversando(sujeto, relacion, objeto, negada=False):
    """
    Pide a APOLLO aprender una relación. Si hay una contradicción,
    pregunta al usuario y, si acepta, le pide a APOLLO reemplazar.
    """
    r = aprender_relacion(sujeto, relacion, objeto, negada)

    if r["estado"] != "contradiccion":
        anunciar(r)
        return

    print("HEFESTO: Esto contradice algo que ya sé:")

    for conflicto in r["conflictos"]:
        print(f"  {flecha(conflicto)}")

    if not confirmar(f"¿Lo cambio por {flecha(r)}?"):
        print("HEFESTO: Me quedo con lo que ya sabía.")
        return

    anunciar(aprender_relacion(sujeto, relacion, objeto, negada, reemplazar=True))


# ==========================================
# OLVIDAR
# ==========================================

SEPARADORES_SINONIMO = (
    " es sinónimo de ",
    " es sinonimo de ",
    " significa ",
    " quiere decir ",
    " equivale a ",
)


def confirmar(pregunta):
    """Pide confirmación (s/n). Se usa antes de borrar cosas grandes."""
    return input(f"HEFESTO: {pregunta} (s/n): ").strip().lower() == "s"


def olvidar_frase(frase):
    """
    Interpreta 'olvida que <frase>' y borra lo que corresponda:
    un sinónimo, una relación o una categoría.
    """

    # 1. ¿Es un sinónimo?
    for separador in SEPARADORES_SINONIMO:
        if separador in frase:
            a, b = frase.split(separador, 1)
            a, b = limpiar_concepto(a), limpiar_concepto(b)

            if olvidar_sinonimo(a, b):
                print(f"HEFESTO: Olvidé que '{a}' es sinónimo de '{b}'.")
            else:
                print(f"HEFESTO: No sabía que '{a}' fuera sinónimo de '{b}'.")
            return

    # 2. ¿Es una relación? (mide, usa, NO puede...)
    resultado = (
        extraer_relacion_con_negacion(frase)
        or negacion_de_categoria(frase)
    )

    if resultado:
        sujeto, relacion, objeto, negada = resultado
        no = "NO " if negada else ""

        if olvidar_relacion(sujeto, relacion, objeto, negada):
            print(f"HEFESTO: Olvidé que {sujeto} → {no}{relacion} → {objeto}.")
        else:
            print(
                f"HEFESTO: No tenía guardado que "
                f"{sujeto} → {no}{relacion} → {objeto}."
            )
        return

    # 3. ¿Es una categoría? (X es Y / X son Y)
    resultado = extraer_relacion(frase, incluir_es=True)

    if resultado:
        concepto, _, categoria = resultado

        if olvidar_categoria(concepto, categoria):
            print(f"HEFESTO: Olvidé que {concepto} es {categoria}.")
        else:
            print(f"HEFESTO: No tenía guardado que {concepto} es {categoria}.")
        return

    print(
        "HEFESTO: No entendí qué debo olvidar. "
        "Ejemplo: olvida que el sensor mide la humedad"
    )


def olvidar_todo_sobre(concepto):
    """Borra un concepto completo, pidiendo confirmación."""

    if not existe_concepto(concepto):
        print(f"HEFESTO: No sé nada sobre {concepto}.")
        return

    if not confirmar(
        f"¿Seguro que quieres que olvide TODO sobre {concepto}?"
    ):
        print("HEFESTO: No olvidé nada.")
        return

    nombre, menciones = olvidar_concepto(concepto)

    if nombre is None:
        print(f"HEFESTO: No tenía información propia de {concepto}.")
        return

    print(f"HEFESTO: Olvidé todo lo que sabía de {nombre}.")

    if menciones:
        print(
            f"HEFESTO: Ojo: otros conceptos todavía lo mencionan "
            f"en {menciones} relación(es). Pregunta "
            f"'qué sabes de {nombre}' para verlas."
        )


def olvidar_recuerdo(texto):
    """Borra recuerdos de la memoria que contengan el texto."""

    memoria = cargar_memoria()
    buscado = normalizar_texto(texto)

    coincidencias = [
        conocimiento
        for conocimiento in memoria["conocimientos"]
        if isinstance(conocimiento, dict)
        and buscado in normalizar_texto(str(conocimiento.get("contenido", "")))
    ]

    if not coincidencias:
        print(f"HEFESTO: No tengo recuerdos que digan '{texto}'.")
        return

    if len(coincidencias) == 1:
        elegido = coincidencias[0]

        if not confirmar(f"¿Olvido el recuerdo '{elegido['contenido']}'?"):
            print("HEFESTO: No olvidé nada.")
            return

    else:
        print("HEFESTO: Encontré varios recuerdos:")

        for numero, conocimiento in enumerate(coincidencias, start=1):
            print(f"  {numero}. {conocimiento['contenido']}")

        respuesta = input(
            "HEFESTO: ¿Cuál olvido? (número, o Enter para ninguno): "
        ).strip()

        if not respuesta.isdigit() or not 1 <= int(respuesta) <= len(coincidencias):
            print("HEFESTO: No olvidé nada.")
            return

        elegido = coincidencias[int(respuesta) - 1]

    memoria["conocimientos"].remove(elegido)
    guardar_memoria(memoria)

    print(f"HEFESTO: Olvidé el recuerdo '{elegido['contenido']}'.")


# ==========================================
# RAZONAMIENTO: CÓMO PRESENTARLO
# ==========================================

PALABRAS_DE_PREGUNTA = (
    "qué", "que", "quién", "quien", "cómo", "como", "cuál", "cual",
    "dónde", "donde", "cuándo", "cuando", "por qué", "por que",
    "con qué", "con que", "dime"
)


# Formas de preguntar por cada relación (las genera APOLLO).
PREGUNTAS_DE_RELACION = [
    (inicio + " ", relacion) for inicio, relacion in preguntas_de_relacion()
]


def negacion_de_categoria(frase):
    """
    'el pingüino no es un mamífero' → ('pingüino', 'es', 'mamífero', True).
    Solo para negaciones: 'X es Y' se sigue guardando como asociación.
    """
    resultado = extraer_relacion_con_negacion(frase, incluir_es=True)

    if resultado and resultado[1] == "es" and resultado[3]:
        return resultado

    return None


def mostrar_cadena(cadena, sangria="  "):
    """Imprime los pasos de un razonamiento: a → relación → b."""
    for paso in cadena:
        print(
            f"{sangria}{paso['origen']} → "
            f"{paso['relacion']} → {paso['destino']}"
        )


def parsear_pregunta_inversa(texto):
    """
    'quién mide la temperatura' → ('mide', 'temperatura')
    'qué cosa produce calor'    → ('produce', 'calor')
    Devuelve None si no es una pregunta de ese tipo.
    """
    texto = texto.replace("¿", "").replace("?", "").strip()

    for inicio in ("quién ", "quien ", "qué cosa ", "que cosa "):

        if not texto.startswith(inicio):
            continue

        resto = texto[len(inicio):]

        for forma, oficial in formas_de_relacion(incluir_es=True):
            if resto.startswith(forma + " "):
                objeto = limpiar_concepto(resto[len(forma):])
                if objeto:
                    return oficial, objeto

    return None


def parsear_pregunta_si_no(comando):
    """
    '¿la raspberry pi necesita electricidad?'
        → ('raspberry pi', 'necesita', 'electricidad')
    Solo si parece pregunta y no empieza con qué/quién/cómo...
    """
    if "?" not in comando and "¿" not in comando:
        return None

    texto = normalizar_texto(comando.replace("¿", "").replace("?", ""))

    if texto.startswith(PALABRAS_DE_PREGUNTA):
        return None

    return extraer_relacion(texto, incluir_es=True)


# ==========================================
# AYUDA
# ==========================================

AYUDA = """
HEFESTO: Esto es lo que sé hacer:

  APRENDER
    aprende que <algo> es <descripción>
        aprende que la raspberry pi es una computadora
    aprende que <algo> <relación> <algo>
        aprende que los sensores miden la temperatura
    aprende que <algo> es sinónimo de <otro nombre>
        aprende que raspberry pi es sinónimo de rpi
    aprende que <algo> no <relación> <algo>
        aprende que el pingüino no puede volar
    recuerda <una idea>
        recuerda Focus tendrá sensores de temperatura

  PREGUNTAR
    qué sabes de <algo>
    qué mide / controla / usa / necesita / produce ... <algo>
    con qué se comunica <algo>
    camino <origen> <destino>
        camino raspberry pi temperatura
    recuerdos

  CONVERSACIÓN (recuerdo de qué hablamos)
    qué sabes del pingüino
    ¿y puede nadar?          → entiendo que hablas del pingüino
    ¿y qué tiene?
    qué más sabes de él
    ¿y el gorrión también?   → repite tu última pregunta con el gorrión
    ¿y del sensor?           → lo mismo, con el sensor
    de qué hablamos
    cambiemos de tema        → olvida el tema actual
    (me acuerdo del tema aunque me apagues)

  OLVIDAR Y CORREGIR
    olvida que <algo> <relación> <algo>
        olvida que el sensor mide la humedad
    olvida que <algo> es <categoría>
    olvida que <algo> es sinónimo de <otro nombre>
    olvida todo sobre <algo>
    olvida el recuerdo <texto>
    Para corregir: olvida lo incorrecto y aprende lo correcto.

  RAZONAR
    ¿<algo> <relación> <algo>?      pregunta de sí o no
        ¿la raspberry pi necesita electricidad?
        ¿la raspberry pi es una máquina?
    quién <relación> <algo>          relación inversa
        quién mide la temperatura

  RED NEURONAL
    xor                 ver cómo resuelve XOR
    aprende [0,1] = 1   guardar un ejemplo de entrenamiento
    entrenar            aprender de los ejemplos guardados

  SISTEMA
    ordena tu diccionario   une repetidos y pasa conceptos a singular
    estado, quién eres, ayuda, salir

  Relaciones que entiendo:
    {relaciones}
"""


def mostrar_ayuda():
    relaciones = ", ".join(sorted(RELACIONES_VALIDAS))
    print(AYUDA.format(relaciones=relaciones))


# ==========================================
# INICIAR HEFESTO
# ==========================================

def iniciar_hefesto():

    print("\n================================")
    print("            HEFESTO")
    print("================================")

    # ======================================
    # CREAR / CARGAR HEFESTO V2
    # ======================================

    hefesto = RedNeuronal(
        entradas=2,
        ocultas=4,
        salidas=1,
        tasa=0.1
    )

    if os.path.exists("hefesto_modelo_v2.npz"):

        print("\n=== MODELO V2 ENCONTRADO ===")

        hefesto.cargar_modelo("hefesto_modelo_v2.npz")

    else:

        print("\n=== CREANDO MODELO V2 ===")

        hefesto.entrenar(entradas, objetivos, 10000)

        hefesto.guardar_modelo("hefesto_modelo_v2.npz")

    # ======================================
    # EVALUAR HEFESTO
    # ======================================

    print("\n=== INICIANDO HEFESTO ===")
    print("\n=== PRUEBA XOR ===")

    hefesto.evaluar(entradas, objetivos)

    error = hefesto.calcular_error(entradas, objetivos)

    print("Error promedio:", error)
    print("HEFESTO ONLINE.")
    print("Modelo cargado correctamente.")
    print("Escribe 'ayuda' para ver lo que sé hacer, o 'salir' para apagarme.")

    # ======================================
    # CARGAR MEMORIA
    # ======================================

    memoria = cargar_memoria()

    # ======================================
    # INTERFAZ PRINCIPAL
    # ======================================

    # De qué estamos hablando (para entender "¿y puede nadar?")
    # y la última pregunta (para entender "¿y el gorrión también?").
    # Se recuerdan de la sesión anterior.
    estado = cargar_estado()
    tema_actual = estado["tema"]
    ultima_plantilla = estado["plantilla"]

    if tema_actual:
        cuando = describir_fecha(estado["fecha"])
        cuando = f" ({cuando})" if cuando else ""
        print(
            f"HEFESTO: La última vez{cuando} hablábamos de {tema_actual}. "
            f"Podemos seguir, o dime 'cambiemos de tema'."
        )

    while True:

        try:
            comando = input("\nTú: ").strip()

        except (KeyboardInterrupt, EOFError):
            print("\nHEFESTO: Apagando sistema...")
            break

        if not comando:
            continue

        # ======================================
        # CONTEXTO DE LA CONVERSACIÓN
        # ======================================

        comando, uso_contexto = aplicar_contexto(comando, tema_actual, ultima_plantilla)

        if uso_contexto is None:
            print(
                "HEFESTO: ¿De qué estamos hablando? "
                "Todavía no sé a qué te refieres."
            )
            continue

        if uso_contexto:
            print(f"HEFESTO: (Entiendo: {comando})")

        nuevo_tema = detectar_tema(comando)

        if nuevo_tema:
            ultima_plantilla = crear_plantilla(comando, nuevo_tema) or ultima_plantilla

            # Si viene con error de escritura, recordar la forma correcta.
            if not existe_concepto(nuevo_tema):
                nuevo_tema = sugerir_concepto(nuevo_tema) or nuevo_tema
            tema_actual = nuevo_tema
            guardar_estado(tema_actual, ultima_plantilla)

        comando_normalizado = expandir_contracciones(normalizar_texto(comando))

        pregunta_inversa = parsear_pregunta_inversa(comando_normalizado)
        pregunta_si_no = parsear_pregunta_si_no(comando)

        # ======================================
        # SALIR
        # ======================================

        if comando_normalizado == "salir":

            print("HEFESTO: Apagando sistema...")
            break

        # ======================================
        # ESTADO
        # ======================================

        elif comando_normalizado == "estado":

            print(
                "HEFESTO: Todos mis sistemas "
                "principales están funcionando."
            )
            print("HEFESTO: Mi modelo está cargado.")
            print("HEFESTO: Mi red neuronal está disponible.")

        # ======================================
        # ORDENAR EL DICCIONARIO
        # ======================================

        elif comando_normalizado in (
            "ordena tu diccionario", "ordena el diccionario", "ordénate", "ordenate"
        ):

            r = ordenar_diccionario()

            if not r["unidas"] and not r["renombradas"]:
                print("HEFESTO: Mi diccionario ya estaba en orden.")
            else:
                print("HEFESTO: Listo, ordené mi diccionario.")

                if r["unidas"]:
                    print(f"  Uní {r['unidas']} concepto(s) repetido(s).")

                for antes, despues in r["renombradas"]:
                    print(f"  {antes} → {despues}")

        # ======================================
        # CAMBIAR DE TEMA
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip() in (
            "cambiemos de tema", "cambia de tema", "olvida el tema",
            "nuevo tema", "otro tema"
        ):

            tema_actual = None
            ultima_plantilla = None
            olvidar_estado()
            print("HEFESTO: Va, empecemos de cero. ¿De qué quieres hablar?")

        # ======================================
        # DE QUÉ HABLAMOS
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip() in (
            "de qué hablamos", "de que hablamos", "de qué estamos hablando",
            "de que estamos hablando"
        ):

            if tema_actual:
                print(f"HEFESTO: Estamos hablando de {tema_actual}.")
            else:
                print("HEFESTO: Todavía no hemos hablado de nada en particular.")

        # ======================================
        # AYUDA
        # ======================================

        elif comando_normalizado in ("ayuda", "help", "?"):

            mostrar_ayuda()

        # ======================================
        # PROBAR XOR
        # ======================================

        elif comando_normalizado == "xor":

            print("\nHEFESTO analiza:")
            print("[0,0] →", hefesto.predecir([0, 0]))
            print("[0,1] →", hefesto.predecir([0, 1]))
            print("[1,0] →", hefesto.predecir([1, 0]))
            print("[1,1] →", hefesto.predecir([1, 1]))

        # ======================================
        # OLVIDAR
        # ======================================

        elif comando_normalizado.startswith(("olvida todo sobre ", "olvida todo de ")):

            concepto = comando_normalizado.split(" ", 3)[3]
            olvidar_todo_sobre(resolver_concepto(limpiar_concepto(concepto)))

        elif comando_normalizado.startswith("olvida el recuerdo "):

            olvidar_recuerdo(comando[len("olvida el recuerdo "):].strip())

        elif comando_normalizado.startswith("olvida que "):

            olvidar_frase(comando_normalizado[len("olvida que "):])

        # ======================================
        # RECORDAR CONOCIMIENTO
        # ======================================

        elif comando_normalizado.startswith("recuerda"):

            contenido = comando[len("recuerda"):].strip()

            if not contenido:
                print("HEFESTO: ¿Qué quieres que recuerde?")
                continue

            conocimiento = analizar_conocimiento(contenido)
            guardar_conocimiento(conocimiento)

        # ======================================
        # ACTUALIZAR CONOCIMIENTO
        # ======================================

        elif comando_normalizado.startswith("actualiza |"):

            partes = comando.split("|")

            if len(partes) != 5:

                print("HEFESTO: Formato incorrecto.")
                print(
                    "Usa: actualiza | tipo | tema | "
                    "contenido_anterior | contenido_nuevo"
                )
                continue

            tipo = partes[1].strip()
            tema = partes[2].strip()
            contenido_anterior = partes[3].strip()
            contenido_nuevo = partes[4].strip()

            actualizar_conocimiento(
                tipo,
                tema,
                contenido_nuevo,
                contenido_anterior
            )

        # ======================================
        # APRENDER PALABRAS Y RELACIONES
        # ======================================

        elif comando_normalizado.startswith("aprende que "):

            contenido = comando_normalizado[
                len("aprende que "):
            ].strip()

            # ======================================
            # APRENDIZAJE DE SINÓNIMOS
            # ======================================

            separadores_sinonimos = (
                " es sinónimo de ",
                " es sinonimo de ",
                " significa ",
                " quiere decir ",
                " equivale a ",
            )

            separador = next(
                (
                    s for s in separadores_sinonimos
                    if s in contenido
                ),
                None
            )

            if separador is not None:

                palabra, sinonimo = contenido.split(separador, 1)

                anunciar(aprender_sinonimo(palabra.strip(), sinonimo.strip()))

            else:

                # ======================================
                # APRENDIZAJE DE RELACIONES
                # ======================================

                # Primero relaciones normales (mide, puede...),
                # luego "X no es Y". Ambas entienden el "no".
                resultado = (
                    extraer_relacion_con_negacion(contenido)
                    or negacion_de_categoria(contenido)
                )

                if resultado:

                    sujeto, relacion, objeto, negada = resultado

                    aprender_relacion_conversando(sujeto, relacion, objeto, negada)

                else:

                    # ======================================
                    # APRENDIZAJE DE ASOCIACIONES
                    # ======================================

                    # "X es Y" o, en plural, "X son Y".
                    partes = []

                    for conector in (" es ", " son "):
                        if conector in contenido:
                            partes = contenido.split(conector, 1)
                            break

                    if len(partes) != 2:

                        print(
                            "HEFESTO: No pude identificar "
                            "una asociación o relación."
                        )
                        continue

                    palabra = partes[0].strip()
                    asociacion = partes[1].strip()

                    anunciar(aprender_palabra(palabra, asociacion))

        # ======================================
        # RELACIONES INVERSAS: quién mide X
        # ======================================

        elif pregunta_inversa is not None:

            verbo, objeto = pregunta_inversa
            objeto = resolver_concepto(objeto)

            sujetos = [
                inversa["sujeto"]
                for inversa in relaciones_inversas(objeto)
                if inversa["relacion"] == verbo
            ]

            if sujetos:
                print("HEFESTO: Esto es lo que sé:")
                for sujeto in sujetos:
                    print(f"  {sujeto} → {verbo} → {objeto}")
            else:
                print(f"HEFESTO: No conozco nada que {verbo} {objeto}.")

        # ======================================
        # CONSULTAR RELACIONES
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip().startswith(
            tuple(prefijo for prefijo, _ in PREGUNTAS_DE_RELACION)
        ):

            pregunta = (
                comando_normalizado
                .replace("¿", "")
                .replace("?", "")
                .strip()
            )

            prefijos = PREGUNTAS_DE_RELACION

            verbo_encontrado = None
            sujeto = ""

            for prefijo, verbo in prefijos:

                if pregunta.startswith(prefijo):

                    verbo_encontrado = verbo
                    sujeto = pregunta[len(prefijo):].strip()

                    for articulo in (
                        "el ", "la ", "los ", "las ",
                        "un ", "una ", "unos ", "unas "
                    ):
                        if sujeto.startswith(articulo):
                            sujeto = sujeto[len(articulo):].strip()
                            break

                    break

            if verbo_encontrado is None:

                print(
                    "HEFESTO: Todavía no reconozco "
                    "la relación de esa pregunta."
                )

            else:

                sujeto = resolver_concepto(sujeto)

                relaciones = buscar_relaciones(sujeto)

                encontradas = [
                    relacion
                    for relacion in relaciones
                    if normalizar_relacion(
                        relacion.get("relacion", "")
                    ) == normalizar_relacion(verbo_encontrado)
                ]

                if encontradas:

                    print("HEFESTO: Esto es lo que sé:")

                    for relacion in encontradas:
                        print(
                            f"  {sujeto} → {verbo_encontrado} → "
                            f"{relacion['objetivo']}"
                        )

                else:

                    verbo_oficial = normalizar_relacion(verbo_encontrado)

                    deducidas = [
                        inferida
                        for inferida in relaciones_inferidas(sujeto)
                        if inferida["relacion"] == verbo_oficial
                    ]

                    inversas = [
                        inversa["sujeto"]
                        for inversa in relaciones_inversas(sujeto)
                        if inversa["relacion"] == verbo_oficial
                    ]

                    if deducidas:

                        print("HEFESTO: Nadie me lo dijo, pero lo deduzco:")

                        for inferida in deducidas:
                            print(
                                f"- {sujeto} {verbo_oficial} "
                                f"{inferida['objetivo']}, porque:"
                            )
                            mostrar_cadena(inferida["cadena"], "    ")

                    elif inversas:

                        print(
                            f"HEFESTO: No sé qué {verbo_oficial} {sujeto}, "
                            f"pero sé esto sobre {sujeto}:"
                        )

                        for otro in inversas:
                            print(f"  {otro} → {verbo_oficial} → {sujeto}")

                    else:

                        negadas = [
                            relacion
                            for relacion in buscar_relaciones(sujeto, negadas=True)
                            if normalizar_relacion(relacion["relacion"]) == verbo_oficial
                        ]

                        if negadas:
                            print(
                                f"HEFESTO: No sé qué {verbo_oficial} {sujeto}, "
                                f"pero sé lo que NO:"
                            )
                            for relacion in negadas:
                                print(
                                    f"  {sujeto} → NO {verbo_oficial} → "
                                    f"{relacion['objetivo']}"
                                )
                        else:
                            print(
                                f"HEFESTO: No conozco relaciones de tipo "
                                f"'{verbo_encontrado}' para {sujeto}."
                            )

        # ======================================
        # BUSCAR CAMINO ENTRE CONCEPTOS
        # ======================================

        elif comando_normalizado.startswith("camino "):

            texto = comando_normalizado[len("camino "):].strip()

            origen, destino = separar_origen_destino(texto)

            if not origen or not destino:
                print(
                    "HEFESTO: Indica el origen y el destino. "
                    "Ejemplo: camino raspberry pi temperatura "
                    "(o: camino raspberry pi | temperatura)."
                )

            else:

                origen = resolver_concepto(origen)
                destino = resolver_concepto(destino)

                camino = buscar_camino(origen, destino)

                if camino is None:

                    print(
                        f"HEFESTO: No encontré un camino entre "
                        f"{origen} y {destino}."
                    )

                elif not camino:

                    print(
                        "HEFESTO: El origen y el destino "
                        "son el mismo concepto."
                    )

                else:

                    print("HEFESTO: Encontré esta conexión:")

                    for paso in camino:
                        print(
                            f"  {paso['origen']} "
                            f"→ {paso['relacion']} → "
                            f"{paso['destino']}"
                        )

        # ======================================
        # CONSULTAR CONOCIMIENTO
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip().startswith(
            ("qué sabes de ", "que sabes de ")
        ):

            pregunta = (
                comando_normalizado
                .replace("¿", "")
                .replace("?", "")
                .strip()
            )

            if pregunta.startswith("qué sabes de "):
                palabra = pregunta[len("qué sabes de "):].strip()
            else:
                palabra = pregunta[len("que sabes de "):].strip()

            palabra = resolver_concepto(limpiar_concepto(palabra))

            palabra_normalizada = normalizar_concepto(palabra)

            asociaciones = buscar_palabra(palabra)
            relaciones = buscar_relaciones(palabra)

            entrada = buscar_entrada(palabra)

            sinonimos = (
                entrada.get("sinonimos", [])
                if entrada is not None
                else []
            )

            memoria = cargar_memoria()
            conocimientos = memoria.get("conocimientos", [])
            conocimientos_encontrados = []

            for conocimiento in conocimientos:

                if not isinstance(conocimiento, dict):
                    continue

                tema = conocimiento.get("tema", "")
                temas = conocimiento.get("temas", [])

                if isinstance(temas, str):
                    temas = [temas]

                if not isinstance(temas, list):
                    temas = []

                if isinstance(tema, str) and tema:
                    temas = temas + [tema]

                contenido_memoria = conocimiento.get("contenido", "")

                if not isinstance(contenido_memoria, str):
                    contenido_memoria = ""

                coincide_tema = any(
                    isinstance(t, str)
                    and normalizar_concepto(t) == palabra_normalizada
                    for t in temas
                )

                coincide_contenido = (
                    palabra_normalizada in normalizar_concepto(
                        contenido_memoria
                    )
                )

                if coincide_tema or coincide_contenido:
                    conocimientos_encontrados.append(conocimiento)

            encontrado = False

            if asociaciones:

                encontrado = True
                print(f"HEFESTO: {palabra} está relacionado con:")

                for asociacion in asociaciones:
                    print("-", asociacion)

            if sinonimos:

                encontrado = True
                nombre_principal = entrada.get("palabra", palabra)

                if normalizar_concepto(nombre_principal) != palabra_normalizada:
                    print(
                        f"HEFESTO: '{palabra}' es otro nombre "
                        f"para '{nombre_principal}'."
                    )

                print(
                    f"HEFESTO: Sinónimos conocidos de "
                    f"{nombre_principal}:"
                )

                for sinonimo in sinonimos:
                    print("-", sinonimo)

            if relaciones:

                encontrado = True
                print(f"HEFESTO: Relaciones conocidas de {palabra}:")

                for relacion in relaciones:
                    print(
                        f"- {relacion['relacion']} "
                        f"→ {relacion['objetivo']}"
                    )

            negaciones = buscar_relaciones(palabra, negadas=True)

            if negaciones:

                encontrado = True
                print(f"HEFESTO: Sé que {palabra} NO:")

                for relacion in negaciones:
                    print(
                        f"- {relacion['relacion']} "
                        f"→ {relacion['objetivo']}"
                    )

            if conocimientos_encontrados:

                encontrado = True
                print(
                    f"HEFESTO: Esto es lo que recuerdo sobre {palabra}:"
                )

                for conocimiento in conocimientos_encontrados:
                    print(
                        f"- [{conocimiento.get('tipo', 'sin tipo')}] "
                        f"{conocimiento.get('contenido', '')}"
                    )

            categorias = ancestros(palabra)
            deducidas = relaciones_inferidas(palabra)
            inversas = relaciones_inversas(palabra)

            # Las categorías directas ya salen como asociaciones;
            # aquí solo mostramos las deducidas.
            categorias_deducidas = [
                (categoria, cadena)
                for categoria, cadena in categorias
                if len(cadena) > 1
            ]

            if categorias_deducidas:

                encontrado = True
                print(f"HEFESTO: Por deducción, {palabra} también es:")

                for categoria, cadena in categorias_deducidas:
                    via = cadena[-1]["origen"]
                    print(f"- {categoria} (porque es {via})")

            if deducidas:

                encontrado = True
                print(f"HEFESTO: Además deduzco que {palabra}:")

                for inferida in deducidas:
                    via = inferida["cadena"][-1]["origen"]
                    print(
                        f"- {inferida['relacion']} → {inferida['objetivo']} "
                        f"(porque es {via})"
                    )

            if inversas:

                encontrado = True
                print(f"HEFESTO: Lo que se relaciona con {palabra}:")

                for inversa in inversas:
                    print(
                        f"- {inversa['sujeto']} → "
                        f"{inversa['relacion']} → {palabra}"
                    )

            if not encontrado:

                print(
                    f"HEFESTO: Todavía no encuentro información "
                    f"sobre {palabra}."
                )

        # ======================================
        # APRENDER DATOS PARA LA RED NEURONAL
        # ======================================

        elif comando_normalizado.startswith("aprende "):

            try:

                datos = comando[len("aprende "):]
                entrada_texto, objetivo_texto = datos.split("=", 1)

                entrada_texto = entrada_texto.strip().strip("[]")
                objetivo_texto = objetivo_texto.strip()

                entrada = [
                    int(valor.strip())
                    for valor in entrada_texto.split(",")
                ]

                objetivo = int(objetivo_texto)

                guardar_dato_aprendizaje(entrada, objetivo)

            except (ValueError, IndexError):

                print(
                    "HEFESTO: No pude interpretar ese dato. "
                    "Usa el formato: aprende [0,1] = 1"
                )

        # ======================================
        # ENTRENAR
        # ======================================

        elif comando_normalizado == "entrenar":

            (
                entradas_aprendizaje,
                objetivos_aprendizaje
            ) = preparar_datos_aprendizaje()

            if len(entradas_aprendizaje) == 0:

                print("HEFESTO: No tengo datos de aprendizaje.")

            else:

                print("HEFESTO: Voy a aprender de mis datos.")

                hefesto.aprender(
                    entradas_aprendizaje,
                    objetivos_aprendizaje,
                    5000
                )

        # ======================================
        # MOSTRAR RECUERDOS
        # ======================================

        elif comando_normalizado == "recuerdos":

            memoria = cargar_memoria()

            print("\nYo recuerdo:")

            for conocimiento in memoria.get("conocimientos", []):
                print("-", conocimiento)

        # ======================================
        # IDENTIDAD
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip() in (
            "quien eres",
            "quién eres"
        ):

            identidad = memoria.get("identidad", {})

            print(
                f"Yo soy {identidad.get('nombre', 'HEFESTO')}, "
                "el sistema de inteligencia para Focus."
            )

            print(
                f"Mi creador es "
                f"{identidad.get('creador', 'no especificado')}."
            )

        # ======================================
        # PREGUNTAS DE SÍ O NO
        # ======================================

        elif pregunta_si_no is not None:

            sujeto, verbo, objeto = pregunta_si_no

            sujeto = resolver_concepto(sujeto)
            objeto = resolver_concepto(objeto)

            respuesta, cadena = responder(sujeto, verbo, objeto)

            if respuesta == SI:
                inicio = "Sí"
            elif respuesta == NO:
                inicio = "No"
            else:
                inicio = None

            if inicio is None:
                print(
                    "HEFESTO: No lo sé. No tengo información "
                    "que lo confirme ni que lo niegue."
                )
            elif len(cadena) == 1:
                print(f"HEFESTO: {inicio}. Me lo enseñaste:")
                mostrar_cadena(cadena)
            else:
                print(f"HEFESTO: {inicio}. Nadie me lo dijo, pero lo deduje así:")
                mostrar_cadena(cadena)

        else:

            print(
                "HEFESTO: Todavía no sé procesar ese comando. "
                "Escribe 'ayuda' para ver lo que sé hacer."
            )


if __name__ == "__main__":
    try:
        iniciar_hefesto()
    except ErrorAlmacenamiento as error:
        print(f"HEFESTO: Tengo un problema con mis archivos: {error}")