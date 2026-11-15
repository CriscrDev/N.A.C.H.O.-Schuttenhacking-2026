"""Recomendaciones de rutina para el bienestar de la tripulación.

Cada cierto tiempo el monitor le propone al tripulante una actividad corta
para estar presente y aguantar mejor el aislamiento. Tomamos ideas de lo que
NASA menciona (diario, luz para el sueño, plantas, familia y equipo) y de
ejercicios conocidos: respiración lenta, respiración en caja, 5-4-3-2-1,
relajación muscular y "tres cosas buenas".

Es un prototipo, no reemplaza el apoyo psicológico de la misión.
"""

import random

from .guias import Guia

SEGUNDOS_ENTRE_RECOMENDACIONES = 75.0   # lo dejamos corto para que se alcance a ver en la demo
SEGUNDOS_PRIMERA = 30.0

# cada actividad: clave, título, por qué ayuda, pasos y opciones de la ventana
# "calma" marca las que sirven para bajar el estrés en el momento
_ACTIVIDADES = (
    dict(clave="respiracion_lenta", calma=True, titulo="RESPIRE LENTO UN MINUTO",
         resumen="Respirar unas 6 veces por minuto calma el cuerpo y mejora la variabilidad del corazón.",
         pasos=["Sujétese en un lugar cómodo y relaje los hombros.",
                "Tome aire por la nariz mientras el círculo crece (4 segundos).",
                "Suelte el aire por la boca mientras el círculo se achica (6 segundos).",
                "Ponga su atención solo en el aire que entra y sale."],
         modo="respiracion", respiracion=(4.0, 6.0), duracion=60.0, alivio=6.0),
    dict(clave="respiracion_caja", calma=True, titulo="RESPIRACIÓN EN CAJA",
         resumen="Cuatro tiempos iguales. Es una técnica muy usada para mantener la calma bajo presión.",
         pasos=["Tome aire contando 4.",
                "Sostenga el aire contando 4.",
                "Suelte el aire contando 4.",
                "Quédese sin aire contando 4. Siga el contador hasta que termine."],
         modo="respiracion", respiracion=(4.0, 4.0, 4.0, 4.0), duracion=64.0, alivio=6.0),
    dict(clave="anclaje", calma=True, titulo="VUELVA AL MOMENTO: 5-4-3-2-1",
         resumen="Usar los cinco sentidos trae la mente al presente y corta las preocupaciones.",
         pasos=["Nombre 5 cosas que puede VER a su alrededor.",
                "Nombre 4 cosas que puede TOCAR. Tóquelas.",
                "Nombre 3 cosas que puede ESCUCHAR.",
                "Nombre 2 cosas que puede OLER.",
                "Nombre 1 cosa que puede SABOREAR. Respire hondo una vez."],
         alivio=16.0),
    dict(clave="relajacion", calma=True, titulo="RELAJE SUS MÚSCULOS",
         resumen="Apretar y soltar cada grupo de músculos quita la tensión acumulada del cuerpo.",
         pasos=["Apriete los puños 5 segundos y suéltelos de golpe. Note la diferencia.",
                "Suba los hombros hasta las orejas 5 segundos y suéltelos.",
                "Apriete el abdomen 5 segundos y suéltelo.",
                "Apriete piernas y pies 5 segundos y suéltelos.",
                "Termine con tres respiraciones lentas."],
         alivio=16.0),
    dict(clave="diario", calma=False, titulo="ESCRIBA EN SU DIARIO",
         resumen="NASA usa los diarios de a bordo para cuidar el ánimo durante el aislamiento.",
         pasos=["Abra su diario personal.",
                "Escriba 3 líneas: qué hizo hoy, cómo se siente y qué espera de mañana.",
                "No importa la ortografía: nadie más lo leerá."],
         alivio=14.0),
    dict(clave="tres_cosas", calma=False, titulo="TRES COSAS BUENAS",
         resumen="Recordar lo que salió bien mejora el ánimo y ayuda a dormir mejor.",
         pasos=["Piense en 3 cosas buenas de hoy, aunque sean pequeñas.",
                "Diga por qué pasó cada una.",
                "Cuénteselas a un compañero o anótelas en su diario."],
         alivio=12.0),
    dict(clave="tierra", calma=False, titulo="MIRE LA TIERRA",
         resumen="Mirar el planeta por la ventana da calma y recuerda el sentido de la misión.",
         pasos=["Vaya a la ventana más cercana.",
                "Mire la Tierra durante 2 minutos sin hacer nada más.",
                "Busque un lugar que conozca o tome una foto para su familia."],
         alivio=14.0),
    dict(clave="plantas", calma=False, titulo="CUIDE LAS PLANTAS",
         resumen="NASA estudia cómo cuidar plantas a bordo alivia el encierro y el aislamiento.",
         pasos=["Vaya al módulo de cultivo.",
                "Revise el agua y la luz de las plantas.",
                "Tóquelas, huélalas y anote cuánto han crecido."],
         alivio=12.0),
    dict(clave="compania", calma=False, titulo="HABLE CON ALGUIEN",
         resumen="El contacto con la familia y el equipo es la mejor defensa contra el aislamiento.",
         pasos=["Busque a un compañero y pregúntele cómo está. Escuche sin interrumpir.",
                "Cuéntele algo de su día que no sea de trabajo.",
                "Si hay enlace disponible, grabe un mensaje corto para su familia."],
         alivio=16.0),
    dict(clave="movimiento", calma=False, titulo="ESTÍRESE DOS MINUTOS",
         resumen="El movimiento baja la tensión y además protege huesos y músculos en microgravedad.",
         pasos=["Sujete los pies y estire los brazos hacia arriba 10 segundos.",
                "Gire el cuello despacio a cada lado, 5 veces.",
                "Lleve cada rodilla al pecho 10 segundos.",
                "Abra y cierre las manos 20 veces."],
         alivio=10.0),
    dict(clave="luz_agua", calma=False, titulo="PAUSA DE LUZ Y AGUA",
         resumen="La luz adecuada ordena el reloj del cuerpo y el sueño; el agua mantiene la atención.",
         pasos=["Beba un vaso de agua a sorbos.",
                "Si es su mañana: encienda la luz brillante. Si falta poco para dormir: baje la luz.",
                "Aparte la vista de las pantallas 1 minuto y mire algo lejano."],
         alivio=8.0),
    dict(clave="reto_mental", calma=False, titulo="RETO MENTAL RÁPIDO",
         resumen="Un juego corto ocupa la mente en algo distinto y rompe la monotonía.",
         pasos=["Cuente hacia atrás desde 100 restando de 7 en 7, hasta llegar a 30.",
                "Diga un país por cada letra de su nombre.",
                "Rete a un compañero a hacerlo más rápido."],
         alivio=10.0),
)


class Recomendador:
    """Elige la siguiente recomendación sin repetir las más recientes."""

    def __init__(self):
        self._recientes = []

    def elegir(self, astronauta):
        """Con estrés moderado o alto se priorizan las actividades que calman."""
        opciones = [d for d in _ACTIVIDADES if d["clave"] not in self._recientes]
        if astronauta.estres >= 40.0:
            calmantes = [d for d in opciones if d["calma"]]
            opciones = calmantes or opciones
        datos = random.choice(opciones)
        self._recientes.append(datos["clave"])
        del self._recientes[:-6]
        return Guia(
            "rutina_" + datos["clave"], datos["titulo"], 0, datos["resumen"], datos["pasos"],
            modo=datos.get("modo"), respiracion=datos.get("respiracion"), rutina=True,
            duracion=datos.get("duracion"), alivio=datos["alivio"],
            acciones=(("Hecho", "rutina_hecha"), ("Ahora no", "rutina_posponer")))
