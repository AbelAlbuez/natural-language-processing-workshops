"""Interfaz Streamlit del asistente RAG. Solo habla con la API (no con Milvus ni Ollama).

Variables de entorno: API_URL (obligatoria), LLM_MODEL y LLM_MODELS (lista separada
por comas) para el selector de modelo.
Uso: streamlit run app/ui.py
"""
import os

import requests
import streamlit as st

st.set_page_config(page_title="Asistente RAG", layout="wide")
st.title("Asistente RAG · prensa y Bluesky")
st.caption("Respuestas basadas en el corpus; contraste siempre las fuentes originales.")

api_url = os.getenv("API_URL", "").rstrip("/")
if not api_url:
    st.error("Falta la variable de entorno API_URL.")
    st.stop()

default_model = os.getenv("LLM_MODEL", "").strip()
models = [m.strip() for m in os.getenv("LLM_MODELS", "").split(",") if m.strip()]
if default_model and default_model not in models:
    models.insert(0, default_model)
if not models:
    st.error("Defina LLM_MODEL o LLM_MODELS.")
    st.stop()

with st.sidebar:
    model = st.selectbox("Modelo (Ollama)", models)
    k = st.slider("Top-k", 1, 15, 5)
    if st.button("Estado de los servicios"):
        try:
            st.json(requests.get(f"{api_url}/health", params={"deep": "true"}, timeout=15).json())
        except requests.RequestException as exc:
            st.error(f"La API no responde: {type(exc).__name__}")

question = st.text_area("Pregunta", height=100)

if st.button("Consultar", type="primary", disabled=len(question.strip()) < 3):
    with st.spinner("Recuperando evidencia y generando respuesta…"):
        try:
            r = requests.post(
                f"{api_url}/ask",
                json={"question": question.strip(), "model": model, "k": k},
                timeout=300,
            )
        except requests.RequestException as exc:
            st.error(f"La API no responde: {type(exc).__name__}")
            st.stop()
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text[:300]
        st.error(f"Error {r.status_code}: {detail}")
        st.stop()

    out = r.json()
    if out["abstained"]:
        st.warning(f"Abstención ({out['abstention_reason']}): {out['answer']}")
    else:
        st.subheader("Respuesta")
        st.write(out["answer"])
        if out.get("invalid_citations"):
            st.caption(f"Citas sin fragmento correspondiente: {out['invalid_citations']}")
        if not out.get("citations"):
            st.caption("La respuesta no cita ningún fragmento.")

    p = out["params"]
    t = p["timings"]
    st.caption(
        f"Modelo: {p['model']} · k={p['top_k']} · umbral={p['score_threshold']} · "
        f"{p['prompt_name']} v{p['prompt_version']} · recuperación {t['retrieval_s']} s · "
        f"generación {t['generation_s']} s · total {t['total_s']} s"
    )

    cited = {c["ref"] for c in out.get("citations", [])}
    st.subheader("Fuentes")
    for f in out["evidence"]:
        mark = " · citado" if f["ref"] in cited else ""
        with st.expander(f"[{f['ref']}] {f.get('source', '')} · {f.get('document_id', '')} · score={f['score']:.3f}{mark}"):
            st.write(f.get("text", ""))
            if f.get("url"):
                st.markdown(f"[Abrir fuente]({f['url']})")
    if out.get("dropped_by_budget"):
        st.caption(f"{out['dropped_by_budget']} fragmentos no entraron en el presupuesto de contexto.")
