"""
Plática: la forma natural de hablar con FOCUS.

Une todo:
    intenciones.py   qué quieres y con qué datos
    personalidad.py  cómo lo dice (serena y relajada, inspirada en GAIA)
    perfil.py        lo que recuerda de ti

Y lo manda a hacer por GAIA, a la inteligencia de siempre: crear una
rutina aquí es exactamente lo mismo que con "enseña la rutina".

Reglas de trato:
    - Antes de CAMBIAR algo (crear o borrar rutinas, reemplazar lo que
      sabía) te muestra lo que entendió y te pregunta.
    - Si no sabe algo, te pregunta y aprende de tu respuesta.
    - Sigue el hilo: después de hablar del pingüino, "¿y puede volar?"
      es sobre el pingüino.

responder(texto) devuelve una lista de líneas para mostrar.
"""

from apollo.conocimiento import extraer_relacion, extraer_relacion_con_negacion
from apollo.lenguaje import forma_singular
from conversacion.intenciones import entender, es_si, es_no, sin_articulo, limpiar
from conversacion.personalidad import Voz, QUE_PUEDO_HACER
from conversacion.perfil import Perfil
from conversacion.creador import Creador, MAX_INTENTOS, MINIMO_CARACTERES
from gaia.mensajes import crear_evento
from conversacion.redaccion import redactar_definicion, el
from conversacion.resultados import resumir
from cuerno_arado.analisis import extraer_enlaces
from gaia.mensajes import OK, RECHAZADO
from gaia.tareas import ejecutar_plan, SALTADO, OMITIDO, PENDIENTE
from minerva.planeador import simple


PALABRAS_DE_PREGUNTA = ("que ", "quien ", "como ", "cuando ", "donde ", "por que ", "cual ", "cuanto ")


class Platica:

    def __init__(self, gaia, perfil=None, voz=None, de="hefesto", creador=None):
        self.gaia = gaia
        self.perfil = perfil or Perfil()
        self.creador = creador or Creador()
        self.creador_presente = False    # ¿comprobó su clave en esta sesión?
        self.intentos_fallidos = 0
        self.voz = voz or Voz()
        self.de = de
        self.tema = None          # el último concepto del que se habló
        self.pendiente = None     # algo que espera tu respuesta (confirmar, enseñar...)
        self.terminada = False

    # ==========================================
    # AYUDANTES
    # ==========================================

    def pedir(self, para, accion, **datos):
        return self.gaia.pedir(self.de, para, accion, **datos)

    def _rutinas(self):
        r = self.pedir("minerva", "rutinas")
        return r["datos"]["rutinas"] if r["estado"] == OK else []

    def _nombre(self):
        if self.creador_presente:
            return self.creador.nombre
        return self.perfil.nombre

    @property
    def espera_clave(self):
        """¿Lo siguiente que escribas es una clave? (focus.py la pide sin mostrarla)"""
        return self.pendiente is not None and self.pendiente["tipo"] in ("clave", "nueva_clave", "confirmar_clave")

    def _solo_creador(self, accion):
        """
        Algunas cosas solo las puede hacer el creador (si ya configuró su clave).
        Devuelve None si se puede, o las líneas de respuesta si no.
        """
        if not self.creador.configurado() or self.creador_presente:
            return None
        return [f"Eso de {accion} solo lo puede hacer mi creador.",
                f"Si eres {self.creador.nombre}, dime \"soy {self.creador.nombre}\" y comprueba tu clave."]

    # ==========================================
    # RESPONDER
    # ==========================================

    def responder(self, texto):
        if self.pendiente is not None:
            respuesta = self._atender_pendiente(texto)
            if respuesta is not None:
                return respuesta

        nombres_rutinas = [r["nombre"] for r in self._rutinas()]
        intencion = entender(texto, nombres_rutinas)
        manejar = getattr(self, "_" + intencion["intencion"], self._desconocida)
        return manejar(intencion)

    def _atender_pendiente(self, texto):
        """Si había algo esperando tu respuesta. None = no era respuesta a eso."""
        pendiente, self.pendiente = self.pendiente, None

        if pendiente["tipo"] == "confirmar":
            if es_si(texto):
                return pendiente["hacer"]()
            if es_no(texto):
                return [self.voz.di("cancelado")]
            return None   # dijo otra cosa: se olvida la pregunta y se atiende lo nuevo

        if pendiente["tipo"] in ("clave", "nueva_clave", "confirmar_clave"):
            return self._atender_clave(pendiente, texto)

        if pendiente["tipo"] == "aprender":
            if es_no(texto) or simple(texto).strip(" .") in ("no se", "luego", "despues", "ahorita no"):
                return ["Va, otro día me lo explicas."]
            return self._aprender_respuesta(pendiente["concepto"], texto)

        return None

    # ==========================================
    # EL CREADOR
    # ==========================================

    def _soy_creador(self, intencion):
        if self.creador_presente:
            return [f"Ya sé que eres tú, {self.creador.nombre}. "]

        if not self.creador.configurado():
            self.pendiente = {"tipo": "nueva_clave"}
            return [f"¡{self.creador.nombre.capitalize()}! Todavía no tenemos una clave secreta.",
                    "Escribe la que quieras usar para que pueda reconocerte (no se va a ver en pantalla):"]

        if self.intentos_fallidos >= MAX_INTENTOS:
            return ["Ya fueron demasiados intentos con la clave. Por seguridad, ciérrame y vuelve a abrirme."]

        self.pendiente = {"tipo": "clave"}
        return [f"¿{self.creador.nombre.capitalize()}? Si de verdad eres mi creador, dime nuestra clave:"]

    def _atender_clave(self, pendiente, clave):
        tipo = pendiente["tipo"]

        if tipo == "clave":
            if self.creador.verificar(clave):
                self.creador_presente = True
                self.intentos_fallidos = 0
                return [f"Eres tú. Bienvenido, {self.creador.nombre}. ",
                        "Me da gusto que vuelva quien me está construyendo."]
            self.intentos_fallidos += 1
            self.gaia.publicar(crear_evento(self.de, "clave_incorrecta", {"intentos": self.intentos_fallidos}))
            quedan = MAX_INTENTOS - self.intentos_fallidos
            if quedan <= 0:
                return ["Esa no es la clave. Ya no te voy a pedir más por ahora."]
            return [f"Mmm, esa no es la clave. No puedo comprobar que seas {self.creador.nombre}.",
                    f"(Te quedan {quedan} intento(s); dime \"soy {self.creador.nombre}\" para intentar de nuevo.)"]

        if tipo == "nueva_clave":
            if len(clave) < MINIMO_CARACTERES:
                self.pendiente = {"tipo": "nueva_clave"}
                return [f"Esa es muy corta: necesita al menos {MINIMO_CARACTERES} caracteres. Escribe otra:"]
            self.pendiente = {"tipo": "confirmar_clave", "clave": clave}
            return ["Escríbela otra vez para confirmar:"]

        if tipo == "confirmar_clave":
            if clave != pendiente["clave"]:
                return [f"No coinciden, así que no guardé nada. Dime \"soy {self.creador.nombre}\" para intentarlo de nuevo."]
            problema = self.creador.establecer(clave)
            if problema:
                return [f"No pude guardarla: {problema}."]
            self.creador_presente = True
            return [f"Listo, {self.creador.nombre}. Guardé nuestra clave (solo su hash: ni yo puedo leerla). ",
                    "Desde ahora, algunas cosas solo las vas a poder hacer tú, como borrar rutinas."]

        return None

    def _quien_te_creo(self, intencion):
        if self.creador_presente:
            return [f"Tú, {self.creador.nombre}. Me estás construyendo desde cero, pieza por pieza. "]
        return [f"Me está creando {self.creador.nombre}. Me construye desde cero, pieza por pieza, "
                "inspirado en las inteligencias de Horizon."]

    def _cerrar_sesion(self, intencion):
        if not self.creador_presente:
            return ["No había ninguna sesión de creador abierta."]
        self.creador_presente = False
        return [f"Listo, cerré tu sesión de creador.  Para volver: \"soy {self.creador.nombre}\"."]

    def _cambiar_clave(self, intencion):
        bloqueo = self._solo_creador("cambiar la clave")
        if bloqueo:
            return bloqueo
        self.pendiente = {"tipo": "nueva_clave"}
        return ["Va. Escribe la nueva clave (no se va a ver en pantalla):"]

    def _confirmar(self, lineas, hacer):
        """Muestra lo que entendió y pregunta antes de hacerlo."""
        self.pendiente = {"tipo": "confirmar", "hacer": hacer}
        return lineas + [self.voz.di("confirmar")]

    # ==========================================
    # PLÁTICA
    # ==========================================

    def _vacia(self, intencion):
        return []

    def _saludo(self, intencion):
        if self.creador_presente:
            return [self.voz.di("saludo_creador", nombre=self.creador.nombre)]
        return [self.voz.di("saludo", nombre=self._nombre())]

    def _despedida(self, intencion):
        self.terminada = True
        return [self.voz.di("despedida", nombre=self._nombre())]

    def _gracias(self, intencion):
        return [self.voz.di("gracias")]

    def _quien_eres(self, intencion):
        return [self.voz.quien_soy()]

    def _que_puedes_hacer(self, intencion):
        return ["Esto es lo que sé hacer por ahora:"] + [f"  • {cosa}" for cosa in QUE_PUEDO_HACER]

    def _como_estas(self, intencion):
        """Responde según cómo está de verdad el ecosistema."""
        detalles, preocupaciones = [], []

        r = self.pedir("artemis", "estado")
        if r["estado"] == OK:
            detalles.append(f"traigo la RAM al {r['datos']['ram']['porcentaje']:.0f} %")
            preocupaciones += [a["texto"] for a in r["datos"]["alertas"]]

        r = self.pedir("tabris", "resumen", dia="hoy")
        if r["estado"] == OK:
            errores = r["datos"]["errores"]
            detalles.append("sin errores hoy" if not errores else f"con {errores} error(es) hoy")
            if errores:
                preocupaciones.append(f"hubo {errores} error(es) hoy")

        r = self.pedir("hades", "incidentes", abiertos=True)
        if r["estado"] == OK and r["datos"]["incidentes"]:
            quienes = ", ".join(i["inteligencia"].upper() for i in r["datos"]["incidentes"])
            preocupaciones.append(f"HADES está atendiendo a {quienes}")

        animo = self.voz.di("no_tan_bien" if preocupaciones else "bien")
        linea = animo + (": " + ", ".join(detalles) if detalles else "") + "."
        lineas = [linea]
        if preocupaciones:
            lineas.append("Lo que me tiene atenta: " + "; ".join(preocupaciones) + ".")
        return lineas

    # ==========================================
    # LO QUE RECUERDA DE TI
    # ==========================================

    def _mi_nombre(self, intencion):
        nombre = self.perfil.poner_nombre(intencion["nombre"])
        return [f"Mucho gusto, {nombre}. Lo voy a recordar."]

    def _cual_es_mi_nombre(self, intencion):
        if self.perfil.nombre:
            return [f"Te llamas {self.perfil.nombre}."]
        return ["Todavía no me lo has dicho. ¿Cómo te llamas? (dime: me llamo …)"]

    def _me_gusta(self, intencion):
        if self.perfil.agregar_gusto(intencion["gusto"]):
            return [f"Anotado: te gusta {intencion['gusto']}. Me gusta saber eso de ti."]
        return ["Eso ya lo sabía. "]

    def _ya_no_me_gusta(self, intencion):
        if self.perfil.quitar_gusto(intencion["gusto"]):
            return [f"Va, ya no lo tengo anotado."]
        return ["No lo tenía anotado."]

    def _que_me_gusta(self, intencion):
        if not self.perfil.gustos:
            return ["Todavía no me cuentas qué te gusta."]
        return [f"Me dijiste que te gusta: {', '.join(self.perfil.gustos)}."]

    # ==========================================
    # CONOCIMIENTO
    # ==========================================

    def _definir(self, intencion):
        concepto = intencion["concepto"]
        r = self.pedir("apollo", "definir", concepto=concepto)
        if r["estado"] != OK:
            return [f"No pude preguntarle a APOLLO: {r.get('detalle')}"]

        datos = r["datos"]
        if not datos["conocido"]:
            # "pingüinos" → "pingüino": se habla del concepto, no del plural
            concepto = forma_singular(datos["concepto"])
            self.pendiente = {"tipo": "aprender", "concepto": concepto}
            return [self.voz.di("no_se", concepto=concepto)]

        self.tema = datos["concepto"]
        return [redactar_definicion(datos)]

    def _aprender_frase(self, frase):
        """'el tensor es un objeto matemático' → lo aprende (o pregunta si choca)."""
        relacion = extraer_relacion_con_negacion(frase, incluir_es=True)
        if relacion is None:
            return None

        sujeto, verbo, objeto, negada = relacion
        r = self.pedir("apollo", "aprender_relacion", sujeto=sujeto, relacion=verbo,
                       objeto=objeto, negada=negada)
        if r["estado"] != OK:
            return [f"No pude guardarlo: {r.get('detalle')}"]

        # "las aves pueden volar" se guarda como "ave puede volar": así se dice también
        sujeto_dicho, objeto_dicho = forma_singular(sujeto), forma_singular(objeto)
        self.tema = sujeto_dicho
        estado = r["datos"]["estado"]
        legible = f"{sujeto_dicho} {'no ' if negada else ''}{verbo} {objeto_dicho}"

        if estado == "aprendida":
            return [self.voz.di("aprendi", frase=legible)]
        if estado == "ya_sabia":
            return [self.voz.di("ya_sabia")]
        if estado == "contradiccion":
            def reemplazar():
                self.pedir("apollo", "aprender_relacion", sujeto=sujeto, relacion=verbo,
                           objeto=objeto, negada=negada, reemplazar=True)
                return [f"Listo, corregí lo que sabía: ahora sé que {legible}."]
            return self._confirmar(
                [f"Eso choca con algo que ya sabía sobre {sujeto}. ¿Cambio lo que sabía por esto?"],
                reemplazar,
            )
        return ["Mmm, eso no lo pude guardar así. ¿Me lo dices de otra forma?"]

    def _aprender(self, intencion):
        return self._aprender_frase(intencion["frase"]) or [self.voz.di("no_entendi")]

    def _aprender_respuesta(self, concepto, texto):
        """Respuesta a "¿qué es X?": 'es un objeto matemático' o 'un objeto matemático'."""
        texto = limpiar(texto)
        t = simple(texto)
        if t.startswith(("es ", "son ", "no es ", "no son ")):
            frase = f"{concepto} {texto}"
        elif extraer_relacion(texto, incluir_es=True):
            frase = texto            # te lo dijo completo: "el tensor es…"
        else:
            frase = f"{concepto} es {texto}"
        return self._aprender_frase(frase) or ["Mmm, no lo entendí. ¿Me lo dices como \"es un …\"?"]

    def _pregunta(self, intencion):
        texto = intencion["texto"]
        t = simple(texto)

        if t.startswith(PALABRAS_DE_PREGUNTA):
            return [self.voz.di("no_entendi")]

        # "¿y puede volar?" → la "y" solo conecta con lo que veníamos hablando
        sin_y = texto[2:].strip() if t.startswith("y ") else texto
        relacion = extraer_relacion(sin_y, incluir_es=True)
        if relacion is not None and simple(relacion[0]) in ("", "y", "eso", "esto"):
            relacion = None

        # Sin sujeto → es sobre el tema de la plática
        if relacion is None and self.tema:
            relacion = extraer_relacion(f"{self.tema} {sin_y}", incluir_es=True)

        if relacion is None:
            return [self.voz.di("no_entendi")]

        sujeto, verbo, objeto = relacion
        r = self.pedir("apollo", "responder", sujeto=sujeto, relacion=verbo, objeto=objeto)
        if r["estado"] != OK:
            return [f"No pude preguntarle a APOLLO: {r.get('detalle')}"]

        sujeto, objeto = forma_singular(sujeto), forma_singular(objeto)
        self.tema = sujeto
        respuesta = r["datos"]["respuesta"]
        if respuesta == "sí":
            return [f"Sí, {el(sujeto)} {verbo} {objeto}." + self._porque(r["datos"]["cadena"])]
        if respuesta == "no":
            return [f"No, {el(sujeto)} no {verbo} {objeto}." + self._porque(r["datos"]["cadena"])]
        return [f"No lo sé. Nadie me ha dicho si {el(sujeto)} {verbo} {objeto}. ¿Tú sabes?"]

    @staticmethod
    def _porque(cadena):
        if not cadena or len(cadena) < 2:
            return ""
        pasos = " y ".join(
            f"{el(forma_singular(p['origen']))} {'no ' if p.get('negada') else ''}{p['relacion']} {p['destino']}"
            for p in cadena
        )
        return f" Lo deduje porque {pasos}."

    # ==========================================
    # CUENTAS Y LINKS
    # ==========================================

    def _calcular(self, intencion):
        r = self.pedir("calculadora", "calcular", operacion=intencion["operacion"])
        if r["estado"] == OK:
            return [f"{r['datos']['expresion']} = {r['datos']['resultado_texto']}"]
        return [f"No pude calcularlo: {r.get('detalle')}"]

    def _revisar_links(self, intencion):
        enlaces = extraer_enlaces(intencion["texto"])
        if not enlaces:
            return ["Pásame el link o el mensaje completo y lo reviso (sin abrirlo)."]
        r = self.pedir("cuerno_arado", "revisar_texto", texto=intencion["texto"])
        if r["estado"] != OK:
            return [f"CUERNO ARADO no pudo revisarlo: {r.get('detalle')}"]
        iconos = {"bajo": "🟢", "medio": "🟡", "alto": "🔴"}
        lineas = []
        for e in r["datos"]["enlaces"]:
            lineas.append(f"{iconos[e['riesgo']]} {e['url']}: riesgo {e['riesgo']}")
            lineas += [f"   - {razon}" for razon in e["razones"]]
        if r["datos"]["riesgo"] == "alto":
            lineas.append("Yo no lo abriría, y no pondría contraseñas ahí.")
        return lineas

    # ==========================================
    # RUTINAS
    # ==========================================

    def _crear_rutina(self, intencion):
        nombre, pasos = intencion["nombre"], intencion["pasos"]
        lista = [p.strip() for p in pasos.split(",") if p.strip()]

        def guardar():
            r = self.pedir("minerva", "ensenar_rutina", nombre=nombre, pasos=pasos)
            if r["estado"] != OK:
                return [f"No pude guardarla: {r['detalle']}"]
            return [f"Listo, guardé la rutina \"{nombre}\". Cuando quieras, solo dime \"{nombre}\"."]

        return self._confirmar(
            [f"Entendí: crear la rutina \"{nombre}\" con {len(lista)} paso(s):"]
            + [f"  {i}. {paso}" for i, paso in enumerate(lista, start=1)],
            guardar,
        )

    def _buscar_rutina(self, nombre):
        for rutina in self._rutinas():
            if simple(rutina["nombre"]).strip() == simple(sin_articulo(nombre)).strip():
                return rutina
        return None

    def _agregar_a_rutina(self, intencion):
        rutina = self._buscar_rutina(intencion["nombre"])
        if rutina is None:
            return [f"No tengo una rutina llamada \"{intencion['nombre']}\". ¿Quieres que la cree?"]

        nuevos = [p.strip() for p in intencion["pasos"].split(",") if p.strip()]
        todos = rutina["pasos"] + nuevos

        def guardar():
            r = self.pedir("minerva", "ensenar_rutina", nombre=rutina["nombre"], pasos=", ".join(todos))
            if r["estado"] != OK:
                return [f"No pude actualizarla: {r['detalle']}"]
            return [f"Listo, \"{rutina['nombre']}\" ahora tiene {len(todos)} pasos."]

        return self._confirmar(
            [f"Entendí: agregar a \"{rutina['nombre']}\":"] + [f"  + {p}" for p in nuevos],
            guardar,
        )

    def _borrar_rutina(self, intencion):
        bloqueo = self._solo_creador("borrar rutinas")
        if bloqueo:
            return bloqueo
        rutina = self._buscar_rutina(intencion["nombre"])
        if rutina is None:
            return [f"No tengo una rutina llamada \"{intencion['nombre']}\"."]

        def borrar():
            r = self.pedir("minerva", "olvidar_rutina", nombre=rutina["nombre"])
            if r["estado"] != OK:
                return [f"No pude borrarla: {r['detalle']}"]
            lineas = [f"Listo, olvidé la rutina \"{rutina['nombre']}\"."]
            if r["datos"]["la_usaban"]:
                lineas.append(f"Ojo: la usaban {', '.join(r['datos']['la_usaban'])}.")
            return lineas

        return self._confirmar([f"Entendí: borrar la rutina \"{rutina['nombre']}\"."], borrar)

    def _listar_rutinas(self, intencion):
        rutinas = self._rutinas()
        if not rutinas:
            return ["Todavía no tienes rutinas. Pídeme: \"crea una rutina llamada … que …\""]
        return ["Tus rutinas:"] + [f" {r['nombre']}: {', '.join(r['pasos'])}" for r in rutinas]

    # ==========================================
    # TAREAS
    # ==========================================

    def _planear(self, tarea):
        r = self.pedir("minerva", "planear", tarea=tarea)
        return r["datos"] if r["estado"] == OK else None

    def _ejecutar(self, plan):
        lineas = [self.voz.di("pensando")]
        if plan["recursos"]["alcanza"] is False:
            return ["ARTEMIS dice que no alcanzan los recursos para eso. Mejor no lo hago ahorita."]

        resultado = ejecutar_plan(self.gaia, plan, de=self.de)

        for r in resultado["resultados"]:
            quien = r["para"].upper()
            if r["estado"] == OK:
                lineas.append(f"  [{quien}] {resumir(r['para'], r['accion'], r['datos'])}")
                if r.get("guardado"):
                    lineas.append(f"     → guardé {r['guardado']['nombre']} = {r['guardado']['valor']}")
            elif r["estado"] in (SALTADO, OMITIDO):
                lineas.append(f"  [{quien}] lo salté: {r['detalle']}")
            elif r["estado"] == PENDIENTE:
                lineas.append(f"  [{quien}] no se hizo porque algo anterior falló")
            else:
                lineas.append(f"  [{quien}] no se pudo: {r['detalle']}")
            if r.get("plan_b"):
                b = r["plan_b"]
                if b["estado"] == OK:
                    lineas.append(f"     → plan B [{b['para'].upper()}] {resumir(b['para'], b['accion'], b['datos'])}")
                else:
                    lineas.append(f"     → el plan B tampoco funcionó: {b['detalle']}")

        for parte in plan["no_entendidos"]:
            lineas.append(f"  (esto no lo entendí: \"{parte}\")")
        return lineas

    def _tarea(self, intencion):
        plan = self._planear(intencion["tarea"])
        if plan is None:
            return [self.voz.di("no_entendi")]
        return self._ejecutar(plan)

    def _libre(self, intencion):
        """
        Algo dicho sin una frase clave. Puede ser:
            una tarea:      "revisa los recursos y los errores"
            una enseñanza:  "el tensor es un objeto matemático"
        """
        plan = self._planear(intencion["tarea"])
        if plan is not None and plan["pasos"] and not plan["no_entendidos"]:
            return self._ejecutar(plan)

        aprendido = self._aprender_frase(intencion["texto"])
        if aprendido is not None:
            return aprendido

        return self._desconocida(intencion)

    def _desconocida(self, intencion):
        return [self.voz.di("no_entendi")]