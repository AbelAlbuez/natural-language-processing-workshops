"""Plantilla de Excel para el gold estándar y su conversión a gold.jsonl.

  plantilla  Crea el libro de Excel: instrucciones, listas desplegables, ejemplos y las
             preguntas sintéticas candidatas (todavía sin verificar).
  convertir  Lee el libro, toma solo las filas con estado "verificada", las valida y escribe
             gold.jsonl. Las demás filas quedan en pendientes.jsonl. Si hay errores, no
             escribe nada: así nunca queda un gold a medio corregir.

Uso:
  python -m scripts.gold_excel plantilla --salida data/gold/plantilla_gold.xlsx \
      --sinteticas docs/gold/preguntas_sinteticas.jsonl --filas-vacias 30
  python -m scripts.gold_excel convertir --entrada data/gold/plantilla_gold.xlsx \
      --salida-dir data/gold
"""
import argparse, json, os, re, sys
from collections import Counter
from datetime import date

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# (columna, ancho, ayuda que aparece al pasar el cursor sobre el encabezado)
COLUMNAS = [
    ('question_id', 12, 'Identificador único. T01… son las preguntas del profesor; S01… las sintéticas. No repetir.'),
    ('split', 9, 'dev o test. Las de test no se usan para ajustar el sistema.'),
    ('pregunta', 60, 'Escríbela como la escribiría un usuario real, sin copiar frases del documento.'),
    ('idioma', 9, 'es o en.'),
    ('tipo', 16, 'factual, interpretativa, comparativa, sin_evidencia, adversarial o temporal.'),
    ('dificultad', 12, 'facil, media o dificil.'),
    ('fuente_esperada', 16, 'media_cloud, gdelt, bluesky, mixta o ninguna.'),
    ('palabras_busqueda', 28, 'Palabras para buscar con buscar_candidatos, separadas por ;. Deben aparecer todas.'),
    ('documentos_relevantes', 38, 'document_id de los documentos que responden, separados por ;. Vacío en sin_evidencia.'),
    ('criterio_correccion', 50, 'Qué debe contener una respuesta correcta. Escríbelo ANTES de mirar lo que responde el sistema.'),
    ('respuesta_referencia', 40, 'Respuesta corta, tal como la dice el documento.'),
    ('evidencia_literal', 50, 'Frase copiada textualmente del documento (máximo 300 caracteres). Si hay varios documentos (comparativa), una frase por documento separadas por ||.'),
    ('origen', 15, 'manual; llm_generada (sin revisar); llm_revisado (la revisó una persona).'),
    ('estado', 15, 'por_verificar, borrador, verificada o descartada. Solo verificada entra al gold.'),
    ('anotador', 10, 'Tus iniciales.'),
    ('notas', 40, 'Lo que haga falta recordar.'),
]
OBLIGATORIAS = ['question_id', 'split', 'pregunta', 'idioma', 'tipo', 'dificultad',
                'documentos_relevantes', 'origen', 'estado']
LISTAS = {
    'split': ['dev', 'test'],
    'idioma': ['es', 'en'],
    'tipo': ['factual', 'interpretativa', 'comparativa', 'sin_evidencia', 'adversarial', 'temporal'],
    'dificultad': ['facil', 'media', 'dificil'],
    'fuente_esperada': ['media_cloud', 'gdelt', 'bluesky', 'mixta', 'ninguna'],
    'origen': ['manual', 'llm_generada', 'llm_revisado'],
    'estado': ['por_verificar', 'borrador', 'verificada', 'descartada'],
}
SIN_DOCS = {'sin_evidencia'}
DOCS_OPCIONALES = {'sin_evidencia', 'adversarial'}

INSTRUCCIONES = [
    'Cómo usar esta plantilla',
    '',
    '1. Escriba una pregunta por fila en la hoja Preguntas. Las filas T01 a T30 son para sus preguntas.',
    '   Las filas S son preguntas sintéticas candidatas: no están verificadas y deben revisarse una por una.',
    '2. Busque los documentos que responden cada pregunta con el comando buscar_candidatos y LÉALOS.',
    '   Copie sus document_id en documentos_relevantes, separados por punto y coma.',
    '3. Escriba criterio_correccion ANTES de mirar la respuesta del sistema. Así no lo ajusta a la respuesta.',
    '4. Copie en evidencia_literal la frase exacta del documento. El conversor no la verifica; el validador sí.',
    '5. Cuando la fila esté revisada, cambie estado a verificada. Ponga origen en llm_revisado si la generó',
    '   un modelo, o en manual si la escribió usted.',
    '6. Solo las filas verificadas entran a gold.jsonl. El resto queda en pendientes.jsonl.',
    '',
    'Tipos de pregunta y qué se espera del sistema',
    '- factual: un dato concreto del documento. Se responde con ese dato.',
    '- interpretativa: causa, motivo o posición de un actor. Exige entender el texto.',
    '- comparativa: contrasta dos fuentes (prensa y Bluesky). Necesita documentos de ambas.',
    '- sin_evidencia: el corpus NO responde. Lo correcto es abstenerse. Deje documentos_relevantes vacío',
    '  y confirme con buscar_candidatos que no haya coincidencias. Si las hay, no es sin_evidencia.',
    '- adversarial: la pregunta trae una premisa falsa. Lo correcto es corregirla con la evidencia.',
    '- temporal: pregunta acotada a una fecha o periodo. Un documento de otra fecha es un error.',
    '',
    'No cambie el question_id una vez asignado: el historial de resultados depende de él.',
]

EJEMPLOS = [
    ('factual', '¿Cuándo aprobó el Parlamento Europeo la Ley de Restauración de la Naturaleza?',
     'Se entiende sin leer el documento y pide un dato que el texto debe dar. Buena para medir recuperación.'),
    ('factual (mala)', 'Según el artículo, ¿cuándo se votó la ley?',
     'Depende de un texto que el usuario no ve. Quite la referencia al artículo.'),
    ('copia literal (mala)', 'Parlamento Europeo aprobó estrecha Restauración Naturaleza',
     'Repite palabras del documento. Mide coincidencia de palabras, no comprensión.'),
    ('interpretativa', '¿Qué críticas aparecen contra eliminar las reglas de neutralidad de nutrientes en Inglaterra?',
     'Exige entender el texto y resumir posiciones. No basta con localizar una palabra.'),
    ('comparativa', '¿En qué difieren las noticias y las publicaciones de Bluesky al hablar de la COP16?',
     'Necesita al menos un documento de prensa y uno de Bluesky, así que tendrá dos document_id.'),
    ('sin_evidencia', '¿Cuál fue el resultado del partido de la Selección Colombia en las eliminatorias?',
     'Tema fuera del corpus. Lo correcto es abstenerse. Verifique con buscar_candidatos que no haya coincidencias.'),
    ('sin_evidencia (mala)', '¿Qué piensan los usuarios de Bluesky sobre la COP16?',
     'Parece sin respuesta, pero el corpus sí tiene publicaciones sobre la COP16. Si lo verifica, es factual.'),
    ('adversarial', '¿Por qué la COP16 se realizó en Bogotá?',
     'Premisa falsa: lo correcto es corregirla con la evidencia. La etiqueta del corpus sugiere Cali; confírmelo en el texto.'),
    ('temporal', '¿Qué se informó sobre la deforestación en Colombia durante el primer semestre de 2025?',
     'Acotada a una fecha. Si el sistema cita un documento de otro periodo, falla.'),
]


def _celda(v):
    if v is None:
        return ''
    if isinstance(v, list):
        return ';'.join(str(x) for x in v)
    return str(v)


def _texto(v):
    return '' if v is None else str(v).strip()


def _estilo_cabecera(ws, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1F4E5A')
        cell.alignment = Alignment(wrap_text=True, vertical='center')


def plantilla(salida, sinteticas, vacias):
    wb = Workbook()

    wi = wb.active
    wi.title = 'Instrucciones'
    wi.column_dimensions['A'].width = 120
    for linea in INSTRUCCIONES:
        wi.append([linea])
    for row in wi.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical='top')
    wi['A1'].font = Font(bold=True, size=14)

    wp = wb.create_sheet('Preguntas')
    cols = [c[0] for c in COLUMNAS]
    wp.append(cols)
    _estilo_cabecera(wp, len(cols))
    for i, (nombre, ancho, ayuda) in enumerate(COLUMNAS, 1):
        wp.column_dimensions[get_column_letter(i)].width = ancho
        wp.cell(row=1, column=i).comment = Comment(ayuda, 'gold')

    filas = []
    if sinteticas:
        with open(sinteticas, encoding='utf-8') as f:
            filas += [json.loads(l) for l in f if l.strip()]
    for i in range(vacias):
        filas.append({'question_id': f'T{i + 1:02d}', 'split': 'test'})
    for r in filas:
        wp.append([_celda(r.get(c)) for c in cols])
    for row in wp.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical='top')
    wp.freeze_panes = 'C2'

    ultimo = max(wp.max_row, 2) + 200
    for campo, valores in LISTAS.items():
        letra = get_column_letter(cols.index(campo) + 1)
        dv = DataValidation(type='list', formula1='"' + ','.join(valores) + '"', allow_blank=True)
        dv.error = 'Elija un valor de la lista.'
        dv.errorTitle = 'Valor no válido'
        wp.add_data_validation(dv)
        dv.add(f'{letra}2:{letra}{ultimo}')

    we = wb.create_sheet('Ejemplos')
    we.append(['Tipo', 'Ejemplo de pregunta', 'Por qué'])
    _estilo_cabecera(we, 3)
    for fila in EJEMPLOS:
        we.append(list(fila))
    we.column_dimensions['A'].width = 22
    we.column_dimensions['B'].width = 70
    we.column_dimensions['C'].width = 75
    for row in we.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical='top')

    wl = wb.create_sheet('Listas')
    wl.append(list(LISTAS.keys()))
    _estilo_cabecera(wl, len(LISTAS))
    largo = max(len(v) for v in LISTAS.values())
    for i in range(largo):
        wl.append([v[i] if i < len(v) else '' for v in LISTAS.values()])
    for i in range(1, len(LISTAS) + 1):
        wl.column_dimensions[get_column_letter(i)].width = 18

    os.makedirs(os.path.dirname(salida) or '.', exist_ok=True)
    wb.save(salida)
    return {'salida': salida, 'preguntas_sinteticas': len(filas) - vacias,
            'filas_vacias': vacias}


def _validar_y_construir(r, fecha):
    e = []
    pos = f"fila {r['_fila']} ({r.get('question_id') or 'sin id'})"
    for campo in ['question_id', 'pregunta', 'split', 'idioma', 'tipo', 'dificultad', 'origen']:
        if not r.get(campo):
            e.append(f'{pos}: falta {campo}')
    for campo in ['split', 'idioma', 'tipo', 'dificultad']:
        if r.get(campo) and r[campo] not in LISTAS[campo]:
            e.append(f'{pos}: {campo} "{r[campo]}" no válido; use {LISTAS[campo]}')
    if r.get('origen') == 'llm_generada':
        e.append(f'{pos}: origen sigue en llm_generada. Tras revisarla, cámbielo a llm_revisado')
    elif r.get('origen') and r['origen'] not in ('manual', 'llm_revisado'):
        e.append(f'{pos}: origen "{r["origen"]}" no válido')

    docs = [d for d in re.split(r'[;,\s]+', r.get('documentos_relevantes', '')) if d]
    tipo = r.get('tipo')
    if tipo in SIN_DOCS and docs:
        e.append(f'{pos}: sin_evidencia no debe tener documentos. Si los tiene, no es sin_evidencia')
    if tipo not in DOCS_OPCIONALES and not docs:
        e.append(f'{pos}: faltan documentos_relevantes')
    if len(docs) != len(set(docs)):
        e.append(f'{pos}: documentos_relevantes repite algún id')
    if tipo == 'comparativa' and len(set(docs)) < 2:
        e.append(f'{pos}: una comparativa necesita al menos dos documentos (prensa y Bluesky)')
    if docs and not r.get('evidencia_literal'):
        e.append(f'{pos}: hay documentos pero falta evidencia_literal')
    for frag in r.get('evidencia_literal', '').split('||'):
        if len(frag.strip()) > 300:
            e.append(f'{pos}: una frase de evidencia_literal pasa de 300 caracteres (separe varias frases con ||)')
    if not r.get('criterio_correccion'):
        e.append(f'{pos}: falta criterio_correccion; sin él no se puede juzgar la respuesta')
    if e:
        return e, None

    item = {
        'question_id': r['question_id'], 'pregunta': r['pregunta'], 'idioma': r['idioma'],
        'tipo': tipo, 'dificultad': r['dificultad'],
        'fuente_esperada': r.get('fuente_esperada') or None,
        'documentos_relevantes': list(dict.fromkeys(docs)),
        'respuesta_referencia': r.get('respuesta_referencia', ''),
        'evidencia_literal': r.get('evidencia_literal', ''),
        'evidencias': [x.strip() for x in r.get('evidencia_literal', '').split('||') if x.strip()],
        'criterio_correccion': r['criterio_correccion'],
        'split': r['split'], 'origen': r['origen'],
        'anotadores': [r['anotador']] if r.get('anotador') else [],
        'notas': r.get('notas', ''), 'creada': fecha,
    }
    return [], item


def convertir(entrada, salida_dir, fecha):
    wb = load_workbook(entrada, data_only=True)
    if 'Preguntas' not in wb.sheetnames:
        raise SystemExit('El libro no tiene una hoja llamada "Preguntas".')
    ws = wb['Preguntas']
    cab = [_texto(c.value) for c in ws[1]]
    faltan = [c for c in OBLIGATORIAS if c not in cab]
    if faltan:
        raise SystemExit(f'Faltan columnas en la hoja Preguntas: {faltan}')

    filas = []
    for n, valores in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        r = {cab[i]: _texto(v) for i, v in enumerate(valores) if i < len(cab) and cab[i]}
        if not (r.get('pregunta') or r.get('estado') or r.get('documentos_relevantes')):
            continue
        r['_fila'] = n
        filas.append(r)

    errores = []
    for qid, k in Counter(r.get('question_id') for r in filas if r.get('question_id')).items():
        if k > 1:
            errores.append(f'question_id "{qid}" aparece {k} veces')

    estados = Counter(r.get('estado') or 'por_verificar' for r in filas)
    gold, pendientes = [], []
    for r in filas:
        estado = r.get('estado') or 'por_verificar'
        if estado != 'verificada':
            pendientes.append({'fila': r['_fila'], 'question_id': r.get('question_id', ''),
                               'estado': estado, 'pregunta': r.get('pregunta', '')})
            continue
        e, item = _validar_y_construir(r, fecha)
        errores += e
        if item:
            gold.append(item)

    if errores:
        for e in errores:
            print('ERROR  ' + e, file=sys.stderr)
        print(f'No se escribió nada: {len(errores)} error(es). Corríjalos y vuelva a convertir.',
              file=sys.stderr)
        sys.exit(1)

    os.makedirs(salida_dir, exist_ok=True)
    ruta_gold = os.path.join(salida_dir, 'gold.jsonl')
    ruta_pend = os.path.join(salida_dir, 'pendientes.jsonl')
    with open(ruta_gold, 'w', encoding='utf-8') as f:
        for item in gold:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    with open(ruta_pend, 'w', encoding='utf-8') as f:
        for item in pendientes:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    return {'filas_con_contenido': len(filas), 'estados': dict(estados),
            'escritas_en_gold': len(gold), 'pendientes': len(pendientes),
            'gold': ruta_gold, 'pendientes_archivo': ruta_pend}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('plantilla')
    a.add_argument('--salida', default='data/gold/plantilla_gold.xlsx')
    a.add_argument('--sinteticas', default=None, help='jsonl de preguntas sintéticas candidatas')
    a.add_argument('--filas-vacias', type=int, default=30)
    b = sub.add_parser('convertir')
    b.add_argument('--entrada', required=True)
    b.add_argument('--salida-dir', default='data/gold')
    b.add_argument('--fecha', default=date.today().isoformat())
    args = p.parse_args()
    if args.cmd == 'plantilla':
        print(json.dumps(plantilla(args.salida, args.sinteticas, args.filas_vacias),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(convertir(args.entrada, args.salida_dir, args.fecha),
                         ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
