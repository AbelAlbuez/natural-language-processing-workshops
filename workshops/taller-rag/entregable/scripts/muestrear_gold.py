"""Muestra estratificada de documentos para construir el gold estándar.

Produce tres salidas que se usan juntas:
  1. <salida>/subconjunto_ids.txt  -> los document_id que se deben indexar (scripts/ingest.py --ids-file)
  2. <salida>/muestra.jsonl        -> metadatos de cada documento muestreado
  3. <salida>/paquete_NN.md        -> los pasajes formateados para pegar en el prompt de generación

El muestreo es reproducible: con la misma semilla y el mismo archivo salen los mismos documentos.

Uso típico (cuotas del análisis de Abel, ventana comparable prensa/Bluesky):
    python -m scripts.muestrear_gold --input data/documentos_rag.parquet \
        --cuota media_cloud:es=18 --cuota media_cloud:en=10 \
        --cuota bluesky:es=8 --cuota bluesky:en=8 --cuota gdelt:es=3 --cuota gdelt:en=3 \
        --desde 2025-01-01 --semilla 20261106
"""
import argparse, json, os, random, re, unicodedata
from collections import defaultdict

import pyarrow.parquet as pq

CAMPOS = ['document_id', 'text', 'title', 'url', 'source', 'collection_name',
          'lang', 'created_at_utc', 'word_count', 'dup_count', 'publisher',
          'keyword_family', 'collection_keyword_label', 'section']

# Señales de texto de navegación: menús y pies de página pegados al artículo.
RUIDO = re.compile(r'(iniciar sesi|suscr[ií]b|men[uú] principal|todos los derechos|'
                   r'cookies|newsletter|compartir en|s[ií]guenos|subscribe|sign in)', re.I)


def normalizar(s):
    return unicodedata.normalize('NFKC', s or '').replace(' ', ' ')


def limpiar(texto, maximo):
    t = re.sub(r'[ \t]+', ' ', normalizar(texto))
    t = re.sub(r'\n{3,}', '\n\n', t).strip()
    return t[:maximo] + ('…' if len(t) > maximo else '')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='data/documentos_rag.parquet')
    p.add_argument('--salida', default='data/gold')
    p.add_argument('--cuota', action='append', default=[],
                   help='fuente:idioma=n, p. ej. media_cloud:es=18 (repetible)')
    p.add_argument('--desde', default=None, help='fecha mínima ISO, p. ej. 2025-01-01')
    p.add_argument('--hasta', default=None, help='fecha máxima ISO')
    p.add_argument('--min-palabras', type=int, default=60)
    p.add_argument('--max-palabras', type=int, default=3000)
    p.add_argument('--sin-duplicados', action='store_true',
                   help='excluye documentos cuyo texto aparece más de una vez')
    p.add_argument('--excluir-ruido', action='store_true',
                   help='excluye textos con señales de menú o pie de página')
    p.add_argument('--caracteres-pasaje', type=int, default=1800)
    p.add_argument('--por-paquete', type=int, default=10, help='pasajes por archivo de prompt')
    p.add_argument('--semilla', type=int, default=20261106)
    args = p.parse_args()

    cuotas = {}
    for c in args.cuota:
        clave, _, n = c.partition('=')
        fuente, _, lang = clave.partition(':')
        if not (fuente and lang and n.isdigit()):
            raise SystemExit(f'Cuota mal escrita: {c}. Formato: fuente:idioma=n')
        cuotas[(fuente, lang)] = int(n)
    if not cuotas:
        raise SystemExit('Indique al menos una --cuota, p. ej. --cuota media_cloud:es=18')

    parq = pq.ParquetFile(args.input)
    disponibles = set(parq.schema_arrow.names)
    campos = [c for c in CAMPOS if c in disponibles]
    if 'lang' not in campos:
        raise SystemExit('El archivo no tiene columna "lang": use el corpus preparado, no el original.')

    # Reservoir sampling por estrato: una sola pasada, memoria acotada, reproducible.
    rng = random.Random(args.semilla)
    reserva = defaultdict(list)
    vistos = defaultdict(int)
    descartes = defaultdict(int)

    for batch in parq.iter_batches(batch_size=4096, columns=campos):
        for r in batch.to_pylist():
            estrato = (r.get('source'), r.get('lang'))
            if estrato not in cuotas:
                continue
            wc = r.get('word_count') or 0
            if not (args.min_palabras <= wc <= args.max_palabras):
                descartes['longitud'] += 1; continue
            fecha = r.get('created_at_utc')
            if args.desde or args.hasta:
                if fecha is None:
                    descartes['sin_fecha'] += 1; continue
                iso = str(fecha)[:10]
                if args.desde and iso < args.desde:
                    descartes['fuera_de_ventana'] += 1; continue
                if args.hasta and iso > args.hasta:
                    descartes['fuera_de_ventana'] += 1; continue
            if args.sin_duplicados and (r.get('dup_count') or 1) > 1:
                descartes['duplicado'] += 1; continue
            texto = normalizar(r.get('text'))
            if args.excluir_ruido and RUIDO.search(texto[:1200]):
                descartes['ruido'] += 1; continue

            k = cuotas[estrato]
            vistos[estrato] += 1
            if len(reserva[estrato]) < k:
                reserva[estrato].append(r)
            else:
                j = rng.randrange(vistos[estrato])
                if j < k:
                    reserva[estrato][j] = r

    os.makedirs(args.salida, exist_ok=True)
    seleccion = []
    for estrato in sorted(cuotas):
        seleccion.extend(sorted(reserva[estrato], key=lambda r: r['document_id']))

    with open(os.path.join(args.salida, 'subconjunto_ids.txt'), 'w', encoding='utf-8') as f:
        for r in seleccion:
            f.write(r['document_id'] + '\n')

    with open(os.path.join(args.salida, 'muestra.jsonl'), 'w', encoding='utf-8') as f:
        for r in seleccion:
            f.write(json.dumps({
                'document_id': r['document_id'], 'source': r.get('source'), 'lang': r.get('lang'),
                'title': normalizar(r.get('title')), 'url': r.get('url'),
                'fecha': str(r.get('created_at_utc'))[:10] if r.get('created_at_utc') else None,
                'word_count': r.get('word_count'), 'dup_count': r.get('dup_count'),
                'publisher': r.get('publisher'), 'keyword_family': r.get('keyword_family'),
            }, ensure_ascii=False) + '\n')

    paquetes = 0
    for i in range(0, len(seleccion), args.por_paquete):
        paquetes += 1
        lote = seleccion[i:i + args.por_paquete]
        ruta = os.path.join(args.salida, f'paquete_{paquetes:02d}.md')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(f'# Pasajes {i + 1}–{i + len(lote)}\n\n')
            f.write('Pegue este bloque completo al final del prompt de generación.\n\n')
            for r in lote:
                fecha = str(r.get('created_at_utc'))[:10] if r.get('created_at_utc') else 'sin fecha'
                f.write(f"---\nDOCUMENT_ID: {r['document_id']}\n")
                f.write(f"FUENTE: {r.get('source')} | IDIOMA: {r.get('lang')} | FECHA: {fecha}\n")
                f.write(f"TITULO: {limpiar(r.get('title'), 200) or '(sin título)'}\n")
                f.write(f"TEXTO:\n{limpiar(r.get('text'), args.caracteres_pasaje)}\n\n")

    resumen = {'seleccionados': len(seleccion), 'paquetes': paquetes,
               'por_estrato': {f'{s}:{l}': len(reserva[(s, l)]) for (s, l) in sorted(cuotas)},
               'cuotas_sin_llenar': {f'{s}:{l}': cuotas[(s, l)] - len(reserva[(s, l)])
                                     for (s, l) in sorted(cuotas) if len(reserva[(s, l)]) < cuotas[(s, l)]},
               'candidatos_por_estrato': {f'{s}:{l}': vistos[(s, l)] for (s, l) in sorted(cuotas)},
               'descartes': dict(descartes), 'semilla': args.semilla, 'salida': args.salida}
    with open(os.path.join(args.salida, 'muestra_stats.json'), 'w', encoding='utf-8') as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
