"""CLI del servicio de corpus (§22)."""

from __future__ import annotations

from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import get_settings

app = typer.Typer(
    add_completion=False,
    help="Corpus histórico de noticias colombianas (2006–2026).",
)
catalog_app = typer.Typer(help="Inspeccionar y sincronizar el catálogo.")
app.add_typer(catalog_app, name="catalog")

from news_corpus.cli_analyze import (  # noqa: E402
    clean_content_cmd,
    enrich,
    export,
    extract,
    profile,
    tag,
)
from news_corpus.cli_collect import collect, retry_failed  # noqa: E402

app.command("collect")(collect)
app.command("retry-failed")(retry_failed)
app.command("enrich")(enrich)
app.command("tag")(tag)
app.command("export")(export)
app.command("extract")(extract)
app.command("clean-content")(clean_content_cmd)
app.command("profile")(profile)

console = Console()


def _catalog():
    return load_catalog(get_settings().config_dir)


@catalog_app.command("check")
def catalog_check() -> None:
    """Valida config/*.yaml sin tocar la base de datos."""
    settings = get_settings()
    try:
        catalog = _catalog()
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[bold red]Configuración inválida[/]\n{exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓[/] Configuración válida en [dim]{settings.config_dir}[/]")
    console.print(
        f"  medios {len(catalog.sources)} "
        f"([green]{len(catalog.active_sources())} activos[/]) · "
        f"gobiernos {len(catalog.governments)} · temas {len(catalog.topics)}"
    )


@catalog_app.command("sources")
def catalog_sources() -> None:
    """Lista los medios y su cobertura verificada."""
    catalog = _catalog()
    table = Table(box=None, pad_edge=False)
    table.add_column("id", style="bold")
    table.add_column("medio")
    table.add_column("estrategia", style="dim")
    table.add_column("archivo desde", justify="right")
    table.add_column("fiable desde", justify="right")
    table.add_column("act.", justify="center")

    for s in catalog.sources:
        table.add_row(
            s.id,
            s.name,
            s.discovery.strategy,
            str(s.discovery.archive_from or "—"),
            str(s.discovery.reliable_from or "—"),
            "[green]sí[/]" if s.active else "[red]no[/]",
        )
    console.print(table)


@catalog_app.command("governments")
def catalog_governments() -> None:
    """Lista los gobiernos que delimitan el corpus."""
    catalog = _catalog()
    table = Table(box=None, pad_edge=False)
    table.add_column("id", style="bold")
    table.add_column("presidente")
    table.add_column("desde", justify="right")
    table.add_column("hasta", justify="right")
    table.add_column("verificado", justify="center")

    for g in sorted(catalog.governments, key=lambda x: x.start_date):
        table.add_row(
            g.id,
            f"{g.president} ({g.term}º)",
            str(g.start_date),
            str(g.end_date),
            "[green]sí[/]" if g.source_note else "[yellow]pendiente[/]",
        )
    console.print(table)


@catalog_app.command("sync")
def catalog_sync_cmd() -> None:
    """Sincroniza config/*.yaml → Postgres. Idempotente."""
    from news_corpus.db.session import session_scope
    from news_corpus.pipeline.catalog_sync import sync_catalog

    catalog = _catalog()
    with session_scope() as session:
        report = sync_catalog(session, catalog)
    console.print("[green]✓[/] Catálogo sincronizado")
    console.print(report.render())


@app.command("which-government")
def which_government(
    when: str = typer.Argument(..., help="Fecha ISO, p. ej. 2013-05-20"),
) -> None:
    """Responde qué gobierno estaba vigente en una fecha."""
    catalog = _catalog()
    target = date.fromisoformat(when)
    gov = catalog.government_at(target)
    if gov is None:
        console.print(
            f"[yellow]{target}[/] queda fuera del horizonte del corpus "
            f"({get_settings().corpus_start} → {get_settings().corpus_end})"
        )
        raise typer.Exit(1)
    console.print(f"[bold]{gov.president}[/] ({gov.id}) — {gov.start_date} → {gov.end_date}")


@app.command("status")
def status() -> None:
    """Estado del corpus: bloques por estado y artículos almacenados."""
    from sqlalchemy import func, select

    from news_corpus.db.models import Article
    from news_corpus.db.session import session_scope
    from news_corpus.pipeline.collector import corpus_summary

    with session_scope() as session:
        summary = corpus_summary(session)
        por_medio = session.execute(
            select(Article.source_id, func.count(), func.min(Article.published_date),
                   func.max(Article.published_date))
            .group_by(Article.source_id).order_by(func.count().desc())
        ).all()

    if not summary["chunks"]:
        console.print("[dim]Sin bloques de adquisición registrados todavía.[/]")
    else:
        table = Table(box=None, pad_edge=False)
        table.add_column("estado", style="bold")
        table.add_column("bloques", justify="right")
        for st, n in sorted(summary["chunks"].items()):
            table.add_row(st, str(n))
        console.print(table)

    console.print(
        f"\nartículos [bold]{summary['articles']}[/] · "
        f"registros de discovery {summary['discovery_records']}"
    )

    if por_medio:
        t2 = Table(box=None, pad_edge=False, title=None)
        t2.add_column("medio", style="bold")
        t2.add_column("artículos", justify="right")
        t2.add_column("desde", justify="right")
        t2.add_column("hasta", justify="right")
        for sid, n, lo, hi in por_medio:
            t2.add_row(sid, str(n), str(lo or "—"), str(hi or "—"))
        console.print()
        console.print(t2)


if __name__ == "__main__":
    app()
