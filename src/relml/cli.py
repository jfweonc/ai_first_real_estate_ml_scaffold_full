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
    """Apply a basic structlog configuration for CLI usage."""
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
def main() -> None:  # pragma: no cover - invoked by Typer automatically
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
) -> None:
    """Discover CSV files and emit a stub summary (Phase 0.5 placeholder)."""

    root = root.expanduser().resolve()
    result = etl.import_csv(root=root, dry_run=dry_run)
    console.print(f"[cyan]{result.message}[/cyan]")
    logger.info(
        "cli.import_csv.complete",
        event=result.to_event(),
    )


if __name__ == "__main__":
    app()
