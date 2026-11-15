"""Sonidos del monitor: alarmas, tonos de paro y el audio del Geiger.

Los tonos se generan al arrancar y el audio del Geiger es el archivo de la
carpeta assests. Solo suena en Windows.
"""

import glob
import math
import os
import struct
import tempfile
import wave

try:
    import ctypes
    import winsound
    _mci = ctypes.windll.winmm.mciSendStringW
except (ImportError, AttributeError, OSError):
    winsound = None
    _mci = None

_FRECUENCIA = 22050


def _tono(hz, segundos, volumen=0.5):
    """Muestras de un tono con entrada y salida suaves; hz = 0 es silencio."""
    n = int(_FRECUENCIA * segundos)
    borde = max(1, int(_FRECUENCIA * 0.008))
    muestras = []
    for i in range(n):
        if hz <= 0:
            muestras.append(0)
            continue
        suave = min(1.0, i / borde, (n - i) / borde)
        muestras.append(int(32767 * volumen * suave * math.sin(2 * math.pi * hz * i / _FRECUENCIA)))
    return muestras


# cada sonido es una secuencia de (frecuencia, duración) que se repite en bucle
_SONIDOS = {
    # ritmo desfibrilable: tono agudo, rápido y alternado (pide descarga)
    "desfibrilable": [(1400, 0.12), (1000, 0.12)] * 3 + [(0, 0.35)],
    # ritmo no desfibrilable: tono grave y continuo (línea plana)
    "no_desfibrilable": [(440, 1.3), (0, 0.25)],
    # emergencia que necesita ayuda de la tripulación
    "ayuda": [(880, 0.16), (0, 0.08), (880, 0.16), (0, 0.08), (880, 0.16), (0, 1.1)],
}


class Sonido:
    """Controla la alarma en curso y el audio del contador Geiger."""

    def __init__(self, carpeta_proyecto):
        self.disponible = winsound is not None
        self._alarma = None
        self._geiger_abierto = False
        self._geiger_sonando = False
        self._archivos = {}
        if not self.disponible:
            return
        carpeta = tempfile.mkdtemp(prefix="monitor_sonidos_")
        for nombre, secuencia in _SONIDOS.items():
            ruta = os.path.join(carpeta, nombre + ".wav")
            muestras = [m for hz, seg in secuencia for m in _tono(hz, seg)]
            with wave.open(ruta, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(_FRECUENCIA)
                w.writeframes(struct.pack(f"<{len(muestras)}h", *muestras))
            self._archivos[nombre] = ruta

        # audio del Geiger: el primer archivo de audio que haya en la carpeta
        for nombre_carpeta in ("assests", "assets"):
            encontrados = sorted(glob.glob(os.path.join(carpeta_proyecto, nombre_carpeta, "*.mp3"))
                                 + glob.glob(os.path.join(carpeta_proyecto, nombre_carpeta, "*.wav")))
            if encontrados:
                self._abrir_geiger(encontrados[0])
                break

    def _abrir_geiger(self, ruta):
        tipo = "mpegvideo" if ruta.lower().endswith(".mp3") else "waveaudio"
        error = _mci(f'open "{ruta}" type {tipo} alias geiger', None, 0, None)
        self._geiger_abierto = error == 0
        self._repetir = " repeat" if tipo == "mpegvideo" else ""

    def alarma(self, nombre):
        """Cambia la alarma en bucle; None la detiene."""
        if not self.disponible or nombre == self._alarma:
            return
        self._alarma = nombre
        if nombre is None:
            winsound.PlaySound(None, winsound.SND_PURGE)
        else:
            winsound.PlaySound(self._archivos[nombre],
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)

    def geiger(self, encendido):
        """Reproduce el audio del contador Geiger mientras la radiación esté elevada."""
        if not self._geiger_abierto or encendido == self._geiger_sonando:
            return
        self._geiger_sonando = encendido
        if encendido:
            _mci("seek geiger to start", None, 0, None)
            _mci("play geiger" + self._repetir, None, 0, None)
        else:
            _mci("stop geiger", None, 0, None)

    def cerrar(self):
        self.alarma(None)
        if self._geiger_abierto:
            _mci("close geiger", None, 0, None)
            self._geiger_abierto = False
