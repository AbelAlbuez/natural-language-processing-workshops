"""Valida el gold estándar antes de usarlo para evaluar.

Comprueba estructura, identificadores únicos, que los document_id existan en el subconjunto
indexado, que la evidencia literal aparezca de verdad en el documento, y resume la distribución
frente a las cuotas del taller.

Uso:
    python -m scripts.validar_gold --gold data/gold/gold.jsonl \
        --ids data/gold/subconjunto_ids.txt --corpus data/documentos_rag.parquet

Kappa de Cohen sobre la submuestra de doble anotación:
    python -m scripts.validar_gold --kappa data/gold/anotador_a.jsonl data/gold/anotador_b.jsonl
"""
import argparse, json, re, sys, unicodedata
from collections import Counter, defaultdict

OBLIGATORIOS = ['question_id', 'pregunta', 'idioma', 'tipo', 'dificultad',
                'documentos_relevantes', 'split', 'origen']
TIPOS = {'factual', 'interpretativa', 'comparativa', 'sin_evidencia', 'adversarial', 'temporal'}
DIFICULTADES = {'facil', 'media', 'dificil'}
SPLITS = {'dev', 'test'}
ORIGENES = {'manual', 'llm_revisado'}
IDIOMAS = {'es', 'en'}
# Tipos cuya respuesta correcta es abstenerse: no deben traer documentos relevantes.
SIN_DOCS = {'sin_evidencia'}


def norm(s):
    """Normaliza para comparar: sin acentos, minúsculas, espacios colapsados."""
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip().lower()


def leer_jsonl(ruta):
    filas = []
    with open(ruta, encoding='utf-8') as f:
        for n, linea in enumerate(f, 1):
            linea = linea.strip()
            if not linea or linea.startswith('//'):
                continue
            try:
                filas.append((n, json.loads(linea)))
            except json.JSONDecodeError as e:
                raise SystemExit(f'{ruta}:{n}: JSON inválido ({e.msg})')
    return filas


def kappa_cohen(a, b):
    """Kappa sobre pares (question_id, document_id) juzgados por ambos anotadores."""
    pares_a = {(r['question_id'], d): 1 for r in a for d in r.get('documentos_relevantes', [])}
    pares_b = {(r['question_id'], d): 1 for r in b for d in r.get('documentos_relevantes', [])}
    universo = set(pares_a) | set(pares_b)
    # Se añaden los no-relevantes: documentos que el otro anotador sí marcó para esa pregunta.
    if not universo:
        return None
    ja = [pares_a.get(p, 0) for p in sorted(universo)]
    jb = [pares_b.get(p, 0) for p in sorted(universo)]
    n = len(ja)
    po = sum(1 for x, y in zip(ja, jb) if x == y) / n
    pa1, pb1 = sum(ja) / n, sum(jb) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return {'pares_juzgados': n, 'acuerdo_observado': round(po, 4),
            'acuerdo_esperado': round(pe, 4),
            'kappa': round((po - pe) / (1 - pe), 4) if pe < 1 else None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--gold', default='data/gold/gold.jsonl')
    p.add_argument('--ids', default=None, help='subconjunto_ids.txt: los documentos indexados')
    p.add_argument('--corpus', default=None, help='parquet, para verificar la evidencia literal')
    p.add_argument('--minimo', type=int, default=40)
    p.add_argument('--kappa', nargs=2, metavar=('A', 'B'), default=None)
    args = p.parse_args()

    if args.kappa:
        a = [r for _, r in leer_jsonl(args.kappa[0])]
        b = [r for _, r in leer_jsonl(args.kappa[1])]
        res = kappa_cohen(a, b)
        print(json.dumps(res or {'error': 'sin pares para comparar'}, ensure_ascii=False, indent=1))
        return

    filas = leer_jsonl(args.gold)
    errores, avisos = [], []
    ids_vistos = {}
    docs_citados = set()

    for n, r in filas:
        pos = f'línea {n}'
        for campo in OBLIGATORIOS:
            if campo not in r:
                errores.append(f'{pos}: falta el campo "{campo}"')
        qid = r.get('question_id')
        if qid in ids_vistos:
            errores.append(f'{pos}: question_id repetido "{qid}" (ya estaba en la línea {ids_vistos[qid]})')
        elif qid:
            ids_vistos[qid] = n
        if r.get('tipo') not in TIPOS:
            errores.append(f'{pos}: tipo "{r.get("tipo")}" no válido; use {sorted(TIPOS)}')
        if r.get('dificultad') not in DIFICULTADES:
            errores.append(f'{pos}: dificultad "{r.get("dificultad")}" no válida')
        if r.get('split') not in SPLITS:
            errores.append(f'{pos}: split "{r.get("split")}" no válido (dev o test)')
        if r.get('origen') not in ORIGENES:
            errores.append(f'{pos}: origen "{r.get("origen")}" no válido')
        if r.get('idioma') not in IDIOMAS:
            errores.append(f'{pos}: idioma "{r.get("idioma")}" no válido')
        if not str(r.get('pregunta', '')).strip():
            errores.append(f'{pos}: la pregunta está vacía')
        docs = r.get('documentos_relevantes')
        if not isinstance(docs, list):
            errores.append(f'{pos}: documentos_relevantes debe ser una lista')
            docs = []
        if r.get('tipo') in SIN_DOCS and docs:
            errores.append(f'{pos}: una pregunta "{r["tipo"]}" no debe tener documentos relevantes')
        if r.get('tipo') not in SIN_DOCS and r.get('tipo') != 'adversarial' and not docs:
            errores.append(f'{pos}: sin documentos relevantes; el Recall no se puede calcular')
        if len(docs) != len(set(docs)):
            errores.append(f'{pos}: documentos_relevantes tiene repetidos')
        docs_citados.update(docs)
        if r.get('tipo') == 'comparativa' and len(docs) < 2:
            avisos.append(f'{pos}: una comparativa con un solo documento no compara nada')
        if re.search(r'seg[uú]n el (texto|art[ií]culo|documento)|en el (texto|art[ií]culo)',
                     str(r.get('pregunta', '')), re.I):
            avisos.append(f'{pos}: la pregunta dice "según el texto"; no se sostiene sola')
        if not str(r.get('evidencia_literal', '')).strip() and r.get('tipo') not in SIN_DOCS:
            avisos.append(f'{pos}: sin evidencia_literal; no se podrá verificar la respuesta')

    # ¿Los documentos citados están en el subconjunto indexado?
    if args.ids:
        with open(args.ids, encoding='utf-8') as f:
            indexados = {l.strip() for l in f if l.strip()}
        faltan = sorted(docs_citados - indexados)
        for d in faltan:
            errores.append(f'document_id "{d}" no está en {args.ids}: nunca se podrá recuperar')

    # ¿La evidencia literal está de verdad en el documento?
    verificadas = no_encontradas = 0
    if args.corpus:
        import pyarrow.parquet as pq
        necesarios = {}
        for _, r in filas:
            ev = str(r.get('evidencia_literal', '')).strip()
            if ev:
                for d in dict.fromkeys(r.get('documentos_relevantes', [])):
                    necesarios.setdefault(d, [])
        textos = {}
        if necesarios:
            parq = pq.ParquetFile(args.corpus)
            for batch in parq.iter_batches(batch_size=4096, columns=['document_id', 'text']):
                for row in batch.to_pylist():
                    if row['document_id'] in necesarios:
                        textos[row['document_id']] = norm(row['text'] or '')
                if len(textos) == len(necesarios):
                    break
        for d in necesarios:
            if not textos.get(d):
                errores.append(f'document_id "{d}" no existe en {args.corpus}')
        for _, r in filas:
            qid = r.get('question_id')
            evs = [x.strip() for x in str(r.get('evidencia_literal', '')).split('||') if x.strip()]
            docs = [d for d in dict.fromkeys(r.get('documentos_relevantes', [])) if textos.get(d)]
            if not evs or not docs:
                continue
            if len(evs) == 1:  # una sola frase: debe estar en todos los documentos
                for d in docs:
                    verificadas += 1
                    if norm(evs[0]) not in textos[d]:
                        no_encontradas += 1
                        errores.append(f'{qid}: la evidencia literal no aparece en el documento {d}')
            else:  # varias frases (separadas por ||): cada una en algún documento y cada documento con alguna
                for ev in evs:
                    verificadas += 1
                    if not any(norm(ev) in textos[d] for d in docs):
                        no_encontradas += 1
                        errores.append(f'{qid}: la frase "{ev[:60]}…" no aparece en ninguno de los documentos')
                for d in docs:
                    if not any(norm(ev) in textos[d] for ev in evs):
                        errores.append(f'{qid}: el documento {d} no contiene ninguna de las frases de evidencia')

    total = len(filas)
    por = lambda k: dict(Counter(r.get(k) for _, r in filas))
    cruce = Counter((r.get('split'), r.get('tipo')) for _, r in filas)
    resumen = {
        'archivo': args.gold, 'preguntas': total,
        'minimo_requerido': args.minimo, 'cumple_minimo': total >= args.minimo,
        'por_tipo': por('tipo'), 'por_idioma': por('idioma'),
        'por_dificultad': por('dificultad'), 'por_split': por('split'),
        'por_origen': por('origen'),
        'split_x_tipo': {f'{s}|{t}': n for (s, t), n in sorted(cruce.items(), key=lambda x: str(x[0]))},
        'documentos_distintos_citados': len(docs_citados),
        'evidencias_verificadas': verificadas, 'evidencias_no_encontradas': no_encontradas,
        'errores': len(errores), 'avisos': len(avisos),
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    for a in avisos:
        print('AVISO  ' + a, file=sys.stderr)
    for e in errores:
        print('ERROR  ' + e, file=sys.stderr)
    if total < args.minimo:
        print(f'ERROR  solo hay {total} preguntas; el taller pide al menos {args.minimo}', file=sys.stderr)
    sys.exit(1 if errores or total < args.minimo else 0)


if __name__ == '__main__':
    main()
