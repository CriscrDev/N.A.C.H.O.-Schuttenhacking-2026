"""Aquí se revisan las alarmas de la tripulación y del entorno.

Nivel 1 es alerta (ámbar) y nivel 2 es crítico (rojo).
Cada alarma sale como (nivel, parámetro, mensaje).
"""

from .estres import LIMITE_ALTO
from .huesos import LIMITE_ALERTA
from .radiacion import LIMITE_CARRERA, sintomas_probables

ALERTA = 1
CRITICO = 2


def evaluar_tripulante(a):
    """Regresa las alarmas activas de un tripulante."""
    alarmas = []

    # en paro no hay signos que revisar
    if a.sin_pulso:
        nombre, desfibrilable = a.ritmo
        tipo = "ritmo desfibrilable" if desfibrilable else "ritmo no desfibrilable"
        return [(CRITICO, "paro", f"PARO CARDIACO, sin signos ({nombre.lower()}, {tipo})")]

    fc = a.fc
    if fc < 36 or fc > 160:
        alarmas.append((CRITICO, "fc", f"Frecuencia cardiaca {'muy baja' if fc < 36 else 'muy alta'} ({fc:.0f} lpm)"))
    elif fc < 44 or fc > 132:
        alarmas.append((ALERTA, "fc", f"Frecuencia cardiaca {'baja' if fc < 44 else 'alta'} ({fc:.0f} lpm)"))
    if a.extrasistoles_recientes >= 2:
        alarmas.append((ALERTA, "fc", "Extrasístoles ventriculares frecuentes"))

    if a.spo2 < 90:
        alarmas.append((CRITICO, "spo2", f"Saturación de oxígeno crítica ({a.spo2:.0f} %)"))
    elif a.spo2 < 94:
        alarmas.append((ALERTA, "spo2", f"Saturación de oxígeno baja ({a.spo2:.0f} %)"))

    fr = a.fr
    if fr < 6 or fr > 36:
        alarmas.append((CRITICO, "fr", f"Frecuencia respiratoria {'baja' if fr < 6 else 'muy alta'} ({fr:.0f} rpm)"))
    elif fr < 8 or fr > 30:
        alarmas.append((ALERTA, "fr", f"Frecuencia respiratoria {'baja' if fr < 8 else 'alta'} ({fr:.0f} rpm)"))

    if a.temp > 38.8:
        alarmas.append((CRITICO, "temp", f"Temperatura corporal crítica ({a.temp:.1f} °C)"))
    elif a.temp > 37.9:
        alarmas.append((ALERTA, "temp", f"Temperatura corporal alta ({a.temp:.1f} °C)"))
    elif a.temp < 35.5:
        alarmas.append((ALERTA, "temp", f"Temperatura corporal baja ({a.temp:.1f} °C)"))

    sis = a.pni_sis
    if sis > 180 or sis < 80:
        alarmas.append((CRITICO, "pni", f"Presión arterial {'muy alta' if sis > 180 else 'muy baja'} ({sis}/{a.pni_dia})"))
    elif sis > 162 or sis < 90:
        alarmas.append((ALERTA, "pni", f"Presión arterial {'alta' if sis > 162 else 'baja'} ({sis}/{a.pni_dia})"))

    # PAM: abajo de 65 mmHg ya no llega bien la sangre a los órganos
    pam = a.pam
    if pam < 60:
        alarmas.append((CRITICO, "pam", f"PAM crítica ({pam} mmHg): perfusión insuficiente"))
    elif pam < 70:
        alarmas.append((ALERTA, "pam", f"PAM baja ({pam} mmHg)"))

    # nivel de estrés (índice de 0 a 100)
    if a.estres >= LIMITE_ALTO:
        alarmas.append((ALERTA, "estres", f"Nivel de estrés alto ({a.estres:.0f} de 100)"))

    # pérdida ósea por microgravedad: riesgo de fractura
    cadera = a.perdida_osea["cadera"]
    if cadera > LIMITE_ALERTA:
        alarmas.append((ALERTA, "hueso", f"Pérdida ósea elevada en cadera ({cadera:.1f} %)"))

    # radiación: síntomas probables según la dosis del evento y límite de carrera
    nivel, resumen, _ = sintomas_probables(a.dosis_evento, 0.0)
    if nivel:
        alarmas.append((nivel, "dosis", f"Radiación: {resumen} (dosis {a.dosis_evento:.0f} mSv)"))
    if a.dosis > LIMITE_CARRERA:
        alarmas.append((ALERTA, "carrera", f"Límite de dosis de carrera superado ({a.dosis:.0f} mSv)"))

    # indicadores de riesgo de la misión (columna, inmunidad, flujo venoso, etc.)
    for r in a.riesgos:
        if r["nivel"]:
            alarmas.append((r["nivel"], r["clave"], r["mensaje"]))

    return alarmas


def evaluar_entorno(e):
    """Regresa las alarmas activas del entorno."""
    alarmas = []
    if e.pp_o2 < 15.5:
        alarmas.append((CRITICO, "o2", f"Oxígeno respirable crítico ({e.pp_o2:.1f} kPa)"))
    elif e.pp_o2 < 18.0:
        alarmas.append((ALERTA, "o2", f"Oxígeno respirable bajo ({e.pp_o2:.1f} kPa)"))

    if e.co2 > 8.0:
        alarmas.append((CRITICO, "co2", f"CO2 crítico ({e.co2:.1f} mmHg)"))
    elif e.co2 > 5.3:
        alarmas.append((ALERTA, "co2", f"CO2 elevado ({e.co2:.1f} mmHg)"))

    if e.tasa_radiacion > 2.0:
        alarmas.append((CRITICO, "rad", f"Radiación crítica, buscar refugio ({e.tasa_radiacion:.1f} mSv/h)"))
    elif e.tasa_radiacion > 0.5:
        alarmas.append((ALERTA, "rad", f"Radiación elevada ({e.tasa_radiacion:.1f} mSv/h)"))
    return alarmas


def nivel_maximo(alarmas):
    return max((a[0] for a in alarmas), default=0)


def niveles_por_parametro(alarmas):
    """Nivel más alto de cada parámetro, para resaltar su panel."""
    niveles = {}
    for nivel, parametro, _ in alarmas:
        niveles[parametro] = max(nivel, niveles.get(parametro, 0))
    return niveles
