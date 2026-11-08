from __future__ import annotations

import argparse
import hashlib
import math
import os
import subprocess
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from transformers import AutoTokenizer


PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
INPUT = DATA / "documentos_rag.parquet"
OUTPUT = DATA / "chunks_tok256.parquet"

MODEL = "intfloat/multilingual-e5-small"
STRATEGY = "tok256_overlap48_v1"
WINDOW = 256
OVERLAP = 48
STRIDE = WINDOW - OVERLAP
BATCH_SIZE = 32

EXPECTED_DOCUMENTS = 146923
EXPECTED_CHUNKS = 577324
EXPECTED_DISTRIBUTION = (3.0, 10.0, 426)

COLUMNS = [
    "document_id",
    "text",
    "url",
    "source",
    "created_at_utc",
]

SCHEMA = pa.schema([
    ("chunk_id", pa.string()),
    ("document_id", pa.string()),
    ("chunk_index", pa.int32()),
    ("strategy", pa.string()),
    ("text", pa.string()),
    ("token_start", pa.int32()),
    ("token_end", pa.int32()),
    ("char_start", pa.int64()),
    ("char_end", pa.int64()),
    ("token_count", pa.int32()),
    ("url", pa.string()),
    ("source", pa.string()),
    ("created_at_utc", pa.string()),
])


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(*arguments):
    result = subprocess.run(
        ["git", "-C", str(PROJECT), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def require_unused_output():
    require(
        OUTPUT.resolve().is_relative_to(DATA.resolve()),
        "La salida no está dentro de data/.",
    )
    require(
        not os.path.lexists(OUTPUT),
        "La salida ya existe; no se sobrescribirá.",
    )


def tokenize(tokenizer, texts, offsets=False):
    return tokenizer(
        texts,
        add_special_tokens=False,
        truncation=False,
        return_offsets_mapping=offsets,
        return_attention_mask=False,
        return_token_type_ids=False,
    )


def count_chunks(token_count):
    return 1 + math.ceil(max(0, token_count - WINDOW) / STRIDE)


def distribution(counts):
    values = np.asarray(list(counts), dtype=np.int64)
    median, p95 = np.percentile(values, [50, 95])
    return float(median), float(p95), int(values.max())


def optional_string(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def preflight(tokenizer):
    document_ids = set()
    counts = []

    for batch in pq.ParquetFile(INPUT).iter_batches(
        columns=["document_id", "text"],
        batch_size=BATCH_SIZE,
    ):
        rows = batch.to_pylist()
        encoded = tokenize(
            tokenizer,
            [row["text"] or "" for row in rows],
        )
        for row, token_ids in zip(rows, encoded["input_ids"]):
            require(row["document_id"] is not None, "document_id nulo.")
            document_id = str(row["document_id"])
            require(
                document_id not in document_ids,
                "document_id duplicado en el corpus.",
            )
            document_ids.add(document_id)
            counts.append(count_chunks(len(token_ids)))

    require(
        len(document_ids) == EXPECTED_DOCUMENTS,
        "El número de documentos no coincide.",
    )
    require(
        sum(counts) == EXPECTED_CHUNKS,
        "El total esperado de chunks no coincide.",
    )
    require(
        distribution(counts) == EXPECTED_DISTRIBUTION,
        "Los percentiles esperados no coinciden.",
    )
    print(f"documents={len(document_ids)}")
    print(f"expected_chunks={sum(counts)}")
    return document_ids


def chunk_records(row, offsets):
    document_id = str(row["document_id"])
    text = row["text"] or ""
    token_start = 0
    chunk_index = 0

    while True:
        token_end = min(token_start + WINDOW, len(offsets))
        valid_offsets = [
            (begin, end)
            for begin, end in offsets[token_start:token_end]
            if end > begin
        ]
        char_start = valid_offsets[0][0] if valid_offsets else 0
        char_end = valid_offsets[-1][1] if valid_offsets else 0
        payload = (
            f"{document_id}\x1f{chunk_index}\x1f{STRATEGY}"
        ).encode("utf-8")

        yield {
            "chunk_id": hashlib.sha256(payload).hexdigest(),
            "document_id": document_id,
            "chunk_index": chunk_index,
            "strategy": STRATEGY,
            "text": text[char_start:char_end],
            "token_start": token_start,
            "token_end": token_end,
            "char_start": char_start,
            "char_end": char_end,
            "token_count": token_end - token_start,
            "url": optional_string(row["url"]),
            "source": optional_string(row["source"]),
            "created_at_utc": optional_string(row["created_at_utc"]),
        }

        if token_end == len(offsets):
            break
        token_start += STRIDE
        chunk_index += 1


def write_temporary(tokenizer, temporary):
    with pq.ParquetWriter(
        temporary, SCHEMA, compression="zstd"
    ) as writer:
        for batch in pq.ParquetFile(INPUT).iter_batches(
            columns=COLUMNS,
            batch_size=BATCH_SIZE,
        ):
            rows = batch.to_pylist()
            encoded = tokenize(
                tokenizer,
                [row["text"] or "" for row in rows],
                offsets=True,
            )
            records = []
            for row, offsets in zip(rows, encoded["offset_mapping"]):
                records.extend(chunk_records(row, offsets))
            writer.write_table(
                pa.Table.from_pylist(records, schema=SCHEMA)
            )


def verify(tokenizer, temporary, document_ids):
    parquet = pq.ParquetFile(temporary)
    require(
        parquet.metadata.num_rows == EXPECTED_CHUNKS,
        "Las filas escritas no coinciden.",
    )

    chunk_ids = set()
    per_document = Counter()
    maximum_tokens = 0
    retokenized_over_256 = 0
    maximum_token_difference = 0

    for batch in parquet.iter_batches(
        columns=["chunk_id", "document_id", "text", "token_count"],
        batch_size=BATCH_SIZE,
    ):
        rows = batch.to_pylist()
        encoded = tokenize(
            tokenizer, [row["text"] for row in rows]
        )
        for row, token_ids in zip(rows, encoded["input_ids"]):
            require(
                row["chunk_id"] not in chunk_ids,
                "ID de chunk duplicado.",
            )
            chunk_ids.add(row["chunk_id"])
            per_document[row["document_id"]] += 1
            require(
                row["token_count"] <= WINDOW,
                "Ventana original mayor de 256 tokens.",
            )
            require(
                len(token_ids) <= 512,
                "Texto del chunk retokenizado supera 512 tokens.",
            )
            maximum_tokens = max(maximum_tokens, len(token_ids))
            retokenized_over_256 += len(token_ids) > WINDOW
            maximum_token_difference = max(
                maximum_token_difference, len(token_ids) - row["token_count"]
            )

    require(
        set(per_document) == document_ids,
        "La cobertura de document_id no coincide.",
    )
    require(
        distribution(per_document.values()) == EXPECTED_DISTRIBUTION,
        "La distribución escrita no coincide.",
    )
    return (
        chunk_ids, per_document, maximum_tokens,
        retokenized_over_256, maximum_token_difference,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Chunking local; por defecto solo preanálisis."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Generar y validar data/chunks_tok256.parquet.",
    )
    arguments = parser.parse_args()

    require_unused_output()
    status_before = git("status", "--short")
    ignore_rule = git(
        "check-ignore", "-v", "data/chunks_tok256.parquet"
    )
    require(ignore_rule.strip(), "La salida no está ignorada por Git.")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, local_files_only=True
    )
    require(tokenizer.is_fast, "Se necesita un tokenizador rápido.")
    document_ids = preflight(tokenizer)

    if not arguments.write:
        print("dry_run=True")
        return

    require_unused_output()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="chunks_tok256.",
        suffix=".parquet.tmp",
        dir=DATA,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)

    try:
        write_temporary(tokenizer, temporary)
        (
            chunk_ids, per_document, maximum_tokens,
            retokenized_over_256, maximum_token_difference,
        ) = verify(tokenizer, temporary, document_ids)
        require(
            git("status", "--short") == status_before,
            "El estado Git cambió durante la ejecución.",
        )
        git("check-ignore", "-v", "data/chunks_tok256.parquet")

        require_unused_output()
        os.link(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)

    status_after = git("status", "--short")
    require(
        status_after == status_before,
        "El estado Git cambió tras publicar el Parquet.",
    )

    median, p95, maximum = distribution(per_document.values())
    print(f"rows={len(chunk_ids)}")
    print(f"unique_chunk_ids={len(chunk_ids)}")
    print(f"covered_documents={len(per_document)}")
    print(f"max_chunk_tokens={maximum_tokens}")
    print(f"retokenized_over_256={retokenized_over_256}")
    print(f"max_difference_from_token_count={maximum_token_difference}")
    print(
        f"chunks_per_document_p50={median:.1f} "
        f"p95={p95:.1f} max={maximum}"
    )
    print(
        "documents_with_multiple_chunks="
        f"{sum(count > 1 for count in per_document.values())}"
    )
    print(f"file_size_mib={OUTPUT.stat().st_size / 1024**2:.2f}")
    print("git_check_ignore:")
    print(ignore_rule, end="")
    print("git_status_short:")
    print(status_after, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {type(error).__name__}")
        raise SystemExit(1) from None