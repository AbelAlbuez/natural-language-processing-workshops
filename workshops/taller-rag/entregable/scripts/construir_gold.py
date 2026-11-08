"""Constructor del gold standard sintético a partir de las cuotas.

Qué hace, en dos pasos:
  1. `candidatos`: elige con semilla 42 chunks candidatos por estrato (fuente e idioma)
     de documentos sin duplicados y con longitud mínima; en Bluesky prefiere etiquetas de
     tema distintas. Toma el primer chunk (chunk_index 0) de cada documento.
  2. `construir`: asocia cada candidato usado con su pregunta y respuesta de referencia
     (diccionario QA de este archivo), asigna desarrollo o prueba dentro de cada estrato
     con semilla 42 según las cuotas, usa las listas de IDs de §4 del protocolo y añade
     las 6 preguntas no respondibles (NO_RESP).

Las preguntas y respuestas de QA se redactaron a partir del texto de cada chunk
candidato, con asistencia de IA, y están pendientes de revisión humana
(validada_por = "pendiente de revisión humana"). Cada respuesta se deduce solo de su
chunk. Las claves C00, C01... son posiciones en el archivo de candidatos: reproducirlas
exige los mismos datos de entrada y la misma semilla.

Lee:      data/documentos_rag.parquet y data/chunks_tok256.parquet (candidatos);
          data/gold_candidatos.json (construir).
Escribe:  data/gold_candidatos.json (contiene texto de chunks; data/ no se versiona);
          docs/gold_standard.csv, docs/cuotas_gold.json y data/gold_trazabilidad.json.
          No sobrescribe archivos existentes salvo con --sobrescribir.

Uso:
    python -m scripts.construir_gold candidatos
    python -m scripts.construir_gold construir [--sobrescribir]
No imprime texto de preguntas, respuestas ni documentos: solo conteos.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import random
from pathlib import Path

SEMILLA = 42
# Candidatos por estrato (fuente, idioma): necesarias en el gold, con margen.
NECESARIAS = {("bluesky", "en"): 8, ("bluesky", "es"): 4, ("gdelt", "es"): 1,
              ("media_cloud", "en"): 8, ("media_cloud", "es"): 13}
MARGEN = 1.6

# Preguntas y respuestas de referencia por candidato: (idioma, pregunta, respuesta).
QA = {
 # Bluesky en
 "C00": ("en", "According to a Bluesky post, during which historical period did the Earth's temperature begin to rise because of the mass burning of fossil fuels?",
         "The post says it began with the second industrial revolution, which was huge in the UK and started the mass burning of fossil fuels."),
 "C01": ("en", "Which organisation's petition did a Bluesky post urge people worldwide to sign to help the UK get safe and clean water?",
         "We Own It; the post asked people in any country to sign its petition for safe and clean water in the UK."),
 "C03": ("en", "According to a Bluesky post, through which mechanism might progress be sought after the inaction on Copper Mark complaints?",
         "Through the OECD National Contact Points, including the one in the UK."),
 "C04": ("en", "In which three countries does a Bluesky post say plastic-free lifestyle apps help individuals reduce plastic pollution?",
         "The USA, the UK and Canada."),
 "C06": ("en", "According to a Bluesky post, what was the magnitude of the earthquake that struck western Colombia days after Abelardo De La Espriella was sworn in as president?",
         "The post reports a magnitude 7.4 earthquake."),
 "C08": ("en", "According to a Bluesky post citing scientists, on which kind of pollution is the UK falling behind the EU and the US?",
         "Microplastics pollution; the EU and the US are already introducing enforceable targets and limits on microplastics in water."),
 "C09": ("en", "Which two countries does a Bluesky post hope will face pressure to stop buying Russian oil, and which pipeline has Ukraine attacked?",
         "Hungary and Slovakia; Ukraine has attacked the Druzhba pipeline."),
 "C11": ("en", "Which beetle was highlighted at Sherwood National Nature Reserve in a Bluesky post, and what is its conservation status?",
         "The Hazel Pot Beetle, which the post describes as a UK LBAP priority species and one of Nottinghamshire's highlights."),
 # Bluesky es
 "C13": ("es", "Según una publicación en Bluesky, ¿qué político opositor al Gobierno de Gustavo Petro regresa a la campaña electoral?",
         "Germán Vargas Lleras, descrito como uno de los políticos más curtidos de Colombia y uno de los opositores más vocales a Petro."),
 "C14": ("es", "Según una publicación en Bluesky, ¿qué enviará Colombia a Venezuela tras los terremotos?",
         "Un hospital de campaña para apoyar la atención médica de los afectados y reforzar la respuesta humanitaria."),
 "C16": ("es", "Según una publicación en Bluesky, ¿qué límite de calentamiento global se busca no superar con las demandas trasladadas al Gobierno de Pedro Sánchez para las negociaciones de Santa Marta?",
         "El límite crítico de 1,5 °C."),
 "C17": ("es", "Según una publicación en Bluesky, ¿qué encuentro reunió en Cartagena a delegaciones de más de 100 países para discutir la reforma agraria?",
         "El ICARRD+20, donde organizaciones campesinas, negras e indígenas discutieron una hoja de ruta para profundizar los cambios en el campo."),
 # GDELT es
 "C19": ("es", "¿Qué frase dijo el intendente Juan Pablo Poletti al anunciar las acciones preventivas de Santa Fe ante un posible episodio de El Niño?",
         "Dijo «Tenemos que prepararnos para el peor escenario» al anunciar las acciones preventivas del municipio."),
 # Media Cloud en
 "C22": ("en", "Why did Boris Johnson visit Solihull, and how did he describe the HS2 rail project to its critics?",
         "He visited the HS2 Interchange Station site and said HS2 was the cleanest and greenest way to travel up and down the country."),
 "C24": ("en", "What did a recent study find about urban ecology citizen science projects in Australia?",
         "It found that the number and diversity of urban ecology citizen science projects in Australia is relatively low."),
 "C25": ("en", "What did young people from the group Climate Generation ask the Minnesota Youth Council to support?",
         "A bill requiring schools to teach more about climate change."),
 "C26": ("en", "What legal status did a U.S. federal court order give to the offspring of Pablo Escobar's hippos?",
         "They can be recognized as people or 'interested persons' with legal rights in the U.S.; the order has no effect in Colombia."),
 "C28": ("en", "According to Oceana's analysis of Global Fishing Watch data, how many hours of suspected bottom trawling took place in the UK's offshore marine protected areas in 2023?",
         "At least 33,000 hours, out of more than 100,000 hours of apparent industrial fishing in those areas."),
 "C30": ("en", "According to research published in Nature Sustainability, what did governments ignore when approving the groundwater plans of Adani's Carmichael coal mine?",
         "Independent scientific advice; governments repeatedly ignored it and failed to compel Adani to fully investigate the environmental risks of its water plans."),
 "C31": ("en", "How much did the Langholm community buyout raise for its second stage, and which nature reserve will it double in size?",
         "It reached its £2.2m target by the 31 July deadline, which will double the size of the Tarras Valley Nature Reserve."),
 "C34": ("en", "According to a large-scale study of 885 European cities, what share of them had climate adaptation plans?",
         "Only 47% had adaptation plans in place."),
 # Media Cloud es
 "C36": ("es", "Según un artículo sobre el Foro mundial del agua en Brasilia, ¿qué porcentaje de los habitantes del mundo ya sufre escasez de agua potable?",
         "El 40 %, con el riesgo de que en 2025 la sufra un 15 % más."),
 "C37": ("es", "¿Qué día se conmemora el Día Mundial de Lucha contra la Desertificación y la Sequía y cuál es el lema mencionado en el artículo?",
         "Se conmemora cada 17 de junio y el lema es «Restaurar la tierra. Liberar las oportunidades»."),
 "C39": ("es", "¿Qué proyecto de ley aprobó en primer debate la Comisión Segunda del Senado de Colombia para ratificar el Acuerdo de Escazú?",
         "El Proyecto de Ley 251 de 2021, aprobado el 26 de abril."),
 "C41": ("es", "¿Qué premio recibió el presidente Iván Duque durante su visita oficial a Estados Unidos y por qué política?",
         "El premio del instituto ICCF Teddy Roosevelt, por la política «Producir Conservando y Conservar Produciendo»."),
 "C42": ("es", "¿A cuántas familias beneficiará el programa 'Mi Techo Propio' lanzado por el alcalde Alex Char en Barranquilla?",
         "A 10.000 familias durante el cuatrienio."),
 "C44": ("es", "Según un artículo sobre turismo sostenible, ¿cuántas personas de otros países llegaron a Colombia en 2017?",
         "Más de 6,5 millones de personas, una cifra récord."),
 "C45": ("es", "¿Dónde se encuentra el Mirador de San Carlos y en qué año se inauguró?",
         "En Nuevo Guaymas, en el estado de Sonora (México); se inauguró en 2018."),
 "C47": ("es", "¿Cuánto proyecta el Grupo Cibest de Bancolombia que promediará el precio del dólar en Colombia durante 2026?",
         "Proyecta un promedio de $3.878 pesos durante 2026."),
 "C48": ("es", "¿Con qué sobrenombre se conoce a la ciudad de Tortosa, en Tarragona?",
         "Como la «ciudad del Renacimiento»."),
 "C49": ("es", "¿Cuántas hectáreas administra Parques Nacionales Naturales de Colombia y qué porcentaje de la representatividad ecosistémica cubre junto con el SINAP?",
         "Más de 38 millones de hectáreas; junto con el SINAP cubre casi 50 millones, el 83 % de la representatividad ecosistémica del país."),
 "C51": ("es", "¿Cuántas plántulas de mangle se restauraron en la Ciénaga Grande de Santa Marta y qué organización comunitaria ha liderado la restauración?",
         "14 mil plántulas; la restauración la ha liderado la Fundación Ambiental de Mujeres del Magdalena (Fundamag)."),
 "C54": ("es", "¿Qué organizaciones ganaron la quinta edición de los Premios a la Protección del Medio Ambiente de Caracol Televisión?",
         "El Grupo EPM, la Fundación Biodiversa Colombia y la Asociación de usuarios de agua de los ríos Tuluá y Morales (Asurtumo)."),
 "C55": ("es", "¿Qué montos exigía un profesor de la Secretaría de Educación de Antioquia a sus colegas a cambio de tramitar traslados?",
         "Entre 2.500.000 y 6.000.000 de pesos por traslado; se estima que recibió alrededor de 40 millones de pesos."),
}
NO_RESP = {
 "desarrollo": [("es", "¿Cuál es la receta tradicional de la paella valenciana?"),
                ("en", "Which national team won the 2018 FIFA World Cup final?"),
                ("en", "How do you reverse a linked list in Python?")],
 "prueba": [("es", "¿Cuántos minutos se deben hornear unas galletas de avena con chocolate?"),
            ("en", "Which player holds the record for the most men's singles Grand Slam tennis titles?"),
            ("es", "¿Cómo se declara una variable constante en JavaScript?")],
}

CUOTAS = {("bluesky", "en"): (4, 4), ("bluesky", "es"): (2, 2), ("gdelt", "es"): (0, 1),
          ("media_cloud", "en"): (4, 4), ("media_cloud", "es"): (7, 6)}
DEV = "G01 G02 G04 G09 G10 G12 G14 G16 G17 G18 G20 G21 G25 G27 G30 G31 G32 G33 G36 G39".split()
TEST = "G03 G05 G06 G07 G08 G11 G13 G15 G19 G22 G23 G24 G26 G28 G29 G34 G35 G37 G38 G40".split()
NR_IDS = {"desarrollo": ["G33", "G36", "G39"], "prueba": ["G37", "G38", "G40"]}
COLUMNAS = ["id", "pregunta", "idioma", "tipo", "fuente_esperada", "tema", "respuesta_referencia",
            "evidencia_doc_id", "split", "validada_por"]
PENDIENTE = "pendiente de revisión humana"


def _no_sobrescribir(paths, sobrescribir):
    existentes = [str(p) for p in paths if Path(p).exists()]
    if existentes and not sobrescribir:
        raise SystemExit(f"Ya existen {existentes}; use --sobrescribir para reemplazarlos.")


def seleccionar_candidatos(documentos, chunks):
    """Devuelve la lista de candidatos (con texto del chunk) en un orden reproducible."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    rng = random.Random(SEMILLA)
    docs = pq.read_table(documentos, columns=["document_id", "source", "lang", "collection_keyword_label",
                                              "dup_count", "word_count"]).to_pylist()
    meta = {d["document_id"]: d for d in docs}
    pool = {}
    for d in docs:
        key = (d["source"], d["lang"])
        if key not in NECESARIAS or (d["dup_count"] or 1) > 1:
            continue
        if d["source"] == "bluesky" and (not d["collection_keyword_label"] or (d["word_count"] or 0) < 30):
            continue
        if d["source"] != "bluesky" and (d["word_count"] or 0) < 150:
            continue
        pool.setdefault(key, []).append(d["document_id"])
    elegidos = []
    for key, n in NECESARIAS.items():
        ids = sorted(pool[key])
        rng.shuffle(ids)
        quiero = max(n + 2, round(n * MARGEN))
        tomados, etiquetas = [], set()
        for doc_id in ids:  # Bluesky: preferir etiquetas no usadas
            etiqueta = meta[doc_id]["collection_keyword_label"]
            if key[0] == "bluesky" and etiqueta in etiquetas and len(etiquetas) < 18:
                continue
            tomados.append(doc_id)
            etiquetas.add(etiqueta)
            if len(tomados) >= quiero:
                break
        elegidos.extend((key, d) for d in tomados)
    ids = pa.array([d for _, d in elegidos])
    filas = pq.read_table(chunks, columns=["chunk_id", "document_id", "chunk_index", "text"],
                          filters=pc.is_in(pc.field("document_id"), value_set=ids)).to_pylist()
    primero = {c["document_id"]: c for c in filas if c["chunk_index"] == 0}
    return [{"key": f"{src}/{lang}", "doc_id": doc_id, "chunk_id": primero[doc_id]["chunk_id"],
             "tema": meta[doc_id]["collection_keyword_label"] if src == "bluesky" else "",
             "text": primero[doc_id]["text"]}
            for (src, lang), doc_id in elegidos]


def construir_filas(candidatos):
    """Arma las 40 filas del gold standard (34 respondibles + 6 no respondibles)."""
    cand = {f"C{i:02d}": r for i, r in enumerate(candidatos)}
    rng = random.Random(SEMILLA)
    por_estrato = collections.defaultdict(list)
    for cid, (idioma, _q, _a) in QA.items():
        src, lang = cand[cid]["key"].split("/")
        if lang != idioma:
            raise SystemExit(f"{cid}: el idioma del candidato no coincide; los candidatos no son los esperados.")
        por_estrato[(src, lang)].append(cid)
    asignadas = {"desarrollo": [], "prueba": []}
    for key in sorted(por_estrato):
        ids = sorted(por_estrato[key])
        rng.shuffle(ids)
        dev_n, test_n = CUOTAS[key]
        if len(ids) != dev_n + test_n:
            raise SystemExit(f"Estrato {key}: hay {len(ids)} preguntas y la cuota es {dev_n + test_n}.")
        asignadas["desarrollo"] += [(key, c) for c in ids[:dev_n]]
        asignadas["prueba"] += [(key, c) for c in ids[dev_n:]]
    filas = []
    for split, ids_split in (("desarrollo", DEV), ("prueba", TEST)):
        libres = [i for i in ids_split if i not in NR_IDS[split]]
        if not len(libres) == len(asignadas[split]) == 17:
            raise SystemExit(f"Partición {split}: se esperaban 17 respondibles.")
        for gid, ((src, _lang), cid) in zip(libres, asignadas[split]):
            c = cand[cid]
            idioma, pregunta, respuesta = QA[cid]
            filas.append({"id": gid, "pregunta": pregunta, "idioma": idioma, "tipo": "sintetica",
                          "fuente_esperada": src, "tema": c["tema"] if src == "bluesky" else "",
                          "respuesta_referencia": respuesta, "evidencia_doc_id": c["doc_id"], "split": split,
                          "validada_por": PENDIENTE, "_chunk": c["chunk_id"], "_cand": cid})
        for gid, (idioma, pregunta) in zip(NR_IDS[split], NO_RESP[split]):
            filas.append({"id": gid, "pregunta": pregunta, "idioma": idioma, "tipo": "no_respondible",
                          "fuente_esperada": "", "tema": "", "respuesta_referencia": "", "evidencia_doc_id": "",
                          "split": split, "validada_por": PENDIENTE, "_chunk": "", "_cand": ""})
    return sorted(filas, key=lambda f: f["id"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="paso", required=True)
    p1 = sub.add_parser("candidatos", help="Selecciona chunks candidatos (semilla 42).")
    p1.add_argument("--documentos", default="data/documentos_rag.parquet")
    p1.add_argument("--chunks", default="data/chunks_tok256.parquet")
    p1.add_argument("--salida", default="data/gold_candidatos.json")
    p1.add_argument("--sobrescribir", action="store_true")
    p2 = sub.add_parser("construir", help="Construye el gold standard y las cuotas.")
    p2.add_argument("--candidatos", default="data/gold_candidatos.json")
    p2.add_argument("--gold", default="docs/gold_standard.csv")
    p2.add_argument("--cuotas", default="docs/cuotas_gold.json")
    p2.add_argument("--trazabilidad", default="data/gold_trazabilidad.json")
    p2.add_argument("--sobrescribir", action="store_true")
    args = parser.parse_args(argv)

    if args.paso == "candidatos":
        _no_sobrescribir([args.salida], args.sobrescribir)
        filas = seleccionar_candidatos(args.documentos, args.chunks)
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
        print(dict(collections.Counter(r["key"] for r in filas)), "| total", len(filas),
              "| temas Bluesky distintos", len({r["tema"] for r in filas if r["tema"]}))
        return 0

    _no_sobrescribir([args.gold, args.cuotas, args.trazabilidad], args.sobrescribir)
    candidatos = json.loads(Path(args.candidatos).read_text(encoding="utf-8"))
    filas = construir_filas(candidatos)
    for p in (args.gold, args.cuotas, args.trazabilidad):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(args.gold, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    Path(args.trazabilidad).write_text(json.dumps(
        {f["id"]: {"chunk_id": f["_chunk"], "candidato": f["_cand"]} for f in filas}, indent=1), encoding="utf-8")
    Path(args.cuotas).write_text(json.dumps(
        {"nota": "Cuotas de respondibles por fuente esperada e idioma de la pregunta. "
                 "Las 6 no respondibles (3 y 3) van aparte.",
         "estratos": [{"fuente_esperada": s, "idioma": l, "desarrollo": d, "prueba": p}
                      for (s, l), (d, p) in sorted(CUOTAS.items())]}, ensure_ascii=False, indent=1), encoding="utf-8")
    cnt = collections.Counter((f["split"], f["tipo"], f["fuente_esperada"], f["idioma"]) for f in filas)
    for k in sorted(cnt):
        print(k, cnt[k])
    print("filas", len(filas), "| temas Bluesky distintos", len({f["tema"] for f in filas if f["tema"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
