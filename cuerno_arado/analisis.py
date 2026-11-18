"""
CUERNO ARADO — Análisis de enlaces.

Revisa un link SIN abrirlo y sin internet, buscando las trampas que usan
el phishing y las descargas peligrosas. Cada pista suma puntos:

    0          riesgo bajo   (no vi nada raro, que no es lo mismo que seguro)
    1 a 2      riesgo medio
    3 o más    riesgo alto

Son pistas, no una garantía: un link "limpio" puede ser malo y uno
"raro" puede ser legítimo. Funciones puras: texto entra, datos salen.
"""

import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit


# ==========================================
# DATOS
# ==========================================

# Marcas que se suelen imitar → su dominio oficial.
MARCAS = {
    "paypal": ["paypal.com"],
    "mercadolibre": ["mercadolibre.com.mx", "mercadolibre.com"],
    "mercadopago": ["mercadopago.com.mx", "mercadopago.com"],
    "amazon": ["amazon.com.mx", "amazon.com", "amazonaws.com"],
    "google": ["google.com", "google.com.mx", "googleapis.com", "googleusercontent.com"],
    "gmail": ["gmail.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "facebook": ["facebook.com"],
    "instagram": ["instagram.com"],
    "whatsapp": ["whatsapp.com"],
    "microsoft": ["microsoft.com", "microsoftonline.com"],
    "outlook": ["outlook.com", "live.com"],
    "apple": ["apple.com"],
    "icloud": ["icloud.com"],
    "netflix": ["netflix.com"],
    "spotify": ["spotify.com"],
    "steam": ["steampowered.com", "steamcommunity.com"],
    "epicgames": ["epicgames.com"],
    "playstation": ["playstation.com"],
    "xbox": ["xbox.com"],
    "roblox": ["roblox.com"],
    "discord": ["discord.com", "discord.gg"],
    "bbva": ["bbva.mx"],
    "banorte": ["banorte.com"],
    "santander": ["santander.com.mx"],
    "banamex": ["banamex.com"],
    "sat": ["sat.gob.mx"],
    "imss": ["imss.gob.mx"],
}

# Terminaciones de dos partes: en "tienda.com.mx" el dominio es "tienda.com.mx".
SEGUNDO_NIVEL = {
    "com.mx", "gob.mx", "org.mx", "edu.mx", "net.mx",
    "co.uk", "org.uk", "com.br", "com.ar", "com.co", "com.es", "co.jp",
}

ACORTADORES = {
    "bit.ly", "tinyurl.com", "t.co", "cutt.ly", "is.gd", "ow.ly",
    "shorturl.at", "rb.gy", "goo.su", "tiny.cc", "s.id",
}

# Terminaciones baratas que aparecen mucho en estafas (no todas lo son).
TERMINACIONES_RARAS = {
    "xyz", "top", "click", "zip", "mov", "tk", "ml", "ga", "cf", "gq",
    "work", "loan", "rest", "cam", "sbs", "cfd",
}

DESCARGAS_PELIGROSAS = (".exe", ".scr", ".bat", ".cmd", ".msi", ".vbs", ".js", ".jar", ".apk", ".ps1", ".lnk")
COMPRIMIDOS = (".zip", ".rar", ".7z")

PALABRAS_GANCHO = (
    "login", "verifica", "verificar", "seguro", "segura", "cuenta", "actualiza",
    "desbloquea", "premio", "gratis", "free", "gana", "robux", "skins", "nitro",
    "reembolso", "suspendida", "bloqueada", "confirma",
)

# Letras o pares que se confunden a la vista → la letra que imitan.
PARECIDOS = [("rn", "m"), ("vv", "w"), ("cl", "d"), ("0", "o"), ("1", "l"), ("3", "e"),
             ("5", "s"), ("4", "a"), ("@", "a"), ("$", "s")]

# Un link con http(s):// o www., o algo como "github.com/algo" (nombre, punto y una
# terminación de 2 a 24 letras). "son las 3.30" no cuenta: la terminación no es de letras.
ENLACE = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+"
    r"|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,24}\b(?:/[^\s<>\"']*)?",
    re.IGNORECASE,
)


# ==========================================
# AYUDANTES
# ==========================================

def extraer_enlaces(texto):
    """Todos los links de un texto (un SMS, un mensaje de WhatsApp...)."""
    return [m.group(0).rstrip(".,;:!?)") for m in ENLACE.finditer(texto)]


def dominio_registrable(host):
    """'www.paypal.com.login-seguro.xyz' → 'login-seguro.xyz' (el dueño real)."""
    partes = host.lower().strip(".").split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in SEGUNDO_NIVEL:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:])


def nombre_del_dominio(dominio):
    """'mercadolibre.com.mx' → 'mercadolibre'"""
    return dominio.split(".")[0]


def sin_disfraz(texto):
    """'paypa1' → 'paypal', 'rnercadolibre' → 'mercadolibre'"""
    texto = texto.lower().replace("-", "")
    for falso, real in PARECIDOS:
        texto = texto.replace(falso, real)
    return texto


def distancia(a, b):
    """Cuántas letras hay que cambiar, quitar o poner para pasar de a a b."""
    anterior = list(range(len(b) + 1))
    for i, letra_a in enumerate(a, 1):
        actual = [i]
        for j, letra_b in enumerate(b, 1):
            actual.append(min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + (letra_a != letra_b)))
        anterior = actual
    return anterior[-1]


def es_ip(host):
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def es_oficial(dominio, marca):
    return dominio in MARCAS[marca]


# ==========================================
# ANALIZAR
# ==========================================

def analizar(url, confiables=(), bloqueados=()):
    """
    Devuelve:
        url, host, dominio, riesgo ("bajo"|"medio"|"alto"), puntos,
        razones [texto], oficial_de (marca si es el sitio oficial)
    """
    original = url.strip()
    texto = original if re.match(r"^[a-z][a-z0-9+.-]*:", original, re.I) else "http://" + original
    partes = urlsplit(texto)
    esquema = partes.scheme.lower()

    razones = []
    puntos = 0

    def pista(valor, razon):
        nonlocal puntos
        puntos += valor
        razones.append(razon)

    if esquema not in ("http", "https"):
        return _resultado(original, "", "", 5, [f"no es una página web: usa '{esquema}:', que puede ejecutar código"])

    host = (partes.hostname or "").lower()
    if not host:
        return _resultado(original, "", "", 3, ["no tiene un sitio claro"])

    dominio = host if es_ip(host) else dominio_registrable(host)

    # Tus listas mandan
    if dominio in bloqueados:
        return _resultado(original, host, dominio, 5, [f"tú bloqueaste {dominio}"])
    if dominio in confiables:
        return _resultado(original, host, dominio, 0, [f"tú marcaste {dominio} como confiable"])

    # ¿Es el sitio oficial de una marca conocida?
    oficial_de = next((marca for marca in MARCAS if es_oficial(dominio, marca)), None)

    if "@" in (partes.netloc or ""):
        pista(4, f"tiene una @ que esconde el sitio real: en realidad te lleva a {host}")

    if esquema == "http" and not original.lower().startswith(("www.",)) and original.lower().startswith("http://"):
        pista(1, "no usa conexión segura (http sin s)")

    if es_ip(host):
        pista(2, "usa números (una IP) en vez de un nombre de sitio")
    else:
        if host.startswith("xn--") or ".xn--" in host:
            pista(3, "usa letras de otros alfabetos que se ven iguales a las normales")
        elif any(ord(c) > 127 for c in host):
            pista(3, "tiene letras que no son normales (podrían imitar a otras)")

        if dominio in ACORTADORES:
            pista(1, "es un acortador: esconde a dónde te lleva de verdad")

        terminacion = dominio.rsplit(".", 1)[-1]
        if terminacion in TERMINACIONES_RARAS:
            pista(1, f"termina en .{terminacion}, muy usada en estafas")

        if host.count(".") >= 4:
            pista(1, "tiene demasiados subdominios")

        if oficial_de is None:
            nombre = nombre_del_dominio(dominio)
            imitada = _marca_imitada(nombre)
            if imitada:
                marca, oficial = imitada
                pista(4, f"se parece mucho a {marca} pero NO es su sitio oficial ({oficial})")
            else:
                mencionada = next(
                    (m for m in MARCAS if len(m) >= 4 and m in sin_disfraz(host.replace(".", "-"))), None
                )
                if mencionada:
                    pista(3, f"menciona a {mencionada} pero el sitio es {dominio}, no {MARCAS[mencionada][0]}")

    ruta = (partes.path or "").lower()
    if ruta.endswith(DESCARGAS_PELIGROSAS):
        pista(3, "descarga un programa que se puede ejecutar en tu compu")
    elif ruta.endswith(COMPRIMIDOS):
        pista(1, "descarga un archivo comprimido (puede esconder programas)")

    texto_buscable = sin_disfraz(host + " " + ruta)
    ganchos = [p for p in PALABRAS_GANCHO if p in texto_buscable]
    if ganchos and oficial_de is None:
        pista(min(len(ganchos), 2), f"usa palabras gancho ({', '.join(ganchos[:3])})")

    return _resultado(original, host, dominio, puntos, razones, oficial_de)


def _marca_imitada(nombre):
    """
    (marca, dominio oficial) que 'nombre' intenta imitar, si se parece
    demasiado sin ser igual. Compara con la marca ("steam") y con el
    nombre de cada dominio oficial ("steamcommunity").
    """
    limpio = sin_disfraz(nombre)
    for marca, oficiales in MARCAS.items():
        for oficial in oficiales:
            for objetivo in {marca, nombre_del_dominio(oficial)}:
                if nombre == objetivo:
                    continue
                if limpio == objetivo or (len(objetivo) >= 5 and distancia(limpio, objetivo) == 1):
                    return marca, oficial
    return None


def _resultado(url, host, dominio, puntos, razones, oficial_de=None):
    riesgo = "bajo" if puntos == 0 else "medio" if puntos <= 2 else "alto"
    return {
        "url": url, "host": host, "dominio": dominio,
        "riesgo": riesgo, "puntos": puntos, "razones": razones,
        "oficial_de": oficial_de,
    }