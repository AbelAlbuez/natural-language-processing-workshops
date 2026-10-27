"""Verificación de solo lectura de dragons_rag.parquet. Imprime JSON con las cifras."""
import hashlib
import json
import os
import sys

import pyarrow.compute as pc
import pyarrow.parquet as pq

PATH = sys.argv[1]
REF_SHA = "f4a669f17eaedd357f72b70c2192e685b6d534a94f6ffaeadbced7290b181728"
ESSENTIAL = ["document_id", "text", "collection_name", "title", "url", "source",
             "language", "created_at", "text_sha256", "word_count", "char_count"]

out = {"path": PATH, "bytes": os.path.getsize(PATH)}

h = hashlib.sha256()
with open(PATH, "rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
out["sha256"] = h.hexdigest()
out["sha256_ok"] = out["sha256"] == REF_SHA
if not out["sha256_ok"]:
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(2)

pf = pq.ParquetFile(PATH)
schema = pf.schema_arrow
out["rows"] = pf.metadata.num_rows
out["cols"] = len(schema.names)
out["row_groups"] = pf.metadata.num_row_groups
out["schema"] = [[f.name, str(f.type)] for f in schema]
present = [c for c in ESSENTIAL if c in schema.names]
out["missing_essential"] = [c for c in ESSENTIAL if c not in schema.names]

# Nulos: para "text" se lee por row group para no cargar todo el texto de golpe.
nulls, empty = {}, {}
for c in present:
    n = e = 0
    for i in range(pf.metadata.num_row_groups):
        col = pf.read_row_group(i, columns=[c]).column(0)
        n += col.null_count
        if c in ("text", "title", "document_id", "text_sha256") and str(col.type) in ("string", "large_string"):
            e += pc.sum(pc.equal(pc.utf8_length(pc.fill_null(col, "x")), 0)).as_py() or 0
    nulls[c] = n
    if c in ("text", "title", "document_id", "text_sha256"):
        empty[c] = e
out["nulls"] = nulls
out["empty_strings"] = empty


def dup_rows(colname):
    t = pq.read_table(PATH, columns=[colname]).column(0)
    nonnull = pc.drop_null(t)
    uniq = len(pc.unique(nonnull))
    return {"non_null": len(nonnull), "unique": uniq, "duplicate_rows": len(nonnull) - uniq}


for c in ("document_id", "text_sha256"):
    if c in schema.names:
        out[f"dup_{c}"] = dup_rows(c)

for c in ("source", "language", "collection_name", "source_type"):
    if c in schema.names:
        vc = pc.value_counts(pq.read_table(PATH, columns=[c]).column(0)).to_pylist()
        out[f"counts_{c}"] = sorted(([d["values"], d["counts"]] for d in vc), key=lambda x: -x[1])

if "created_at" in schema.names:
    ca = pq.read_table(PATH, columns=["created_at"]).column(0)
    out["created_at_type"] = str(ca.type)
    mm = pc.min_max(ca).as_py()
    out["created_at_min"], out["created_at_max"] = str(mm["min"]), str(mm["max"])

for c in ("word_count", "char_count"):
    if c in schema.names:
        col = pq.read_table(PATH, columns=[c]).column(0)
        mm = pc.min_max(col).as_py()
        out[f"stats_{c}"] = {"min": mm["min"], "max": mm["max"], "mean": round(pc.mean(col).as_py(), 2)}

print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
