# Checklist de validacion del research

## Verificado tecnicamente

- [x] input_rows: 708768.
- [x] input_checksum: SHA-256 coincide.
- [x] unique_ids: article_id unico.
- [x] date_range: Intervalo semiabierto Duque.
- [x] six_sources: Cinco medios principales y Cambio.
- [x] titles: 707553.
- [x] missing_not_derivable: Todos siguen rechazados por el parser de Kelly.
- [x] before_after_same_rows: Original y export tienen mismo corte y numero de filas.
- [x] global_frequencies: Reconteo exacto de tokens.
- [x] global_vocabulary: Vocabulario coincide.
- [x] event_Reforma tributaria_blu_radio: Keywords recontadas desde input.
- [x] event_Reforma tributaria_cambio: Keywords recontadas desde input.
- [x] event_Reforma tributaria_el_tiempo: Keywords recontadas desde input.
- [x] event_Reforma tributaria_la_republica: Keywords recontadas desde input.
- [x] event_Reforma tributaria_noticias_caracol: Keywords recontadas desde input.
- [x] event_Reforma tributaria_noticias_rcn: Keywords recontadas desde input.
- [x] event_Conflicto armado_blu_radio: Keywords recontadas desde input.
- [x] event_Conflicto armado_cambio: Keywords recontadas desde input.
- [x] event_Conflicto armado_el_tiempo: Keywords recontadas desde input.
- [x] event_Conflicto armado_la_republica: Keywords recontadas desde input.
- [x] event_Conflicto armado_noticias_caracol: Keywords recontadas desde input.
- [x] event_Conflicto armado_noticias_rcn: Keywords recontadas desde input.
- [x] event_Corrupcion_blu_radio: Keywords recontadas desde input.
- [x] event_Corrupcion_cambio: Keywords recontadas desde input.
- [x] event_Corrupcion_el_tiempo: Keywords recontadas desde input.
- [x] event_Corrupcion_la_republica: Keywords recontadas desde input.
- [x] event_Corrupcion_noticias_caracol: Keywords recontadas desde input.
- [x] event_Corrupcion_noticias_rcn: Keywords recontadas desde input.
- [x] best_k: Argmax coincide.
- [x] topic_terms_0: Terminos del modelo iguales al CSV.
- [x] topic_weights_0: Pesos del modelo iguales al CSV.
- [x] topic_terms_1: Terminos del modelo iguales al CSV.
- [x] topic_weights_1: Pesos del modelo iguales al CSV.
- [x] topic_terms_2: Terminos del modelo iguales al CSV.
- [x] topic_weights_2: Pesos del modelo iguales al CSV.
- [x] topic_terms_3: Terminos del modelo iguales al CSV.
- [x] topic_weights_3: Pesos del modelo iguales al CSV.
- [x] topic_terms_4: Terminos del modelo iguales al CSV.
- [x] topic_weights_4: Pesos del modelo iguales al CSV.
- [x] assignment_ids: Todos los IDs coinciden.
- [x] assignment_source: Medios alineados por ID.
- [x] assignment_date: Fechas alineadas por ID.
- [x] excluded_empty_bow: Topico -1 exactamente sin vocabulario util.
- [x] confidence_range: Probabilidades validas.
- [x] topic_counts: Conteos recalculados por IDs.
- [x] topic_proportions: Proporciones exactas, incluido -1.

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
