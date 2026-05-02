import typer

app = typer.Typer()

@app.command()
def import_pdf(path: str):
    """Import a new bank statement and categorise transactions."""
    typer.echo(f"Processing {path}...")
    # Logic to parse -> categorise -> store

@app.command()
def report(month: str = None):
    """View monthly spending summary and chart."""
    # Logic to run analytics and open PNG
    typer.launch("monthly_summary.png")

if __name__ == "__main__":
    app()