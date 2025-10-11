from __future__ import annotations

from pathlib import Path

import structlog
import typer
from rich.console import Console

from . import etl

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()
logger = structlog.get_logger(__name__)


def _configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        cache_logger_on_first_use=True,
    )


@app.callback()
def main() -> None:  # pragma: no cover
    _configure_structlog()


@app.command()
def doctor() -> None:
    """Basic sanity checks for the scaffold."""
    console.print("[green]Environment OK[/green]")


@app.command("import-csv")
def import_csv(
    root: Path = typer.Option(  # noqa: B008
        Path("data/raw"),
        "--root",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory containing CSV files to ingest.",
    ),
    dry_run: bool = typer.Option(  # noqa: B008
        False,
        "--dry-run",
        is_flag=True,
        help="Discover files without writing outputs.",
    ),
    images_manifest: Path | None = typer.Option(  # noqa: B008
        None,
        "--images-manifest",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Optional JSONL manifest used to summarize image coverage.",
    ),
) -> None:
    """Discover CSV files, persist ledger entries, and emit coverage summaries."""

    root = root.expanduser().resolve()
    manifest_path = images_manifest.expanduser().resolve() if images_manifest else None
    result = etl.import_csv(root=root, dry_run=dry_run, images_manifest=manifest_path)
    console.print(f"[cyan]{result.message}[/cyan]")

    metrics = result.coverage_metrics
    console.print(
        "[green]Coverage:[/green] "
        f"{metrics['rows_clean']}/{metrics['rows_total']} clean "
        f"({metrics['coverage_pct']:.2f}%); gaps={metrics['gap_candidates']}"
    )

    if result.quarantine_file:
        console.print(f"[yellow]Quarantine:[/yellow] {result.quarantine_file}")
    if result.clean_rows_file:
        console.print(f"[yellow]Clean export:[/yellow] {result.clean_rows_file}")
    if result.coverage_report_file:
        console.print(f"[yellow]Coverage report:[/yellow] {result.coverage_report_file}")
    if result.selected_listings_file:
        console.print(f"[yellow]Gap manifest:[/yellow] {result.selected_listings_file}")

    if result.images_summary:
        counts = result.images_summary.get("download_status_counts", {})
        total_records = result.images_summary.get("total_records", 0)
        console.print("[magenta]Images manifest:[/magenta] " f"records={total_records} status_counts={counts}")

    logger.info(
        "cli.import_csv.complete",
        result=result.to_event(),
    )


if __name__ == "__main__":
    app()
