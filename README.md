# N.A.C.H.O. - NASA Administration Crew Health Onboard

Simulador de signos vitales para astronautas.

Monitor biomédico simulado para el seguimiento continuo de una tripulación en
misiones espaciales. Todos los datos son generados por un modelo; no provienen
de sensores reales.

## Cómo ejecutarlo

```bash
python main.py
```

Requiere Python 3.10 o posterior. No necesita instalar nada adicional.

## Qué muestra

- Trazos en tiempo real del tripulante seleccionado: electrocardiograma
  (derivaciones I, II y III), onda de pulso y respiración.
- Valores numéricos: frecuencia cardiaca, presión arterial (medida cada 30 s),
  temperatura, saturación de oxígeno y frecuencia respiratoria.
- Resumen de los cuatro tripulantes; al pulsar una tarjeta se cambia de tripulante.
- Entorno: presión de cabina o traje, oxígeno respirable, CO2, temperatura,
  radiación, dosis acumulada y aceleración.
- Alarmas en dos niveles (alerta y crítico) con bitácora de eventos.

## Controles

| Grupo | Efecto |
| --- | --- |
| Fase de misión | Reposo, sueño, ejercicio, lanzamiento, actividad extravehicular y reentrada. Afecta a toda la tripulación. |
| Evento médico | Hipoxia, arritmia, hipertermia, estrés agudo o descompensación en el tripulante seleccionado. |
| Entorno | Fuga de presión, CO2 elevado o tormenta solar. Afecta a toda la tripulación. |
| Grabar datos | Guarda una fila por tripulante cada segundo en `registros/` (archivo CSV). |
| Sonido de alarma | Aviso sonoro mientras haya una alarma crítica. |

## Presión arterial media y descompensación

La presión arterial media se calcula como `PAM = (PS + PD x 2) / 3` y se muestra
en el panel de presión. Se marca con una flecha de descenso y cambia de color
cuando baja: alerta por debajo de 70 mmHg y crítico por debajo de 60 mmHg.

El evento "Descompensación" avanza durante unos 90 segundos en tres etapas
(compensando, descompensado y estado crítico): sube la frecuencia cardiaca, caen
la presión y la perfusión, la onda de pulso pierde amplitud y el
electrocardiograma muestra descenso del segmento ST, inversión de la onda T,
extrasístoles y, al final, bradicardia con complejos anchos. Al volver a
"Sin evento" el tripulante se recupera en unos 25 segundos.

## Salud ósea

Junto a los signos vitales hay un panel con la figura del cuerpo y el esqueleto
coloreado (de verde a rojo) según la pérdida de densidad ósea por microgravedad
de cada región. Incluye un indicador de densidad global, la pérdida por región y
una barra de riesgo de fractura. La pérdida depende de los días de misión y de
cada tripulante; los botones "- 30 días" y "+ 30 días" adelantan o retrasan la
misión para ver su evolución. Se avisa cuando la pérdida en cadera supera 10 %.

## Guías de emergencia paso a paso

Cuando el monitor detecta una emergencia en el tripulante seleccionado, aparece
una ventana semitransparente frente a los trazos con el título de la acción, una
frase que explica qué pasa, el dato que hay que vigilar y los pasos numerados.
Están escritas para tripulantes que no son médicos. Son material de prototipo y
no sustituyen los procedimientos médicos oficiales.

| Situación | Qué muestra |
| --- | --- |
| SpO2 baja | "Colóquese oxígeno" y botón "Oxígeno colocado" (la saturación sube) |
| Respiración rápida | Contador para respirar despacio hasta normalizarla |
| Respiración lenta | Contador para respirar profundo |
| Taquicardia / bradicardia | Qué hacer y cuándo pedir ayuda |
| Descompensación, infarto, evento cerebrovascular | Pasos y alerta sonora a toda la tripulación |
| Paro cardiaco | "SIN SIGNOS", todos los paneles en rojo, contador de compresiones y si el ritmo es desfibrilable |
| Hipertermia, hipotermia, arritmia, radiación, CO2 | Pasos correspondientes |

Ritmos de paro: fibrilación ventricular y taquicardia ventricular sin pulso son
desfibrilables (tono agudo alternado; "Dar descarga" puede recuperar el pulso,
mejor tras compresiones). Asistolia y actividad eléctrica sin pulso no son
desfibrilables (tono grave continuo; solo se recuperan con unos 40 segundos de
compresiones).

La radiación recibida en tormentas solares también reduce la densidad ósea, y el
panel de salud ósea lista las lesiones probables. El audio de la carpeta
`assests` suena mientras la radiación está elevada.

## Nivel de estrés

Debajo de los trazos hay un panel con el índice de estrés del tripulante (0 a
100), su nivel (bajo, moderado, alto o muy alto), las causas que más pesan en
ese momento y una gráfica de los últimos 3 minutos con las líneas de 40 y 70.
Cada tarjeta de tripulante muestra además una barra con su nivel.

El índice se apoya en las medidas que usan los estudios de estrés en vuelo
espacial y en misiones análogas:

| Marcador | Qué indica |
| --- | --- |
| Variabilidad cardiaca (RMSSD, ms) | Baja cuando sube el estrés |
| Índice de tensión de Baevsky | Nació en la medicina espacial; 50 a 150 es normal en reposo |
| Cortisol en saliva (nmol/L) | Sube con el estrés sostenido |

Cada botón aporta carga: lanzamiento, reentrada, actividad extravehicular,
eventos médicos, fuga de presión, CO2, tormenta solar, la emergencia de un
compañero y los días de aislamiento. A partir de 70 se avisa y aparece la guía
"Baje su estrés" con el contador de respiración. Los valores son simulados y
las fórmulas son aproximaciones para el prototipo.

## Recomendaciones de rutina

Cuando no hay emergencia y la tripulación está en reposo, el monitor invita de
vez en cuando al tripulante seleccionado a hacer una actividad corta (ventana
azul): respiración lenta, respiración en caja, anclaje 5-4-3-2-1, relajación
muscular, diario personal, tres cosas buenas, mirar la Tierra, cuidar las
plantas, hablar con alguien, estirarse, pausa de luz y agua, o un reto mental.
Con "Hecho" la actividad resta estrés durante un tiempo; "Ahora no" la pospone.
Si el estrés ya es moderado se priorizan las actividades que calman.

Se basan en lo que NASA describe para el riesgo de aislamiento y confinamiento
(diarios, luz para ordenar el sueño, cuidado de plantas, apoyo del equipo y la
familia) y en ejercicios de respiración y atención con respaldo en estudios.
"Recomendación ahora" muestra una al instante y "Rutina automática" las activa
o desactiva. En la demostración aparecen cada 75 segundos aproximadamente.

## Contador Geiger y síntomas probables

El panel del contador muestra la tasa de radiación en un medidor de aguja
(escala de 0.01 a 1000 mSv/h), las cuentas por minuto, la dosis del evento y la
dosis acumulada frente al límite de carrera de 600 mSv. Con "Sonido de alarma"
activo se oyen los chasquidos del contador.

Al activar "Tormenta solar" la tasa sube (mucho más en actividad extravehicular)
y el panel indica los síntomas probables según la dosis recibida en el evento:

| Dosis del evento | Síntomas probables |
| --- | --- |
| Menos de 50 mSv | Sin síntomas; buscar refugio |
| 50 a 250 mSv | Sin síntomas agudos; mayor riesgo de cáncer y vigilancia neurológica |
| 250 a 500 mSv | Descenso de linfocitos, fatiga leve |
| 500 a 1000 mSv | Náuseas, pérdida de apetito, fatiga |
| 1000 a 2000 mSv | Náuseas y vómito, fatiga marcada, caída de defensas |
| Más de 2000 mSv | Síndrome agudo de radiación |

NASA indica que la radiación espacial aumenta el riesgo de cáncer y daña el
sistema nervioso central; los rangos de síntomas agudos son los de la medicina
general de radiación, no cifras publicadas por NASA. Para que se vea en una
demostración, durante la tormenta cada segundo cuenta como dos minutos de
exposición.

## Riesgos de la misión

Seis indicadores medibles, uno por cada línea de investigación de NASA:

| Indicador | Qué se mide | Aviso |
| --- | --- | --- |
| Salud de la columna | Pérdida de músculo paraespinal (%) y aumento de estatura | 12 % o más |
| Inmunidad alterada | Linfocitos en sangre (x10³/µL); bajan con la radiación | Menos de 1.0 |
| Hemostasia venosa | Velocidad de flujo de la vena yugular (cm/s) | Menos de 7 |
| Biomarcadores del líquido espinal | Neurofilamento ligero en LCR (pg/mL) | Más de 900 |
| Presión de líquido cerebral | Presión intracraneal (mmHg); sube con el CO2 | Más de 20 |
| SANS | Engrosamiento de la retina junto al nervio óptico (µm) | 20 µm o más |

Dependen de los días de misión, del tripulante y del entorno. Las fórmulas son
aproximaciones para el prototipo, no modelos clínicos validados.

## Estructura

- `vitales/estres.py`: índice de estrés y sus marcadores.
- `vitales/rutina.py`: recomendaciones de rutina para el bienestar.
- `vitales/huesos.py`: modelo de pérdida ósea.
- `vitales/guias.py`: textos de las guías de emergencia.
- `vitales/sonido.py`: alarmas y audio del contador Geiger.
- `vitales/radiacion.py`: contador Geiger y síntomas por dosis.
- `vitales/riesgos.py`: indicadores de riesgo de la misión.

- `main.py`: punto de entrada.
- `vitales/modelo.py`: modelo fisiológico, entorno y catálogos de fases y eventos.
- `vitales/alarmas.py`: límites y evaluación de alarmas.
- `vitales/interfaz.py`: ventana del monitor.
- `vitales/registro.py`: grabación en CSV.
