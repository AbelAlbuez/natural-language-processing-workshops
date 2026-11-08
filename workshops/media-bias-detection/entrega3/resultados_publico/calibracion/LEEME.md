# Calibración manual del emparejamiento (paso 2)

Sirve para medir qué tan seguido acierta el método que empareja titulares del
mismo hecho entre medios, y para elegir el umbral de similitud a partir de
datos y no a ojo.

## Para el equipo: dos personas en paralelo

Hay una planilla por persona:

- `planilla_persona_1.xlsx`: 135 parejas.
- `planilla_persona_2.xlsx`: 135 parejas.

1. Cada persona abre **su** planilla. La hoja **Instrucciones** explica las
   opciones y trae un ejemplo.
2. En la hoja **Anotación**, elijan para cada pareja una opción de la lista
   desplegable (celdas amarillas):
   - **Mismo hecho**
   - **Mismo tema / otro hecho**
   - **Distinto**
   - **No se puede saber**
3. **No comparen respuestas mientras anotan.** Las **60 parejas dobles** (filas
   azules, `doble = Sí`) están en las dos planillas a propósito: con ellas se
   mide si las dos personas entienden igual el criterio.
4. Las otras **150 parejas están repartidas 75 y 75**, sin repetir, y cada
   planilla tiene casos de todos los tramos de similitud.
5. **No abran `clave_no_abrir.csv`**: tiene la similitud de cada pareja y
   sesgaría la respuesta.
6. La hoja **Progreso** muestra cuánto falta.

Tiempo estimado: unos 30 segundos por pareja, ≈ 70 minutos por persona.

## Cómo se armó la muestra

- Se tomaron 30.000 titulares al azar del subcorpus de asuntos públicos, sólo
  con fecha exacta.
- Para cada uno y cada otro medio se buscó el titular más parecido en ±2 días
  (similitud coseno de embeddings multilingües). Se conservaron sólo las parejas
  **recíprocas**: cada titular es el más parecido del otro en el medio del otro.
  Es el mismo criterio con el que se arman los eventos.
- Se tomaron **30 parejas por tramo de similitud**: 0,60–0,65, 0,65–0,70, …,
  0,90–1,00. Son 7 tramos y 210 parejas en orden aleatorio, con el orden A/B
  también al azar.
- Se excluyen las 1.256 «plantillas masivas» que también excluye `eventos.py`:
  más de mil páginas «En vivo elecciones… en \<municipio\>» de El Tiempo
  publicadas el mismo día. Quedan 20.891 parejas recíprocas.
- Semilla 42. Se regenera con `python calibracion.py muestra` y
  `python calibracion.py dividir`. `python calibracion.py planilla` genera, en su
  lugar, un solo archivo para dos anotadores.

## Después de anotar

Guarden las dos planillas llenas en esta carpeta (con el mismo nombre) y corran:

```bash
python calibracion.py evaluar --personas resultados_publico/calibracion/planilla_persona_1.xlsx \
                                         resultados_publico/calibracion/planilla_persona_2.xlsx
```

Genera:

- `precision_por_tramo.csv`: proporción de «Mismo hecho» en cada tramo, con
  intervalo de Wilson.
- `precision_por_umbral.csv`: precisión de quedarse con las parejas ≥ cada
  umbral, ponderada por cuántas parejas hay de cada tramo en el corpus
  (`poblacion_tramos.csv`). La versión sin ponderar queda en
  `precision_por_umbral_sin_ponderar.csv`.
- `evaluacion.json`: umbral recomendado (el menor con precisión ≥ 90 %; se
  cambia con `--precision-objetivo`) y **kappa de Cohen** sobre las parejas
  dobles, en 4 clases y en binario «mismo hecho / no».

«No se puede saber» queda fuera del cálculo de precisión. Un kappa por debajo
de ~0,6 indicaría que las definiciones no son lo bastante claras y habría que
revisarlas antes de fijar el umbral.

## Resultado (noviembre de 2026)

Kappa 0,77 (mismo hecho sí/no) y 0,70 (4 clases). Precisión ponderada: 75 % con
umbral 0,75, **81 % con 0,80** y 93 % con 0,90. El equipo eligió **0,80** y los
eventos se rearmaron con ese umbral (ver el README de `entrega3`).
