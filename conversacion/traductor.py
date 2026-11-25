"""
Traductor: de cómo hablas a los comandos exactos de HEFESTO.

HEFESTO entiende comandos fijos ("rover ve a 3 4", "respalda"...).
FOCUS te deja decirlo a tu manera y aquí se traduce:

    "¿dónde anda el rover?"            → "rover estado"
    "manda el rover a 3, 4"            → "rover ve a 3 4"
    "haz una copia de seguridad"       → "respalda"
    "activa el micrófono"              → "autoriza ruido"
    "marca la 8 como terminada"        → "marca 8 como existe"

Cada regla es (patrón, plantilla). El patrón se busca en el texto
simple (sin acentos ni mayúsculas); los grupos se recortan del texto
original, así "lee Notas.txt" no se vuelve "notas.txt".

traducir(texto) → {"comando": ..., "delicado": bool} o None.

"delicado" = borra, olvida o reemplaza algo. FOCUS pregunta antes de
hacerlo, y si ya tienes clave de creador, solo tú puedes.
"""

import re

from minerva.planeador import simple


# ==========================================
# NOMBRES QUE SE DICEN DE VARIAS FORMAS
# ==========================================

SENSORES = {
    "ruido": "ruido", "microfono": "ruido", "el microfono": "ruido", "el ruido": "ruido",
    "sensor de ruido": "ruido", "el sensor de ruido": "ruido",
    "wifi": "wifi", "el wifi": "wifi", "la senal": "wifi", "la senal del wifi": "wifi",
    "sensor de wifi": "wifi", "el sensor de wifi": "wifi", "internet": "wifi",
    "temperatura": "temp_cpu", "la temperatura": "temp_cpu", "temp_cpu": "temp_cpu",
    "sensor de temperatura": "temp_cpu", "el sensor de temperatura": "temp_cpu",
    "la temperatura del procesador": "temp_cpu", "la temperatura de la cpu": "temp_cpu",
}

ESTADOS = {
    "existe": "existe", "lista": "existe", "listo": "existe", "hecha": "existe", "hecho": "existe",
    "terminada": "existe", "terminado": "existe", "completa": "existe", "completada": "existe",
    "ya existe": "existe", "funcionando": "existe",
    "a medias": "a medias", "en proceso": "a medias", "empezada": "a medias", "empezado": "a medias",
    "en progreso": "a medias", "medio hecha": "a medias",
    "falta": "falta", "pendiente": "falta", "no existe": "falta", "por hacer": "falta",
}

# Comandos que borran, olvidan o reemplazan algo.
DELICADOS = ("olvida ", "restaura ", "desprotege ", "revoca permisos", "quita la capacidad",
             "quita el sitio", "olvida la rutina")


def _clave(texto):
    """Para buscar en SENSORES y ESTADOS: sin acentos y con la ñ como n."""
    return simple(texto).replace("ñ", "n").strip()


# De esos, los que HEFESTO ya pregunta solo ("¿Volver a ...? (sí / no)"):
# FOCUS no vuelve a preguntar, para no preguntar dos veces.
HEFESTO_PREGUNTA = ("restaura ", "olvida todo sobre ", "olvida todo de ", "olvida el recuerdo ")


def es_delicado(comando):
    return simple(comando).startswith(DELICADOS)


def hefesto_pregunta(comando):
    return simple(comando).startswith(HEFESTO_PREGUNTA)


# ==========================================
# LAS REGLAS
# ==========================================
#
# Se revisan en orden; gana la primera que encaje con TODO el texto.
# La plantilla puede usar {1}, {2}... (los grupos) o ser una función.

NUM = r"#?(\d+)"
COORD = r"\(?\s*(-?\d+)\s*[, ]\s*(?:y\s+)?(-?\d+)\s*\)?"
VER = r"(?:muestrame|ense[nñ]ame|dame|dime|quiero ver|ver|muestra|ense[nñ]a|abre|checa|revisa)"
QUE = r"(?:que|cuales)"

REGLAS = [
    # ---------- ROVER ----------
    (r"(?:conecta|conectate a|conectate con|busca|enciende|prende)\s+(?:el|al)\s+rover", "conecta el rover"),
    (r"(?:manda|lleva|mueve|envia|dile al rover que vaya)\s+(?:(?:el|al)\s+rover\s+)?(?:a|al punto|a la posicion|hacia)\s+" + COORD,
     "rover ve a {1} {2}"),
    (r"rover,?\s+(?:ve|vete|ir|muevete|anda|camina)\s+(?:a|al punto|hacia)\s+" + COORD, "rover ve a {1} {2}"),
    (r"(?:donde (?:esta|anda|quedo)|como (?:esta|va|anda)|que (?:hace|onda con)|estado del)\s+(?:el\s+)?rover", "rover estado"),
    (r"(?:recarga|carga)\s+(?:la bateria del|el)\s+rover|el rover necesita (?:bateria|carga)", "rover recarga"),

    # ---------- SENSORES Y ENTORNO (ÉTER) ----------
    (QUE + r"\s+sensores\s+(?:tengo|hay|tienes|detectaste|encontraste)|(?:" + VER + r"\s+)?(?:los|mis)\s+sensores", "sensores"),
    (r"(?:autoriza|activa|enciende|prende|usa)\s+(?:el\s+)?(?:sensor\s+(?:de\s+)?)?(.+)",
     lambda g: f"autoriza {SENSORES[_clave(g[0])]}" if _clave(g[0]) in SENSORES else None),
    (r"(?:desactiva|apaga|deja de usar|ya no uses)\s+(?:el\s+)?(?:sensor\s+(?:de\s+)?)?(.+)",
     lambda g: f"desactiva {SENSORES[_clave(g[0])]}" if _clave(g[0]) in SENSORES else None),
    (r"(?:como esta|que hay en|que pasa en|lee|revisa|checa)\s+(?:el\s+)?(?:entorno|ambiente|cuarto)|"
     r"que hay a mi alrededor|lee los sensores|que dicen los sensores|como esta todo alrededor", "entorno"),
    (VER + r"\s+el\s+mapa|el mapa|que descubrio el rover|que hay en el mapa", "mapa"),

    # ---------- SISTEMA ----------
    (r"(?:quien|quienes)\s+(?:esta|estan)\s+conectad[oa]s?|" + QUE + r"\s+inteligencias\s+(?:hay|tienes|estan)|"
     r"(?:" + VER + r"\s+)?el ecosistema", "ecosistema"),
    (r"que (?:paso|ha pasado|hiciste) hoy|resumen del dia|como estuvo el dia|(?:" + VER + r"\s+)?el registro", "qué pasó hoy"),
    (r"(?:hubo|hay|tuviste)\s+errores(?:\s+hoy)?|" + QUE + r"\s+errores\s+(?:hubo|hay|tuviste)(?:\s+hoy)?|"
     r"(?:" + VER + r"\s+)?(?:los\s+)?(?:ultimos\s+)?errores", "errores"),
    (r"(?:hay|hubo|tienes)\s+(?:algun\s+)?(?:incidentes?|problemas?)|algo anda mal|" + QUE + r"\s+incidentes\s+hay|"
     r"(?:" + VER + r"\s+)?los incidentes", "incidentes"),
    (r"(?:como esta|como va|como anda|revisa|checa)\s+(?:la compu|la computadora|el equipo|la pc|la maquina)|"
     r"cuanta (?:ram|memoria|bateria) (?:hay|queda|tengo)|(?:" + VER + r"\s+)?los recursos", "recursos"),
    (r"(?:hubo|hay)\s+(?:algo\s+)?(?:sospechoso|ataques?|mensajes sospechosos)|como esta la seguridad|"
     r"(?:" + VER + r"\s+)?la seguridad", "seguridad"),
    (r"(?:recupera|reinicia|revive|arregla|libera)\s+(?:a\s+)?(\w+)", "recupera {1}"),
    (r"(?:ordena|acomoda|limpia)\s+(?:tu|el)\s+diccionario", "ordena tu diccionario"),
    (r"(?:muestrame|haz|resuelve)\s+(?:el\s+)?xor", "xor"),
    (r"entrena(?:te)?|ponte a entrenar|practica con los ejemplos", "entrenar"),

    # ---------- DOCUMENTOS ----------
    (r"(?:lee|leete|abre|revisa)\s+(?:el\s+)?(?:archivo|documento|texto)\s+(.+)", "lee {1}"),
    (r"(?:lee|leete)\s+(\S+\.\w{2,4})", "lee {1}"),

    # ---------- RECUERDOS ----------
    (QUE + r"\s+(?:recuerdos tienes|recuerdas)|(?:" + VER + r"\s+)?(?:tus|los)\s+recuerdos", "recuerdos"),
    (r"de que (?:hablamos|hablabamos|estabamos hablando)", "de qué hablamos"),
    (r"(?:cambiemos|cambia)\s+de\s+tema|otro tema|hablemos de otra cosa", "cambiemos de tema"),

    # ---------- OLVIDAR (delicado) ----------
    (r"(?:olvida|borra)\s+todo\s+(?:lo que sabes\s+)?(?:sobre|de)\s+(.+)", "olvida todo sobre {1}"),
    (r"(?:ya no es cierto|no es cierto|es falso|te ense[nñ]e mal)\s+que\s+(.+)", "olvida que {1}"),
    (r"(?:borra|olvida)\s+el\s+recuerdo\s+(.+)", "olvida el recuerdo {1}"),

    # ---------- LABORATORIO (MINERVA) ----------
    (QUE + r"\s+proyectos\s+(?:tengo|hay|tienes|llevamos)|(?:" + VER + r"\s+)?(?:mis|los)\s+proyectos|"
     r"el laboratorio", "proyectos"),
    (r"(?:carga|trae)\s+(?:el\s+)?(?:proyecto|mapa)\s+(?:de\s+)?focus", "carga el proyecto focus"),
    (r"(?:crea|haz|empieza|arma|inicia)\s+(?:un\s+)?(?:nuevo\s+)?proyecto\s+(?:llamado|que se llame|de nombre)?\s*(.+)",
     "nuevo proyecto {1}"),
    (r"(?:abre|abreme|ve al|vamos al|trabajemos en el|cambia al)\s+(?:el\s+)?proyecto\s+(.+)", "proyecto {1}"),
    (r"(?:marca|pon)\s+(?:la\s+|el\s+)?(?:capacidad\s+)?" + NUM + r"\s+como\s+(.+)",
     lambda g: f"marca {g[0]} como {ESTADOS[_clave(g[1])]}" if _clave(g[1]) in ESTADOS else None),
    (r"(?:la\s+|el\s+)?(?:capacidad\s+)?" + NUM + r"\s+ya\s+(?:esta|existe|quedo)(?:\s+(?:lista|hecha|terminada))?",
     "marca {1} como existe"),
    (r"(?:dame\s+)?(?:ideas|estrategias)\s+(?:para|de)\s+(?:la\s+|el\s+)?(?:capacidad\s+)?" + NUM +
     r"|como (?:lleno|hago|resuelvo)\s+(?:la\s+|el\s+)?(?:capacidad\s+)?" + NUM,
     lambda g: f"estrategias {g[0] or g[1]}"),
    (r"(?:registra|anota)\s+un\s+experimento\s+(?:en|para)\s+(?:la\s+|el\s+)?" + NUM, "experimento en {1}"),
    (r"(?:quita|borra|elimina)\s+(?:la\s+|el\s+)?capacidad\s+" + NUM, "quita la capacidad {1}"),
    (r"que sigue|que hago (?:ahora|despues)|que me recomiendas(?: hacer)?|cual es el siguiente paso|"
     r"en que trabajo(?: ahora)?|que deberia hacer(?: ahora)?", "qué sigue"),

    # ---------- RESPALDOS Y BITÁCORA (ELEUTHIA) ----------
    (r"(?:haz|hazme|crea|guarda)\s+(?:un|una)\s+(?:respaldo|copia(?: de seguridad)?)|respalda(?:te| todo)?|"
     r"guarda una copia de todo", "respalda"),
    (QUE + r"\s+respaldos\s+(?:hay|tengo|tienes)|(?:" + VER + r"\s+)?(?:los|mis)\s+respaldos", "respaldos"),
    (r"(?:restaura|regresa al|vuelve al|usa el|recupera el)\s+(?:el\s+)?respaldo\s+" + NUM, "restaura {1}"),
    (r"(?:" + VER + r"\s+)?la bitacora|que anotaste(?: hoy)?|que aprendiste hoy", "bitácora"),
    (r"(?:anota|apunta|escribe)\s+en\s+la\s+bitacora\s*:?\s*(?:que\s+)?(.+)", "anota {1}"),
    (QUE + r"\s+experimentos\s+(?:hay|tengo|hice|llevamos)|(?:" + VER + r"\s+)?(?:los|mis)\s+experimentos", "experimentos"),
    (r"(?:quiero\s+)?(?:registrar|anotar)\s+un\s+experimento", "nuevo experimento"),

    # ---------- PRIVACIDAD (DEMETER) ----------
    (QUE + r"\s+(?:carpetas|zonas)\s+(?:proteges|estan protegidas|cuidas)|(?:" + VER + r"\s+)?las zonas protegidas", "zonas protegidas"),
    (r"(?:protege|cuida)\s+(?:la\s+carpeta\s+)?(.+)", "protege {1}"),
    (r"(?:deja de proteger|ya no protejas|desprotege)\s+(?:la\s+carpeta\s+)?(.+)", "desprotege {1}"),
    (QUE + r"\s+permisos\s+(?:hay|tienes|di)|(?:" + VER + r"\s+)?(?:los|mis)\s+permisos", "permisos"),

    # ---------- WEB (CUERNO ARADO) ----------
    (r"(?:confia en|es seguro|marca como seguro)\s+(.+)", "confía en {1}"),
    (r"(?:no confies en|bloquea el sitio|marca como peligroso)\s+(.+)", "bloquea {1}"),
    (QUE + r"\s+sitios\s+(?:tengo|hay|bloqueaste|son confiables)|(?:" + VER + r"\s+)?mis sitios", "mis sitios"),

    # ---------- TAREAS ----------
    (r"(?:como|que pasos)\s+(?:harias|haces|seguirias)\s+(?:para\s+)?(.+)|(?:dime como|planea como)\s+(.+)",
     lambda g: f"planea {g[0] or g[1]}"),
]

_REGLAS = [(re.compile(r"^(?:" + patron + r")$"), plantilla) for patron, plantilla in REGLAS]


def _grupos(encontrado, texto):
    """Los grupos del patrón, recortados del texto original (con acentos y mayúsculas)."""
    return [texto[encontrado.start(i):encontrado.end(i)].strip(" ,.:\"'«»") if encontrado.group(i) is not None else None
            for i in range(1, (encontrado.lastindex or 0) + 1)]


def traducir(texto):
    """Texto ya limpio (sin muletillas) → {"comando", "delicado"} o None."""
    texto = texto.strip(" ,.¿?¡!")
    t = simple(texto)
    if not t:
        return None

    for patron, plantilla in _REGLAS:
        encontrado = patron.match(t)
        if not encontrado:
            continue
        grupos = [g for g in _grupos(encontrado, texto)]
        if callable(plantilla):
            comando = plantilla(grupos)
            if comando is None:
                continue          # parecía, pero no (ej. "activa la alarma": no es un sensor)
        else:
            utiles = [g for g in grupos if g is not None]
            comando = plantilla.format(None, *utiles)
        return {"comando": comando, "delicado": es_delicado(comando)}

    return None