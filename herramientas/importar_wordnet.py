"""
Importa WordNet en español al diccionario de HEFESTO.

WordNet es un diccionario donde las palabras están conectadas:
"perro" es un "cánido", "rueda" es una "máquina", "computadora"
también se llama "ordenador"...

Usa el Open Multilingual Wordnet (español, del Multilingual Central
Repository) con el WordNet en inglés como esqueleto de las conexiones.

Uso (desde la carpeta Cerebro):

    pip install wn
    python -m herramientas.importar_wordnet            (todo)
    python -m herramientas.importar_wordnet 500        (solo 500, para probar)

Antes de importar hace una copia de la base de datos actual
(diccionario_hefesto.antes_de_wordnet.db), por si quieres volver atrás.
"""

import os
import shutil
import sys
import time

import wn

from apollo import conocimiento as apollo
from apollo.importador import importar
from apollo.lenguaje import forma_singular


LEXICO_ES = "omw-es:1.4"
LEXICO_EN = "omw-en:1.4"

MAX_SUBIDAS = 3   # niveles que sube buscando una categoría con nombre en español

# WordNet en español mezcla palabras de España y de Latinoamérica.
# Si un significado tiene alguna de estas, se usa como nombre principal.
PREFERIDAS_MEXICO = {
    "computadora", "computadora portátil", "celular", "carro", "jugo", "papa",
    "frijol", "durazno", "elevador", "boleto", "camión", "lentes", "refrigerador",
    "estacionamiento", "cacahuate", "aguacate", "chamarra", "alberca", "pasto",
}


def descargar_si_hace_falta():
    instalados = {f"{lex.id}:{lex.version}" for lex in wn.lexicons()}

    for lexico in (LEXICO_EN, LEXICO_ES):
        if lexico not in instalados:
            print(f"Descargando {lexico} (solo la primera vez)...")
            wn.download(lexico, progress_handler=None)


def ili_de(synset):
    ili = synset.ili
    if ili is None:
        return None
    return ili if isinstance(ili, str) else ili.id


class Importador:

    def __init__(self):
        self.es = wn.Wordnet(LEXICO_ES, expand=LEXICO_EN)
        self.en = wn.Wordnet(LEXICO_EN)
        self._frecuencias = {}

    # ---------- elegir el significado más común ----------

    def frecuencia(self, synset):
        """
        Cuántas veces aparece este significado en textos reales,
        según el WordNet en inglés. Sirve para elegir, por ejemplo,
        "rueda" = wheel y no "rueda" = instrumento de tortura.
        """
        if synset.id not in self._frecuencias:
            total = 0
            ili = ili_de(synset)
            if ili:
                ingles = self.en.synsets(ili=ili)
                if ingles:
                    total = sum(sum(s.counts()) for s in ingles[0].senses())
            self._frecuencias[synset.id] = total
        return self._frecuencias[synset.id]

    def significado_principal(self, lema):
        opciones = self.es.synsets(lema, pos="n")
        if not opciones:
            return None
        return max(opciones, key=lambda s: (self.frecuencia(s), -opciones.index(s)))

    # ---------- nombres ----------

    def que_tan_comun(self, lema):
        """
        Para elegir el nombre principal entre sinónimos ("perro" y no "can"):
        1. Preferir palabras de México ("computadora" y no "ordenador").
        2. Evitar plurales ("ave" y no "aves") y nombres de varias palabras.
        3. La palabra con más significados suele ser la más común.
        """
        return (
            lema in PREFERIDAS_MEXICO,
            forma_singular(lema) == lema.lower(),
            -len(lema.split()),
            len(self.es.synsets(lema)),
        )

    @staticmethod
    def es_palabra(lema):
        """Palabras comunes: minúscula inicial, sin números ni guiones bajos."""
        return lema[:1].islower() and not any(c.isdigit() for c in lema) and "_" not in lema

    def nombre(self, synset):
        """El nombre en español de un significado (el elegido o el primero)."""
        if synset.id in self.nombres:
            return self.nombres[synset.id]
        lemas = [l for l in synset.lemmas() if self.es_palabra(l)]
        return lemas[0] if lemas else None

    def categoria(self, synset):
        """
        La categoría con nombre en español más cercana. Si el "padre"
        no tiene nombre en español, sube hasta MAX_SUBIDAS niveles.
        """
        nivel = synset.hypernyms()

        for _ in range(MAX_SUBIDAS):
            for padre in nivel:
                nombre = self.nombre(padre)
                if nombre:
                    return nombre
            nivel = [abuelo for padre in nivel for abuelo in padre.hypernyms()]
            if not nivel:
                break

        return None

    # ---------- todo junto ----------

    def entradas(self, limite=None):
        """
        Arma las entradas para HEFESTO:
            {"palabra", "asociaciones": [categoría],
             "sinonimos": [...], "relaciones": [forma parte de ...]}
        """
        lemas = sorted({
            lema
            for synset in self.es.synsets(pos="n")
            for lema in synset.lemmas()
            if self.es_palabra(lema)
        })

        if limite:
            lemas = lemas[:limite]

        # 1. Cada palabra elige su significado más común.
        por_significado = {}   # synset.id -> (synset, [lemas que lo eligieron])

        for i, lema in enumerate(lemas, start=1):
            synset = self.significado_principal(lema)
            if synset is not None:
                por_significado.setdefault(synset.id, (synset, []))[1].append(lema)
            if i % 2000 == 0:
                print(f"  ...{i} de {len(lemas)} palabras")

        # 2. Un concepto por significado: la palabra más común es el
        #    nombre y las demás que lo eligieron son sinónimos.
        for synset, lemas_ in por_significado.values():
            lemas_.sort(key=self.que_tan_comun, reverse=True)

        self.nombres = {sid: lemas_[0] for sid, (_, lemas_) in por_significado.items()}

        entradas = []

        for synset, lemas_ in por_significado.values():

            nombre = lemas_[0]
            entrada = {"palabra": nombre, "asociaciones": [], "sinonimos": lemas_[1:], "relaciones": []}

            categoria = self.categoria(synset)
            if categoria and categoria != nombre:
                entrada["asociaciones"].append(categoria)

            for todo in synset.get_related("holo_part"):
                parte_de = self.nombre(todo)
                if parte_de and parte_de != nombre:
                    entrada["relaciones"].append({"relacion": "forma parte de", "objetivo": parte_de})

            entradas.append(entrada)

        return entradas


def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None

    descargar_si_hace_falta()

    ruta = apollo.base()
    respaldo = os.path.splitext(ruta)[0] + ".antes_de_wordnet.db"

    if os.path.exists(ruta) and not os.path.exists(respaldo):
        shutil.copy(ruta, respaldo)
        print(f"Respaldo guardado en {respaldo}")

    inicio = time.time()
    print("Leyendo WordNet en español...")
    entradas = Importador().entradas(limite)

    print(f"Guardando {len(entradas)} conceptos en el diccionario de HEFESTO...")
    r = importar(entradas)

    print(
        f"Listo en {time.time() - inicio:.0f} s: {r['nuevos']} conceptos nuevos, "
        f"{r['ampliados']} que ya conocía ganaron información."
    )


if __name__ == "__main__":
    main()