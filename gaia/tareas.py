"""
GAIA — Ejecución de planes.

MINERVA dice qué hacer y en qué orden; GAIA reparte cada paso a quien
le toca, en orden, y junta los resultados para que HEFESTO los integre.

    resultado = ejecutar_plan(gaia, plan)
    resultado["resultados"] → [{"numero": 1, "estado": "ok", "datos": {...}}, ...]

Si un paso falla:
    si_falla = "continuar"  sigue con los demás (lo normal)
    si_falla = "detener"    los pasos que faltaban quedan "pendiente"

Los pasos que MINERVA marcó con aviso (nadie puede hacerlos) se
"omiten" en vez de mandarse a fallar.

Un paso puede usar lo que dio otro:
    "calcula 5 × 35 y guárdalo como piezas, calcula piezas × 2"
    "calcula 5 × 35 y luego calcula el resultado + 1"
GAIA guarda el valor de cada paso y lo pone en el texto del siguiente.
"""

import re
from fractions import Fraction

from gaia.mensajes import OK, crear_orden, crear_evento


OMITIDO = "omitido"
PENDIENTE = "pendiente"
SALTADO = "saltado"       # tenía una condición que no se cumplió (y eso está bien)


# ==========================================
# USAR EL RESULTADO DE OTRO PASO
# ==========================================

# El "valor" de cada tipo de paso: lo que se guarda con "guárdalo como"
# y lo que significa "el resultado" o "eso" en el paso siguiente.
VALORES = {
    ("calculadora", "calcular"): lambda d: d["resultado"],                 # "175", "1/3"
    ("apollo", "definir"): lambda d: (d["categorias"] or [None])[0],        # pingüino → "ave"
    ("artemis", "estado"): lambda d: str(round(d["ram"]["disponible"] / (1024 * 1024))),  # MB libres
    ("tabris", "resumen"): lambda d: str(d["errores"]),
}

# Algunos pasos responden bien aunque no lograron lo que se pedía:
# APOLLO contesta "todavía no sé qué es tensor". Para el plan B eso cuenta como falla.
LOGRADO = {
    ("apollo", "definir"): lambda d: d.get("conocido", True),
}

_ANTERIOR = re.compile(r"\b(?:el resultado|eso)\b", re.IGNORECASE)


class SinValor(Exception):
    """Un paso usa "el resultado" o un nombre que todavía no tiene valor."""


def valor_de(paso, datos):
    """El valor principal de lo que devolvió un paso, o None."""
    obtener = VALORES.get((paso["para"], paso["accion"]))
    if obtener is None:
        return None
    try:
        valor = obtener(datos)
    except (KeyError, TypeError, IndexError):
        return None
    return None if valor is None else str(valor)


def _en_texto(valor, para_calcular):
    """Un valor como '1/3' se mete entre paréntesis en una cuenta: 2 × (1/3), no 2 × 1/3."""
    if para_calcular:
        try:
            Fraction(valor)
            return f"({valor})" if "/" in valor or valor.startswith("-") else valor
        except (ValueError, ZeroDivisionError):
            pass
    return valor


def sustituir(datos, guardados, anterior, para_calcular=False):
    """
    Cambia "el resultado"/"eso" por el valor del paso anterior, y cada nombre
    guardado por su valor, en todos los textos de 'datos'.
    """
    if isinstance(datos, dict):
        return {k: sustituir(v, guardados, anterior, para_calcular) for k, v in datos.items()}
    if isinstance(datos, list):
        return [sustituir(v, guardados, anterior, para_calcular) for v in datos]
    if not isinstance(datos, str):
        return datos

    texto = datos
    if _ANTERIOR.search(texto):
        if anterior is None:
            raise SinValor("pidió \"el resultado\", pero el paso anterior no dejó ninguno")
        texto = _ANTERIOR.sub(lambda m: _en_texto(anterior, para_calcular), texto)

    # Los nombres largos primero: "piezas grandes" antes que "piezas"
    for nombre in sorted(guardados, key=len, reverse=True):
        patron = re.compile(r"(?<![\wñáéíóú])" + re.escape(nombre) + r"(?![\wñáéíóú])", re.IGNORECASE)
        texto = patron.sub(lambda m, n=nombre: _en_texto(guardados[n], para_calcular), texto)

    return texto


def _hacer(gaia, de, plan, paso, resultado, guardados, anterior):
    """
    Manda un paso (con los valores ya puestos) y llena 'resultado'.
    Devuelve el nuevo "anterior" (el valor que dejó, o el de antes).
    """
    try:
        datos = sustituir(paso["datos"], guardados, anterior,
                          para_calcular=paso["para"] == "calculadora")
    except SinValor as error:
        resultado["estado"] = "rechazado"
        resultado["detalle"] = str(error)
        return anterior

    orden = crear_orden(
        de, paso["para"], paso["accion"], datos,
        objetivo=plan["tarea"],
        si_falla=paso.get("si_falla"),
    )
    respuesta = gaia.enviar(orden)

    resultado["estado"] = respuesta["estado"]
    resultado["datos"] = respuesta["datos"]
    resultado["detalle"] = respuesta.get("detalle")

    if respuesta["estado"] != OK:
        return anterior

    revisar = LOGRADO.get((paso["para"], paso["accion"]))
    if revisar is not None and not revisar(respuesta["datos"]):
        resultado["logrado"] = False
        return anterior

    valor = valor_de(paso, respuesta["datos"])
    if valor is None:
        if paso.get("guardar_como"):
            resultado["detalle"] = f"no dejó un valor para guardar como \"{paso['guardar_como']}\""
        return anterior

    if paso.get("guardar_como"):
        guardados[paso["guardar_como"]] = valor
        resultado["guardado"] = {"nombre": paso["guardar_como"], "valor": valor}
    return valor


# ==========================================
# CONDICIONES
# ==========================================

# Datos del sistema que se pueden usar en una condición, y quién los sabe.
# "si la ram está arriba de 90" → ARTEMIS; "si hay errores" → TABRIS.
DATOS_DEL_SISTEMA = [
    (("ram", "memoria"), "artemis", "estado", {}, lambda d: d["ram"]["porcentaje"]),
    (("disco",), "artemis", "estado", {}, lambda d: d["disco"]["porcentaje"]),
    (("cpu", "procesador"), "artemis", "estado", {}, lambda d: d["cpu"]["porcentaje"]),
    (("bateria",), "artemis", "estado", {}, lambda d: d["bateria"]["porcentaje"]),
    (("error",), "tabris", "resumen", {"dia": "hoy"}, lambda d: d["errores"]),
    (("incidente",), "hades", "incidentes", {"abiertos": True}, lambda d: len(d["incidentes"])),
]

OPERADORES = {
    ">": lambda a, b: a > b, "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
    "=": lambda a, b: a == b, "!=": lambda a, b: a != b,
}


def _simple(texto):
    import unicodedata
    texto = unicodedata.normalize("NFD", str(texto).lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def _numero(texto):
    try:
        return Fraction(str(texto).strip().strip("()"))
    except (ValueError, ZeroDivisionError):
        return None


def valor_de_condicion(lado, guardados, anterior, gaia, de, literal=False):
    """
    Lo que vale un lado de la condición: un número, "el resultado",
    algo guardado o un dato del sistema. Lanza SinValor si no se sabe.
    """
    numero = _numero(lado)
    if numero is not None:
        return numero

    texto = _simple(lado)
    sin_articulo = texto.split(" ", 1)[1] if texto.split(" ")[0] in ("el", "la", "los", "las") and " " in texto else texto

    if _ANTERIOR.fullmatch(texto):
        if anterior is None:
            raise SinValor("la condición usa \"el resultado\", pero el paso anterior no dejó ninguno")
        valor = anterior
    elif any(_simple(n) == sin_articulo for n in guardados):
        valor = next(v for n, v in guardados.items() if _simple(n) == sin_articulo)
    else:
        for claves, para, accion, datos, sacar in DATOS_DEL_SISTEMA:
            if any(clave in texto for clave in claves):
                r = gaia.pedir(de, para, accion, **datos)
                if r["estado"] != OK:
                    raise SinValor(f"no pude saber {lado}: {para.upper()} no contestó")
                try:
                    return Fraction(str(sacar(r["datos"])))
                except (KeyError, TypeError, ValueError):
                    raise SinValor(f"{para.upper()} no sabe {lado}")
        if literal:
            return texto        # lado derecho: "si el resultado es igual a ave"
        raise SinValor(f"no sé cuánto vale \"{lado}\"")

    numero = _numero(valor)
    return numero if numero is not None else _simple(valor)


def cumple(condicion, guardados, anterior, gaia, de="gaia"):
    """(se_cumple, texto que lo explica). Lanza SinValor si no se puede saber."""
    izq = valor_de_condicion(condicion["izq"], guardados, anterior, gaia, de)
    der = valor_de_condicion(condicion["der"], guardados, anterior, gaia, de, literal=True)

    if isinstance(izq, Fraction) != isinstance(der, Fraction):
        if condicion["op"] not in ("=", "!="):
            raise SinValor(f"no puedo comparar \"{condicion['izq']}\" con \"{condicion['der']}\"")
        izq, der = str(izq), str(der)

    resultado = OPERADORES[condicion["op"]](izq, der)
    if isinstance(izq, Fraction):
        mostrado = str(izq.numerator) if izq.denominator == 1 else f"{float(izq):g}"
    else:
        mostrado = izq
    return resultado, f"{condicion['texto']} (vale {mostrado})"


def ejecutar_plan(gaia, plan, de="hefesto", al_terminar_paso=None):
    """
    Ejecuta los pasos del plan uno por uno.

    'al_terminar_paso(resultado)' es opcional: se llama después de cada
    paso, para ir mostrando el avance sin esperar a que acabe todo.
    """
    gaia.publicar(crear_evento(gaia.nombre, "tarea_iniciada", {
        "tarea": plan["tarea"], "pasos": len(plan["pasos"])
    }))

    resultados = []
    detenido = False
    guardados = {}        # {"piezas": "175"}
    anterior = None       # el valor del último paso que dejó uno

    for paso in plan["pasos"]:

        resultado = {
            "numero": paso["numero"],
            "descripcion": paso["descripcion"],
            "para": paso["para"],
            "accion": paso["accion"],
            "datos": {},
            "detalle": None,
        }

        if detenido:
            resultado["estado"] = PENDIENTE

        elif paso.get("aviso"):
            resultado["estado"] = OMITIDO
            resultado["detalle"] = paso["aviso"]

        else:
            # ¿Tiene condición? Si no se cumple, se salta (y eso está bien).
            se_hace = True
            if paso.get("condicion"):
                try:
                    se_hace, explicacion = cumple(paso["condicion"], guardados, anterior, gaia, de)
                    resultado["condicion"] = explicacion
                    if not se_hace:
                        resultado["estado"] = SALTADO
                        resultado["detalle"] = f"no se cumplió que {explicacion}"
                except SinValor as error:
                    se_hace = False
                    resultado["estado"] = "rechazado"
                    resultado["detalle"] = f"no pude revisar la condición: {error}"

            if se_hace:
                anterior = _hacer(gaia, de, plan, paso, resultado, guardados, anterior)

                # Plan B: si el paso falló y hay alternativa, se hace la alternativa
                no_lo_logro = resultado["estado"] != OK or resultado.get("logrado") is False
                if no_lo_logro and paso.get("alternativa"):
                    alternativa = {**paso["alternativa"], "si_falla": "continuar"}
                    plan_b = {"para": alternativa["para"], "accion": alternativa["accion"],
                              "descripcion": alternativa["descripcion"], "datos": {}, "detalle": None}
                    anterior = _hacer(gaia, de, plan, alternativa, plan_b, guardados, anterior)
                    plan_b["fallo_original"] = resultado["detalle"]
                    resultado["plan_b"] = plan_b

            fallo = resultado["estado"] not in (OK, SALTADO) and not (
                resultado.get("plan_b") and resultado["plan_b"]["estado"] == OK
            )
            if fallo and paso.get("si_falla") == "detener":
                detenido = True

        resultados.append(resultado)

        if al_terminar_paso is not None:
            al_terminar_paso(resultado)

    completada = all(
        r["estado"] in (OK, SALTADO) or (r.get("plan_b") and r["plan_b"]["estado"] == OK)
        for r in resultados
    )

    gaia.publicar(crear_evento(gaia.nombre, "tarea_terminada", {
        "tarea": plan["tarea"],
        "completada": completada,
        "bien": sum(1 for r in resultados if r["estado"] in (OK, SALTADO)
                    or (r.get("plan_b") and r["plan_b"]["estado"] == OK)),
        "total": len(resultados),
    }))

    return {"tarea": plan["tarea"], "completada": completada, "resultados": resultados,
            "guardados": guardados}