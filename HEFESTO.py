import numpy as np
import os
import re

from memoria.almacenamiento import (
    cargar_json,
    guardar_json,
    ErrorAlmacenamiento
)

from apollo.conocimiento import (
    cargar_diccionario,
    normalizar_concepto,
    normalizar_texto,
    normalizar_relacion,
    buscar_entrada,
    aprender_palabra,
    aprender_sinonimo,
    buscar_palabra,
    aprender_relacion,
    buscar_relaciones,
    buscar_camino,
    separar_origen_destino,
    extraer_relacion,
    RELACIONES_VALIDAS,
    existe_concepto,
    sugerir_concepto,
    olvidar_relacion,
    olvidar_categoria,
    olvidar_sinonimo,
    olvidar_concepto,
    extraer_relacion_con_negacion,
    ordenar_diccionario
)

from apollo.lenguaje import (
    formas_de_relacion,
    limpiar_concepto,
    expandir_contracciones,
    preguntas_de_relacion
)

from apollo.lector import leer_archivo, guardar_hechos
from apollo.fuentes import documento as fuente_documento, describir as describir_fuente
from apollo.razonamiento import con_fuentes, hechos_con_fuente
from calculo.aritmetica import extraer_operacion
from apollo.lenguaje import quitar_acentos, quitar_signos
from gaia import crear_ecosistema, OK, RECHAZADO
from gaia.tareas import ejecutar_plan, OMITIDO, PENDIENTE, SALTADO
from gaia.mensajes import crear_orden, crear_evento
from gaia.red import InteligenciaRemota
from eleuthia.respaldos import aplicar_restauracion_pendiente, ArchivoOcupado
from cuerno_arado.analisis import extraer_enlaces
from poseidon import Guardia, cargar_clave
import rover.mundo   # también trae rover.HOST y rover.PUERTO
from conversacion.resultados import resumir
from conversacion.redaccion import redactar_definicion
from apollo.lenguaje import forma_singular

from conversacion.contexto import aplicar_contexto, detectar_tema, crear_plantilla
from conversacion.estado import (
    cargar_estado,
    guardar_estado,
    olvidar_estado,
    describir_fecha
)

from apollo.razonamiento import (
    ancestros,
    relaciones_inferidas,
    relaciones_inversas,
    SI,
    NO
)

# ==========================================
# ECOSISTEMA FOCUS
# ==========================================

# GAIA conecta a HEFESTO con las demás inteligencias. HEFESTO ya no
# llama directo a APOLLO ni a la calculadora: les manda mensajes.
#
# Se crea hasta que se necesita (no al importar este archivo), para que
# las pruebas no escriban el registro de TABRIS en la carpeta real.
_ecosistema = None

# Lo que devuelve procesar() (ver preparar_hefesto)
SALIR = "salir"
NO_ENTENDI = "no_entendi"


def usar_ecosistema(gaia):
    """FOCUS le presta su GAIA a HEFESTO, para que los dos usen la misma."""
    global _ecosistema
    _ecosistema = gaia
    gaia.suscribir("sensor_detectado", avisar_sensor_detectado)
    gaia.suscribir("sensor_perdido", avisar_sensor_perdido)


def ecosistema():
    global _ecosistema
    if _ecosistema is None:
        _ecosistema = crear_ecosistema()
        _ecosistema.suscribir("sensor_detectado", avisar_sensor_detectado)
        _ecosistema.suscribir("sensor_perdido", avisar_sensor_perdido)
    return _ecosistema


def avisar_sensor_detectado(evento):
    s = evento["datos"]
    print(f"HEFESTO: 📡 Detecté un sensor nuevo: {s['sensor']} ({s['descripcion']}).")
    print(f"  Está desactivado hasta que lo autorices: autoriza {s['sensor']}")


def avisar_sensor_perdido(evento):
    s = evento["datos"]
    print(f"HEFESTO: ⚠ Dejé de poder leer {s['sensor']}: {s['motivo']}.")


def pedir(para, accion, **datos):
    """
    Le pide algo a otra inteligencia a través de GAIA.
    Devuelve los datos si salió bien; si no, explica qué pasó y
    devuelve None.
    """
    return revisar_respuesta(ecosistema().pedir("hefesto", para, accion, **datos))


def revisar_respuesta(respuesta):
    """Devuelve los datos si salió bien; si no, explica qué pasó y devuelve None."""
    para, accion = respuesta["de"], respuesta["accion"]

    if respuesta["estado"] == OK:
        return respuesta["datos"]

    if respuesta["estado"] == RECHAZADO:
        print(f"HEFESTO: No pude: {respuesta['detalle']}")
    else:
        print(
            f"HEFESTO: Algo falló al pedirle '{accion}' a {para.upper()} "
            f"({respuesta['detalle']})."
        )

    return None


def mostrar_ecosistema():
    """Quién está conectado a GAIA y qué sabe hacer."""
    print("HEFESTO: Inteligencias conectadas a GAIA:")
    for nombre, ficha in ecosistema().directorio().items():
        aislada = "  [AISLADA]" if ficha["aislada"] else ""
        print(f"  {nombre.upper()}{aislada}: {ficha['descripcion']}")
        print(f"    sabe: {', '.join(ficha['acciones'])}")


def comando_simple(comando):
    """'¿Qué pasó hoy?' → 'que paso hoy', para comparar comandos fijos."""
    return " ".join(quitar_acentos(quitar_signos(comando.lower())).split())


def contar(cantidad, singular, plural):
    """contar(1, 'orden', 'órdenes') → '1 orden'; con 3 → '3 órdenes'."""
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def mostrar_registro():
    """Lo que TABRIS vio pasar hoy."""
    r = pedir("tabris", "resumen", dia="hoy")
    if r is None:
        return

    print(
        f"HEFESTO: Según TABRIS, hoy pasaron {contar(r['mensajes'], 'mensaje', 'mensajes')}: "
        f"{contar(r['ordenes'], 'orden', 'órdenes')}, "
        f"{contar(r['rechazos'], 'rechazo', 'rechazos')} y "
        f"{contar(r['errores'], 'error', 'errores')}."
    )

    for nombre, cuantas in sorted(r["por_inteligencia"].items()):
        print(f"  {nombre.upper()}: {contar(cuantas, 'orden', 'órdenes')}")

    if r["ultimo_error"]:
        e = r["ultimo_error"]
        print(f"  Último error: {e['inteligencia'].upper()} al hacer '{e['accion']}' ({e['detalle']})")


def mostrar_incidentes():
    """Los incidentes que HADES tiene abiertos."""
    r = pedir("hades", "incidentes", abiertos=True)
    if r is None:
        return

    if not r["incidentes"]:
        print("HEFESTO: HADES no tiene incidentes abiertos. Todo en orden.")
        return

    print("HEFESTO: Incidentes abiertos según HADES:")
    for i in r["incidentes"]:
        estado = "AISLADA" if i["estado"] == "aislado" else "abierto"
        print(
            f"  #{i['numero']} {i['inteligencia'].upper()} ({estado}): "
            f"{contar(i['fallos'], 'fallo', 'fallos')}, el último: {i['ultimo_detalle']}"
        )
        if i["estado"] == "aislado":
            print(f"     Para intentar recuperarla: recupera {i['inteligencia']}")


def recuperar_inteligencia(nombre):
    """Le pide a HADES que reinicie y libere a una inteligencia."""
    r = pedir("hades", "recuperar", inteligencia=nombre)
    if r is None:
        return

    if r["recuperada"] and not r["estaba_aislada"] and not r["incidentes_cerrados"]:
        print(f"HEFESTO: {nombre.upper()} estaba bien; no había nada que recuperar.")
    elif r["recuperada"]:
        print(
            f"HEFESTO: HADES recuperó a {nombre.upper()} y cerró "
            f"{contar(r['incidentes_cerrados'], 'incidente', 'incidentes')}."
        )
    else:
        print(f"HEFESTO: HADES no pudo recuperar a {nombre.upper()}; sigue aislada.")


def tamano(cantidad_bytes):
    """17066827776 → '15.9 GB'"""
    for unidad in ("bytes", "KB", "MB", "GB"):
        if cantidad_bytes < 1024:
            return f"{cantidad_bytes:.1f} {unidad}" if unidad != "bytes" else f"{cantidad_bytes} bytes"
        cantidad_bytes /= 1024
    return f"{cantidad_bytes:.1f} TB"


def mostrar_recursos():
    """Lo que ARTEMIS ve de la computadora."""
    r = pedir("artemis", "estado")
    if r is None:
        return

    cpu, ram, disco, bateria = r["cpu"], r["ram"], r["disco"], r["bateria"]

    print("HEFESTO: Esto ve ARTEMIS en la computadora:")
    print(f"  CPU:     {cpu['porcentaje']:.0f} % en uso ({contar(cpu['nucleos'], 'núcleo', 'núcleos')})")
    print(f"  RAM:     {ram['porcentaje']:.0f} % en uso; libres {tamano(ram['disponible'])} de {tamano(ram['total'])}")
    print(f"  Disco:   {disco['porcentaje']:.0f} % en uso; libres {tamano(disco['libre'])} de {tamano(disco['total'])}")

    if bateria is None:
        print("  Batería: no tiene (computadora de escritorio o Raspberry Pi)")
    else:
        enchufe = "conectada" if bateria["conectada"] else "sin conectar"
        print(f"  Batería: {bateria['porcentaje']} % ({enchufe})")

    for alerta in r["alertas"]:
        print(f"  ⚠ Ojo: {alerta['texto']}.")


def mostrar_plan(plan):
    """Los pasos que propuso MINERVA, con sus avisos."""
    print(f"HEFESTO: MINERVA lo dividió en {contar(len(plan['pasos']), 'paso', 'pasos')}:")

    for paso in plan["pasos"]:
        linea = f"  {paso['numero']}. {paso['descripcion']}  → {paso['para'].upper()}"
        if paso.get("guardar_como"):
            linea += f"  (se guarda como {paso['guardar_como']})"
        if paso.get("condicion"):
            linea += f"  [solo si {paso['condicion']['texto']}]"
        if paso.get("alternativa"):
            linea += f"  [si falla: {paso['alternativa']['descripcion']}]"
        elif paso.get("si_falla") == "detener":
            linea += "  [si falla: me detengo]"
        if paso["aviso"]:
            linea += f"  ⚠ {paso['aviso']}"
        print(linea)

    for parte in plan["no_entendidos"]:
        print(f"  ?  No entendí: \"{parte}\"")

    recursos = plan["recursos"]
    if recursos["alcanza"] is False:
        print(f"  ⚠ ARTEMIS dice que no alcanza la RAM (faltan {recursos['faltan'].get('ram_mb', '?')} MB).")
    elif recursos["alcanza"] is None:
        print("  (No pude preguntarle a ARTEMIS por los recursos.)")


def planear_tarea(tarea):
    """Solo muestra el plan, sin ejecutarlo."""
    plan = pedir("minerva", "planear", tarea=tarea)
    if plan is not None:
        mostrar_plan(plan)
        if plan["viable"]:
            print("  El plan se puede hacer. Si quieres que lo haga: encárgate de <tarea>")


def mostrar_paso(resultado):
    """Se llama al terminar cada paso, para ir mostrando el avance."""
    numero = resultado["numero"]
    quien = resultado["para"].upper()

    if resultado["estado"] == OK:
        texto = resumir(resultado["para"], resultado["accion"], resultado["datos"])
        print(f"  {numero}. [{quien}] {texto}")
        if resultado.get("guardado"):
            g = resultado["guardado"]
            print(f"       → guardé {g['nombre']} = {g['valor']}")
        elif resultado.get("detalle"):
            print(f"       ({resultado['detalle']})")
    elif resultado["estado"] == SALTADO:
        print(f"  {numero}. [{quien}] Lo salté: {resultado['detalle']}.")
    elif resultado["estado"] == OMITIDO:
        print(f"  {numero}. [{quien}] Lo salté: {resultado['detalle']}.")
    elif resultado["estado"] == PENDIENTE:
        print(f"  {numero}. [{quien}] No se hizo porque un paso anterior falló.")
    else:
        print(f"  {numero}. [{quien}] No se pudo: {resultado['detalle']}")

    # Plan B
    if resultado.get("plan_b"):
        b = resultado["plan_b"]
        quien_b = b["para"].upper()
        if b["estado"] == OK:
            texto = resumir(b["para"], b["accion"], b["datos"])
            print(f"       → plan B: [{quien_b}] {texto}")
            if b.get("guardado"):
                print(f"       → guardé {b['guardado']['nombre']} = {b['guardado']['valor']}")
        else:
            print(f"       → el plan B tampoco funcionó: {b['detalle']}")


def encargarse_de(tarea):
    """MINERVA planea, GAIA reparte y HEFESTO junta los resultados."""
    plan = pedir("minerva", "planear", tarea=tarea)
    if plan is None:
        return

    mostrar_plan(plan)

    if plan["recursos"]["alcanza"] is False:
        print("HEFESTO: No lo voy a hacer: no alcanzan los recursos.")
        return

    print("HEFESTO: Manos a la obra:")
    resultado = ejecutar_plan(ecosistema(), plan, al_terminar_paso=mostrar_paso)

    bien = sum(1 for r in resultado["resultados"] if r["estado"] == OK)
    total = len(resultado["resultados"])

    if resultado["completada"]:
        print(f"HEFESTO: Listo, terminé {contar(total, 'paso', 'pasos')}.")
    else:
        print(f"HEFESTO: Terminé {bien} de {contar(total, 'paso', 'pasos')}.")


# ==========================================
# ROVER (por la red, protegido por POSEIDON)
# ==========================================

def conectar_rover():
    """Busca al rover en la red y lo registra en GAIA."""
    remoto = InteligenciaRemota("rover_1", rover.HOST, rover.PUERTO, Guardia(cargar_clave()))

    if not remoto.conectar():
        print(
            "HEFESTO: No encontré al rover. ¿Ya lo encendiste? En otra terminal: "
            "python -m rover.servidor"
        )
        return

    gaia = ecosistema()
    if remoto.nombre in gaia.inteligencias:
        gaia.retirar(remoto.nombre)   # reconectar: se cambia el representante viejo
    gaia.registrar(remoto)

    print(f"HEFESTO: Conectado con {remoto.nombre.upper()} en {rover.HOST}:{rover.PUERTO}.")
    print(f"  Sabe: {', '.join(sorted(remoto.acciones))}")


def rover_conectado():
    if "rover_1" in ecosistema().inteligencias:
        return True
    print("HEFESTO: El rover no está conectado. Escribe: conecta el rover")
    return False


def mandar_rover(x, y):
    """Le da al rover un objetivo; él decide cómo llegar."""
    if not rover_conectado():
        return

    # Lo que ya se sabe del mapa (ÉTER) viaja con la orden.
    mapa = pedir("eter", "mapa") or {"obstaculos": []}
    conocidos = [o["casilla"] for o in mapa["obstaculos"]]

    orden = crear_orden(
        "hefesto", "rover_1", "ir_a", {"x": x, "y": y, "obstaculos_conocidos": conocidos},
        objetivo=f"llegar a ({x}, {y})",
        restricciones={"bateria_minima": 10},
        si_falla="buscar otra ruta",
    )
    r = revisar_respuesta(ecosistema().enviar(orden))
    if r is None:
        return

    for decision in r["decisiones"]:
        print(f"  ROVER: {decision}")

    # Lo que descubrió se comparte con ÉTER, para la próxima (y para otros robots).
    if r.get("descubiertos"):
        guardado = pedir("eter", "reportar_obstaculos", obstaculos=r["descubiertos"], origen="rover_1")
        if guardado and guardado["nuevos"]:
            print(f"  ÉTER: guardé {contar(guardado['nuevos'], 'obstáculo nuevo', 'obstáculos nuevos')} en el mapa compartido.")

    posicion = f"({r['posicion'][0]}, {r['posicion'][1]})"
    if r["llego"]:
        print(
            f"HEFESTO: El rover llegó a {posicion} en {contar(r['casillas'], 'casilla', 'casillas')}. "
            f"Batería: {r['bateria']} %."
        )
    else:
        print(f"HEFESTO: El rover no llegó; se quedó en {posicion}. Batería: {r['bateria']} %.")
        if r["motivo"] == "bateria":
            print("  Para recargarlo: rover recarga")


def mostrar_rover():
    if not rover_conectado():
        return
    r = pedir("rover_1", "estado")
    if r is None:
        return
    x, y = r["posicion"]
    print(f"HEFESTO: El rover está en ({x}, {y}) con {r['bateria']} % de batería.")
    if r["obstaculos_conocidos"]:
        obstaculos = ", ".join(f"({a}, {b})" for a, b in r["obstaculos_conocidos"])
        print(f"  Obstáculos que ya descubrió: {obstaculos}")


def recargar_rover():
    if rover_conectado() and pedir("rover_1", "recargar") is not None:
        print("HEFESTO: Rover recargado al 100 %.")


# ==========================================
# ENTORNO (ÉTER)
# ==========================================

NOMBRES_DE_TIPO = {
    "señal_wifi": "Señal del WiFi",
    "ruido": "Ruido",
    "temperatura": "Temperatura",
    "humedad": "Humedad",
    "luz": "Luz",
    "distancia": "Distancia",
    "movimiento": "Movimiento",
}


def mostrar_entorno():
    """ÉTER pide lecturas a todos los dispositivos y explica qué significan."""
    r = pedir("eter", "actualizar")
    if r is None:
        return

    if not r["dispositivos"]:
        print("HEFESTO: No hay dispositivos con sensores conectados.")
        return

    e = pedir("eter", "entorno")
    if e is None:
        return

    if not e["sensores"]:
        print("HEFESTO: No hay ningún sensor activo. Escribe 'sensores' para ver por qué.")
        return

    print(f"HEFESTO: Según ÉTER ({contar(len(r['dispositivos']), 'dispositivo', 'dispositivos')}):")
    for s in e["sensores"]:
        valor = f"{s['valor']} {s['unidad']}".strip()
        sentido = f" ({s['etiqueta']})" if s["etiqueta"] else ""
        nombre = NOMBRES_DE_TIPO.get(s["tipo"], s["tipo"].capitalize())
        print(f"  {nombre} en {s['lugar']}: {valor}{sentido}")
        for raro in s["raro"]:
            print(f"     ⚠ {raro}")

    for dispositivo in r["fallaron"]:
        print(f"  ⚠ {dispositivo.upper()} no contestó.")


def dibujar_mapa():
    """El mapa compartido de ÉTER, dibujado en texto."""
    m = pedir("eter", "mapa")
    if m is None:
        return

    obstaculos = {tuple(o["casilla"]) for o in m["obstaculos"]}

    posicion = None
    if "rover_1" in ecosistema().inteligencias and not ecosistema().esta_aislada("rover_1"):
        estado = ecosistema().pedir("hefesto", "rover_1", "estado")
        if estado["estado"] == OK:
            posicion = tuple(estado["datos"]["posicion"])

    print(f"HEFESTO: Mapa compartido de ÉTER ({contar(len(obstaculos), 'obstáculo conocido', 'obstáculos conocidos')}):")
    for y in range(rover.mundo.ALTO - 1, -1, -1):
        fila = []
        for x in range(rover.mundo.ANCHO):
            if (x, y) == posicion:
                fila.append("R")
            elif (x, y) in obstaculos:
                fila.append("#")
            else:
                fila.append("·")
        print(f"  {y} " + " ".join(fila))
    print("    " + " ".join(str(x) for x in range(rover.mundo.ANCHO)))
    print("  R = rover   # = obstáculo   · = libre o sin explorar")


ICONOS_ESTADO = {"activo": "✅", "desactivado": "❌", "pendiente": "⏳"}


def mostrar_sensores():
    """Los sensores reales de esta máquina y su estado."""
    r = pedir("dispositivo_local", "detectar")
    if r is None:
        return

    print("HEFESTO: Sensores reales de esta computadora:")
    for s in r["sensores"]:
        icono = ICONOS_ESTADO.get(s["estado"], "?")
        print(f"  {icono} {s['sensor']}: {s['descripcion']}")
        if s["estado"] == "desactivado":
            print(f"       desactivado: {s['motivo']}")
        elif s["estado"] == "pendiente":
            print(f"       detectado, falta tu permiso: autoriza {s['sensor']}")


def avisar_pendientes():
    """Al arrancar: si hay sensores esperando permiso, decirlo."""
    r = ecosistema().pedir("hefesto", "dispositivo_local", "sensores")
    if r["estado"] != OK:
        return
    pendientes = [s["sensor"] for s in r["datos"]["sensores"] if s["estado"] == "pendiente"]
    if pendientes:
        print(f"📡 Hay {contar(len(pendientes), 'sensor', 'sensores')} esperando tu permiso: "
              f"{', '.join(pendientes)}. Escribe 'sensores' para verlos.")


def autorizar_sensor(sensor):
    r = pedir("dispositivo_local", "autorizar", sensor=sensor)
    if r is not None:
        print(f"HEFESTO: {sensor} autorizado. ÉTER ya lo va a leer.")


def desactivar_sensor(sensor):
    r = pedir("dispositivo_local", "desactivar", sensor=sensor)
    if r is not None:
        print(f"HEFESTO: {sensor} desactivado. Para volver a usarlo: autoriza {sensor}")


def conectar_estacion_simulada():
    """Para pruebas: una estación de mentira con temperatura, humedad y luz."""
    from dispositivos.estacion import EstacionSimulada
    if "estacion_1" in ecosistema().inteligencias:
        print("HEFESTO: La estación simulada ya estaba conectada.")
        return
    ecosistema().registrar(EstacionSimulada())
    print("HEFESTO: Conecté la estación SIMULADA (temperatura, humedad y luz de mentira).")
    print("  Para provocar una alerta: simula temp_cuarto 45")


def simular_sensor(sensor, valor):
    if "estacion_1" not in ecosistema().inteligencias:
        print("HEFESTO: Primero conecta la estación simulada: conecta la estacion simulada")
        return
    r = pedir("estacion_1", "simular", sensor=sensor, valor=valor)
    if r is not None:
        print(f"HEFESTO: La próxima lectura de {sensor} será {valor}. Escribe 'entorno' para verla.")


# ==========================================
# PRIVACIDAD (DEMETER)
# ==========================================

RESPUESTAS_PERMISO = {
    "si": "una vez", "sí": "una vez", "s": "una vez",
    "no": "no", "n": "no",
    "siempre": "siempre",
    "nunca": "nunca",
}


def pedir_permiso(inteligencia, ruta, operacion):
    """
    Le pregunta a DEMETER si se puede tocar un archivo. Si DEMETER no
    tiene una regla, te pregunta a ti. Devuelve True o False.
    """
    r = pedir("demeter", "solicitar", inteligencia=inteligencia, ruta=ruta, operacion=operacion)
    if r is None:
        print("HEFESTO: Como DEMETER no pudo revisarlo, mejor no lo toco.")
        return False

    if r["decision"] == "permitir":
        return True

    if r["decision"] == "negar":
        print(f"HEFESTO: DEMETER no me deja {operacion} archivos de '{r['zona']}' ({r['motivo']}).")
        print(f"  Para cambiarlo: revoca permisos de {r['zona']}")
        return False

    # Preguntar a la persona
    print(f"HEFESTO: 🔒 '{ruta}' está en tu zona protegida '{r['zona']}'.")
    while True:
        try:
            respuesta = input(f"  ¿Dejas que {inteligencia.upper()} lo pueda {operacion}? (sí / no / siempre / nunca): ")
        except (KeyboardInterrupt, EOFError):
            print()
            return False

        eleccion = RESPUESTAS_PERMISO.get(respuesta.strip().lower())
        if eleccion is not None:
            break
        print("  Responde sí, no, siempre o nunca.")

    if eleccion in ("siempre", "nunca"):
        pedir(
            "demeter", "conceder", inteligencia=inteligencia, zona=r["zona"], operacion=operacion,
            decision="permitir" if eleccion == "siempre" else "negar",
        )
        print(f"  Listo, lo recordaré para toda la zona '{r['zona']}'.")

    if eleccion in ("no", "nunca"):
        print("HEFESTO: Va, no lo toco.")

    return eleccion in ("una vez", "siempre")


def mostrar_zonas():
    r = pedir("demeter", "zonas")
    if r is None:
        return
    if not r["zonas"]:
        print("HEFESTO: No hay zonas protegidas. Para agregar una: protege <ruta de la carpeta>")
        return
    print("HEFESTO: Zonas protegidas por DEMETER:")
    for z in r["zonas"]:
        print(f"  🔒 {z['nombre']}: {z['ruta']}")
    print(f"  (La carpeta de FOCUS siempre es libre: {r['carpeta_focus']})")


def mostrar_permisos():
    r = pedir("demeter", "permisos")
    if r is None:
        return
    if not r["reglas"]:
        print("HEFESTO: No hay reglas guardadas; DEMETER te preguntará cada vez.")
        return
    print("HEFESTO: Reglas de DEMETER:")
    for regla in r["reglas"]:
        icono = "✅" if regla["decision"] == "permitir" else "⛔"
        verbo = "puede" if regla["decision"] == "permitir" else "NO puede"
        print(f"  {icono} {regla['inteligencia'].upper()} {verbo} {regla['operacion']} en '{regla['zona']}'")


def proteger_carpeta(ruta):
    r = pedir("demeter", "proteger", ruta=ruta)
    if r is not None:
        print(f"HEFESTO: 🔒 Protegí '{r['zona']['nombre']}' ({r['zona']['ruta']}).")


def desproteger_zona(nombre):
    r = pedir("demeter", "desproteger", nombre=nombre)
    if r is not None:
        print(f"HEFESTO: '{r['zona']['nombre']}' ya no está protegida.")


def revocar_permisos(zona):
    r = pedir("demeter", "revocar", zona=zona)
    if r is not None:
        print(f"HEFESTO: Borré {contar(r['borradas'], 'regla', 'reglas')} de '{zona}'. DEMETER volverá a preguntarte.")


# ==========================================
# PRESERVACIÓN (ELEUTHIA)
# ==========================================

def respaldo_diario():
    """Al arrancar: un respaldo si el último tiene más de un día."""
    r = ecosistema().pedir("hefesto", "eleuthia", "respaldo_al_dia")
    if r["estado"] == OK and r["datos"]["hecho"]:
        print(f"ELEUTHIA: Guardé el respaldo del día ({contar(len(r['datos']['archivos']), 'archivo', 'archivos')}).")


def respaldar_ahora():
    r = pedir("eleuthia", "respaldar")
    if r is not None:
        print(f"HEFESTO: ELEUTHIA guardó {r['nombre']} ({contar(len(r['archivos']), 'archivo', 'archivos')}, {tamano(r['bytes'])}).")


def mostrar_respaldos():
    r = pedir("eleuthia", "respaldos")
    if r is None:
        return
    if not r["respaldos"]:
        print("HEFESTO: Todavía no hay respaldos. Para hacer uno: respalda")
        return
    print(f"HEFESTO: Respaldos de ELEUTHIA (en {r['carpeta']}):")
    for numero, respaldo in enumerate(r["respaldos"], start=1):
        print(f"  {numero}. {respaldo['nombre']}  ({tamano(respaldo['bytes'])})")
    print("  Para volver a uno: restaura <número>")


def restaurar_respaldo(numero):
    lista = pedir("eleuthia", "respaldos")
    if lista is None:
        return
    if not 1 <= numero <= len(lista["respaldos"]):
        print("HEFESTO: Ese número no está en la lista. Escribe 'respaldos' para verla.")
        return

    nombre = lista["respaldos"][numero - 1]["nombre"]
    try:
        seguro = input(f"  ¿Volver a {nombre}? Lo de ahorita se respalda antes, por si acaso (sí / no): ")
    except (KeyboardInterrupt, EOFError):
        return
    if seguro.strip().lower() not in ("si", "sí", "s"):
        print("HEFESTO: Va, no restauré nada.")
        return

    r = pedir("eleuthia", "restaurar", respaldo=nombre)
    if r is not None:
        print(f"HEFESTO: Listo. Lo de ahorita quedó en {r['respaldo_de_seguridad']}.")
        print("  Para terminar de restaurar, apágame (salir) y vuelve a abrirme.")


def mostrar_bitacora():
    r = pedir("eleuthia", "bitacora", dia="hoy")
    if r is None:
        return
    if not r["entradas"]:
        print("HEFESTO: Hoy todavía no hay nada en la bitácora.")
        return
    print("HEFESTO: Bitácora de hoy:")
    for entrada in r["entradas"]:
        hora = entrada["fecha"][11:16]
        print(f"  {hora}  {entrada['texto']}")


def anotar_en_bitacora(texto):
    if pedir("eleuthia", "anotar", texto=texto) is not None:
        print("HEFESTO: Anotado en la bitácora.")


def registrar_experimento():
    """Pregunta los datos de un experimento y se los da a ELEUTHIA."""
    try:
        proyecto = input("  ¿De qué proyecto? ").strip()
        intento = input("  ¿Qué intentaste? ").strip()
        resultado = input("  ¿Cómo salió? (funcionó / falló / a medias): ").strip().lower()
        aprendizaje = input("  ¿Qué aprendiste? (Enter para saltar): ").strip()
    except (KeyboardInterrupt, EOFError):
        return

    resultado = {"funciono": "funcionó", "fallo": "falló", "a medias": "a medias"}.get(
        quitar_acentos(resultado), resultado
    )
    r = pedir("eleuthia", "experimento", proyecto=proyecto, intento=intento,
              resultado=resultado, aprendizaje=aprendizaje)
    if r is not None:
        print("HEFESTO: Experimento guardado.")


def mostrar_experimentos(proyecto=None):
    r = pedir("eleuthia", "experimentos", proyecto=proyecto)
    if r is None:
        return
    if not r["experimentos"]:
        print("HEFESTO: No hay experimentos registrados. Para agregar uno: nuevo experimento")
        return
    s = r["resumen"]
    print(f"HEFESTO: {contar(len(r['experimentos']), 'experimento', 'experimentos')}: "
          f"{s['funcionó']} funcionaron, {s['falló']} fallaron y {s['a medias']} a medias.")
    iconos = {"funcionó": "✅", "falló": "❌", "a medias": "🟡"}
    for e in r["experimentos"]:
        print(f"  {iconos[e['resultado']]} [{e['proyecto']}] {e['intento']}")
        if e["aprendizaje"]:
            print(f"       aprendí: {e['aprendizaje']}")


# ==========================================
# PROTECCIÓN WEB (CUERNO ARADO)
# ==========================================

ICONOS_RIESGO = {"bajo": "🟢", "medio": "🟡", "alto": "🔴"}


def mostrar_enlace(r):
    icono = ICONOS_RIESGO[r["riesgo"]]
    print(f"  {icono} Riesgo {r['riesgo'].upper()}: {r['url']}")
    if r["oficial_de"]:
        print(f"       es el sitio oficial de {r['oficial_de']}")
    for razon in r["razones"]:
        print(f"       - {razon}")
    if r["riesgo"] == "bajo" and not r["razones"] and not r["oficial_de"]:
        print("       no vi nada raro (eso no garantiza que sea seguro)")


def revisar_enlaces(texto):
    """Un link o un mensaje completo con links."""
    r = pedir("cuerno_arado", "revisar_texto", texto=texto)
    if r is None:
        return
    if not r["enlaces"]:
        print("HEFESTO: No encontré ningún link para revisar.")
        return

    print(f"HEFESTO: CUERNO ARADO revisó {contar(len(r['enlaces']), 'link', 'links')} (sin abrirlos):")
    for enlace in r["enlaces"]:
        mostrar_enlace(enlace)

    if r["riesgo"] == "alto":
        print("  ⚠ Mi consejo: no lo abras y no escribas tus contraseñas ahí.")
    print("  (Son pistas, no una garantía. Si dudas, entra escribiendo tú mismo la dirección oficial.)")


def cambiar_lista_web(accion, sitio):
    r = pedir("cuerno_arado", accion, dominio=sitio)
    if r is None:
        return
    if accion == "confiar":
        print(f"HEFESTO: Listo, {r['dominio']} queda como confiable.")
    elif accion == "bloquear":
        print(f"HEFESTO: Listo, {r['dominio']} queda bloqueado.")
    else:
        print(f"HEFESTO: Quité {r['dominio']} de tus listas." if r["estaba"] else f"HEFESTO: {r['dominio']} no estaba en tus listas.")


def mostrar_listas_web():
    r = pedir("cuerno_arado", "listas")
    if r is None:
        return
    print("HEFESTO: Tus listas de CUERNO ARADO:")
    print(f"  🟢 Confiables: {', '.join(r['confiables']) or '(ninguno)'}")
    print(f"  ⛔ Bloqueados: {', '.join(r['bloqueados']) or '(ninguno)'}")


# ==========================================
# LABORATORIO DE INNOVACIÓN (MINERVA)
# ==========================================

ICONOS_CAPACIDAD = {"existe": "✅", "a_medias": "🟡", "falta": "❌"}

ESTADOS_ESCRITOS = {
    "existe": "existe", "listo": "existe", "lista": "existe", "hecho": "existe", "hecha": "existe",
    "a medias": "a_medias", "a_medias": "a_medias", "medias": "a_medias",
    "falta": "falta", "pendiente": "falta",
}

# El proyecto abierto: así no hay que repetir su nombre en cada comando.
proyecto_abierto = None


def barra(porcentaje, ancho=20):
    llenos = round(ancho * porcentaje / 100)
    return "█" * llenos + "░" * (ancho - llenos)


def mostrar_proyecto(nombre):
    global proyecto_abierto
    r = pedir("minerva", "proyecto", nombre=nombre)
    if r is None:
        return
    proyecto_abierto = r["nombre"]

    print(f"HEFESTO: 🧪 {r['nombre']}: {r['meta']}")
    print(f"  Avance: {barra(r['avance'])} {r['avance']} %")

    if not r["capacidades"]:
        print("  Todavía no tiene capacidades. Agrega una: agrega <nombre>")
        return

    for c in r["capacidades"]:
        sangria = "   " * c["nivel"]
        extra = "" if c["es_hoja"] else f"  ({c['avance']} %)"
        print(f"  {sangria}{ICONOS_CAPACIDAD[c['estado']]} #{c['id']} {c['nombre']}{extra}")
        if c["notas"]:
            print(f"  {sangria}      {c['notas']}")

    if r["siguiente"]:
        s = r["siguiente"]
        print(f"  👉 Siguiente sugerido: #{s['id']} {s['nombre']}   (ideas: estrategias {s['id']})")
    else:
        print("  🎉 ¡Todas las capacidades existen!")


def proyecto_actual():
    if proyecto_abierto is None:
        print("HEFESTO: Primero abre un proyecto: proyecto <nombre>  (o escribe 'proyectos')")
    return proyecto_abierto


def mostrar_proyectos():
    r = pedir("minerva", "proyectos")
    if r is None:
        return
    if not r["proyectos"]:
        print("HEFESTO: No hay proyectos en el laboratorio. Para empezar con el de FOCUS: carga el proyecto focus")
        return
    print("HEFESTO: Proyectos del laboratorio:")
    for p in r["proyectos"]:
        print(f"  🧪 {p['nombre']}  {barra(p['avance'], 10)} {p['avance']} %  — {p['meta']}")


def nuevo_proyecto(nombre):
    try:
        meta = input("  ¿Cuál es la meta? ").strip()
    except (KeyboardInterrupt, EOFError):
        return
    if pedir("minerva", "crear_proyecto", nombre=nombre, meta=meta) is not None:
        mostrar_proyecto(nombre)


def cargar_proyecto_focus():
    if pedir("minerva", "cargar_focus") is not None:
        print("HEFESTO: Cargué el mapa de FOCUS en el laboratorio.")
    mostrar_proyecto("FOCUS")


def agregar_capacidad(texto):
    proyecto = proyecto_actual()
    if proyecto is None:
        return
    padre = None
    partes = re.split(r"\s+dentro de\s+#?(\d+)\s*$", texto.strip())
    if len(partes) > 1:
        texto, padre = partes[0], int(partes[1])
    r = pedir("minerva", "agregar_capacidad", proyecto=proyecto, nombre=texto, padre=padre)
    if r is not None:
        print(f"HEFESTO: Agregué #{r['id']} {r['nombre']} (❌ falta).")


def marcar_capacidad(numero, estado_escrito, notas=None):
    proyecto = proyecto_actual()
    if proyecto is None:
        return
    estado = ESTADOS_ESCRITOS.get(estado_escrito.strip().lower())
    if estado is None:
        print("HEFESTO: El estado puede ser: existe, a medias o falta.")
        return
    r = pedir("minerva", "marcar", proyecto=proyecto, capacidad=numero, estado=estado, notas=notas)
    if r is None:
        return
    print(f"HEFESTO: #{r['id']} {r['nombre']} → {ICONOS_CAPACIDAD[r['estado']]}")
    p = pedir("minerva", "proyecto", nombre=proyecto)
    if p is not None:
        print(f"  Avance de {p['nombre']}: {barra(p['avance'])} {p['avance']} %")


def quitar_capacidad(numero):
    proyecto = proyecto_actual()
    if proyecto is None:
        return
    r = pedir("minerva", "quitar_capacidad", proyecto=proyecto, capacidad=numero)
    if r is not None:
        print(f"HEFESTO: Quité {contar(len(r['quitadas']), 'capacidad', 'capacidades')}.")


def mostrar_estrategias(numero):
    proyecto = proyecto_actual()
    if proyecto is None:
        return
    r = pedir("minerva", "estrategias", proyecto=proyecto, capacidad=numero)
    if r is None:
        return
    c = r["capacidad"]
    print(f"HEFESTO: Ideas de MINERVA para #{c['id']} {c['nombre']} ({ICONOS_CAPACIDAD[r['estado']]}):")
    for idea in r["ideas"]:
        print(f"  • {idea['estrategia'].capitalize()}: {idea['idea']}")
    print(f"  Cuando lo intentes: experimento en {c['id']}")


def experimento_en(numero):
    """Un experimento ligado a una capacidad del proyecto abierto."""
    proyecto = proyecto_actual()
    if proyecto is None:
        return
    try:
        intento = input("  ¿Qué intentaste? ").strip()
        resultado = input("  ¿Cómo salió? (funcionó / falló / a medias): ").strip().lower()
        aprendizaje = input("  ¿Qué aprendiste? (Enter para saltar): ").strip()
    except (KeyboardInterrupt, EOFError):
        return

    resultado = {"funciono": "funcionó", "fallo": "falló", "a medias": "a medias"}.get(
        quitar_acentos(resultado), resultado
    )
    r = pedir("eleuthia", "experimento", proyecto=proyecto, capacidad=numero, intento=intento,
              resultado=resultado, aprendizaje=aprendizaje)
    if r is None:
        return
    print("HEFESTO: Experimento guardado.")
    if resultado == "funcionó":
        print(f"  Si ya quedó, márcala: marca {numero} como existe")


def mostrar_siguiente():
    proyecto = proyecto_actual()
    if proyecto is None:
        return
    r = pedir("minerva", "siguiente", proyecto=proyecto)
    if r is None:
        return
    if r["siguiente"] is None:
        print("HEFESTO: 🎉 No falta nada en este proyecto.")
        return
    mostrar_estrategias(r["siguiente"]["id"])


def mostrar_seguridad():
    r = pedir("poseidon", "reporte")
    if r is None:
        return
    if not r["sospechosos"]:
        print("HEFESTO: POSEIDON no ha visto mensajes sospechosos.")
        return
    print(f"HEFESTO: POSEIDON detectó {contar(r['sospechosos'], 'mensaje sospechoso', 'mensajes sospechosos')}:")
    for motivo, cuantos in r["por_motivo"].items():
        print(f"  {motivo}: {cuantos}")


# ==========================================
# RUTINAS (MINERVA)
# ==========================================

def es_rutina(texto):
    r = ecosistema().pedir("hefesto", "minerva", "es_rutina", texto=texto)
    return r["estado"] == OK and r["datos"]["es_rutina"]


def ensenar_rutina(texto):
    """'"checa todo": revisa los recursos y revisa los errores'"""
    if ":" not in texto:
        print('HEFESTO: Escríbela así: enseña la rutina "nombre": paso, paso y paso')
        return
    nombre, pasos = texto.split(":", 1)
    r = pedir("minerva", "ensenar_rutina", nombre=nombre.strip(), pasos=pasos.strip())
    if r is None:
        return
    verbo = "actualizó" if r["reemplazada"] else "aprendió"
    print(f"HEFESTO: MINERVA {verbo} la rutina \"{r['nombre']}\" ({contar(len(r['pasos']), 'paso', 'pasos')}):")
    for numero, paso in enumerate(r["pasos"], start=1):
        print(f"  {numero}. {paso}")
    print(f"  Para usarla: {r['nombre']}")


def mostrar_rutinas():
    r = pedir("minerva", "rutinas")
    if r is None:
        return
    if not r["rutinas"]:
        print('HEFESTO: No hay rutinas. Enséñame una: enseña la rutina "checa todo": revisa los recursos y revisa los errores')
        return
    print("HEFESTO: Rutinas que me enseñaste:")
    for rutina in r["rutinas"]:
        print(f"  🔁 {rutina['nombre']}: {', '.join(rutina['pasos'])}")


def olvidar_rutina(nombre):
    r = pedir("minerva", "olvidar_rutina", nombre=nombre)
    if r is None:
        return
    print(f"HEFESTO: Olvidé la rutina \"{r['nombre']}\".")
    if r["la_usaban"]:
        print(f"  Ojo: la usaban {', '.join(r['la_usaban'])}; ese paso ya no se va a entender.")


def mostrar_errores():
    """Los últimos errores que registró TABRIS."""
    r = pedir("tabris", "buscar", estado="error", cantidad=5)
    if r is None:
        return

    if not r["mensajes"]:
        print("HEFESTO: TABRIS no tiene errores registrados.")
        return

    print("HEFESTO: Últimos errores que registró TABRIS:")
    for m in r["mensajes"]:
        hora = m["fecha"].replace("T", " ")
        print(f"  {hora}  {m['de'].upper()} → {m['accion']}: {m['detalle']}")


# ==========================================
# FUNCIÓN DE ACTIVACIÓN
# ==========================================

def sigmoid(x):
    return 1 / (1 + np.exp(-x))


# ==========================================
# ARCHIVOS DE HEFESTO
# ==========================================

ARCHIVO_MEMORIA = "memoria.json"
ARCHIVO_DATOS = "datos_aprendizaje.json"

MEMORIA_INICIAL = {
    "identidad": {
        "nombre": "HEFESTO",
        "creador": "spanky"
    },
    "conocimientos": []
}

DATOS_INICIALES = {"datos": []}


def cargar_memoria():
    memoria = cargar_json(ARCHIVO_MEMORIA, MEMORIA_INICIAL)

    if not isinstance(memoria, dict) or not isinstance(
        memoria.get("conocimientos"), list
    ):
        raise ErrorAlmacenamiento(
            "La memoria no tiene la estructura esperada."
        )

    return memoria


def guardar_memoria(memoria):
    guardar_json(ARCHIVO_MEMORIA, memoria)


def cargar_datos_aprendizaje():
    datos = cargar_json(ARCHIVO_DATOS, DATOS_INICIALES)

    if not isinstance(datos, dict) or not isinstance(
        datos.get("datos"), list
    ):
        raise ErrorAlmacenamiento(
            "Los datos de aprendizaje no tienen la estructura esperada."
        )

    return datos


def guardar_datos_aprendizaje(datos):
    guardar_json(ARCHIVO_DATOS, datos)


# ==========================================
# CONOCIMIENTOS
# ==========================================

def aprender_conocimiento(tipo, tema, contenido):

    if not all(
        isinstance(valor, str) and valor.strip()
        for valor in (tipo, tema, contenido)
    ):
        print("HEFESTO: Los datos del conocimiento no son válidos.")
        return

    conocimiento = {
        "tipo": tipo.strip(),
        "tema": tema.strip(),
        "contenido": contenido.strip()
    }

    memoria = cargar_memoria()

    conocimientos = memoria.get("conocimientos", [])

    contenido_nuevo = normalizar_concepto(contenido)

    for existente in conocimientos:

        if not isinstance(existente, dict):
            continue

        contenido_existente = existente.get("contenido")

        if not isinstance(contenido_existente, str):
            continue

        if normalizar_concepto(contenido_existente) == contenido_nuevo:
            print("HEFESTO: Ese conocimiento ya existe.")
            return

    memoria["conocimientos"].append(conocimiento)

    guardar_memoria(memoria)

    print("HEFESTO: Conocimiento aprendido.")


# ==========================================
# CAMBIAR / ACTUALIZAR CONOCIMIENTO
# ==========================================

def actualizar_conocimiento(
    tipo,
    tema,
    contenido_nuevo,
    contenido_anterior
):
    memoria = cargar_memoria()

    for conocimiento in memoria.get("conocimientos", []):

        if not isinstance(conocimiento, dict):
            continue

        tipo_guardado = conocimiento.get("tipo", "")
        tema_guardado = conocimiento.get("tema", "")
        temas_guardados = conocimiento.get("temas", [])

        if isinstance(temas_guardados, str):
            temas_guardados = [temas_guardados]

        if not isinstance(temas_guardados, list):
            temas_guardados = []

        # Combinar el tema singular y los temas múltiples.
        temas = list(temas_guardados)

        if isinstance(tema_guardado, str) and tema_guardado:
            temas.append(tema_guardado)

        tema_normalizado = normalizar_concepto(tema)

        tema_encontrado = any(
            isinstance(t, str)
            and normalizar_concepto(t) == tema_normalizado
            for t in temas
        )

        contenido_guardado = conocimiento.get("contenido", "")

        if (
            isinstance(tipo_guardado, str)
            and normalizar_concepto(tipo_guardado)
                == normalizar_concepto(tipo)
            and tema_encontrado
            and isinstance(contenido_guardado, str)
            and normalizar_concepto(contenido_guardado)
                == normalizar_concepto(contenido_anterior)
        ):
            conocimiento["contenido"] = contenido_nuevo
            guardar_memoria(memoria)

            print("HEFESTO: Conocimiento actualizado.")
            return

    print("HEFESTO: No encontré ese conocimiento.")


# ==========================================
# TEMAS CONOCIDOS
# ==========================================

TEMAS = {

    "Focus": [
        "focus"
    ],

    "HEFESTO": [
        "hefesto"
    ],

    "Quantum Robotics": [
        "quantum",
        "quantum robotics"
    ],

    "Batería gravitacional": [
        "batería gravitacional",
        "bateria gravitacional"
    ],

    "Python": [
        "python"
    ],

    "Raspberry Pi": [
        "raspberry pi",
        "raspberry"
    ],

    "ESP32": [
        "esp32",
        "esp-wroom"
    ],

    "Arduino": [
        "arduino"
    ],

    "ROS": [
        "ros",
        "robot operating system"
    ],

    "Robótica": [
        "robótica",
        "robotica",
        "robot"
    ],

    "Programación": [
        "programación",
        "programacion",
        "código",
        "codigo",
        "programa",
        "programar",
        "programando",
        "programado",
        "programador",
        "programadores"
    ],

    "Inteligencia Artificial": [
        "inteligencia artificial",
        "ia",
        "machine learning",
        "aprendizaje automático",
        "aprendizaje automatico",
        "red neuronal"
    ],

    "Matemáticas": [
        "matemáticas",
        "matematicas",
        "matemática",
        "matematica"
    ],

    "Cálculo": [
        "cálculo",
        "calculo",
        "derivada",
        "derivadas",
        "integral",
        "integrales",
        "límite",
        "limite"
    ],

    "Física": [
        "física",
        "fisica",
        "fuerza",
        "velocidad",
        "aceleración",
        "aceleracion",
        "energía",
        "energia",
        "masa",
        "movimiento"
    ],

    "Electrónica": [
        "electrónica",
        "electronica",
        "voltaje",
        "corriente",
        "resistencia",
        "circuito",
        "circuitos",
        "amperaje",
        "potencia"
    ]
}


# ==========================================
# ANALIZAR CONOCIMIENTO
# ==========================================

def analizar_conocimiento(contenido):

    texto = contenido.lower()

    tipo = "sin_categoria"
    temas = []

    # =========================
    # CONSULTAR DICCIONARIO
    # =========================

    diccionario = cargar_diccionario()

    asociaciones_aprendidas = []

    for entrada in diccionario["palabras"]:

        palabra = entrada["palabra"].lower()

        if palabra in texto:

            for asociacion in entrada.get("asociaciones", []):

                if asociacion not in asociaciones_aprendidas:
                    asociaciones_aprendidas.append(asociacion)

    # =========================
    # AGREGAR TEMAS APRENDIDOS
    # =========================

    for asociacion in asociaciones_aprendidas:

        if asociacion not in temas:
            temas.append(asociacion)

    # =========================
    # DETECTAR TEMAS
    # =========================

    for nombre_tema, palabras in TEMAS.items():

        for palabra in palabras:

            if palabra in texto:
                temas.append(nombre_tema)
                break

    # =========================
    # DETECTAR TIPO
    # =========================

    palabras_hardware = [
        "cámara", "camara", "sensor", "raspberry", "esp32",
        "arduino", "motor", "motorreductor", "batería", "bateria",
        "pantalla", "display", "micrófono", "microfono", "altavoz",
        "bocina", "led", "botón", "boton", "cable", "resistencia",
        "capacitor", "transistor", "chip", "procesador", "placa",
        "microcontrolador", "servo", "encoder", "actuador",
        "relevador", "relay"
    ]

    palabras_software = [
        "python", "programa", "programación", "programacion",
        "código", "codigo", "software", "algoritmo", "función",
        "funcion", "variable", "clase", "script", "biblioteca",
        "librería", "libreria", "módulo", "modulo", "json",
        "numpy", "ros", "programando", "programado",
        "programador", "programadores"
    ]

    palabras_ia = [
        "inteligencia artificial", "ia", "neurona", "red neuronal",
        "machine learning", "aprendizaje automático",
        "aprendizaje automatico", "entrenamiento", "modelo",
        "predicción", "prediccion", "clasificación",
        "clasificacion", "dataset", "inferencia"
    ]

    palabras_fisica = [
        "voltaje", "tensión", "corriente", "amperaje", "amperios",
        "voltios", "resistencia", "potencia", "energía", "energia",
        "fuerza", "masa", "peso", "velocidad", "aceleración",
        "aceleracion", "distancia", "trabajo", "movimiento",
        "torque", "par", "frecuencia", "carga"
    ]

    palabras_matematicas = [
        "matemáticas", "matematicas", "ecuación", "ecuacion",
        "derivada", "integral", "límite", "limite", "vector",
        "matriz", "probabilidad", "estadística", "estadistica",
        "álgebra", "algebra", "geometría", "geometria",
        "trigonometría", "trigonometria"
    ]

    # =========================
    # ASIGNAR TIPO
    # =========================

    if any(palabra in texto for palabra in palabras_hardware):
        tipo = "hardware"

    elif any(palabra in texto for palabra in palabras_software):
        tipo = "software"

    elif any(palabra in texto for palabra in palabras_ia):
        tipo = "inteligencia_artificial"

    elif any(palabra in texto for palabra in palabras_fisica):
        tipo = "fisica_electronica"

    elif any(palabra in texto for palabra in palabras_matematicas):
        tipo = "matematicas"

    conocimiento = {
        "tipo": tipo,
        "temas": temas,
        "contenido": contenido
    }

    print("ANALIZADOR:", conocimiento)

    return conocimiento


# ==========================================
# GUARDAR CONOCIMIENTO
# ==========================================

def guardar_conocimiento(conocimiento):

    if not isinstance(conocimiento, dict):
        print("HEFESTO: Formato de conocimiento inválido.")
        return

    contenido_nuevo = conocimiento.get("contenido")

    if not isinstance(contenido_nuevo, str) or not contenido_nuevo.strip():
        print("HEFESTO: El contenido del conocimiento es inválido.")
        return

    memoria = cargar_memoria()
    conocimientos = memoria.get("conocimientos", [])

    contenido_normalizado = normalizar_concepto(contenido_nuevo)

    for existente in conocimientos:

        if not isinstance(existente, dict):
            continue

        contenido_existente = existente.get("contenido", "")

        if not isinstance(contenido_existente, str):
            continue

        if normalizar_concepto(contenido_existente) == contenido_normalizado:
            print("HEFESTO: Ese conocimiento ya existe.")
            return

    memoria["conocimientos"].append(conocimiento)
    guardar_memoria(memoria)

    print("HEFESTO: Conocimiento guardado.")


# ==========================================
# DATOS DE APRENDIZAJE
# ==========================================

def guardar_dato_aprendizaje(entrada, objetivo):

    datos = cargar_datos_aprendizaje()

    datos["datos"].append({
        "entrada": entrada,
        "objetivo": objetivo
    })

    guardar_datos_aprendizaje(datos)

    print("HEFESTO: Ejemplo de aprendizaje guardado.")


def preparar_datos_aprendizaje():

    datos = cargar_datos_aprendizaje()

    entradas = []
    objetivos = []

    for dato in datos["datos"]:
        entradas.append(dato["entrada"])
        objetivos.append(dato["objetivo"])

    return (
        np.array(entradas),
        np.array(objetivos)
    )


# ==========================================
# RED NEURONAL
# ==========================================

class RedNeuronal:

    # ======================================
    # CONSTRUCTOR
    # ======================================

    def __init__(self, entradas, ocultas, salidas, tasa):

        self.tasa = tasa

        self.pesos_ocultos = np.random.randn(ocultas, entradas)
        self.bias_ocultos = np.zeros(ocultas)

        self.pesos_salida = np.random.randn(salidas, ocultas)
        self.bias_salida = np.zeros(salidas)

    # ======================================
    # PREDICCIÓN
    # ======================================

    def predecir(self, entrada):

        entrada = np.array(entrada)

        resultado_oculto = (
            np.dot(entrada, self.pesos_ocultos.T)
            + self.bias_ocultos
        )

        activacion_oculta = sigmoid(resultado_oculto)

        resultado_salida = (
            np.dot(self.pesos_salida, activacion_oculta)
            + self.bias_salida
        )

        activacion_salida = sigmoid(resultado_salida)

        return activacion_salida

    # ======================================
    # APRENDER
    # ======================================

    def aprender(self, entradas, objetivos, epocas):

        print("Estoy aprendiendo...")

        self.crear_backup()

        error_final = self.entrenar(entradas, objetivos, epocas)

        self.guardar_modelo("hefesto_modelo_v2.npz")

        print("Error final:", error_final)
        print("He terminado de aprender.")

        return error_final

    # ======================================
    # ENTRENAMIENTO
    # ======================================

    def entrenar(self, entradas, objetivos, epocas):

        error_total = 0

        for epoca in range(epocas):

            error_total = 0

            for i in range(len(entradas)):

                entrada = entradas[i]
                objetivo = objetivos[i]

                # Propagación hacia adelante.
                resultado_oculto = (
                    np.dot(entrada, self.pesos_ocultos.T)
                    + self.bias_ocultos
                )

                activacion_oculta = sigmoid(resultado_oculto)

                resultado_salida = (
                    np.dot(self.pesos_salida, activacion_oculta)
                    + self.bias_salida
                )

                activacion_salida = sigmoid(resultado_salida)

                error = objetivo - activacion_salida

                error_total += np.sum(np.abs(error))

                # Retropropagación.
                delta_salida = activacion_salida - objetivo

                derivadas_ocultas = (
                    activacion_oculta
                    * (1 - activacion_oculta)
                )

                delta_oculta = (
                    self.pesos_salida.T @ delta_salida
                ) * derivadas_ocultas

                grad_pesos_salida = np.outer(
                    delta_salida,
                    activacion_oculta
                )
                grad_bias_salida = delta_salida

                grad_pesos_ocultos = np.outer(delta_oculta, entrada)
                grad_bias_ocultos = delta_oculta

                # Actualizar pesos.
                self.pesos_salida -= self.tasa * grad_pesos_salida
                self.bias_salida -= self.tasa * grad_bias_salida
                self.pesos_ocultos -= self.tasa * grad_pesos_ocultos
                self.bias_ocultos -= self.tasa * grad_bias_ocultos

            if epoca % 1000 == 0:
                print("Época:", epoca, "Error total:", error_total)

        return error_total

    # ======================================
    # EVALUACIÓN
    # ======================================

    def evaluar(self, entradas, objetivos):

        aciertos = 0

        for i in range(len(entradas)):

            prediccion = self.predecir(entradas[i])

            resultado = 1 if prediccion[0] >= 0.5 else 0

            print(
                entradas[i], "→", prediccion, "→", resultado,
                "→ objetivo:", objetivos[i]
            )

            if resultado == objetivos[i]:
                aciertos += 1

        precision = aciertos / len(entradas)

        print("\nHEFESTO: Evaluación completada.")
        print("Aciertos:", aciertos)
        print("Total:", len(entradas))
        print("Precisión:", precision * 100, "%")

    # ======================================
    # CALCULAR ERROR
    # ======================================

    def calcular_error(self, entradas, objetivos):

        errores = []

        for i in range(len(entradas)):

            prediccion = self.predecir(entradas[i])

            error = np.mean(np.abs(prediccion - objetivos[i]))

            errores.append(error)

        return np.mean(errores)

    # ======================================
    # GUARDAR MODELO
    # ======================================

    def guardar_modelo(self, archivo):

        np.savez(
            archivo,
            pesos_ocultos=self.pesos_ocultos,
            bias_ocultos=self.bias_ocultos,
            pesos_salida=self.pesos_salida,
            bias_salida=self.bias_salida
        )

        print("Modelo guardado correctamente.")

    # ======================================
    # CREAR BACKUP
    # ======================================

    def crear_backup(self):

        self.guardar_modelo("hefesto_modelo_v2_backup.npz")

        print("HEFESTO: Backup del modelo V2 creado.")

    # ======================================
    # CARGAR MODELO
    # ======================================

    def cargar_modelo(self, archivo):

        modelo = np.load(archivo)

        self.pesos_ocultos = modelo["pesos_ocultos"]
        self.bias_ocultos = modelo["bias_ocultos"]
        self.pesos_salida = modelo["pesos_salida"]
        self.bias_salida = modelo["bias_salida"]


# ==========================================
# DATOS XOR
# ==========================================

entradas = np.array([
    [0, 0],
    [0, 1],
    [1, 0],
    [1, 1]
])

objetivos = np.array([
    0,
    1,
    1,
    0
])


# ==========================================
# ENTENDER ERRORES DE ESCRITURA
# ==========================================

def resolver_concepto(texto):
    """
    Si Hefesto no conoce el concepto pero se parece a uno que sí,
    pregunta si era ese. Devuelve el concepto a usar.
    """

    if existe_concepto(texto):
        return texto

    sugerencia = sugerir_concepto(texto)

    if sugerencia is None:
        return texto

    respuesta = input(
        f"HEFESTO: No conozco '{texto}'. "
        f"¿Quisiste decir '{sugerencia}'? (s/n): "
    ).strip().lower()

    if respuesta == "s":
        return sugerencia

    return texto


# ==========================================
# APRENDER: CÓMO DECIRLO
# ==========================================
# APOLLO devuelve un resultado con un "estado"; aquí se traduce
# cada estado a una frase. Si mañana HEFESTO habla por voz o en
# una página web, solo cambia esta parte, no APOLLO.

def flecha(r):
    """'sensor → NO mide → humedad'"""
    no = "NO " if r.get("negada") else ""
    return f"{r['sujeto']} → {no}{r['relacion']} → {r['objeto']}"


MENSAJES = {
    # aprender_palabra
    "nueva": "Aprendí la palabra {palabra} y su asociación con {asociacion}.",
    "asociada": "Aprendí que {palabra} está relacionado con {asociacion}.",
    # aprender_sinonimo
    "aprendido": "Aprendí que '{sinonimo}' es sinónimo de '{palabra}'.",
    "ya_registrado": "'{sinonimo}' ya está registrado.",
    "desconocido": "No conozco el concepto '{palabra}'. Enséñamelo primero.",
    "iguales": "Ambos términos son iguales.",
    # aprender_relacion
    "aprendida": "Aprendí la relación {flecha}.",
    "relacion_invalida": "Todavía no reconozco la relación '{relacion}'. No la guardaré.",
    "mismo_concepto": "El sujeto y el objeto son iguales. Revisa esa relación.",
    # comunes
    "ya_sabia": "Ya lo sabía.",
    "vacio": "No puedo aprender términos vacíos.",
}


def anunciar(r):
    """Dice en voz de HEFESTO el resultado de aprender algo."""
    datos = dict(r)

    if "relacion" in r and "sujeto" in r:
        datos["flecha"] = flecha(r)

    plantilla = MENSAJES.get(r["estado"], "Listo ({estado}).")
    texto = plantilla.format(**datos)
    print("HEFESTO: " + texto)

    # Lo nuevo que aprendió queda en la bitácora de ELEUTHIA.
    # (Solo si el ecosistema ya está encendido: no se enciende solo para esto.)
    if _ecosistema is not None and r["estado"] in ESTADOS_NUEVOS:
        _ecosistema.publicar(crear_evento("hefesto", "aprendizaje", {"texto": texto}))


def aprender_relacion_conversando(sujeto, relacion, objeto, negada=False):
    """
    Pide a APOLLO aprender una relación. Si hay una contradicción,
    pregunta al usuario y, si acepta, le pide a APOLLO reemplazar.
    """
    r = aprender_relacion(sujeto, relacion, objeto, negada)

    if r["estado"] != "contradiccion":
        anunciar(r)
        return

    print("HEFESTO: Esto contradice algo que ya sé:")

    for conflicto in r["conflictos"]:
        print(f"  {flecha(conflicto)}")

    if not confirmar(f"¿Lo cambio por {flecha(r)}?"):
        print("HEFESTO: Me quedo con lo que ya sabía.")
        return

    anunciar(aprender_relacion(sujeto, relacion, objeto, negada, reemplazar=True))


# ==========================================
# LEER DOCUMENTOS
# ==========================================

CARPETA_DOCUMENTOS = "documentos"
EXTENSIONES_TEXTO = (".txt", ".md")
ESTADOS_NUEVOS = {"nueva", "asociada", "aprendido", "aprendida"}


def describir_hecho(hecho):
    """Un hecho leído, en forma de flecha."""
    sujeto = forma_singular(hecho["sujeto"])

    if hecho["tipo"] == "categoria":
        return f"{sujeto} → es → {forma_singular(hecho['objeto'])}"

    if hecho["tipo"] == "sinonimo":
        return f"{hecho['sujeto']} ↔ {hecho['objeto']}  (mismo concepto)"

    no = "NO " if hecho["negada"] else ""
    return f"{sujeto} → {no}{hecho['relacion']} → {hecho['objeto']}"


def encontrar_documento(texto):
    """Busca el archivo tal cual o dentro de la carpeta documentos."""
    ruta = texto.strip().strip('"').strip("'")

    for candidata in (ruta, os.path.join(CARPETA_DOCUMENTOS, ruta)):
        if os.path.isfile(candidata):
            return candidata

    return None


def elegir_hechos(hechos):
    """
    Pregunta qué guardar: s = todo, n = nada,
    o los números de los que NO se quieren (ej. '2 5').
    """
    respuesta = input(
        "HEFESTO: ¿Qué guardo? "
        "(s = todo, n = nada, o los números que NO quieres, ej. 2 5): "
    ).strip().lower()

    if respuesta in ("s", "si", "sí", "todo"):
        return hechos

    numeros = {int(n) for n in re.findall(r"\d+", respuesta)}

    if not numeros:
        return []

    return [h for i, h in enumerate(hechos, start=1) if i not in numeros]


def leer_documento(texto_ruta):
    """Lee un documento, muestra lo que entendió y guarda lo que elijas."""

    ruta = encontrar_documento(texto_ruta)

    if ruta is None:
        print(
            f"HEFESTO: No encontré '{texto_ruta.strip()}'. "
            f"Ponlo en la carpeta '{CARPETA_DOCUMENTOS}' o escribe la ruta completa."
        )
        return

    if not ruta.lower().endswith(EXTENSIONES_TEXTO):
        print("HEFESTO: Por ahora solo sé leer archivos de texto (.txt o .md).")
        return

    if not pedir_permiso("hefesto", ruta, "leer"):
        return

    lectura = leer_archivo(ruta)
    hechos = lectura["hechos"]
    no_entendidas = lectura["no_entendidas"]

    if not hechos:
        print(f"HEFESTO: Leí {ruta}, pero no encontré nada que pudiera aprender.")
        return

    print(f"HEFESTO: Leí {ruta}. Esto es lo que entendí:")

    for numero, hecho in enumerate(hechos, start=1):
        print(f"  {numero:>2}. {describir_hecho(hecho)}")

    if no_entendidas:
        print(f"HEFESTO: Y no entendí {len(no_entendidas)} oración(es):")

        for oracion in no_entendidas[:10]:
            print(f"   - {oracion}")

        if len(no_entendidas) > 10:
            print(f"   ... y {len(no_entendidas) - 10} más.")

    elegidos = elegir_hechos(hechos)

    if not elegidos:
        print("HEFESTO: Va, no guardé nada.")
        return

    # Cada hecho queda anotado con el documento de donde salió.
    resultados = guardar_hechos(elegidos, fuente=fuente_documento(os.path.basename(ruta)))

    nuevos = sum(1 for _, r in resultados if r["estado"] in ESTADOS_NUEVOS)
    sabidos = sum(1 for _, r in resultados if r["estado"] == "ya_sabia")
    choques = [(h, r) for h, r in resultados if r["estado"] == "contradiccion"]
    fallidos = [
        (h, r) for h, r in resultados
        if r["estado"] not in ESTADOS_NUEVOS | {"ya_sabia", "contradiccion"}
    ]

    print(f"HEFESTO: Aprendí {nuevos} cosa(s) nueva(s). Ya sabía {sabidos}.")

    if choques:
        print("HEFESTO: Estas contradicen lo que sé y no las guardé:")
        for hecho, r in choques:
            print(f"  - {describir_hecho(hecho)}")
            for conflicto in r["conflictos"]:
                print(f"      (yo sé: {flecha(conflicto)})")
        print("  Si alguna es correcta, enséñamela con 'aprende que...'.")

    if fallidos:
        print("HEFESTO: Estas no las pude guardar:")
        for hecho, r in fallidos:
            print(f"  - {describir_hecho(hecho)} ({r['estado']})")


# ==========================================
# OLVIDAR
# ==========================================

SEPARADORES_SINONIMO = (
    " es sinónimo de ",
    " es sinonimo de ",
    " significa ",
    " quiere decir ",
    " equivale a ",
)


def confirmar(pregunta):
    """Pide confirmación (s/n). Se usa antes de borrar cosas grandes."""
    return input(f"HEFESTO: {pregunta} (s/n): ").strip().lower() == "s"


def olvidar_frase(frase):
    """
    Interpreta 'olvida que <frase>' y borra lo que corresponda:
    un sinónimo, una relación o una categoría.
    """

    # 1. ¿Es un sinónimo?
    for separador in SEPARADORES_SINONIMO:
        if separador in frase:
            a, b = frase.split(separador, 1)
            a, b = limpiar_concepto(a), limpiar_concepto(b)

            if olvidar_sinonimo(a, b):
                print(f"HEFESTO: Olvidé que '{a}' es sinónimo de '{b}'.")
            else:
                print(f"HEFESTO: No sabía que '{a}' fuera sinónimo de '{b}'.")
            return

    # 2. ¿Es una relación? (mide, usa, NO puede...)
    resultado = (
        extraer_relacion_con_negacion(frase)
        or negacion_de_categoria(frase)
    )

    if resultado:
        sujeto, relacion, objeto, negada = resultado
        no = "NO " if negada else ""

        if olvidar_relacion(sujeto, relacion, objeto, negada):
            print(f"HEFESTO: Olvidé que {sujeto} → {no}{relacion} → {objeto}.")
        else:
            print(
                f"HEFESTO: No tenía guardado que "
                f"{sujeto} → {no}{relacion} → {objeto}."
            )
        return

    # 3. ¿Es una categoría? (X es Y / X son Y)
    resultado = extraer_relacion(frase, incluir_es=True)

    if resultado:
        concepto, _, categoria = resultado

        if olvidar_categoria(concepto, categoria):
            print(f"HEFESTO: Olvidé que {concepto} es {categoria}.")
        else:
            print(f"HEFESTO: No tenía guardado que {concepto} es {categoria}.")
        return

    print(
        "HEFESTO: No entendí qué debo olvidar. "
        "Ejemplo: olvida que el sensor mide la humedad"
    )


def olvidar_todo_sobre(concepto):
    """Borra un concepto completo, pidiendo confirmación."""

    if not existe_concepto(concepto):
        print(f"HEFESTO: No sé nada sobre {concepto}.")
        return

    if not confirmar(
        f"¿Seguro que quieres que olvide TODO sobre {concepto}?"
    ):
        print("HEFESTO: No olvidé nada.")
        return

    nombre, menciones = olvidar_concepto(concepto)

    if nombre is None:
        print(f"HEFESTO: No tenía información propia de {concepto}.")
        return

    print(f"HEFESTO: Olvidé todo lo que sabía de {nombre}.")

    if menciones:
        print(
            f"HEFESTO: Ojo: otros conceptos todavía lo mencionan "
            f"en {menciones} relación(es). Pregunta "
            f"'qué sabes de {nombre}' para verlas."
        )


def olvidar_recuerdo(texto):
    """Borra recuerdos de la memoria que contengan el texto."""

    memoria = cargar_memoria()
    buscado = normalizar_texto(texto)

    coincidencias = [
        conocimiento
        for conocimiento in memoria["conocimientos"]
        if isinstance(conocimiento, dict)
        and buscado in normalizar_texto(str(conocimiento.get("contenido", "")))
    ]

    if not coincidencias:
        print(f"HEFESTO: No tengo recuerdos que digan '{texto}'.")
        return

    if len(coincidencias) == 1:
        elegido = coincidencias[0]

        if not confirmar(f"¿Olvido el recuerdo '{elegido['contenido']}'?"):
            print("HEFESTO: No olvidé nada.")
            return

    else:
        print("HEFESTO: Encontré varios recuerdos:")

        for numero, conocimiento in enumerate(coincidencias, start=1):
            print(f"  {numero}. {conocimiento['contenido']}")

        respuesta = input(
            "HEFESTO: ¿Cuál olvido? (número, o Enter para ninguno): "
        ).strip()

        if not respuesta.isdigit() or not 1 <= int(respuesta) <= len(coincidencias):
            print("HEFESTO: No olvidé nada.")
            return

        elegido = coincidencias[int(respuesta) - 1]

    memoria["conocimientos"].remove(elegido)
    guardar_memoria(memoria)

    print(f"HEFESTO: Olvidé el recuerdo '{elegido['contenido']}'.")


# ==========================================
# RAZONAMIENTO: CÓMO PRESENTARLO
# ==========================================

PALABRAS_DE_PREGUNTA = (
    "qué", "que", "quién", "quien", "cómo", "como", "cuál", "cual",
    "dónde", "donde", "cuándo", "cuando", "por qué", "por que",
    "con qué", "con que", "dime"
)


# Formas de preguntar por cada relación (las genera APOLLO).
PREGUNTAS_DE_RELACION = [
    (inicio + " ", relacion) for inicio, relacion in preguntas_de_relacion()
]


def negacion_de_categoria(frase):
    """
    'el pingüino no es un mamífero' → ('pingüino', 'es', 'mamífero', True).
    Solo para negaciones: 'X es Y' se sigue guardando como asociación.
    """
    resultado = extraer_relacion_con_negacion(frase, incluir_es=True)

    if resultado and resultado[1] == "es" and resultado[3]:
        return resultado

    return None


def mostrar_cadena(cadena, sangria="  "):
    """
    Imprime los pasos de un razonamiento, cada uno con de dónde lo sacó:
        pingüino → es → ave   (me lo dijiste tú hoy)
    """
    for paso in con_fuentes(cadena):
        print(
            f"{sangria}{paso['origen']} → "
            f"{paso['relacion']} → {paso['destino']}   ({describir_fuente(paso['fuente'])})"
        )


def mostrar_fuentes(concepto):
    """'fuentes de pingüino': lo que sé de él y de dónde salió cada cosa."""
    entrada = buscar_entrada(concepto)
    if entrada is None:
        print(f"HEFESTO: No sé nada de {concepto}.")
        return

    hechos = hechos_con_fuente(concepto)
    if not hechos:
        print(f"HEFESTO: Conozco {entrada['palabra']}, pero no sé nada directo de él.")
        return

    print(f"HEFESTO: Lo que sé de {entrada['palabra']} y de dónde lo saqué:")
    for hecho in hechos:
        print(f"  {describir_hecho_guardado(entrada['palabra'], hecho)}   ({describir_fuente(hecho['fuente'])})")


def describir_hecho_guardado(sujeto, hecho):
    """{"tipo": "puede", "objeto": "volar", "negada": True} → 'pingüino NO puede volar'"""
    if hecho["tipo"] == "sinonimo":
        return f"{sujeto} también se llama {hecho['objeto']}"
    return f"{sujeto} {'NO ' if hecho['negada'] else ''}{hecho['tipo']} {hecho['objeto']}"


def parsear_pregunta_inversa(texto):
    """
    'quién mide la temperatura' → ('mide', 'temperatura')
    'qué cosa produce calor'    → ('produce', 'calor')
    Devuelve None si no es una pregunta de ese tipo.
    """
    texto = texto.replace("¿", "").replace("?", "").strip()

    for inicio in ("quién ", "quien ", "qué cosa ", "que cosa "):

        if not texto.startswith(inicio):
            continue

        resto = texto[len(inicio):]

        for forma, oficial in formas_de_relacion(incluir_es=True):
            if resto.startswith(forma + " "):
                objeto = limpiar_concepto(resto[len(forma):])
                if objeto:
                    return oficial, objeto

    return None


def parsear_pregunta_si_no(comando):
    """
    '¿la raspberry pi necesita electricidad?'
        → ('raspberry pi', 'necesita', 'electricidad')
    Solo si parece pregunta y no empieza con qué/quién/cómo...
    """
    if "?" not in comando and "¿" not in comando:
        return None

    texto = normalizar_texto(comando.replace("¿", "").replace("?", ""))

    if texto.startswith(PALABRAS_DE_PREGUNTA):
        return None

    return extraer_relacion(texto, incluir_es=True)


# ==========================================
# CALCULAR
# ==========================================

def mostrar_calculo(operacion):
    """Resuelve una operación y explica cada paso."""
    r = pedir("calculadora", "calcular", operacion=operacion)
    if r is None:
        return

    print(f"HEFESTO: {r['expresion']} = {r['resultado_texto']}")

    if len(r["pasos"]) <= 1:
        return

    for numero, paso in enumerate(r["pasos"], start=1):
        razon = f"   ({paso['razon']})" if paso["razon"] else ""
        print(f"  {numero}. {paso['operacion']}{razon}")
        if numero < len(r["pasos"]):
            print(f"     → {paso['queda']}")


# ==========================================
# AYUDA
# ==========================================

AYUDA = """
HEFESTO: Esto es lo que sé hacer:

  APRENDER
    aprende que <algo> es <descripción>
        aprende que la raspberry pi es una computadora
    aprende que <algo> <relación> <algo>
        aprende que los sensores miden la temperatura
    aprende que <algo> es sinónimo de <otro nombre>
        aprende que raspberry pi es sinónimo de rpi
    aprende que <algo> no <relación> <algo>
        aprende que el pingüino no puede volar
    recuerda <una idea>
        recuerda Focus tendrá sensores de temperatura

  PREGUNTAR
    define <algo>  /  qué es <algo>   te lo explico con mis palabras
    qué sabes de <algo>
    fuentes de <algo>        lo que sé de algo y de dónde salió cada cosa
    qué mide / controla / usa / necesita / produce ... <algo>
    con qué se comunica <algo>
    camino <origen> <destino>
        camino raspberry pi temperatura
    recuerdos

  CONVERSACIÓN (recuerdo de qué hablamos)
    qué sabes del pingüino
    ¿y puede nadar?          → entiendo que hablas del pingüino
    ¿y qué tiene?
    qué más sabes de él
    ¿y el gorrión también?   → repite tu última pregunta con el gorrión
    ¿y del sensor?           → lo mismo, con el sensor
    de qué hablamos
    cambiemos de tema        → olvida el tema actual
    (me acuerdo del tema aunque me apagues)

  LEER DOCUMENTOS
    lee <archivo.txt>        busca en la carpeta 'documentos'
        lee ejemplo.txt
    Te muestro lo que entendí y tú decides qué guardo.

  OLVIDAR Y CORREGIR
    olvida que <algo> <relación> <algo>
        olvida que el sensor mide la humedad
    olvida que <algo> es <categoría>
    olvida que <algo> es sinónimo de <otro nombre>
    olvida todo sobre <algo>
    olvida el recuerdo <texto>
    Para corregir: olvida lo incorrecto y aprende lo correcto.

  CALCULAR (te explico el orden de las operaciones)
    cuánto es 3 + 4 × 2
    calcula (2 + 3)^2 − raíz de 16
    cuánto es treinta y dos entre ocho
    3 + 4 * 2                 (también así, directo)

  RAZONAR
    ¿<algo> <relación> <algo>?      pregunta de sí o no
        ¿la raspberry pi necesita electricidad?
        ¿la raspberry pi es una máquina?
    quién <relación> <algo>          relación inversa
        quién mide la temperatura

  RED NEURONAL
    xor                 ver cómo resuelve XOR
    aprende [0,1] = 1   guardar un ejemplo de entrenamiento
    entrenar            aprender de los ejemplos guardados

  SISTEMA
    ordena tu diccionario   une repetidos y pasa conceptos a singular
    ecosistema              quién está conectado a GAIA y qué sabe hacer
    qué pasó hoy            resumen de TABRIS: órdenes, rechazos y errores
    errores                 los últimos errores que registró TABRIS
    incidentes              los problemas que HADES está atendiendo
    recursos                CPU, RAM, disco y batería según ARTEMIS

  ROVER (otro programa: python -m rover.servidor)
    conecta el rover        lo busca en la red y lo conecta a GAIA
    rover ve a <x> <y>      le das un objetivo; él decide cómo llegar
    rover estado            dónde está y qué obstáculos descubrió
    rover recarga           batería al 100 %
    seguridad               mensajes sospechosos que detectó POSEIDON

  ENTORNO (ÉTER)
    entorno                 lee los sensores y dice qué significan
    sensores                los sensores reales de esta compu y su estado
    autoriza <sensor>       activa un sensor detectado (autoriza ruido)
    desactiva <sensor>      lo apaga aunque exista
    conecta la estacion simulada   sensores de mentira, para probar
    mapa                    el mapa compartido con lo que descubrió el rover
    simula <sensor> <valor> fuerza una lectura de la estación simulada

  RUTINAS (MINERVA)
    enseña la rutina "<nombre>": paso, paso y paso
        enseña la rutina "checa todo": revisa los recursos, revisa los errores y revisa el entorno
    <nombre de la rutina>   la ejecuta (también: encárgate de <nombre>)
    rutinas                 las que me enseñaste
    olvida la rutina <nombre>

  LABORATORIO DE INNOVACIÓN (MINERVA)
    proyectos               los proyectos y su avance
    carga el proyecto focus el mapa de FOCUS hacia los niveles 4 y 5
    nuevo proyecto <nombre> / proyecto <nombre>     crear / abrir
    agrega <capacidad> [dentro de <número>]
    marca <número> como existe | a medias | falta
    estrategias <número>    ideas para llenar ese hueco
    experimento en <número> registra un intento en esa capacidad
    qué sigue               la siguiente capacidad recomendada y sus ideas
    quita la capacidad <número>

  PROTECCIÓN WEB (CUERNO ARADO)
    revisa <link o mensaje>  revisa links sin abrirlos (puedes pegar un SMS completo)
    confía en <sitio> / bloquea <sitio> / quita el sitio <sitio>
    mis sitios              tus listas de confiables y bloqueados

  PRESERVACIÓN (ELEUTHIA)
    respalda                guarda una copia del conocimiento (también hay uno diario automático)
    respaldos / restaura <número>   ver y volver a un respaldo
    bitácora                lo que pasó y aprendí hoy
    anota <texto>           escribe algo en la bitácora
    nuevo experimento       registra qué intentaste y qué aprendiste
    experimentos [de <proyecto>]    los experimentos y cómo salieron

  PRIVACIDAD (DEMETER)
    zonas protegidas        las carpetas que nadie toca sin tu permiso
    protege <carpeta>       agrega una zona protegida
    desprotege <nombre>     la quita
    permisos                las reglas que ya decidiste (siempre / nunca)
    revoca permisos de <zona>   borra las reglas; volverá a preguntarte

  TAREAS (MINERVA planea, GAIA reparte, HEFESTO junta)
    planea <tarea>          muestra los pasos sin hacerlos
    encárgate de <tarea>    hace la tarea completa
        encárgate de investigar qué es un ave, calcular 2^10 y revisar los recursos
    Dentro de una tarea o rutina también puedes usar:
        ... y guárdalo como <nombre>      el resultado + 1      define eso
        si <algo> es mayor que / menor que / igual a <algo>, <paso>
        si la ram está arriba de 90, ...   si hay errores ...   si no hay incidentes ...
        <paso> y si falla <otro paso>      si falla, detente
    recupera <inteligencia> HADES intenta reiniciarla y liberarla
    estado, quién eres, ayuda, salir

  Relaciones que entiendo:
    {relaciones}
"""


def mostrar_ayuda():
    relaciones = ", ".join(sorted(RELACIONES_VALIDAS))
    print(AYUDA.format(relaciones=relaciones))


# ==========================================
# INICIAR HEFESTO
# ==========================================

def preparar_hefesto():
    """
    Arranca HEFESTO (modelo, memoria, tema de la conversación) y devuelve
    la función procesar(comando). No pide nada por teclado.
    """

    print("\n================================")
    print("            HEFESTO")
    print("================================")

    # Si pediste restaurar un respaldo, se aplica ANTES de abrir cualquier archivo.
    try:
        restaurados = aplicar_restauracion_pendiente(os.getcwd())
        if restaurados:
            print(f"ELEUTHIA: Restauré el respaldo ({contar(len(restaurados), 'archivo', 'archivos')}).")
    except ArchivoOcupado as ocupados:
        print(f"ELEUTHIA: No pude terminar de restaurar porque otro programa tiene abierto: {ocupados}.")
        print("  ¿Hay otro HEFESTO abierto? Ciérralo y vuelve a abrirme; lo intentaré otra vez.")

    # ======================================
    # CREAR / CARGAR HEFESTO V2
    # ======================================

    hefesto = RedNeuronal(
        entradas=2,
        ocultas=4,
        salidas=1,
        tasa=0.1
    )

    if os.path.exists("hefesto_modelo_v2.npz"):

        print("\n=== MODELO V2 ENCONTRADO ===")

        hefesto.cargar_modelo("hefesto_modelo_v2.npz")

    else:

        print("\n=== CREANDO MODELO V2 ===")

        hefesto.entrenar(entradas, objetivos, 10000)

        hefesto.guardar_modelo("hefesto_modelo_v2.npz")

    # ======================================
    # EVALUAR HEFESTO
    # ======================================

    print("\n=== INICIANDO HEFESTO ===")
    print("\n=== PRUEBA XOR ===")

    hefesto.evaluar(entradas, objetivos)

    error = hefesto.calcular_error(entradas, objetivos)

    print("Error promedio:", error)
    print("HEFESTO ONLINE.")
    print("Modelo cargado correctamente.")
    print("Escribe 'ayuda' para ver lo que sé hacer, o 'salir' para apagarme.")
    avisar_pendientes()
    respaldo_diario()

    # ======================================
    # CARGAR MEMORIA
    # ======================================

    memoria = cargar_memoria()

    # ======================================
    # INTERFAZ PRINCIPAL
    # ======================================

    # De qué estamos hablando (para entender "¿y puede nadar?")
    # y la última pregunta (para entender "¿y el gorrión también?").
    # Se recuerdan de la sesión anterior.
    estado = cargar_estado()
    tema_actual = estado["tema"]
    ultima_plantilla = estado["plantilla"]

    if tema_actual:
        cuando = describir_fecha(estado["fecha"])
        cuando = f" ({cuando})" if cuando else ""
        print(
            f"HEFESTO: La última vez{cuando} hablábamos de {tema_actual}. "
            f"Podemos seguir, o dime 'cambiemos de tema'."
        )

    # ======================================
    # PROCESAR UN COMANDO
    # ======================================
    #
    # Todo lo que HEFESTO sabe hacer con un comando vive aquí adentro.
    # Antes era el cuerpo del "while True"; ahora es una función para que
    # FOCUS también pueda pasarle comandos (conversacion/puente.py).
    #
    # Devuelve:
    #     SALIR        si pidieron apagar
    #     NO_ENTENDI   si no supo qué hacer con el comando
    #     None         en cualquier otro caso (ya respondió con print)

    def procesar(comando):
        # "nonlocal": estas variables son de preparar_hefesto, no nuevas.
        nonlocal tema_actual, ultima_plantilla

        comando = (comando or "").strip()
        if not comando:
            return None


        # ======================================
        # CONTEXTO DE LA CONVERSACIÓN
        # ======================================

        comando, uso_contexto = aplicar_contexto(comando, tema_actual, ultima_plantilla)

        if uso_contexto is None:
            print(
                "HEFESTO: ¿De qué estamos hablando? "
                "Todavía no sé a qué te refieres."
            )
            return NO_ENTENDI

        if uso_contexto:
            print(f"HEFESTO: (Entiendo: {comando})")

        nuevo_tema = detectar_tema(comando)

        if nuevo_tema:
            ultima_plantilla = crear_plantilla(comando, nuevo_tema) or ultima_plantilla

            # Si viene con error de escritura, recordar la forma correcta.
            if not existe_concepto(nuevo_tema):
                nuevo_tema = sugerir_concepto(nuevo_tema) or nuevo_tema
            tema_actual = nuevo_tema
            guardar_estado(tema_actual, ultima_plantilla)

        comando_normalizado = expandir_contracciones(normalizar_texto(comando))

        pregunta_inversa = parsear_pregunta_inversa(comando_normalizado)
        pregunta_si_no = parsear_pregunta_si_no(comando)

        # ======================================
        # SALIR
        # ======================================

        if comando_normalizado == "salir":

            print("HEFESTO: Apagando sistema...")
            return SALIR

        # ======================================
        # ESTADO
        # ======================================

        elif comando_normalizado == "estado":

            print(
                "HEFESTO: Todos mis sistemas "
                "principales están funcionando."
            )
            print("HEFESTO: Mi modelo está cargado.")
            print("HEFESTO: Mi red neuronal está disponible.")

        # ======================================
        # ORDENAR EL DICCIONARIO
        # ======================================

        elif comando_normalizado in (
            "ordena tu diccionario", "ordena el diccionario", "ordénate", "ordenate"
        ):

            r = ordenar_diccionario()

            if not r["unidas"] and not r["renombradas"]:
                print("HEFESTO: Mi diccionario ya estaba en orden.")
            else:
                print("HEFESTO: Listo, ordené mi diccionario.")

                if r["unidas"]:
                    print(f"  Uní {r['unidas']} concepto(s) repetido(s).")

                for antes, despues in r["renombradas"]:
                    print(f"  {antes} → {despues}")

        # ======================================
        # CAMBIAR DE TEMA
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip() in (
            "cambiemos de tema", "cambia de tema", "olvida el tema",
            "nuevo tema", "otro tema"
        ):

            tema_actual = None
            ultima_plantilla = None
            olvidar_estado()
            print("HEFESTO: Va, empecemos de cero. ¿De qué quieres hablar?")

        # ======================================
        # DE QUÉ HABLAMOS
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip() in (
            "de qué hablamos", "de que hablamos", "de qué estamos hablando",
            "de que estamos hablando"
        ):

            if tema_actual:
                print(f"HEFESTO: Estamos hablando de {tema_actual}.")
            else:
                print("HEFESTO: Todavía no hemos hablado de nada en particular.")

        # ======================================
        # AYUDA
        # ======================================

        elif comando_normalizado in ("ayuda", "help", "?"):

            mostrar_ayuda()

        # ======================================
        # ECOSISTEMA
        # ======================================

        elif comando_simple(comando) in ("ecosistema", "quien esta conectado"):

            mostrar_ecosistema()

        elif comando_simple(comando) in ("registro", "que paso hoy"):

            mostrar_registro()

        elif comando_simple(comando) in ("errores", "errores recientes"):

            mostrar_errores()

        elif comando_simple(comando).startswith("planea "):

            planear_tarea(comando.strip().split(" ", 1)[1])

        elif comando_simple(comando).startswith(("encargate de ", "haz esto ")):

            tarea = comando.strip().split(" ", 2)[2]
            encargarse_de(tarea)

        elif comando_simple(comando) in ("conecta el rover", "conecta rover", "conecta al rover"):

            conectar_rover()

        elif re.match(r"^rover (ve|ir|muevete|anda) a\s+(\d+)[\s,]+(\d+)$", comando_simple(comando)):

            x, y = re.match(r"^rover \w+ a\s+(\d+)[\s,]+(\d+)$", comando_simple(comando)).groups()
            mandar_rover(int(x), int(y))

        elif comando_simple(comando) in ("rover estado", "donde esta el rover", "rover"):

            mostrar_rover()

        elif comando_simple(comando) in ("rover recarga", "recarga el rover"):

            recargar_rover()

        elif comando_simple(comando) in ("sensores", "que sensores tengo"):

            mostrar_sensores()

        elif comando_simple(comando).startswith("autoriza "):

            autorizar_sensor(comando_simple(comando).split(" ", 1)[1].strip())

        elif comando_simple(comando).startswith("desactiva "):

            desactivar_sensor(comando_simple(comando).split(" ", 1)[1].strip())

        elif comando_simple(comando) in ("conecta la estacion simulada", "conecta la estacion"):

            conectar_estacion_simulada()

        elif comando_simple(comando) in ("entorno", "como esta el entorno"):

            mostrar_entorno()

        elif comando_simple(comando) in ("mapa", "muestra el mapa"):

            dibujar_mapa()

        elif re.match(r"^simula (\w+) (-?\d+(?:\.\d+)?)$", comando.strip().lower()):

            sensor, valor = re.match(r"^simula (\w+) (-?\d+(?:\.\d+)?)$", comando.strip().lower()).groups()
            simular_sensor(sensor, float(valor))

        elif comando.strip().lower().startswith("revisa ") and extraer_enlaces(comando):

            revisar_enlaces(comando.strip()[len("revisa "):])

        elif re.match(r"^conf[ií]a en ", comando.strip().lower()):

            cambiar_lista_web("confiar", comando.strip().split(" ", 2)[2])

        elif comando.strip().lower().startswith("bloquea "):

            cambiar_lista_web("bloquear", comando.strip().split(" ", 1)[1])

        elif re.match(r"^(quita|olvida) el sitio ", comando.strip().lower()):

            cambiar_lista_web("olvidar", comando.strip().split(" ", 3)[3])

        elif comando_simple(comando) in ("mis sitios", "listas web", "sitios confiables"):

            mostrar_listas_web()

        elif re.match(r"^ens[eé][ñn]a(me)? la rutina ", comando.strip().lower()):

            ensenar_rutina(re.sub(r"^ens[eé][ñn]a(me)? la rutina ", "", comando.strip(), flags=re.I))

        elif comando_simple(comando) in ("rutinas", "mis rutinas"):

            mostrar_rutinas()

        elif comando.strip().lower().startswith("olvida la rutina "):

            olvidar_rutina(comando.strip()[len("olvida la rutina "):])

        elif comando_simple(comando) in ("proyectos", "laboratorio", "mis proyectos"):

            mostrar_proyectos()

        elif comando_simple(comando) in ("carga el proyecto focus", "proyecto focus") and \
                not ecosistema().pedir("hefesto", "minerva", "proyecto", nombre="FOCUS")["estado"] == OK:

            cargar_proyecto_focus()

        elif comando.strip().lower().startswith("nuevo proyecto "):

            nuevo_proyecto(comando.strip()[len("nuevo proyecto "):].strip())

        elif comando.strip().lower().startswith("proyecto "):

            mostrar_proyecto(comando.strip()[len("proyecto "):].strip())

        elif comando.strip().lower().startswith("agrega ") and not comando_normalizado.startswith("agrega que"):

            agregar_capacidad(comando.strip()[len("agrega "):])

        elif re.match(r"^marca #?(\d+) como (.+)$", comando.strip().lower()):

            numero, estado = re.match(r"^marca #?(\d+) como (.+)$", comando.strip().lower()).groups()
            marcar_capacidad(int(numero), estado)

        elif re.match(r"^estrategias #?(\d+)$", comando_simple(comando)):

            mostrar_estrategias(int(re.findall(r"\d+", comando)[0]))

        elif re.match(r"^experimento en #?(\d+)$", comando_simple(comando)):

            experimento_en(int(re.findall(r"\d+", comando)[0]))

        elif re.match(r"^quita la capacidad #?(\d+)$", comando_simple(comando)):

            quitar_capacidad(int(re.findall(r"\d+", comando)[0]))

        elif comando_simple(comando) in ("siguiente paso", "que sigue", "que hago ahora"):

            mostrar_siguiente()

        elif comando_simple(comando) in ("respalda", "haz un respaldo", "respaldar"):

            respaldar_ahora()

        elif comando_simple(comando) in ("respaldos", "mis respaldos"):

            mostrar_respaldos()

        elif re.match(r"^restaura (\d+)$", comando_simple(comando)):

            restaurar_respaldo(int(comando_simple(comando).split()[1]))

        elif comando_simple(comando) in ("bitacora", "que aprendiste hoy", "que paso en la bitacora"):

            mostrar_bitacora()

        elif comando.strip().lower().startswith("anota "):

            anotar_en_bitacora(comando.strip()[len("anota "):])

        elif comando_simple(comando) in ("nuevo experimento", "registra un experimento"):

            registrar_experimento()

        elif comando_simple(comando) == "experimentos" or comando_simple(comando).startswith("experimentos de "):

            partes = comando.strip().split(" de ", 1)
            mostrar_experimentos(partes[1].strip() if len(partes) == 2 else None)

        elif comando_simple(comando) in ("zonas protegidas", "zonas", "que esta protegido"):

            mostrar_zonas()

        elif comando_simple(comando) in ("permisos", "reglas de privacidad"):

            mostrar_permisos()

        elif comando.strip().lower().startswith("protege "):

            proteger_carpeta(comando.strip()[len("protege "):].strip().strip('"'))

        elif comando.strip().lower().startswith("desprotege "):

            desproteger_zona(comando.strip()[len("desprotege "):].strip())

        elif comando.strip().lower().startswith("revoca permisos de "):

            revocar_permisos(comando.strip()[len("revoca permisos de "):].strip())

        elif comando_simple(comando) in ("seguridad", "poseidon"):

            mostrar_seguridad()

        elif comando_simple(comando) in ("recursos", "como esta la compu"):

            mostrar_recursos()

        elif comando_simple(comando) in ("incidentes", "hay problemas"):

            mostrar_incidentes()

        elif comando_simple(comando).startswith("recupera "):

            recuperar_inteligencia(comando_simple(comando).split(" ", 1)[1].strip())

        # ======================================
        # PROBAR XOR
        # ======================================

        elif comando_normalizado == "xor":

            print("\nHEFESTO analiza:")
            print("[0,0] →", hefesto.predecir([0, 0]))
            print("[0,1] →", hefesto.predecir([0, 1]))
            print("[1,0] →", hefesto.predecir([1, 0]))
            print("[1,1] →", hefesto.predecir([1, 1]))

        # ======================================
        # CALCULAR: "cuánto es 3 + 4 × 2", "3+4*2"
        # ======================================

        elif extraer_operacion(comando) is not None:

            mostrar_calculo(extraer_operacion(comando))

        # ======================================
        # DEFINIR: "define pingüino", "qué es un pingüino"
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip().startswith(
            ("define ", "qué es ", "que es ", "qué son ", "que son ",
             "qué significa ", "que significa ")
        ):

            pregunta = comando_normalizado.replace("¿", "").replace("?", "").strip()
            concepto = limpiar_concepto(pregunta.split(" ", 1)[1])

            # "qué es" deja la palabra "es" adelante: quitarla.
            for inicio in ("es ", "son ", "significa "):
                if concepto.startswith(inicio):
                    concepto = limpiar_concepto(concepto[len(inicio):])

            concepto = resolver_concepto(concepto)

            datos = pedir("apollo", "definir", concepto=concepto)
            if datos is not None:
                print("HEFESTO: " + redactar_definicion(datos))

        # ======================================
        # LEER DOCUMENTOS
        # ======================================

        elif comando_simple(comando).startswith("fuentes de "):

            mostrar_fuentes(comando.strip()[len("fuentes de "):].strip())

        elif comando_normalizado.startswith("lee "):

            ruta = re.sub(
                r"^\s*lee\s+(?:el\s+(?:archivo|documento)\s+)?", "",
                comando, flags=re.IGNORECASE
            )
            leer_documento(ruta)

        # ======================================
        # OLVIDAR
        # ======================================

        elif comando_normalizado.startswith(("olvida todo sobre ", "olvida todo de ")):

            concepto = comando_normalizado.split(" ", 3)[3]
            olvidar_todo_sobre(resolver_concepto(limpiar_concepto(concepto)))

        elif comando_normalizado.startswith("olvida el recuerdo "):

            olvidar_recuerdo(comando[len("olvida el recuerdo "):].strip())

        elif comando_normalizado.startswith("olvida que "):

            olvidar_frase(comando_normalizado[len("olvida que "):])

        # ======================================
        # RECORDAR CONOCIMIENTO
        # ======================================

        elif comando_normalizado.startswith("recuerda"):

            contenido = comando[len("recuerda"):].strip()

            if not contenido:
                print("HEFESTO: ¿Qué quieres que recuerde?")
                return None

            conocimiento = analizar_conocimiento(contenido)
            guardar_conocimiento(conocimiento)

        # ======================================
        # ACTUALIZAR CONOCIMIENTO
        # ======================================

        elif comando_normalizado.startswith("actualiza |"):

            partes = comando.split("|")

            if len(partes) != 5:

                print("HEFESTO: Formato incorrecto.")
                print(
                    "Usa: actualiza | tipo | tema | "
                    "contenido_anterior | contenido_nuevo"
                )
                return None

            tipo = partes[1].strip()
            tema = partes[2].strip()
            contenido_anterior = partes[3].strip()
            contenido_nuevo = partes[4].strip()

            actualizar_conocimiento(
                tipo,
                tema,
                contenido_nuevo,
                contenido_anterior
            )

        # ======================================
        # APRENDER PALABRAS Y RELACIONES
        # ======================================

        elif comando_normalizado.startswith("aprende que "):

            contenido = comando_normalizado[
                len("aprende que "):
            ].strip()

            # ======================================
            # APRENDIZAJE DE SINÓNIMOS
            # ======================================

            separadores_sinonimos = (
                " es sinónimo de ",
                " es sinonimo de ",
                " significa ",
                " quiere decir ",
                " equivale a ",
            )

            separador = next(
                (
                    s for s in separadores_sinonimos
                    if s in contenido
                ),
                None
            )

            if separador is not None:

                palabra, sinonimo = contenido.split(separador, 1)

                anunciar(aprender_sinonimo(palabra.strip(), sinonimo.strip()))

            else:

                # ======================================
                # APRENDIZAJE DE RELACIONES
                # ======================================

                # Primero relaciones normales (mide, puede...),
                # luego "X no es Y". Ambas entienden el "no".
                resultado = (
                    extraer_relacion_con_negacion(contenido)
                    or negacion_de_categoria(contenido)
                )

                if resultado:

                    sujeto, relacion, objeto, negada = resultado

                    aprender_relacion_conversando(sujeto, relacion, objeto, negada)

                else:

                    # ======================================
                    # APRENDIZAJE DE ASOCIACIONES
                    # ======================================

                    # "X es Y" o, en plural, "X son Y".
                    partes = []

                    for conector in (" es ", " son "):
                        if conector in contenido:
                            partes = contenido.split(conector, 1)
                            break

                    if len(partes) != 2:

                        print(
                            "HEFESTO: No pude identificar "
                            "una asociación o relación."
                        )
                        return None

                    palabra = partes[0].strip()
                    asociacion = partes[1].strip()

                    anunciar(aprender_palabra(palabra, asociacion))

        # ======================================
        # RELACIONES INVERSAS: quién mide X
        # ======================================

        elif pregunta_inversa is not None:

            verbo, objeto = pregunta_inversa
            objeto = resolver_concepto(objeto)

            sujetos = [
                inversa["sujeto"]
                for inversa in relaciones_inversas(objeto)
                if inversa["relacion"] == verbo
            ]

            if sujetos:
                print("HEFESTO: Esto es lo que sé:")
                for sujeto in sujetos:
                    print(f"  {sujeto} → {verbo} → {objeto}")
            else:
                print(f"HEFESTO: No conozco nada que {verbo} {objeto}.")

        # ======================================
        # CONSULTAR RELACIONES
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip().startswith(
            tuple(prefijo for prefijo, _ in PREGUNTAS_DE_RELACION)
        ):

            pregunta = (
                comando_normalizado
                .replace("¿", "")
                .replace("?", "")
                .strip()
            )

            prefijos = PREGUNTAS_DE_RELACION

            verbo_encontrado = None
            sujeto = ""

            for prefijo, verbo in prefijos:

                if pregunta.startswith(prefijo):

                    verbo_encontrado = verbo
                    sujeto = pregunta[len(prefijo):].strip()

                    for articulo in (
                        "el ", "la ", "los ", "las ",
                        "un ", "una ", "unos ", "unas "
                    ):
                        if sujeto.startswith(articulo):
                            sujeto = sujeto[len(articulo):].strip()
                            break

                    break

            if verbo_encontrado is None:

                print(
                    "HEFESTO: Todavía no reconozco "
                    "la relación de esa pregunta."
                )

            else:

                sujeto = resolver_concepto(sujeto)

                relaciones = buscar_relaciones(sujeto)

                encontradas = [
                    relacion
                    for relacion in relaciones
                    if normalizar_relacion(
                        relacion.get("relacion", "")
                    ) == normalizar_relacion(verbo_encontrado)
                ]

                if encontradas:

                    print("HEFESTO: Esto es lo que sé:")

                    for relacion in encontradas:
                        print(
                            f"  {sujeto} → {verbo_encontrado} → "
                            f"{relacion['objetivo']}"
                        )

                else:

                    verbo_oficial = normalizar_relacion(verbo_encontrado)

                    deducidas = [
                        inferida
                        for inferida in relaciones_inferidas(sujeto)
                        if inferida["relacion"] == verbo_oficial
                    ]

                    inversas = [
                        inversa["sujeto"]
                        for inversa in relaciones_inversas(sujeto)
                        if inversa["relacion"] == verbo_oficial
                    ]

                    if deducidas:

                        print("HEFESTO: Nadie me lo dijo, pero lo deduzco:")

                        for inferida in deducidas:
                            print(
                                f"- {sujeto} {verbo_oficial} "
                                f"{inferida['objetivo']}, porque:"
                            )
                            mostrar_cadena(inferida["cadena"], "    ")

                    elif inversas:

                        print(
                            f"HEFESTO: No sé qué {verbo_oficial} {sujeto}, "
                            f"pero sé esto sobre {sujeto}:"
                        )

                        for otro in inversas:
                            print(f"  {otro} → {verbo_oficial} → {sujeto}")

                    else:

                        negadas = [
                            relacion
                            for relacion in buscar_relaciones(sujeto, negadas=True)
                            if normalizar_relacion(relacion["relacion"]) == verbo_oficial
                        ]

                        if negadas:
                            print(
                                f"HEFESTO: No sé qué {verbo_oficial} {sujeto}, "
                                f"pero sé lo que NO:"
                            )
                            for relacion in negadas:
                                print(
                                    f"  {sujeto} → NO {verbo_oficial} → "
                                    f"{relacion['objetivo']}"
                                )
                        else:
                            print(
                                f"HEFESTO: No conozco relaciones de tipo "
                                f"'{verbo_encontrado}' para {sujeto}."
                            )

        # ======================================
        # BUSCAR CAMINO ENTRE CONCEPTOS
        # ======================================

        elif comando_normalizado.startswith("camino "):

            texto = comando_normalizado[len("camino "):].strip()

            origen, destino = separar_origen_destino(texto)

            if not origen or not destino:
                print(
                    "HEFESTO: Indica el origen y el destino. "
                    "Ejemplo: camino raspberry pi temperatura "
                    "(o: camino raspberry pi | temperatura)."
                )

            else:

                origen = resolver_concepto(origen)
                destino = resolver_concepto(destino)

                camino = buscar_camino(origen, destino)

                if camino is None:

                    print(
                        f"HEFESTO: No encontré un camino entre "
                        f"{origen} y {destino}."
                    )

                elif not camino:

                    print(
                        "HEFESTO: El origen y el destino "
                        "son el mismo concepto."
                    )

                else:

                    print("HEFESTO: Encontré esta conexión:")

                    for paso in camino:
                        print(
                            f"  {paso['origen']} "
                            f"→ {paso['relacion']} → "
                            f"{paso['destino']}"
                        )

        # ======================================
        # CONSULTAR CONOCIMIENTO
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip().startswith(
            ("qué sabes de ", "que sabes de ")
        ):

            pregunta = (
                comando_normalizado
                .replace("¿", "")
                .replace("?", "")
                .strip()
            )

            if pregunta.startswith("qué sabes de "):
                palabra = pregunta[len("qué sabes de "):].strip()
            else:
                palabra = pregunta[len("que sabes de "):].strip()

            palabra = resolver_concepto(limpiar_concepto(palabra))

            palabra_normalizada = normalizar_concepto(palabra)

            asociaciones = buscar_palabra(palabra)
            relaciones = buscar_relaciones(palabra)

            entrada = buscar_entrada(palabra)

            sinonimos = (
                entrada.get("sinonimos", [])
                if entrada is not None
                else []
            )

            memoria = cargar_memoria()
            conocimientos = memoria.get("conocimientos", [])
            conocimientos_encontrados = []

            for conocimiento in conocimientos:

                if not isinstance(conocimiento, dict):
                    continue

                tema = conocimiento.get("tema", "")
                temas = conocimiento.get("temas", [])

                if isinstance(temas, str):
                    temas = [temas]

                if not isinstance(temas, list):
                    temas = []

                if isinstance(tema, str) and tema:
                    temas = temas + [tema]

                contenido_memoria = conocimiento.get("contenido", "")

                if not isinstance(contenido_memoria, str):
                    contenido_memoria = ""

                coincide_tema = any(
                    isinstance(t, str)
                    and normalizar_concepto(t) == palabra_normalizada
                    for t in temas
                )

                coincide_contenido = (
                    palabra_normalizada in normalizar_concepto(
                        contenido_memoria
                    )
                )

                if coincide_tema or coincide_contenido:
                    conocimientos_encontrados.append(conocimiento)

            encontrado = False

            if asociaciones:

                encontrado = True
                print(f"HEFESTO: {palabra} está relacionado con:")

                for asociacion in asociaciones:
                    print("-", asociacion)

            if sinonimos:

                encontrado = True
                nombre_principal = entrada.get("palabra", palabra)

                if normalizar_concepto(nombre_principal) != palabra_normalizada:
                    print(
                        f"HEFESTO: '{palabra}' es otro nombre "
                        f"para '{nombre_principal}'."
                    )

                print(
                    f"HEFESTO: Sinónimos conocidos de "
                    f"{nombre_principal}:"
                )

                for sinonimo in sinonimos:
                    print("-", sinonimo)

            if relaciones:

                encontrado = True
                print(f"HEFESTO: Relaciones conocidas de {palabra}:")

                for relacion in relaciones:
                    print(
                        f"- {relacion['relacion']} "
                        f"→ {relacion['objetivo']}"
                    )

            negaciones = buscar_relaciones(palabra, negadas=True)

            if negaciones:

                encontrado = True
                print(f"HEFESTO: Sé que {palabra} NO:")

                for relacion in negaciones:
                    print(
                        f"- {relacion['relacion']} "
                        f"→ {relacion['objetivo']}"
                    )

            if conocimientos_encontrados:

                encontrado = True
                print(
                    f"HEFESTO: Esto es lo que recuerdo sobre {palabra}:"
                )

                for conocimiento in conocimientos_encontrados:
                    print(
                        f"- [{conocimiento.get('tipo', 'sin tipo')}] "
                        f"{conocimiento.get('contenido', '')}"
                    )

            categorias = ancestros(palabra)
            deducidas = relaciones_inferidas(palabra)
            inversas = relaciones_inversas(palabra)

            # Las categorías directas ya salen como asociaciones;
            # aquí solo mostramos las deducidas.
            categorias_deducidas = [
                (categoria, cadena)
                for categoria, cadena in categorias
                if len(cadena) > 1
            ]

            if categorias_deducidas:

                encontrado = True
                print(f"HEFESTO: Por deducción, {palabra} también es:")

                for categoria, cadena in categorias_deducidas:
                    via = cadena[-1]["origen"]
                    print(f"- {categoria} (porque es {via})")

            if deducidas:

                encontrado = True
                print(f"HEFESTO: Además deduzco que {palabra}:")

                for inferida in deducidas:
                    via = inferida["cadena"][-1]["origen"]
                    print(
                        f"- {inferida['relacion']} → {inferida['objetivo']} "
                        f"(porque es {via})"
                    )

            if inversas:

                encontrado = True
                print(f"HEFESTO: Lo que se relaciona con {palabra}:")

                for inversa in inversas[:15]:
                    print(
                        f"- {inversa['sujeto']} → "
                        f"{inversa['relacion']} → {palabra}"
                    )

                if len(inversas) > 15:
                    print(f"- ... y {len(inversas) - 15} más.")

            if not encontrado:

                print(
                    f"HEFESTO: Todavía no encuentro información "
                    f"sobre {palabra}."
                )

        # ======================================
        # APRENDER DATOS PARA LA RED NEURONAL
        # ======================================

        elif comando_normalizado.startswith("aprende "):

            try:

                datos = comando[len("aprende "):]
                entrada_texto, objetivo_texto = datos.split("=", 1)

                entrada_texto = entrada_texto.strip().strip("[]")
                objetivo_texto = objetivo_texto.strip()

                entrada = [
                    int(valor.strip())
                    for valor in entrada_texto.split(",")
                ]

                objetivo = int(objetivo_texto)

                guardar_dato_aprendizaje(entrada, objetivo)

            except (ValueError, IndexError):

                print(
                    "HEFESTO: No pude interpretar ese dato. "
                    "Usa el formato: aprende [0,1] = 1"
                )

        # ======================================
        # ENTRENAR
        # ======================================

        elif comando_normalizado == "entrenar":

            (
                entradas_aprendizaje,
                objetivos_aprendizaje
            ) = preparar_datos_aprendizaje()

            if len(entradas_aprendizaje) == 0:

                print("HEFESTO: No tengo datos de aprendizaje.")

            else:

                print("HEFESTO: Voy a aprender de mis datos.")

                hefesto.aprender(
                    entradas_aprendizaje,
                    objetivos_aprendizaje,
                    5000
                )

        # ======================================
        # MOSTRAR RECUERDOS
        # ======================================

        elif comando_normalizado == "recuerdos":

            memoria = cargar_memoria()

            print("\nYo recuerdo:")

            for conocimiento in memoria.get("conocimientos", []):
                print("-", conocimiento)

        # ======================================
        # IDENTIDAD
        # ======================================

        elif comando_normalizado.replace("¿", "").replace("?", "").strip() in (
            "quien eres",
            "quién eres"
        ):

            identidad = memoria.get("identidad", {})

            print(
                f"Yo soy {identidad.get('nombre', 'HEFESTO')}, "
                "el sistema de inteligencia para Focus."
            )

            print(
                f"Mi creador es "
                f"{identidad.get('creador', 'no especificado')}."
            )

        # ======================================
        # PREGUNTAS DE SÍ O NO
        # ======================================

        elif pregunta_si_no is not None:

            sujeto, verbo, objeto = pregunta_si_no

            sujeto = resolver_concepto(sujeto)
            objeto = resolver_concepto(objeto)

            datos = pedir(
                "apollo", "responder",
                sujeto=sujeto, relacion=verbo, objeto=objeto
            )
            if datos is None:
                return None

            respuesta, cadena = datos["respuesta"], datos["cadena"]

            if respuesta == SI:
                inicio = "Sí"
            elif respuesta == NO:
                inicio = "No"
            else:
                inicio = None

            if inicio is None:
                print(
                    "HEFESTO: No lo sé. No tengo información "
                    "que lo confirme ni que lo niegue."
                )
            elif len(cadena) == 1:
                print(f"HEFESTO: {inicio}. Me lo enseñaste:")
                mostrar_cadena(cadena)
            else:
                print(f"HEFESTO: {inicio}. Nadie me lo dijo, pero lo deduje así:")
                mostrar_cadena(cadena)

        elif es_rutina(comando):

            # Una rutina se puede usar solo con su nombre: "checa todo"
            encargarse_de(comando.strip())

        else:

            print(
                "HEFESTO: Todavía no sé procesar ese comando. "
                "Escribe 'ayuda' para ver lo que sé hacer."
            )
            return NO_ENTENDI

    return procesar


def iniciar_hefesto():
    """El modo de comandos exactos: python HEFESTO.py"""
    procesar = preparar_hefesto()

    while True:

        try:
            comando = input("\nTú: ").strip()

        except (KeyboardInterrupt, EOFError):
            print("\nHEFESTO: Apagando sistema...")
            break

        if procesar(comando) == SALIR:
            break


if __name__ == "__main__":
    try:
        iniciar_hefesto()
    except ErrorAlmacenamiento as error:
        print(f"HEFESTO: Tengo un problema con mis archivos: {error}")