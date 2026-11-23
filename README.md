# HEFESTO

Una inteligencia artificial construida desde cero en Python: aprende conceptos y relaciones conversando, razona sobre lo que sabe y explica cómo llegó a cada conclusión.

HEFESTO es la primera inteligencia de **FOCUS**, un ecosistema de IAs especializadas que colaboran entre sí, inspirado en las inteligencias de *Horizon Forbidden West*.

```
Tú: aprende que las aves pueden volar
Tú: aprende que el pingüino es un ave
Tú: ¿el pingüino puede volar?
HEFESTO: Sí. Nadie me lo dijo, pero lo deduje así:
  pingüino → es → ave
  ave → puede → volar

Tú: aprende que el pingüino no puede volar
Tú: ¿y puede volar?
HEFESTO: (Hablando de pingüino: ¿pingüino puede volar?)
HEFESTO: No. Me lo enseñaste:
  pingüino → NO puede → volar
```

## Qué sabe hacer

- **Aprender en lenguaje natural**: conceptos, categorías, relaciones (*mide*, *usa*, *pertenece a*…), sinónimos y negaciones.
- **Entender variaciones**: acentos, plurales, artículos, conjugaciones y contracciones. "Las baterías" y "bateria" son el mismo concepto; "miden" y "mide", la misma relación.
- **Corregir errores de escritura**: si escribes `raspbery pi`, pregunta si quisiste decir `raspberry pi` (distancia de edición de Damerau-Levenshtein).
- **Razonar**:
  - *Herencia*: si la Raspberry Pi es una computadora y las computadoras necesitan electricidad, deduce que la Raspberry Pi necesita electricidad.
  - *Excepciones*: lo más específico gana (el pingüino es un ave, pero no vuela).
  - *Relaciones inversas*: si el sensor mide la temperatura, sabe responder quién mide la temperatura.
  - *Sí, no o no sé*: sin información no inventa; responde "no lo sé" (suposición de mundo abierto).
- **Detectar contradicciones** y preguntar antes de reemplazar lo que ya sabía.
- **Olvidar y corregir** relaciones, sinónimos, conceptos completos y recuerdos.
- **Seguir una conversación**: recuerda el tema (incluso entre sesiones) para entender preguntas como "¿y qué tiene?" o "¿y el gorrión también?".
- **Explicar con sus palabras**: `define pingüino` arma una definición juntando lo que sabe y lo que deduce ("Es un ave. Puede nadar, pero no puede volar. Por ser ave, tiene plumas.").
- **Leer documentos**: extrae hechos de un `.txt` y te muestra lo que entendió antes de guardarlo.
- **Base de datos SQLite** con consultas directas e índices: con 5,000 conceptos, buscar pasó de ~1 s a ~2 ms y aprender de ~300 ms a ~3 ms.
- **Diccionario de casi 17,000 conceptos** importado de WordNet en español, conectado con lo que le enseñas: si le dices que el pingüino es un ave, deduce solo que es un vertebrado y un animal.
- **Red neuronal propia**, escrita a mano con NumPy (propagación hacia adelante y retropropagación), que resuelve XOR.

## Arquitectura

Cada parte del código corresponde a una inteligencia o servicio de FOCUS:

```
Cerebro/
├── focus.py                Puerta de entrada: platicar de forma natural
├── HEFESTO.py              Interfaz de comandos exactos
├── gaia/                   GAIA: coordina a las inteligencias con mensajes
│   ├── mensajes.py         Órdenes, respuestas y eventos (listos para JSON)
│   ├── inteligencia.py     El molde que comparten todas las inteligencias
│   ├── nucleo.py           Directorio, entrega, fallos, eventos e historial
│   ├── tareas.py           Ejecuta los planes de MINERVA paso por paso
│   └── red.py              Habla con inteligencias en otros programas (TCP + JSON)
├── tabris/                 TABRIS: supervisa y registra todo lo que pasa
│   ├── registro.py         Guarda cada mensaje en un archivo .jsonl
│   └── servicio.py         Resumen, búsqueda y detección de fallos repetidos
├── hades/                  HADES: atiende fallos y recupera inteligencias
│   └── servicio.py         Incidentes, cuarentena y recuperación
├── artemis/                ARTEMIS: administra los recursos de la computadora
│   ├── medidor.py          Lee CPU, RAM, disco y batería con psutil
│   └── servicio.py         Alertas y "¿alcanza para esta tarea?"
├── poseidon/               POSEIDON: protege las comunicaciones
│   ├── firma.py            Firma HMAC-SHA256 y la clave secreta
│   ├── guardia.py          Rechaza firmas falsas, mensajes viejos y repetidos
│   └── servicio.py         Reporte de mensajes sospechosos
├── eter/                   ÉTER: percibe el entorno
│   ├── interpretacion.py   De números a significado (31 °C → "calor") y lo anormal
│   └── servicio.py         Lecturas, anomalías y el mapa compartido (eter_mapa.json)
├── dispositivos/
│   ├── sensores_locales.py Sensores reales: WiFi, temperatura del procesador, ruido
│   ├── local.py            Los detecta, los activa o desactiva y pide permiso
│   └── estacion.py         Estación simulada, solo para pruebas
├── cuerno_arado/           CUERNO ARADO: protección web (parte de POSEIDON)
│   ├── analisis.py         Revisa links sin abrirlos: imitaciones, @, IPs, descargas...
│   └── servicio.py         Revisa mensajes completos y tus listas de sitios
├── eleuthia/               ELEUTHIA: preservación
│   ├── respaldos.py        Respaldos .zip (SQLite con backup), restaurar en dos tiempos
│   └── servicio.py         Respaldo diario, bitácora automática y experimentos
├── demeter/                DEMETER: privacidad
│   ├── rutas.py            ¿Este archivo está dentro de esa carpeta? (sin trampas)
│   └── servicio.py         Zonas protegidas, permisos y lo que sale por la red
├── rover/                  La mini IA de un robot (programa aparte)
│   ├── mundo.py            Mapa simulado con obstáculos ocultos y rutas (BFS)
│   ├── robot.py            Decide solo: esquiva, recalcula y frena por seguridad
│   └── servidor.py         Recibe órdenes por la red: python -m rover.servidor
├── minerva/                MINERVA: planea tareas e innova
│   ├── planeador.py        Divide una tarea en pasos y decide a quién le toca cada uno
│   ├── rutinas.py          Rutinas que le enseñas ("checa todo"), sin círculos
│   ├── condiciones.py      Entiende "si piezas es mayor que 100", "si hay errores", "si falla"
│   ├── laboratorio.py      Laboratorio de innovación: capacidades, avance y estrategias
│   └── servicio.py         Revisa responsables y recursos antes de aprobar el plan
├── apollo/                 APOLLO: gestión del conocimiento
│   ├── conocimiento.py     Conceptos, relaciones, sinónimos, caminos, olvido
│   ├── lenguaje.py         Normalización, verbos y distancia de edición
│   ├── razonamiento.py     Herencia, excepciones, inversas y sí/no/no sé
│   ├── definicion.py       Junta todo lo que se sabe de un concepto
│   ├── lector.py           Extrae hechos de documentos
│   ├── importador.py       Importa conocimiento en bloque
│   └── servicio.py         APOLLO como inteligencia conectada a GAIA
├── calculo/
│   ├── aritmetica.py       Calculadora exacta, paso a paso
│   └── servicio.py         La calculadora como herramienta de GAIA
├── conversacion/
│   ├── contexto.py         Tema y última pregunta (funciones puras)
│   ├── estado.py           Recuerda la conversación entre sesiones
│   ├── resultados.py       Resume en una frase lo que devolvió cada paso
│   ├── intenciones.py      Qué quieres y con qué datos, dicho a tu manera
│   ├── personalidad.py     La voz de FOCUS (inspirada en GAIA, relajada)
│   ├── perfil.py           Lo que recuerda de ti
│   └── platica.py          Une todo: confirma, pregunta, aprende y sigue el hilo
│   └── redaccion.py        Redacta en español: artículos, género, listas
├── memoria/
│   ├── almacenamiento.py   Guardado atómico de JSON
│   └── base_datos.py       SQLite: tablas, índices, migraciones y consultas
├── herramientas/
│   └── importar_wordnet.py Importa WordNet en español
└── tests/                  Pruebas automáticas con pytest
```

Las inteligencias no se llaman entre sí: se mandan **mensajes a través de GAIA**.

```python
gaia.pedir("hefesto", "apollo", "definir", concepto="pingüino")
# → {"tipo": "respuesta", "estado": "ok", "datos": {...}, "responde_a": "a3f9..."}
```

- Cada mensaje se puede convertir a JSON, así que el mismo formato servirá por WiFi o para darle órdenes a la mini IA de un robot. Las órdenes pueden llevar `objetivo`, `restricciones` y `si_falla` (plan B).
- Si una inteligencia falla, GAIA no se cae: responde `error` y publica el evento `fallo` (la semilla de HADES).
- **TABRIS** observa cada mensaje y lo guarda en `tabris_registro.jsonl`, así que sobrevive aunque se apague HEFESTO. Responde "¿qué pasó hoy?" y, si una inteligencia falla tres veces seguidas, publica el evento `anomalia`. Como dice el plan de FOCUS, no repara nada: identifica, documenta y avisa.
- **HADES** responde a esos avisos: abre un incidente con cada fallo y, cuando TABRIS detecta una anomalía, le pide a GAIA que **aísle** a esa inteligencia (deja de recibir órdenes). Con `recupera <inteligencia>` la reinicia y la libera. HADES nunca se aísla a sí misma.
- **ARTEMIS** mide la CPU, la RAM, el disco y la batería (`recursos`), publica `recursos_bajos` cuando algo se está acabando y responde si alcanza para una tarea, algo que MINERVA usa para planear.
- **MINERVA** divide una tarea en pasos ("investiga qué es X, calcula Y y revisa los recursos"), revisa que cada inteligencia esté disponible y que alcancen los recursos. **GAIA** ejecuta el plan paso por paso y **HEFESTO** junta los resultados (`encárgate de <tarea>`).

### Rutinas: MINERVA aprende tareas nuevas

```
Tú: enseña la rutina "checa todo": revisa los recursos, revisa los errores y revisa el entorno
Tú: enseña la rutina "buenos días": checa todo y respalda
Tú: buenos días
  1. [ARTEMIS] CPU al 9 %, RAM al 76 %, disco al 48 %.
  2. [TABRIS] hoy van 36 mensajes, 0 errores y 2 rechazos.
  3. [ÉTER] señal del WiFi 87 % (buena).
  4. [ELEUTHIA] guardé respaldo_2026-11-19_15-09-49.zip (6 archivos).
```

- Le enseñas tareas con tus palabras y las usas solo con su nombre. Una rutina puede usar otras.
- Al enseñarla revisa que entienda cada paso, que no haya círculos (A usa B y B usa A) y que el nombre no tape un comando que ya existe.
- **Un paso puede usar el resultado de otro**: `guárdalo como <nombre>` guarda un valor, y `el resultado` o `eso` se refieren al paso anterior.

```
Tú: encárgate de calcular 5 × 35 y guárdalo como piezas, calcula piezas × 2 y calcula el resultado + 1/3
  1. [CALCULADORA] 5 × 35 = 175        → guardé piezas = 175
  2. [CALCULADORA] 175 × 2 = 350
  3. [CALCULADORA] 350 + 1 ÷ 3 = 1051/3
Tú: encárgate de investigar qué es un pingüino y luego define eso      (define "ave")
```

- **Condiciones**: `si <algo> es mayor que / menor que / igual a <algo>`, `si hay errores`, `si no hay incidentes`. Se pueden comparar valores guardados, el resultado anterior y **datos reales del sistema** (la RAM, el disco, la CPU y la batería de ARTEMIS, los errores de TABRIS, los incidentes de HADES). Si no se cumple, el paso se salta.
- **Plan B**: `<paso> y si falla <otro paso>`, o `si falla, detente`. "No lo conozco" de APOLLO también cuenta como falla.

```
Tú: enseña la rutina "guardia": si no hay errores buenos días, si hay errores revisa los incidentes
Tú: encárgate de definir tensor y si falla calcula 2 + 2
  1. [APOLLO] Todavía no sé qué es tensor.
       → plan B: [CALCULADORA] 2 + 2 = 4
```

### El rover: una IA en otro programa

```
Terminal 1:  python -m rover.servidor
Terminal 2:  python HEFESTO.py
             Tú: conecta el rover
             Tú: rover ve a 6 6
               ROVER: encontré un obstáculo en (2, 0); recalculé la ruta
               ...
             HEFESTO: El rover llegó a (6, 6) en 12 casillas. Batería: 76 %.
```

- El rover recibe órdenes **con su objetivo, restricciones y plan B**, no solo movimientos. Descubre obstáculos que no conocía, recalcula su ruta solo y los recuerda para la próxima. Si la batería bajaría del mínimo, se detiene por seguridad.
- Para GAIA es una inteligencia más (`InteligenciaRemota`), así que TABRIS lo registra, HADES lo aísla si se desconecta y lo recupera cuando vuelve.
- **POSEIDON** firma cada mensaje con HMAC-SHA256. El rover ignora órdenes sin firma válida, viejas o repetidas (ataque de repetición). La clave vive en `poseidon_clave.txt`, que **nunca** se sube a GitHub.

### CUERNO ARADO: links sospechosos

- `revisa <link o mensaje>` analiza los enlaces **sin abrirlos y sin internet**. Puedes pegar un SMS o un WhatsApp completo y revisa todos sus links.
- Detecta imitaciones (`paypa1.com`, `rnercadolibre.com.mx`, `steamcomunity.com`), el truco del subdominio (`paypal.com.inicio-seguro.xyz`), la @ que esconde el sitio real, IPs, letras de otros alfabetos, acortadores, descargas de programas y palabras gancho ("robux gratis").
- Reconoce los sitios oficiales para no dar falsas alarmas. Tienes tus propias listas (`confía en`, `bloquea`).
- Los links de riesgo alto los cuenta POSEIDON y los anota ELEUTHIA. Son pistas, no una garantía.

### ELEUTHIA: que nada se pierda

- **Respaldos**: uno automático al día y los que pidas (`respalda`). Guarda los últimos 10 en `respaldos/`. La base de datos se copia con la función *backup* de SQLite, y la clave de POSEIDON **no** se respalda, porque es un secreto.
- **Restaurar** (`restaura <número>`) primero respalda lo de ahorita y deja la restauración pendiente; se aplica al arrancar, antes de abrir cualquier archivo.
- **Bitácora** (`bitácora`): se llena sola con lo que HEFESTO aprende y lo importante del ecosistema (tareas, recuperaciones, sensores nuevos, alertas). También puedes escribir en ella (`anota <texto>`).
- **Experimentos** (`nuevo experimento`): qué se intentó, cómo salió y qué se aprendió. Es la base del futuro laboratorio de innovación.

### DEMETER: privacidad

- **Zonas protegidas**: la primera vez protege solas tus carpetas personales (Imágenes, Videos, Documentos, Música, Escritorio). La carpeta de FOCUS siempre es libre.
- Antes de tocar un archivo, cada inteligencia **pide permiso**: DEMETER responde *permitir*, *negar* o *preguntar*. Si pregunta, HEFESTO te pregunta a ti: `sí`, `no`, `siempre` o `nunca`. Las reglas se guardan en `demeter_permisos.json`.
- **Nada protegido sale por la red**: si una orden para el rover (u otro dispositivo) menciona un archivo de una zona protegida, no sale sin permiso de *compartir*.
- DEMETER solo decide: **nunca mueve, cambia ni borra** tus archivos.

### ÉTER: el entorno

- Los dispositivos **miden**; ÉTER **entiende y recuerda**. Le pregunta a GAIA quién sabe hacer `leer` y les pide sus lecturas a todos, sin importar si es la computadora, un ESP32 o cualquier dispositivo que cumpla ese mismo contrato.
- **Sensores reales** de la máquina donde corre FOCUS (`sensores`): señal del WiFi, temperatura del procesador (Linux y Raspberry Pi) y ruido del cuarto con el micrófono (`pip install sounddevice`; solo mide el volumen, nunca graba). Cada uno está **activo**, **desactivado** (dice por qué) o **pendiente**: si aparece después, avisa y espera a que lo autorices (`autoriza <sensor>`). El micrófono siempre pide permiso.
- Interpreta cada lectura (`entorno`), detecta lo anormal (muy alto, cambio brusco, un sensor que dejó de mandar datos) y avisa con el evento `anomalia_entorno`.
- Guarda un **mapa compartido** (`mapa`): lo que descubre el rover se guarda en `eter_mapa.json`, y un rover reiniciado (o uno nuevo) llega sin toparse con lo que ya se conocía.
- Agregar una inteligencia nueva es crear una clase con sus acciones y registrarla; no hay que tocar a las demás.

APOLLO no sabe que HEFESTO existe, así que cualquier otra inteligencia de FOCUS puede usarlo.

## Cómo usarlo

Requiere Python 3.10 o superior.

```
pip install -r requirements.txt
python focus.py        # platicar de forma natural
python HEFESTO.py      # modo de comandos exactos
```

### Platicar con FOCUS (`focus.py`)

```
Tú: Oye, ¿cómo andas?
HEFESTO: Todo fluye tranquilo: traigo la RAM al 7 %, sin errores hoy.
Tú: ¿qué es un tensor?
HEFESTO: Todavía no conozco tensor. Me encantaría aprenderlo, ¿qué es?
Tú: es un objeto matemático
HEFESTO: Va, lo aprendí: tensor es objeto matemático. Gracias por enseñarme.
Tú: crea una rutina llamada comprobación de estados, que revise los recursos, los errores y el entorno
HEFESTO: Entendí: crear la rutina "comprobación de estados" con 3 paso(s): ... ¿Te parece bien? (sí / no)
Tú: ¿el pingüino puede volar?
HEFESTO: No, el pingüino no puede volar.
```

- Entiende **intenciones** aunque las digas a tu manera, y las manda a la inteligencia de siempre por GAIA (crear una rutina platicando es lo mismo que con `enseña la rutina`).
- **Confirma antes de cambiar algo**, pregunta lo que no sabe y aprende de tu respuesta, sigue el hilo ("¿y puede volar?") y recuerda tu nombre y lo que te gusta.
- Personalidad inspirada en las IAs de Horizon: serena y cálida como GAIA, pero relajada (`conversacion/personalidad.py`).

Escribe `ayuda` para ver todos los comandos, o `ecosistema` para ver qué inteligencias están conectadas a GAIA.

## Pruebas

```
python -m pytest
```

897 pruebas cubren el lenguaje, el conocimiento, el razonamiento, las contradicciones, el olvido y el contexto, la base de datos, la redacción, la importación, la calculadora, la coordinación entre inteligencias con GAIA, la supervisión de TABRIS la recuperación de HADES los recursos de ARTEMIS, los planes de MINERVA, las firmas de POSEIDON, el rover por la red y la percepción de ÉTER. Cada prueba usa un diccionario temporal, así que nunca toca el conocimiento real de HEFESTO.

## Hoja de ruta

FOCUS crece por niveles:

1. **IA individual** ✅ procesar instrucciones, aprender, recordar y resolver problemas sencillos.
2. **IA especializada** 🟡 cada inteligencia tiene su v1; falta hacerlas buenas de verdad en lo suyo.
3. **Ecosistema multiagente** 🟡 **las 12 inteligencias existen y se comunican por GAIA** (el esqueleto está completo); falta el hardware real (Raspberry Pi 5, ESP32).
4. **Ecosistema autónomo supervisado**: planes de varios pasos, herramientas, administración de recursos y control de dispositivos, con límites de seguridad.
5. **Ecosistema cognitivo integrado**: la meta ambiciosa.

Para llegar a los niveles 4 y 5 está el **laboratorio de innovación** de MINERVA, para proyectos que "todavía no se pueden" hacer completos:

```
Tú: carga el proyecto focus
HEFESTO: 🧪 FOCUS: Llegar a los niveles 4 y 5      Avance: ████░░░░░░ 19 %
  🟡 #7 Nivel 4: autónomo supervisado  (29 %)
     ❌ #9 Prioridades y conflictos en GAIA
  ...
Tú: estrategias 9
  • Combinar: ya tienes cosas parecidas que funcionan: #2 ...
  • Dividir / Crear desde cero / Adaptar ...
  • No repetir: ya intentaste "cola por orden de llegada" y falló: prueba otra estrategia
```

- Cada proyecto es un **árbol de capacidades**: ✅ existe, 🟡 a medias, ❌ falta. Las ramas calculan su estado y su avance con el de sus partes.
- **Estrategias de inventor** para cada hueco: combinar, adaptar, aproximar, dividir, simular, enchufe primero (definir el contrato antes de tener el hardware) y crear desde cero.
- Los **experimentos** de ELEUTHIA se ligan a cada capacidad, y MINERVA los usa para no repetir errores y para sugerir qué sigue.
- Su primer proyecto es **el propio FOCUS** (`carga el proyecto focus`).

## Diccionario: WordNet en español

Para darle a HEFESTO miles de palabras ya conectadas:

```
pip install wn
python -m herramientas.importar_wordnet
```

Elige el significado más común de cada palabra usando la frecuencia de uso del WordNet en inglés (para que "rueda" sea *wheel* y no un instrumento de tortura), prefiere palabras de México ("computadora" sobre "ordenador") y respalda la base de datos antes de importar.

Créditos: [Multilingual Central Repository](https://adimen.si.ehu.es/web/MCR/) (WordNet en español, licencia [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)) a través del [Open Multilingual Wordnet](https://omwn.org/), y [Princeton WordNet 3.0](https://wordnet.princeton.edu/) ([licencia](https://wordnet.princeton.edu/license-and-commercial-use)).