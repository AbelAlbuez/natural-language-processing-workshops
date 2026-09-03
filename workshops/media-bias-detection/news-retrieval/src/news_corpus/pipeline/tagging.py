"""Etiquetado temático, aplicado DESPUÉS del discovery (§8).

Se etiqueta sobre el corpus ya almacenado, no durante la búsqueda. Así, cambiar
`topics.yaml` re-etiqueta todo sin volver a descargar nada, y `rule_version`
deja constancia de qué versión de reglas produjo cada etiqueta.

Es deliberadamente un emparejamiento por palabras clave, no un clasificador: el
`CLAUDE.md` §32 excluye modelos de este servicio. Sirve para segmentar el corpus
por tema, no para afirmar de qué trata un artículo.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from news_corpus.config.catalog import Catalog, TopicConfig
from news_corpus.db.models import Article, ArticleTopic


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", strip_accents(text.lower()))


def rule_version(catalog: Catalog) -> str:
    """Huella de las keywords vigentes. Cambia si cambia topics.yaml."""
    payload = "|".join(
        f"{t.id}:{','.join(sorted(t.keywords))}" for t in sorted(catalog.topics, key=lambda x: x.id)
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


@dataclass
class Match:
    topic_id: str
    keyword: str
    field: str


class TopicTagger:
    def __init__(self, catalog: Catalog) -> None:
        self.version = rule_version(catalog)
        self._rules: list[tuple[TopicConfig, list[tuple[str, re.Pattern]]]] = []
        for topic in catalog.topics:
            if not topic.active or not topic.keywords:
                continue
            patterns = [
                # \b evita que "paz" empareje dentro de "capaz" o "Paz de Río".
                (kw, re.compile(rf"\b{re.escape(normalize_text(kw)).strip()}\b"))
                for kw in topic.keywords
            ]
            self._rules.append((topic, patterns))

    def match(self, *, title: str | None, url: str, section: str | None) -> list[Match]:
        campos = [
            ("title", normalize_text(title) if title else ""),
            ("url_path", normalize_text(url)),
            ("section", normalize_text(section) if section else ""),
        ]
        encontrados: dict[str, Match] = {}
        for topic, patterns in self._rules:
            for field, text in campos:
                if not text:
                    continue
                for kw, pattern in patterns:
                    if pattern.search(text):
                        # El título manda sobre la URL: si ya emparejó ahí, no
                        # se degrada la evidencia.
                        if topic.id not in encontrados:
                            encontrados[topic.id] = Match(topic.id, kw, field)
                        break
        return list(encontrados.values())


def tag_corpus(session: Session, catalog: Catalog, *, retag: bool = False) -> dict[str, int]:
    tagger = TopicTagger(catalog)
    stats = {"articulos": 0, "etiquetas": 0, "sin_tema": 0, "version": tagger.version}

    if retag:
        session.execute(delete(ArticleTopic))
        session.flush()

    ya_etiquetados: set[int] = set()
    if not retag:
        ya_etiquetados = set(
            session.scalars(
                select(ArticleTopic.article_id).where(
                    ArticleTopic.rule_version == tagger.version
                )
            ).all()
        )

    for article in session.scalars(select(Article)).yield_per(1000):
        if article.id in ya_etiquetados:
            continue
        stats["articulos"] += 1

        matches = tagger.match(
            title=article.title, url=article.url, section=article.section
        )
        if not matches:
            # Se conserva sin tema (§8 keep_untagged): un artículo sin etiqueta
            # sigue siendo parte del corpus y del denominador.
            stats["sin_tema"] += 1
            continue

        for m in matches:
            session.add(
                ArticleTopic(
                    article_id=article.id,
                    topic_id=m.topic_id,
                    matched_on=m.field,
                    matched_keyword=m.keyword,
                    rule_version=tagger.version,
                )
            )
            stats["etiquetas"] += 1

    return stats
