# Inicio rápido — proyecto en un repositorio nuevo

Esta carpeta es el proyecto completo de detección de sesgo mediático, con los
cambios de la Entrega 2 ya incluidos. No hay que aplicar ningún patch.

Trae:

- el prototipo multiagente (raíz);
- `news-retrieval/`, el servicio de corpus con los proveedores nuevos (Arc e
  índice de sitemap) y el comando `probe`;
- el corpus piloto en `news-retrieval/dumps/news_corpus.dump` (17.202 artículos).

## Requisitos

- **Docker Desktop**, abierto.
- **Python 3.12** o superior.
- **Git**.
- **uv**: `pip install uv`.
- **Windows:** usar la terminal **Git Bash** en VS Code (los scripts `.sh` no
  corren en PowerShell).

## 1. Crear el repositorio nuevo

Descomprime el zip, abre la carpeta `media-bias-detection` en VS Code y, en la
terminal (*Terminal → New Terminal*):

```bash
git init
git add -A
git commit -m "Proyecto sesgo mediático - Entrega 2"
```

Para subirlo a GitHub, crea un repositorio vacío en github.com y ejecuta:

```bash
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git branch -M main
git push -u origin main
```

## 2. Levantar la base y cargar el corpus piloto

```bash
cd news-retrieval
cp .env.example .env
docker compose up -d
./scripts/restore-db.sh
```

## 3. Instalar y verificar

```bash
uv venv --python 3.12
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
uv pip install -e ".[dev,export]"
pytest -q                          # debe decir: 103 passed
```

## 4. Ampliar el corpus

```bash
./scripts/ampliar-corpus.sh
```

El script hace lo siguiente:

1. Muestra hasta dónde llega cada medio nuevo. **Envía una captura de esa tabla.**
2. Pide confirmación.
3. Recolecta de 2022-08 a 2026-07, reintenta los bloques fallidos, completa los
   titulares y etiqueta los temas.

Si se corta, se puede volver a ejecutar: no repite lo ya hecho.

Para una ventana distinta: `./scripts/ampliar-corpus.sh 2024-01 2024-06`.

## 5. Guardar el resultado

```bash
./scripts/dump-db.sh
git add -A && git commit -m "Corpus ampliado" && git push
```

## Problemas comunes

| Síntoma | Causa |
|---|---|
| Error de conexión a la base | Docker Desktop no está abierto, o el contenedor no está `healthy` (`docker ps`) |
| `port is already allocated` | El puerto 5433 está ocupado: cambia `DB_PORT` y `DB_PORT_HOST` en `.env` |
| `news-corpus: command not found` | El entorno virtual no está activado (paso 3, línea `source`) |
| `Permission denied` al correr un `.sh` | `chmod +x scripts/*.sh` |

Detalle técnico y decisiones: `news-retrieval/docs/06-ampliacion-corpus.md`.
