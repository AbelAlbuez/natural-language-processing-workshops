"""Experimento: ¿priors dispersos o más pasadas estabilizan el LDA en titulares cortos?

Se corrió tras ver que ningún tópico de K=15 era estable entre semillas. Resultado
en resultados/experimento_priors.csv: ninguna configuración mejora la estabilidad
(Jaccard top-10 medio 0,25–0,30) ni la coherencia, así que se mantuvo la base.

Uso (después de ./run.sh prepare), desde media-bias-detection/:
  docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/workspace" -w /workspace/entrega3 \
    -e PYTHONPATH=/workspace/entrega3:/workspace/entrega2 duque-petro-lda:local python experimento_priors.py
"""
import json, sys, time
import numpy as np, pandas as pd
from gensim.corpora import Dictionary
from gensim.models import CoherenceModel, LdaMulticore
from topics import match_topics

out = "/workspace/entrega3/resultados/"
frame = pd.read_parquet(out + "prepared.parquet", columns=["tokens", "in_sample"])
dictionary = Dictionary.load(out + "modelos/dictionary.dict")
texts = [t.tolist() for t in frame.loc[frame["in_sample"], "tokens"]]
bows = [dictionary.doc2bow(t) for t in texts]
keep = [i for i, b in enumerate(bows) if b]
bows = [bows[i] for i in keep]; texts = [texts[i] for i in keep]
rng = np.random.default_rng(42)
cv_texts = [texts[i] for i in rng.choice(len(texts), 50000, replace=False)]
configs = {
    "base (α=1/K, η=1/K, 10 pasadas)": dict(alpha="symmetric", eta=None, passes=10),
    "dispersos (α=0,05, η=0,01, 10 pasadas)": dict(alpha=0.05, eta=0.01, passes=10),
    "dispersos + 20 pasadas": dict(alpha=0.05, eta=0.01, passes=20),
}
rows = []
for k in (10, 15):
    for name, cfg in configs.items():
        models = []
        for seed in (42, 7):
            t0 = time.monotonic()
            models.append(LdaMulticore(corpus=bows, id2word=dictionary, num_topics=k, workers=10,
                                       passes=cfg["passes"], iterations=100, chunksize=4000,
                                       random_state=seed, eval_every=None, alpha=cfg["alpha"], eta=cfg["eta"]))
        cv = CoherenceModel(model=models[0], texts=cv_texts, dictionary=dictionary, coherence="c_v",
                            topn=10, processes=10).get_coherence()
        m, sims = match_topics(models[0].get_topics(), models[1].get_topics())
        jac = []
        for t in range(k):
            a = {w for w, _ in models[0].show_topic(t, 10)}; b = {w for w, _ in models[1].show_topic(int(m[t]), 10)}
            jac.append(len(a & b) / len(a | b))
        jac = np.array(jac)
        row = {"K": k, "config": name, "c_v": round(cv, 4), "sim_js_media": round(float(sims.mean()), 3),
               "jaccard10_media": round(float(jac.mean()), 3), "topicos_jaccard_ge_0_5": int((jac >= 0.5).sum())}
        rows.append(row); print(row, flush=True)
pd.DataFrame(rows).to_csv(out + "experimento_priors.csv", index=False)
