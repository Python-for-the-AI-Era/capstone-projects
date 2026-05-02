"""
Command-line interface for the pipeline package.

This module provides CLI commands using Typer for easy
pipeline execution and management.
"""

from pathlib import Path
from typing import List, Optional

import typer
import structlog

from .core.pipeline import Pipeline
from .utils.logging import setup_logging, get_logger


# Create CLI app
app = typer.Typer(
    name="pipeline-pkg",
    help="Pipeline Package - A modular data processing pipeline",
    add_completion=False,
)

# Global logger
logger = get_logger(__name__)


@app.command()
def execute(
    endpoints: List[str] = typer.Argument(
        default=["users", "products", "orders"],
        help="API endpoints to process",
    ),
    recipients: List[str] = typer.Option(
        default=["admin@example.com"],
        help="Email recipients for reports",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file path",
    ),
    output_dir: str = typer.Option(
        "./output",
        "--output-dir",
        "-o",
        help="Output directory for reports",
    ),
    database_url: str = typer.Option(
        "sqlite:///pipeline.db",
        "--database-url",
        "-d",
        help="Database connection URL",
    ),
    api_base_url: str = typer.Option(
        "https://api.example.com",
        "--api-base-url",
        "-a",
        help="Base URL for API requests",
    ),
    api_key: str = typer.Option(
        ...,
        "--api-key",
        "-k",
        help="API key for authentication",
    ),
    smtp_server: str = typer.Option(
        "smtp.gmail.com",
        "--smtp-server",
        help="SMTP server hostname",
    ),
    smtp_port: int = typer.Option(
        587,
        "--smtp-port",
        help="SMTP server port",
    ),
    smtp_username: str = typer.Option(
        ...,
        "--smtp-username",
        "-u",
        help="SMTP username",
    ),
    smtp_password: str = typer.Option(
        ...,
        "--smtp-password",
        "-p",
        help="SMTP password",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Request timeout in seconds",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        "-r",
        help="Maximum number of retry attempts",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without sending emails",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Logging level",
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log-file",
        help="Log file path",
    ),
) -> None:
    """
    Execute the data pipeline.
    
    This command runs the complete data processing pipeline including
    data fetching, processing, PDF generation, and email reporting.
    """
    # Setup logging
    setup_logging(log_level=log_level, log_file=log_file)
    
    try:
        # Load configuration if provided
        if config and config.exists():
            import json
            with open(config, 'r') as f:
                config_data = json.load(f)
                logger.info("Configuration loaded", config_file=str(config))
        
        # Initialize pipeline
        with Pipeline(
            database_url=database_url,
            api_base_url=api_base_url,
            api_key=api_key,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            output_dir=output_dir,
            timeout=timeout,
            max_retries=max_retries,
        ) as pipeline:
            
            # Test connections
            if not dry_run:
                logger.info("Testing service connections...")
                connections = pipeline.test_connections()
                
                if not all(connections.values()):
                    logger.error("Some service connections failed", connections=connections)
                    raise typer.Exit(1)
                
                logger.info("All service connections successful")
            
            # Run pipeline
            logger.info("Starting pipeline execution...")
            results = pipeline.run_pipeline(endpoints, recipients)
            
            # Print results
            typer.echo("\n" + "=" * 50)
            typer.echo("PIPELINE EXECUTION RESULTS")
            typer.echo("=" * 50)
            typer.echo(f"Status: {results.status}")
            typer.echo(f"Start Time: {results.start_time}")
            typer.echo(f"End Time: {results.end_time}")
            typer.echo(f"Endpoints Processed: {results.endpoints_processed}")
            typer.echo(f"Records Processed: {results.records_processed}")
            typer.echo(f"Emails Sent: {results.emails_sent}")
            typer.echo(f"PDFs Generated: {results.pdfs_generated}")
            
            if results.errors:
                typer.echo("\nErrors:")
                for error in results.errors:
                    typer.echo(f"  - {error}")
            
            typer.echo("=" * 50)
            
            # Exit with error code if failed
            if results.status == "failed":
                raise typer.Exit(1)
                
    except Exception as e:
        logger.error("Pipeline execution failed", error=str(e))
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def test(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file path",
    ),
    database_url: str = typer.Option(
        "sqlite:///pipeline.db",
        "--database-url",
        "-d",
        help="Database connection URL",
    ),
    smtp_server: str = typer.Option(
        "smtp.gmail.com",
        "--smtp-server",
        help="SMTP server hostname",
    ),
    smtp_port: int = typer.Option(
        587,
        "--smtp-port",
        help="SMTP server port",
    ),
    smtp_username: str = typer.Option(
        ...,
        "--smtp-username",
        "-u",
        help="SMTP username",
    ),
    smtp_password: str = typer.Option(
        ...,
        "--smtp-password",
        "-p",
        help="SMTP password",
    ),
) -> None:
    """
    Test service connections.
    
    This command tests connectivity to all required services
    including database and email server.
    """
    setup_logging()
    
    try:
        # Initialize pipeline with minimal configuration
        with Pipeline(
            database_url=database_url,
            api_base_url="https://api.example.com",
            api_key="test-key",
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
        ) as pipeline:
            
            typer.echo("Testing service connections...")
            
            # Test connections
            connections = pipeline.test_connections()
            
            typer.echo("\nConnection Test Results:")
            typer.echo("=" * 30)
            for service, status in connections.items():
                status_str = "✓ Connected" if status else "✗ Failed"
                typer.echo(f"{service}: {status_str}")
            
            if all(connections.values()):
                typer.echo("\n✓ All connections successful!")
            else:
                typer.echo("\n✗ Some connections failed!")
                raise typer.Exit(1)
                
    except Exception as e:
        logger.error("Connection test failed", error=str(e))
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def stats(
    database_url: str = typer.Option(
        "sqlite:///pipeline.db",
        "--database-url",
        "-d",
        help="Database connection URL",
    ),
) -> None:
    """
    Show pipeline statistics.
    
    This command displays statistics about processed data,
    email logs, and API responses.
    """
    setup_logging()
    
    try:
        # Initialize database repository
        from .storage.database import DatabaseRepository
        
        db_repo = DatabaseRepository(database_url)
        
        # Get statistics
        stats = db_repo.get_statistics()
        
        typer.echo("Pipeline Statistics")
        typer.echo("=" * 30)
        typer.echo(f"Pipeline Data Count: {stats['pipeline_data_count']}")
        typer.echo(f"Email Count: {stats['email_count']}")
        typer.echo(f"API Response Count: {stats['api_response_count']}")
        typer.echo(f"Successful Emails: {stats['successful_emails']}")
        typer.echo(f"Successful API Calls: {stats['successful_api_calls']}")
        typer.echo(f"Email Success Rate: {stats['email_success_rate']:.1f}%")
        typer.echo(f"API Success Rate: {stats['api_success_rate']:.1f}%")
        
        db_repo.close()
        
    except Exception as e:
        logger.error("Failed to get statistics", error=str(e))
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    from . import __version__
    typer.echo(f"Pipeline Package v{__version__}")


if __name__ == "__main__":
    app()
