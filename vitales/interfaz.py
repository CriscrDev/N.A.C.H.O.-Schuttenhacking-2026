"""La ventana del monitor: trazos, paneles, botones y ventanas emergentes."""

import math
import os
import time
import tkinter as tk

from .alarmas import (ALERTA, CRITICO, evaluar_entorno, evaluar_tripulante,
                      nivel_maximo, niveles_por_parametro)
from . import estres as modelo_estres
from .guias import guia_para
from .rutina import (SEGUNDOS_ENTRE_RECOMENDACIONES, SEGUNDOS_PRIMERA,
                     Recomendador)
from .modelo import (EVENTOS_ENTORNO, EVENTOS_MEDICOS, FASES, GRUPOS_EVENTOS,
                     PARO, Mision, formato_mision)
from .huesos import NOMBRES as NOMBRES_OSEOS
from .huesos import (densidad_global, lesiones_probables, nivel_riesgo,
                     riesgo_fractura)
from .radiacion import (LIMITE_CARRERA, UMBRAL_EVENTO, cuentas_por_segundo,
                        detecciones, sintomas_probables)
from .registro import Registro
from .sonido import Sonido

# paleta de colores
FONDO = "#04070b"
PANEL = "#0a1018"
PANEL_ALTO = "#111a26"
BORDE = "#1d2a3a"
TEXTO = "#d7e0ea"
TENUE = "#6f8196"
VERDE = "#2fe26f"
CIAN = "#39c6f4"
AMARILLO = "#ece23a"
BLANCO = "#f2f5f8"
ROJO = "#ff3d3d"
ROJO_FONDO = "#a3141b"
AMBAR = "#ffb020"

SEGUNDOS_BARRIDO = 6.0   # tiempo que tarda el trazo en cruzar la pantalla
PUNTOS_POR_PIXEL = 2


def fuente(tam, negrita=False):
    """Fuente con tamaño en pixeles (negativo en Tk) para un diseño estable."""
    return ("Bahnschrift", -int(tam), "bold" if negrita else "normal")


def puntos_corazon(cx, cy, escala):
    """Contorno vectorial de un corazón centrado en (cx, cy)."""
    pts = []
    for i in range(40):
        t = 2 * math.pi * i / 40
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts += [cx + x * escala, cy - y * escala]
    return pts


# trazo de barrido

class Trazo:
    """Curva que se va pintando de izquierda a derecha como en un monitor real.

    La partimos en tramos cortitos y en cada cuadro solo se actualiza el tramo
    donde va el cursor, así la animación no se traba.
    """

    TRAMO = 24  # puntos por tramo

    def __init__(self, lienzo, color, grosor=2):
        self.lienzo = lienzo
        self.color = color
        self.grosor = grosor
        self.n = 0
        self.tramos = []

    def configurar(self, x0, x1, centro, amplitud):
        self.n = max(4, int((x1 - x0) * PUNTOS_POR_PIXEL))
        paso = (x1 - x0) / (self.n - 1)
        self.xs = [x0 + i * paso for i in range(self.n)]
        self.ys = [centro] * self.n
        self.centro = centro
        self.amplitud = amplitud
        self.cursor = 0
        total = math.ceil((self.n - 1) / self.TRAMO)
        self.tramos = [
            self.lienzo.create_line(0, 0, 0, 0, fill=self.color, width=self.grosor,
                                    state="hidden", joinstyle="round")
            for _ in range(total)
        ]

    def agregar(self, valores):
        """Agrega muestras normalizadas (positivo hacia arriba)."""
        if not self.tramos or not valores:
            return
        tramo, n, ultimo_tramo = self.TRAMO, self.n, len(self.tramos) - 1
        sucios = set()
        for v in valores:
            j = self.cursor
            self.ys[j] = self.centro - v * self.amplitud
            sucios.add(min(j // tramo, ultimo_tramo))
            if j % tramo == 0 and j > 0:
                sucios.add(j // tramo - 1)
            self.cursor = (j + 1) % n
        ultimo = (self.cursor - 1) % n
        for c in sucios:
            self._refrescar(c, ultimo)
        # el tramo que sigue al cursor se esconde, es la franja que va borrando
        siguiente = min(ultimo // tramo, ultimo_tramo) + 1
        if siguiente <= ultimo_tramo:
            self.lienzo.itemconfigure(self.tramos[siguiente], state="hidden")

    def _refrescar(self, c, ultimo):
        a = c * self.TRAMO
        b = min(a + self.TRAMO, self.n - 1)
        if c == min(ultimo // self.TRAMO, len(self.tramos) - 1) and ultimo < b:
            b = ultimo
        item = self.tramos[c]
        if b - a < 1:
            self.lienzo.itemconfigure(item, state="hidden")
            return
        coords = []
        xs, ys = self.xs, self.ys
        for j in range(a, b + 1):
            coords.append(xs[j])
            coords.append(ys[j])
        self.lienzo.coords(item, *coords)
        self.lienzo.itemconfigure(item, state="normal")


# panel numérico

class PanelNumerico(tk.Canvas):
    """Recuadro con el valor grande de un parámetro y datos secundarios."""

    def __init__(self, padre, titulo, unidad, color, corazon=False, caracteres=3):
        super().__init__(padre, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDE, width=290, height=100)
        self.titulo = titulo
        self.unidad = unidad
        self.color = color
        self.con_corazon = corazon
        self.caracteres = caracteres
        self.valor = "--"
        self.sub = ""
        self.nivel = 0
        self.destello = False
        self.latiendo = False
        self._listo = False
        # dato destacado opcional (texto, nivel de alarma, si va en descenso)
        self.destacado = None
        self.bind("<Configure>", lambda e: self._componer())

    def _componer(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return
        tam = max(20, int(min(h * 0.62, (w * 0.60) / (0.56 * self.caracteres))))
        self.id_titulo = self.create_text(10, 7, anchor="nw", text=self.titulo,
                                          fill=self.color, font=fuente(14, True))
        self.id_unidad = self.create_text(w - 10, 8, anchor="ne", text=self.unidad,
                                          fill=TENUE, font=fuente(12))
        self.id_estado = self.create_text(10, 27, anchor="nw", text="", font=fuente(11, True))
        self.id_valor = self.create_text(w - 14, h * 0.58, anchor="e", text=self.valor,
                                         fill=self.color, font=fuente(tam, True))
        self.id_sub = self.create_text(10, h - 8, anchor="sw", text=self.sub, fill=TEXTO,
                                       font=fuente(12), justify="left")
        if self.con_corazon:
            self.id_corazon = self.create_polygon(puntos_corazon(74, 17, 0.55),
                                                  fill=ROJO_FONDO, outline="")
        # dato destacado con flecha vectorial de descenso
        yd = h * 0.56
        self.id_flecha = self.create_polygon(10, yd - 6, 24, yd - 6, 17, yd + 7,
                                             fill=ROJO, outline="", state="hidden")
        self.id_destacado = self.create_text(10, yd, anchor="w", text="", fill=TEXTO,
                                             font=fuente(20, True))
        self._listo = True
        self._pintar()

    def actualizar(self, valor, sub, nivel, destello, destacado=None):
        self.destacado = destacado
        self.valor, self.sub, self.nivel, self.destello = valor, sub, nivel, destello
        if self._listo:
            self._pintar()

    def latir(self, activo):
        self.latiendo = activo
        if self._listo and self.con_corazon:
            self.itemconfigure(self.id_corazon, fill=ROJO if activo else ROJO_FONDO)

    def _pintar(self):
        critico_encendido = self.nivel == CRITICO and self.destello
        self.configure(bg=ROJO_FONDO if critico_encendido else PANEL)
        borde = {0: BORDE, ALERTA: AMBAR, CRITICO: ROJO}[self.nivel]
        self.configure(highlightbackground=borde)
        self.itemconfigure(self.id_valor, text=self.valor,
                           fill=BLANCO if critico_encendido else self.color)
        self.itemconfigure(self.id_titulo, fill=BLANCO if critico_encendido else self.color)
        self.itemconfigure(self.id_sub, text=self.sub)
        estado = {0: "", ALERTA: "ALERTA", CRITICO: "CRÍTICO"}[self.nivel]
        color_estado = AMBAR if self.nivel == ALERTA else (BLANCO if critico_encendido else ROJO)
        self.itemconfigure(self.id_estado, text=estado, fill=color_estado)
        if self.destacado:
            texto, nivel_d, bajando = self.destacado
            tinta = {0: TEXTO, ALERTA: AMBAR, CRITICO: ROJO}[nivel_d]
            if critico_encendido:
                tinta = BLANCO
            self.itemconfigure(self.id_flecha, fill=tinta, state="normal" if bajando else "hidden")
            self.coords(self.id_destacado, 30 if bajando else 10, self.winfo_height() * 0.56)
            self.itemconfigure(self.id_destacado, text=texto, fill=tinta)
        if self.con_corazon and critico_encendido and not self.latiendo:
            self.itemconfigure(self.id_corazon, fill="#5c0b10")
        elif self.con_corazon and not self.latiendo:
            self.itemconfigure(self.id_corazon, fill=ROJO_FONDO)


# panel de salud ósea

def color_perdida(perdida):
    """Color de una región según su pérdida de densidad (verde a rojo)."""
    escala = ((0.0, (47, 226, 111)), (3.0, (236, 226, 58)), (7.0, (255, 150, 40)), (12.0, (255, 61, 61)))
    if perdida >= escala[-1][0]:
        r, g, b = escala[-1][1]
    else:
        r, g, b = escala[0][1]
        for (p0, c0), (p1, c1) in zip(escala, escala[1:]):
            if p0 <= perdida < p1:
                k = (perdida - p0) / (p1 - p0)
                r, g, b = (c0[i] + (c1[i] - c0[i]) * k for i in range(3))
                break
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


class PanelOseo(tk.Canvas):
    """Figura del cuerpo con el esqueleto coloreado según la pérdida ósea."""

    ANCHO = 250
    PIE = 296   # alto reservado bajo la figura para indicadores y botones
    LISTA = ("cadera", "lumbar", "femur", "tibia", "calcaneo", "antebrazo")

    def __init__(self, padre, al_cambiar_dias):
        super().__init__(padre, width=self.ANCHO, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDE)
        self.al_cambiar_dias = al_cambiar_dias
        self._listo = False
        self._datos = None
        self.bind("<Configure>", lambda e: self._componer())

    def _componer(self):
        self.delete("all")
        self._listo = False
        w, h = self.winfo_width(), self.winfo_height()
        if w < 200 or h < 380:
            return
        self.create_text(10, 7, anchor="nw", text="SALUD ÓSEA", fill=BLANCO, font=fuente(14, True))
        self.id_dia = self.create_text(w - 10, 8, anchor="ne", text="", fill=TENUE, font=fuente(12))

        # la figura se dibuja en proporciones del alto del cuerpo
        y0 = 36
        alto = h - self.PIE - y0
        cx = w / 2

        def plano(puntos):
            return [c for x, y in puntos for c in (cx + x * alto, y0 + y * alto)]

        # silueta: primero el contorno brillante y encima el relleno oscuro
        for color, extra in (("#1f7f9e", 3), ("#0a222e", 0)):
            def linea(puntos, ancho):
                self.create_line(*plano(puntos), fill=color, width=ancho * alto + extra,
                                 capstyle="round", joinstyle="round")
            x, y = cx, y0 + 0.062 * alto
            r = 0.055 * alto + extra / 2
            self.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
            linea([(0, 0.11), (0, 0.16)], 0.05)
            self.create_polygon(*plano([(-0.105, 0.17), (0.105, 0.17), (0.085, 0.36), (0.09, 0.50),
                                        (-0.09, 0.50), (-0.085, 0.36)]),
                                fill=color, outline=color, width=extra, joinstyle="round")
            for s in (-1, 1):
                linea([(s * 0.118, 0.185), (s * 0.15, 0.36), (s * 0.168, 0.52)], 0.042)
                linea([(s * 0.052, 0.50), (s * 0.06, 0.73), (s * 0.056, 0.95)], 0.068)
                linea([(s * 0.056, 0.955), (s * 0.085, 0.975)], 0.035)

        # esqueleto: cada región tiene su etiqueta para poder cambiarle el color
        def hueso(clave, puntos, ancho=0.014, suave=False):
            self.create_line(*plano(puntos), fill=VERDE, width=max(2, ancho * alto),
                             capstyle="round", joinstyle="round", smooth=suave, tags=("r_" + clave,))

        def anillo(clave, x, y, radio, ancho):
            puntos = [(x + radio * math.cos(2 * math.pi * i / 16), y + radio * math.sin(2 * math.pi * i / 16))
                      for i in range(17)]
            hueso(clave, puntos, ancho, suave=True)

        anillo("craneo", 0, 0.058, 0.034, 0.010)
        hueso("toracica", [(0, 0.125), (0, 0.365)], 0.016)
        hueso("costillas", [(-0.098, 0.178), (0.098, 0.178)], 0.010)
        for y in (0.205, 0.24, 0.275, 0.31):
            for s in (-1, 1):
                hueso("costillas", [(0, y), (s * 0.045, y - 0.008), (s * 0.07, y + 0.012)], 0.009, True)
        hueso("lumbar", [(0, 0.385), (0, 0.465)], 0.024)
        hueso("pelvis", [(-0.075, 0.468), (-0.04, 0.508), (0, 0.518), (0.04, 0.508), (0.075, 0.468)], 0.020)
        for s in (-1, 1):
            anillo("cadera", s * 0.068, 0.515, 0.011, 0.012)
            hueso("femur", [(s * 0.066, 0.54), (s * 0.06, 0.715)], 0.018)
            hueso("tibia", [(s * 0.06, 0.75), (s * 0.056, 0.93)], 0.015)
            hueso("calcaneo", [(s * 0.054, 0.952), (s * 0.084, 0.972)], 0.016)
            hueso("humero", [(s * 0.122, 0.20), (s * 0.15, 0.35)], 0.014)
            hueso("antebrazo", [(s * 0.154, 0.375), (s * 0.168, 0.505)], 0.012)

        # indicador circular de densidad global
        yb = h - self.PIE + 8
        gx, gy, gr = 56, yb + 50, 40
        caja = (gx - gr, gy - gr, gx + gr, gy + gr)
        self.create_arc(*caja, start=225, extent=-270, style="arc", width=7, outline=BORDE)
        self.id_arco = self.create_arc(*caja, start=225, extent=-270, style="arc", width=7, outline=VERDE)
        self.id_densidad = self.create_text(gx, gy - 2, text="", fill=BLANCO, font=fuente(24, True))
        self.create_text(gx, gy + 20, text="%", fill=TENUE, font=fuente(11))
        self.create_text(gx, yb + 104, text="Densidad ósea", fill=TENUE, font=fuente(11))

        # pérdida por región
        self.id_filas = {}
        for i, clave in enumerate(self.LISTA):
            y = yb + 6 + i * 17
            self.create_text(112, y, anchor="nw", text=NOMBRES_OSEOS[clave].replace("Columna l", "L"),
                             fill=TENUE, font=fuente(12))
            self.id_filas[clave] = self.create_text(w - 10, y, anchor="ne", text="", font=fuente(12, True))

        # barra de riesgo de fractura
        y1 = yb + 122
        self.create_text(10, y1, anchor="nw", text="Riesgo de fractura", fill=TENUE, font=fuente(11))
        self.id_riesgo = self.create_text(w - 10, y1 - 1, anchor="ne", text="", font=fuente(12, True))
        self._barra = (10, w - 10, y1 + 24)
        tercio = (w - 20) / 3
        for i, color in enumerate(("#1f7a40", "#8a6a14", "#8a1d1d")):
            self.create_rectangle(10 + i * tercio, y1 + 24, 10 + (i + 1) * tercio - 2, y1 + 31,
                                  fill=color, outline="")
        self.id_marca = self.create_polygon(0, 0, 0, 0, 0, 0, fill=BLANCO, outline="")

        # botones para adelantar o retrasar la misión
        # lesiones probables, en lenguaje sencillo
        self.create_text(10, yb + 166, anchor="w", text="LESIONES PROBABLES", fill=TENUE,
                         font=fuente(11, True))
        self.id_lesiones = self.create_text(10, yb + 176, anchor="nw", text="", fill=TEXTO,
                                            width=w - 20, font=fuente(11))

        y2 = yb + 236
        mitad = w / 2
        for etiqueta, texto, xa, xb, dias in (("menos", "- 30 días", 10, mitad - 3, -30),
                                              ("mas", "+ 30 días", mitad + 3, w - 10, 30)):
            self.create_rectangle(xa, y2, xb, y2 + 26, fill=PANEL_ALTO, outline=BORDE, tags=(etiqueta,))
            self.create_text((xa + xb) / 2, y2 + 13, text=texto, fill=TEXTO, font=fuente(12),
                             tags=(etiqueta,))
            self.tag_bind(etiqueta, "<Button-1>", lambda e, d=dias: self.al_cambiar_dias(d))
            self.tag_bind(etiqueta, "<Enter>", lambda e: self.configure(cursor="hand2"))
            self.tag_bind(etiqueta, "<Leave>", lambda e: self.configure(cursor=""))

        self._listo = True
        if self._datos:
            self.actualizar(*self._datos)

    def actualizar(self, dia, perdidas, densidad, riesgo, lesiones):
        self._datos = (dia, perdidas, densidad, riesgo, lesiones)
        if not self._listo:
            return
        hay_lesion = not lesiones[0].startswith("Sin lesiones")
        self.itemconfigure(self.id_lesiones, text="\n".join(lesiones),
                           fill=AMBAR if hay_lesion else TEXTO)
        self.itemconfigure(self.id_dia, text=f"Día de misión {dia}")
        for clave, perdida in perdidas.items():
            self.itemconfigure("r_" + clave, fill=color_perdida(perdida))
        for clave, item in self.id_filas.items():
            self.itemconfigure(item, text=f"-{perdidas[clave]:.1f} %", fill=color_perdida(perdidas[clave]))
        # el indicador abarca de 80 a 100 % de densidad
        lleno = max(0.02, min(1.0, (densidad - 80.0) / 20.0))
        self.itemconfigure(self.id_arco, extent=-270 * lleno, outline=color_perdida(100.0 - densidad))
        self.itemconfigure(self.id_densidad, text=f"{densidad:.0f}")
        nivel = nivel_riesgo(riesgo)
        self.itemconfigure(self.id_riesgo, text=nivel,
                           fill={"Bajo": VERDE, "Moderado": AMBAR, "Alto": ROJO}[nivel])
        xa, xb, y = self._barra
        x = xa + (xb - xa) * riesgo
        self.coords(self.id_marca, x - 6, y - 9, x + 6, y - 9, x, y - 1)
        self.configure(highlightbackground=ROJO if nivel == "Alto" else BORDE)


# panel de radiación (contador Geiger) y riesgos de la misión

class PanelRiesgos(tk.Canvas):
    """Contador Geiger con síntomas probables e indicadores de riesgo medibles."""

    ANCHO = 262
    ALTO_GEIGER = 268
    _COLOR_NIVEL = {0: VERDE, ALERTA: AMBAR, CRITICO: ROJO}

    def __init__(self, padre):
        super().__init__(padre, width=self.ANCHO, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDE)
        self._listo = False
        self._datos = None
        self._clic = False
        self.bind("<Configure>", lambda e: self._componer())

    def _componer(self):
        self.delete("all")
        self._listo = False
        w, h = self.winfo_width(), self.winfo_height()
        if w < 200 or h < 420:
            return
        self.create_text(10, 7, anchor="nw", text="CONTADOR GEIGER", fill=BLANCO, font=fuente(14, True))
        self.id_clic = self.create_oval(w - 22, 9, w - 10, 21, fill="#3a2a05", outline="")

        # medidor de aguja con escala logarítmica de 0.01 a 1000 mSv/h
        self._centro = gx, gy = 72, 100
        self._radio = r = 54
        caja = (gx - r, gy - r, gx + r, gy + r)
        for i, color in enumerate((VERDE, "#a8e23a", AMARILLO, AMBAR, ROJO)):
            self.create_arc(*caja, start=180 - 36 * i, extent=-34, style="arc", width=8, outline=color)
        self.create_text(gx - r, gy + 9, text="0.01", fill=TENUE, font=fuente(10))
        self.create_text(gx + r, gy + 9, text="1000", fill=TENUE, font=fuente(10))
        self.id_aguja = self.create_line(gx, gy, gx - r + 12, gy, fill=BLANCO, width=3, capstyle="round")
        self.create_oval(gx - 5, gy - 5, gx + 5, gy + 5, fill=BLANCO, outline="")
        self.id_tasa = self.create_text(gx, gy + 27, text="", fill=TEXTO, font=fuente(14, True))

        self.id_cpm = self.create_text(w - 10, 66, anchor="e", text="", fill=VERDE, font=fuente(28, True))
        self.create_text(w - 10, 90, anchor="e", text="cuentas por minuto", fill=TENUE, font=fuente(11))

        self.create_text(10, 142, anchor="nw", text="Dosis del evento", fill=TENUE, font=fuente(12))
        self.id_evento = self.create_text(w - 10, 142, anchor="ne", text="", font=fuente(12, True))
        self.create_text(10, 160, anchor="nw", text="Dosis acumulada", fill=TENUE, font=fuente(12))
        self.id_dosis = self.create_text(w - 10, 160, anchor="ne", text="", fill=TEXTO, font=fuente(12, True))
        self.create_rectangle(10, 181, w - 10, 185, fill=BORDE, outline="")
        self.id_carrera = self.create_rectangle(10, 181, 10, 185, fill=VERDE, outline="")
        self.create_text(10, 196, anchor="w", text="SÍNTOMAS PROBABLES", fill=TENUE, font=fuente(11, True))
        self.id_sintomas = self.create_text(10, 206, anchor="nw", text="", fill=TEXTO, width=w - 20,
                                            font=fuente(12))
        self.create_line(0, self.ALTO_GEIGER, w, self.ALTO_GEIGER, fill=BORDE)

        # indicadores de riesgo
        y0 = self.ALTO_GEIGER + 8
        self.create_text(10, y0, anchor="nw", text="RIESGOS DE LA MISIÓN", fill=BLANCO, font=fuente(14, True))
        y0 += 26
        alto = (h - y0 - 4) / 6
        self.id_filas = []
        for i in range(6):
            y = y0 + i * alto
            nombre = self.create_text(10, y, anchor="nw", text="", fill=TENUE, font=fuente(11))
            valor = self.create_text(10, y + 14, anchor="nw", text="", font=fuente(15, True))
            detalle = self.create_text(w - 10, y + 19, anchor="ne", text="", fill=TENUE, font=fuente(10))
            self.create_rectangle(10, y + 36, w - 10, y + 40, fill=BORDE, outline="")
            barra = self.create_rectangle(10, y + 36, 10, y + 40, fill=VERDE, outline="")
            self.id_filas.append((nombre, valor, detalle, barra, y + 36))
        self._listo = True
        if self._datos:
            self.actualizar(*self._datos)

    def clic(self, encendido):
        """Enciende el indicador cuando el contador detecta una partícula."""
        if self._listo and encendido != self._clic:
            self._clic = encendido
            self.itemconfigure(self.id_clic, fill=AMBAR if encendido else "#3a2a05")

    def actualizar(self, tasa, cpm, nivel_tasa, dosis_evento, dosis, limite, sintomas, riesgos):
        self._datos = (tasa, cpm, nivel_tasa, dosis_evento, dosis, limite, sintomas, riesgos)
        if not self._listo:
            return
        w = self.winfo_width()
        # aguja: cinco décadas repartidas en media circunferencia
        k = max(0.0, min(1.0, (math.log10(max(tasa, 0.01)) + 2.0) / 5.0))
        angulo = math.pi * (1.0 - k)
        gx, gy = self._centro
        largo = self._radio - 10
        self.coords(self.id_aguja, gx, gy, gx + largo * math.cos(angulo), gy - largo * math.sin(angulo))
        color = self._COLOR_NIVEL[nivel_tasa]
        self.itemconfigure(self.id_tasa, text=f"{tasa:.2f} mSv/h" if tasa < 10 else f"{tasa:.0f} mSv/h",
                           fill=TEXTO if nivel_tasa == 0 else color)
        self.itemconfigure(self.id_cpm, text=f"{cpm:,.0f}".replace(",", " "), fill=color)

        nivel_s, _, texto = sintomas
        color_s = self._COLOR_NIVEL[nivel_s]
        hay_evento = dosis_evento > 0.05 or nivel_tasa > 0
        self.itemconfigure(self.id_evento, text=f"{dosis_evento:.1f} mSv",
                           fill=color_s if nivel_s else (AMBAR if hay_evento else TEXTO))
        self.itemconfigure(self.id_dosis, text=f"{dosis:.1f} / {limite:.0f} mSv",
                           fill=ROJO if dosis > limite else TEXTO)
        self.coords(self.id_carrera, 10, 181, 10 + (w - 20) * min(1.0, dosis / limite), 185)
        self.itemconfigure(self.id_carrera, fill=ROJO if dosis > limite else AMBAR if dosis > 0.5 * limite else VERDE)
        self.itemconfigure(self.id_sintomas, text=texto,
                           fill=color_s if nivel_s else (AMBAR if hay_evento else TEXTO))
        self.configure(highlightbackground=color if nivel_tasa else BORDE)

        for (nombre, valor, detalle, barra, y), r in zip(self.id_filas, riesgos):
            c = self._COLOR_NIVEL[r["nivel"]]
            self.itemconfigure(nombre, text=r["nombre"])
            self.itemconfigure(valor, text=r["valor"], fill=c if r["nivel"] else TEXTO)
            self.itemconfigure(detalle, text=r["detalle"])
            self.coords(barra, 10, y, 10 + (w - 20) * r["fraccion"], y + 4)
            self.itemconfigure(barra, fill=c)


# panel del nivel de estrés

class PanelEstres(tk.Canvas):
    """Índice de estrés, los marcadores con que se mide y su gráfica de 3 minutos."""

    ALTO = 132
    _COLORES = (VERDE, AMARILLO, AMBAR, ROJO)

    def __init__(self, padre):
        super().__init__(padre, height=self.ALTO, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDE)
        self._listo = False
        self._datos = None
        self.bind("<Configure>", lambda e: self._componer())

    def _componer(self):
        self.delete("all")
        self._listo = False
        w, h = self.winfo_width(), self.winfo_height()
        if w < 520 or h < 100:
            return
        self.create_text(10, 7, anchor="nw", text="NIVEL DE ESTRÉS", fill=BLANCO, font=fuente(14, True))
        self.id_valor = self.create_text(10, 26, anchor="nw", text="", fill=VERDE, font=fuente(46, True))
        self.id_de = self.create_text(96, 60, anchor="nw", text="de 100", fill=TENUE, font=fuente(11))
        self.id_nivel = self.create_text(10, 84, anchor="nw", text="", fill=VERDE, font=fuente(15, True))
        self.id_tendencia = self.create_text(10, 106, anchor="nw", text="", fill=TENUE, font=fuente(11))

        # marcadores con los que se mide
        x0, x1 = 158, 346
        self.id_marcadores = []
        for i, titulo in enumerate(("Variabilidad cardiaca", "Índice de Baevsky", "Cortisol en saliva")):
            y = 30 + i * 32
            self.create_text(x0, y, anchor="nw", text=titulo, fill=TENUE, font=fuente(11))
            self.id_marcadores.append(
                self.create_text(x0, y + 12, anchor="nw", text="", fill=TEXTO, font=fuente(14, True)))
        self.create_line(x1, 8, x1, h - 8, fill=BORDE)

        # gráfica: eje vertical de 0 a 100 y los últimos 3 minutos en horizontal
        self._gx0, self._gx1 = x1 + 34, w - 12
        self._gy0, self._gy1 = 28, h - 20
        gx0, gx1, gy0, gy1 = self._gx0, self._gx1, self._gy0, self._gy1
        self.id_causas = self.create_text(gx1, 7, anchor="ne", text="", fill=TENUE, font=fuente(11))
        self.create_rectangle(gx0, gy0, gx1, gy1, fill="#05090e", outline=BORDE)
        for valor, color in ((modelo_estres.LIMITE_MODERADO, AMARILLO), (modelo_estres.LIMITE_ALTO, AMBAR)):
            y = gy1 - (gy1 - gy0) * valor / 100.0
            self.create_line(gx0, y, gx1, y, fill=color, dash=(2, 5))
            self.create_text(gx0 - 5, y, anchor="e", text=f"{valor:.0f}", fill=color, font=fuente(10))
        self.create_text(gx0 - 5, gy0 + 4, anchor="e", text="100", fill=TENUE, font=fuente(10))
        self.create_text(gx0 - 5, gy1 - 4, anchor="e", text="0", fill=TENUE, font=fuente(10))
        self.create_text(gx0, gy1 + 3, anchor="nw", text="hace 3 min", fill=TENUE, font=fuente(10))
        self.create_text(gx1, gy1 + 3, anchor="ne", text="ahora", fill=TENUE, font=fuente(10))
        self.id_linea = self.create_line(gx0, gy1, gx1, gy1, fill=VERDE, width=2, joinstyle="round")
        self.id_punto = self.create_oval(0, 0, 0, 0, fill=VERDE, outline="")
        self._listo = True
        if self._datos:
            self.actualizar(*self._datos)

    def actualizar(self, a, destello):
        self._datos = (a, destello)
        if not self._listo:
            return
        if a.sin_pulso:
            # en paro no hay señal para medir el estrés
            self.itemconfigure(self.id_valor, text="--", fill=ROJO)
            self.itemconfigure(self.id_nivel, text="Sin signos", fill=ROJO)
            self.itemconfigure(self.id_tendencia, text="")
            for ident in self.id_marcadores:
                self.itemconfigure(ident, text="--", fill=ROJO)
            self.itemconfigure(self.id_causas, text="")
            self.configure(highlightbackground=ROJO if destello else ROJO_FONDO)
            return
        numero, nombre = modelo_estres.nivel(a.estres)
        color = self._COLORES[numero]
        self.itemconfigure(self.id_valor, text=f"{a.estres:.0f}", fill=color)
        self.coords(self.id_de, 20 + 27 * len(f"{a.estres:.0f}"), 60)
        self.itemconfigure(self.id_nivel, text=nombre, fill=color)
        historial = a.historial_estres
        cambio = a.estres - historial[-20] if len(historial) >= 20 else 0.0
        self.itemconfigure(self.id_tendencia,
                           text="Subiendo" if cambio > 2.0 else "Bajando" if cambio < -2.0 else "Estable")
        baevsky = modelo_estres.indice_baevsky(a.estres)
        textos = (f"{a.rmssd:.0f} ms", f"{baevsky:.0f}", f"{a.cortisol:.1f} nmol/L")
        avisos = (a.rmssd < 20.0, baevsky > 150.0, a.cortisol > 25.0)
        for ident, texto, aviso in zip(self.id_marcadores, textos, avisos):
            self.itemconfigure(ident, text=texto, fill=color if aviso and numero else TEXTO)

        # causas que más pesan en este momento
        causas = sorted((f for f in a.factores_estres if abs(f[1]) >= 3.0), key=lambda f: -f[1])[:3]
        texto = "   ·   ".join(f"{n} {p:+.0f}" for n, p in causas)
        if a.alivio >= 3.0:
            texto += f"   ·   Bienestar {-a.alivio:+.0f}"
        self.itemconfigure(self.id_causas, text=texto)

        # curva de los últimos 3 minutos; la muestra más reciente queda a la derecha
        gx0, gx1, gy0, gy1 = self._gx0, self._gx1, self._gy0, self._gy1
        n, maximo = len(historial), historial.maxlen
        if n >= 2:
            paso = (gx1 - gx0) / (maximo - 1)
            puntos = []
            for i, valor in enumerate(historial):
                puntos += (gx1 - (n - 1 - i) * paso, gy1 - (gy1 - gy0) * valor / 100.0)
            self.coords(self.id_linea, *puntos)
            x, y = puntos[-2], puntos[-1]
            self.coords(self.id_punto, x - 4, y - 4, x + 4, y + 4)
        self.itemconfigure(self.id_linea, fill=color)
        self.itemconfigure(self.id_punto, fill=color)
        self.configure(highlightbackground=color if numero >= 2 else BORDE)


# ventana emergente con la guía paso a paso

class VentanaGuia(tk.Toplevel):
    """Ventana medio transparente que sale frente al monitor con los pasos.

    Pensada para gente que no es médico: título grande, una frase de qué pasa,
    pasos numerados y si hace falta un contador para respirar o dar compresiones.
    """

    FONDO_GUIA = "#070b11"

    def __init__(self, app, al_accion):
        super().__init__(app)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(app)
        self.app = app
        self.al_accion = al_accion
        self.clave = None       # (tripulante, guía) que se está mostrando
        self.guia = None
        self.visible = False
        self._geometria = None
        self._ancho = 0
        self._alto = 0
        self._t0 = 0.0
        self.contador = None
        self.marco = tk.Frame(self, bg=self.FONDO_GUIA)
        self.marco.pack(fill="both", expand=True, padx=3, pady=3)

    def mostrar(self, guia, astronauta):
        clave = (astronauta.nombre, guia.clave)
        ancho = self.app.lienzo.winfo_width() - 20
        self.guia = guia
        if clave != self.clave or ancho != self._ancho:
            self.clave = clave
            self._ancho = ancho
            self._construir(guia, astronauta)
            self._t0 = time.perf_counter()
            self._geometria = None
        if guia.estado:
            self.et_estado.configure(text=guia.estado())
        self.colocar()
        if not self.visible:
            self.deiconify()
            self.lift()
            self.visible = True

    def ocultar(self):
        if self.visible:
            self.withdraw()
            self.visible = False
        self.clave = None

    def colocar(self):
        """Acomoda la ventana sobre la zona de trazos del monitor."""
        lienzo = self.app.lienzo
        alto_lienzo = lienzo.winfo_height()
        if self.guia.modo == "rcp":
            alto = alto_lienzo - 20          # el paro cubre todo el monitor
        else:
            alto = min(self._alto, alto_lienzo - 20)
        x = lienzo.winfo_rootx() + 10
        y = lienzo.winfo_rooty() + alto_lienzo - alto - 10
        geometria = f"{self._ancho}x{alto}+{x}+{y}"
        if geometria != self._geometria:
            self._geometria = geometria
            self.geometry(geometria)

    def _construir(self, guia, astronauta):
        for hijo in self.marco.winfo_children():
            hijo.destroy()
        paro = guia.modo == "rcp"
        color = CIAN if guia.rutina else ROJO if guia.nivel == CRITICO else AMBAR
        fondo = self.FONDO_GUIA
        self.configure(bg=color)
        # en paro va más transparente para seguir viendo el trazo de atrás
        self.attributes("-alpha", 0.84 if paro else 0.92)

        arriba = tk.Frame(self.marco, bg=fondo)
        arriba.pack(fill="x", padx=14, pady=(10, 4))
        self.contador = None
        if guia.modo:
            self.contador = tk.Canvas(arriba, width=170, height=170, bg=fondo, highlightthickness=0)
            self.contador.pack(side="right", padx=(10, 0))
            self.id_circulo = self.contador.create_oval(55, 55, 115, 115, fill="#12384a", outline=color, width=3)
            self.id_cuenta = self.contador.create_text(85, 78, text="", fill=BLANCO, font=fuente(38, True))
            self.id_palabra = self.contador.create_text(85, 112, text="", fill=BLANCO, font=fuente(13, True))
        textos = tk.Frame(arriba, bg=fondo)
        textos.pack(side="left", fill="x", expand=True)
        ancho_texto = self._ancho - 60 - (180 if guia.modo else 0)
        if guia.rutina:
            tk.Label(textos, text="RECOMENDACIÓN DE RUTINA  ·  CUIDE SU BIENESTAR", bg=fondo, fg=TENUE,
                     anchor="w", font=fuente(11, True)).pack(anchor="w")
        tk.Label(textos, text=guia.titulo, bg=fondo, fg=color, anchor="w",
                 font=fuente(58 if paro else 30, True)).pack(anchor="w")
        tk.Label(textos, text=astronauta.nombre + "  ·  " + guia.resumen, bg=fondo, fg=BLANCO,
                 anchor="w", justify="left", wraplength=ancho_texto, font=fuente(15)).pack(anchor="w")
        self.et_estado = tk.Label(textos, text="", bg=fondo, fg=color, anchor="w", justify="left",
                                  wraplength=ancho_texto, font=fuente(15, True))
        self.et_estado.pack(anchor="w", pady=(4, 0))

        tk.Frame(self.marco, bg=color, height=2).pack(fill="x", padx=14, pady=(4, 6))
        tk.Label(self.marco, text="QUÉ HACER, PASO A PASO", bg=fondo, fg=TENUE,
                 font=fuente(11, True)).pack(anchor="w", padx=14)
        for numero, paso in enumerate(guia.pasos, start=1):
            fila = tk.Frame(self.marco, bg=fondo)
            fila.pack(fill="x", padx=14, pady=2)
            tk.Label(fila, text=str(numero), bg=color, fg="#10141a", width=2,
                     font=fuente(14, True)).pack(side="left", anchor="n")
            tk.Label(fila, text=paso, bg=fondo, fg=TEXTO, anchor="w", justify="left",
                     wraplength=self._ancho - 80, font=fuente(14)).pack(side="left", padx=(8, 0))

        pie = tk.Frame(self.marco, bg=fondo)
        pie.pack(fill="x", padx=14, pady=(8, 10))
        for texto, accion in guia.acciones:
            tk.Button(pie, text=texto, command=lambda a=accion: self.al_accion(a), bg=color,
                      fg="#10141a", activebackground=BLANCO, relief="flat", bd=0, cursor="hand2",
                      font=fuente(14, True), padx=14, pady=6).pack(side="left", padx=(0, 8))
        if not paro and not guia.rutina:
            tk.Button(pie, text="Entendido", command=lambda: self.al_accion("entendido"),
                      bg=PANEL_ALTO, fg=TEXTO, activebackground=BORDE, activeforeground=BLANCO,
                      relief="flat", bd=0, cursor="hand2", font=fuente(14), padx=14,
                      pady=6).pack(side="right")
        self.update_idletasks()
        self._alto = self.marco.winfo_reqheight() + 6

    def animar(self, ahora):
        """Actualiza el contador de respiración o de compresiones."""
        if not self.visible or self.contador is None:
            return
        t = ahora - self._t0
        if self.guia.modo == "respiracion":
            tiempos = self.guia.respiracion
            if len(tiempos) == 2:
                tiempos = (tiempos[0], 0.0, tiempos[1], 0.0)
            inhalar, sostener, exhalar, pausa = tiempos
            t %= inhalar + sostener + exhalar + pausa
            if t < inhalar:
                lleno, palabra, cuenta = t / inhalar, "TOME AIRE", int(t) + 1
            elif t < inhalar + sostener:
                lleno, palabra, cuenta = 1.0, "SOSTENGA", int(t - inhalar) + 1
            elif t < inhalar + sostener + exhalar:
                t -= inhalar + sostener
                lleno, palabra, cuenta = 1.0 - t / exhalar, "SUELTE EL AIRE", int(t) + 1
            else:
                lleno, palabra, cuenta = 0.0, "ESPERE", int(t - inhalar - sostener - exhalar) + 1
            radio = 30 + 50 * lleno
        else:
            # compresiones a 110 por minuto: 30 compresiones y pausa para 2 respiraciones
            periodo = 60.0 / 110.0
            t %= 30 * periodo + 4.0
            if t < 30 * periodo:
                fase = (t % periodo) / periodo
                radio = 78 if fase < 0.4 else 52
                palabra, cuenta = "EMPUJE", int(t / periodo) + 1
            else:
                radio, palabra, cuenta = 40, "2 RESPIRACIONES", ""
        self.contador.coords(self.id_circulo, 85 - radio, 85 - radio, 85 + radio, 85 + radio)
        self.contador.itemconfigure(self.id_cuenta, text=str(cuenta))
        self.contador.itemconfigure(self.id_palabra, text=palabra)


# tarjeta de tripulante

class TarjetaTripulante(tk.Canvas):
    """Resumen compacto de un tripulante; al pulsarla se selecciona."""

    ANCHO, ALTO = 226, 90

    def __init__(self, padre, astronauta, al_pulsar):
        super().__init__(padre, width=self.ANCHO, height=self.ALTO, bg=PANEL,
                         highlightthickness=1, highlightbackground=BORDE, cursor="hand2")
        w, h = self.ANCHO, self.ALTO
        self.id_barra = self.create_rectangle(0, 0, 5, h + 2, fill=VERDE, outline="")
        # icono vectorial de casco
        self.create_oval(14, 10, 46, 42, outline=TEXTO, width=2)
        self.create_oval(20, 18, 40, 34, fill="#1c6f8c", outline=CIAN)
        self.create_line(22, 44, 38, 44, fill=TEXTO, width=2)
        self.create_text(56, 9, anchor="nw", text=astronauta.nombre, fill=BLANCO,
                         font=fuente(14, True))
        self.create_text(56, 28, anchor="nw", text=astronauta.rol, fill=TENUE, font=fuente(11))
        self.id_fc = self.create_text(14, 52, anchor="nw", fill=VERDE, font=fuente(13, True))
        self.id_spo2 = self.create_text(84, 52, anchor="nw", fill=CIAN, font=fuente(13, True))
        self.id_fr = self.create_text(166, 52, anchor="nw", fill=AMARILLO, font=fuente(13, True))
        self.id_estado = self.create_text(14, 71, anchor="nw", fill=TENUE, font=fuente(11))
        # barra vertical con el nivel de estrés, en el borde derecho
        self.create_rectangle(w - 9, 8, w - 4, h - 8, fill=BORDE, outline="")
        self.id_estres = self.create_rectangle(w - 9, h - 8, w - 4, h - 8, fill=VERDE, outline="")
        self.bind("<Button-1>", lambda e: al_pulsar())

    def actualizar(self, a, nivel, seleccionado, destello):
        paro = a.sin_pulso
        self.itemconfigure(self.id_fc, text="FC --" if paro else f"FC {a.fc:.0f}")
        self.itemconfigure(self.id_spo2, text="SpO2 --" if paro else f"SpO2 {a.spo2:.0f}")
        self.itemconfigure(self.id_fr, text="FR 0" if paro else f"FR {a.fr:.0f}")
        numero_estres = modelo_estres.nivel(a.estres)[0]
        w, h = self.ANCHO, self.ALTO
        lleno = 0.0 if paro else a.estres / 100.0
        self.coords(self.id_estres, w - 9, h - 8 - (h - 16) * lleno, w - 4, h - 8)
        self.itemconfigure(self.id_estres, fill=(VERDE, AMARILLO, AMBAR, ROJO)[numero_estres])
        color = {0: VERDE, ALERTA: AMBAR, CRITICO: ROJO}[nivel]
        if nivel == CRITICO and not destello:
            color = ROJO_FONDO
        self.itemconfigure(self.id_barra, fill=color)
        estado = {0: "Normal", ALERTA: "Alerta", CRITICO: "Crítico"}[nivel]
        if paro:
            estado = "SIN SIGNOS"
        elif a.etapa:
            estado += "  ·  " + a.etapa
        elif a.evento != "ninguno":
            estado += "  ·  " + EVENTOS_MEDICOS[a.evento]["nombre"]
        self.itemconfigure(self.id_estado, text=estado,
                           fill={0: TENUE, ALERTA: AMBAR, CRITICO: ROJO}[nivel])
        self.configure(bg=PANEL_ALTO if seleccionado else PANEL,
                       highlightbackground=CIAN if seleccionado else BORDE)


# aplicación

class Aplicacion(tk.Tk):

    # etiqueta, color, peso vertical, posición de la línea base, amplitud, transformación
    _TRAZOS = (
        ("I", VERDE, 1.0, 0.68, 0.50, lambda v: v * 1.6),
        ("II", VERDE, 1.0, 0.68, 0.50, lambda v: v),
        ("III", VERDE, 1.0, 0.68, 0.50, lambda v: v * 1.6),
        ("PLETH", CIAN, 1.1, 0.56, 0.40, lambda v: (v - 0.5) * 1.7),
        ("RESP", AMARILLO, 1.1, 0.56, 0.34, lambda v: v),
    )

    def __init__(self, carpeta_base):
        super().__init__()
        self.title("N.A.C.H.O. - NASA Administration Crew Health Onboard")
        self.configure(bg=FONDO)
        # ventana centrada y que quepa en la pantalla
        pantalla_w, pantalla_h = self.winfo_screenwidth(), self.winfo_screenheight()
        ancho = min(1720, pantalla_w - 40)
        alto = min(950, pantalla_h - 100)
        self.geometry(f"{ancho}x{alto}+{(pantalla_w - ancho) // 2}+{max(0, (pantalla_h - alto) // 2 - 30)}")
        self.minsize(min(1500, ancho), min(790, alto))

        # nuestro logo: icono de la ventana y emblema de la barra de arriba
        self._imagenes = {}
        for nombre_carpeta in ("assests", "assets"):
            for clave in ("icono_256", "icono_48", "icono_32", "logo_barra"):
                ruta = os.path.join(carpeta_base, nombre_carpeta, clave + ".png")
                if clave not in self._imagenes and os.path.exists(ruta):
                    try:
                        self._imagenes[clave] = tk.PhotoImage(file=ruta)
                    except tk.TclError:
                        pass
        iconos = [self._imagenes[c] for c in ("icono_256", "icono_48", "icono_32") if c in self._imagenes]
        if iconos:
            self.iconphoto(True, *iconos)

        self.mision = Mision()
        self.sel = 0
        self.pausa = False
        self.sonido = True
        self.audio = Sonido(carpeta_base)
        self._guia_oculta = None   # (tripulante, guía) que el usuario cerró con "Entendido"
        # recomendaciones de rutina: salen de vez en cuando si no hay emergencia
        self.rutina_auto = True
        self.recomendador = Recomendador()
        self._rutina = None        # (tripulante, guía, instante de inicio) en pantalla
        self._t_rutina = time.perf_counter() + SEGUNDOS_PRIMERA
        self.registro = Registro(os.path.join(carpeta_base, "registros"))
        self._alarmas_previas = set()
        self._origenes_con_alarma = set()
        self._etapas = {}
        self._cps = 0.0           # ritmo actual del contador Geiger
        self._cpm = 0.0           # cuentas por minuto suavizadas
        self._acum_muestras = 0.0
        self._dt_muestra = 0.01
        self._t_lento = 0.0
        self._t_registro = 0.0
        self._pendiente_ondas = None

        self._construir()
        self.ventana_guia = VentanaGuia(self, self._accion_guia)
        self._anotar("Monitoreo iniciado")
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self._t_prev = time.perf_counter()
        self.after(50, self._cuadro)

    # --- construcción ---

    def _construir(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # barra superior
        barra = tk.Frame(self, bg=PANEL, height=46)
        barra.grid(row=0, column=0, sticky="ew")
        barra.grid_propagate(False)
        barra.columnconfigure(2, weight=1)
        marca = tk.Frame(barra, bg=PANEL)
        marca.grid(row=0, column=0, padx=(14, 18), pady=4)
        if "logo_barra" in self._imagenes:
            tk.Label(marca, image=self._imagenes["logo_barra"], bg=PANEL).pack(side="left", padx=(0, 10))
        tk.Label(marca, text="N.A.C.H.O.", bg=PANEL, fg=BLANCO, font=fuente(20, True)).pack(side="left")
        tk.Label(marca, text="NASA Administration\nCrew Health Onboard", bg=PANEL, fg=TENUE,
                 justify="left", font=fuente(11)).pack(side="left", padx=(10, 0))
        self.et_reloj = tk.Label(barra, text="", bg=PANEL, fg=CIAN, font=fuente(16, True))
        self.et_reloj.grid(row=0, column=1, padx=6)
        self.et_fase = tk.Label(barra, text="", bg=PANEL, fg=TENUE, font=fuente(14))
        self.et_fase.grid(row=0, column=2, sticky="w", padx=14)
        self.aviso = tk.Frame(barra, bg=PANEL)
        self.aviso.grid(row=0, column=3, sticky="e", padx=8, pady=6)
        self.icono_aviso = tk.Canvas(self.aviso, width=30, height=30, bg=PANEL, highlightthickness=0)
        self.icono_aviso.pack(side="left", padx=(8, 2))
        # icono vectorial de advertencia
        self.id_triangulo = self.icono_aviso.create_polygon(15, 4, 28, 26, 2, 26, fill="", outline=VERDE, width=2)
        self.id_palo = self.icono_aviso.create_line(15, 12, 15, 19, fill=VERDE, width=2)
        self.id_punto = self.icono_aviso.create_oval(14, 21, 16, 23, fill=VERDE, outline=VERDE)
        self.et_aviso = tk.Label(self.aviso, text="", bg=PANEL, fg=VERDE, font=fuente(14, True))
        self.et_aviso.pack(side="left", padx=(2, 12))

        # zona central
        centro = tk.Frame(self, bg=FONDO)
        centro.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        centro.columnconfigure(1, weight=1)
        centro.rowconfigure(0, weight=1)

        izquierda = tk.Frame(centro, bg=FONDO)
        izquierda.grid(row=0, column=0, rowspan=2, sticky="ns")
        tk.Label(izquierda, text="TRIPULACIÓN", bg=FONDO, fg=TENUE,
                 font=fuente(11, True)).pack(anchor="w", pady=(0, 3))
        self.tarjetas = []
        for i, a in enumerate(self.mision.tripulacion):
            t = TarjetaTripulante(izquierda, a, lambda i=i: self._seleccionar(i))
            t.pack(pady=(0, 5))
            self.tarjetas.append(t)
        tk.Label(izquierda, text="BITÁCORA", bg=FONDO, fg=TENUE,
                 font=fuente(11, True)).pack(anchor="w", pady=(4, 3))
        self.bitacora = tk.Text(izquierda, width=1, height=1, bg=PANEL, fg=TEXTO, bd=0,
                                highlightthickness=1, highlightbackground=BORDE,
                                font=fuente(11), wrap="word", state="disabled",
                                padx=6, pady=4, cursor="arrow")
        self.bitacora.tag_configure("hora", foreground=TENUE)
        self.bitacora.tag_configure("alerta", foreground=AMBAR)
        self.bitacora.tag_configure("critico", foreground=ROJO)
        self.bitacora.pack(fill="both", expand=True)

        self.lienzo = tk.Canvas(centro, bg="#000000", highlightthickness=1,
                                highlightbackground=BORDE)
        self.lienzo.grid(row=0, column=1, sticky="nsew", padx=6)
        self.lienzo.bind("<Configure>", self._ondas_redimensionadas)
        self.trazos = [Trazo(self.lienzo, color) for _, color, *_ in self._TRAZOS]

        # nivel de estrés con su gráfica, debajo de los trazos
        self.p_estres = PanelEstres(centro)
        self.p_estres.grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))

        # salud ósea, junto a los signos vitales
        self.p_oseo = PanelOseo(centro, self._cambiar_dias)
        self.p_oseo.grid(row=0, column=2, rowspan=2, sticky="ns", padx=(0, 6))

        # contador Geiger y riesgos de la misión
        self.p_riesgos = PanelRiesgos(centro)
        self.p_riesgos.grid(row=0, column=3, rowspan=2, sticky="ns", padx=(0, 6))

        derecha = tk.Frame(centro, bg=FONDO)
        derecha.grid(row=0, column=4, rowspan=2, sticky="ns")
        self.p_fc = PanelNumerico(derecha, "FC", "lpm", VERDE, corazon=True)
        self.p_pni = PanelNumerico(derecha, "PNI", "mmHg", BLANCO, caracteres=7)
        self.p_temp = PanelNumerico(derecha, "TEMP", "°C", BLANCO, caracteres=4)
        self.p_spo2 = PanelNumerico(derecha, "SpO2", "%", CIAN)
        self.p_fr = PanelNumerico(derecha, "RESP", "rpm", AMARILLO)
        for fila, (panel, peso) in enumerate(((self.p_fc, 11), (self.p_pni, 10), (self.p_temp, 10),
                                              (self.p_spo2, 11), (self.p_fr, 10))):
            panel.grid(row=fila, column=0, sticky="nsew", pady=(0, 4 if fila < 4 else 0))
            derecha.rowconfigure(fila, weight=peso)

        # zona inferior: entorno y controles
        inferior = tk.Frame(self, bg=PANEL)
        inferior.grid(row=2, column=0, sticky="ew")

        lecturas = tk.Frame(inferior, bg=PANEL)
        lecturas.pack(fill="x", padx=10, pady=(6, 2))
        self.lecturas = {}
        for clave, titulo in (("presion", "Presión de cabina"), ("o2", "Oxígeno respirable"),
                              ("co2", "CO2 ambiental"), ("temp", "Temperatura de cabina"),
                              ("rad", "Radiación"), ("dosis", "Dosis acumulada"),
                              ("g", "Aceleración")):
            celda = tk.Frame(lecturas, bg=PANEL)
            celda.pack(side="left", expand=True, fill="x")
            et = tk.Label(celda, text=titulo, bg=PANEL, fg=TENUE, font=fuente(11))
            et.pack(anchor="w")
            valor = tk.Label(celda, text="", bg=PANEL, fg=TEXTO, font=fuente(16, True))
            valor.pack(anchor="w")
            self.lecturas[clave] = (et, valor)

        fila1 = tk.Frame(inferior, bg=PANEL)
        fila1.pack(fill="x", padx=10, pady=(4, 2))
        self.b_fases = self._grupo(fila1, "Fase de misión",
                                   [(k, v["nombre"]) for k, v in FASES.items()], self._cambiar_fase)
        sistema = tk.Frame(fila1, bg=PANEL)
        sistema.pack(side="right")
        self.b_recomendar = self._boton(sistema, "Recomendación ahora",
                                        lambda: self._accion_guia("rutina_ahora"))
        self.b_rutina = self._boton(sistema, "Rutina automática", self._alternar_rutina)
        self.b_pausa = self._boton(sistema, "Pausar", self._alternar_pausa)
        self.b_grabar = self._boton(sistema, "Grabar datos", self._alternar_grabacion)
        self.b_sonido = self._boton(sistema, "Sonido de alarma", self._alternar_sonido)

        # condiciones del tripulante seleccionado, agrupadas por tipo
        self.b_eventos = {}
        fila = None
        for titulo, claves in GRUPOS_EVENTOS:
            if titulo != "Paro cardiaco":   # el paro comparte fila con las urgencias
                fila = tk.Frame(inferior, bg=PANEL)
                fila.pack(fill="x", padx=10, pady=2)
            else:
                tk.Frame(fila, bg=PANEL, width=24).pack(side="left")
            self.b_eventos.update(self._grupo(
                fila, titulo, [(k, EVENTOS_MEDICOS[k]["nombre"]) for k in claves], self._cambiar_evento))

        fila4 = tk.Frame(inferior, bg=PANEL)
        fila4.pack(fill="x", padx=10, pady=(2, 8))
        self.b_entorno = self._grupo(fila4, "Entorno", list(EVENTOS_ENTORNO.items()),
                                     self._cambiar_entorno)
        tk.Frame(fila4, bg=PANEL, width=24).pack(side="left")
        tk.Label(fila4, text="ATENCIÓN", bg=PANEL, fg=TENUE, width=15, anchor="w",
                 font=fuente(11, True)).pack(side="left")
        self.b_oxigeno = self._boton(fila4, "Oxígeno", lambda: self._accion_guia("oxigeno_alternar"))
        self.b_rcp = self._boton(fila4, "Compresiones", lambda: self._accion_guia("rcp_alternar"))
        self.b_descarga = self._boton(fila4, "Dar descarga", lambda: self._accion_guia("descarga"))
        self._marcar_botones()

    def _boton(self, padre, texto, comando):
        b = tk.Button(padre, text=texto, command=comando, bg=PANEL_ALTO, fg=TEXTO,
                      activebackground=BORDE, activeforeground=BLANCO, relief="flat", bd=0,
                      font=fuente(12), padx=10, pady=4, cursor="hand2")
        b.pack(side="left", padx=2)
        return b

    def _grupo(self, padre, titulo, opciones, accion):
        tk.Label(padre, text=titulo.upper(), bg=PANEL, fg=TENUE, width=15, anchor="w",
                 font=fuente(11, True)).pack(side="left")
        return {clave: self._boton(padre, nombre, lambda c=clave: accion(c))
                for clave, nombre in opciones}

    @staticmethod
    def _estilo(boton, activo, color=CIAN):
        boton.configure(bg=color if activo else PANEL_ALTO, fg="#04121a" if activo else TEXTO,
                        activebackground=color if activo else BORDE)

    def _marcar_botones(self):
        a = self.mision.tripulacion[self.sel]
        for k, b in self.b_fases.items():
            self._estilo(b, k == self.mision.fase)
        for k, b in self.b_eventos.items():
            grave = k in PARO or k in ("descompensacion", "infarto", "ictus")
            self._estilo(b, k == a.evento, VERDE if k == "ninguno" else ROJO if grave else AMBAR)
        self._estilo(self.b_oxigeno, a.oxigeno)
        self._estilo(self.b_rcp, a.rcp)
        for k, b in self.b_entorno.items():
            self._estilo(b, k == self.mision.entorno.evento, VERDE if k == "nominal" else AMBAR)
        self._estilo(self.b_rutina, self.rutina_auto)
        self._estilo(self.b_pausa, self.pausa, AMBAR)
        self._estilo(self.b_grabar, self.registro.activo, ROJO)
        self._estilo(self.b_sonido, self.sonido)
        self.b_pausa.configure(text="Reanudar" if self.pausa else "Pausar")
        self.b_grabar.configure(text="Detener grabación" if self.registro.activo else "Grabar datos")

    # --- acciones ---

    def _seleccionar(self, i):
        if i == self.sel:
            return
        self.sel = i
        self._componer_ondas()
        self._marcar_botones()
        self._actualizar_lento()

    def _cambiar_fase(self, clave):
        self.mision.fase = clave
        self._anotar("Fase de misión: " + FASES[clave]["nombre"])
        self._marcar_botones()

    def _cambiar_evento(self, clave):
        a = self.mision.tripulacion[self.sel]
        a.evento = clave
        if clave == "ninguno":
            a.oxigeno = False
        self._guia_oculta = None
        self._anotar(f"{a.nombre}: {EVENTOS_MEDICOS[clave]['nombre'].lower()}")
        self._marcar_botones()

    def _accion_guia(self, accion):
        """Acciones de atención: desde la ventana emergente o desde los botones."""
        a = self.mision.tripulacion[self.sel]
        if accion in ("oxigeno", "oxigeno_alternar"):
            a.oxigeno = True if accion == "oxigeno" else not a.oxigeno
            self._anotar(f"{a.nombre}: oxígeno {'colocado' if a.oxigeno else 'retirado'}")
        elif accion in ("rcp", "rcp_alternar"):
            if not a.sin_pulso:
                self._anotar(f"{a.nombre}: tiene pulso, no necesita compresiones")
            else:
                a.rcp = True if accion == "rcp" else not a.rcp
                self._anotar(f"{a.nombre}: compresiones {'iniciadas' if a.rcp else 'detenidas'}")
        elif accion == "descarga":
            if not a.sin_pulso:
                self._anotar(f"{a.nombre}: tiene pulso, NO dar descarga")
            else:
                self._anotar(f"{a.nombre}: descarga aplicada", "critico")
                a.dar_descarga()
        elif accion == "entendido" and self.ventana_guia.clave:
            self._guia_oculta = self.ventana_guia.clave
        elif accion == "rutina_hecha":
            self._terminar_rutina(completada=True)
        elif accion == "rutina_posponer":
            self._terminar_rutina(completada=False)
        elif accion == "rutina_ahora":
            if guia_para(a, self.mision.entorno, self.mision.fase):
                self._anotar(f"{a.nombre}: hay una emergencia, la recomendación espera")
            else:
                self._nueva_rutina(a)
        self._marcar_botones()
        self._actualizar_lento()

    # --- recomendaciones de rutina ---

    def _nueva_rutina(self, a):
        """Muestra una recomendación de bienestar al tripulante seleccionado."""
        guia = self.recomendador.elegir(a)
        inicio = time.perf_counter()
        if guia.duracion:
            guia.estado = lambda: (f"Faltan {max(0, guia.duracion - (time.perf_counter() - inicio)):.0f} "
                                   f"segundos   ·   Estrés {a.estres:.0f} de 100")
        else:
            guia.estado = lambda: f"Estrés {a.estres:.0f} de 100   ·   Pulse Hecho al terminar"
        self._rutina = (a, guia, inicio)
        self._anotar(f"{a.nombre}: recomendación, {guia.titulo.lower()}")

    def _terminar_rutina(self, completada):
        if not self._rutina:
            return
        a, guia, _ = self._rutina
        self._rutina = None
        ahora = time.perf_counter()
        if completada:
            a.aliviar(guia.alivio)
            self._anotar(f"{a.nombre}: actividad completada, {guia.titulo.lower()}")
            self._t_rutina = ahora + SEGUNDOS_ENTRE_RECOMENDACIONES
        else:
            self._anotar(f"{a.nombre}: recomendación pospuesta")
            self._t_rutina = ahora + SEGUNDOS_ENTRE_RECOMENDACIONES / 2

    def _guia_rutina(self, a, emergencia):
        """Regresa la recomendación de rutina que toca mostrar, o None."""
        ahora = time.perf_counter()
        if self._rutina:
            tripulante, guia, inicio = self._rutina
            if emergencia or tripulante is not a:
                # si hay emergencia o cambian de tripulante, quitamos la recomendación
                self._rutina = None
                self._t_rutina = ahora + SEGUNDOS_ENTRE_RECOMENDACIONES / 2
                return None
            if guia.duracion and ahora - inicio >= guia.duracion:
                self._terminar_rutina(completada=True)
                return None
            return guia
        # solo molestamos al tripulante cuando está en reposo
        if (self.rutina_auto and not emergencia and not self.pausa and ahora >= self._t_rutina
                and self.mision.fase == "reposo" and self.state() != "iconic"):
            self._nueva_rutina(a)
            return self._rutina[1]
        return None

    def _alternar_rutina(self):
        self.rutina_auto = not self.rutina_auto
        self._t_rutina = time.perf_counter() + SEGUNDOS_PRIMERA
        self._anotar("Recomendaciones de rutina " + ("activadas" if self.rutina_auto else "desactivadas"))
        self._marcar_botones()

    def _cambiar_entorno(self, clave):
        self.mision.entorno.evento = clave
        self._anotar(EVENTOS_ENTORNO[clave])
        self._marcar_botones()

    def _cambiar_dias(self, dias):
        """Adelanta o retrasa la misión para ver la evolución de la pérdida ósea."""
        nuevo = self.mision.t_mision + dias * 86400
        if nuevo < 0:
            return
        self.mision.t_mision = nuevo
        for a in self.mision.tripulacion:
            a.actualizar_cronicos(nuevo, self.mision.entorno)
        self._anotar(f"Día de misión {int(nuevo // 86400)}")
        self._actualizar_lento()

    def _alternar_pausa(self):
        self.pausa = not self.pausa
        self._marcar_botones()

    def _alternar_sonido(self):
        self.sonido = not self.sonido
        self._marcar_botones()
        self._actualizar_lento()

    def _alternar_grabacion(self):
        if self.registro.activo:
            self.registro.cerrar()
            self._anotar("Grabación detenida")
        else:
            try:
                self.registro.iniciar()
                self._anotar("Grabación iniciada: " + os.path.basename(self.registro.ruta))
            except OSError:
                self._anotar("No se pudo iniciar la grabación", "critico")
        self._marcar_botones()

    def _anotar(self, mensaje, etiqueta=None):
        hora = formato_mision(self.mision.t_mision, con_dias=False)
        self.bitacora.configure(state="normal")
        self.bitacora.insert("1.0", mensaje + "\n", etiqueta or ())
        self.bitacora.insert("1.0", hora + "  ", "hora")
        if int(self.bitacora.index("end-1c").split(".")[0]) > 200:
            self.bitacora.delete("200.0", "end")
        self.bitacora.configure(state="disabled")

    def _cerrar(self):
        self.audio.cerrar()
        self.registro.cerrar()
        self.destroy()

    # --- trazos ---

    def _ondas_redimensionadas(self, _evento):
        # esperamos a que terminen de cambiar el tamaño para volver a dibujar
        if self._pendiente_ondas:
            self.after_cancel(self._pendiente_ondas)
        self._pendiente_ondas = self.after(120, self._componer_ondas)

    def _componer_ondas(self):
        self._pendiente_ondas = None
        c = self.lienzo
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 80 or h < 80:
            return
        a = self.mision.tripulacion[self.sel]
        total = sum(t[2] for t in self._TRAZOS)
        y = 0.0
        for trazo, (etiqueta, color, peso, base, amp, _) in zip(self.trazos, self._TRAZOS):
            alto = h * peso / total
            if y > 0:
                c.create_line(0, y, w, y, fill="#0d151f")
            c.create_text(10, y + 6, anchor="nw", text=etiqueta, fill=color, font=fuente(13, True))
            trazo.configurar(8, w - 8, y + alto * base, alto * amp)
            y += alto
        c.create_text(w - 10, 6, anchor="ne", text=f"{a.nombre}  ·  {a.rol}", fill=TENUE,
                      font=fuente(13))
        self._dt_muestra = SEGUNDOS_BARRIDO / self.trazos[0].n
        self._acum_muestras = 0.0

    # --- ciclo principal ---

    def _cuadro(self):
        ahora = time.perf_counter()
        dt = min(ahora - self._t_prev, 0.1)
        self._t_prev = ahora

        if not self.pausa:
            self.mision.avanzar(dt)
            sel = self.mision.tripulacion[self.sel]
            for a in self.mision.tripulacion:
                if a is not sel:
                    a.avanzar_ritmo(dt)
                    a.latido = False

            if self.trazos[0].tramos:
                self._acum_muestras += dt
                k = int(self._acum_muestras / self._dt_muestra)
                if k:
                    self._acum_muestras -= k * self._dt_muestra
                    muestras = [sel.muestrear(self._dt_muestra) for _ in range(k)]
                    for i, trazo in enumerate(self.trazos):
                        f = self._TRAZOS[i][5]
                        trazo.agregar([f(m[i]) for m in muestras])
            else:
                sel.avanzar_ritmo(dt)

            # contador Geiger: detecciones aleatorias según la radiación ambiental
            self._cps = cuentas_por_segundo(self.mision.entorno.tasa_radiacion)
            n = detecciones(self._cps * dt)
            if dt > 0:
                self._cpm += (n / dt * 60.0 - self._cpm) * min(1.0, dt / 1.5)
            self.p_riesgos.clic(n > 0)

            if sel.latido:
                sel.latido = False
                self.p_fc.latir(True)
                self.after(140, lambda: self.p_fc.latir(False))

        self.ventana_guia.animar(ahora)
        if ahora - self._t_lento >= 0.25:
            self._t_lento = ahora
            self._actualizar_lento()
        self.after(15, self._cuadro)

    def _actualizar_lento(self):
        ahora = time.perf_counter()
        m = self.mision
        e = m.entorno
        destello = int(ahora * 2.5) % 2 == 0

        al_entorno = evaluar_entorno(e)
        al_trip = [evaluar_tripulante(a) for a in m.tripulacion]

        # mensajes del modelo: pulso recuperado, respiración normalizada, etc
        hubo_avisos = False
        for trip in m.tripulacion:
            while trip.avisos:
                self._anotar(f"{trip.nombre}: {trip.avisos.pop(0)}")
                hubo_avisos = True
        if hubo_avisos:
            self._marcar_botones()

        # guía de actuación de cada tripulante; las graves avisan a toda la tripulación
        guias = [guia_para(trip, e, m.fase) for trip in m.tripulacion]
        for guia, lista in zip(guias, al_trip):
            if guia and guia.avisar:
                lista.append((CRITICO, "ayuda",
                              f"ALERTA A LA TRIPULACIÓN, necesita ayuda ({guia.titulo.lower()})"))
        self._registrar_alarmas(al_trip, al_entorno)

        # paneles del tripulante seleccionado
        a = m.tripulacion[self.sel]
        # si no hay emergencia, de vez en cuando sale una recomendación de rutina
        rutina = self._guia_rutina(a, guias[self.sel] is not None)
        self._mostrar_guia(a, guias[self.sel] or rutina)
        self._sonar(guias)
        self.p_estres.actualizar(a, destello)
        niv = niveles_por_parametro(al_trip[self.sel])
        nombre_ritmo, desfibrilable = a.ritmo
        medida = formato_mision(a.pni_instante or m.t_mision, con_dias=False)
        if a.sin_pulso:
            # paro: sin signos, todos los paneles en rojo
            tipo = "DESFIBRILABLE" if desfibrilable else "NO desfibrilable"
            self.p_fc.actualizar("--", f"{nombre_ritmo}\n{tipo}", CRITICO, destello)
            self.p_pni.actualizar("--/--", "Sin pulso", CRITICO, destello,
                                  destacado=("PAM --", CRITICO, False))
            self.p_temp.actualizar(f"{a.temp:.1f}", "", CRITICO, destello)
            self.p_spo2.actualizar("--", "Sin pulso", CRITICO, destello)
            self.p_fr.actualizar("0", "Sin respiración", CRITICO, destello)
        else:
            ev = a.extrasistoles_recientes
            ritmo = nombre_ritmo + (f"\nExtrasístoles: {ev}" if ev else "")
            self.p_fc.actualizar(f"{a.fc:.0f}", ritmo, niv.get("fc", 0), destello)
            # PAM = (PS + PD x 2) / 3, la marcamos con flecha y color cuando baja
            nivel_pam = niv.get("pam", 0)
            bajando = nivel_pam > 0 or a.tendencia_pam <= -3 or a.evento == "descompensacion"
            self.p_pni.actualizar(f"{a.pni_sis}/{a.pni_dia}", f"Medida {medida}",
                                  max(niv.get("pni", 0), nivel_pam), destello,
                                  destacado=(f"PAM {a.pam}", nivel_pam, bajando))
            self.p_temp.actualizar(f"{a.temp:.1f}",
                                   f"Piel {a.temp_piel:.1f}\nDif. {a.temp - a.temp_piel:.1f}",
                                   niv.get("temp", 0), destello)
            oxigeno = "\nCon oxígeno" if a.oxigeno else ""
            self.p_spo2.actualizar(f"{a.spo2:.0f}", f"Perfusión {a.perfusion:.1f} %{oxigeno}",
                                   niv.get("spo2", 0), destello)
            self.p_fr.actualizar(f"{a.fr:.0f}", f"Ciclo {60.0 / a.fr:.1f} s", niv.get("fr", 0), destello)

        # etapas de la descompensación en la bitácora
        for trip in m.tripulacion:
            previa = self._etapas.get(trip.nombre, "")
            if trip.etapa != previa:
                self._etapas[trip.nombre] = trip.etapa
                if trip.etapa:
                    self._anotar(f"{trip.nombre}: {trip.etapa.lower()}",
                                 "critico" if trip.etapa == "Estado crítico" else "alerta")
                else:
                    self._anotar(f"{trip.nombre}: estabilizado")

        self.p_oseo.actualizar(int(m.t_mision // 86400), a.perdida_osea,
                               densidad_global(a.perdida_osea),
                               riesgo_fractura(a.perdida_osea, e.aceleracion),
                               lesiones_probables(a.perdida_osea, a.dosis_alta))

        nivel_rad = niveles_por_parametro(al_entorno).get("rad", 0)
        self.p_riesgos.actualizar(e.tasa_radiacion, self._cpm, nivel_rad, a.dosis_evento, a.dosis,
                                  LIMITE_CARRERA, sintomas_probables(a.dosis_evento, e.tasa_radiacion),
                                  a.riesgos)

        for i, (tarjeta, trip) in enumerate(zip(self.tarjetas, m.tripulacion)):
            tarjeta.actualizar(trip, nivel_maximo(al_trip[i]), i == self.sel, destello)

        # lecturas del entorno
        niv_e = niveles_por_parametro(al_entorno)
        color = lambda clave: {0: TEXTO, ALERTA: AMBAR, CRITICO: ROJO}[niv_e.get(clave, 0)]
        en_eva = m.fase == "eva"
        self.lecturas["presion"][0].configure(text="Presión del traje" if en_eva else "Presión de cabina")
        self.lecturas["presion"][1].configure(text=f"{e.presion:.1f} kPa", fg=color("o2"))
        self.lecturas["o2"][1].configure(text=f"{e.pp_o2:.1f} kPa", fg=color("o2"))
        self.lecturas["co2"][1].configure(text=f"{e.co2:.1f} mmHg", fg=color("co2"))
        self.lecturas["temp"][1].configure(text=f"{e.temperatura:.1f} °C")
        self.lecturas["rad"][1].configure(text=f"{e.tasa_radiacion:.2f} mSv/h", fg=color("rad"))
        self.lecturas["dosis"][1].configure(text=f"{a.dosis:.3f} mSv", fg=color("rad"))
        self.lecturas["g"][1].configure(text=f"{e.aceleracion:.1f} g")

        self.et_reloj.configure(text="T+ " + formato_mision(m.t_mision))
        self.et_fase.configure(text=FASES[m.fase]["nombre"] + ("   ·   EN PAUSA" if self.pausa else "")
                               + ("   ·   GRABANDO" if self.registro.activo else ""))

        # aviso general: la alarma más grave de toda la tripulación y el entorno
        todas = [(n, "Entorno", msg) for n, _, msg in al_entorno]
        for trip, lista in zip(m.tripulacion, al_trip):
            todas += [(n, trip.nombre, msg) for n, _, msg in lista]
        self._pintar_aviso(todas, destello)

        if self.registro.activo and not self.pausa and ahora - self._t_registro >= 1.0:
            self._t_registro = ahora
            self.registro.escribir(m, al_trip)


    def _mostrar_guia(self, a, guia):
        """Muestra u oculta la ventana emergente con los pasos para el tripulante seleccionado."""
        clave = (a.nombre, guia.clave) if guia else None
        if self._guia_oculta and self._guia_oculta[0] == a.nombre and clave != self._guia_oculta:
            self._guia_oculta = None   # la situación cambió: se vuelve a avisar
        visible = guia is not None and clave != self._guia_oculta and self.state() != "iconic"
        if visible:
            self.ventana_guia.mostrar(guia, a)
        else:
            self.ventana_guia.ocultar()
        # el contador de respiración solo ayuda mientras está a la vista
        for trip in self.mision.tripulacion:
            trip.respiracion_guiada = visible and trip is a and guia.modo == "respiracion"

    def _sonar(self, guias):
        """Elige la alarma sonora: tono de paro según el ritmo, o llamada de ayuda."""
        if not self.sonido or self.pausa:
            self.audio.alarma(None)
            self.audio.geiger(False)
            return
        trip = self.mision.tripulacion
        en_paro = [t for t in [trip[self.sel]] + trip if t.sin_pulso]
        if en_paro:
            self.audio.alarma("desfibrilable" if en_paro[0].ritmo[1] else "no_desfibrilable")
        elif any(g and g.avisar for g in guias):
            self.audio.alarma("ayuda")
        else:
            self.audio.alarma(None)
        self.audio.geiger(self.mision.entorno.tasa_radiacion > UMBRAL_EVENTO)

    def _pintar_aviso(self, todas, destello):
        if not todas:
            fondo, tinta, texto = PANEL, VERDE, "Sin alarmas activas"
        else:
            todas.sort(key=lambda t: -t[0])
            nivel, origen, mensaje = todas[0]
            texto = f"{'CRÍTICO' if nivel == CRITICO else 'ALERTA'}   {origen}: {mensaje}"
            if len(todas) > 1:
                texto += f"   (+{len(todas) - 1})"
            if nivel == CRITICO:
                fondo, tinta = (ROJO_FONDO if destello else "#5c0b10"), BLANCO
            else:
                fondo, tinta = AMBAR, "#1a1200"
        self.aviso.configure(bg=fondo)
        self.icono_aviso.configure(bg=fondo)
        self.icono_aviso.itemconfigure(self.id_triangulo, outline=tinta)
        self.icono_aviso.itemconfigure(self.id_palo, fill=tinta)
        self.icono_aviso.itemconfigure(self.id_punto, fill=tinta, outline=tinta)
        self.et_aviso.configure(text=texto, bg=fondo, fg=tinta)

    def _registrar_alarmas(self, al_trip, al_entorno):
        """Anota en la bitácora las alarmas nuevas y las que se normalizan."""
        actuales = set()
        origenes = set()
        grupos = [("Entorno", al_entorno)] + [(a.nombre, l) for a, l in zip(self.mision.tripulacion, al_trip)]
        for origen, lista in grupos:
            for nivel, parametro, mensaje in lista:
                clave = (origen, parametro, nivel, mensaje.split(" (")[0])
                actuales.add(clave)
                origenes.add(origen)
                if clave not in self._alarmas_previas:
                    self._anotar(f"{origen}: {mensaje}", "critico" if nivel == CRITICO else "alerta")
        for origen in self._origenes_con_alarma - origenes:
            self._anotar(f"{origen}: valores normalizados")
        self._alarmas_previas = actuales
        self._origenes_con_alarma = origenes
