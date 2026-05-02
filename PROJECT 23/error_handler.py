import logging

logging.basicConfig(filename="datadump.log", level=logging.ERROR)

def safe_run(func):
    try:
        func()
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] The file '{e.filename}' was not found.")
        console.print("[yellow]Hint:[/yellow] Check your path or use 'ls' to verify the file exists.")
    except Exception as e:
        logging.error("Unexpected crash", exc_info=True)
        console.print("[red]A fatal error occurred.[/red] Check datadump.log for details.")