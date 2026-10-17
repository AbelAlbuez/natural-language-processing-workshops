# Clasificación de Discurso de Odio

Este proyecto debe clasificar discursos de odio en texto: **HS** (*Hate Speech*), **TR** (*Targeted*) y **AG** (*Aggressiveness*). El énfasis estará en el procesamiento y representación del texto para que los modelos clásicos puedan capturar mejor las señales de toxicidad.

### Reglas Generales

- Está permitido el uso de librerías comunes de NLP y ML, incluyendo: `NLTK`, `Scikit-learn`, `TensorFlow`, `PyTorch`, `Pandas`, `Numpy`.
- No está permitido el uso de transformers o modelos preentrenados, solo las libreria comunes de NLP y ML
- **Se espera un notebook claro y bien documentado, que describa**:
  - El procesamiento de los datos.
  - Las estrategias de preprocesamiento y representación de texto.
  - Los modelos y experimentos realizados.
- **El dataset de prueba no debe ser usado para entrenamiento.**
- El archivo de predicción debe respetar el formato definido en `submission.csv`.

## Data

El dataset contiene textos anotados con etiquetas de toxicidad.
El objetivo es predecir las columnas `HS`, `TR` y `AG` a partir del texto (`text`).

| Columna | Descripción |
|---------|-------------|
| `id`    | Identificador único del texto. |
| `text`  | El contenido del tuit o comentario. |
| `HS`    | Indica si hay discurso de odio (1 = sí, 0 = no). |
| `TR`    | Indica si el discurso está dirigido contra una persona o grupo (1 = sí, 0 = no). |
| `AG`    | Indica si el texto es agresivo (1 = sí, 0 = no). |

### 1. `Toxic_train.csv`

Contiene los textos de entrenamiento junto con sus etiquetas de toxicidad.

| id    | text | HS | TR | AG |
|-------|------|----|----|----|
| 20001 | Easyjet quiere duplicar el número de mujeres piloto… Verás tú para aparcar el avión | 1 | 0 | 0 |
| 20013 | @MaivePerez Llora te lo mereces por zorra | 1 | 1 | 1 |
| 20025 | Qué buen día para salir a caminar por el parque | 0 | 0 | 0 |

### 2. `toxic_test.csv`

Contiene los textos de prueba.
En Kaggle, las columnas `HS`, `TR` y `AG` están ocultas y se usarán solo para calcular la métrica final.

| id | text |
|----|------|
| 1  | El árbitro siempre favorece al mismo equipo, qué descaro total. |
| 2  | @usuario cállate, nadie te pidió tu opinión. |
| 3  | Orgulloso de mi equipo, excelente trabajo y dedicación. |

### 3. `submission.csv`

Archivo de ejemplo que muestra el formato que deben seguir los envíos.

| id | HS | TR | AG |
|----|----|----|----|
| 1  | 1  | 1  | 1  |
| 2  | 0  | 0  | 1  |
| 3  | 0  | 0  | 0  |
