"""
ROVER: la mini IA de un robot de exploración (simulado).

Corre como un programa aparte (python -m rover.servidor) y recibe las
órdenes de GAIA por la red, firmadas por POSEIDON. Por ahora se mueve en
un mapa simulado; con el robot de verdad (Raspberry Pi o ESP32) solo
cambia la parte que mueve los motores y lee los sensores.
"""

# Dónde escucha el rover. 127.0.0.1 es "esta misma computadora".
# Cuando el rover sea una Raspberry Pi, aquí irá su dirección en tu WiFi.
HOST = "127.0.0.1"
PUERTO = 5050