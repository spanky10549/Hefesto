"""
TABRIS — Registro.

Guarda cada mensaje en un archivo, uno por línea, en formato JSON
(a esto se le llama JSON Lines o .jsonl):

    {"id": "a3f9...", "tipo": "orden", "de": "hefesto", "para": "apollo", ...}
    {"id": "b71c...", "tipo": "respuesta", "estado": "ok", ...}

¿Por qué una línea por mensaje y no un solo JSON gigante?
    - Agregar un mensaje es solo escribir una línea al final: rápido,
      sin tener que leer ni reescribir todo el archivo.
    - Si la compu se apaga a media escritura, solo se daña la última
      línea; las demás siguen bien.
"""

import json
from collections import deque


class Registro:

    def __init__(self, ruta):
        self.ruta = ruta

    def anotar(self, mensaje):
        """Agrega un mensaje al final del archivo."""
        linea = json.dumps(mensaje, ensure_ascii=False)

        with open(self.ruta, "a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")

    def leer(self):
        """
        Recorre los mensajes guardados, del más viejo al más nuevo.
        Las líneas dañadas se saltan en vez de detener todo.

        Es un generador (usa 'yield'): entrega los mensajes de uno
        en uno, sin cargar el archivo completo en memoria.
        """
        try:
            archivo = open(self.ruta, encoding="utf-8")
        except FileNotFoundError:
            return   # todavía no hay registro: no hay nada que leer

        with archivo:
            for linea in archivo:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    yield json.loads(linea)
                except json.JSONDecodeError:
                    continue

    def buscar(self, filtro=None, cantidad=10):
        """
        Los últimos 'cantidad' mensajes que cumplan el filtro.
        'filtro' es una función que recibe un mensaje y dice True o False.
        """
        encontrados = deque(maxlen=cantidad)

        for mensaje in self.leer():
            if filtro is None or filtro(mensaje):
                encontrados.append(mensaje)

        return list(encontrados)