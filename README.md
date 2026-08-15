# Natural Language Processing — Workshops

Repositorio de talleres del curso de Procesamiento de Lenguaje Natural (PLN), Maestria, cuarto semestre.

## Integrantes

| Nombre | Usuario GitHub | Rol |
|---|---|---|
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

## Estructura del repositorio

```text
natural-language-processing-workshops/
├── README.md
├── requirements.txt
├── .gitignore
└── workshops/
    └── 01-colombian-presidential-speeches/
        ├── README.md
        ├── notebook.ipynb
        ├── data/
        │   └── .gitkeep
        ├── figures/
        │   └── .gitkeep
        └── report/
            └── analysis.md
```

## Setup

1. Crear entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Descargar modelo de spaCy:

```bash
python -m spacy download es_core_news_md
```

4. Descargar recursos de NLTK:

```bash
python -m nltk.downloader punkt stopwords wordnet omw-1.4
```

## Indice de talleres

| Taller | Tema | Estado |
|---|---|---|
| 1 | Analisis de discursos presidenciales en Colombia | Pendiente |

## Flujo de trabajo Git

- Cada integrante trabaja en su propia rama con la convencion `feat/<tema>`.
- Los cambios se integran a `main` mediante Pull Request.
- Cada Pull Request debe tener al menos una revision aprobada antes del merge.
