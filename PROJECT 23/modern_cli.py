import typer
from rich.console import Console
from rich.table import Table
from typing import Optional

app = typer.Typer(help="DataDump: The professional export utility.")
console = Console()

@app.command()
def export(
    src: str = typer.Argument(..., help="Path to the source file"),
    dest: str = typer.Option("output.csv", "--output", "-o", help="Target destination"),
    format: str = typer.Option("csv", help="Format: csv or json")
):
    """
    Export data from a source file to a destination with specific formatting.
    """
    console.print(f"[bold blue]Starting export...[/bold blue]")
    # Student implements logic here...
    
if __name__ == "__main__":
    app()