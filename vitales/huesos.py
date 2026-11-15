"""Pérdida de hueso por microgravedad (simulada).

Sin gravedad los huesos que cargan el peso (cadera, columna lumbar, piernas)
pierden como 1 a 1.5 % de densidad al mes; brazos y cráneo casi nada.
El ejercicio ayuda a perder menos. Los valores son aproximados.
"""

import math

# clave, nombre, pérdida de densidad en % por mes sin contramedidas
REGIONES = (
    ("craneo", "Cráneo", 0.0),
    ("toracica", "Columna torácica", 0.6),
    ("costillas", "Tórax", 0.3),
    ("humero", "Húmero", 0.1),
    ("antebrazo", "Antebrazo", 0.1),
    ("lumbar", "Columna lumbar", 1.0),
    ("pelvis", "Pelvis", 1.3),
    ("cadera", "Cadera", 1.5),
    ("femur", "Fémur", 1.3),
    ("tibia", "Tibia", 1.2),
    ("calcaneo", "Calcáneo", 1.4),
)
NOMBRES = {clave: nombre for clave, nombre, _ in REGIONES}

# huesos de carga: son los que definen la densidad global y el riesgo
DE_CARGA = ("lumbar", "pelvis", "cadera", "femur", "tibia", "calcaneo")

PERDIDA_MAXIMA = 25.0   # la pérdida se estabiliza en este porcentaje
LIMITE_ALERTA = 10.0    # pérdida en cadera a partir de la cual se avisa


# la radiación fuerte también daña el hueso, sobre todo columna, pelvis y cadera
# aquí va cuánto le pega a cada región
_PESO_RADIACION = {
    "craneo": 0.3, "toracica": 0.9, "costillas": 0.7, "humero": 0.5, "antebrazo": 0.4,
    "lumbar": 1.0, "pelvis": 1.0, "cadera": 1.0, "femur": 0.8, "tibia": 0.6, "calcaneo": 0.5,
}
PERDIDA_MAXIMA_RADIACION = 8.0   # % adicional como máximo en las regiones más sensibles


def perdida_por_radiacion(dosis):
    """Pérdida ósea adicional (%) en las regiones más sensibles para una dosis en mSv."""
    return PERDIDA_MAXIMA_RADIACION * (1.0 - math.exp(-max(0.0, dosis) / 1200.0))


def calcular_perdidas(dias_mision, factor, dosis_radiacion=0.0):
    """Pérdida de densidad (%) de cada región según los días de misión.

    factor: qué tanto pierde cada quien (menos de 1 = pierde menos hueso).
    dosis_radiacion: los mSv de las tormentas, que suman más pérdida.
    """
    meses = max(0.0, dias_mision) / 30.0
    extra = perdida_por_radiacion(dosis_radiacion)
    return {
        clave: PERDIDA_MAXIMA * (1.0 - math.exp(-tasa * factor * meses / PERDIDA_MAXIMA))
        + extra * _PESO_RADIACION[clave]
        for clave, _, tasa in REGIONES
    }


def lesiones_probables(perdidas, dosis_radiacion=0.0):
    """Lesiones óseas probables según la pérdida de cada región, en lenguaje sencillo."""
    lesiones = []
    if perdidas["cadera"] >= 10.0 or perdidas["femur"] >= 10.0:
        lesiones.append("Cadera o fémur: fractura por golpes")
    if perdidas["lumbar"] >= 8.0:
        lesiones.append("Vértebras: aplastamiento al cargar")
    if perdidas["calcaneo"] >= 9.0 or perdidas["tibia"] >= 9.0:
        lesiones.append("Pierna o talón: fractura al caminar")
    if perdidas["pelvis"] >= 9.0 and len(lesiones) < 3:
        lesiones.append("Pelvis: fisura en impactos")
    extra = perdida_por_radiacion(dosis_radiacion)
    if extra >= 0.5:
        lesiones.insert(0, f"Radiación: -{extra:.1f} % extra en columna")
    if not lesiones:
        lesiones.append("Sin lesiones probables por ahora")
    return lesiones[:4]


def densidad_global(perdidas):
    """Densidad ósea restante (%) promediando los huesos de carga."""
    return 100.0 - sum(perdidas[c] for c in DE_CARGA) / len(DE_CARGA)


def riesgo_fractura(perdidas, aceleracion=0.0):
    """Índice de 0 a 1; aumenta con la pérdida en cadera y con la aceleración."""
    riesgo = perdidas["cadera"] / 15.0 * (1.0 + 0.15 * aceleracion)
    return max(0.0, min(1.0, riesgo))


def nivel_riesgo(riesgo):
    if riesgo < 0.33:
        return "Bajo"
    if riesgo < 0.66:
        return "Moderado"
    return "Alto"
