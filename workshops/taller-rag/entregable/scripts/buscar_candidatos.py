"""Busca palabras en el corpus para verificar preguntas y documentos relevantes.

No distingue mayúsculas ni tildes. Por defecto exige que aparezcan TODAS las palabras.
Lee el corpus completo (no el índice de Milvus), así que también encuentra documentos que
aún no estén indexados; si uno sí responde, agréguelo a subconjunto_ids.txt.

Uso:
  python -m scripts.buscar_candidatos --palabras "COP16;Cali"
  python -m scripts.buscar_candidatos --palabras "Bitcoin" --max 5
  python -m scripts.buscar_candidatos --palabras "deforestación;2024" --desde 2025-01-01 --modo todas
"""
import argparse, sys, unicodedata

import pyarrow.parquet as pq


def _tabla_sin_tildes():
    """Mapa carácter a carácter (1 a 1), así las posiciones coinciden con el texto original."""
    tabla = {}
    for cp in range(0xC0, 0x250):
        ch = chr(cp)
        base = unicodedata.normalize('NFD', ch)[0]
        if base != ch:
            tabla[cp] = base.lower()
    return tabla


TABLA = _tabla_sin_tildes()


def normalizar(s):
    # lower() puede cambiar la longitud en casos raros (p. ej. la I con punto); el fragmento
    # mostrado puede desplazarse unos caracteres en esos casos.
    return (s or '').lower().translate(TABLA)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--palabras', required=True, help='palabras separadas por ;')
    p.add_argument('--modo', choices=['todas', 'alguna'], default='todas')
    p.add_argument('--desde', default=None, help='fecha mínima, AAAA-MM-DD')
    p.add_argument('--hasta', default=None, help='fecha máxima, AAAA-MM-DD')
    p.add_argument('--max', type=int, default=10, help='cuántos fragmentos mostrar')
    p.add_argument('--contexto', type=int, default=160, help='caracteres de contexto')
    p.add_argument('--input', default='data/documentos_rag.parquet')
    a = p.parse_args()

    palabras = [normalizar(x.strip()) for x in a.palabras.split(';') if x.strip()]
    if not palabras:
        sys.exit('Indique al menos una palabra con --palabras.')

    pf = pq.ParquetFile(a.input)
    columnas = [c for c in ['document_id', 'text', 'source', 'lang', 'created_at_utc']
                if c in pf.schema_arrow.names]
    total, mostrados = 0, []
    for lote in pf.iter_batches(batch_size=4096, columns=columnas):
        for r in lote.to_pylist():
            fecha = str(r.get('created_at_utc') or '')[:10]
            if a.desde and (not fecha or fecha < a.desde):
                continue
            if a.hasta and (not fecha or fecha > a.hasta):
                continue
            texto = r.get('text') or ''
            hay = normalizar(texto)
            posiciones = [hay.find(w) for w in palabras]
            encontradas = [x for x in posiciones if x >= 0]
            if not encontradas:
                continue
            if a.modo == 'todas' and len(encontradas) != len(palabras):
                continue
            total += 1
            if len(mostrados) < a.max:
                pos = min(encontradas)
                ini = max(0, pos - a.contexto // 2)
                fin = min(len(texto), pos + a.contexto)
                fragmento = texto[ini:fin].replace('\n', ' ')
                mostrados.append((r.get('document_id'), r.get('source'), r.get('lang'), fecha, fragmento))

    print(f'Coincidencias: {total}. Mostrando {len(mostrados)}.')
    for doc, fuente, lang, fecha, frag in mostrados:
        print(f'\n{doc} | {fuente} | {lang} | {fecha or "sin fecha"}\n   ...{frag}...')
    if total == 0:
        print('\nSin coincidencias. Eso solo indica ausencia para estas palabras: pruebe sinónimos y '
              'variantes en otro idioma antes de declarar sin_evidencia.')


if __name__ == '__main__':
    main()
