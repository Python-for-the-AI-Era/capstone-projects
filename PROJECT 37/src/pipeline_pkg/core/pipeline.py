"""
Core pipeline orchestrator.

This module contains the main Pipeline class that orchestrates
the data processing workflow and coordinates all services.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from ..clients.http import HTTPClient
from ..models import PipelineData, PipelineResult
from ..services.email import EmailSender
from ..services.pdf import PDFGenerator
from ..storage.database import DatabaseRepository


class Pipeline:
    """
    Main pipeline orchestrator that coordinates all services.
    
    This class is the brain of the pipeline, orchestrating data flow
    between HTTP client, database, email service, and PDF generator.
    """
    
    def __init__(
        self,
        database_url: str,
        api_base_url: str,
        api_key: str,
        smtp_server: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        output_dir: str = "./output",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the pipeline.
        
        Args:
            database_url: Database connection URL
            api_base_url: Base URL for API requests
            api_key: API key for authentication
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            output_dir: Directory for output files
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.logger = structlog.get_logger(__name__)
        
        # Initialize services
        self.db_repo = DatabaseRepository(database_url)
        self.http_client = HTTPClient(
            base_url=api_base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.email_sender = EmailSender(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            username=smtp_username,
            password=smtp_password,
        )
        self.pdf_generator = PDFGenerator(output_dir)
        
        self.logger.info("Pipeline initialized successfully")
    
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and transform data.
        
        Args:
            data: Raw data dictionary
            
        Returns:
            Processed data dictionary
        """
        processed = {}
        
        # Data validation
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        # Data cleaning and transformation
        for key, value in data.items():
            if isinstance(value, str):
                processed[key] = value.strip().lower()
            elif isinstance(value, (int, float)):
                processed[key] = value
            elif isinstance(value, list):
                processed[key] = [
                    item.strip().lower() if isinstance(item, str) else item
                    for item in value
                ]
            else:
                processed[key] = value
        
        # Add processing metadata
        processed["processed_at"] = datetime.utcnow().isoformat()
        processed["processing_version"] = "1.0"
        
        self.logger.debug("Data processed successfully", keys=list(processed.keys()))
        return processed
    
    def fetch_and_process_endpoint(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch data from an endpoint and process it.
        
        Args:
            endpoint: API endpoint to fetch
            params: Optional query parameters
            
        Returns:
            Processed data or None if failed
        """
        try:
            # Fetch data from API
            raw_data, api_response = self.http_client.get(endpoint, params)
            
            # Save API response log
            self.db_repo.save_api_response(api_response)
            
            if not raw_data:
                self.logger.warning("No data received from endpoint", endpoint=endpoint)
                return None
            
            # Process data
            processed_data = self.process_data(raw_data)
            
            # Save to database
            pipeline_data = PipelineData(
                source=endpoint,
                data=processed_data,
                processed_at=datetime.utcnow(),
            )
            record_id = self.db_repo.save_pipeline_data(pipeline_data)
            
            self.logger.info(
                "Endpoint processed successfully",
                endpoint=endpoint,
                record_id=record_id,
            )
            
            return processed_data
            
        except Exception as e:
            self.logger.error(
                "Failed to process endpoint",
                endpoint=endpoint,
                error=str(e),
            )
            return None
    
    def run_pipeline(
        self,
        endpoints: List[str],
        recipients: List[str],
        params: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Run the complete data pipeline.
        
        Args:
            endpoints: List of API endpoints to process
            recipients: List of email recipients
            params: Optional query parameters for all endpoints
            
        Returns:
            Pipeline execution results
        """
        result = PipelineResult(
            start_time=datetime.utcnow().isoformat(),
            status="running",
        )
        
        try:
            self.logger.info(
                "Starting pipeline execution",
                endpoints=endpoints,
                recipients=recipients,
            )
            
            all_processed_data = []
            
            # Process each endpoint
            for endpoint in endpoints:
                processed_data = self.fetch_and_process_endpoint(endpoint, params)
                if processed_data:
                    all_processed_data.append(processed_data)
                    result.endpoints_processed += 1
                    result.records_processed += 1
                else:
                    error_msg = f"Failed to process endpoint: {endpoint}"
                    result.errors.append(error_msg)
            
            # Generate PDF report if we have data
            pdf_path = None
            if all_processed_data:
                try:
                    pdf_path = self.pdf_generator.generate_report(
                        data=all_processed_data,
                        title="Pipeline Execution Report",
                        subtitle=f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    )
                    result.pdfs_generated = 1
                    
                    self.logger.info("PDF report generated", pdf_path=str(pdf_path))
                    
                except Exception as e:
                    error_msg = f"Failed to generate PDF: {e}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)
            
            # Send email reports
            if pdf_path and recipients:
                for recipient in recipients:
                    try:
                        subject = f"Pipeline Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        body = f"""
Pipeline execution completed successfully.

Summary:
- Endpoints processed: {result.endpoints_processed}
- Records processed: {result.records_processed}
- PDF report attached: {pdf_path.name}

Please find the detailed report attached.

Pipeline execution started: {result.start_time}
Pipeline execution completed: {datetime.utcnow().isoformat()}
"""
                        
                        email_log = self.email_sender.send_email(
                            recipient=recipient,
                            subject=subject,
                            body=body,
                            attachments=[str(pdf_path)],
                        )
                        
                        # Save email log
                        self.db_repo.save_email_log(email_log)
                        
                        if email_log.status == "sent":
                            result.emails_sent += 1
                        else:
                            error_msg = f"Failed to send email to {recipient}: {email_log.error_message}"
                            result.errors.append(error_msg)
                            
                    except Exception as e:
                        error_msg = f"Error sending email to {recipient}: {e}"
                        result.errors.append(error_msg)
                        self.logger.error(error_msg)
            
            # Set final status
            result.end_time = datetime.utcnow().isoformat()
            if result.errors:
                result.status = "completed_with_errors"
            else:
                result.status = "completed"
            
            self.logger.info(
                "Pipeline execution completed",
                status=result.status,
                endpoints_processed=result.endpoints_processed,
                records_processed=result.records_processed,
                emails_sent=result.emails_sent,
                errors_count=len(result.errors),
            )
            
        except Exception as e:
            result.end_time = datetime.utcnow().isoformat()
            result.status = "failed"
            result.errors.append(str(e))
            
            self.logger.error(
                "Pipeline execution failed",
                error=str(e),
                endpoints_processed=result.endpoints_processed,
                errors_count=len(result.errors),
            )
            raise
        
        return result
    
    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.
        
        Returns:
            Dictionary with pipeline statistics
        """
        return self.db_repo.get_statistics()
    
    def test_connections(self) -> Dict[str, bool]:
        """
        Test all service connections.
        
        Returns:
            Dictionary with connection test results
        """
        results = {}
        
        # Test database
        try:
            stats = self.db_repo.get_statistics()
            results["database"] = True
        except Exception as e:
            self.logger.error("Database connection test failed", error=str(e))
            results["database"] = False
        
        # Test email
        results["email"] = self.email_sender.test_connection()
        
        self.logger.info("Connection tests completed", results=results)
        return results
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self.http_client.close()
            self.db_repo.close()
            self.logger.info("Pipeline cleanup completed")
        except Exception as e:
            self.logger.error("Error during cleanup", error=str(e))
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
