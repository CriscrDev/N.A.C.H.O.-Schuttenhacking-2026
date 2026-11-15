"""Contador Geiger y síntomas probables según la dosis.

NASA dice que la radiación espacial sube el riesgo de cáncer y afecta al
sistema nervioso. Los síntomas por rango de dosis los tomamos de la
descripción médica general del síndrome agudo de radiación (aproximado).
"""

import math
import random

UMBRAL_EVENTO = 0.5          # mSv/h a partir de los cuales se considera un evento de radiación
LIMITE_CARRERA = 600.0       # mSv: límite de dosis para toda la carrera de un astronauta
# en una tormenta aceleramos la exposición para que se note en la demo:
# cada segundo cuenta como dos minutos
ACELERACION_EXPOSICION = 120.0

# dosis mínima del evento (mSv), nivel de alarma, resumen, síntomas probables
_ESCALA = (
    (2000.0, 2, "síndrome agudo de radiación",
     "Vómito intenso, diarrea, fiebre y riesgo de infección y hemorragia. Atención urgente."),
    (1000.0, 2, "náuseas, vómito e inmunosupresión probables",
     "Náuseas y vómito en pocas horas, fatiga marcada y caída de las defensas."),
    (500.0, 1, "náuseas y fatiga probables",
     "Náuseas, pérdida de apetito y fatiga en las próximas horas."),
    (250.0, 1, "descenso de linfocitos probable",
     "Descenso de linfocitos y fatiga leve. Vigilar análisis de sangre."),
    (50.0, 0, "sin síntomas agudos",
     "Sin síntomas agudos. Mayor riesgo de cáncer a largo plazo; vigilar cognición, "
     "función motora y conducta."),
)


def sintomas_probables(dosis_evento, tasa):
    """Regresa (nivel, resumen, texto) para la dosis recibida en el evento."""
    for minimo, nivel, resumen, texto in _ESCALA:
        if dosis_evento >= minimo:
            return nivel, resumen, texto
    if tasa > UMBRAL_EVENTO:
        return 0, "exposición en curso", "Exposición en curso, aún sin síntomas. Buscar refugio y reducir el tiempo expuesto."
    return 0, "sin síntomas", "Sin síntomas esperados."


def cuentas_por_segundo(tasa):
    """Ritmo medio de detecciones del contador para una tasa en mSv/h."""
    return 1.2 * (max(0.0, tasa) * 1000.0) ** 0.7


def detecciones(media):
    """Número aleatorio de detecciones (distribución de Poisson)."""
    if media <= 0.0:
        return 0
    if media > 30.0:
        return max(0, round(random.gauss(media, math.sqrt(media))))
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= random.random()
        if p <= limite:
            return k
        k += 1
