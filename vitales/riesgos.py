"""Indicadores de los riesgos de salud en el espacio.

Uno por cada línea de investigación de NASA que revisamos: columna,
inmunidad, hemostasia venosa, biomarcadores del líquido espinal, presión del
líquido cerebral y SANS. Las fórmulas son aproximaciones nuestras.
"""

import math

# clave y nombre de cada indicador, en el orden en que se muestran
INDICADORES = (
    ("columna", "Columna: músculo paraespinal"),
    ("inmunidad", "Inmunidad: linfocitos"),
    ("venoso", "Flujo venoso yugular"),
    ("lcr", "Biomarcador neuronal en LCR"),
    ("pic", "Presión intracraneal"),
    ("sans", "SANS: engrosamiento retiniano"),
)


def _fraccion(x):
    return max(0.0, min(1.0, x))


def calcular_riesgos(a, dias, entorno):
    """Regresa la lista de indicadores del tripulante.

    Cada uno trae clave, nombre, valor (texto), detalle, fraccion (0 bien,
    1 mal), nivel de alarma y mensaje.
    """
    f = a.factores
    dias = max(0.0, dias)
    meses = dias / 30.0
    lista = []

    def agregar(clave, valor, detalle, fraccion, nivel, mensaje):
        lista.append(dict(clave=clave, nombre=dict(INDICADORES)[clave], valor=valor, detalle=detalle,
                          fraccion=_fraccion(fraccion), nivel=nivel, mensaje=mensaje))

    # columna: sin carga, los músculos que la sostienen se atrofian y la columna se alarga
    musculo = 20.0 * (1.0 - math.exp(-meses * f["columna"] / 9.0))
    estatura = 4.5 * (1.0 - math.exp(-dias / 3.0))
    agregar("columna", f"-{musculo:.1f} %", f"Estatura +{estatura:.1f} cm", musculo / 20.0,
            1 if musculo >= 12.0 else 0, f"Pérdida de músculo de la columna ({musculo:.0f} %)")

    # inmunidad: los linfocitos bajan con el tiempo de misión y con la radiación recibida
    linfocitos = (2.3 * f["inmunidad"] - 0.3 * (1.0 - math.exp(-meses / 3.0))
                  - 1.4 * min(1.0, a.dosis_evento / 1500.0))
    linfocitos = max(0.1, linfocitos)
    nivel = 2 if linfocitos < 0.5 else 1 if linfocitos < 1.0 else 0
    agregar("inmunidad", f"{linfocitos:.1f} x10³/µL", "Normal 1.0 a 4.8", (2.6 - linfocitos) / 2.1,
            nivel, f"Linfocitos bajos, inmunidad reducida ({linfocitos:.1f} x10³/µL)")

    # hemostasia venosa: el flujo de la vena yugular se enlentece; el estancamiento favorece coágulos
    flujo = 22.0 * f["venoso"] * (1.0 - 0.68 * (1.0 - math.exp(-dias / 40.0)))
    nivel = 2 if flujo < 3.0 else 1 if flujo < 7.0 else 0
    agregar("venoso", f"{flujo:.1f} cm/s", "Estasis bajo 7", (22.0 - flujo) / 19.0,
            nivel, f"Flujo yugular lento, riesgo de trombosis ({flujo:.1f} cm/s)")

    # biomarcador en líquido cefalorraquídeo (neurofilamento ligero): sube con el daño neuronal
    nfl = 450.0 * f["lcr"] + 30.0 * min(meses, 12.0) + 0.25 * a.dosis_evento
    agregar("lcr", f"{nfl:.0f} pg/mL", "Límite 900", (nfl - 400.0) / 700.0,
            1 if nfl > 900.0 else 0, f"Biomarcador neuronal elevado en LCR ({nfl:.0f} pg/mL)")

    # presión intracraneal: sube por el desplazamiento de líquidos hacia la cabeza y por el CO2
    pic = (10.0 + 2.0 * f["pic"] + 2.5 * (1.0 - math.exp(-dias / 15.0))
           + 1.6 * max(0.0, entorno.co2 - 3.5) + 0.8 * entorno.aceleracion)
    nivel = 2 if pic > 25.0 else 1 if pic > 20.0 else 0
    agregar("pic", f"{pic:.1f} mmHg", "Límite 20", (pic - 10.0) / 15.0,
            nivel, f"Presión intracraneal alta ({pic:.0f} mmHg)")

    # SANS: engrosamiento de la retina alrededor del nervio óptico; 20 µm o más es el criterio
    retina = 28.0 * f["sans"] * (1.0 - math.exp(-dias / 90.0)) + 1.2 * max(0.0, pic - 16.0)
    agregar("sans", f"+{retina:.0f} µm", "Criterio 20 µm", retina / 40.0,
            1 if retina >= 20.0 else 0, f"Signos de síndrome neuroocular ({retina:.0f} µm)")

    return lista
