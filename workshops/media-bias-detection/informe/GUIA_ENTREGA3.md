# Guía para terminar el informe final (entrega 3)

Ya hay un borrador completo que compila: [`entrega3.tex`](entrega3.tex) (PDF de
muestra: `entrega3-borrador.pdf`, 5 páginas). Tiene el mismo formato que la
entrega 2, con las figuras y cifras reales. La versión larga, con todos los
detalles, es [`../entrega3/INFORME_FINAL.md`](../entrega3/INFORME_FINAL.md):
úsenla como fuente cuando necesiten ampliar algo.

## 1. Empezar (15 min)

1. `git pull` en el repo.
2. **Compilar el borrador**, de una de estas dos formas:
   - **Overleaf:** suban la carpeta `informe/` y, al mismo nivel, la carpeta
     `entrega3/resultados_publico/` con su ruta (las figuras se leen desde
     `../entrega3/resultados_publico/`). Lo más fácil es subir el zip del repo
     con esas dos carpetas y poner `informe/entrega3.tex` como documento
     principal.
   - **Local con Docker** (desde `media-bias-detection/`):
     ```bash
     docker run --rm -u $(id -u):$(id -g) -v "$PWD:/w" -w /w/informe texlive/texlive:latest-medium \
       sh -c "pdflatex entrega3.tex && pdflatex entrega3.tex"
     ```
3. Abran el PDF y léanlo completo una vez **antes** de cambiar nada.

## 2. Repartir el trabajo (sugerencia para 4 personas)

| Persona | Secciones de `entrega3.tex` | Fuente para ampliar |
|---|---|---|
| A | Resumen, Introducción, Datos | `INFORME_FINAL.md` §1–2; `entrega3/README.md` § Datos |
| B | Métodos y Resultados: agenda | §3.1 y §4.1; `RESUMEN_EJECUTIVO.md`; `resultados_publico/comparacion_metodos.csv` |
| C | Métodos y Resultados: eventos, omisión, léxico y carga | §3.2–3.6 y §4.2–4.5; los `LEEME.md` de `omision/`, `lexico/` y `carga/` |
| D | Silver standard, coincidencias, Limitaciones y Conclusiones | §3.7, §4.6–4.7 y §5–8; `resultados_publico/silver/LEEME.md` |

Cada quien edita **sólo sus secciones**, para evitar conflictos en el `.tex`.

## 3. Qué revisar en cada sección

- **Lo que está en rojo** (`\todo{...}`) son pendientes. Antes de entregar,
  descomenten `\renewcommand{\todo}[1]{}` o borren cada uno.
- **Cifras:** cada número del borrador sale de un CSV. Si cambian algo, copien
  el valor del CSV, no de memoria.

  | Cifra | Archivo |
  |---|---|
  | Embudo del corpus | `entrega3/README.md` § Datos |
  | Estabilidad de los modelos | `resultados_publico/comparacion_metodos.csv` |
  | Δ relativo (BERTopic) | `resultados_publico/bertopic/deltas.csv` |
  | Calibración | `resultados_publico/calibracion/precision_por_umbral.csv` y `evaluacion.json` |
  | Eventos | `resultados_publico/eventos/eventos.json` |
  | Omisión | `resultados_publico/omision/` (CSV y `LEEME.md`) |
  | Personalización | `resultados_publico/lexico/` (CSV de formas de nombrar) |
  | Carga | `resultados_publico/carga/carga_medio_gobierno.csv` y `carga_gobierno.csv` |
  | Silver standard | `resultados_publico/silver/analisis/tasas_por_definicion.csv`, `diferencias_petro_duque.csv`, `validacion_indicadores.csv` y `silver_analisis.json` |

- **Figuras:** el borrador usa 8 de las 38 (01, 17, 12-BERTopic, 24, 29, 31, 36
  y 38). Si sobra espacio o el profesor pide más, las candidatas son:
  - `16_control_seccion.png`, para mostrar el efecto del control;
  - `eventos/figuras/20_sensibilidad_umbral.png`, para la calibración;
  - `carga/figuras/30_carga_medio_gobierno.png`;
  - `silver/analisis/figuras/37_silver_desfavorable.png`.
- **Redacción prudente:** describan («cubre más», «usa más»), no atribuyan
  intención («favorece», «ataca»). Carga ≠ sesgo y tópico ≠ encuadre.

## 4. Puntos que deben decidir como equipo

1. **Silver standard.** La planilla 2 la anotó un modelo de lenguaje, y así lo
   dicen el borrador (Métodos y Limitaciones) y las figuras 36 y 38. Si quieren
   que el κ sea entre personas, una segunda persona anota la planilla 2 (~2 h)
   o adjudica los 32 desacuerdos de `entrega3/resultados_publico/silver/adjudicacion.xlsx`.
   Después se corre:
   ```bash
   cd entrega3
   SCRIPT=silver.py ./run.sh - evaluar --adjudicacion resultados_publico/silver/adjudicacion.xlsx
   SCRIPT=silver_analisis.py ./run.sh -
   ```
   y se actualizan las cifras de §3.4, §4.4 y Limitaciones.
2. **Extensión:** si hay un límite de páginas, recorten primero las figuras de
   ancho completo (3, 7 y 8) a una columna, o pasen la tabla de coincidencias a
   un anexo.
3. **Formato:** si piden IEEE, cambien `\documentclass` por `IEEEtran` (el
   contenido no cambia).
4. **Presentación:** el orden del informe (agenda → selección → encuadre →
   silver standard → conclusión) sirve tal cual como guion de diapositivas, con
   una figura por diapositiva.

## 5. Antes de entregar (lista de chequeo)

- [ ] No queda texto en rojo (`\todo`).
- [ ] Todas las cifras coinciden con los CSV citados.
- [ ] Las figuras se leen impresas: tamaño de letra y leyendas.
- [ ] Las referencias citadas aparecen en la bibliografía, y no hay entradas
      sin citar.
- [ ] Los nombres y la afiliación están bien escritos (tildes incluidas, si
      corresponde).
- [ ] El PDF final queda como `informe/entrega3.pdf` y se sube al repo.
