"""
MINERVA — Planeador.

Convierte una tarea escrita en español en una lista de pasos:

    "investiga qué es una raspberry pi, calcula 5 × 35 y revisa los recursos"

    1. apollo       → definir   {"concepto": "raspberry pi"}
    2. calculadora  → calcular  {"operacion": "5 × 35"}
    3. artemis      → estado    {}

Funciona con reglas: cada regla dice con qué palabras empieza una
parte de la tarea y a qué inteligencia le toca. No sabe si esas
inteligencias existen; eso lo revisa MINERVA (servicio.py).

Funciones puras: reciben texto y devuelven datos.
"""

import re
import unicodedata


# ==========================================
# TEXTO SIMPLE PARA COMPARAR
# ==========================================

def simple(texto):
    """
    'Investiga ¿QUÉ es?' → 'investiga  que es '

    Quita acentos y signos, y pasa a minúsculas, PERO conserva el largo
    del texto: cada letra se cambia por otra, nunca se borra. Así una
    posición en el texto simple es la misma en el original, y se puede
    recortar el original (con sus acentos) donde se encontró algo.
    """
    resultado = []

    for letra in texto.lower():
        if letra == "ñ":
            resultado.append(letra)
        elif letra in "¿?¡!":
            resultado.append(" ")
        else:
            resultado.append(unicodedata.normalize("NFD", letra)[0])

    return "".join(resultado)


ARTICULOS = ("el ", "la ", "los ", "las ", "un ", "una ", "unos ", "unas ")


def quitar_articulo(texto):
    """'una raspberry pi' → 'raspberry pi'"""
    texto = texto.strip()
    for articulo in ARTICULOS:
        if simple(texto).startswith(articulo):
            return texto[len(articulo):].strip()
    return texto


# ==========================================
# DIVIDIR LA TAREA
# ==========================================

# Palabras con las que empieza cada parte de una tarea.
VERBOS = (
    "investiga", "investigar", "averigua", "averiguar", "define", "definir",
    "busca", "buscar", "dime", "explicame", "que es", "que son",
    "calcula", "calcular", "resuelve", "resolver", "cuanto es", "cuanto son",
    "revisa", "revisar", "checa", "checar", "mide", "medir", "que paso",
    "respalda", "respaldar", "haz un respaldo", "lee los sensores",
)

# Lo que sobra en las orillas de cada parte: "¿Qué es X?" → "Qué es X"
SOBRANTES = " .¿?¡!"

CONECTORES = ("y luego ", "luego ", "despues ", "y despues ", "primero ", "tambien ", "por favor ", "y ")

# " y " seguido de un verbo de tarea: "calcula 5 + 3 y revisa..." se divide,
# pero "define agua y hielo" o "calcula 2 y 3" no.
_Y_ANTES_DE_VERBO = re.compile(
    r"\s+y\s+(?=(?:luego\s+|despues\s+)?(?:" + "|".join(VERBOS) + r")\b)"
)


def _cortes(texto_simple):
    """Las posiciones (inicio, fin) de cada separador encontrado."""
    cortes = [(m.start(), m.end()) for m in re.finditer(r"[,;]", texto_simple)]
    cortes += [(m.start(), m.end()) for m in _Y_ANTES_DE_VERBO.finditer(texto_simple)]
    return sorted(cortes)


def dividir_tarea(texto):
    """
    'investiga qué es X, calcula 2 + 2 y luego revisa los recursos'
        → ['investiga qué es X', 'calcula 2 + 2', 'revisa los recursos']
    """
    texto_simple = simple(texto)
    partes, inicio = [], 0

    for corte_inicio, corte_fin in _cortes(texto_simple):
        partes.append(texto[inicio:corte_inicio])
        inicio = corte_fin
    partes.append(texto[inicio:])

    limpias = []
    for parte in partes:
        parte = parte.strip(SOBRANTES)
        # Quitar "luego", "y después"... del inicio
        cambio = True
        while cambio:
            cambio = False
            for conector in CONECTORES:
                if simple(parte).startswith(conector):
                    parte = parte[len(conector):].strip(SOBRANTES)
                    cambio = True
        if parte:
            limpias.append(parte)

    return limpias


# ==========================================
# INTERPRETAR CADA PARTE
# ==========================================

def _despues_de(prefijos, parte):
    """Si 'parte' empieza con algún prefijo, devuelve lo que sigue (original)."""
    parte_simple = simple(parte)
    for prefijo in sorted(prefijos, key=len, reverse=True):
        if parte_simple == prefijo or parte_simple.startswith(prefijo + " "):
            return parte[len(prefijo):].strip(" ¿?¡!:")
    return None


PREFIJOS_DEFINIR = (
    "investiga que es", "investiga que son", "investiga sobre", "investiga",
    "investigar que es", "investigar que son", "investigar sobre", "investigar",
    "averigua que es", "averiguar que es", "define", "definir",
    "busca informacion sobre", "busca informacion de",
    "buscar informacion sobre", "buscar informacion de",
    "dime que es", "explicame que es", "que es", "que son",
)

PREFIJOS_CALCULAR = (
    "calcula", "calcular", "resuelve", "resolver", "cuanto es", "cuanto son",
)

VERBOS_REVISAR = ("revisa", "revisar", "checa", "checar", "mide", "medir")


# "... y guárdalo como piezas" / "..., guárdalo como 'piezas'"
_GUARDAR = re.compile(
    r"[\s,]+(?:y\s+)?gu[aá]rd(?:a|alo|ala|ar)\s+(?:el resultado\s+)?como\s+[\"'«]?([a-zñáéíóúü_][\wñáéíóúü ]*?)[\"'»]?\s*$",
    re.IGNORECASE,
)


def separar_guardado(parte):
    """
    'calcula 5 × 35 y guárdalo como piezas' → ('calcula 5 × 35', 'piezas')
    'calcula 5 × 35'                        → ('calcula 5 × 35', None)
    """
    encontrado = _GUARDAR.search(parte)
    if not encontrado:
        return parte, None
    return parte[:encontrado.start()], " ".join(encontrado.group(1).lower().split())


def interpretar(parte):
    """
    Una parte de la tarea → un paso, o None si no la entiende.
        {"para": "apollo", "accion": "definir", "datos": {"concepto": "..."}}
    Si termina con "guárdalo como X", el paso lleva "guardar_como": "x".
    """
    parte, guardar_como = separar_guardado(parte.strip(SOBRANTES))
    paso = _interpretar(parte)
    if paso is not None and guardar_como:
        paso["guardar_como"] = guardar_como
    return paso


def _interpretar(parte):
    parte = parte.strip(SOBRANTES)
    parte_simple = simple(parte)

    # Calcular va antes que definir: "cuánto es" no debe tomarse como "qué es"
    operacion = _despues_de(PREFIJOS_CALCULAR, parte)
    if operacion:
        return {"para": "calculadora", "accion": "calcular", "datos": {"operacion": operacion}}

    # "revisa los recursos", "checa cómo está la compu", "revisa los errores"
    palabras = parte_simple.split()
    if palabras and palabras[0] in VERBOS_REVISAR:
        if any(clave in parte_simple for clave in ("incidente", "falla")):
            return {"para": "hades", "accion": "incidentes", "datos": {"abiertos": True}}
        if any(clave in parte_simple for clave in ("error", "registro", "problema")):
            return {"para": "tabris", "accion": "resumen", "datos": {"dia": "hoy"}}
        if any(clave in parte_simple for clave in ("recurso", "compu", "memoria", "ram", "disco", "bateria")):
            return {"para": "artemis", "accion": "estado", "datos": {}}
        if any(clave in parte_simple for clave in ("entorno", "sensor", "cuarto")):
            return {"para": "eter", "accion": "entorno", "datos": {"actualizar": True}}
        if any(clave in parte_simple for clave in ("seguridad", "sospechos", "hackeo")):
            return {"para": "poseidon", "accion": "reporte", "datos": {}}

    if parte_simple.strip() in ("entorno", "lee los sensores"):
        return {"para": "eter", "accion": "entorno", "datos": {"actualizar": True}}

    if parte_simple.strip() in ("respalda", "respaldar", "haz un respaldo", "respalda todo"):
        return {"para": "eleuthia", "accion": "respaldar", "datos": {}}

    if parte_simple.strip().startswith("que paso"):
        return {"para": "tabris", "accion": "resumen", "datos": {"dia": "hoy"}}

    concepto = _despues_de(PREFIJOS_DEFINIR, parte)
    if concepto:
        return {"para": "apollo", "accion": "definir", "datos": {"concepto": quitar_articulo(concepto)}}

    return None


# ==========================================
# RUTINAS (tareas que la persona le enseña)
# ==========================================

PREFIJOS_RUTINA = ("haz la rutina ", "ejecuta la rutina ", "corre la rutina ", "la rutina ", "rutina ")

# Una rutina puede usar otras, pero no infinitamente.
MAX_PROFUNDIDAD = 5


def nombre_de_rutina(texto):
    """'Haz la rutina «Checa todo»' → 'checa todo' (para comparar)."""
    texto = " ".join(simple(texto).strip(" .\"'«»").split())
    for prefijo in PREFIJOS_RUTINA:
        if texto.startswith(prefijo):
            texto = texto[len(prefijo):]
            break
    return texto.strip(" \"'«»")


def expandir(parte, rutinas, camino=()):
    """
    Una parte de la tarea → lista de (descripción, paso o None).
    Si la parte es una rutina, se cambia por sus pasos (y si alguno es
    otra rutina, también se expande).

    'camino' son las rutinas que se están expandiendo ahorita: si una
    aparece dos veces, es un círculo (A usa B y B usa A) y se detiene.
    """
    nombre = nombre_de_rutina(parte)

    if nombre in rutinas:
        if nombre in camino or len(camino) >= MAX_PROFUNDIDAD:
            return [(parte, None)]
        resultado = []
        for descripcion, paso in procesar(rutinas[nombre]["pasos"], rutinas, camino + (nombre,)):
            # "[checa todo] revisa los recursos": se nota de qué rutina vino
            resultado.append((f"[{rutinas[nombre]['nombre']}] {descripcion}", paso))
        return resultado

    return [(parte, interpretar(parte))]


def procesar(partes, rutinas, camino=()):
    """
    Las partes de una tarea (o de una rutina) → [(descripción, paso o None)].

    Además de los pasos normales entiende:
        "si piezas > 100, calcula X"   condición para el paso que sigue
        "calcula X si piezas > 100"    condición al final
        "define X y si falla calcula Y" plan B del paso anterior
        "si falla, detente"             si falla el anterior, no seguir
    """
    # Se importa aquí porque condiciones.py también usa este archivo.
    from minerva.condiciones import partir_plan_b, es_plan_b, es_detenerse, separar_condicion

    salida = []
    pendiente = None      # condición escrita sola: "si piezas > 100," aplica a lo que sigue
    plan_b_pendiente = False   # "si falla," solo: lo que sigue es el plan B

    for parte_completa in partes:
        for parte in partir_plan_b(parte_completa):

            alternativa = es_plan_b(parte)

            # "..., si falla, detente": la coma separó "si falla" de lo que sigue
            if alternativa == "":
                plan_b_pendiente = True
                continue
            if plan_b_pendiente:
                plan_b_pendiente = False
                alternativa = parte.strip(" ,.")

            if alternativa is not None:
                anteriores = [paso for _, paso in salida if paso is not None]
                if not anteriores:
                    salida.append((parte, None))
                elif es_detenerse(alternativa):
                    anteriores[-1]["si_falla"] = "detener"
                else:
                    paso_b = interpretar(alternativa)
                    if paso_b is None:
                        salida.append((parte, None))
                    else:
                        anteriores[-1]["si_falla"] = "plan b"
                        anteriores[-1]["alternativa"] = {**paso_b, "descripcion": alternativa}
                continue

            condicion, resto = separar_condicion(parte, [r["nombre"] for r in rutinas.values()])
            if condicion and not resto.strip():
                pendiente = condicion
                continue

            condicion = condicion or pendiente
            pendiente = None

            for descripcion, paso in expandir(resto, rutinas, camino):
                if paso is not None:
                    paso.setdefault("si_falla", "continuar")
                    if condicion:
                        paso["condicion"] = condicion
                salida.append((descripcion, paso))

    if pendiente:
        salida.append((f"si {pendiente['texto']}", None))   # una condición sin nada después
    if plan_b_pendiente:
        salida.append(("si falla", None))                    # "si falla" sin nada después

    return salida


def planear(tarea, rutinas=None):
    """
    La tarea completa → plan con pasos numerados y lo que no se entendió.
    'rutinas' son las que la persona le enseñó: {nombre: {"nombre", "pasos"}}.
    """
    rutinas = rutinas or {}
    pasos, no_entendidos = [], []

    for descripcion, paso in procesar(dividir_tarea(tarea), rutinas):
        if paso is None:
            no_entendidos.append(descripcion)
            continue
        pasos.append({"numero": len(pasos) + 1, "descripcion": descripcion, **paso})

    return {"tarea": tarea, "pasos": pasos, "no_entendidos": no_entendidos}