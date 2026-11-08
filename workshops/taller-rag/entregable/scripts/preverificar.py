"""Pre-verifica las preguntas de la plantilla: busca sus palabras en el corpus de una vez.

No decide nada. Para cada pregunta con palabras_busqueda escribe un informe con el número de
coincidencias y los fragmentos EXACTOS de los primeros documentos (copiables como evidencia).
La decisión (verificada, descartada, etc.) la toma una persona, leyendo el informe.

Lee el corpus UNA sola vez para todas las preguntas.

Uso:
  python -m scripts.preverificar --plantilla data/gold/plantilla_gold.xlsx \
      --input data/documentos_rag.parquet --salida data/gold/preverificacion.md
"""
import argparse, os, sys
from datetime import date

import pyarrow.parquet as pq
from openpyxl import load_workbook

from scripts.buscar_candidatos import normalizar

# Ventanas temporales de las preguntas que las necesitan (las demás buscan en todo el corpus).
VENTANAS = {
    'S17': ('2026-01-01', None),
    'S20': ('2025-01-01', '2025-06-30'),
    'S21': ('2025-01-01', '2025-12-31'),
}


def buscar_todas(parquet, consultas, maximo=3, contexto=300):
    """Una sola pasada por el corpus para todas las consultas (modo: todas las palabras).

    consultas: lista de dicts con 'qid', 'palabras' (ya normalizadas), 'desde', 'hasta'.
    Devuelve {qid: (total, muestra)}.
    """
    pf = pq.ParquetFile(parquet)
    cols = [c for c in ['document_id', 'text', 'source', 'lang', 'created_at_utc']
            if c in pf.schema_arrow.names]
    res = {c['qid']: [0, []] for c in consultas}
    for lote in pf.iter_batches(batch_size=4096, columns=cols):
        for r in lote.to_pylist():
            fecha = str(r.get('created_at_utc') or '')[:10]
            texto = r.get('text') or ''
            hay = normalizar(texto)  # se normaliza una vez por documento, no una vez por pregunta
            for c in consultas:
                if c['desde'] and (not fecha or fecha < c['desde']):
                    continue
                if c['hasta'] and (not fecha or fecha > c['hasta']):
                    continue
                posiciones = [hay.find(w) for w in c['palabras']]
                if any(p < 0 for p in posiciones):
                    continue  # debe aparecer TODAS las palabras
                acum = res[c['qid']]
                acum[0] += 1
                if len(acum[1]) < maximo:
                    ini = max(0, min(posiciones) - contexto // 3)
                    fin = min(len(texto), ini + contexto)
                    acum[1].append({'document_id': r.get('document_id'), 'fuente': r.get('source'),
                                    'idioma': r.get('lang'), 'fecha': fecha or 'sin fecha',
                                    'fragmento': texto[ini:fin].replace('\n', ' ')})
    return {qid: (v[0], v[1]) for qid, v in res.items()}


def marca(tipo, total):
    if tipo == 'sin_evidencia':
        return ('REVISAR: hay coincidencias, puede tener respuesta' if total
                else 'CANDIDATA: sin coincidencias; confirmar leyendo')
    if total == 0:
        return 'SIN COINCIDENCIAS: revisar palabras o cambiar la pregunta'
    return f'{total} coincidencias: leer los primeros documentos'


def leer_preguntas(plantilla):
    ws = load_workbook(plantilla, data_only=True)['Preguntas']
    cab = [c.value for c in ws[1]]
    idx = {n: i for i, n in enumerate(cab) if n}
    preguntas = []
    for fila in ws.iter_rows(min_row=2, values_only=True):
        r = {n: ('' if fila[i] is None else str(fila[i]).strip()) for n, i in idx.items()}
        if r.get('estado') == 'descartada' or not r.get('pregunta') or not r.get('palabras_busqueda'):
            continue
        palabras = [x.strip() for x in r['palabras_busqueda'].split(';') if x.strip()]
        if not palabras:
            continue
        r['_palabras'] = palabras
        preguntas.append(r)
    return preguntas


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plantilla', default='data/gold/plantilla_gold.xlsx')
    p.add_argument('--input', default='data/documentos_rag.parquet')
    p.add_argument('--salida', default='data/gold/preverificacion.md')
    a = p.parse_args()

    preguntas = leer_preguntas(a.plantilla)
    if not preguntas:
        sys.exit('No hay preguntas con palabras_busqueda que no estén descartadas.')

    consultas = []
    for r in preguntas:
        qid = r.get('question_id', '?')
        desde, hasta = VENTANAS.get(qid, (None, None))
        consultas.append({'qid': qid, 'palabras': [normalizar(x) for x in r['_palabras']],
                          'desde': desde, 'hasta': hasta})
    resultados = buscar_todas(a.input, consultas)

    resumen, detalle = [], []
    for r in preguntas:
        qid = r.get('question_id', '?')
        tipo = r.get('tipo', '')
        desde, hasta = VENTANAS.get(qid, (None, None))
        total, muestra = resultados[qid]
        estado = marca(tipo, total)
        resumen.append((qid, tipo, total, estado))

        detalle += [f'## {qid} · {tipo} · {r.get("idioma", "")}', '',
                    f'**Pregunta:** {r["pregunta"]}', '',
                    f'**Palabras:** {" + ".join(r["_palabras"])}'
                    + (f' · ventana {desde} a {hasta or "hoy"}' if desde else ''), '',
                    f'**Resultado:** {estado}', '']
        for i, m in enumerate(muestra, 1):
            detalle += [f'{i}. `{m["document_id"]}` · {m["fuente"]} · {m["idioma"]} · {m["fecha"]}',
                        f'   > {m["fragmento"]}', '']
        if total == 0:
            detalle += ['_Sin fragmentos para mostrar._', '']

    cabecera = ['# Preverificación de preguntas', '',
                f'Generado el {date.today().isoformat()} sobre `{a.input}`.', '',
                'Los fragmentos son texto exacto del corpus. Este informe no decide nada: '
                'cada pregunta se confirma o descarta leyendo el documento.', '',
                '| ID | Tipo | Coincidencias | Resultado |', '|---|---|---:|---|']
    cabecera += [f'| {q} | {t} | {n} | {e} |' for q, t, n, e in resumen]
    cabecera += ['', '---', '']

    os.makedirs(os.path.dirname(a.salida) or '.', exist_ok=True)
    with open(a.salida, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cabecera + detalle) + '\n')

    print(f'{"ID":6}{"TIPO":18}{"HITS":>8}  RESULTADO')
    for qid, tipo, total, estado in resumen:
        print(f'{qid:6}{tipo:18}{total:>8}  {estado}')
    print(f'\nInforme: {a.salida}')


if __name__ == '__main__':
    sys.exit(main())
