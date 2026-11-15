"""Guías paso a paso para cada emergencia.

Los astronautas NO son médicos, así que van frases cortas, una acción por
paso y sin palabras técnicas. Es un prototipo, no reemplaza los
procedimientos médicos oficiales.
"""

from .modelo import PARO

ALERTA = 1
CRITICO = 2


class Guia:
    """Instrucciones que el monitor muestra en la ventana emergente."""

    def __init__(self, clave, titulo, nivel, resumen, pasos, modo=None, acciones=(),
                 avisar=False, estado=None, respiracion=None, rutina=False, duracion=None,
                 alivio=0.0):
        self.clave = clave            # identifica la guía (si cambia, se redibuja la ventana)
        self.titulo = titulo
        self.nivel = nivel
        self.resumen = resumen        # qué está pasando, en una frase
        self.pasos = pasos            # qué hacer, en orden
        self.modo = modo              # none, "respiracion" o "rcp": contador animado
        self.acciones = acciones      # botones: (texto, clave de acción)
        self.avisar = avisar          # enviar alerta a toda la tripulación
        self.estado = estado          # función que regresa el dato en vivo que hay que vigilar
        # (segundos de inhalar, de exhalar) o (inhalar, sostener, exhalar, sostener)
        self.respiracion = respiracion
        self.rutina = rutina          # recomendación de rutina, no una emergencia
        self.duracion = duracion      # segundos que dura la actividad (None: la cierra el tripulante)
        self.alivio = alivio          # puntos de estrés que resta al completarla


def _si_no(valor):
    return "sí" if valor else "no"


def guia_para(a, entorno, fase):
    """Regresa la guía más urgente para el tripulante, o None si no hace falta."""
    en_actividad = fase in ("ejercicio", "lanzamiento", "reentrada")

    # paro cardiaco
    if a.sin_pulso:
        nombre, desfibrilable = PARO[a.evento]
        inicio = [
            "PIDA AYUDA: la alerta ya se envió a toda la tripulación.",
            "Háblele fuerte y sacuda sus hombros. Si no responde y no respira, siga.",
            "Sujete al paciente boca arriba sobre una superficie firme y sujétese usted con las correas.",
            "COMPRESIONES: manos una sobre otra en el centro del pecho. Empuje fuerte y rápido, "
            "al ritmo del contador, sin parar.",
            "Otro tripulante trae el desfibrilador, lo enciende y pega los dos parches sobre el pecho "
            "desnudo, como muestra el dibujo de los parches.",
        ]
        if desfibrilable:
            pasos = inicio + [
                "RITMO DESFIBRILABLE: digan todos 'fuera', nadie toca al paciente, y presione DAR DESCARGA.",
                "Después de la descarga siga con las compresiones 2 minutos: 30 compresiones y 2 respiraciones "
                "con la mascarilla. Luego repita la descarga si el monitor lo indica.",
            ]
            acciones = (("Compresiones iniciadas", "rcp"), ("DAR DESCARGA", "descarga"))
            resumen = f"El corazón no bombea sangre. {nombre}: la descarga SÍ puede salvarlo."
        else:
            pasos = inicio + [
                "RITMO NO DESFIBRILABLE: NO dé descarga, en este ritmo no sirve.",
                "No pare las compresiones: 30 compresiones y 2 respiraciones con la mascarilla. "
                "Cambien de persona cada 2 minutos para no cansarse.",
            ]
            acciones = (("Compresiones iniciadas", "rcp"),)
            resumen = f"El corazón no bombea sangre. {nombre}: la descarga NO sirve, solo compresiones."
        return Guia("paro_" + a.evento, "SIN SIGNOS", CRITICO, resumen, pasos, modo="rcp",
                    acciones=acciones, avisar=True,
                    estado=lambda: f"Compresiones: {_si_no(a.rcp)}   ·   Tiempo en paro: "
                                   f"{int(a.t_paro) // 60}:{int(a.t_paro) % 60:02d}")

    # descompensación: necesita ayuda de la tripulación
    if a.gravedad >= 0.35 or a.pam < 60:
        return Guia(
            "descompensacion", "NECESITA AYUDA", CRITICO,
            "Su presión está cayendo y el cuerpo no recibe suficiente sangre.",
            [
                "La alerta ya se envió a la tripulación. No deje solo al paciente.",
                "Acuéstelo y sujételo con las correas. Levante sus piernas unos 30 centímetros.",
                "Colóquele la mascarilla de oxígeno y abra el flujo.",
                "Abríguelo. No le dé comida ni bebida.",
                "Traiga el desfibrilador y déjelo encendido junto al paciente.",
                "Llame al médico de vuelo y lea en voz alta los números del monitor.",
                "Si deja de responder y no respira: inicie compresiones en el pecho.",
            ],
            acciones=(("Oxígeno colocado", "oxigeno"),), avisar=True,
            estado=lambda: f"PAM {a.pam} mmHg (debe estar sobre 65)   ·   FC {a.fc:.0f}   ·   "
                           f"Oxígeno: {_si_no(a.oxigeno)}")

    # lesiones del corazón y del cerebro
    if a.evento == "infarto":
        return Guia(
            "infarto", "POSIBLE INFARTO", CRITICO,
            "El corazón no recibe suficiente sangre. Suele doler el pecho, el brazo o la mandíbula.",
            [
                "La alerta ya se envió a la tripulación. El paciente no debe hacer ningún esfuerzo.",
                "Siéntelo medio recostado, sujételo y afloje su ropa.",
                "Colóquele la mascarilla de oxígeno.",
                "Si está despierto y no es alérgico: que mastique una aspirina del botiquín.",
                "Traiga el desfibrilador y déjelo encendido a su lado.",
                "Llame al médico de vuelo. Anote la hora en que empezó el dolor.",
                "Si pierde el conocimiento y no respira: inicie compresiones en el pecho.",
            ],
            acciones=(("Oxígeno colocado", "oxigeno"),), avisar=True,
            estado=lambda: f"FC {a.fc:.0f}   ·   Presión {a.pni_sis}/{a.pni_dia}   ·   SpO2 {a.spo2:.0f} %")

    if a.evento == "ictus":
        return Guia(
            "ictus", "POSIBLE DAÑO CEREBRAL", CRITICO,
            "Puede ser un derrame o un coágulo en el cerebro. Cada minuto cuenta.",
            [
                "La alerta ya se envió a la tripulación. Anote la hora exacta en que empezó.",
                "CARA: pídale que sonría. Vea si un lado de la boca cae.",
                "BRAZOS: pídale que levante los dos brazos. Vea si uno baja solo.",
                "HABLA: pídale que repita una frase. Escuche si habla raro o no entiende.",
                "Sujételo con la cabeza un poco elevada. No le dé comida, bebida ni medicinas.",
                "Colóquele oxígeno si el número SpO2 baja de 94.",
                "Llame de inmediato al médico de vuelo y diga lo que vio en cara, brazos y habla.",
            ],
            acciones=(("Oxígeno colocado", "oxigeno"),), avisar=True,
            estado=lambda: f"Presión {a.pni_sis}/{a.pni_dia} (muy alta)   ·   FC {a.fc:.0f}   ·   SpO2 {a.spo2:.0f} %")

    # oxígeno bajo
    # (si respira muy lento, primero sale la guía de respiración)
    respira_lento = a.fr < 8 or a.evento == "bradipnea"
    if a.spo2 < 94 and not respira_lento:
        critico = a.spo2 < 90
        pasos = [
            "Tome la mascarilla de oxígeno más cercana.",
            "Póngala sobre nariz y boca y ajuste la banda detrás de la cabeza.",
            "Abra la válvula del oxígeno hasta sentir el flujo.",
            "Respire lento y profundo. Deténgase y sujétese: no haga esfuerzos.",
            "Mire el número SpO2: debe subir a 94 o más en pocos minutos.",
            "Si no sube, o siente mareo o confusión, avise a la tripulación.",
        ]
        if entorno.pp_o2 < 18.0:
            pasos.insert(0, "FALTA OXÍGENO EN EL AIRE: toda la tripulación debe usar mascarilla "
                            "e ir al módulo seguro.")
        return Guia(
            "spo2", "COLÓQUESE OXÍGENO", CRITICO if critico else ALERTA,
            "Su sangre lleva poco oxígeno.", pasos,
            acciones=(("Oxígeno colocado", "oxigeno"),), avisar=critico,
            estado=lambda: f"SpO2 {a.spo2:.0f} % (meta: 94 o más)   ·   Oxígeno colocado: {_si_no(a.oxigeno)}")

    # respiración
    if a.fr < 8 or a.evento == "bradipnea":
        return Guia(
            "bradipnea", "RESPIRE PROFUNDO", CRITICO,
            "Está respirando demasiado lento.",
            [
                "Siga el contador: tome aire cuando el círculo crece y suéltelo cuando se achica.",
                "Respire hondo, llenando el pecho.",
                "Si el paciente está dormido o no responde: despiértelo y háblele fuerte.",
                "Colóquele oxígeno si el número SpO2 baja de 94.",
                "Si no despierta o deja de respirar: pida ayuda e inicie compresiones.",
            ],
            modo="respiracion", respiracion=(2.0, 3.0), acciones=(("Oxígeno colocado", "oxigeno"),),
            avisar=True,
            estado=lambda: f"Respiraciones por minuto: {a.fr:.0f} (meta: 12 a 20)   ·   SpO2 {a.spo2:.0f} %")

    # la radiación va antes que los avisos leves
    if entorno.tasa_radiacion > 2.0:
        return Guia(
            "radiacion", "VAYA AL REFUGIO", CRITICO,
            "Hay radiación peligrosa por una tormenta solar.",
            [
                "Si está fuera de la nave: termine la salida y entre de inmediato.",
                "Toda la tripulación va al refugio contra radiación.",
                "Quédense en el refugio hasta que el contador baje.",
                "Avise si alguien tiene náuseas, vómito o mucho cansancio.",
                "Tomen agua y anoten la dosis que marca el contador de cada persona.",
            ],
            estado=lambda: f"Radiación {entorno.tasa_radiacion:.0f} mSv/h   ·   Dosis recibida {a.dosis_evento:.0f} mSv")

    # la dejamos mientras el contador hace efecto, para no cortarlo a medias
    rapida = a.fr > 30 or (a.calma > 0.05 and a.fr > 20)
    if a.evento == "taquipnea" or (rapida and not en_actividad):
        return Guia(
            "taquipnea", "RESPIRE DESPACIO", ALERTA,
            "Está respirando demasiado rápido.",
            [
                "Deténgase, sujétese y relaje los hombros.",
                "Siga el contador: tome aire por la nariz mientras el círculo crece.",
                "Suelte el aire despacio por la boca mientras el círculo se achica.",
                "Siga así hasta que el número de respiraciones baje de 20.",
                "Si siente hormigueo, mareo o dolor en el pecho, avise a la tripulación.",
            ],
            modo="respiracion", respiracion=(4.0, 6.0),
            estado=lambda: f"Respiraciones por minuto: {a.fr:.0f} (meta: menos de 20)")

    # frecuencia cardiaca
    if a.fc > 132 and not en_actividad:
        critico = a.fc > 160
        return Guia(
            "taquicardia", "CORAZÓN MUY RÁPIDO", CRITICO if critico else ALERTA,
            "Su corazón late demasiado rápido.",
            [
                "Deje lo que está haciendo, sujétese y quédese quieto.",
                "Respire lento: 4 segundos tomando aire y 6 soltándolo.",
                "Puje con fuerza 15 segundos, como si inflara un globo muy duro. Descanse y repita 2 veces.",
                "Mójese la cara con una toalla fría.",
                "Si hay dolor en el pecho, mareo, falta de aire o desmayo: avise ya a la tripulación.",
                "Si en 5 minutos no baja de 120, llame al médico de vuelo.",
            ],
            avisar=critico,
            estado=lambda: f"Latidos por minuto: {a.fc:.0f} (meta: menos de 120)   ·   {a.ritmo[0]}")

    if a.fc < 44 and fase != "sueno":
        critico = a.fc < 36
        return Guia(
            "bradicardia", "CORAZÓN MUY LENTO", CRITICO if critico else ALERTA,
            "Su corazón late demasiado lento.",
            [
                "Pregúntele cómo se siente. Si está bien y despierto, solo vigile el número.",
                "Si hay mareo, palidez, confusión o debilidad: acuéstelo y sujételo.",
                "Levante sus piernas unos 30 centímetros.",
                "Colóquele la mascarilla de oxígeno.",
                "Traiga el desfibrilador y déjelo encendido a su lado.",
                "Llame al médico de vuelo. Si se desmaya y no respira: inicie compresiones.",
            ],
            acciones=(("Oxígeno colocado", "oxigeno"),), avisar=critico,
            estado=lambda: f"Latidos por minuto: {a.fc:.0f} (meta: más de 50)   ·   Presión {a.pni_sis}/{a.pni_dia}")

    # temperatura
    if a.temp > 37.9 and a.evento == "hipertermia":
        return Guia(
            "hipertermia", "ENFRÍE AL PACIENTE", CRITICO if a.temp > 38.8 else ALERTA,
            "Su cuerpo está demasiado caliente.",
            [
                "Detenga toda actividad. En traje espacial: suba el enfriamiento al máximo.",
                "Quítele ropa y llévelo a la zona más fresca y ventilada.",
                "Ponga paños húmedos y fríos en cuello, axilas e ingles.",
                "Si está despierto, que beba agua a sorbos pequeños.",
                "Si está confundido o deja de sudar, llame al médico de vuelo.",
            ],
            avisar=a.temp > 38.8,
            estado=lambda: f"Temperatura {a.temp:.1f} °C (meta: menos de 37.8)")

    if a.temp < 35.5:
        return Guia(
            "hipotermia", "ABRIGUE AL PACIENTE", ALERTA,
            "Su cuerpo está demasiado frío.",
            [
                "Llévelo a la zona más cálida y quítele la ropa húmeda.",
                "Envuélvalo con la manta térmica, también la cabeza.",
                "Si está despierto, dele una bebida tibia.",
                "No lo frote ni lo mueva con brusquedad.",
                "Si está muy dormido o confundido, llame al médico de vuelo.",
            ],
            estado=lambda: f"Temperatura {a.temp:.1f} °C (meta: más de 36)")

    # latidos irregulares
    if a.extrasistoles_recientes >= 3:
        return Guia(
            "arritmia", "LATIDOS IRREGULARES", ALERTA,
            "El corazón está dando latidos fuera de ritmo.",
            [
                "Deténgase, sujétese y respire despacio.",
                "No tome café ni bebidas con cafeína.",
                "Avise si siente palpitaciones, mareo o dolor en el pecho.",
                "Tenga el desfibrilador a la mano.",
                "Informe al médico de vuelo en el siguiente contacto.",
            ],
            estado=lambda: f"Latidos fuera de ritmo en 20 segundos: {a.extrasistoles_recientes}")

    # entorno
    if entorno.co2 > 5.3:
        return Guia(
            "co2", "AIRE VICIADO", CRITICO if entorno.co2 > 8.0 else ALERTA,
            "Hay demasiado dióxido de carbono en el aire.",
            [
                "Revise que el purificador de aire esté encendido.",
                "Muévanse a un módulo con mejor ventilación.",
                "Si hay dolor de cabeza, sueño o falta de aire: use la mascarilla de oxígeno.",
                "Avise a control de misión.",
            ],
            acciones=(("Oxígeno colocado", "oxigeno"),),
            estado=lambda: f"CO2 {entorno.co2:.1f} mmHg (meta: menos de 5)")

    # estrés alto
    if a.evento == "estres" or a.crisis_estres:
        return Guia(
            "estres", "BAJE SU ESTRÉS", ALERTA,
            "Su cuerpo muestra señales de estrés alto. Respirar lento lo baja en poco tiempo.",
            [
                "Deje lo que está haciendo si es seguro. Sujétese y afloje hombros y mandíbula.",
                "Siga el contador: tome aire por la nariz mientras el círculo crece.",
                "Suelte el aire despacio por la boca mientras el círculo se achica.",
                "Mientras respira, nombre en silencio 3 cosas que ve y 2 que escucha.",
                "Siga hasta que el número de estrés baje de 50. Si no baja, hable con un compañero.",
            ],
            modo="respiracion", respiracion=(4.0, 6.0),
            estado=lambda: f"Estrés {a.estres:.0f} de 100 (meta: menos de 50)   ·   "
                           f"Variabilidad cardiaca {a.rmssd:.0f} ms")

    return None
