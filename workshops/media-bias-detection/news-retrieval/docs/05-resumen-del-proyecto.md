# El proyecto explicado sin tecnicismos

Para entender qué se hizo, por qué, y cómo seguir — sin necesidad de leer código.

Versión técnica: [`04-resumen-tecnico.md`](04-resumen-tecnico.md).
Para poner el corpus a funcionar: [`03-guia-del-equipo.md`](03-guia-del-equipo.md).

---

## 1. Qué queremos averiguar

La pregunta del proyecto es:

> ¿Los medios colombianos cuentan los mismos hechos de forma sistemáticamente
> distinta, y eso cambia según el gobierno de turno?

Un ejemplo de lo que buscamos. La misma protesta, dos titulares:

```
Medio A:  "Manifestantes exigen cambios al gobierno"
Medio B:  "Disturbios afectan la movilidad de la ciudad"
```

Mismo hecho. Uno pone el foco en la demanda, el otro en la molestia. Ninguno
miente. Esa diferencia es lo que queremos poder medir.

### Lo que decidimos NO hacer

Hay un atajo tentador: usar análisis de sentimiento y decir que las noticias
negativas sobre el gobierno indican un medio opositor. **Lo descartamos a
propósito.** Un atentado se cuenta en negativo en todos los medios; eso no dice
nada sobre su línea editorial. Confundir tono con parcialización es el error más
común en este tipo de trabajo.

En su lugar el corpus se diseñó para poder estudiar varias dimensiones por
separado: qué palabras se eligen, a quién se cita, qué se enfatiza, qué se omite
y cómo se enmarca cada hecho.

---

## 2. Qué se construyó

Un sistema que **recolecta noticias de forma ordenada y deja registro de todo**.

La diferencia con un scraper corriente está en el registro. De cada artículo
sabemos de dónde salió, quién lo encontró, cuándo, con qué búsqueda y qué tan
fiable es cada dato que guardamos. Eso permite que, meses después, cualquiera
pueda explicar cómo se construyó cualquier parte del corpus — que es un
requisito de un trabajo académico, no un lujo.

El proceso, de principio a fin:

```
1. Buscar        Se leen los índices que cada medio publica de su propio
                 archivo (mes a mes) y se obtiene la lista de artículos.

2. Ordenar       Se normalizan fechas y direcciones, se eliminan repetidos y
                 se asigna a cada artículo el gobierno vigente en su fecha.

3. Leer          Se abre cada artículo para obtener el titular real, la fecha
                 real y el texto.

4. Limpiar       Se quitan del texto los restos de la página web (botones,
                 marcas de publicidad) que no escribió ningún periodista.

5. Clasificar    Se etiqueta cada artículo por tema.

6. Guardar       Todo queda en una base de datos, exportable a un archivo
                 plano para analizar.
```

Cada paso se puede repetir sin rehacer los anteriores. Si mañana cambiamos la
lista de temas, se reclasifica todo el corpus **sin volver a descargar nada**.

---

## 3. Qué tenemos hoy

Tres medios — **El Tiempo, Noticias Caracol y Blu Radio** — en una ventana de
2013, con unos 17.000 artículos.

Es deliberadamente pequeño. La meta del proyecto son 20 años y diez medios, pero
la primera entrega sólo necesita demostrar que el proceso completo funciona de
punta a punta. El mismo sistema, sin cambios, sirve para ampliarlo.

Las cifras exactas y actualizadas están en `dumps/MANIFEST.md`.

---

## 4. Los tres descubrimientos que cambian lo que se puede concluir

Esta es la parte más importante del documento. Son problemas reales de los
archivos web que, si se ignoran, producen "hallazgos" que en realidad son
defectos del archivo.

### Descubrimiento 1 — Las fechas de los archivos mienten

Los índices que publican los medios traen una fecha, pero en varios casos es la
fecha en que el artículo se **modificó** (por ejemplo, al cambiar de sistema de
publicación), no en que se publicó.

En Blu Radio esto pasa en el **100 %** de los casos: artículos de enero de 2013
aparecen fechados en abril de 2016.

**Cómo lo resolvimos.** Cada artículo lleva una marca que dice qué tan fiable es
su fecha: si es exacta al día, si sólo conocemos el mes, o si no se sabe. Y
cuando sólo se conoce el mes y ese mes es de cambio de gobierno, **no le
asignamos gobierno**: elegir uno sería inventarse el dato.

Al abrir cada artículo recuperamos la fecha real, y eso corrige el problema para
la mayoría.

### Descubrimiento 2 — Algunos titulares no son titulares

Cuando la dirección de un artículo no dice de qué trata (por ejemplo,
`.../documento/CMS-16551020`), reconstruimos un título aproximado a partir de la
dirección. Sale sin tildes y con mayúsculas inventadas.

Si se mezclan esos títulos con los reales en un análisis de palabras, lo que se
mide es de dónde salió el título, no qué palabras usó el medio.

**Cómo lo resolvimos.** Cada título lleva marcado si es el publicado o una
reconstrucción. Y abrimos las páginas para conseguir los reales.

### Descubrimiento 3 — Buena parte del archivo no tiene el texto

El más importante, y el que más condiciona el análisis.

Al abrir los artículos de 2013 encontramos que muchas páginas de archivo **no
contienen la noticia escrita**. En esa época Caracol y Blu Radio publicaban
mucho vídeo y audio: la página conserva el titular y el reproductor, pero no hay
texto que analizar.

Qué proporción de cada medio conserva el texto completo:

| Medio | Página de archivo de 2013 | Artículos con texto |
|---|---|---|
| **El Tiempo** | la noticia completa | **99 %** |
| **Noticias Caracol** | mezcla de notas escritas y fichas de vídeo | 19 % en enero → 36 % en marzo |
| **Blu Radio** | mezcla de notas escritas y posts de audio | 10 % en enero → 21 % en marzo |

No es un fallo de nuestro sistema. Lo comprobamos mirando el código fuente de
las páginas: en esos casos **el texto no está ahí**. Y no es un corte limpio por
año: la proporción sube con el tiempo, ya se nota dentro del propio 2013, y
hacia 2018–2019 los tres medios publican mayoritariamente texto.

**Lo que significa, y es más sutil que "faltan datos".** Sí tenemos texto de
Caracol y Blu Radio en 2013 —unos 1.500 y 1.100 artículos— pero **no es una
muestra representativa**: son justamente las noticias que ese medio decidió
publicar escritas, no las que publicó en vídeo. Analizar ese grupo y decir "así
escribe Blu Radio" mide el subconjunto escrito, no al medio entero.

Por eso, para 2013, la comparación defendible entre los tres medios es sobre
**titulares y resúmenes**, que sí existen para todos. Para comparar el cuerpo de
las noticias conviene recolectar de 2019 en adelante. Es la limitación más
relevante del corpus hoy, y conviene decirla en cualquier informe.

---

## 5. Qué se puede hacer hoy con estos datos

**Sí se puede:**

- Comparar qué palabras usa cada medio en sus titulares.
- Comparar a qué temas le da espacio cada medio (en proporción, nunca en
  números absolutos: un medio con más artículos archivados parecerá cubrirlo
  todo más).
- Comparar a qué actores nombra cada medio y con qué frecuencia.
- Encontrar el mismo hecho contado por dos medios el mismo día y leer las dos
  versiones lado a lado. Esto ya funciona y da ejemplos reales:

```
Blu Radio         Ruth Marina Díaz Rueda, la primera presidenta de la Corte Suprema
Noticias Caracol  Ruth Marina Díaz, nueva presidenta de la Corte Suprema
```

  El mismo nombramiento. Uno destaca que es la primera mujer; el otro no. Eso
  es exactamente el tipo de diferencia que el proyecto quiere estudiar.

- Analizar el texto completo de El Tiempo por dentro.

**Todavía no se puede:**

- Comparar cómo cambia la cobertura entre gobiernos: la ventana cargada es muy
  corta.
- Analizar el cuerpo de las noticias de Caracol y Blu Radio en 2013: no existe.
- Decir qué medio es "más parcializado". Esa no es una pregunta que un corpus
  responda; se miden dimensiones concretas y se describen los patrones.
- Saber qué hechos cubrió un medio y otro ignoró: hace falta agrupar
  automáticamente los artículos por acontecimiento, que está pendiente.

---

## 6. Cómo retomar el trabajo

### Si sólo quieres ver los datos

Sigue [`03-guia-del-equipo.md`](03-guia-del-equipo.md). Son seis pasos y no hay
que descargar nada de los medios: el corpus viaja como un archivo que se carga
en minutos.

Después abre el notebook `03-analisis-del-corpus.ipynb`, que recorre los
análisis posibles explicando en cada uno qué filtro hay que aplicar para no
medir un defecto del archivo.

### Si quieres hacer avanzar el proyecto

En orden de utilidad:

1. **Ampliar a años más recientes** (2019 en adelante). Es lo que más valor
   añade y no requiere programar nada nuevo: son los mismos comandos con otras
   fechas. Desbloquea la comparación de textos completos entre los tres medios,
   que es la que motiva todo el proyecto.
2. **Agrupar artículos por acontecimiento**, para poder estudiar qué cubre cada
   medio y qué omite.
3. **Añadir más medios.** Hay diez configurados y verificados; sólo tres están
   recolectados.

Una advertencia práctica: recolectar lleva horas y se hace despacio a propósito,
para no saturar unos sitios que nos están dando su archivo gratis. Conviene
lanzarlo y dejarlo correr, no esperarlo sentado.

---

## 7. Las decisiones que se tomaron, en una lista

| Decisión | Por qué |
|---|---|
| Leer los índices de cada medio en vez de usar una API de noticias | La API candidata (GDELT) devolvía datos de otra época sin avisar y sólo funcionaba en el 38 % de los intentos |
| Separar la adquisición del análisis | Si construyéramos el corpus suponiendo cómo se mide la parcialización, sólo podríamos confirmar esa suposición |
| No borrar nunca nada, sólo marcarlo | Poder explicar después qué se descartó y por qué |
| Marcar la fiabilidad de cada fecha y cada título | Los archivos web tienen defectos; esconderlos produce conclusiones falsas |
| Guardar cuántos artículos ofreció cada medio cada mes | Una diferencia de cobertura puede ser una diferencia de archivado, y hay que poder distinguirlas |
| Descargar despacio y respetar `robots.txt` | Son archivos públicos que nos dan gratis; no se saturan |
| Compartir el corpus como archivo cargable | Reconstruirlo cuesta horas de peticiones; hacerlo en cada máquina es innecesario |
| No usar sentimiento como medida de parcialización | Tono y posicionamiento no son lo mismo |
