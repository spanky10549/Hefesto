"""
APOLLO — Definiciones.

Junta todo lo que se sabe de un concepto, directo y deducido,
para que alguien (HEFESTO) lo pueda explicar:

    pingüino
        categorías:  ave
        hace:        puede → nadar
        no hace:     NO puede → volar
        hereda:      tiene → plumas   (por ser ave)

No redacta frases: devuelve datos ordenados. Cómo se dicen es
trabajo de quien habla.
"""

from apollo.conocimiento import buscar_entrada, buscar_relaciones
from apollo.lenguaje import normalizar_relacion
from apollo.razonamiento import (
    categorias_directas,
    ancestros,
    relaciones_inferidas,
    relaciones_inversas
)


def _agrupar(pares):
    """[("tiene", "plumas"), ("tiene", "pico")] → {"tiene": ["plumas", "pico"]}"""
    grupos = {}

    for verbo, objetivo in pares:
        lista = grupos.setdefault(verbo, [])
        if objetivo not in lista:
            lista.append(objetivo)

    return grupos


def definir(concepto):
    """
    Todo lo que se sabe de un concepto, listo para explicarse.

    Devuelve un diccionario con:
        concepto              el nombre principal
        conocido              False si no sabe nada
        sinonimos             otros nombres
        categorias            lo que es directamente ("ave")
        categorias_deducidas  [(categoría, por ser)] ("animal", por ser "ave")
        hace                  {verbo: [objetivos]}   lo que sí
        no_hace               {verbo: [objetivos]}   lo que no
        hereda                [(por ser, verbo, objetivo)]
        ejemplos              lo que es de este tipo ("pingüino" para "ave")
        lo_mencionan          [(sujeto, verbo)] otros que apuntan a él
        pistas_genero         {concepto: su primera categoría}, para adivinar
                              si es "el" o "la" (raspberry pi → computadora → la)
    """
    entrada = buscar_entrada(concepto)
    nombre = entrada["palabra"] if entrada else concepto

    sinonimos = list(entrada.get("sinonimos", [])) if entrada else []

    categorias = categorias_directas(nombre)

    categorias_deducidas = [
        (categoria, cadena[-1]["origen"])
        for categoria, cadena in ancestros(nombre)
        if len(cadena) > 1
    ]

    hace = _agrupar(
        (normalizar_relacion(r["relacion"]), r["objetivo"])
        for r in buscar_relaciones(nombre)
        if normalizar_relacion(r["relacion"]) != "es"   # las categorías van aparte
    )

    no_hace = _agrupar(
        (normalizar_relacion(r["relacion"]), r["objetivo"])
        for r in buscar_relaciones(nombre, negadas=True)
    )

    hereda = [
        (inferida["cadena"][-1]["origen"], inferida["relacion"], inferida["objetivo"])
        for inferida in relaciones_inferidas(nombre)
    ]

    inversas = relaciones_inversas(nombre)

    ejemplos = [i["sujeto"] for i in inversas if i["relacion"] == "es"]

    lo_mencionan = [
        (i["sujeto"], i["relacion"]) for i in inversas if i["relacion"] != "es"
    ]

    pistas_genero = {}
    for sujeto in [nombre] + [s for s, _ in lo_mencionan]:
        categorias_sujeto = categorias if sujeto == nombre else categorias_directas(sujeto)
        if categorias_sujeto:
            pistas_genero[sujeto] = categorias_sujeto[0]

    conocido = any([
        entrada, categorias, hace, no_hace, hereda, ejemplos, lo_mencionan
    ])

    return {
        "concepto": nombre,
        "conocido": bool(conocido),
        "sinonimos": sinonimos,
        "categorias": categorias,
        "categorias_deducidas": categorias_deducidas,
        "hace": hace,
        "no_hace": no_hace,
        "hereda": hereda,
        "ejemplos": ejemplos,
        "lo_mencionan": lo_mencionan,
        "pistas_genero": pistas_genero,
    }