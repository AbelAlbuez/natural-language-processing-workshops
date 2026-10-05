# Entrega 2: corpus Duque

Analisis ejecutado sobre 708.768 registros, seis medios presentes y 707.553
titulos derivados de URL. No hay cuerpos HTML. Cambio aporta solo 98 titulos;
no es una sexta serie completa comparable. No se afirma deteccion validada de
sesgo ni que las keywords identifiquen el mismo acontecimiento.

## Resultados

- [Notebook ejecutado](entrega2.ipynb).
- [Informe LaTeX](../informe/entrega2.tex) y [PDF](../informe/entrega2.pdf).
- [Presentacion editable, 10 diapositivas](../informe/entrega2.pptx).
- [Resumen de metricas](resultados/resumen.json), [grilla LDA](resultados/lda_optimization.csv)
  y [pyLDAvis](resultados/lda_visualization.html).
- [Cobertura tematica](resultados/eventos_polemicos.csv), [casos temporales](resultados/casos_temporales.csv)
  y [ejemplos con URL](resultados/ejemplos_casos.csv).

Los resultados incluyen Zipf descriptivo, diversidad por titulo y agregada,
bigramas/trigramas depurados, tasas tematicas por medio, casos candidatos,
contrastes lexicos descriptivos y LDA. Los n-gramas no son pruebas de
significancia; tampoco lo es el log-odds descriptivo.

Se entrenaron K=3,5,7,10,15 sobre todos los 706.083 documentos con vocabulario
util, con diez pasadas, 50 iteraciones internas y semilla 42. No se uso una
muestra. K=5 obtuvo el mayor c_v de la grilla (0,35955). Su perplejidad de
entrenamiento no fue la minima: coherencia y perplejidad son criterios distintos.
Los 2.685 documentos sin vocabulario LDA reciben topico -1. Los modelos,
diccionario y corpus Matrix Market se conservan en resultados/modelos.

## Reproducir

Desde esta carpeta, con la imagen base de Kelly ya construida:

```bash
docker build -t duque-entrega2:local .
ROOT="$(cd .. && pwd)"
CORPUS="$ROOT/news-retrieval/dumps/kelly/natural-language-processing-workshops-corpus-v2/workshops/media-bias-detection/news-retrieval/exports/duque-candidatos.parquet"
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$ROOT:/workspace" -v "$CORPUS:/data/duque.parquet:ro" \
  -w /workspace/entrega2 -e PYTHONPATH=/workspace/entrega2 \
  duque-entrega2:local python analysis.py --input /data/duque.parquet \
  --topics 3 5 7 10 15 --passes 10
```

El ejecutor reutiliza modelos/checkpoints con el mismo corpus y parametros;
no mezcla checkpoints de otro input. Para cambiar normalizacion o entrenamiento,
usar otra carpeta con `--output`. `--stage textometry` calcula solo fases 1-3;
`--stage deliverables` regenera documentos desde resultados existentes, sin LDA.
Regenerar documentos reemplaza el notebook; volver a ejecutarlo para guardar
salidas. Las versiones efectivas y el checksum del input quedan en resultados.

La compilacion del informe usa `pdflatex` dos veces desde la carpeta informe.
Los datos originales se montan read-only y el analisis no se conecta a PostgreSQL.
pyLDAvis HTML referencia recursos web externos; el notebook conserva figuras
estaticas para revision sin red.

## Metodologia Y Validacion

La normalizacion de texto y stopwords usa el mismo tratamiento de tildes.
Se conservan actores y geografia. Yule K es `10000 * sum(f*(f-1))/N**2`;
el caso de un token no divide por cero. MSTTR agregado descarta segmentos
incompletos; TTR de titulos cortos tiene poco poder discriminante. La relacion
rango-frecuencia se ajusta descriptivamente, sin certificar una ley de potencia.

Los temas amplios son Reforma tributaria, Conflicto armado y Corrupcion. Las
ventanas concretas son candidatos de reforma/paro 2021, bombardeo/menores 2019
y Centros Poblados 2021, con URLs para comprobacion humana. Cada tasa usa el
numero de titulos disponibles de su medio/ventana; cohortes pueden solaparse.
Ausencia de coincidencias no significa ausencia de cobertura.

Nueve tests del nucleo pasaron y se ejecuto una prueba end-to-end sintetica sin
publicar datos sinteticos. El notebook se ejecuto con 30 celdas (15 de codigo).
Se verifican IDs, conteos, proporciones, JSON del notebook, imagenes y geometria
del PPT. Las diferencias de genero/archivo (programas de radio, emisiones y
notas escritas), las fechas mensuales y los proxies slug son limitaciones
centrales; faltan anotacion humana y texto publicado para estudiar framing.