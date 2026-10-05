# Replit: documentacion basada en el research

## Alcance

Los resultados son asociaciones y descripciones de proxies slug, no sesgo editorial validado. Hay cinco series principales y Cambio con 98 registros fechados en seis dias. No hay cuerpos HTML. Mostrar siempre denominadores y distinguir topico -1 de confianza baja. Replit no se desplego ni certifico en esta auditoria; los comandos Python se comprobaron localmente en Docker, no en el runtime de Replit.

## Opcion A: tablas livianas sin corpus completo

Subir DATA_INSIGHTS_TABLES.csv, research_metrics.json, RESEARCH_REPORT_ENTREGA2.md y figuras. No subir credenciales, .env ni dumps PostgreSQL. Verificar permisos/licencia antes de redistribuir datos. La tabla larga tiene section, metric, source_id, tema, topic_id, value, unit, n, low, high, method, status, source_file. Es apta para filtrar/graficar sin cargar 708.768 registros.

```bash
python -m pip install pandas matplotlib
```

Desde la carpeta que contiene los archivos:

```python
import pandas as pd
import matplotlib.pyplot as plt
table = pd.read_csv('DATA_INSIGHTS_TABLES.csv')
rates = table.loc[table['metric'].eq('keyword_rate_pct')]
print(rates[['source_id','tema','value','n','low','high']])
main = rates.loc[rates['source_id'].ne('cambio')]
pivot = main.pivot(index='source_id', columns='tema', values='value')
pivot.plot.bar(figsize=(10,5))
plt.ylabel('% de titulos del medio')
plt.title('Coincidencias de keywords; no prueba de sesgo')
plt.tight_layout()
plt.savefig('replit_event_rates.png',dpi=150)
```

No dividir estas tasas por la suma de otros temas ni aplicar chi-cuadrado sobre porcentajes. Si value de un p ajustado es cero, mostrar underflow y no probabilidad exactamente cero. low/high de rarefaccion son cuantiles de submuestras; los de Wilson y bootstrap tienen otros supuestos y no son intercambiables.

## Opcion B: reproduccion completa offline de noticias

Se necesita Python 3.12+, memoria recomendada de al menos 2-4 GB y almacenamiento para el Parquet original y resultados. No necesita PostgreSQL vivo, API keys, Docker ni scraping en Replit. Hay que subir los archivos locales: no se hizo commit/push y no se garantiza que esten en la rama remota. La opcion completa no es reproducible sin el Parquet y todos los sidecars del modelo K=5.

Mantener estructura media-bias-detection/entrega2 (codigo, resultados, research) y la copia Kelly. resultados/modelos debe incluir lda_k5.model, su state, id2word y expElogbeta; no solo el archivo principal. Conservar CSV originales, stopwords.json, config.json, resumen.json, document_topics.parquet y db_evidence.json. La ultima es evidencia capturada, no una conexion a la DB.

Desde media-bias-detection:

```bash
KELLY='news-retrieval/dumps/kelly/natural-language-processing-workshops-corpus-v2/workshops/media-bias-detection/news-retrieval'
python --version
python -m pip install --timeout 180 --retries 10 -r "$KELLY/requirements.txt" -r entrega2/requirements.txt
python -m pip install --no-deps --no-build-isolation "$KELLY"
python -m nltk.downloader stopwords
cd entrega2
python -m pytest -q tests/test_core.py
python research.py --input "../$KELLY/exports/duque-candidatos.parquet"
python research_report.py
```

La descarga inicial instala paquetes y stopwords; no descarga noticias. Guardar la copia exacta de los datos y las versiones de resumen.json. Los rangos minimos de requirements no son un lock: futuras actualizaciones pueden cambiar APIs. Si no se sube la estructura Kelly, instalar el paquete news-corpus por una via autorizada y suministrar --input con la ruta real. No sustituir el corpus por una muestra y reutilizar su resumen completo: la auditoria rechaza un checksum distinto.

## Reproducir localmente con Docker verificado

Desde media-bias-detection/entrega2, con duque-entrega2:local disponible:

```bash
ROOT="$(cd .. && pwd)"
KELLY="$ROOT/news-retrieval/dumps/kelly/natural-language-processing-workshops-corpus-v2/workshops/media-bias-detection/news-retrieval"
docker run --rm --network none --user "$(id -u):$(id -g)"   -v "$ROOT:/workspace" -v "$KELLY/exports/duque-candidatos.parquet:/data/duque.parquet:ro"   -w /workspace/entrega2 -e PYTHONPATH=/workspace/entrega2   duque-entrega2:local python research.py --input /data/duque.parquet
docker run --rm --network none --user "$(id -u):$(id -g)"   -v "$ROOT:/workspace" -w /workspace/entrega2   duque-entrega2:local python research_report.py
```

La evidencia SQL ya esta capturada en research/db_evidence.json. No cambies el original y no restaures un dump con --clean para ejecutar este research. Los cuatro outputs son RESEARCH_REPORT_ENTREGA2.md, REPLIT_DOCUMENTATION_FROM_RESEARCH.md, DATA_INSIGHTS_TABLES.csv y RESEARCH_VALIDATION_CHECKLIST.md, dentro de entrega2/research.

## Recomendaciones de interfaz

Mostrar: corte semiabierto, cinco medios principales, Cambio aparte, titulo_source, precision de fecha y n. Usar tasas por medio; etiquetar zero como ausencia de keywords, no ausencia de noticias. Mostrar V de Cramer junto a p. K=5 es mejor en la grilla con una sola semilla, no optimo universal. Distancias JS son de distribuciones de topicos, no ideologia. El HTML pyLDAvis usa recursos externos; las figuras PNG funcionan sin esas dependencias.

## Lo pendiente

Despliegue y pruebas reales en Replit, capacidad/timeout del plan cloud, etiquetas humanas, cuerpos HTML, fechas editoriales autenticadas, varias semillas LDA y comparacion temporal controlada Duque/Petro. No presentar una validacion tecnica local como aceptacion academica o validacion causal.
