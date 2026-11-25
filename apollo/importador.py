"""
APOLLO — Importar conocimiento en bloque.

Para cargar miles de conceptos de golpe (por ejemplo, de WordNet).
Mezcla lo nuevo con lo que HEFESTO ya sabe, sin borrar nada ni
duplicar, y lo guarda todo en UNA transacción.
"""

from apollo.conocimiento import cargar_diccionario, guardar_diccionario, base
from apollo.lenguaje import normalizar_concepto, normalizar_relacion
from apollo import fuentes


def _agregar_sin_repetir(destino, nuevos, clave):
    """Agrega lo que no estaba y devuelve la lista de lo agregado."""
    vistos = {clave(x) for x in destino}
    agregados = []

    for x in nuevos:
        if clave(x) not in vistos:
            destino.append(x)
            vistos.add(clave(x))
            agregados.append(x)

    return agregados


def _que_se_agrego(palabra, asociaciones, sinonimos, relaciones):
    """Lo agregado, en la forma que pide fuentes.anotar: (sujeto, tipo, objeto, negada)."""
    return (
        [(palabra, "es", a, False) for a in asociaciones if isinstance(a, str)]
        + [(palabra, "sinonimo", s, False) for s in sinonimos if isinstance(s, str)]
        + [(palabra, r["relacion"], r["objetivo"], bool(r.get("negada")))
           for r in relaciones if isinstance(r, dict) and r.get("relacion") and r.get("objetivo")]
    )


def importar(entradas, fuente=fuentes.WORDNET):
    """
    Agrega una lista de entradas al diccionario:
        [{"palabra", "asociaciones", "sinonimos", "relaciones"}, ...]

    Si el concepto ya existe, solo le suma lo que no tenía.
    Lo que agrega queda anotado con su 'fuente' (WordNet, por defecto).
    Devuelve {"estado": "importado", "nuevos": N, "ampliados": M}.
    """
    diccionario = cargar_diccionario()

    existentes = {}
    for entrada in diccionario["palabras"]:
        existentes.setdefault(normalizar_concepto(entrada["palabra"]), entrada)

    clave_relacion = lambda r: (
        normalizar_relacion(r.get("relacion", "")),
        normalizar_concepto(r.get("objetivo", "")),
        bool(r.get("negada"))
    )

    nuevos = ampliados = 0
    anotaciones = []

    for entrada in entradas:

        clave = normalizar_concepto(entrada["palabra"])

        if not clave:
            continue

        if clave not in existentes:
            nueva = {
                "palabra": entrada["palabra"],
                "asociaciones": list(entrada.get("asociaciones", [])),
                "sinonimos": list(entrada.get("sinonimos", [])),
                "relaciones": list(entrada.get("relaciones", [])),
            }
            diccionario["palabras"].append(nueva)
            existentes[clave] = nueva
            nuevos += 1
            anotaciones += _que_se_agrego(nueva["palabra"], nueva["asociaciones"],
                                          nueva["sinonimos"], nueva["relaciones"])
            continue

        actual = existentes[clave]
        asociaciones = _agregar_sin_repetir(
            actual.setdefault("asociaciones", []), entrada.get("asociaciones", []), normalizar_concepto)
        sinonimos = _agregar_sin_repetir(
            actual.setdefault("sinonimos", []), entrada.get("sinonimos", []), normalizar_concepto)
        relaciones = _agregar_sin_repetir(
            actual.setdefault("relaciones", []), entrada.get("relaciones", []), clave_relacion)

        if asociaciones or sinonimos or relaciones:
            ampliados += 1
            anotaciones += _que_se_agrego(actual["palabra"], asociaciones, sinonimos, relaciones)

    guardar_diccionario(diccionario)
    fuentes.anotar(base(), anotaciones, fuente)

    return {"estado": "importado", "nuevos": nuevos, "ampliados": ampliados}