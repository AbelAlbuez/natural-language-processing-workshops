"""Prepara dragons_rag para el RAG: deduplica, filtra idioma, normaliza fechas y descarta textos cortos.

No modifica el parquet de entrada. Conserva todas sus columnas y agrega:
lang, lang_source, lang_prob y created_at_utc.
"""
import argparse, json, os
import fasttext
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DEFAULT_INPUT = os.path.expanduser('~/.open_corpus_co_es/data/dragons_rag/dragons_rag.parquet')


def detect(model, texts, threshold):
    """Devuelve (idioma, probabilidad); 'und' si la probabilidad es menor que el umbral."""
    clean = [' '.join(t.split()) for t in texts]  # fasttext exige una sola línea
    labels, probs = model.predict(clean, k=1)
    out = []
    for label, prob in zip(labels, probs):
        lang, p = label[0].replace('__label__', ''), float(prob[0])
        out.append(('und' if p < threshold else lang, p))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default=DEFAULT_INPUT)
    p.add_argument('--output', default='data/documentos_rag.parquet')
    p.add_argument('--languages', nargs='+', default=['es'], help='idiomas a conservar, p. ej. --languages es en')
    p.add_argument('--lid-model', default='models/lid.176.bin')
    p.add_argument('--lid-threshold', type=float, default=0.5)
    p.add_argument('--min-words', type=int, default=5)
    p.add_argument('--stats', default=None, help='ruta opcional para guardar las cifras en JSON')
    args = p.parse_args()
    if os.path.abspath(args.input) == os.path.abspath(args.output):
        raise SystemExit('La salida no puede sobrescribir la entrada.')

    table = pq.read_table(args.input)
    stats = {'input': args.input, 'languages': args.languages, 'lid_threshold': args.lid_threshold,
             'min_words': args.min_words, 'rows_input': table.num_rows}
    meta = table.select(['text_sha256', 'title', 'created_at', 'language_base', 'word_count', 'source',
                         'document_id', 'url']).to_pandas()
    meta['row'] = range(len(meta))

    # 1. Duplicados por text_sha256: primero la fila con title no vacío, luego la de created_at más antiguo.
    meta['created_at_utc'] = pd.to_datetime(meta.created_at, utc=True, errors='coerce', format='mixed')
    meta['has_title'] = meta.title.fillna('').str.strip().str.len() > 0
    # Procedencia de todas las copias (incluida la conservada), para no perder trazabilidad.
    copies = meta.groupby('text_sha256', sort=False).agg(
        dup_document_ids=('document_id', list), dup_urls=('url', list), dup_sources=('source', list))
    copies['dup_count'] = copies.dup_document_ids.str.len()
    meta = (meta.sort_values(['has_title', 'created_at_utc', 'row'], ascending=[False, True, True], na_position='last')
                .drop_duplicates('text_sha256', keep='first').sort_values('row'))
    meta = meta.join(copies, on='text_sha256')
    stats['rows_after_dedup'] = len(meta)
    stats['removed_dedup'] = stats['rows_input'] - len(meta)

    # 2. Idioma: language_base si existe; si no, fasttext sobre el texto.
    meta['lang'] = meta.language_base
    meta['lang_source'] = 'language_base'
    meta['lang_prob'] = float('nan')
    missing = meta.lang.isna()
    stats['lid_candidates'] = int(missing.sum())
    if missing.any():
        model = fasttext.load_model(args.lid_model)
        texts = table.column('text').take(pa.array(meta.loc[missing, 'row'].to_numpy())).to_pylist()
        detected = detect(model, texts, args.lid_threshold)
        meta.loc[missing, 'lang'] = [d[0] for d in detected]
        meta.loc[missing, 'lang_prob'] = [d[1] for d in detected]
        meta.loc[missing, 'lang_source'] = 'fasttext'
    lid = meta[meta.lang_source == 'fasttext'].lang
    stats['lid_es'] = int((lid == 'es').sum())
    stats['lid_und'] = int((lid == 'und').sum())
    stats['lid_other'] = int(len(lid) - stats['lid_es'] - stats['lid_und'])
    stats['lid_by_source'] = {k: {kk: int(vv) for kk, vv in v.items()} for k, v in
                              meta[meta.lang_source == 'fasttext'].assign(
                                  g=lambda d: d.lang.where(d.lang.isin(['es', 'und']), 'otro'))
                              .groupby('source').g.value_counts().unstack(fill_value=0).to_dict('index').items()}
    before = len(meta)
    meta = meta[meta.lang.isin(args.languages)]
    stats['removed_language'] = before - len(meta)
    stats['rows_after_language'] = len(meta)

    # 3. created_at_utc ya está calculada arriba; no se filtra por fecha.
    stats['created_at_utc_null'] = int(meta.created_at_utc.isna().sum())

    # 4. Textos cortos.
    before = len(meta)
    meta = meta[meta.word_count >= args.min_words]
    stats['removed_short'] = before - len(meta)
    stats['rows_output'] = len(meta)

    # 5. Salida: columnas originales + nuevas, en el orden original de filas.
    out = table.take(pa.array(meta.row.to_numpy()))
    out = out.append_column('lang', pa.array(meta.lang.to_numpy(), pa.string()))
    out = out.append_column('lang_source', pa.array(meta.lang_source.to_numpy(), pa.string()))
    out = out.append_column('lang_prob', pa.array(meta.lang_prob.to_numpy(), pa.float64(), from_pandas=True))
    out = out.append_column('created_at_utc', pa.array(meta.created_at_utc, pa.timestamp('ns', tz='UTC')))
    out = out.append_column('dup_count', pa.array(meta.dup_count.to_numpy(), pa.int64()))
    for c in ('dup_document_ids', 'dup_urls', 'dup_sources'):
        out = out.append_column(c, pa.array(meta[c].tolist(), pa.list_(pa.string())))
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    pq.write_table(out, args.output, compression='zstd')

    stats['output'] = args.output
    stats['columns_output'] = out.num_columns
    stats['by_source'] = meta.source.value_counts().to_dict()
    stats['by_lang_source'] = meta.lang_source.value_counts().to_dict()
    stats['by_source_lang_source'] = {f'{s}|{l}': int(n) for (s, l), n in meta.groupby(['source', 'lang_source']).size().items()}
    stats['created_at_utc_min'] = str(meta.created_at_utc.min())
    stats['created_at_utc_max'] = str(meta.created_at_utc.max())
    text = json.dumps(stats, ensure_ascii=False, indent=1, default=int)
    if args.stats:
        with open(args.stats, 'w', encoding='utf-8') as f: f.write(text)
    print(text)


if __name__ == '__main__': main()
