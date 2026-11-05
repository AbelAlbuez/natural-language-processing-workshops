# Resumen ejecutivo — Agenda de cinco medios bajo Duque y Petro (LDA)

*5 de noviembre de 2026 · corpus `news_corpus` (dump 2026-10-04, slug procesado 2026-11-04)*

## Qué se hizo

1. **Se limpió el corpus** con el enfoque de slug: 1,73 M de URLs con titular
   reconstruido y sección, y 78.859 piezas que no son noticias marcadas
   (emisiones, loterías, pico y placa, dólar del día, caricaturas, publirreportajes).
   Detalle en `news-retrieval/docs/07-tratamiento-del-slug.md`.
2. **Se entrenó un único modelo LDA** para los dos gobiernos, con una muestra
   balanceada de 400.000 titulares (40.000 por medio y gobierno). Después se
   asignaron tópicos a las **1.573.421 noticias** de El Tiempo, Blu Radio,
   Noticias RCN, Noticias Caracol y La República.
3. **Se comparó la agenda**: qué parte de cada medio ocupa cada tópico en cada
   gobierno y cuánto cambió de Duque a Petro, descontando el cambio común a todos
   los medios (Δ relativo).

## Resultados principales

**1. El modelo mejora respecto a la Entrega 2, pero sólo 5 de 15 tópicos son fiables.**
K = 15 alcanza una coherencia c_v de 0,417 (0,36 en la Entrega 2). Al
reentrenarlo con otras semillas sólo se repiten 3 tópicos (Fútbol, Conflicto
armado, Gobierno–Petro–política internacional) y 2 de forma parcial (Sucesos,
Justicia). Con ~6 palabras útiles por titular el LDA es inestable; ajustar sus
parámetros no lo corrigió. Las conclusiones se limitan a esos 5 tópicos.

**2. La comparación entre gobiernos sí es robusta.** El Δ relativo calculado con
las tres semillas tiene correlación 0,87–0,89 y mantiene el signo en el 93 % de
los casos de tópicos robustos. **14 de 75** combinaciones medio × tópico cambian
de forma significativa (Holm < 0,05) y estable:

| Medio | Tópico | Duque → Petro | Δ relativo* |
|---|---|---|---|
| Noticias RCN | Fútbol | 9,3 % → 18,5 % | **+11,5 pp** |
| El Tiempo | Fútbol | 9,7 % → 7,3 % | −5,0 pp |
| Blu Radio | Fútbol | 8,7 % → 7,1 % | −3,8 pp |
| Noticias RCN | Gobierno, Petro y política internacional | 7,1 % → 6,2 % | −2,9 pp |
| Noticias RCN | Conflicto armado y orden público | 8,7 % → 7,1 % | −2,5 pp |
| Blu Radio | Conflicto armado y orden público | 8,5 % → 10,5 % | **+2,5 pp** |
| Noticias RCN | Sucesos (accidentes y muertes) | 7,5 % → 6,3 % | −2,2 pp |
| Blu Radio | Justicia y tribunales | 7,7 % → 6,7 % | −1,8 pp |
| Blu Radio | Sucesos (accidentes y muertes) | 7,2 % → 8,8 % | +1,7 pp |
| Noticias Caracol | Fútbol | 3,2 % → 3,5 % | −1,5 pp |
| El Tiempo | Sucesos (accidentes y muertes) | 6,4 % → 7,7 % | +1,3 pp |
| Blu Radio | Gobierno, Petro y política internacional | 6,5 % → 8,2 % | +0,9 pp |
| El Tiempo | Justicia y tribunales | 7,4 % → 7,1 % | −0,8 pp |
| El Tiempo | Conflicto armado y orden público | 6,4 % → 7,0 % | +0,7 pp |

\* Cambio del medio menos el cambio promedio de los otros cuatro, en puntos
porcentuales; IC 95 % por bootstrap de bloques mensuales (`resultados/deltas.csv`).

**3. El tópico de gobierno crece con Petro en cuatro de los cinco medios.** Sube en
El Tiempo (6,5 → 7,6 %), Blu Radio (6,5 → 8,2 %), Caracol (5,6 → 7,2 %) y La
República (7,4 → 9,1 %). **RCN es la excepción** (7,1 → 6,2 %), y también le
dedica menos espacio relativo al conflicto armado y a los sucesos.

**4. Blu Radio se desplaza hacia el orden público.** Es el medio que más aumenta
la cobertura de conflicto armado (+2,5 pp relativos; 10,5 % de su agenda con Petro)
y de sucesos, y el que más reduce justicia y tribunales.

**5. Las agendas de los medios se separan un poco con Petro.** La distancia media
entre las agendas de los cinco medios pasa de 0,180 a 0,204 (Jensen-Shannon).
RCN es el medio que más cambia respecto a sí mismo (0,139). La República es el
más distinto de todos en los dos gobiernos, por su perfil económico: los
tópicos de economía y empresas ocupan cerca del 30 % de su agenda, aunque los
dos son inestables entre semillas y esa cifra es sólo indicativa.

## Cautelas antes de citar estos resultados

- **Fútbol refleja el archivo, no necesariamente la línea editorial.** La sección
  de deportes pasa del ~1 % al 43–45 % de las URLs de RCN entre 2019–20 y
  2023–24, y baja en El Tiempo y Blu Radio. Los Δ de Fútbol siguen esa
  composición.
- **Agenda no es framing.** El LDA dice *de qué* se habla, no *cómo*. Ningún
  resultado de este análisis mide sesgo por sí solo.
- **Los titulares son reconstruidos** desde la URL (sin tildes, cifras ni
  puntuación) y en RCN 2018–2020 sólo se conoce el mes de publicación.

## Siguientes pasos recomendados

1. **Emparejar titulares del mismo hecho entre medios** (TF-IDF + embeddings
   multilingües, ventana de ±2 días). Es la base para pasar de agenda a encuadre.
2. Sobre esos eventos: **cobertura u omisión** de cada medio y **elección
   léxica** (*log-odds* con prior informativo) dentro del mismo hecho.
3. **Controlar por sección** al comparar tópicos entre gobiernos, para separar
   cambios del archivo de cambios editoriales.
4. Probar un **modelo de tópicos para textos cortos** (BERTopic sobre embeddings
   o GSDMM) y comparar su estabilidad con la de este LDA.

## Dónde está todo

- Código y cómo reproducir: [`README.md`](README.md) · `./run.sh all`
- Figuras (14, una por etapa): [`resultados/figuras/`](resultados/figuras/); la
  central es `12_delta_relativo.png`
- Tablas: `resultados/deltas.csv`, `participacion_medio_gobierno.csv`,
  `topic_robustness.csv`, `distancias_js.csv`
- Exploración interactiva de los tópicos: `resultados/lda_visualization.html`
