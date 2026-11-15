"""Nivel de estrés de cada tripulante (de 0 a 100).

Nos basamos en lo que miden los estudios de estrés en astronautas:
- variabilidad de la frecuencia cardiaca (RMSSD), que baja con el estrés
- índice de Baevsky, SI = AMo / (2 x Mo x MxDMn), normal entre 50 y 150
- cortisol en saliva, que sube con el estrés

Ojo: todo es simulado. Cada situación (fase, evento médico, entorno,
aislamiento) suma puntos y de ahí sacamos los marcadores. Son aproximaciones
nuestras para el prototipo.
"""

import math

from .radiacion import UMBRAL_EVENTO

BASAL = 14.0            # estrés normal de alguien descansado
LIMITE_MODERADO = 40.0
LIMITE_ALTO = 70.0      # de aquí para arriba avisamos y sale la guía de respiración
LIMITE_MUY_ALTO = 85.0
ALIVIO_MAXIMO = 40.0    # lo máximo que pueden bajar las actividades de bienestar

# puntos de carga por fase de misión
_CARGA_FASE = {"reposo": 0, "sueno": -8, "ejercicio": 8, "lanzamiento": 35, "eva": 24, "reentrada": 38}

# puntos de carga por el evento médico del propio tripulante
_CARGA_EVENTO = {
    "estres": 55, "hipoxia": 30, "taquicardia": 26, "taquipnea": 30, "arritmia": 20,
    "hipertermia": 20, "hipotermia": 20, "bradicardia": 12, "bradipnea": 15,
    "infarto": 50, "ictus": 42,
}


def calcular_factores(a, fase, entorno, dias, nombres_fase, nombres_evento):
    """Lista de (causa, puntos) que suben o bajan el estrés del tripulante."""
    factores = []

    # aislamiento y confinamiento: crece con los días de misión
    aislamiento = 14.0 * (1.0 - math.exp(-dias / 120.0))
    factores.append(("Aislamiento", aislamiento))

    carga = _CARGA_FASE.get(fase, 0)
    if carga:
        factores.append((nombres_fase[fase]["nombre"], carga))

    if a.gravedad > 0.0:
        factores.append(("Descompensación", 25.0 + 35.0 * a.gravedad))
    carga = _CARGA_EVENTO.get(a.evento, 0)
    if carga:
        factores.append((nombres_evento[a.evento]["nombre"], carga))

    # entorno
    if entorno.evento == "fuga":
        factores.append(("Fuga de presión", 28.0))
    if entorno.co2 > 3.5:
        factores.append(("CO2 elevado", min(20.0, 3.2 * (entorno.co2 - 3.5))))
    if entorno.tasa_radiacion > UMBRAL_EVENTO:
        puntos = 12.0 + 8.0 * math.log10(entorno.tasa_radiacion / UMBRAL_EVENTO)
        factores.append(("Tormenta solar", min(32.0, puntos)))

    # emergencia de un compañero
    if a.carga_equipo:
        factores.append(("Emergencia de un compañero", a.carga_equipo))

    return [(nombre, puntos * a.sensibilidad) for nombre, puntos in factores]


def objetivo(factores, alivio):
    """Estrés hacia el que tiende el tripulante con sus factores actuales."""
    return max(2.0, min(100.0, BASAL + sum(p for _, p in factores) - alivio))


def rmssd(estres, basal):
    """Variabilidad cardiaca (ms): cae de forma exponencial con el estrés."""
    return basal * math.exp(-1.7 * (estres - BASAL) / 100.0)


def indice_baevsky(estres):
    """Índice de tensión de Baevsky (unidades convencionales)."""
    return 62.0 * math.exp(2.6 * estres / 100.0)


def cortisol(estres):
    """Cortisol en saliva (nmol/L) hacia el que tiende el tripulante."""
    return 8.0 + 0.3 * estres


def nivel(estres):
    """Regresa (número de nivel 0 a 3, nombre)."""
    if estres >= LIMITE_MUY_ALTO:
        return 3, "Muy alto"
    if estres >= LIMITE_ALTO:
        return 2, "Alto"
    if estres >= LIMITE_MODERADO:
        return 1, "Moderado"
    return 0, "Bajo"
