# Pool final de prueba del RAG

Archivo principal: `pool_final.xlsx` (hojas Preguntas, Resumen, Instrucciones, Ejemplos, Listas). Reúne las dos versiones que subiste y suma 53 preguntas nuevas.

## Estado actual (94 filas)

| Tipo | verificada | borrador | por_verificar | descartada |
|---|---:|---:|---:|---:|
| factual | 11 | 25 | 0 | 0 |
| interpretativa | 3 | 7 | 0 | 1 |
| comparativa | 5 | 10 | 0 | 2 |
| sin_evidencia | 9 | 0 | 0 | 2 |
| adversarial | 4 | 6 | 0 | 0 |
| temporal | 4 | 6 | 0 | 0 |
| **total** | **37** | **54** | **0** | **5** |

- **verificada (30):** entran al gold (`gold.jsonl`). La evidencia de cada una la comprobé contra el texto del documento.
- **borrador (54):** la evidencia también la comprobé contra el texto (salvo 8 filas T cuyos documentos no tengo, ver abajo), pero falta que una persona las lea. Cuando las revises, cambia `origen` a `llm_revisado` (las S) y `estado` a `verificada`.
- **por_verificar (7):** S68, S71, S72, S73, S74 y tus dos preguntas T12 y T13 (sin_evidencia por comprobar, ver más abajo).
- Las preguntas nuevas (S22–S74) van con `split = dev` (para ajustar el RAG), salvo las sin_evidencia, que van con `test` porque son pocas; S01–S21 y las T van con `test`.

## Lo que corregí en tus filas T

**Errores que habrían hecho fallar la conversión o la validación:**
- `estado` vacío en todas las T: ninguna habría entrado al gold.
- `documentos_relevantes` con comas, tildes invertidas ` y texto pegado ("(2025-06-10). Bluesky: …"); ids terminados en punto (T09, T10); un id repetido (T04) y uno que no estaba (bluesky_3mukdplrtl72n).
- `evidencia_literal` de 400 a 1.360 caracteres, con varias frases de distintos documentos pegadas (T01–T07). Ahora cada frase queda en su documento y se separan con `||`. Lo adapté en el convertidor y en el validador (ver abajo).
- T11 no tenía documento. T26 era comparativa con un solo documento: la pasé a temporal.
- T24: la evidencia omitía el emoji de bandera y no coincidía; la recorté antes del emoji. T07: "olima" por "Tolima".

**Campos incompletos o mal anotados:** `origen` vacío (T04), `dificultad` vacía (T06), `palabras_busqueda` con coma o espacios (T07, T25), "altamar" (T06), criterios cortados (T08), respuestas de referencia que decían otra cosa que el criterio (T01, T05, T06, T10), faltas de ortografía en preguntas y respuestas.

**Qué quedó en cada T:** verificadas (11): T03, T04, T06, T07, T08, T09, T10, T22, T24, T25, T26 (y T11 como borrador). En borrador (8): T01, T02, T05, T23, T27, T28, T29, T30, porque sus documentos no están en los textos que tengo; la prueba definitiva es `validar_gold` con tu corpus (abajo). T11 sigue sin documento.

## Mejoras al convertidor y al validador

`evidencia_literal` admite varias frases separadas por `||`. Con una sola frase, debe estar en todos los documentos (como antes). Con varias, cada frase debe estar en algún documento y cada documento debe tener al menos una. Esto es lo natural en las comparativas: una frase por fuente. Los archivos actualizados están en `paquete_pool_final.zip`.

## Las preguntas nuevas (S22–S74)

Temas nuevos respecto a lo anterior: presupuesto de Ambiente 2026–2027, leyes de humedales, NDC 2035, caza de ballenas en Noruega, Festival Mundial de Salsa de Cali, decálogo del Caribe, castores en Norfolk y Gales, especies nuevas (puercoespín, rana, árbol, polilla), Fondo de Restauración de la Naturaleza del Reino Unido, Planning and Infrastructure Bill, COP30 y pueblos indígenas, créditos de carbono, COP17 de desertificación, ley europea de restauración de 2023.

Reparto de las 53 (S22–S74): 19 factuales, 7 interpretativas, 7 comparativas, 6 temporales, 6 adversariales y 8 sin_evidencia. Las 45 con documento tienen evidencia comprobada contra el texto; las sin_evidencia tienen su señuelo anotado en `notas`.

Importante: son borradores míos (`origen = llm_generada`). Hasta que las leas, no son gold. Dos dudas que anoté en notas: S33 (el nombre Coendou vossi está con letra cursiva Unicode en el post) y S52 (comparativa de dos hechos distintos).

## Cambios tras traer_documentos.py (S65–S74)

- **S65, S66, S67: verificadas como sin_evidencia.** Los pocos documentos que contienen sus palabras son de otros temas (tarifas de agua, jagua azul, Canal del Dique, expedición Deep Arctic, misión comercial a Asia). Las leí por la cabecera (el archivo recorta cada texto a 1.800 caracteres); si quieres máxima certeza, ábrelas completas con `--max-chars 0`.
- **S69 y S70 dejan de ser sin_evidencia:** el corpus sí dice que la COP18 de desertificación será en Egipto, y que Colombia adoptó la estrategia climática Colombia E2050 (neutralidad de carbono a 2050, Ley 2169 de 2021). Las convertí en factuales (borrador).
- **S68 y S71:** salieron 73 y 11 documentos y no pude descartar que alguno responda; quedan por comprobar con palabras más estrechas. Nuevas hipótesis: S72 (bosque primario perdido en 2026), S73 (visitantes de la Zona Verde de la COP17), S74 (ratificaciones del Tratado de Alta Mar en diciembre de 2026).
- Resultado: sin_evidencia pasa de 1 a 4 verificadas; con S68 y S71–S74 confirmadas llegarías a 9.

- **T12 y T13 (tuyas):** el vestido de Anne Hathaway en los Óscar 2025 y el barrio más cool de Latinoamérica en 2026. Las agregué como sin_evidencia (`origen = manual`, `split = test`) y corregí el nombre ("Ane Hethaway"). Con ellas, tus sin_evidencia manuales son 2 de 6–8.

## Lo que falta para que el pool sea completo

1. **Tus preguntas manuales siguen incompletas por tipo.** Faltan sin_evidencia (0 de 6–8), adversarial (2 de 4–6) y temporal (2 de 3–4). Los huecos T12–T21 sirven para eso. Ideas de sin_evidencia con señuelo conocido: bosque primario perdido en Colombia en 2026 (señuelo: −17 % de 2025); hectáreas por incendios en Colombia en 2025 (señuelo: Tolima 2026, 27 mil ha); precio al que Chevron compró créditos de carbono; ministro de Ambiente en 2027 (señuelo: Fabio Arjona, 2026); presupuesto de Parques Nacionales 2027. Adversarial: "¿Por qué la ministra Irene Vélez revocó la reserva de La Baja?" (fue el ministro Arjona) y "¿Por qué fracasó la reanudación de la COP16 en Roma?". Temporal: ratificaciones del Tratado de Alta Mar al 10 de junio de 2025 (49 de 60). Están desarrolladas en `fichas_T.md`.
2. **Corrección de mis fichas anteriores.** El presupuesto del Ministerio de Ambiente sí está en el corpus (790 mil millones para 2027, 1,24 billones para 2026), igual que COP17, El Niño y las especies nuevas: no sirven como sin_evidencia. Las usé como factuales, interpretativas o adversariales.
3. **Prueba con tu corpus completo.** Yo comprobé las evidencias contra los 110 textos que me has pasado, no contra los 146.923 documentos. El validador lo hace por ti (paso 3).
4. **Indexar** los documentos del gold en Milvus (`ingest --ids-file`) antes de medir. El script `scripts/evaluar.py` todavía no existe.

## Pasos en PowerShell

`scripts/` va dentro de la imagen de Docker y `data/` está montada. Por eso los scripts nuevos se ejecutan desde `data/`, sin reconstruir la imagen.

**1. Instalar el paquete (desde la carpeta del proyecto)**
```
Expand-Archive "$HOME\Downloads\paquete_pool_final.zip" -DestinationPath . -Force
```
```
Copy-Item scripts\gold_excel.py data\gold_excel.py -Force
```
```
Copy-Item scripts\validar_gold.py data\validar_gold.py -Force
```

**2. Convertir la plantilla en gold** (debe decir 30 líneas)
```
docker compose exec api python data/gold_excel.py convertir --entrada data/gold/pool_final.xlsx --salida-dir data/gold
```

**3. Validar contra el corpus real** (debe dar `errores: 0`)
```
docker compose exec api python data/validar_gold.py --gold data/gold/gold.jsonl --corpus data/documentos_rag.parquet --minimo 1
```

**4. Traer documentos para comprobar sin_evidencia**
```
docker compose exec api python data/traer_documentos.py --solo S68,S71,S72,S73,S74,T12,T13 --k 8 --max-chars 700
```
Sale `data/documentos_para_verificar.md`. Con `--estados por_verificar,borrador --relevantes` incluye también los borradores y sus documentos citados.

**5. Exportar los archivos de prueba para el RAG**
```
docker compose exec api python data/exportar_pool.py --entrada data/gold/pool_final.xlsx --salida-dir data/gold
```
Escribe `pool_completo.jsonl` (todo con su estado) y `preguntas.jsonl` (solo las preguntas, para alimentar al RAG). Con `--solo-verificadas`, `preguntas.jsonl` contiene solo el gold.
