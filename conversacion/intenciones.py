"""
Intenciones: qué quieres hacer y con qué datos, aunque lo digas a tu manera.

    "crea una rutina llamada comprobación de estados, que revise los recursos, los errores y el entorno"
        → {"intencion": "crear_rutina",
           "nombre": "comprobación de estados",
           "pasos": "revisa los recursos, revisa los errores, revisa el entorno"}

    "oye, ¿qué sabes de los pingüinos?"
        → {"intencion": "definir", "concepto": "pingüinos"}

Funciones puras: texto entra, datos salen. Quién hace cada cosa lo
decide platica.py.

Truco de siempre: simple() quita acentos y mayúsculas SIN cambiar el
largo del texto, así que se busca en el texto simple y se recorta el
original (con sus acentos) en las mismas posiciones.
"""

import re

from minerva.planeador import simple, VERBOS
from conversacion.traductor import traducir


# ==========================================
# AYUDANTES
# ==========================================

MULETILLAS = ("oye ", "oiga ", "hey ", "hefesto ", "focus ", "porfa ", "por favor ", "a ver ", "mira ", "este ")

ARTICULOS = ("el ", "la ", "los ", "las ", "un ", "una ", "unos ", "unas ")


def limpiar(texto):
    """Quita muletillas del inicio y signos de las orillas: 'Oye, ¿qué es X?' → 'qué es X'"""
    texto = texto.strip()
    cambio = True
    while cambio:
        cambio = False
        texto = texto.strip(" ,.¿?¡!")
        for muletilla in MULETILLAS:
            # "oye ", "oye, " u "oye," → fuera
            encontrado = re.match(r"^" + re.escape(muletilla.strip()) + r"[\s,]+", simple(texto))
            if encontrado:
                texto = texto[encontrado.end():]
                cambio = True
    return texto.strip(" ,.¿?¡!")


def sin_articulo(texto):
    texto = texto.strip(" ,.¿?¡!\"'«»")
    for articulo in ARTICULOS:
        if simple(texto).startswith(articulo):
            return texto[len(articulo):].strip()
    return texto


def _despues(patron, texto):
    """Si el texto simple encaja con el patrón, devuelve los grupos recortados del original."""
    encontrado = re.match(patron, simple(texto))
    if not encontrado:
        return None
    return [texto[encontrado.start(i):encontrado.end(i)].strip(" ,.:\"'«»")
            if encontrado.group(i) is not None else None
            for i in range(1, (encontrado.lastindex or 0) + 1)]


# ==========================================
# PASOS DE UNA RUTINA DICHOS A TU MANERA
# ==========================================

# "que revise", "que hagas un respaldo" → la forma de orden que entiende MINERVA
A_ORDEN = {
    "revise": "revisa", "revises": "revisa", "revisar": "revisa",
    "cheque": "checa", "cheques": "checa", "checar": "checa",
    "mida": "mide", "midas": "mide", "medir": "mide",
    "calcule": "calcula", "calcules": "calcula", "calcular": "calcula",
    "investigue": "investiga", "investigues": "investiga", "investigar": "investiga",
    "defina": "define", "definas": "define", "definir": "define",
    "respalde": "respalda", "respaldes": "respalda", "respaldar": "respalda",
    "lea": "lee", "leas": "lee", "leer": "lee",
    "busque": "busca", "busques": "busca", "buscar": "busca",
    "haga": "haz", "hagas": "haz", "hacer": "haz",
}

VERBOS_DE_PASO = {"revisa", "checa", "mide", "calcula", "investiga", "define", "respalda",
                  "lee", "busca", "haz", "dime", "explicame", "resuelve", "averigua"}


def normalizar_pasos(texto, rutinas=()):
    """
    'revise los recursos, los errores y el entorno'
        → 'revisa los recursos, revisa los errores, revisa el entorno'

    - Cambia "revise/revisar/que revises" por "revisa".
    - Si un pedazo no trae verbo, usa el del pedazo anterior ("los errores" → "revisa los errores").
    - Respeta los nombres de rutinas y las partes con "si ..." (condiciones y plan B).
    """
    nombres = {simple(r) for r in rutinas}
    # Se parte en comas y en "y" (pero no en "y si falla", que es un plan B)
    pedazos = re.split(r",|\s+y\s+(?!si\s)", texto)
    verbo = None
    salida = []

    for pedazo in pedazos:
        pedazo = pedazo.strip(" .")
        if not pedazo:
            continue
        palabras = pedazo.split()

        # "que también revise", "luego cheque" → sin relleno
        while palabras and simple(palabras[0]) in ("que", "tambien", "luego", "despues", "y", "ademas"):
            palabras = palabras[1:]
        if not palabras:
            continue

        primera = simple(palabras[0])
        # "que haga un respaldo" → "haz un respaldo"; "que haga revisar X" → "revisa X"
        if primera in ("haga", "hagas") and len(palabras) > 1 and simple(palabras[1]) in A_ORDEN:
            palabras = palabras[1:]
            primera = simple(palabras[0])
        if primera in A_ORDEN:
            palabras[0] = A_ORDEN[primera]
            primera = palabras[0]

        pedazo = " ".join(palabras)
        es_rutina = simple(pedazo) in nombres
        es_condicion = primera == "si" or simple(pedazo).startswith(("si ", "y si "))

        if es_condicion:
            # "si hay errores revise los incidentes" → también aquí "revisa"
            pedazo = " ".join(A_ORDEN.get(simple(p), p) for p in pedazo.split())
        elif primera in VERBOS_DE_PASO or primera in VERBOS:
            verbo = primera
        elif not es_rutina and not es_condicion and verbo:
            pedazo = f"{verbo} {pedazo}"

        salida.append(pedazo)

    return ", ".join(salida)


# ==========================================
# INTENCIONES
# ==========================================

SI = {"si", "sí", "s", "va", "dale", "ok", "okay", "claro", "simon", "sale", "sí, hazlo", "hazlo",
      "si hazlo", "adelante", "correcto", "eso", "exacto", "de acuerdo"}
NO = {"no", "n", "nel", "nop", "mejor no", "cancela", "cancelar", "no gracias", "olvidalo", "dejalo"}


def es_si(texto):
    return simple(texto).strip(" .!¡") in {simple(s) for s in SI}


def es_no(texto):
    return simple(texto).strip(" .!¡") in {simple(n) for n in NO}


def entender(texto, rutinas=()):
    """
    Texto → {"intencion": ..., datos}. Si no entiende: {"intencion": "desconocida"}.
    'rutinas' son los nombres de las rutinas que existen (para reconocerlos).
    """
    original = texto
    texto = limpiar(texto)
    t = simple(texto)

    if not t:
        return {"intencion": "vacia"}

    # ---------- rutinas ----------
    crear = _despues(
        r"^(?:crea|creame|haz|hazme|arma|armame|genera|nueva|quiero)\s+(?:una\s+)?(?:nueva\s+)?rutina\s+"
        r"(?:llamada|que se llame|de nombre|con el nombre(?: de)?)?\s*(.+?)\s*[,:]?\s*"
        r"(?:que|para que|y que)\s+(.+)$", texto)
    if crear:
        nombre, pasos = crear
        return {"intencion": "crear_rutina", "nombre": nombre, "pasos": normalizar_pasos(pasos, rutinas)}

    cuando = _despues(
        r"^quiero que cuando (?:te )?diga\s+(.+?)\s*,?\s+((?:" + "|".join(A_ORDEN) + r"|"
        + "|".join(VERBOS_DE_PASO) + r")\b.+)$", texto)
    if cuando:
        nombre, pasos = cuando
        return {"intencion": "crear_rutina", "nombre": nombre, "pasos": normalizar_pasos(pasos, rutinas)}

    agregar = _despues(r"^(?:agrega|a[nñ]ade|suma|pon)\s+(?:a|en)\s+(?:la\s+)?rutina\s+(.+?)\s*,?\s+que\s+(?:tambien\s+)?(.+)$", texto)
    if agregar:
        nombre, pasos = agregar
        return {"intencion": "agregar_a_rutina", "nombre": nombre, "pasos": normalizar_pasos(pasos, rutinas)}

    borrar = _despues(r"^(?:borra|elimina|olvida|quita)\s+(?:la\s+)?rutina\s+(.+)$", texto)
    if borrar:
        return {"intencion": "borrar_rutina", "nombre": borrar[0]}

    if "rutina" in t and re.search(r"\b(que|cuales|mis|tengo|lista)\b", t):
        return {"intencion": "listar_rutinas"}

    # ---------- el creador ----------
    if re.match(r"^(soy spanky|soy tu creador|soy el creador|soy quien te creo|soy quien te esta creando)$", t):
        return {"intencion": "soy_creador"}

    if re.match(r"^(quien te creo|quien te hizo|quien es tu creador|quien te esta creando|quien te programo|"
                r"quien te esta desarrollando|quien te desarrollo)$", t):
        return {"intencion": "quien_te_creo"}

    if re.match(r"^(cierra sesion|cerrar sesion|bloquea(te)?|ya no soy yo|modo normal)$", t):
        return {"intencion": "cerrar_sesion"}

    if re.match(r"^(cambia (mi|la|tu) clave|nueva clave|cambiar (mi|la) clave)$", t):
        return {"intencion": "cambiar_clave"}

    # ---------- seguir el hilo ----------
    if re.match(r"^(?:otra vez|otra|de nuevo|hazlo (?:otra vez|de nuevo)|repite|repitelo|una vez mas|"
                r"y ahora|y ahorita|vuelve a hacerlo|again)$", t):
        return {"intencion": "otra_vez"}

    # ---------- tu forma de decir las cosas (frases.py) ----------
    frase = _despues(r"^cuando (?:te )?diga\s+(.+?)\s*,?\s*(?:quiero decir|me refiero a|significa|"
                     r"es como decir|es lo mismo que|hazme)\s+(.+)$", texto)
    if frase:
        return {"intencion": "ensenar_frase", "dicho": frase[0], "significa": frase[1]}

    olvida_frase = _despues(r"^(?:olvida|borra)\s+(?:la frase|lo que significa)\s+(.+)$", texto)
    if olvida_frase:
        return {"intencion": "olvidar_frase", "dicho": olvida_frase[0]}

    if re.match(r"^(que frases te ense[nñ]e|mis frases|que frases (?:sabes|conoces|te he ense[nñ]ado))$", t):
        return {"intencion": "listar_frases"}

    # ---------- reacciones cortas ----------
    if re.match(r"^((?:ja){2,}j?|(?:je){2,}|(?:ji){2,}|x+d+|lol|jsjs\w*|jajaj\w*)$", t.replace(" ", "")):
        return {"intencion": "risa"}

    if re.match(r"^(si|ok|okay|va|vale|sale|perfecto|excelente|genial|chido|bien|muy bien|listo|entendido|"
                r"orale|aja|ya veo|ah ok|ok gracias|va gracias|que bien|super|cool)$", t):
        return {"intencion": "acuerdo"}

    # ---------- de ti ----------
    nombre = _despues(r"^(?:me llamo|mi nombre es|llamame|soy)\s+([a-zñ ]{2,30})$", texto)
    if nombre:
        return {"intencion": "mi_nombre", "nombre": nombre[0]}

    gusto = _despues(r"^(?:me gusta|me gustan|me encanta|me encantan)\s+(.+)$", texto)
    if gusto:
        return {"intencion": "me_gusta", "gusto": gusto[0]}

    ya_no = _despues(r"^(?:ya no me gusta|ya no me gustan|olvida que me gusta|olvida que me gustan)\s+(.+)$", texto)
    if ya_no:
        return {"intencion": "ya_no_me_gusta", "gusto": ya_no[0]}

    if re.match(r"^(como me llamo|cual es mi nombre|sabes como me llamo|quien soy yo)$", t):
        return {"intencion": "cual_es_mi_nombre"}

    if re.match(r"^(que me gusta|que cosas me gustan|sabes que me gusta)$", t):
        return {"intencion": "que_me_gusta"}

    # ---------- plática ----------
    if re.match(r"^(hola|holi|buenas|buenos dias|buenas tardes|buenas noches|que onda|que tal|hey|saludos)\b", t) \
            and len(t.split()) <= 4 and not re.search(r"\b(es|sabes|puede)\b", t):
        return {"intencion": "saludo"}

    if re.match(r"^(adios|bye|nos vemos|hasta luego|hasta ma[nñ]ana|chao|me voy|salir|apagate)\b", t):
        return {"intencion": "despedida"}

    if re.match(r"^(gracias|muchas gracias|te lo agradezco|thanks|grax)\b", t):
        return {"intencion": "gracias"}

    if re.match(r"^(como estas|como andas|como te sientes|que tal estas|como vas|todo bien|estas bien)$", t):
        return {"intencion": "como_estas"}

    if re.match(r"^(quien eres|que eres|como te llamas|presentate)$", t):
        return {"intencion": "quien_eres"}

    if re.match(r"^(que puedes hacer|que sabes hacer|ayuda|ayudame|que haces|en que me ayudas)$", t):
        return {"intencion": "que_puedes_hacer"}

    # ---------- comandos de HEFESTO dichos a tu manera ----------
    # "¿dónde anda el rover?" → "rover estado"   (ver traductor.py)
    comando = traducir(texto)
    if comando:
        return {"intencion": "hefesto", **comando}

    # ---------- cuentas ----------
    cuenta = _despues(r"^(?:cuanto es|cuanto son|calcula|resuelve|cuanto da)\s+(.+)$", texto)
    if cuenta:
        return {"intencion": "calcular", "operacion": cuenta[0]}
    if re.fullmatch(r"[\d\s\.,+\-−–×x*/÷^()√]+", t) and re.search(r"\d", t) and re.search(r"[+\-−–×x*/÷^√]", t):
        return {"intencion": "calcular", "operacion": texto}

    # ---------- links ----------
    if re.search(r"(https?://|www\.)", t) or re.match(r"^(revisa|checa)\s+(este|el)\s+(link|enlace|mensaje)", t):
        return {"intencion": "revisar_links", "texto": texto}

    # ---------- de dónde sabe algo (fuentes) ----------
    de_donde = _despues(
        r"^(?:de donde sacaste|quien te dijo|como sabes|por que sabes|donde aprendiste|donde leiste|"
        r"de donde sabes|quien te ense[nñ]o|de donde aprendiste)\s+que\s+(.+)$", texto)
    if de_donde:
        return {"intencion": "de_donde", "frase": de_donde[0]}

    if re.match(r"^(?:y\s+)?(de donde lo sacaste|de donde sacaste eso|quien te lo dijo|quien te dijo eso|"
                r"como lo sabes|como sabes eso|por que lo sabes|de donde viene eso|cual es tu fuente|"
                r"quien te lo ense[nñ]o|donde lo aprendiste|donde lo leiste|y eso de donde)$", t):
        return {"intencion": "de_donde", "frase": None}      # sobre lo último que dije

    fuentes = _despues(
        r"^(?:(?:tus\s+)?fuentes|de donde sabes lo que sabes|de donde viene lo que sabes|"
        r"quien te ense[nñ]o|quienes te ense[nñ]aron|de donde aprendiste)\s+(?:del|de|sobre|lo de|acerca de)\s+(.+)$", texto)
    if fuentes:
        return {"intencion": "fuentes", "concepto": sin_articulo(fuentes[0])}

    # ---------- conocimiento ----------
    aprende = _despues(r"^(?:aprende que|apunta que|recuerda que|toma nota de que)\s+(.+)$", texto)
    if aprende:
        return {"intencion": "aprender", "frase": aprende[0]}

    definir = _despues(
        r"^(?:que sabes de|que sabes sobre|que es|que son|explicame que es|explicame|hablame de|hablame sobre|"
        r"que onda con|dime que es|define|investiga que es|investiga|que me dices de)\s+(.+)$", texto)
    if definir:
        return {"intencion": "definir", "concepto": sin_articulo(definir[0])}

    if "?" in original or "¿" in original:
        return {"intencion": "pregunta", "texto": texto}

    # ---------- tareas ----------
    tarea = _despues(r"^(?:encargate de|haz lo siguiente|ejecuta|corre|haz)\s*:?\s+(.+)$", texto)
    if tarea:
        return {"intencion": "tarea", "tarea": normalizar_pasos(tarea[0], rutinas)}

    if t in {simple(r) for r in rutinas}:
        return {"intencion": "tarea", "tarea": texto}

    # Puede ser una tarea dicha directo ("revisa los recursos y los errores")
    # o algo que me estás enseñando ("el tensor es un objeto matemático").
    return {"intencion": "libre", "texto": texto, "tarea": normalizar_pasos(texto, rutinas)}