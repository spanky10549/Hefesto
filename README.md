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
├── HEFESTO.py              Interfaz: entiende comandos y responde
├── gaia/                   GAIA: coordina a las inteligencias con mensajes
│   ├── mensajes.py         Órdenes, respuestas y eventos (listos para JSON)
│   ├── inteligencia.py     El molde que comparten todas las inteligencias
│   └── nucleo.py           Directorio, entrega, fallos, eventos e historial
├── tabris/                 TABRIS: supervisa y registra todo lo que pasa
│   ├── registro.py         Guarda cada mensaje en un archivo .jsonl
│   └── servicio.py         Resumen, búsqueda y detección de fallos repetidos
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
- Agregar una inteligencia nueva es crear una clase con sus acciones y registrarla; no hay que tocar a las demás.

APOLLO no sabe que HEFESTO existe, así que cualquier otra inteligencia de FOCUS puede usarlo.

## Cómo usarlo

Requiere Python 3.10 o superior.

```
pip install -r requirements.txt
python HEFESTO.py
```

Escribe `ayuda` para ver todos los comandos, o `ecosistema` para ver qué inteligencias están conectadas a GAIA.

## Pruebas

```
python -m pytest
```

379 pruebas cubren el lenguaje, el conocimiento, el razonamiento, las contradicciones, el olvido y el contexto, la base de datos, la redacción, la importación, la calculadora, la coordinación entre inteligencias con GAIA y la supervisión de TABRIS. Cada prueba usa un diccionario temporal, así que nunca toca el conocimiento real de HEFESTO.

## Hoja de ruta

FOCUS crece por niveles:

IA individual: procesar instrucciones, aprender, recordar y resolver problemas sencillos.
IA especializada: TABRIS (supervisión y registro de eventos) y MINERVA (planificación).
Ecosistema multiagente: GAIA coordina a las inteligencias; ÉTER percibe el entorno con sensores reales (ESP32).
Ecosistema autónomo supervisado: planes de varios pasos, herramientas, administración de recursos y control de dispositivos, con límites de seguridad.
Ecosistema cognitivo integrado: la meta ambiciosa.

Próximos pasos para entrenar mejor a HEFESTO: leer documentos, migrar a una base de datos real, importar conocimiento público (Wikidata, ConceptNet), llevar la red neuronal a PyTorch y explorar embeddings y un mini transformer.

## Diccionario: WordNet en español

Para darle a HEFESTO miles de palabras ya conectadas:

pip install wn
python -m herramientas.importar_wordnet

Elige el significado más común de cada palabra usando la frecuencia de uso del WordNet en inglés (para que "rueda" sea *wheel* y no un instrumento de tortura), prefiere palabras de México ("computadora" sobre "ordenador") y respalda la base de datos antes de importar.

Créditos: [Multilingual Central Repository](https://adimen.si.ehu.es/web/MCR/) (WordNet en español, licencia [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)) a través del [Open Multilingual Wordnet](https://omwn.org/), y [Princeton WordNet 3.0](https://wordnet.princeton.edu/) ([licencia](https://wordnet.princeton.edu/license-and-commercial-use)).