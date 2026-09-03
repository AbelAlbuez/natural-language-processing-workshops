"""Comandos de adquisición (§22)."""

from __future__ import annotations

from datetime import date

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table
from sqlalchemy import select

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import get_settings
from news_corpus.db.models import ChunkStatus, CollectionChunk
from news_corpus.db.session import session_scope
from news_corpus.pipeline.collector import collect_chunk
from news_corpus.pipeline.planner import plan, resolve_sources
from news_corpus.providers.base import Period
from news_corpus.providers.sitemap import SitemapProvider

console = Console()


def _parse_month(value: str, *, last_day: bool = False) -> date:
    """Acepta `2013-05` o `2013-05-20`."""
    parts = value.split("-")
    if len(parts) == 2:
        return date(int(parts[0]), int(parts[1]), 28 if last_day else 1)
    return date.fromisoformat(value)


def collect(
    source: list[str] = typer.Option(
        None, "--source", "-s", help="ID del medio. Repetible. Por defecto: todos con sitemap."
    ),
    desde: str = typer.Option(..., "--from", "-f", help="Mes inicial, p. ej. 2013-01"),
    hasta: str = typer.Option(..., "--to", "-t", help="Mes final, p. ej. 2013-03"),
    force: bool = typer.Option(False, "--force", help="Reprocesar bloques ya completados."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mostrar el plan sin ejecutar."),
) -> None:
    """Recolecta artículos por bloques mensuales."""
    settings = get_settings()
    catalog = load_catalog(settings.config_dir)

    try:
        source_ids = resolve_sources(catalog, source)
    except KeyError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    chunks = plan(
        catalog,
        source_ids=source_ids,
        start=_parse_month(desde),
        end=_parse_month(hasta, last_day=True),
    )

    if not chunks:
        console.print("[yellow]Nada que recolectar con esos parámetros.[/]")
        raise typer.Exit(0)

    console.print(
        f"Plan: [bold]{len(chunks)}[/] bloques · "
        f"{len(source_ids)} medios · {desde} → {hasta}"
    )
    avisos = [c for c in chunks if c.warning]
    if avisos:
        console.print(
            f"[yellow]{len(avisos)} bloques con archivo adelgazado o incompleto "
            f"(se recolectan igual, quedan marcados).[/]"
        )

    if dry_run:
        table = Table(box=None, pad_edge=False)
        table.add_column("medio", style="bold")
        table.add_column("periodo")
        table.add_column("aviso", style="yellow")
        for c in chunks[:40]:
            table.add_row(c.source.id, c.period.label, c.warning or "")
        console.print(table)
        if len(chunks) > 40:
            console.print(f"[dim]… y {len(chunks) - 40} más[/]")
        raise typer.Exit(0)

    provider = SitemapProvider()
    totals = {"nuevos": 0, "duplicados": 0, "rechazados": 0, "fallidos": 0, "vacios": 0}

    try:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("recolectando", total=len(chunks))
            for planned in chunks:
                progress.update(
                    task, description=f"{planned.source.id} {planned.period.label}"
                )
                # Una sesión por bloque: un fallo no arrastra lo ya guardado.
                with session_scope() as session:
                    outcome = collect_chunk(
                        session,
                        provider=provider,
                        catalog=catalog,
                        source=planned.source,
                        period=planned.period,
                        force=force,
                    )
                if outcome.status == ChunkStatus.FAILED:
                    totals["fallidos"] += 1
                else:
                    totals["nuevos"] += outcome.n_new
                    totals["duplicados"] += outcome.n_duplicates
                    totals["rechazados"] += outcome.n_rejected
                    if outcome.n_found == 0:
                        totals["vacios"] += 1
                progress.advance(task)
    finally:
        provider.close()

    console.print(
        f"\n[green]✓[/] artículos nuevos [bold]{totals['nuevos']}[/] · "
        f"duplicados {totals['duplicados']} · rechazados {totals['rechazados']}"
    )
    if totals["vacios"]:
        console.print(f"[dim]{totals['vacios']} bloques sin URLs (mes vacío o sin archivo).[/]")
    if totals["fallidos"]:
        console.print(
            f"[yellow]{totals['fallidos']} bloques fallidos.[/] "
            f"Reintentar con [bold]news-corpus retry-failed[/]"
        )


def retry_failed(
    limit: int = typer.Option(100, "--limit", help="Máximo de bloques a reintentar."),
) -> None:
    """Reintenta los bloques que quedaron en FAILED."""
    settings = get_settings()
    catalog = load_catalog(settings.config_dir)

    with session_scope() as session:
        pendientes = session.scalars(
            select(CollectionChunk)
            .where(CollectionChunk.status == ChunkStatus.FAILED)
            .order_by(CollectionChunk.attempts, CollectionChunk.period_start)
            .limit(limit)
        ).all()
        objetivos = [
            (c.source_id, Period(start=c.period_start, end=c.period_end))
            for c in pendientes
        ]

    if not objetivos:
        console.print("[green]No hay bloques fallidos.[/]")
        raise typer.Exit(0)

    console.print(f"Reintentando [bold]{len(objetivos)}[/] bloques…")
    provider = SitemapProvider()
    recuperados = 0
    try:
        for source_id, period in objetivos:
            with session_scope() as session:
                outcome = collect_chunk(
                    session,
                    provider=provider,
                    catalog=catalog,
                    source=catalog.source(source_id),
                    period=period,
                )
            if outcome.status == ChunkStatus.COMPLETED:
                recuperados += 1
    finally:
        provider.close()

    console.print(f"[green]✓[/] recuperados {recuperados}/{len(objetivos)}")
