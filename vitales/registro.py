"""Grabación de los signos vitales en un archivo CSV."""

import csv
import os
from datetime import datetime

from .alarmas import nivel_maximo
from .modelo import EVENTOS_ENTORNO, EVENTOS_MEDICOS, FASES, formato_mision

_ESTADOS = {0: "Normal", 1: "Alerta", 2: "Crítico"}


class Registro:
    """Escribe una fila por tripulante cada vez que se llama a escribir()."""

    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.ruta = None
        self._archivo = None
        self._escritor = None

    @property
    def activo(self):
        return self._archivo is not None

    def iniciar(self):
        os.makedirs(self.carpeta, exist_ok=True)
        nombre = datetime.now().strftime("registro_%Y%m%d_%H%M%S.csv")
        self.ruta = os.path.join(self.carpeta, nombre)
        # utf-8-sig para que las hojas de cálculo muestren bien los acentos
        self._archivo = open(self.ruta, "w", newline="", encoding="utf-8-sig")
        self._escritor = csv.writer(self._archivo)
        self._escritor.writerow([
            "hora", "tiempo_mision", "tripulante", "fase", "evento_medico", "entorno",
            "fc_lpm", "spo2_pct", "fr_rpm", "pas_mmHg", "pad_mmHg", "pam_mmHg", "temp_C",
            "presion_kPa", "co2_mmHg", "radiacion_mSv_h", "dosis_mSv", "perdida_osea_cadera_pct",
            "estres_0_100", "vfc_rmssd_ms", "cortisol_nmol_L", "estado",
        ])

    def escribir(self, mision, alarmas_por_tripulante):
        if not self.activo:
            return
        hora = datetime.now().strftime("%H:%M:%S")
        e = mision.entorno
        for a, alarmas in zip(mision.tripulacion, alarmas_por_tripulante):
            self._escritor.writerow([
                hora, formato_mision(mision.t_mision), a.nombre,
                FASES[mision.fase]["nombre"], EVENTOS_MEDICOS[a.evento]["nombre"],
                EVENTOS_ENTORNO[e.evento],
                round(a.fc), round(a.spo2), round(a.fr), a.pni_sis, a.pni_dia, a.pam,
                f"{a.temp:.1f}", f"{e.presion:.1f}", f"{e.co2:.1f}",
                f"{e.tasa_radiacion:.3f}", f"{a.dosis:.3f}",
                f"{a.perdida_osea['cadera']:.1f}",
                round(a.estres), round(a.rmssd), f"{a.cortisol:.1f}", _ESTADOS[nivel_maximo(alarmas)],
            ])
        self._archivo.flush()

    def cerrar(self):
        if self._archivo:
            self._archivo.close()
        self._archivo = None
        self._escritor = None
