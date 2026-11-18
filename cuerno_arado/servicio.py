"""
CUERNO ARADO — Protección web (v1).

Según el plan de FOCUS es una capacidad dentro de POSEIDON: revisa
enlaces antes de que los abras. Supervisada por TABRIS (todo queda en
su registro) y coordinada por HEFESTO.

    revisar        {"url"}     un link: riesgo y razones
    revisar_texto  {"texto"}   todos los links de un mensaje (SMS, WhatsApp...)
    confiar        {"dominio"} tu lista de sitios confiables
    bloquear       {"dominio"} tu lista de sitios bloqueados
    olvidar        {"dominio"} lo quita de las dos listas
    listas         {}

Cuando un link sale con riesgo ALTO publica "enlace_peligroso":
POSEIDON lo cuenta como sospechoso y ELEUTHIA lo anota en la bitácora.
Nunca abre ni descarga nada.
"""

import os

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo, crear_evento
from memoria.almacenamiento import cargar_json, guardar_json

from cuerno_arado.analisis import analizar, extraer_enlaces, dominio_registrable


ARCHIVO_LISTAS = "cuerno_arado_listas.json"
MAX_ENLACES_POR_TEXTO = 20


class CuernoArado(Inteligencia):

    nombre = "cuerno_arado"
    descripcion = "Protección web (parte de POSEIDON): revisa enlaces sospechosos sin abrirlos."

    def __init__(self, ruta_listas=None):
        self.ruta = ruta_listas or ARCHIVO_LISTAS
        guardado = cargar_json(self.ruta, {}) if os.path.exists(self.ruta) else {}
        self.confiables = set(guardado.get("confiables", []))
        self.bloqueados = set(guardado.get("bloqueados", []))

        self.acciones = {
            "revisar": self.revisar,
            "revisar_texto": self.revisar_texto,
            "confiar": self.confiar,
            "bloquear": self.bloquear,
            "olvidar": self.olvidar,
            "listas": self.listas,
        }

    def _guardar(self):
        guardar_json(self.ruta, {
            "confiables": sorted(self.confiables),
            "bloqueados": sorted(self.bloqueados),
        })

    # ==========================================
    # REVISAR
    # ==========================================

    def _analizar(self, url):
        resultado = analizar(url, self.confiables, self.bloqueados)

        if resultado["riesgo"] == "alto" and self.gaia is not None:
            self.gaia.publicar(crear_evento(self.nombre, "enlace_peligroso", {
                "dominio": resultado["dominio"],
                "razon": resultado["razones"][0] if resultado["razones"] else None,
            }))

        return resultado

    def revisar(self, datos):
        url = datos.get("url")
        if not isinstance(url, str) or not url.strip():
            raise Rechazo("falta 'url'")
        return self._analizar(url)

    def revisar_texto(self, datos):
        texto = datos.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise Rechazo("falta 'texto'")

        enlaces = extraer_enlaces(texto)[:MAX_ENLACES_POR_TEXTO]
        resultados = [self._analizar(enlace) for enlace in enlaces]
        peor = max((r["puntos"] for r in resultados), default=0)

        return {
            "enlaces": resultados,
            "riesgo": "bajo" if peor == 0 else "medio" if peor <= 2 else "alto",
        }

    # ==========================================
    # LISTAS
    # ==========================================

    def _dominio(self, datos):
        texto = datos.get("dominio")
        if not isinstance(texto, str) or not texto.strip():
            raise Rechazo("falta 'dominio'")
        texto = texto.strip().lower()
        # Acepta "https://www.tec.mx/algo" o "tec.mx"
        texto = texto.split("://", 1)[-1].split("/", 1)[0].split("@")[-1].split(":")[0]
        if "." not in texto:
            raise Rechazo(f"'{texto}' no parece un sitio (ejemplo: tec.mx)")
        return dominio_registrable(texto)

    def confiar(self, datos):
        dominio = self._dominio(datos)
        self.bloqueados.discard(dominio)
        self.confiables.add(dominio)
        self._guardar()
        return {"dominio": dominio, "lista": "confiables"}

    def bloquear(self, datos):
        dominio = self._dominio(datos)
        self.confiables.discard(dominio)
        self.bloqueados.add(dominio)
        self._guardar()
        return {"dominio": dominio, "lista": "bloqueados"}

    def olvidar(self, datos):
        dominio = self._dominio(datos)
        estaba = dominio in self.confiables or dominio in self.bloqueados
        self.confiables.discard(dominio)
        self.bloqueados.discard(dominio)
        self._guardar()
        return {"dominio": dominio, "estaba": estaba}

    def listas(self, datos):
        return {"confiables": sorted(self.confiables), "bloqueados": sorted(self.bloqueados)}