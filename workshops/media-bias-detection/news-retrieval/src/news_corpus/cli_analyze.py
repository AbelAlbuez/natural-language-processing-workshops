"""Comandos de enriquecimiento, etiquetado y export."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import get_settings
from news_corpus.db.session import session_scope

console = Console()


def month_windows(desde: str | None, hasta: str | None) -> list[tuple[date | None, date | None]]:
    """Parte el rango en meses para confirmar cada uno por separado.

    `enrich` y `tag` cargan cada artículo en la sesión; sobre cientos de miles
    de filas en una sola transacción la memoria crece hasta tumbar el proceso.
    Un mes por transacción la acota y deja lo ya hecho confirmado si se corta.
    Sin rango se conserva la ejecución de siempre: una sola pasada.
    """
    from news_corpus.cli_collect import _parse_month

    if not desde and not hasta:
        return [(None, None)]
    if not (desde and hasta):
        raise typer.BadParameter("--from y --to van juntos.")
    inicio, fin = _parse_month(desde), _parse_month(hasta, last_day=True)
    ventanas: list[tuple[date | None, date | None]] = []
    cursor = inicio
    while cursor <= fin:
        siguiente = date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)
        ventanas.append((cursor, min(fin, siguiente - timedelta(days=1))))
        cursor = siguiente
    return ventanas


def _sumar(total: dict, parcial: dict) -> None:
    for clave, valor in parcial.items():
        if isinstance(valor, int):
            total[clave] = total.get(clave, 0) + valor
        else:
            total[clave] = valor


def enrich(
    all_articles: bool = typer.Option(
        False, "--all", help="Reprocesar también los que ya tienen título."
    ),
    desde: str = typer.Option(None, "--from", "-f", help="Mes o día inicial, p. ej. 2018-08"),
    hasta: str = typer.Option(None, "--to", "-t", help="Mes o día final, p. ej. 2022-08"),
) -> None:
    """Deriva título y sección a partir de la URL."""
    from news_corpus.pipeline.enrich import enrich_articles

    stats: dict = {}
    for inicio, fin in month_windows(desde, hasta):
        with session_scope() as session:
            _sumar(stats, enrich_articles(
                session, only_missing=not all_articles, date_from=inicio, date_to=fin
            ))
        if inicio:
            console.print(f"[dim]{inicio:%Y-%m} · revisados {stats['revisados']}[/]")

    console.print(
        f"[green]✓[/] revisados {stats['revisados']} · "
        f"títulos derivados [bold]{stats['titulos']}[/] · "
        f"secciones {stats['secciones']}"
    )
    if stats["sin_titulo"]:
        console.print(
            f"[yellow]{stats['sin_titulo']} sin título derivable[/] "
            f"(URLs tipo /archivo/documento/MAM-0000000: requieren extracción)."
        )
    console.print(
        "[dim]Los títulos derivados quedan marcados title_source='slug': son "
        "una reconstrucción, no el titular publicado.[/]"
    )


def tag(
    retag: bool = typer.Option(False, "--retag", help="Borrar y rehacer las etiquetas del rango."),
    desde: str = typer.Option(None, "--from", "-f", help="Mes o día inicial, p. ej. 2018-08"),
    hasta: str = typer.Option(None, "--to", "-t", help="Mes o día final, p. ej. 2022-08"),
) -> None:
    """Etiqueta el corpus con la jerarquía de config/topics.yaml."""
    from news_corpus.pipeline.tagging import tag_corpus

    catalog = load_catalog(get_settings().config_dir)
    stats: dict = {}
    for inicio, fin in month_windows(desde, hasta):
        with session_scope() as session:
            _sumar(stats, tag_corpus(
                session, catalog, retag=retag, date_from=inicio, date_to=fin
            ))
        if inicio:
            console.print(f"[dim]{inicio:%Y-%m} · procesados {stats['articulos']}[/]")

    console.print(
        f"[green]✓[/] artículos procesados {stats['articulos']} · "
        f"etiquetas [bold]{stats['etiquetas']}[/] · "
        f"sin tema {stats['sin_tema']}"
    )
    console.print(f"[dim]versión de reglas: {stats['version']}[/]")


def export(
    out: Path = typer.Option(Path("exports/corpus.parquet"), "--out", "-o"),
    fmt: str = typer.Option("parquet", "--format", "-F", help="parquet | csv | jsonl"),
    source: str = typer.Option(None, "--source", "-s"),
    desde: str = typer.Option(None, "--from", "-f"),
    hasta: str = typer.Option(None, "--to", "-t"),
    sin_cuerpo: bool = typer.Option(
        False, "--no-content", help="Sólo metadata: omite `content` y `content_hash`."
    ),
) -> None:
    """Exporta el corpus para análisis NLP."""
    from news_corpus.pipeline.export import export_corpus

    with session_scope() as session:
        stats = export_corpus(
            session,
            out=out,
            fmt=fmt,
            source_id=source,
            desde=date.fromisoformat(desde) if desde else None,
            hasta=date.fromisoformat(hasta) if hasta else None,
            with_content=not sin_cuerpo,
        )

    console.print(
        f"[green]✓[/] {stats.rows} filas → [bold]{stats.path}[/] ({stats.fmt})"
    )


def extract(
    limit: int = typer.Option(100, "--limit", "-n", help="Máximo de artículos por corrida."),
    source: str = typer.Option(None, "--source", "-s"),
    all_articles: bool = typer.Option(
        False, "--all", help="También los que ya tienen título derivado del slug."
    ),
    retry: bool = typer.Option(False, "--retry", help="Reintentar los que fallaron por red."),
    desde: str = typer.Option(None, "--from", "-f", help="Mes o día inicial, p. ej. 2018-08"),
    hasta: str = typer.Option(None, "--to", "-t", help="Mes o día final, p. ej. 2026-08"),
    topic: list[str] = typer.Option(
        None, "--topic", help="ID de tema (incluye sus subtemas). Repetible. Requiere `tag`."
    ),
) -> None:
    """Lee la página del artículo para obtener titular, fecha y cuerpo reales."""
    from news_corpus.cli_collect import _parse_month
    from news_corpus.pipeline.extraction import extract_pending

    catalog = load_catalog(get_settings().config_dir)
    try:
        with session_scope() as session:
            stats = extract_pending(
                session,
                catalog,
                limit=limit,
                source_id=source,
                only_missing_title=not all_articles,
                retry_failed=retry,
                date_from=_parse_month(desde) if desde else None,
                date_to=_parse_month(hasta, last_day=True) if hasta else None,
                topic_ids=topic or None,
            )
    except KeyError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    if stats["intentados"] == 0:
        console.print("[green]Nada pendiente de extraer con esos filtros.[/]")
        return

    console.print(
        f"[green]✓[/] intentados {stats['intentados']} · "
        f"con titular [bold]{stats['ok']}[/] · con cuerpo {stats['con_cuerpo']}"
    )
    if stats["fechas_mejoradas"]:
        console.print(
            f"[green]{stats['fechas_mejoradas']} fechas ascendidas de 'month' a 'day'[/] "
            f"(y su gobierno reasignado)."
        )
    problemas = {
        "sin titular": stats["sin_titulo"],
        "artículo ya no existe (404)": stats["http_error"],
        "fallo de red (reintentable)": stats["fallidos"],
        "bloqueado por robots.txt": stats["robots"],
    }
    for etiqueta, n in problemas.items():
        if n:
            console.print(f"[yellow]{n}[/] {etiqueta}")


def clean_content_cmd() -> None:
    """Vuelve a limpiar el cuerpo ya guardado con las reglas actuales."""
    from news_corpus.pipeline.extraction import reclean_stored_content

    with session_scope() as session:
        stats = reclean_stored_content(session)

    console.print(
        f"[green]✓[/] revisados {stats['revisados']} · "
        f"modificados [bold]{stats['modificados']}[/]"
    )
    if stats["vaciados"]:
        console.print(
            f"[yellow]{stats['vaciados']} quedaron sin cuerpo[/]: todo su texto "
            f"era interfaz de la página (típico de las notas que sólo son audio)."
        )


def profile() -> None:
    """Radiografía del corpus: qué se puede analizar y qué no."""
    from sqlalchemy import func, select

    from news_corpus.db.models import Article, ArticleTopic

    with session_scope() as session:
        total = session.scalar(select(func.count()).select_from(Article)) or 0
        if total == 0:
            console.print("[yellow]El corpus está vacío. Ejecuta `news-corpus collect`.[/]")
            raise typer.Exit(0)

        con_titulo = session.scalar(
            select(func.count()).select_from(Article).where(Article.title.isnot(None))
        )
        por_precision = session.execute(
            select(Article.date_precision, func.count()).group_by(Article.date_precision)
        ).all()
        por_medio = session.execute(
            select(
                Article.source_id,
                func.count(),
                func.min(Article.published_date),
                func.max(Article.published_date),
            ).group_by(Article.source_id).order_by(func.count().desc())
        ).all()
        # Un cuerpo por debajo de este umbral no es una nota: es el sumario que
        # acompaña a un audio o un vídeo. Medido en Blu Radio 2013, donde el
        # archivo son posts de radio sin texto (ver README).
        umbral = 500
        por_texto = session.execute(
            select(
                Article.source_id,
                func.count(),
                func.count(Article.content),
                func.count().filter(func.length(Article.content) >= umbral),
                func.percentile_cont(0.5)
                .within_group(func.length(Article.content))
                .filter(Article.content.is_not(None)),
            ).group_by(Article.source_id).order_by(func.count().desc())
        ).all()
        top_temas = session.execute(
            select(ArticleTopic.topic_id, func.count())
            .group_by(ArticleTopic.topic_id)
            .order_by(func.count().desc())
            .limit(10)
        ).all()

    console.print(f"[bold]{total}[/] artículos · con título {con_titulo}")

    t = Table(title="Cobertura por medio", box=None, pad_edge=False, title_justify="left")
    t.add_column("medio", style="bold")
    t.add_column("artículos", justify="right")
    t.add_column("desde", justify="right")
    t.add_column("hasta", justify="right")
    for sid, n, lo, hi in por_medio:
        t.add_row(sid, str(n), str(lo or "—"), str(hi or "—"))
    console.print()
    console.print(t)

    t2 = Table(title="Fiabilidad de la fecha", box=None, pad_edge=False, title_justify="left")
    t2.add_column("precisión", style="bold")
    t2.add_column("artículos", justify="right")
    for prec, n in sorted(por_precision, key=lambda r: -r[1]):
        t2.add_row(str(prec), str(n))
    console.print()
    console.print(t2)

    t4 = Table(
        title=f"Texto completo (cuerpo ≥ {umbral} caracteres = analizable)",
        box=None, pad_edge=False, title_justify="left",
    )
    t4.add_column("medio", style="bold")
    t4.add_column("artículos", justify="right")
    t4.add_column("con cuerpo", justify="right")
    t4.add_column("analizable", justify="right")
    t4.add_column("mediana car.", justify="right")
    for sid, n, con_cuerpo, analizable, mediana in por_texto:
        t4.add_row(
            sid, str(n), str(con_cuerpo), str(analizable),
            str(int(mediana)) if mediana else "—",
        )
    console.print()
    console.print(t4)

    if top_temas:
        t3 = Table(title="Temas más frecuentes", box=None, pad_edge=False, title_justify="left")
        t3.add_column("tema", style="bold")
        t3.add_column("artículos", justify="right")
        for tid, n in top_temas:
            t3.add_row(tid, str(n))
        console.print()
        console.print(t3)
    else:
        console.print("\n[dim]Sin etiquetas temáticas. Ejecuta `news-corpus tag`.[/]")

    console.print(
        "\n[yellow]Antes de comparar volúmenes entre medios o períodos:[/] "
        "consulta la tabla [bold]archive_density[/]. Una diferencia de cobertura "
        "puede ser una diferencia de archivado."
    )
