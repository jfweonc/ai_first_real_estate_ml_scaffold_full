from __future__ import annotations
import typer
from rich import print

app = typer.Typer(add_completion=False, no_args_is_help=True)

@app.command()
def doctor() -> None:
    """Basic sanity checks for the scaffold."""
    print("[green]✅ Environment OK[/green]")

if __name__ == "__main__":
    app()
