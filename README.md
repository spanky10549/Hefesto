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
- **Seguir una conversación**: recuerda el tema para entender preguntas como "¿y qué tiene?".
- **Red neuronal propia**, escrita a mano con NumPy (propagación hacia adelante y retropropagación), que resuelve XOR.

## Arquitectura

Cada parte del código corresponde a una inteligencia o servicio de FOCUS:

```
Cerebro/
├── HEFESTO.py              Interfaz: entiende comandos y responde
├── apollo/                 APOLLO: gestión del conocimiento
│   ├── conocimiento.py     Conceptos, relaciones, sinónimos, caminos, olvido
│   ├── lenguaje.py         Normalización, verbos y distancia de edición
│   └── razonamiento.py     Herencia, excepciones, inversas y sí/no/no sé
├── conversacion/
│   └── contexto.py         Tema de la conversación (funciones puras)
├── memoria/
│   └── almacenamiento.py   Guardado atómico y validación de JSON
└── tests/                  Pruebas automáticas con pytest
```

Las dependencias van en un solo sentido: `HEFESTO → APOLLO → memoria`. APOLLO no sabe que HEFESTO existe, así que cualquier otra inteligencia de FOCUS puede usarlo.

## Cómo usarlo

Requiere Python 3.10 o superior.

```
pip install -r requirements.txt
python HEFESTO.py
```

Escribe `ayuda` para ver todos los comandos.

## Pruebas

```
python -m pytest
```

135 pruebas cubren el lenguaje, el conocimiento, el razonamiento, las contradicciones, el olvido y el contexto. Cada prueba usa un diccionario temporal, así que nunca toca el conocimiento real de HEFESTO.

## Hoja de ruta

FOCUS crece por niveles:

1. **IA individual** ✅ procesar instrucciones, aprender, recordar y resolver problemas sencillos.
2. **IA especializada**: TABRIS (supervisión y registro de eventos) y MINERVA (planificación).
3. **Ecosistema multiagente**: GAIA coordina a las inteligencias; ÉTER percibe el entorno con sensores reales (ESP32).
4. **Ecosistema autónomo supervisado**: planes de varios pasos, herramientas, administración de recursos y control de dispositivos, con límites de seguridad.
5. **Ecosistema cognitivo integrado**: la meta ambiciosa.

Próximos pasos para entrenar mejor a HEFESTO: leer documentos, migrar a una base de datos real, importar conocimiento público (Wikidata, ConceptNet), llevar la red neuronal a PyTorch y explorar embeddings y un mini transformer.
