"""
APOLLO — Importar conocimiento en bloque.

Para cargar miles de conceptos de golpe (por ejemplo, de WordNet).
Mezcla lo nuevo con lo que HEFESTO ya sabe, sin borrar nada ni
duplicar, y lo guarda todo en UNA transacción.
"""

from apollo.conocimiento import cargar_diccionario, guardar_diccionario
from apollo.lenguaje import normalizar_concepto, normalizar_relacion


def _agregar_sin_repetir(destino, nuevos, clave):
    vistos = {clave(x) for x in destino}
    agregados = 0

    for x in nuevos:
        if clave(x) not in vistos:
            destino.append(x)
            vistos.add(clave(x))
            agregados += 1

    return agregados


def importar(entradas):
    """
    Agrega una lista de entradas al diccionario:
        [{"palabra", "asociaciones", "sinonimos", "relaciones"}, ...]

    Si el concepto ya existe, solo le suma lo que no tenía.
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
            continue

        actual = existentes[clave]
        cambios = 0
        cambios += _agregar_sin_repetir(
            actual.setdefault("asociaciones", []), entrada.get("asociaciones", []), normalizar_concepto)
        cambios += _agregar_sin_repetir(
            actual.setdefault("sinonimos", []), entrada.get("sinonimos", []), normalizar_concepto)
        cambios += _agregar_sin_repetir(
            actual.setdefault("relaciones", []), entrada.get("relaciones", []), clave_relacion)

        if cambios:
            ampliados += 1

    guardar_diccionario(diccionario)

    return {"estado": "importado", "nuevos": nuevos, "ampliados": ampliados}