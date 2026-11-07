"""Esquema e índice de la colección Milvus para los chunks tok256 con E5-small.

La colección guarda un vector por chunk (``data/chunks_tok256.parquet``) y los metadatos
necesarios para citar y filtrar. Este módulo no se conecta a Milvus al importarse: solo
construye objetos de esquema e índice; ``ensure_collection`` recibe un cliente ya creado.

Nota: ``app/core.py`` define un esquema anterior (chunks de 1.000 caracteres, métrica
COSINE, campos ``title``/``position``). No deben compartir colección.
"""
from __future__ import annotations

from pymilvus import DataType, MilvusClient

COLLECTION_NAME = "rag_e5s_tok256_v1"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
DIM = 384
METRIC = "IP"  # Producto interno = coseno, porque los vectores están normalizados (L2).

# HNSW: grafo navegable; buen equilibrio recall/latencia para ~6e5 vectores en CPU.
# M = vecinos por nodo; efConstruction = amplitud de búsqueda al construir el grafo.
INDEX_TYPE = "HNSW"
INDEX_PARAMS = {"M": 16, "efConstruction": 200}
# ef en búsqueda: debe ser >= top-k; 64 da margen para k <= 15.
SEARCH_PARAMS = {"metric_type": METRIC, "params": {"ef": 64}}

# Longitudes máximas de VARCHAR (Milvus las cuenta en bytes UTF-8). Medidas sobre
# chunks_tok256.parquet: chunk_id 64, document_id 71, url 548, source 11,
# created_at_utc 35, text 6.800 bytes. Se deja holgura.
FIELDS = [
    {"name": "chunk_id", "dtype": DataType.VARCHAR, "max_length": 64, "is_primary": True},
    {"name": "vector", "dtype": DataType.FLOAT_VECTOR, "dim": DIM},
    {"name": "document_id", "dtype": DataType.VARCHAR, "max_length": 256},
    {"name": "source", "dtype": DataType.VARCHAR, "max_length": 32},
    {"name": "lang", "dtype": DataType.VARCHAR, "max_length": 8},
    {"name": "url", "dtype": DataType.VARCHAR, "max_length": 4096},
    # ISO 8601 en texto; "" cuando el documento no tiene fecha (162 chunks).
    {"name": "created_at_utc", "dtype": DataType.VARCHAR, "max_length": 64},
    {"name": "token_count", "dtype": DataType.INT32},
    {"name": "text", "dtype": DataType.VARCHAR, "max_length": 16384},
]

FIELD_NAMES = [f["name"] for f in FIELDS]
VARCHAR_LIMITS = {f["name"]: f["max_length"] for f in FIELDS if f["dtype"] == DataType.VARCHAR}
OUTPUT_FIELDS = [n for n in FIELD_NAMES if n != "vector"]


class SchemaMismatch(RuntimeError):
    """La colección existe pero con campos distintos a los de este esquema."""


def build_schema():
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    for spec in FIELDS:
        spec = dict(spec)
        schema.add_field(spec.pop("name"), spec.pop("dtype"), **spec)
    return schema


def build_index_params():
    index = MilvusClient.prepare_index_params()
    index.add_index(
        field_name="vector",
        index_type=INDEX_TYPE,
        metric_type=METRIC,
        params=dict(INDEX_PARAMS),
    )
    return index


def existing_field_names(client, collection_name):
    info = client.describe_collection(collection_name)
    return [f["name"] for f in info.get("fields", [])]


def ensure_collection(client, collection_name=COLLECTION_NAME):
    """Crea la colección si no existe. Devuelve True si la creó, False si ya estaba.

    Si ya existe con otros campos, lanza SchemaMismatch en lugar de mezclar esquemas.
    """
    if client.has_collection(collection_name):
        found = existing_field_names(client, collection_name)
        if sorted(found) != sorted(FIELD_NAMES):
            raise SchemaMismatch(
                f"La colección {collection_name!r} existe con campos {sorted(found)}; "
                f"se esperaban {sorted(FIELD_NAMES)}. Use otro nombre de colección."
            )
        return False
    client.create_collection(
        collection_name=collection_name,
        schema=build_schema(),
        index_params=build_index_params(),
    )
    return True
