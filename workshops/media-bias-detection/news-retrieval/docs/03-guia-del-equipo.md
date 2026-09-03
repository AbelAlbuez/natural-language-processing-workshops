# Guía del equipo — cargar el corpus y empezar a analizarlo

Esta guía es para quien llega al proyecto y quiere **el corpus ya construido**.

No hay que ejecutar la adquisición. Recolectar y extraer costó unas 17.000
peticiones a los medios a menos de 1 req/s: horas de reloj, y carga sobre unos
sitios que nos están dando su archivo gratis. Por eso el corpus viaja como un
volcado de la base que se restaura en minutos.

```text
clonar → docker compose up → restaurar el dump → comprobar → analizar
```

---

## Paso 1 — Requisitos

| | |
|---|---|
| Docker | para el Postgres y, si quieres, para JupyterLab |
| Python 3.12+ | sólo si vas a usar la CLI o los notebooks fuera de Docker |
| [uv](https://docs.astral.sh/uv/) | gestor de entornos; `pip` también sirve |

Comprueba que Docker está arriba antes de nada:

```bash
docker info >/dev/null && echo "Docker OK"
```

Si falla, abre Docker Desktop y espera a que arranque. (Es el fallo más común:
un contenedor detenido produce errores de conexión que parecen del código.)

---

## Paso 2 — Clonar y configurar

```bash
git clone git@github.com:AbelAlbuez/natural-language-processing-workshops.git
cd natural-language-processing-workshops/workshops/media-bias-detection/news-retrieval

cp .env.example .env
```

Abre `.env` sólo si el puerto **5433** ya está ocupado en tu máquina; en ese
caso cambia `DB_PORT`. No hay credenciales que pedir: la base es local.

---

## Paso 3 — Levantar Postgres

```bash
docker compose up -d
```

Comprueba que el contenedor está sano antes de seguir:

```bash
docker ps --filter name=news-corpus-db
```

Debe decir `healthy`. Si dice `starting`, espera unos segundos.

---

## Paso 4 — Restaurar el corpus

```bash
./scripts/restore-db.sh
```

El script espera a que Postgres acepte conexiones, restaura y **al terminar
imprime un recuento por medio**. Compáralo con [`dumps/MANIFEST.md`](../dumps/MANIFEST.md):
si cuadra, ya tienes el corpus completo.

Detalles que conviene saber:

- Es **idempotente**. El dump se restaura con `--clean --if-exists`, así que
  puedes volver a lanzarlo sobre una base que ya tenía datos y quedará
  exactamente como el dump. No hace falta borrar nada a mano.
- **No necesitas `alembic upgrade head`.** El dump trae el esquema y la tabla
  `alembic_version`, de modo que las migraciones quedan alineadas solas.
- Restaurar en otra base: `DB_NAME=mi_copia ./scripts/restore-db.sh` (créala
  antes con `createdb`). Útil para probar sin tocar la tuya.

---

## Paso 5 — Comprobar desde la CLI

```bash
uv venv --python 3.12
uv pip install -e ".[dev,export]"
source .venv/bin/activate

news-corpus status      # bloques recolectados y total de artículos
news-corpus profile     # radiografía: qué se puede analizar y qué no
```

`profile` es el comando que hay que leer antes de escribir cualquier análisis.
Dice, por medio, cuántos artículos tienen cuerpo y cuántos lo tienen lo bastante
largo como para analizarlo. **No todos los medios tienen texto en todos los
años**, y dar eso por supuesto es el error más caro que se puede cometer con
este corpus. Ver la sección correspondiente del `README.md`.

---

## Paso 6 — Analizar

Tres vías, de menos a más comodidad:

### a) El notebook de análisis

```bash
uv pip install -e ".[notebook]"
jupyter lab notebooks/03-analisis-del-corpus.ipynb
```

Es el punto de partida recomendado: carga el corpus en un DataFrame y recorre
las preguntas que este dataset sí puede responder, señalando en cada una qué
filtro hay que aplicar para no medir un artefacto del archivo.

Además:

| Notebook | Para qué |
|---|---|
| `notebooks/02-guia-del-corpus.ipynb` | Qué guarda cada tabla y por qué |
| `notebooks/00-conexion-db.py` | Comprobar la conexión de punta a punta |
| `notebooks/01-exploracion-corpus.py` | Exploración rápida en consola |

### b) JupyterLab en Docker

Si prefieres no instalar Python en tu máquina:

```bash
docker compose up -d jupyter
open http://localhost:8888/lab?token=news-corpus
```

Dentro del contenedor la base es `postgres:5432`, no `localhost:5433`, pero el
servicio ya exporta las variables correctas: el mismo notebook funciona dentro y
fuera de Docker sin tocar nada.

### c) SQL directo

```bash
docker exec -it news-corpus-db psql -U news_corpus -d news_corpus
```

Recetario de consultas en [`docs/02-consultas.md`](02-consultas.md).

### d) Un archivo plano, sin base de datos

```bash
news-corpus export -o exports/corpus.parquet          # con el texto completo
news-corpus export -o exports/meta.csv -F csv --no-content   # sólo metadata
```

Útil si prefieres pandas o R y no quieres levantar Postgres.

---

## Actualizar el dump

Sólo hace falta si has ampliado el corpus (`collect`, `extract`) y quieres
compartir el resultado:

```bash
./scripts/dump-db.sh   # regenera dumps/news_corpus.dump y dumps/MANIFEST.md
git add dumps/ && git commit -m "chore: actualizar dump del corpus"
```

El manifiesto se regenera solo con las cifras nuevas, así que sirve de registro
de cómo iba creciendo el corpus.

---

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `connection to server at "127.0.0.1", port 5433 failed` | Docker Desktop parado o contenedor caído | `docker compose up -d` |
| `El contenedor 'news-corpus-db' no está corriendo` | Igual que la anterior | `docker compose up -d` |
| El puerto 5433 está ocupado | Otro Postgres local | Cambia `DB_PORT` en `.env` y relanza |
| `pg_restore: error: could not execute query` | Restaurando sobre una base a la que le falta el rol | El dump es `--no-owner`; comprueba que te conectas como `news_corpus` |
| `profile` da cero artículos | El dump no se restauró | Repite el paso 4 y lee la salida completa |
| Los notebooks no encuentran `news_corpus` | Falta instalar el paquete | `uv pip install -e ".[dev,export,notebook]"` |
