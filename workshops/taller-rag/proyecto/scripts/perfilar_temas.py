"""Perfila DE QUÉ trata el corpus, no su estructura.

Lee las columnas temáticas (keyword_family, collection_keyword_label, collection_query,
section, publisher, event_context, top_terms) y escribe un informe en Markdown + JSON.

Uso:
    python -m scripts.perfilar_temas --input data/documentos_rag.parquet \
        --salida-md docs/temas_corpus.md --salida-json docs/temas_corpus.json
"""
import argparse, json, re
from collections import Counter

import pyarrow.parquet as pq

# Columnas temáticas que puede traer el corpus. Se usan solo las que existan.
CATEGORICAS = ['keyword_family', 'collection_keyword_label', 'collection_keyword',
               'collection_query', 'section', 'publisher', 'url_domain', 'event_context']
CRUCE = ['source', 'lang', 'language_base']


def es_num(n, dec=0):
    """Formato español: punto para miles, coma para decimales."""
    return f'{n:,.{dec}f}'.translate(str.maketrans({',': '.', '.': ','})) if dec \
        else f'{n:,}'.replace(',', '.')


def resumen(contador, total, tope):
    filas = []
    for valor, n in contador.most_common(tope):
        filas.append({'valor': valor, 'filas': n, 'pct': round(100 * n / total, 2)})
    return filas


def tabla_md(filas, encabezado):
    out = [f'| {encabezado} | Filas | % |', '|---|---:|---:|']
    for f in filas:
        valor = str(f['valor']).replace('|', '\\|')
        if len(valor) > 70:
            valor = valor[:67] + '…'
        out.append(f"| `{valor}` | {es_num(f['filas'])} | {es_num(f['pct'], 2)} % |")
    return '\n'.join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='data/documentos_rag.parquet')
    p.add_argument('--salida-md', default='docs/temas_corpus.md')
    p.add_argument('--salida-json', default='docs/temas_corpus.json')
    p.add_argument('--tope', type=int, default=25, help='valores a mostrar por columna')
    args = p.parse_args()

    parq = pq.ParquetFile(args.input)
    disponibles = set(parq.schema_arrow.names)
    categoricas = [c for c in CATEGORICAS if c in disponibles]
    cruce = [c for c in CRUCE if c in disponibles]
    tiene_top_terms = 'top_terms' in disponibles
    tiene_matches = 'keyword_matches' in disponibles

    columnas = categoricas + cruce + (['top_terms'] if tiene_top_terms else []) \
        + (['keyword_matches'] if tiene_matches else [])
    if not columnas:
        raise SystemExit('El archivo no tiene ninguna columna temática conocida.')

    cont = {c: Counter() for c in categoricas}
    nulos = {c: 0 for c in categoricas}
    terminos = Counter()
    matches = Counter()
    # keyword_family x source, para ver qué tema aporta cada plataforma.
    cruces = {c: Counter() for c in cruce if categoricas}
    total = 0

    for batch in parq.iter_batches(batch_size=4096, columns=columnas):
        filas = batch.to_pylist()
        total += len(filas)
        for r in filas:
            for c in categoricas:
                v = r.get(c)
                if v is None or (isinstance(v, str) and not v.strip()):
                    nulos[c] += 1
                else:
                    cont[c][str(v).strip()] += 1
            if categoricas:
                principal = r.get(categoricas[0]) or '(sin valor)'
                for c in cruce:
                    cruces[c][(str(principal), str(r.get(c) or '(sin valor)'))] += 1
            if tiene_top_terms:
                for t in (r.get('top_terms') or []):
                    if isinstance(t, dict) and t.get('term'):
                        terminos[str(t['term']).lower()] += int(t.get('count') or 1)
            if tiene_matches:
                for m in (r.get('keyword_matches') or []):
                    if m:
                        matches[str(m).lower()] += 1

    datos = {'input': args.input, 'filas': total,
             'columnas_tematicas_presentes': categoricas,
             'valores_distintos': {c: len(cont[c]) for c in categoricas},
             'nulos': {c: nulos[c] for c in categoricas},
             'top': {c: resumen(cont[c], total, args.tope) for c in categoricas},
             'top_terms': resumen(terminos, max(sum(terminos.values()), 1), 40) if tiene_top_terms else None,
             'keyword_matches': resumen(matches, max(sum(matches.values()), 1), 40) if tiene_matches else None}

    md = [f'# De qué trata el corpus\n',
          f'Generado por `scripts/perfilar_temas.py` sobre `{args.input}` ({es_num(total)} filas).',
          '\nEste informe solo lee metadatos temáticos y conteos de términos; no reproduce texto de documentos.\n']

    for c in categoricas:
        distintos = len(cont[c])
        cobertura = round(100 * (total - nulos[c]) / total, 2) if total else 0
        md.append(f'\n## `{c}`\n')
        md.append(f'{es_num(distintos)} valores distintos · presente en {es_num(cobertura, 2)} % de las filas.\n')
        md.append(tabla_md(datos['top'][c], 'Valor'))

    if tiene_matches and matches:
        md.append('\n## Términos que dispararon la recolección (`keyword_matches`)\n')
        md.append(tabla_md(datos['keyword_matches'], 'Término'))
    if tiene_top_terms and terminos:
        md.append('\n## Términos más frecuentes en los textos (`top_terms`)\n')
        md.append(tabla_md(datos['top_terms'], 'Término'))

    if categoricas and cruce:
        c0 = categoricas[0]
        for c in cruce:
            pares = cruces[c].most_common(args.tope)
            if not pares:
                continue
            md.append(f'\n## `{c0}` × `{c}`\n')
            md.append(f'| {c0} | {c} | Filas |')
            md.append('|---|---|---:|')
            for (a, b), n in pares:
                md.append(f'| `{a[:50]}` | `{b}` | {es_num(n)} |')

    with open(args.salida_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md) + '\n')
    with open(args.salida_json, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print(json.dumps({'filas': total, 'columnas_tematicas': categoricas,
                      'md': args.salida_md, 'json': args.salida_json}, ensure_ascii=False))


if __name__ == '__main__':
    main()
