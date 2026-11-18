"""
ELEUTHIA — Preservación (v1).

Que nada de lo que FOCUS aprende o vive se pierda.

    RESPALDOS     una copia del conocimiento al día (automática al
                  arrancar si el último tiene más de un día), los
                  últimos 10, y restaurar si algo se daña.

    BITÁCORA      un diario de lo importante: lo que HEFESTO aprendió,
                  tareas terminadas, inteligencias recuperadas, sensores
                  nuevos, alertas del entorno... Se llena solo escuchando
                  los eventos del ecosistema.

    EXPERIMENTOS  qué se intentó, qué pasó y qué se aprendió. Es la base
                  del laboratorio de innovación: sin memoria de los
                  experimentos se repiten los mismos errores.

Acciones:
    respaldar        {"etiqueta"?}
    respaldos        {}
    respaldo_al_dia  {}            respalda solo si el último tiene más de un día
    restaurar        {"respaldo"}  queda pendiente hasta reiniciar
    anotar           {"texto", "tipo"?}
    bitacora         {"dia"?: "hoy" | "2026-11-18", "tipo"?, "cantidad"?}
    experimento      {"proyecto", "intento", "resultado", "aprendizaje"?}
    experimentos     {"proyecto"?}
"""

import json
import os
from datetime import datetime, timedelta

from gaia.inteligencia import Inteligencia
from gaia.mensajes import Rechazo

from eleuthia import respaldos


ARCHIVO_BITACORA = "eleuthia_bitacora.jsonl"

RESULTADOS = ("funcionó", "falló", "a medias")

# Eventos del ecosistema que vale la pena recordar, y cómo contarlos.
EVENTOS = {
    "aprendizaje": lambda d: d.get("texto", "aprendí algo nuevo"),
    "tarea_terminada": lambda d: (
        f"terminé la tarea \"{d['tarea']}\" ({d['bien']} de {d['total']} pasos bien)"
    ),
    "aislamiento": lambda d: f"{d['inteligencia'].upper()} quedó aislada: {d.get('motivo')}",
    "recuperacion": lambda d: f"HADES recuperó a {d['inteligencia'].upper()}",
    "anomalia_entorno": lambda d: (
        f"algo raro en el sensor {d['sensor']}: {', '.join(d['motivos'])} ({d['valor']})"
    ),
    "sensor_detectado": lambda d: f"apareció un sensor nuevo: {d['sensor']}",
    "salida_bloqueada": lambda d: (
        f"DEMETER no dejó salir un mensaje hacia {d['destino']} ({', '.join(d['zonas'])})"
    ),
    "acceso_negado": lambda d: (
        f"DEMETER negó a {d['inteligencia'].upper()} {d['operacion']} en {d['zona']}"
    ),
    "enlace_peligroso": lambda d: f"CUERNO ARADO detectó un enlace peligroso: {d['dominio']} ({d.get('razon')})",
    "recursos_bajos": lambda d: "recursos bajos: " + "; ".join(a["texto"] for a in d["alertas"]),
}


class Eleuthia(Inteligencia):

    nombre = "eleuthia"
    descripcion = "Preserva: respaldos del conocimiento, bitácora y registro de experimentos."

    def __init__(self, carpeta=None, ruta_bitacora=None, ahora=None):
        self.carpeta = carpeta or os.getcwd()
        self.destino = os.path.join(self.carpeta, respaldos.CARPETA_RESPALDOS)
        self.ruta_bitacora = ruta_bitacora or ARCHIVO_BITACORA
        self.ahora = ahora or datetime.now

        self.acciones = {
            "respaldar": self.respaldar,
            "respaldos": self.listar_respaldos,
            "respaldo_al_dia": self.respaldo_al_dia,
            "restaurar": self.restaurar,
            "anotar": self.anotar,
            "bitacora": self.bitacora,
            "experimento": self.experimento,
            "experimentos": self.experimentos,
        }

    def al_conectarse(self):
        for evento in EVENTOS:
            self.gaia.suscribir(evento, self._escuchar)

    # ==========================================
    # BITÁCORA (archivo .jsonl, una entrada por línea)
    # ==========================================

    def _escribir(self, entrada):
        entrada = {"fecha": self.ahora().isoformat(timespec="seconds"), **entrada}
        with open(self.ruta_bitacora, "a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        return entrada

    def _leer(self):
        try:
            archivo = open(self.ruta_bitacora, encoding="utf-8")
        except FileNotFoundError:
            return
        with archivo:
            for linea in archivo:
                try:
                    yield json.loads(linea)
                except json.JSONDecodeError:
                    continue

    def _escuchar(self, evento):
        try:
            texto = EVENTOS[evento["accion"]](evento["datos"])
        except (KeyError, TypeError):
            texto = f"pasó '{evento['accion']}'"
        self._escribir({"tipo": evento["accion"], "texto": texto, "de": evento["de"]})

    def anotar(self, datos):
        texto = datos.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise Rechazo("falta 'texto'")
        return self._escribir({"tipo": datos.get("tipo") or "nota", "texto": texto.strip(), "de": "persona"})

    def bitacora(self, datos):
        dia = datos.get("dia")
        if dia == "hoy":
            dia = self.ahora().date().isoformat()
        tipo = datos.get("tipo")
        cantidad = datos.get("cantidad", 50)
        if not isinstance(cantidad, int) or cantidad < 1:
            cantidad = 50

        entradas = [
            e for e in self._leer()
            if (not dia or e["fecha"].startswith(dia))
            and (not tipo or e["tipo"] == tipo)
            and e["tipo"] != "experimento"
        ]
        return {"dia": dia, "entradas": entradas[-cantidad:]}

    # ==========================================
    # EXPERIMENTOS
    # ==========================================

    def experimento(self, datos):
        for campo in ("proyecto", "intento"):
            if not isinstance(datos.get(campo), str) or not datos[campo].strip():
                raise Rechazo(f"falta '{campo}'")
        if datos.get("resultado") not in RESULTADOS:
            raise Rechazo(f"'resultado' debe ser: {', '.join(RESULTADOS)}")

        return self._escribir({
            "tipo": "experimento",
            "proyecto": datos["proyecto"].strip(),
            "intento": datos["intento"].strip(),
            "resultado": datos["resultado"],
            "aprendizaje": (datos.get("aprendizaje") or "").strip() or None,
            "texto": f"[{datos['proyecto'].strip()}] {datos['intento'].strip()}: {datos['resultado']}",
            "de": "persona",
        })

    def experimentos(self, datos):
        proyecto = (datos.get("proyecto") or "").strip().lower()
        lista = [
            e for e in self._leer()
            if e["tipo"] == "experimento" and (not proyecto or e["proyecto"].lower() == proyecto)
        ]
        resumen = {resultado: sum(1 for e in lista if e["resultado"] == resultado) for resultado in RESULTADOS}
        return {"experimentos": lista, "resumen": resumen}

    # ==========================================
    # RESPALDOS
    # ==========================================

    def respaldar(self, datos):
        etiqueta = datos.get("etiqueta")
        if etiqueta is not None and (not isinstance(etiqueta, str) or not etiqueta.isalnum()):
            raise Rechazo("la etiqueta solo puede tener letras y números")
        r = respaldos.crear_respaldo(self.carpeta, self.destino, etiqueta, self.ahora)
        if not r["archivos"]:
            raise Rechazo("no encontré nada que respaldar")
        return r

    def listar_respaldos(self, datos):
        return {"respaldos": respaldos.listar(self.destino), "carpeta": self.destino}

    def respaldo_al_dia(self, datos):
        """Respalda solo si no hay ninguno o el último tiene más de un día."""
        ultimo = respaldos.ultimo(self.destino)
        if ultimo is not None:
            antiguedad = self.ahora() - respaldos.fecha_de(ultimo["nombre"])
            if antiguedad < timedelta(days=1):
                return {"hecho": False, "ultimo": ultimo["nombre"]}

        r = respaldos.crear_respaldo(self.carpeta, self.destino, ahora=self.ahora)
        return {"hecho": True, **r}

    def restaurar(self, datos):
        nombre = datos.get("respaldo")
        if not isinstance(nombre, str) or not nombre:
            raise Rechazo("falta 'respaldo'")

        # Antes de restaurar, se respalda lo de ahorita: por si te arrepientes.
        seguro = respaldos.crear_respaldo(self.carpeta, self.destino, "antes", self.ahora)

        try:
            archivos = respaldos.preparar_restauracion(self.destino, nombre)
        except FileNotFoundError:
            raise Rechazo(f"no existe el respaldo '{nombre}'")

        return {"pendiente": archivos, "respaldo_de_seguridad": seguro["nombre"]}