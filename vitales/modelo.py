"""Modelo simulado de la tripulación y de la nave.

Nada viene de sensores reales: cada valor se mueve hacia un objetivo con
algo de inercia y ruido para que se vea natural.
"""

import math
import random
from collections import deque

from . import estres as modelo_estres
from .huesos import calcular_perdidas
from .radiacion import ACELERACION_EXPOSICION, UMBRAL_EVENTO
from .riesgos import INDICADORES, calcular_riesgos

DOS_PI = 2.0 * math.pi

# catálogos: fases de misión, eventos médicos y eventos del entorno

# cada fase le mueve los valores normales al tripulante
# g      -> aceleración percibida (en g)
# ruido  -> artefacto por movimiento en el electrocardiograma (0 a 1)
FASES = {
    "reposo": dict(nombre="Reposo en cabina", fc=0, fr=0, pas=0, pad=0, temp=0.0,
                   spo2=0, g=0.0, ruido=0.0, perf=1.0),
    "sueno": dict(nombre="Sueño", fc=-12, fr=-3, pas=-10, pad=-6, temp=-0.3,
                  spo2=-1, g=0.0, ruido=0.0, perf=1.1),
    "ejercicio": dict(nombre="Ejercicio", fc=62, fr=13, pas=34, pad=5, temp=0.7,
                      spo2=-1, g=0.0, ruido=0.5, perf=1.3),
    "lanzamiento": dict(nombre="Lanzamiento", fc=48, fr=10, pas=26, pad=12, temp=0.2,
                        spo2=-1, g=3.2, ruido=0.8, perf=0.7),
    "eva": dict(nombre="Actividad extravehicular", fc=30, fr=6, pas=12, pad=4, temp=0.4,
                spo2=1, g=0.0, ruido=0.25, perf=0.9),
    "reentrada": dict(nombre="Reentrada", fc=44, fr=9, pas=22, pad=10, temp=0.3,
                      spo2=-1, g=4.1, ruido=0.9, perf=0.7),
}

# eventos médicos: se aplican solo al tripulante seleccionado
EVENTOS_MEDICOS = {
    "ninguno": dict(nombre="Sin evento", fc=0, fr=0, pas=0, pad=0, temp=0.0, spo2=0, perf=1.0),
    "hipoxia": dict(nombre="Hipoxia", fc=28, fr=9, pas=8, pad=4, temp=0.0, spo2=-13, perf=0.45),
    "arritmia": dict(nombre="Arritmia", fc=8, fr=1, pas=-6, pad=-2, temp=0.0, spo2=-1, perf=0.8),
    "hipertermia": dict(nombre="Hipertermia", fc=26, fr=6, pas=-4, pad=-4, temp=2.3, spo2=0, perf=1.2),
    "estres": dict(nombre="Estrés agudo", fc=58, fr=12, pas=36, pad=16, temp=0.2, spo2=0, perf=0.7),
    # la descompensación va poco a poco, depende de la gravedad (ver Astronauta)
    "descompensacion": dict(nombre="Descompensación", fc=0, fr=0, pas=0, pad=0, temp=0.0, spo2=0, perf=1.0),
    "taquicardia": dict(nombre="Taquicardia", fc=112, fr=4, pas=-10, pad=-4, temp=0.0, spo2=0, perf=0.7),
    "bradicardia": dict(nombre="Bradicardia", fc=-30, fr=0, pas=-14, pad=-8, temp=0.0, spo2=0, perf=0.8),
    "taquipnea": dict(nombre="Taquipnea", fc=18, fr=20, pas=6, pad=2, temp=0.0, spo2=1, perf=0.9),
    "bradipnea": dict(nombre="Respiración lenta", fc=-4, fr=-8, pas=-4, pad=-2, temp=0.0, spo2=-8, perf=0.9),
    "hipotermia": dict(nombre="Hipotermia", fc=-14, fr=-3, pas=-8, pad=-4, temp=-2.4, spo2=0, perf=0.6),
    # lesiones cardiovasculares y cerebrales
    "infarto": dict(nombre="Infarto", fc=24, fr=5, pas=-12, pad=-4, temp=0.0, spo2=-2, perf=0.75, st=0.24),
    "ictus": dict(nombre="Evento cerebrovascular", fc=-6, fr=2, pas=66, pad=30, temp=0.1, spo2=-1, perf=0.9),
    # paro cardiaco: el ritmo define si la descarga del desfibrilador sirve o no
    "fv": dict(nombre="Fibrilación ventricular", fc=0, fr=0, pas=0, pad=0, temp=0.0, spo2=0, perf=1.0),
    "tvsp": dict(nombre="Taquicardia ventricular", fc=0, fr=0, pas=0, pad=0, temp=0.0, spo2=0, perf=1.0),
    "asistolia": dict(nombre="Asistolia", fc=0, fr=0, pas=0, pad=0, temp=0.0, spo2=0, perf=1.0),
    "aesp": dict(nombre="Actividad sin pulso", fc=0, fr=0, pas=0, pad=0, temp=0.0, spo2=0, perf=1.0),
}

# ritmos de paro: nombre completo y si son desfibrilables
PARO = {
    "fv": ("Fibrilación ventricular", True),
    "tvsp": ("Taquicardia ventricular sin pulso", True),
    "asistolia": ("Asistolia", False),
    "aesp": ("Actividad eléctrica sin pulso", False),
}

# agrupación de los eventos para los botones de la interfaz
GRUPOS_EVENTOS = (
    ("Signos", ("ninguno", "hipoxia", "taquicardia", "bradicardia", "taquipnea", "bradipnea",
                "hipertermia", "hipotermia", "estres")),
    ("Urgencias", ("arritmia", "descompensacion", "infarto", "ictus")),
    ("Paro cardiaco", ("fv", "tvsp", "asistolia", "aesp")),
)

SEGUNDOS_RCP_PARA_PULSO = 40.0    # compresiones necesarias para recuperar un ritmo no desfibrilable

SEGUNDOS_DESCOMPENSACION = 90.0   # tiempo en llegar al estado más grave
SEGUNDOS_RECUPERACION = 25.0      # tiempo en volver a la normalidad al retirar el evento

# eventos del entorno: afectan a toda la tripulación
EVENTOS_ENTORNO = {
    "nominal": "Entorno nominal",
    "fuga": "Fuga de presión",
    "co2": "CO2 elevado",
    "tormenta": "Tormenta solar",
}

# déficit de saturación según la presión parcial de oxígeno respirada (kPa)
_TABLA_HIPOXIA = [(19.0, 0.0), (17.0, 2.0), (14.5, 7.0), (12.5, 13.0), (11.0, 18.0), (8.0, 28.0)]


def _interpolar(tabla, x):
    """Interpolación lineal sobre una tabla ordenada de mayor a menor x."""
    if x >= tabla[0][0]:
        return tabla[0][1]
    for (x0, y0), (x1, y1) in zip(tabla, tabla[1:]):
        if x >= x1:
            return y0 + (y1 - y0) * (x0 - x) / (x0 - x1)
    return tabla[-1][1]


def _acercar(valor, objetivo, dt, tau):
    """Acerca un valor a su objetivo con una constante de tiempo tau (s)."""
    return valor + (objetivo - valor) * (1.0 - math.exp(-dt / tau))


def _campana(t, centro, ancho, amplitud):
    """Onda gaussiana usada para formar cada componente del latido."""
    z = (t - centro) / ancho
    if z > 5.0 or z < -5.0:
        return 0.0
    return amplitud * math.exp(-0.5 * z * z)


# entorno de la nave o del traje

class Entorno:
    """Condiciones ambientales que comparte toda la tripulación."""

    def __init__(self):
        self.evento = "nominal"
        self.presion = 101.3      # kPa (cabina o traje)
        self.fraccion_o2 = 0.21   # fracción de oxígeno en el gas respirado
        self.co2 = 2.6            # mmHg de presión parcial
        self.temperatura = 22.4   # grados C en cabina
        self.tasa_radiacion = 0.02  # mSv por hora
        self.aceleracion = 0.0    # g

    @property
    def pp_o2(self):
        """Presión parcial de oxígeno respirada, en kPa."""
        return self.presion * self.fraccion_o2

    def avanzar(self, dt, fase):
        en_eva = fase == "eva"
        presion_obj = 29.6 if en_eva else 101.3
        tau_presion = 8.0
        if self.evento == "fuga":
            presion_obj = 13.0 if en_eva else 56.0
            tau_presion = 45.0
        self.presion = _acercar(self.presion, presion_obj, dt, tau_presion)
        self.fraccion_o2 = _acercar(self.fraccion_o2, 1.0 if en_eva else 0.21, dt, 8.0)

        co2_obj = 9.5 if self.evento == "co2" else 2.6
        self.co2 = _acercar(self.co2, co2_obj, dt, 40.0) + random.gauss(0, 0.01) * math.sqrt(dt)

        tasa_obj = 0.06 if en_eva else 0.02
        tau_radiacion = 10.0
        if self.evento == "tormenta":
            # tormenta solar intensa: mucho peor fuera de la nave que dentro
            tasa_obj = 240.0 if en_eva else 60.0
            tau_radiacion = 25.0
        self.tasa_radiacion = _acercar(self.tasa_radiacion, tasa_obj, dt, tau_radiacion)

        self.aceleracion = _acercar(self.aceleracion, FASES[fase]["g"], dt, 3.0)
        self.temperatura = _acercar(self.temperatura, 22.4, dt, 30.0) + random.gauss(0, 0.01) * math.sqrt(dt)


# tripulante

class Astronauta:
    """Estado fisiológico simulado de un miembro de la tripulación."""

    # amplitudes de las ondas P, Q, R, S y T en las derivaciones I y III
    # la II sale de sumar las dos (ley de Einthoven)
    _AMP_I = (0.09, -0.04, 0.55, -0.08, 0.17)
    _AMP_III = (0.05, -0.05, 0.50, -0.14, 0.11)

    def __init__(self, nombre, rol, fc, fr, pas, pad, temp, spo2=98.0, dosis=38.0, oseo=0.7):
        self.nombre = nombre
        self.rol = rol
        self.factor_oseo = oseo   # respuesta individual a la pérdida ósea (menor = pierde menos)
        self.perdida_osea = calcular_perdidas(0, oseo)
        # respuesta individual a cada riesgo (fija para cada tripulante)
        self.factores = {clave: random.Random(nombre + clave).uniform(0.8, 1.2)
                         for clave, _ in INDICADORES}
        self.riesgos = []
        self.dosis_evento = 0.0    # mSv recibidos en el último evento de radiación
        self.dosis_alta = 0.0      # mSv recibidos en todos los eventos de radiación (daña el hueso)
        self._en_evento = False
        # atención que recibe el tripulante
        self.oxigeno = False              # oxígeno suplementario colocado
        self.rcp = False                  # compresiones torácicas en curso
        self.respiracion_guiada = False   # sigue el contador de respiración
        self.calma = 0.0                  # efecto acumulado de la respiración guiada (0 a 1)
        self.t_rcp = 0.0                  # segundos de compresiones en el paro actual
        self.t_paro = 0.0                 # segundos en paro
        self.avisos = []                  # mensajes para la bitácora (los consume la interfaz)
        self._fase_fv = [random.random() * DOS_PI for _ in range(3)]
        self._frec_fv = 5.0
        # nivel de estrés (0 a 100) y marcadores con los que se mide
        azar = random.Random(nombre + "estres")
        self.sensibilidad = azar.uniform(0.88, 1.12)   # respuesta individual al estrés
        self.rmssd_basal = azar.uniform(40.0, 54.0)    # variabilidad cardiaca en calma (ms)
        self.estres = modelo_estres.BASAL + 5.0
        self.rmssd = self.rmssd_basal
        self.cortisol = modelo_estres.cortisol(self.estres)
        self.alivio = 0.0                 # puntos que restan las actividades de bienestar
        self.carga_equipo = 0.0           # carga por la emergencia de un compañero
        self.factores_estres = []         # (causa, puntos) vigentes
        self.crisis_estres = False        # estrés alto: se guía la respiración hasta calmarlo
        self.historial_estres = deque(maxlen=360)   # una muestra cada 0.5 s: 3 minutos
        self._reloj_estres = 0.0
        self.base = dict(fc=fc, fr=fr, pas=pas, pad=pad, temp=temp, spo2=spo2)
        self.evento = "ninguno"

        # signos vitales actuales
        self.fc = float(fc)
        self.fr = float(fr)
        self.pas = float(pas)
        self.pad = float(pad)
        self.temp = float(temp)
        self.temp_piel = temp - 0.9
        self.spo2 = float(spo2)
        self.perfusion = 4.5
        self.dosis = dosis  # mSv acumulados en la misión

        # la presión se mide cada cierto tiempo, como en un monitor de verdad
        self.pni_sis = round(pas)
        self.pni_dia = round(pad)
        self.pni_instante = None
        self._reloj_pni = 0.0
        self.intervalo_pni = 30.0
        self.tendencia_pam = 0   # cambio de la PAM respecto a la medición anterior
        self.gravedad = 0.0      # avance de la descompensación, de 0 a 1

        # estado del ritmo cardiaco y respiratorio
        self._t_latido = random.random() * 0.5
        self._rr = 60.0 / fc
        self._tipo = "normal"
        self._sig_tipo = "normal"
        self._fase_pulso = 0.7
        self._fase_resp = random.random()
        self._amp_pulso = 1.0
        self._ruido_ecg = 0.0
        self._reloj = 0.0
        self._extrasistoles = []
        self.latido = False  # se activa en cada latido; la interfaz lo consume

    # --- dinámica lenta ---

    def actualizar_cronicos(self, t_mision, entorno):
        """Recalcula la pérdida ósea y los indicadores de riesgo de la misión."""
        dias = t_mision / 86400.0
        self.perdida_osea = calcular_perdidas(dias, self.factor_oseo, self.dosis_alta)
        self.riesgos = calcular_riesgos(self, dias, entorno)

    @property
    def sin_pulso(self):
        """True si el tripulante está en paro cardiaco."""
        return self.evento in PARO

    @property
    def ritmo(self):
        """Nombre del ritmo cardiaco y si es desfibrilable (None si no aplica)."""
        if self.evento in PARO:
            return PARO[self.evento]
        if self.evento == "taquicardia":
            return "Taquicardia supraventricular", None
        if self.extrasistoles_recientes >= 2:
            return "Ritmo irregular", None
        if self.fc > 100:
            return "Taquicardia sinusal", None
        if self.fc < 50:
            return "Bradicardia sinusal", None
        return "Ritmo sinusal", None

    def dar_descarga(self):
        """Descarga del desfibrilador. Regresa True si recupera el pulso."""
        if self.evento not in PARO:
            return False
        if not PARO[self.evento][1]:
            self.avisos.append("descarga sin efecto: este ritmo no es desfibrilable")
            return False
        # la descarga funciona mejor si antes hubo compresiones
        if random.random() < (0.9 if self.t_rcp >= 8.0 else 0.5):
            self._recuperar_pulso("recuperó el pulso tras la descarga")
            return True
        self.avisos.append("descarga sin éxito: continuar compresiones")
        return False

    def _recuperar_pulso(self, mensaje):
        self.evento = "ninguno"
        self.rcp = False
        self.t_rcp = 0.0
        self.t_paro = 0.0
        self._t_latido = 0.0
        self._tipo = self._sig_tipo = "normal"
        self.avisos.append(mensaje)

    def avanzar(self, dt, fase, entorno, t_mision):
        """Actualiza los signos vitales hacia el objetivo de la situación actual."""
        self.actualizar_cronicos(t_mision, entorno)
        f = FASES[fase]
        e = EVENTOS_MEDICOS[self.evento]
        b = self.base

        deficit_o2 = _interpolar(_TABLA_HIPOXIA, entorno.pp_o2)
        exceso_co2 = max(0.0, entorno.co2 - 3.5)

        fc_obj = b["fc"] + f["fc"] + e["fc"] + 1.6 * deficit_o2 + 1.2 * exceso_co2
        fr_obj = b["fr"] + f["fr"] + e["fr"] + 0.5 * deficit_o2 + 0.9 * exceso_co2
        pas_obj = b["pas"] + f["pas"] + e["pas"]
        pad_obj = b["pad"] + f["pad"] + e["pad"]
        temp_obj = b["temp"] + f["temp"] + e["temp"]
        spo2_obj = min(100.0, b["spo2"] + f["spo2"] + e["spo2"] - deficit_o2)
        perf_obj = 4.5 * f["perf"] * e["perf"] * (1.0 - min(0.6, deficit_o2 / 30.0))

        # descompensación: primero el corazón se acelera para compensar,
        # luego caen la presión y la perfusión, y al final se pone lento
        if self.evento == "descompensacion":
            self.gravedad = min(1.0, self.gravedad + dt / SEGUNDOS_DESCOMPENSACION)
        else:
            self.gravedad = max(0.0, self.gravedad - dt / SEGUNDOS_RECUPERACION)
        g = self.gravedad
        if g > 0.0:
            fc_obj += 75.0 * min(1.0, g / 0.7)
            if g > 0.88:
                fc_obj -= 98.0 * (g - 0.88) / 0.12
            fr_obj += 16.0 * g
            pas_obj -= 70.0 * g
            pad_obj -= 38.0 * g
            spo2_obj -= 14.0 * max(0.0, g - 0.3) / 0.7
            perf_obj *= 1.0 - 0.92 * g

        # oxígeno suplementario: sube la saturación y alivia el esfuerzo del corazón
        if self.oxigeno:
            fc_obj -= min(10.0, max(0.0, 96.0 - spo2_obj))
            spo2_obj = min(100.0, spo2_obj + 9.0)

        # respiración guiada: seguir el contador lleva la respiración hacia lo normal
        if self.respiracion_guiada:
            self.calma = min(1.0, self.calma + dt / 40.0)
        else:
            self.calma = max(0.0, self.calma - dt / 20.0)
        if self.calma > 0.0:
            fr_obj += (14.0 - fr_obj) * 0.92 * self.calma
            fc_obj -= 10.0 * self.calma * (1.0 if fc_obj > 90.0 else 0.0)
            if self.evento == "bradipnea":
                spo2_obj += 7.0 * self.calma
            if self.calma >= 0.95 and self.evento in ("taquipnea", "bradipnea"):
                self.evento = "ninguno"
                self.respiracion_guiada = False
                self.avisos.append("respiración normalizada con el contador")

        # paro cardiaco: sin pulso ni respiración; las compresiones mantienen algo de circulación
        en_paro = self.evento in PARO
        if en_paro:
            self.t_paro += dt
            pas_obj, pad_obj = (58.0, 22.0) if self.rcp else (6.0, 4.0)
            spo2_obj = 82.0 if self.rcp else 55.0
            perf_obj = 0.8 if self.rcp else 0.05
            fr_obj = 4.0
            self.pas = _acercar(self.pas, pas_obj, dt, 2.5)
            self.pad = _acercar(self.pad, pad_obj, dt, 2.5)
            if self.rcp:
                self.t_rcp += dt
                # un ritmo no desfibrilable solo se recupera con compresiones sostenidas
                if not PARO[self.evento][1] and self.t_rcp >= SEGUNDOS_RCP_PARA_PULSO:
                    self._recuperar_pulso("recuperó el pulso con las compresiones")
        else:
            self.rcp = False
            self.t_rcp = 0.0
            self.t_paro = 0.0

        raiz = math.sqrt(dt)
        self.fc = _acercar(self.fc, fc_obj, dt, 6.0) + random.gauss(0, 0.8) * raiz
        self.fr = _acercar(self.fr, fr_obj, dt, 8.0) + random.gauss(0, 0.3) * raiz
        self.pas = _acercar(self.pas, pas_obj, dt, 10.0) + random.gauss(0, 0.6) * raiz
        self.pad = _acercar(self.pad, pad_obj, dt, 10.0) + random.gauss(0, 0.4) * raiz
        self.temp = _acercar(self.temp, temp_obj, dt, 30.0) + random.gauss(0, 0.01) * raiz
        self.temp_piel = _acercar(self.temp_piel, self.temp - 0.9 + 0.3 * f["temp"], dt, 20.0)
        self.spo2 = min(100.0, _acercar(self.spo2, spo2_obj, dt, 14.0) + random.gauss(0, 0.15) * raiz)
        self.perfusion = max(0.3, _acercar(self.perfusion, perf_obj, dt, 8.0) + random.gauss(0, 0.05) * raiz)

        self.fc = min(220.0, max(25.0, self.fc))
        self.fr = min(60.0, max(4.0, self.fr))
        self._ruido_ecg = _acercar(self._ruido_ecg, f["ruido"], dt, 2.0)

        self._avanzar_estres(dt, fase, entorno, t_mision)

        # dosis de radiación; durante un evento se contabiliza aparte y acelerada
        incremento = entorno.tasa_radiacion * dt / 3600.0
        if entorno.tasa_radiacion > UMBRAL_EVENTO:
            if not self._en_evento:
                self._en_evento = True
                self.dosis_evento = 0.0
            incremento *= ACELERACION_EXPOSICION
            self.dosis_evento += incremento
            self.dosis_alta += incremento
        else:
            self._en_evento = False
        self.dosis += incremento

        # medición periódica de la presión arterial; durante una descompensación
        # el monitor mide de forma casi continua
        intervalo = 4.0 if g > 0.0 else self.intervalo_pni
        self._reloj_pni = min(self._reloj_pni, intervalo) - dt
        if self._reloj_pni <= 0.0:
            pam_anterior = self.pam
            self.pni_sis = round(self.pas)
            self.pni_dia = round(self.pad)
            if self.pni_instante is not None:
                self.tendencia_pam = self.pam - pam_anterior
            self.pni_instante = t_mision
            self._reloj_pni = intervalo

    def _avanzar_estres(self, dt, fase, entorno, t_mision):
        """Nivel de estrés: sube con cada circunstancia y baja con las actividades de bienestar."""
        # la respiración guiada resta estrés mientras se sigue el contador
        if self.respiracion_guiada:
            self.alivio = min(modelo_estres.ALIVIO_MAXIMO, self.alivio + 0.8 * dt)
        else:
            self.alivio = _acercar(self.alivio, 0.0, dt, 300.0)

        if not self.sin_pulso:
            self.factores_estres = modelo_estres.calcular_factores(
                self, fase, entorno, t_mision / 86400.0, FASES, EVENTOS_MEDICOS)
            meta = modelo_estres.objetivo(self.factores_estres, self.alivio)
            # sube rápido y baja más lento, como pasa en la vida real
            tau = 7.0 if meta > self.estres else 14.0
            self.estres = _acercar(self.estres, meta, dt, tau) + random.gauss(0, 0.5) * math.sqrt(dt)
            self.estres = min(100.0, max(0.0, self.estres))
            self.rmssd = max(4.0, _acercar(self.rmssd, modelo_estres.rmssd(self.estres, self.rmssd_basal),
                                           dt, 4.0) + random.gauss(0, 0.6) * math.sqrt(dt))
            self.cortisol = _acercar(self.cortisol, modelo_estres.cortisol(self.estres), dt, 40.0)

        # crisis de estrés: empieza al pasar el límite alto y termina al calmarse
        if self.estres >= modelo_estres.LIMITE_ALTO:
            self.crisis_estres = True
        elif self.estres < 50.0 or self.calma >= 0.95:
            self.crisis_estres = False
        if self.evento == "estres" and self.respiracion_guiada and self.calma >= 0.95:
            self.evento = "ninguno"
            self.avisos.append("estrés controlado con la respiración guiada")

        self._reloj_estres -= dt
        if self._reloj_estres <= 0.0:
            self._reloj_estres = 0.5
            self.historial_estres.append(self.estres)

    def aliviar(self, puntos):
        """Una actividad de bienestar completada resta puntos de estrés durante un tiempo."""
        self.alivio = min(modelo_estres.ALIVIO_MAXIMO, self.alivio + puntos)

    @property
    def pam(self):
        """Presión arterial media: PAM = (PS + PD x 2) / 3."""
        return round((self.pni_sis + self.pni_dia * 2) / 3.0)

    @property
    def etapa(self):
        """Etapa de la descompensación según su gravedad."""
        g = self.gravedad
        if g <= 0.0:
            return ""
        if g < 0.35:
            return "Compensando"
        if g < 0.75:
            return "Descompensado"
        return "Estado crítico"

    @property
    def extrasistoles_recientes(self):
        """Latidos ectópicos detectados en los últimos 20 segundos."""
        limite = self._reloj - 20.0
        self._extrasistoles = [t for t in self._extrasistoles if t >= limite]
        return len(self._extrasistoles)

    # --- ritmo y formas de onda ---

    def _nuevo_latido(self):
        self._tipo = self._sig_tipo
        self._sig_tipo = "normal"
        # probabilidad de latido ectópico: arritmia o descompensación avanzada
        prob = 0.22 if self.evento == "arritmia" else 0.0
        prob = max(prob, 0.30 * (self.gravedad - 0.6) / 0.4)
        if self._tipo == "normal" and random.random() < prob:
            self._sig_tipo = "ectopico"

        rr = 60.0 / self.fc
        if self.evento == "aesp":
            rr = 60.0 / 42.0   # actividad eléctrica lenta que no produce pulso
        elif self.evento != "taquicardia":
            rr *= 1.0 + 0.04 * math.sin(DOS_PI * self._fase_resp)  # arritmia sinusal respiratoria
            rr *= 1.0 + random.gauss(0, 0.015)
        if self._sig_tipo == "ectopico":
            rr *= 0.70   # el latido ectópico llega adelantado
        if self._tipo == "ectopico":
            rr *= 1.30   # pausa compensadora
            self._extrasistoles.append(self._reloj)
        self._rr = max(0.25, rr)
        self.latido = self.evento not in PARO   # en paro no hay latido efectivo

    def avanzar_ritmo(self, dt):
        """Avanza los relojes cardiaco y respiratorio sin generar formas de onda."""
        self._reloj += dt
        self._t_latido += dt
        if self._t_latido >= self._rr:
            self._t_latido -= self._rr
            self._nuevo_latido()
        self._fase_pulso = (self._fase_pulso + dt / self._rr) % 1.0
        self._fase_resp = (self._fase_resp + dt * self.fr / 60.0) % 1.0

    def _onda_paro(self, evento, dt):
        """Electrocardiograma de los ritmos de paro (derivaciones I y III)."""
        if evento == "asistolia":
            # línea casi plana
            base = 0.012 * math.sin(DOS_PI * 0.3 * self._reloj)
            return base, base
        if evento == "tvsp":
            # complejos anchos, regulares y muy rápidos (unos 190 por minuto)
            fase = DOS_PI * 3.15 * self._reloj
            forma = math.sin(fase) + 0.35 * math.sin(2.0 * fase + 0.6)
            return 0.42 * forma, 0.36 * forma
        # fibrilación ventricular: oscilación caótica que pierde amplitud con el tiempo
        self._frec_fv = min(7.5, max(3.5, self._frec_fv + random.gauss(0, 6.0) * dt))
        f = self._frec_fv
        fases = self._fase_fv
        fases[0] += DOS_PI * f * dt
        fases[1] += DOS_PI * f * 1.37 * dt
        fases[2] += DOS_PI * f * 0.21 * dt
        amplitud = 0.18 + 0.30 * math.exp(-self.t_paro / 150.0)
        envolvente = 0.65 + 0.35 * math.sin(fases[2])
        forma = amplitud * envolvente * (math.sin(fases[0]) + 0.5 * math.sin(fases[1]))
        return forma, 0.8 * amplitud * envolvente * (math.sin(fases[0] + 0.7) + 0.5 * math.sin(fases[1] + 0.3))

    def muestrear(self, dt):
        """Avanza dt segundos y regresa una muestra de cada trazo:
        (ECG I, ECG II, ECG III, pletismografía, respiración).
        """
        self.avanzar_ritmo(dt)
        t = self._t_latido
        rr = self._rr

        evento = self.evento
        if evento in ("fv", "tvsp", "asistolia"):
            i, iii = self._onda_paro(evento, dt)
        elif self._tipo == "normal":
            k = min(1.0, rr / 0.75)          # comprime el complejo a frecuencias altas
            raiz = math.sqrt(rr)
            t_r = 0.20 * k
            g = self.gravedad
            # en estado crítico el complejo QRS se ensancha
            ancho = 1.0 + 2.2 * max(0.0, g - 0.8) / 0.2
            if evento == "aesp":
                ancho = 2.0
            formas = (
                (0.08 * k, 0.022 * math.sqrt(k)),       # P
                (t_r - 0.022 * ancho, 0.008 * ancho),   # Q
                (t_r, 0.010 * ancho),                   # R
                (t_r + 0.022 * ancho, 0.009 * ancho),   # S
                (t_r + 0.27 * raiz, 0.050 * raiz),      # T
            )
            # isquemia: la onda T se aplana y se invierte, y el segmento ST desciende
            factores = (1.0 - 0.6 * g, 1.0, 1.0 - 0.25 * g, 1.0, 1.0 - 2.0 * g)
            if evento == "taquicardia":
                factores = (0.0, 1.0, 1.0, 1.0, 0.8)      # sin onda P visible
            elif evento == "aesp":
                factores = (0.0, 0.6, 0.55, 0.6, 0.5)     # complejos anchos y de bajo voltaje
            # infarto: el segmento ST se eleva
            elevacion = EVENTOS_MEDICOS[evento].get("st", 0.0)
            st = _campana(t, t_r + 0.12 * raiz, 0.045 * raiz, elevacion - 0.16 * g)
            i = st + sum(_campana(t, c, a, amp * f)
                         for (c, a), amp, f in zip(formas, self._AMP_I, factores))
            iii = st + sum(_campana(t, c, a, amp * f)
                           for (c, a), amp, f in zip(formas, self._AMP_III, factores))
        else:
            # extrasístole ventricular: sin onda P, complejo ancho y T invertida
            forma = (_campana(t, 0.12, 0.030, 1.0) + _campana(t, 0.19, 0.032, -0.55)
                     + _campana(t, 0.42, 0.070, -0.32))
            i = 0.70 * forma
            iii = 0.60 * forma

        en_paro = evento in PARO
        deriva = 0.0 if en_paro else 0.025 * math.sin(DOS_PI * self._fase_resp)
        if self.rcp:
            # artefacto de las compresiones (110 por minuto)
            deriva += 0.16 * math.sin(DOS_PI * 110.0 / 60.0 * self._reloj)
        sigma = 0.006 + 0.035 * self._ruido_ecg
        i += deriva + random.gauss(0, sigma)
        iii += deriva + random.gauss(0, sigma)
        ii = i + iii

        if en_paro:
            # sin pulso: la onda de pulso es plana salvo por las compresiones; no hay respiración
            self._amp_pulso = _acercar(self._amp_pulso, 0.0, dt, 0.6)
            pulso = 0.0
            if self.rcp:
                pulso = 0.32 * math.sin(math.pi * 110.0 / 60.0 * self._reloj) ** 2
            return i, ii, iii, pulso, random.gauss(0, 0.004)

        # onda de pulso (pletismografía) con muesca dícrota
        # al caer la perfusión la onda pierde amplitud, se estrecha y se borra la muesca
        amp_obj = (0.55 if self._tipo == "ectopico" else 1.0) * min(1.0, 0.10 + self.perfusion / 4.6)
        self._amp_pulso = _acercar(self._amp_pulso, amp_obj, dt, 0.4)
        p = self._fase_pulso
        gr = self.gravedad
        ancho_pulso = 0.075 * (1.0 - 0.3 * gr)
        muesca = 0.38 * (1.0 - gr)
        pulso = 0.0
        for d in (-1.0, 0.0, 1.0):
            pulso += _campana(p + d, 0.16, ancho_pulso, 1.0) + _campana(p + d, 0.42, 0.11, muesca)
        pulso *= self._amp_pulso * (1.0 + 0.08 * math.sin(DOS_PI * self._fase_resp))

        # respiración: inspiración más breve que la espiración
        r = self._fase_resp
        if r < 0.4:
            resp = -math.cos(math.pi * r / 0.4)
        else:
            resp = math.cos(math.pi * (r - 0.4) / 0.6)
        resp *= min(1.0, 0.55 + self.fr / 60.0)

        return i, ii, iii, pulso, resp


# misión

def formato_mision(segundos, con_dias=True):
    """Convierte segundos de misión a texto: 047d 03:12:08."""
    s = int(segundos)
    dias, resto = divmod(s, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, seg = divmod(resto, 60)
    if con_dias:
        return f"{dias:03d}d {horas:02d}:{minutos:02d}:{seg:02d}"
    return f"{horas:02d}:{minutos:02d}:{seg:02d}"


class Mision:
    """Agrupa a la tripulación, el entorno y el reloj de misión."""

    def __init__(self):
        self.fase = "reposo"
        self.entorno = Entorno()
        # tiempo de misión con el que arranca la simulación (inventado)
        self.t_mision = 47 * 86400 + 3 * 3600 + 12 * 60 + 8
        # tripulación inventada para la simulación
        self.tripulacion = [
            Astronauta("Elena Vargas", "Comandante", 60, 13, 116, 74, 36.7, dosis=38.4, oseo=0.62),
            Astronauta("Rodrigo Salgado", "Ingeniero de vuelo", 66, 14, 122, 78, 36.9, dosis=39.1, oseo=0.80),
            Astronauta("Mariana Okafor", "Oficial médico", 58, 12, 110, 70, 36.6, dosis=37.8, oseo=0.55),
            Astronauta("Kenji Duarte", "Especialista de misión", 70, 15, 124, 80, 37.0, dosis=40.2, oseo=0.95),
        ]
        for a in self.tripulacion:
            a.actualizar_cronicos(self.t_mision, self.entorno)

    def avanzar(self, dt):
        self.t_mision += dt
        self.entorno.avanzar(dt, self.fase)
        # la emergencia de un compañero también eleva el estrés de los demás
        graves = ("descompensacion", "infarto", "ictus")
        for a in self.tripulacion:
            a.carga_equipo = max((26.0 if o.sin_pulso else 14.0 if o.evento in graves else 0.0)
                                 for o in self.tripulacion if o is not a)
        for a in self.tripulacion:
            a.avanzar(dt, self.fase, self.entorno, self.t_mision)
