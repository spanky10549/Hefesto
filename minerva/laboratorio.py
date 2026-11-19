"""
MINERVA — Laboratorio de innovación.

Para proyectos que "todavía no se pueden" hacer completos. Se parte la
meta en capacidades, cada una con su estado:

    ✅ existe     ya funciona
    🟡 a_medias   hay algo, pero no completo
    ❌ falta      el hueco

Las capacidades forman un árbol (una puede tener sub-capacidades). Solo
las "hojas" (las que no tienen hijas) llevan estado propio; el de las de
arriba se calcula con el de sus hijas.

    Avance = (hojas que existen + la mitad de las que van a medias) / hojas

Para cada hueco sugiere estrategias de inventor:
    combinar, adaptar, aproximar, simular, enchufe primero, crear desde cero

Se guarda en laboratorio.json.
"""

import os
import re
from datetime import datetime

from memoria.almacenamiento import cargar_json, guardar_json


ARCHIVO_LABORATORIO = "laboratorio.json"

EXISTE = "existe"
A_MEDIAS = "a_medias"
FALTA = "falta"
ESTADOS = (EXISTE, A_MEDIAS, FALTA)

# Palabras que delatan que una capacidad depende de hardware.
HARDWARE = (
    "sensor", "camara", "robot", "rover", "motor", "raspberry", "esp32",
    "dispositivo", "voz", "microfono", "pantalla", "bateria", "fisico",
)

PALABRAS_VACIAS = {
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "en", "con", "para",
    "por", "del", "al", "a", "que", "se", "su", "sus", "mas", "pero", "solo",
    "sin", "hoy", "ya", "no", "falta", "existe", "medias", "como", "todo", "nada",
}


class ErrorLaboratorio(Exception):
    """Algo que se pidió no tiene sentido (proyecto o capacidad que no existe...)."""


def _simple(texto):
    import unicodedata
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def palabras_clave(texto):
    return {p for p in re.findall(r"[a-z0-9ñ]+", _simple(texto)) if p not in PALABRAS_VACIAS and len(p) > 2}


class Laboratorio:

    def __init__(self, ruta=None, ahora=None):
        self.ruta = ruta or ARCHIVO_LABORATORIO
        self.ahora = ahora or datetime.now
        self.proyectos = cargar_json(self.ruta, {}) if os.path.exists(self.ruta) else {}

    def _guardar(self):
        guardar_json(self.ruta, self.proyectos)

    # ==========================================
    # PROYECTOS
    # ==========================================

    def _clave(self, nombre):
        """Busca el proyecto sin importar mayúsculas ni acentos."""
        buscado = _simple(nombre.strip())
        for clave in self.proyectos:
            if _simple(clave) == buscado:
                return clave
        return None

    def proyecto(self, nombre):
        clave = self._clave(nombre or "")
        if clave is None:
            raise ErrorLaboratorio(f"no hay un proyecto llamado '{nombre}'")
        return self.proyectos[clave]

    def crear_proyecto(self, nombre, meta):
        nombre, meta = (nombre or "").strip(), (meta or "").strip()
        if not nombre:
            raise ErrorLaboratorio("el proyecto necesita un nombre")
        if self._clave(nombre):
            raise ErrorLaboratorio(f"ya existe el proyecto '{nombre}'")

        self.proyectos[nombre] = {
            "nombre": nombre,
            "meta": meta or "sin meta todavía",
            "creado": self.ahora().isoformat(timespec="seconds"),
            "capacidades": [],
            "siguiente_id": 1,
        }
        self._guardar()
        return self.proyectos[nombre]

    def borrar_proyecto(self, nombre):
        clave = self._clave(nombre)
        if clave is None:
            raise ErrorLaboratorio(f"no hay un proyecto llamado '{nombre}'")
        del self.proyectos[clave]
        self._guardar()

    # ==========================================
    # CAPACIDADES
    # ==========================================

    def _capacidad(self, proyecto, numero):
        for capacidad in proyecto["capacidades"]:
            if capacidad["id"] == numero:
                return capacidad
        raise ErrorLaboratorio(f"el proyecto no tiene la capacidad #{numero}")

    def hijas(self, proyecto, numero):
        return [c for c in proyecto["capacidades"] if c["padre"] == numero]

    def agregar(self, nombre_proyecto, nombre, padre=None, estado=FALTA, notas=""):
        proyecto = self.proyecto(nombre_proyecto)
        nombre = (nombre or "").strip()
        if not nombre:
            raise ErrorLaboratorio("la capacidad necesita un nombre")
        if estado not in ESTADOS:
            raise ErrorLaboratorio(f"estado inválido: '{estado}'")
        if padre is not None:
            self._capacidad(proyecto, padre)

        capacidad = {
            "id": proyecto["siguiente_id"],
            "nombre": nombre,
            "padre": padre,
            "estado": estado,
            "notas": (notas or "").strip(),
        }
        proyecto["capacidades"].append(capacidad)
        proyecto["siguiente_id"] += 1
        self._guardar()
        return capacidad

    def marcar(self, nombre_proyecto, numero, estado, notas=None):
        proyecto = self.proyecto(nombre_proyecto)
        capacidad = self._capacidad(proyecto, numero)
        if estado not in ESTADOS:
            raise ErrorLaboratorio(f"estado inválido: '{estado}' (usa existe, a_medias o falta)")
        if self.hijas(proyecto, numero):
            raise ErrorLaboratorio(
                f"#{numero} tiene sub-capacidades: su estado sale de ellas, márcalas a ellas"
            )
        capacidad["estado"] = estado
        if notas is not None:
            capacidad["notas"] = notas.strip()
        self._guardar()
        return capacidad

    def quitar(self, nombre_proyecto, numero):
        """Quita una capacidad y todas sus sub-capacidades."""
        proyecto = self.proyecto(nombre_proyecto)
        self._capacidad(proyecto, numero)

        quitar = {numero}
        cambio = True
        while cambio:
            cambio = False
            for c in proyecto["capacidades"]:
                if c["padre"] in quitar and c["id"] not in quitar:
                    quitar.add(c["id"])
                    cambio = True

        proyecto["capacidades"] = [c for c in proyecto["capacidades"] if c["id"] not in quitar]
        self._guardar()
        return sorted(quitar)

    # ==========================================
    # ESTADO Y AVANCE
    # ==========================================

    def estado_de(self, proyecto, numero):
        """Hojas: su estado. Las de arriba: todo existe → existe; nada → falta; si no, a medias."""
        hijas = self.hijas(proyecto, numero)
        if not hijas:
            return self._capacidad(proyecto, numero)["estado"]

        estados = {self.estado_de(proyecto, h["id"]) for h in hijas}
        if estados == {EXISTE}:
            return EXISTE
        if estados == {FALTA}:
            return FALTA
        return A_MEDIAS

    def hojas(self, proyecto):
        con_hijas = {c["padre"] for c in proyecto["capacidades"]}
        return [c for c in proyecto["capacidades"] if c["id"] not in con_hijas]

    def avance(self, proyecto, numero=None):
        """Porcentaje 0-100 del proyecto, o de una rama si se da 'numero'."""
        hojas = self.hojas(proyecto)
        if numero is not None:
            hojas = [h for h in hojas if self._desciende_de(proyecto, h["id"], numero)]
        if not hojas:
            return 0
        puntos = sum(1 if h["estado"] == EXISTE else 0.5 if h["estado"] == A_MEDIAS else 0 for h in hojas)
        return round(100 * puntos / len(hojas))

    def _desciende_de(self, proyecto, numero, ancestro):
        actual = numero
        while actual is not None:
            if actual == ancestro:
                return True
            actual = self._capacidad(proyecto, actual)["padre"]
        return False

    def arbol(self, nombre_proyecto):
        """Las capacidades en orden de árbol, con su nivel y estado calculado."""
        proyecto = self.proyecto(nombre_proyecto)
        filas = []

        def recorrer(padre, nivel):
            for c in proyecto["capacidades"]:
                if c["padre"] == padre:
                    filas.append({
                        **c,
                        "nivel": nivel,
                        "estado": self.estado_de(proyecto, c["id"]),
                        "es_hoja": not self.hijas(proyecto, c["id"]),
                        "avance": self.avance(proyecto, c["id"]),
                    })
                    recorrer(c["id"], nivel + 1)

        recorrer(None, 0)
        return {
            "nombre": proyecto["nombre"],
            "meta": proyecto["meta"],
            "avance": self.avance(proyecto),
            "capacidades": filas,
        }

    def resumen(self):
        return [
            {"nombre": p["nombre"], "meta": p["meta"], "avance": self.avance(p),
             "capacidades": len(p["capacidades"])}
            for p in self.proyectos.values()
        ]

    # ==========================================
    # ESTRATEGIAS
    # ==========================================

    def estrategias(self, nombre_proyecto, numero, experimentos=()):
        """
        Ideas para llenar el hueco #numero. 'experimentos' son los que ya se
        intentaron en esa capacidad (de ELEUTHIA), para no repetir errores.
        """
        proyecto = self.proyecto(nombre_proyecto)
        capacidad = self._capacidad(proyecto, numero)
        estado = self.estado_de(proyecto, numero)
        # Para buscar parecidas se usan solo los NOMBRES: las notas traen
        # palabras sueltas que harían parecer iguales cosas que no lo son.
        clave = palabras_clave(capacidad["nombre"])
        clave_con_notas = palabras_clave(capacidad["nombre"] + " " + capacidad["notas"])
        ideas = []

        def idea(nombre, texto):
            ideas.append({"estrategia": nombre, "idea": texto})

        if estado == EXISTE:
            idea("mejorar", "ya funciona: ¿se puede hacer más rápido, más simple o más barato?")
            return {"capacidad": capacidad, "estado": estado, "ideas": ideas}

        if self.hijas(proyecto, numero):
            pendientes = [h["nombre"] for h in self.hijas(proyecto, numero)
                          if self.estado_de(proyecto, h["id"]) != EXISTE]
            idea("dividir", "ya está dividida; trabaja en sus partes: " + ", ".join(pendientes))
            return {"capacidad": capacidad, "estado": estado, "ideas": ideas}

        # Lo que ya existe en el proyecto y se parece: candidatos a combinar o adaptar
        parecidas = [
            c for c in self.hojas(proyecto)
            if c["id"] != numero and c["estado"] == EXISTE
            and clave & palabras_clave(c["nombre"])
        ]
        if parecidas:
            nombres = ", ".join(f"#{c['id']} {c['nombre']}" for c in parecidas[:3])
            idea("combinar", f"ya tienes cosas parecidas que funcionan: {nombres}. ¿Juntas resuelven esto?")

        if clave_con_notas & set(HARDWARE):
            idea("simular", "haz una versión de mentira del hardware para avanzar con todo lo demás")
            idea("enchufe primero", "define desde ya su contrato (qué recibe y qué devuelve), "
                                    "para que cuando tengas el hardware solo se conecte")

        if estado == A_MEDIAS:
            idea("aproximar", "termina primero una versión simple que funcione completa, aunque no sea la ideal")
        else:
            idea("dividir", "pártela en 2 o 3 sub-capacidades más pequeñas; así es más fácil ver qué sí existe")
            idea("crear desde cero", "construye la versión MÍNIMA que funcione, con sus pruebas")

        idea("adaptar", "busca quién ya resolvió algo parecido en otro campo (una librería, un juego, la naturaleza)")

        # Aprender de los experimentos pasados
        fallidos = [e for e in experimentos if e.get("resultado") == "falló"]
        for e in fallidos[-3:]:
            leccion = f" (aprendiste: {e['aprendizaje']})" if e.get("aprendizaje") else ""
            idea("no repetir", f"ya intentaste \"{e['intento']}\" y falló{leccion}: prueba otra estrategia")

        return {"capacidad": capacidad, "estado": estado, "ideas": ideas}

    def siguiente(self, nombre_proyecto, fallos_por_capacidad=None):
        """
        La siguiente capacidad recomendada: primero lo que va a medias (está
        más cerca), luego lo que no depende de hardware, y lo que menos ha fallado.
        """
        proyecto = self.proyecto(nombre_proyecto)
        fallos = fallos_por_capacidad or {}
        pendientes = [h for h in self.hojas(proyecto) if h["estado"] != EXISTE]
        if not pendientes:
            return None

        def orden(c):
            depende_de_hardware = bool(palabras_clave(c["nombre"] + " " + c["notas"]) & set(HARDWARE))
            return (c["estado"] != A_MEDIAS, depende_de_hardware, fallos.get(c["id"], 0), c["id"])

        return min(pendientes, key=orden)


# ==========================================
# PLANTILLA: EL PROPIO FOCUS
# ==========================================

PLANTILLA_FOCUS = {
    "nombre": "FOCUS",
    "meta": "Llegar a los niveles 4 (autónomo supervisado) y 5 (cognitivo integrado)",
    "ramas": [
        ("Nivel 3: el ecosistema en el mundo real", [
            ("Las 12 inteligencias comunicándose por GAIA", EXISTE, "esqueleto completo, 692 pruebas"),
            ("FOCUS corriendo en la Raspberry Pi 5", FALTA, "por comprar; el código ya es compatible"),
            ("Sensores físicos con ESP32", FALTA, "el contrato 'leer' ya existe"),
            ("Rover físico con motores", FALTA, "el rover simulado ya decide solo"),
            ("Dispositivo portátil con cámara y voz", FALTA, "diseñarlo y simular sus partes"),
        ]),
        ("Nivel 4: autónomo supervisado", [
            ("Planes de varios pasos", A_MEDIAS, "MINERVA divide tareas, pero solo con reglas fijas"),
            ("Prioridades y conflictos en GAIA", FALTA, "hoy todo se atiende en orden de llegada"),
            ("Integración de herramientas", A_MEDIAS, "la calculadora existe; falta un registro de herramientas"),
            ("Inventario de materiales y piezas", FALTA, "ARTEMIS solo ve CPU, RAM, disco y batería"),
            ("Control de dispositivos con límites", A_MEDIAS, "rover simulado con freno de seguridad"),
            ("Mensajes cifrados en la red", FALTA, "POSEIDON firma, pero no cifra"),
            ("Recuperación real de fallos", A_MEDIAS, "HADES solo reconecta"),
        ]),
        ("Nivel 5: cognitivo integrado", [
            ("Fuentes del conocimiento", FALTA, "saber si un dato vino de ti, de un documento o de WordNet"),
            ("Aprender de correcciones", FALTA, ""),
            ("Hipótesis y analogías", FALTA, "imaginar ideas nuevas a partir de lo que sabe"),
            ("Red neuronal útil (PyTorch, embeddings)", FALTA, "hoy solo resuelve XOR"),
            ("Módulo creativo con modelo de lenguaje", FALTA, "el enchufe para proponer código"),
            ("Laboratorio de innovación", A_MEDIAS, "versión 1: árbol, estrategias y avance"),
        ]),
    ],
}


def cargar_plantilla_focus(laboratorio):
    p = PLANTILLA_FOCUS
    laboratorio.crear_proyecto(p["nombre"], p["meta"])
    for rama, capacidades in p["ramas"]:
        padre = laboratorio.agregar(p["nombre"], rama)
        for nombre, estado, notas in capacidades:
            laboratorio.agregar(p["nombre"], nombre, padre["id"], estado, notas)
    return laboratorio.proyecto(p["nombre"])
