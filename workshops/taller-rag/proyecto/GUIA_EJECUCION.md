# Guía de ejecución con Docker, paso a paso

Esta guía levanta el sistema RAG completo desde cero: Milvus, Ollama, API y página web.
Milvus corre en modo standalone con etcd embebido y almacenamiento local (sin MinIO).
No requiere instalar Python ni pagar ningún servicio.

## 0. Requisitos (una sola vez)

1. **Docker Desktop** instalado y abierto (https://www.docker.com/products/docker-desktop/).
   En Windows, durante la instalación acepte usar **WSL 2**.
2. **Memoria para Docker**: al menos 10 GB.
   - Mac: Docker Desktop → Settings → Resources → Memory → 10 GB o más → *Apply & restart*.
   - Windows: Docker usa por defecto la mitad de la RAM del equipo; con 16 GB alcanza.
3. **Espacio libre en disco**: unos 25 GB (imágenes, corpus, modelos y vectores).
4. **Git** (opcional): si no lo tiene, puede descargar el repositorio como ZIP.

Compruebe que Docker funciona abriendo una terminal (Mac: *Terminal*; Windows: *PowerShell*) y escribiendo:

```bash
docker --version
docker compose version
```

Ambos comandos deben mostrar un número de versión.

## 1. Obtener el proyecto

Con Git:

```bash
git clone https://github.com/AbelAlbuez/natural-language-processing-workshops.git
cd natural-language-processing-workshops/workshops/taller-rag/proyecto
```

Sin Git: en GitHub, botón verde **Code → Download ZIP**, descomprímalo y, en la terminal,
entre a la carpeta `workshops/taller-rag/proyecto` con `cd`.
(Truco: escriba `cd ` con un espacio y arrastre la carpeta a la ventana de la terminal.)

Todos los comandos siguientes se ejecutan **dentro de esa carpeta**.

## 2. Crear el archivo de configuración

```bash
# Mac / Linux
cp .env.example .env
# Windows (PowerShell)
copy .env.example .env
```

Si su equipo tiene 8 GB de RAM, abra `.env` con un editor de texto y cambie
`MILVUS_MEM=2g` y `OLLAMA_MEM=4g`.

## 3. Descargar y preparar el corpus (una sola vez, 10–30 min)

```bash
docker compose --profile prep run --rm prep
```

Qué hace: construye una imagen de preparación, descarga `dragons_rag`, verifica su huella SHA-256,
descarga el detector de idioma de fastText y genera `data/documentos_rag.parquet` (español + inglés).

Resultado esperado al final:

```
   sha256_ok = True | filas = 169248 | columnas = 33
   filas de salida = 146923 | por fuente = {...}
Listo: data/documentos_rag.parquet
```

Si el hash no coincide, el proceso se detiene y deja el detalle en `data/inspeccion_corpus.json`.

## 4. Levantar el sistema (la primera vez tarda 10–20 min)

```bash
docker compose up -d --build
```

Espere uno o dos minutos y revise el estado:

```bash
docker compose ps
```

Los cuatro servicios (`rag-milvus`, `rag-ollama`, `rag-api`, `rag-frontend`)
deben decir **healthy**. Milvus es el más lento; si dice *starting*, espere y repita el comando.

## 5. Descargar los modelos de lenguaje (una sola vez)

```bash
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose exec ollama ollama pull llama3.2:1b
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull gemma2:2b
docker compose exec ollama ollama list
```

Cada modelo pesa entre 1 y 2 GB. Quedan guardados aunque se apague Docker.

## 6. Cargar los documentos en Milvus (ingesta piloto)

```bash
docker compose exec api python -m scripts.ingest --input data/documentos_rag.parquet --limit 500
```

La primera vez descarga el modelo de embeddings (e5-small, unos 470 MB). Al final imprime algo como
`{"documents": 500, "chunks": ..., "collection": "rag_e5s_tok256_v1"}`.
Si se vuelve a ejecutar, no duplica: reemplaza los mismos fragmentos.

## 7. Verificar que todo está conectado

Abra en el navegador:

| Dirección | Qué debe ver |
|---|---|
| http://localhost:8000/health?deep=true | `"status": "ok"`, Milvus con `chunks` mayor que 0 y la lista de modelos de Ollama |
| http://localhost:8000/docs | La documentación interactiva de la API (`/health`, `/retrieve`, `/ask`) |
| http://localhost:8501 | La página del RAG: elija un modelo, escriba una pregunta y pulse **Consultar** |

La primera pregunta con cada modelo tarda más (el modelo se carga en memoria: *arranque en frío*).

Pruebas automáticas:

```bash
docker compose exec api python -m pytest -q
```

## 8. Uso diario

| Acción | Comando |
|---|---|
| Apagar (conserva datos, modelos y vectores) | `docker compose down` |
| Volver a encender | `docker compose up -d` |
| Ver mensajes de un servicio | `docker compose logs -f api` (salir con Ctrl+C) |
| Uso de CPU y memoria en vivo | `docker stats` |
| Reconstruir tras cambiar código | `docker compose up -d --build` |
| **Borrar todo**, incluidos vectores y modelos | `docker compose down -v` (¡cuidado!) |

## 9. Solo para equipos con GPU NVIDIA (opcional)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

En Mac no aplica: Docker no puede usar la GPU de Apple y Ollama funciona en CPU (más lento, pero válido).

## 10. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop no está abierto | Abra Docker Desktop y espere a que diga *running* |
| `port is already allocated` | Otro programa usa el puerto 8000, 8501, 11434 o 19530 | Cierre ese programa (por ejemplo, un Ollama instalado aparte) |
| Milvus queda en *unhealthy* | Poca memoria | Suba la memoria de Docker Desktop o baje `MILVUS_MEM` |
| Un contenedor se reinicia solo / `Killed` / código 137 | Se quedó sin memoria | Use modelos más pequeños o suba los límites en `.env` |
| `manifest unknown` o `not found` al bajar `ollama/ollama` | Esa versión no está publicada | Cambie `OLLAMA_VERSION` en `.env` por una versión publicada |
| La página responde *503 No se pudo consultar Ollama* | El modelo elegido no se descargó | Ejecute el `ollama pull` del paso 5 |
| La respuesta dice que no hay evidencia | La colección está vacía | Revise el paso 6 y `health?deep=true` |
| `Falta Parquet: data/documentos_rag.parquet` | No se hizo la preparación | Ejecute el paso 3 |

## Qué cambió respecto a la versión original

- **Sin MinIO ni etcd externos.** Docker Hub eliminó `minio/minio` en septiembre de 2026 y quay.io dejó de
  permitir descargas anónimas, así que la versión original ya no puede arrancar. Milvus usa ahora la
  configuración oficial de `standalone_embed.sh` (etcd embebido y disco local), con Milvus v2.6.25.

- Milvus, Ollama, API y web tienen **healthcheck**, y la API espera a que Milvus y Ollama estén listos.
- Versiones fijadas (Ollama ya no usa `latest`) y configurables en `.env`.
- **Límites de CPU y memoria** por servicio, y archivo opcional para GPU NVIDIA.
- Volumen para el modelo de embeddings: no se descarga en cada reconstrucción.
- La imagen de la API ya no instala `fasttext` ni `open_corpus_co_es`; la versión original
  fallaba al construirse en Mac con chip Apple (M1–M4), porque `fasttext-numpy2` no tiene
  versión precompilada para ARM.
- PyTorch solo CPU: imagen unos 2 GB más liviana.
- Servicio `prep` que descarga, verifica y prepara el corpus dentro de Docker.
- `.dockerignore`, para no copiar el corpus a las imágenes.
- `/health?deep=true` comprueba la conexión real con Milvus y Ollama.
- Rotación de logs, para que no llenen el disco.
