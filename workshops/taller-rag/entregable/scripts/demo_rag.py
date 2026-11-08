"""Demo mínima: la misma pregunta contra RAG–Milvus (denso) y RAG–Solr (BM25).

Para cada motor muestra los fragmentos recuperados (documento, puntuación, inicio del texto),
el tiempo de recuperación y, si no se usa --sin-llm, la respuesta del LLM con sus citas y tiempos.
Al final guarda una traza en Markdown (sin inventar nada: es la salida real de la API).

Solo usa la biblioteca estándar. Con la API levantada (docker compose ... up -d):
  python scripts/demo_rag.py --pregunta "¿En qué ciudad se realizó la COP16?"
  python scripts/demo_rag.py --pregunta "..." --modelo gemma2:2b --k 5
  python scripts/demo_rag.py --pregunta "..." --sin-llm          # solo recuperación (segundos)
  python scripts/demo_rag.py --demo-gold --sin-llm               # 3 preguntas del gold, ambos motores
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

PREGUNTAS_DEMO = [
    "¿En qué ciudad colombiana se realizó la COP16 del Convenio sobre la Diversidad Biológica?",
    "When did the European Parliament vote on its position on the Nature Restoration Law?",
    "¿Cuál es la receta tradicional de la paella valenciana?",  # sin respuesta en el corpus
]


def post(api, ruta, payload, timeout):
    req = urllib.request.Request(api + ruta, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return None, {"error": type(e).__name__}


def recortar(t, n=160):
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n] + "…"


def correr(api, pregunta, backend, k, modelo, sin_llm, out):
    titulo = {"milvus": "RAG–Milvus (denso, E5 + HNSW)", "solr": "RAG–Solr (léxico, BM25)"}[backend]
    out.append(f"\n### {titulo}\n")
    print(f"\n--- {titulo} ---")
    t0 = time.perf_counter()
    st, r = post(api, "/retrieve", {"question": pregunta, "k": k, "backend": backend}, 120)
    dt = time.perf_counter() - t0
    if st != 200:
        msg = f"/retrieve falló: HTTP {st} {json.dumps(r, ensure_ascii=False)[:200]}"
        print(msg)
        out.append(f"- {msg}")
        return
    print(f"recuperación: {dt:.2f} s · colección/core: {r.get('collection')}")
    out.append(f"- Recuperación: {dt:.2f} s (colección/core `{r.get('collection')}`)")
    for i, f in enumerate(r["fragments"], 1):
        linea = f"{i}. score={f['score']:.3f} · {f['document_id']} · {recortar(f['text'])}"
        print("  " + linea)
        out.append("  " + linea)
    if sin_llm:
        return
    t0 = time.perf_counter()
    st, a = post(api, "/ask", {"question": pregunta, "k": k, "model": modelo, "backend": backend}, 330)
    dt = time.perf_counter() - t0
    if st != 200:
        msg = f"/ask falló: HTTP {st} {json.dumps(a, ensure_ascii=False)[:200]}"
        print(msg)
        out.append(f"- {msg}")
        return
    tm = a["params"]["timings"]
    print(f"respuesta ({modelo}, {dt:.1f} s; generación {tm.get('generation_s')} s): {recortar(a['answer'], 400)}")
    print(f"abstuvo: {a['abstained']} ({a['abstention_reason']}) · citas: {[c['ref'] for c in a['citations']]} "
          f"· inválidas: {a['invalid_citations']}")
    out.append(f"- Modelo `{modelo}`: {dt:.1f} s en total; generación {tm.get('generation_s')} s; "
               f"abstuvo={a['abstained']} ({a['abstention_reason']}); citas válidas={[c['ref'] for c in a['citations']]}")
    out.append(f"  > {recortar(a['answer'], 600)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pregunta")
    ap.add_argument("--demo-gold", action="store_true", help="usa 3 preguntas de ejemplo (dos con respuesta, una sin)")
    ap.add_argument("--api", default=os.getenv("RAG_API_URL", "http://localhost:8000"))
    ap.add_argument("--modelo", default="gemma2:2b")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--sin-llm", action="store_true")
    ap.add_argument("--backends", nargs="+", default=["milvus", "solr"], choices=["milvus", "solr"])
    ap.add_argument("--salida", default="reports/demo_trazas.md")
    a = ap.parse_args()
    if not a.pregunta and not a.demo_gold:
        sys.exit("Indique --pregunta o --demo-gold.")
    api = a.api.rstrip("/")
    try:
        with urllib.request.urlopen(api + "/health?deep=true", timeout=30) as r:
            h = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        sys.exit(f"No se alcanza la API en {api}: {e}")
    print(f"API {h.get('status')} · Milvus: {h.get('collection')} ({h.get('milvus', {}).get('rows')} filas) · "
          f"Solr: {h.get('solr', 'no configurado')}")
    out = [f"# Demo RAG: Milvus vs Solr", f"Generada el {datetime.now():%Y-%m-%d %H:%M} contra `{api}`. "
           f"Salida real de la API; no se editó.", f"- Estado: `{json.dumps(h, ensure_ascii=False)}`"]
    for q in ([a.pregunta] if a.pregunta else PREGUNTAS_DEMO):
        print(f"\n=== PREGUNTA: {q}")
        out.append(f"\n## Pregunta: {q}")
        for b in a.backends:
            correr(api, q, b, a.k, a.modelo, a.sin_llm, out)
    os.makedirs(os.path.dirname(a.salida) or ".", exist_ok=True)
    with open(a.salida, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"\nTraza guardada en {a.salida}")


if __name__ == "__main__":
    main()
