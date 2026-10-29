"""Referencia inicial, no sustituto del diseño y la experimentación estudiantil."""
import os
from functools import lru_cache
from pymilvus import MilvusClient, DataType
from sentence_transformers import SentenceTransformer

COLLECTION = os.getenv('MILVUS_COLLECTION', 'rag_e5s_tok256_v1')

@lru_cache(maxsize=1)
def encoder():
    return SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'intfloat/multilingual-e5-small'))

def embed(texts, kind='passage'):
    prefix = 'query: ' if kind == 'query' else 'passage: '
    return encoder().encode([prefix + t for t in texts], normalize_embeddings=True).tolist()

def client():
    return MilvusClient(uri=os.getenv('MILVUS_URI','http://milvus:19530'))

def ensure_collection(c):
    if c.has_collection(COLLECTION):
        return
    dim = len(embed(['ejemplo'])[0])
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field('chunk_id', DataType.VARCHAR, is_primary=True, max_length=128)
    schema.add_field('vector', DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field('text', DataType.VARCHAR, max_length=12000)
    schema.add_field('document_id', DataType.VARCHAR, max_length=256)
    schema.add_field('title', DataType.VARCHAR, max_length=2048)
    schema.add_field('url', DataType.VARCHAR, max_length=4096)
    schema.add_field('collection_name', DataType.VARCHAR, max_length=80)
    schema.add_field('source', DataType.VARCHAR, max_length=80)
    schema.add_field('position', DataType.INT64)
    index = c.prepare_index_params()
    index.add_index(field_name='vector', index_type='AUTOINDEX', metric_type='COSINE')
    c.create_collection(collection_name=COLLECTION, schema=schema, index_params=index)

def retrieve(query, k=5):
    c = client()
    if not c.has_collection(COLLECTION):
        return []
    rows = c.search(collection_name=COLLECTION, data=embed([query], kind='query'), limit=k,
                    output_fields=['text','document_id','title','url','collection_name','source','position'],
                    search_params={'metric_type':'COSINE'})[0]
    return [_hit_to_dict(x) for x in rows]


def _hit_to_dict(hit):
    """Normaliza un resultado de búsqueda.

    En pymilvus 2.6 cada resultado es un diccionario con la clave primaria bajo su nombre real
    ('chunk_id'), 'distance' y 'entity'. En versiones anteriores la clave primaria venía como 'id'.
    Se admiten las dos formas para no depender de la versión instalada.
    """
    fields = dict(hit.get('entity') or {})
    fields.pop('vector', None)
    chunk_id = fields.pop('chunk_id', None)
    if chunk_id is None:
        chunk_id = dict.get(hit, 'chunk_id', None) or dict.get(hit, 'id', None)
    return {'chunk_id': chunk_id, 'score': dict.get(hit, 'distance', None), **fields}
