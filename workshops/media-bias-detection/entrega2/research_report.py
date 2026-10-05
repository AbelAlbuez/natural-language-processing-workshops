import json
from pathlib import Path

import numpy as np
import pandas as pd


def table(frame, columns=None, limit=None):
    if columns:
        frame = frame.loc[:, columns]
    if limit:
        frame = frame.head(limit)
    def format_cell(value, column):
        if pd.isna(value):
            return "n/d"
        if isinstance(value, (bool, np.bool_)):
            return "si" if value else "no"
        if isinstance(value, (float, np.floating)):
            if column in {"p", "p_holm"}:
                return "<1e-300 (underflow)" if value == 0 else f"{value:.3e}"
            return f"{value:.6f}".rstrip("0").rstrip(".")
        return str(value).replace("|", "/").replace("\n", " ")
    header = "| " + " | ".join(map(str, frame.columns)) + " |\n"
    header += "| " + " | ".join("---" for _ in frame.columns) + " |\n"
    return header + "\n".join("| " + " | ".join(format_cell(value, column) for column, value in zip(frame.columns, values)) + " |" for values in frame.itertuples(index=False, name=None)) + "\n"


def generate(root):
    output = root / "research"
    results = root / "resultados"
    metrics = json.loads((output / "research_metrics.json").read_text())
    summary = json.loads((results / "resumen.json").read_text())
    evidence = json.loads((output / "db_evidence.json").read_text()) if (output / "db_evidence.json").exists() else {}
    def read(name, original=False):
        return pd.read_csv((results if original else output) / name)
    checks = read("audit_checks.csv")
    if not metrics["all_checks_passed"] or not checks["passed"].all():
        raise ValueError("No generar reporte con comprobaciones fallidas")
    coverage = read("input_coverage.csv")
    zipf = read("zipf_by_medium.csv")
    diversity = read("diversidad_por_medio.csv", True)
    rarefaction = read("diversity_equal_tokens.csv")
    month_difference = read("diversity_month_difference.csv")
    ngrams = read("ngrams_by_medium.csv")
    rates = read("event_rates.csv")
    event_tests = read("event_tests.csv")
    sensitivity = read("event_sensitivity_day.csv")
    insights = read("DATA_INSIGHTS_TABLES.csv")
    topics = read("topic_terms_verified.csv")
    topic_overlap = read("topic_overlap.csv")
    confidence = read("topic_confidence.csv")
    scores = read("lda_optimization.csv", True)
    centroid = insights.loc[insights["metric"].eq("js_distance_main_centroid"), ["source_id", "value", "n"]].sort_values("value")
    paired = insights.loc[insights["metric"].eq("paired_month_difference_pp"), ["source_id", "tema", "value", "n", "low", "high"]]
    original_rates = read("eventos_polemicos.csv", True).pivot(index="source_id", columns="tema", values="pct_medio").reset_index()
    conditional = pd.read_csv(output / "topic_proportions_assigned.csv", index_col=0)
    distances = pd.read_csv(output / "topic_distances.csv", index_col=0)
    audit, lda = metrics["audit"], metrics["lda"]
    before = audit.get("before", {})
    zero_ci = rates.loc[rates["source_id"].eq("cambio"), ["tema", "count", "total_titles", "wilson_low_pct", "wilson_high_pct"]]
    chunks = evidence.get("cambio_chunks") or []
    chunk_range = f"{min(record['period_start'] for record in chunks)} a {max(record['period_start'] for record in chunks)}" if chunks else "sin evidencia de checkpoints"
    term_groups = pd.DataFrame([{"topic": topic, "terms_top10": ", ".join(group["word"])} for topic, group in topics.groupby("topic")])
    closest = min((distances.loc[first, second], first, second) for first in distances.index if first != "cambio" for second in distances.columns if second != "cambio" and first < second)
    low_percent = 100 * lda["assigned_low_confidence"] / summary["lda"]["documentos_lda"]
    page = []
    def add(title, body):
        page.append(f"## {title}\n\n{body.strip()}\n")
    add("I. Resumen ejecutivo", f"""
Este research audita **{summary['articulos']:,} registros** del corte Duque, entre {summary['desde']} y {summary['hasta']}, frente a su Parquet de entrada, evidencia SQL del origen y resultados publicados localmente. Hay seis medios presentes, pero cinco series principales y solo 98 registros de Cambio. Se completaron **{metrics['checks']} verificaciones automaticas** y se generaron contrastes nuevos sin reentrenar LDA, descargar articulos ni modificar PostgreSQL.

**Tres hallazgos comprobados:**

1. La integridad tecnica se sostiene: IDs, fechas, frecuencias, keywords y parametros/asignaciones del modelo coinciden con sus fuentes. Los titulos pasaron de {before.get('titles', 'n/d')} en el original a {summary['con_titulo']:,} en el export, siempre proxies `slug`. Cambio es una ventana de seis dias del inventario, no una muestra de cuatro anos.
2. Existen asociaciones entre medio y coincidencia tematica bajo el contraste condicional: p-valores Holm pequenos, pero **V de Cramer entre 0,015 y 0,049**. La magnitud es pequena y los supuestos de independencia estan comprometidos por el archivo; no es evidencia causal ni una medicion de sesgo.
3. K=5 gana la grilla por coherencia con margen {lda['coherence_gap_next']:.6f} frente a K={lda['runner_up_k']}. Se distinguen **{lda['no_assignment']:,} excluidos sin vocabulario** y **{lda['assigned_low_confidence']:,} asignados de confianza <0,3**. La relacion confianza-cobertura de vocabulario es minima (Spearman {lda['confidence_vocab_spearman']:.4f}).

**Dos limites centrales:** todo el texto es reconstruccion de URL, sin cuerpos HTML ni anotacion de framing; las fuentes tienen cobertura temporal, volumen, fechas y formatos desiguales. **Conclusion:** se pueden reportar diferencias descriptivas y asociaciones condicionadas, no confirmar ni descartar sesgo editorial, intencion politica o una agenda comun.

Este documento tiene **17 bloques de lectura con saltos sugeridos de pagina**. La extension impresa efectiva depende del renderizador; no se presenta una paginacion de Markdown como medicion fisica de 17 paginas.
""")
    add("II.1 Metodologia: fuentes y cortes", f"""
El origen es `news-corpus-unificado/news_corpus`; el analisis se construyo en `news_duque_work`, aislado del original. Se copiaron ambos agostos completos como candidatos y luego se exporto el corte **inicio inclusivo 2018-08-07, final exclusivo 2022-08-07**. Esta auditoria lee la exportacion final, no consulta una base viva durante los calculos.

{table(coverage)}

La tabla demuestra el numero de registros y el rango **almacenado**, no la fecha editorial autentica ni la completitud de la cobertura. El export tiene **{audit['month_precision']:,} fechas month** y **{audit['non_duque_assignment']} asignaciones presidenciales distintas de duque o ausentes dentro del corte de fecha**. No sustituir `government_id` por un filtro de fecha sin explicar esa diferencia.

`title_source` contiene slug y ausente; no hay sitemap/extracted en este export. No hay cuerpo HTML. Son proxies lexicos: se perdieron tildes, puntuacion y posibles cambios de titular. El parquet tiene checksum **`{metrics['input_sha256']}`**. Las tablas originales de Entrega 2 permanecen intactas; el research escribe en otra carpeta.

Provenance de fuentes: `db_evidence.json` es una consulta de solo lectura; `input_coverage.csv`, `audit_checks.csv` y `research_metrics.json` son verificaciones reproducibles. La captura SQL no equivale a comprobar los sitios actuales.
""")
    add("II.2 Metodologia: procesamiento y contrastes", r"""
Se reutiliza la tokenizacion exacta: minusculas, tildes normalizadas, palabras alfabeticas, longitud mayor de dos, stopwords espanolas y verbos de reporte. Se conserva geografia/actores. La igualdad de stopwords se comprobo frente al archivo original. Los n-gramas se forman dentro del titulo despues de retirar stopwords, no sobre frases originales intactas.

TTR = tipos/tokens. MSTTR promedia segmentos **completos de 50 tokens** y descarta el resto. Yule K = `10000*sum(f*(f-1))/N**2`; no se confunde con Simpson. La rarefaccion usa 100 submuestras aleatorias sin reemplazo de 10.000 tokens, semilla 42: sus cuantiles describen variacion del procedimiento, no un intervalo poblacional de diversidad del medio.

Para temas se contrastan **cinco medios x dos estados (keyword si/no)** por cada tema. Cada articulo entra una vez en cada contraste; los temas pueden solaparse entre contrastes. Se usan conteos crudos, Pearson chi-cuadrado sin correccion Yates, diagnostico de esperados, Holm para tres pruebas y V de Cramer. No se usa una tabla 5x3 de temas solapados como si fueran categorias excluyentes, ni porcentajes truncados a enteros.

Para sensibilidad temporal se emplea bootstrap circular de bloques mensuales de longitud 3, 1.000 remuestreos, semilla 42. Las parejas maximo/minimo se eligieron despues de mirar las tasas; los intervalos son exploratorios, no contrastes confirmatorios preespecificados. El contraste LDA principal usa conteos de topico dominante entre documentos asignados de los cinco medios, excluyendo -1.

Supuestos no garantizados: articulos independientes, archivo representativo, mediciones temporales correctas y ausencia de dependencias por programas repetidos. Tests y p-valores no reparan estos problemas de diseno.
""")
    add("III.1 Textometria: Zipf por medio y outliers", f"""
El global se reproduce exactamente: **{summary['textometry']['tokens']:,} tokens**, **{summary['textometry']['vocabulario']:,} tipos**, r={summary['textometry']['zipf_pearson_r']:.6f}, pendiente={summary['textometry']['zipf_slope']:.6f}, R2={summary['textometry']['zipf_r2']:.6f}. El ajuste utiliza rangos 10-10.000 con frecuencia mayor de uno; no se extrapola toda la cola.

{table(zipf, ['source_id', 'tokens', 'vocabulario', 'pearson_r', 'slope', 'r2', 'hapax'])}

Los cinco medios principales muestran linealidad log-log parecida; Cambio usa solo 476 tokens y 36 rangos ajustados, con pendiente/R2 diferentes. No afirmar que se comprobo Zipf en todos los medios con el mismo poder.

![Ajuste por medio](figuras/zipf_by_medium.png)

**r=-1 no es una hipotesis regular de potencia pura** para un Fisher-z ordinario: es una frontera singular. Ademas, rango y frecuencia estan ordenados por construccion. No se realiza una prueba de significancia contra -1 ni se interpreta p de correlacion como certificacion de Zipf. Harian falta ajuste de distribucion, umbral, bondad de ajuste simulada y comparacion con alternativas, atendiendo dependencias de tokens.

Residuos descriptivos extremos del ajuste, no outliers editoriales confirmados:

{table(read('zipf_residuals.csv'), ['palabra', 'frecuencia', 'rank', 'residual_log'], 10)}
""")
    add("III.2 Diversidad: controlar el numero de tokens", f"""
Los TTR agregados no se pueden comparar causalmente sobre tamanos tan diferentes. Cambio parece extraordinariamente diverso por tener solo 476 tokens; no se incluyo en las submuestras de 10.000.

{table(diversity, ['source_id', 'tokens', 'ttr_agregado', 'msttr_50_agregado', 'ttr_titulo_media'])}

{table(rarefaction, ['source_id', 'budget', 'repetitions', 'ttr_mean', 'q025', 'q975', 'status'])}

![TTR con tamanos iguales](figuras/diversity_equal_tokens.png)

La rarefaccion no conserva secuencia ni agrupacion de documentos: controla presupuesto de tokens, no genero, agenda o independencia. Su orden no coincide necesariamente con MSTTR: son medidas diferentes. No se sostiene la afirmacion de superioridad lexica del 35% de La Republica.

Comparacion mensual pareada de MSTTR, sobre meses comunes de las cinco series:

{table(month_difference)}

El intervalo de bloques excluye cero en esta pareja exploratoria. El resultado describe regularidad del indicador en el archivo; no demuestra cual medio tiene mejor escritura, ni una diferencia de framing. La seleccion post hoc de la pareja y longitud de bloque fija limitan su lectura inferencial.
""")
    add("III.3 N-gramas: globales y especificos de medios", f"""
Top diez bigramas y trigramas publicados, contrastables con tokens:

{table(read('bigrams_top100.csv', True), limit=10)}

{table(read('trigrams_top50.csv', True), limit=10)}

No atribuir esas secuencias a todos los medios. Al desglosar se observan patrones de programacion/emision y otras diferencias de formato. Una secuencia posterior a stopwords tampoco garantiza adyacencia en el titular editorial.

{table(ngrams.loc[ngrams['size'].eq(2)].groupby('source_id', sort=True).head(3), ['source_id', 'ngram', 'count', 'count_per_1000_titles'])}

La tasa por mil titulos facilita escaneo, pero repeticiones de un nombre de programa no equivalen a noticias distintas del mismo hecho. El codigo no filtra automaticamente esos formatos. Una mejora seria requiere catalogar programa/audio/video/noticia escrita y reanalizar una poblacion homogenea; quitar palabras a posteriori solo porque estorban puede ocultar evidencia del sesgo de archivo.
""")
    add("III.4 Temas: cobertura y denominadores", f"""
Se reprodujeron exactamente los 18 conteos medio/tema de Entrega 2. El denominador es el total de titulos disponibles de cada medio, no la suma de matches de tres temas. Los porcentajes no tienen que sumar 100 y los temas pueden solaparse.

{table(original_rates)}

La Republica registra mayor tasa tributaria; RCN/Blu registran mayor tasa del tema amplio de conflicto; Blu registra mayor tasa de keywords de corrupcion. Se habla de **coincidencias**, no de coverage completa ni postura editorial. `violencia`, `fraude` e `impuesto` son palabras amplias con falsos positivos y negativos plausibles.

![Tasas tematicas](figuras/event_rates.png)

Sensibilidad al restringir fecha day (se muestra Reforma tributaria; el CSV contiene los tres temas):

{table(sensitivity.loc[sensitivity['tema'].eq('Reforma tributaria')])}

Esta sensibilidad no autentica day: parte procede de lastmod dentro del mes. Es una restriccion tecnica, no una auditoria independiente de publicaciones. No hay anotacion de precision/recall de la recuperacion por keywords.
""")
    add("III.5 Temas: significancia condicionada y efecto", f"""
Contrastes principales sobre los cinco medios con series grandes:

{table(event_tests, ['tema', 'chi2', 'dof', 'p', 'p_holm', 'cramers_v', 'n', 'expected_min', 'asymptotic_cells_ok'])}

Todos los esperados superan cinco. Bajo las condiciones del modelo, se rechaza independencia medio/match en los tres temas despues de Holm. Los V pequenos (0,015-0,049) y el gran N explican por que p-valores diminutos no significan efecto sustantivo grande. Un cero computacional de p es underflow; no se presenta como probabilidad exactamente cero.

No afirmar que las asociaciones son "aleatorias" porque sean pequenas, ni que son sesgo editorial porque sean significativas. El contraste no controla el programa, el periodo, la seleccion del sitemap ni el acontecimiento. La dependencia entre noticias tambien hace que la precision estadistica sea demasiado optimista.

Sensibilidad de diferencias porcentuales con meses pareados y bloques de longitud 3:

{table(paired)}

Las medias mensuales dan igual peso a cada mes y por eso no son iguales a diferencias de las tasas globales ponderadas por volumen. Las parejas fueron elegidas post hoc; sus bandas son descriptivas. Cambio se excluye del contraste principal; su comparacion Fisher es exploratoria y sus Wilson se interpretan solo como ejercicio condicional al modelo binomial, no representatividad real.
""")
    add("III.6 LDA: seleccion de K y coherencia", f"""
Se verifico el argmax de coherencia de la tabla y se cargo el modelo K=5. Los cinco entrenamientos originales usaron 10 pasadas, semilla 42, 50 iteraciones internas y todos los documentos con vocabulary util; este research no los reentreno.

{table(scores)}

La diferencia de c_v entre K=5 y el segundo K={lda['runner_up_k']} es **{lda['coherence_gap_next']:.6f}**. Hay un ganador numerico de esa grilla, pero no se midio variabilidad por semillas, particiones o bootstrap; no puede decirse que la diferencia este estadisticamente validada. K=3 gana perplejidad de entrenamiento, mientras K=15 tiene un deterioro fuerte en esa metrica.

![Compromiso entre criterios](figuras/lda_tradeoff.png)

El c_v no es exactitud ni porcentaje de documentos bien clasificados. La perplejidad base2 se deriva de un bound de entrenamiento, no de una prueba held-out. La interpretacion de K=5 debe ser exploratoria, condicionada por los titulos cortos, el vocabulario elegido y los generos mezclados.

Para estabilizar: varias semillas por K, alineacion de topicos entre semillas, coherencia por tema, evaluacion held-out y revision humana. No se publica una etiqueta academica de topico como ground truth.
""")
    add("III.7 LDA: terminos e interpretabilidad", f"""
Los terminos y sus pesos coinciden con los del modelo guardado, no se inventaron etiquetas economia/educacion/seguridad:

{table(term_groups)}

El topico 0 incorpora programacion/fechas; el 1 pandemia y noticias generales; el 2 politica nacional/internacional mezclada; el 3 movilidad/video/deportes; el 4 actores politicos/deportivos y casos. Son lecturas orientativas de top-words, no clasificaciones verificadas por un experto.

Solapamiento entre pares de topicos:

{table(topic_overlap)}

Jaccard top10 describe palabras compartidas; el overlap de probabilidades suma minima masa por termino y va de cero a uno. No es una prueba de redundancia ni una distancia editorial. Nombres como Colombia aparecen en varios topicos por decision de conservar geografia. Separar topicos exige leer documentos de alta y baja probabilidad, no solo top-words.

Los ejemplos verificables de Entrega 2 y `low_confidence_examples.csv` permiten esa revision. No se revisaron manualmente todos los articulos ni se anotaron etiquetas verdaderas en este research.
""")
    add("IV.1 Diferencias entre medios y agrupacion", f"""
Distribucion de topico dominante **condicionada a documentos asignados**, distinta del denominador que incluye -1 en la tabla original:

{table((100 * conditional).reset_index())}

![Proporciones condicionadas](figuras/topics_assigned_heatmap.png)

No es una distribucion uniforme cercana al 20% para cada medio. Un chi-cuadrado de cinco medios x cinco topicos obtiene chi2={lda['topic_test']['chi2']:.3f}, df={lda['topic_test']['dof']}, V={lda['topic_test']['cramers_v']:.6f} y p numericamente subdesbordado. Esto describe una asociacion condicionada al modelo aprendido; no mide sesgo ni agenda comun.

El modelo fue entrenado con documentos de esos mismos medios. La dependencia del topico asignado respecto al entrenamiento y el archivo invalida cualquier lectura causal del contraste. Cambio se observa aparte, no se usa para la asociacion principal por su ventana de seis dias.
""")
    add("IV.2 Distancias, outliers y clusters descriptivos", f"""
Se usa distancia Jensen-Shannon base 2 entre distribuciones de topico dominante entre asignados. Distancia cero significa distribuciones iguales en ese resumen; no titulares iguales ni misma postura. Se eligio linkage promedio para describir proximidad, no para validar una segmentacion de medios.

{table(distances.reset_index())}

La pareja principal mas cercana es **{closest[1]} / {closest[2]}**, distancia **{closest[0]:.6f}**. Cambio esta mucho mas lejos, pero su distancia refleja una ventana minuscua y tardia, no una singularidad editorial demostrada.

Distancias al centro ponderado por documentos asignados de los cinco medios principales:

{table(centroid)}

![Agrupacion de medios](figuras/media_dendrogram.png)

Caracol y La Republica tienen mayor distancia al centro que otros medios principales en este modelo. No se usaron silhouette, estabilidad de clusters, semillas alternativas ni labels externos; no presentar el dendrograma como descubrimiento de bloques ideologicos. Las correlaciones de perfiles de eventos se apoyan en solo tres temas, por lo que son insuficientes para inferir clusters robustos.
""")
    add("IV.3 Documentos excluidos y confianza", f"""
**Sin asignacion:** {lda['no_assignment']:,}, exactamente los documentos cuyo bag-of-words queda vacio con el diccionario LDA. **Asignados pero confidence <0,3:** {lda['assigned_low_confidence']:,}, **{low_percent:.2f}% de los asignados**. No sumar ambos y llamarlos "sin topico dominante": los segundos si tienen argmax.

{table(confidence)}

Confianza media entre asignados: **{lda['assigned_mean_confidence']:.6f}**. Spearman confianza/cobertura de palabras conocidas: **{lda['confidence_vocab_spearman']:.6f}**; confianza/numero de tokens conocidos: **{lda['confidence_length_spearman']:.6f}**. La primera asociacion es practicamente nula, la segunda es negativa y limitada; no sostienen una explicacion causal de baja confianza por falta de vocabulario.

El umbral 0,3 es una convencion exploratoria para K=5, cuyo uniforme es 0,2. Confianza es maxima masa posterior, no probabilidad de clasificacion correcta ni calibracion frente a etiquetas verdaderas. No se verifico que el dominante de cada documento sea semanticamente correcto.

Se revalidaron los IDs, medios, fechas, conteos y -1 contra el input y el diccionario. Esta es integridad de asignaciones persistidas, no validacion predictiva. Los cuarenta ejemplos menos confiados estan en `low_confidence_examples.csv`, con URL e informacion de tokens para lectura posterior.
""")
    add("V.1 Limites de cobertura: Cambio, fechas y titulos", f"""
En el inventario completo Cambio registra **{audit['cambio_global'].get('articles', 'n/d'):,} articulos**, desde {audit['cambio_global'].get('first_date')} hasta {audit['cambio_global'].get('last_date')}, y cero fechados antes de agosto de 2022. La captura tiene **{len(chunks)} checkpoints**, {chunk_range}. El subconjunto Duque guarda 98, del {audit['cambio_start']} al {audit['cambio_end']}.

Esa interseccion entre cobertura del dump y corte explica el n pequeno. No se encontro un filtro que eliminara titulos por esas tres keywords; las keywords solo se aplican despues sobre todos los 98. Tampoco se puede determinar sin sondeo real si el indice no tenia archivo anterior, si la corrida se limito a Petro o si una migracion altero fechas. La configuracion declara archivo desde 2021, lo que es distinto de haberlo recolectado.

Los registros de Cambio usan `sitemap:lastmod` en su provenance. Por tanto **los seis dias son fechas almacenadas**, no seis dias de publicaciones autenticas verificadas. `completed` y `coverage=completa` son estados del proveedor, no un censo certificado de toda la historia del sitio.

{table(zero_ci)}

Con cero matches sobre 98, el limite Wilson superior es aproximadamente 3,77% para cada tema bajo modelo binomial. No equivale a una estimacion representativa porque la ventana no es aleatoria. Los cero no prueban omision. [Los 98 titulos y URLs](cambio_titles.csv) permiten comprobar directamente el conjunto; sus otros actores y temas no fueron convertidos en supuestas posturas politicas.
""")
    add("V.2 Limites de medicion e inferencia", f"""
Hay **{audit['normalized_duplicate_rows']:,} filas que comparten titulo normalizado con al menos otra fila**. Eso no las vuelve automaticamente duplicados de noticias: un programa puede repetir texto de URL o varios hechos pueden compartir titular. Si se usan como observaciones independientes, se sobredimensiona precision.

Los proxies slug pierden puntuacion, tildes y versiones editoriales; nombres de programas o fechas dominan vocabulario. No hay cuerpo para citas, actores en contexto, seleccion de fuentes o omisiones. Un titulo con keyword puede ser falso positivo; sin keyword puede tratar exactamente el mismo tema. El diccionario LDA elimina terminos raros, algunos actores y documentos completos.

La fecha de precision month no basta para distinguir acontecimientos del mismo dia, y day puede seguir siendo lastmod. Los tests de software no validan procedencia editorial. La inferencia causal requiere un diseno de comparacion de hechos verificados y control de archivo, formatos y tiempo.

No se midio intencion editorial, postura politica ni framing anotado. No se puede afirmar "no hay sesgo" por falta de evidencia, ni "hay sesgo" por p pequeno. No se confirmo Zipf como ley de potencia, ni estabilidad LDA por semillas, ni representatividad de Cambio. Intervalos Wilson y de bootstrap son condicionales al mecanismo elegido, no reparan cobertura faltante.

El research tampoco hizo validacion externa de sitios, evaluacion held-out ni despliegue Replit. Esta separacion entre prueba tecnica e interpretacion sustantiva debe mantenerse en presentaciones y UI.
""")
    add("VI. Conclusiones y recomendaciones", """
**Se puede afirmar:** integridad tecnica del corpus y de los resultados auditados; titulos mayoritariamente slug; Cambio es una subventana tardia; diferencias de tasas de keywords con efectos pequenos bajo el contraste condicional; medidas de diversidad sensibles al presupuesto de tokens; K=5 gana coherencia de esa grilla; perfiles tematicos no uniformes; exclusiones y confianza baja son fenomenos distintos.

**No se puede afirmar:** sesgo editorial confirmado o ausente; agenda comun; clasificacion correcta de todos los documentos; superioridad de diversidad del 35%; ausencia de noticias en Cambio; bloques ideologicos a partir de dendrogramas o intencion politica a partir de una palabra.

**Prioridades siguientes:**

1. Seleccionar pares de acontecimientos con documentos reales y anotacion humana, no solo keywords.
2. Recuperar titulares publicados/cuerpos en una submuestra balanceada por medio, mes y formato, respetando disponibilidad y robots.
3. Auditar fechas de posesion y lastmod; tratar por separado day/month/gobierno incierto.
4. Repetir LDA con varias semillas, revisar estabilidad y medir coherencia/evaluacion fuera de entrenamiento.
5. Analizar series temporales con controles de formato; comparar Duque/Petro solo en ventanas comunes y corpus igualmente procesados.
6. En Replit mostrar valores, denominadores, intervalos y limites, con Cambio apartado y controles de scope; nunca titular un grafico como "sesgo detectado".

Los entregables se mantienen locales. No se ejecuto commit ni push. La guia adjunta distingue un dashboard liviano de tablas verificadas de la reproduccion completa, que necesita datos/modelos disponibles y un entorno Python compatible.
""")
    add("Anexo. Evidencia, validacion y trazabilidad", f"""
**Checksum de entrada:** `{metrics['input_sha256']}`.

**Evidencia SQL:** [db_evidence.json](db_evidence.json), solo lectura. **Auditoria:** [audit_checks.csv](audit_checks.csv), {metrics['checks']} checks aprobados. **Metricas completas:** [DATA_INSIGHTS_TABLES.csv](DATA_INSIGHTS_TABLES.csv), 90 registros en formato largo, y [research_metrics.json](research_metrics.json).

La auditoria detecto una falsa discrepancia del lector CSV: el token literal `nan`, con una aparicion, se interpretaba como nulo. Se preservaron palabras con `keep_default_na=False` y el reconteo exacto paso. Tambien se adapto factorize a pandas 3 usando un array, sin cambiar el muestreo.

Los helpers tienen 14 tests de software aprobados. El notebook/PDF/PPT originales ya estaban generados: este research no los presenta como validacion editorial independiente. El PPT no fue renderizado en PowerPoint y Replit no se desplego. El paquete de research no reentrena ni modifica resultados originales.

Fuentes metodologicas de referencia: Entman (1993), framing; Blei, Ng y Jordan (2003), LDA; Clauset, Shalizi y Newman (2009), evaluacion de distribuciones de potencia; Holm (1979), ajuste secuencial; Wilson (1927), intervalos de proporcion. Se emplean como orientacion metodologica, no como validacion externa de este corpus.

Los hallazgos se recomputan mediante `research.py`; los documentos se regeneran con `research_report.py`. Para cambiar reglas, diccionario, datos o ventanas, usar otra carpeta y no mezclar tablas viejas con nuevas. Las hipotesis futuras deben especificarse antes de elegir parejas o thresholds.
""")
    heading = "# Deep Research de Entrega 2\n\nFecha: 2026-10-05. Investigacion local reproducible; sin crawling ni despliegue cloud.\n\n"
    (output / "RESEARCH_REPORT_ENTREGA2.md").write_text(heading + '\n<div style="page-break-after: always;"></div>\n\n'.join(page), encoding="utf-8")
    guide = """# Replit: documentacion basada en el research

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
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$ROOT:/workspace" -v "$KELLY/exports/duque-candidatos.parquet:/data/duque.parquet:ro" \
  -w /workspace/entrega2 -e PYTHONPATH=/workspace/entrega2 \
  duque-entrega2:local python research.py --input /data/duque.parquet
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$ROOT:/workspace" -w /workspace/entrega2 \
  duque-entrega2:local python research_report.py
```

La evidencia SQL ya esta capturada en research/db_evidence.json. No cambies el original y no restaures un dump con --clean para ejecutar este research. Los cuatro outputs son RESEARCH_REPORT_ENTREGA2.md, REPLIT_DOCUMENTATION_FROM_RESEARCH.md, DATA_INSIGHTS_TABLES.csv y RESEARCH_VALIDATION_CHECKLIST.md, dentro de entrega2/research.

## Recomendaciones de interfaz

Mostrar: corte semiabierto, cinco medios principales, Cambio aparte, titulo_source, precision de fecha y n. Usar tasas por medio; etiquetar zero como ausencia de keywords, no ausencia de noticias. Mostrar V de Cramer junto a p. K=5 es mejor en la grilla con una sola semilla, no optimo universal. Distancias JS son de distribuciones de topicos, no ideologia. El HTML pyLDAvis usa recursos externos; las figuras PNG funcionan sin esas dependencias.

## Lo pendiente

Despliegue y pruebas reales en Replit, capacidad/timeout del plan cloud, etiquetas humanas, cuerpos HTML, fechas editoriales autenticadas, varias semillas LDA y comparacion temporal controlada Duque/Petro. No presentar una validacion tecnica local como aceptacion academica o validacion causal.
"""
    (output / "REPLIT_DOCUMENTATION_FROM_RESEARCH.md").write_text(guide, encoding="utf-8")
    checklist = "# Checklist de validacion del research\n\n## Verificado tecnicamente\n\n"
    checklist += "\n".join(f"- [x] {row.check}: {row.detail}." for row in checks.itertuples())
    checklist += """

- [x] Catorce tests del nucleo y estadistica aprobados en el entorno Docker.
- [x] Chi-cuadrado sobre conteos crudos 5x2 por tema; esperados >5, Holm3 y V de Cramer.
- [x] Rarefaccion a 10.000 tokens, Cambio excluido por solo 476 tokens.
- [x] Bootstrap temporal de bloques y denominadores mensuales explicitados.
- [x] Distancias JS y agrupacion descriptiva; exclusion de -1 del denominador condicionado.
- [x] Evidencia SQL del original obtenida sin escrituras; research offline sin reentrenar LDA.

## Limites conocidos, no validados sustantivamente

- [ ] Independencia entre articulos: hay titulos repetidos y programas; p e intervalos son condicionales.
- [ ] Representatividad de Cambio: solo seis dias del inventario; no certificado archivo historico completo.
- [ ] Fechas editoriales autenticas: day/lastmod no son equivalentes; hay precision month.
- [ ] Titulares publicados/cuerpos HTML y validacion humana de framing.
- [ ] Precision/recall de keywords y verificacion del mismo acontecimiento.
- [ ] Estabilidad de K por semillas, validacion held-out y calibracion de confianza.
- [ ] Certificacion de ley de potencia/Zipf: no realizada por correlacion log-log.
- [ ] Inferencia de intencion/postura politica o existencia/ausencia de sesgo: no realizada.
- [ ] Clusters ideologicos o agenda comun: no demostrados por el dendrograma o topicos.
- [ ] PowerPoint renderizado en el editor: no realizado; validacion estructural previa solamente.
- [ ] Despliegue y ejecucion real en Replit: guia preparada, no probado en cloud.
- [ ] Publicacion GitHub: no se ejecutaron commit ni push.

## Siguiente puerta de validacion

Anotar una muestra balanceada de acontecimientos con texto publicado, autenticar fechas,
controlar formatos y probar varias semillas/particiones antes de formular hallazgos sobre sesgo.
"""
    (output / "RESEARCH_VALIDATION_CHECKLIST.md").write_text(checklist, encoding="utf-8")
    print(f"RESEARCH DOCS GENERADOS: {len(page)} bloques paginados; {len(checks)} checks; outputs en {output}")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parent)