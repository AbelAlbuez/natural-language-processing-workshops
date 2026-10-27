import sys, re, collections
import pandas as pd, pyarrow.parquet as pq
df = pq.read_table(sys.argv[1], columns=["source","created_at","title","language","language_base"]).to_pandas()
def fmt(s):
    if s is None: return "nulo"
    s = re.sub(r"\d", "9", s); return s
print("formatos created_at:", collections.Counter(fmt(x) for x in df.created_at).most_common(10))
p = pd.to_datetime(df.created_at, utc=True, errors="coerce", format="mixed")
print("no parseables (excl. nulos):", int(p.isna().sum() - df.created_at.isna().sum()))
print("rango parseado:", p.min(), "->", p.max())
print("por source min/max:"); print(p.groupby(df.source).agg(["min","max"]).to_string())
print("anteriores a 2026-01-01:", int((p < "2026-01-01").sum()), "| anteriores a 2025-01-01:", int((p < "2025-01-01").sum()))
print("created_at nulo por source:", df[df.created_at.isna()].source.value_counts().to_dict())
print("title nulo por source:", df[df.title.isna()].source.value_counts().to_dict())
print("language nulo por source:", df[df.language.isna()].source.value_counts().to_dict())
print("language_base nulos:", int(df.language_base.isna().sum()))
print("language_base top:", df.language_base.value_counts(dropna=False).head(8).to_dict())
