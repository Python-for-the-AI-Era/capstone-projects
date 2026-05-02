"""
PDF generation service for creating reports.

This module provides PDF generation functionality with tables,
charts, and professional formatting.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import structlog

from ..models import PipelineData


class PDFGenerator:
    """
    PDF generation service for creating professional reports.
    
    Provides table generation, styling, and layout management
    for data pipeline reports.
    """
    
    def __init__(self, output_dir: Path) -> None:
        """
        Initialize the PDF generator.
        
        Args:
            output_dir: Directory to save PDF files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = structlog.get_logger(__name__)
        
        # Initialize styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        # Custom title style
        self.styles.add(
            "CustomTitle",
            parent=self.styles["Title"],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.darkblue,
        )
        
        # Custom heading style
        self.styles.add(
            "CustomHeading",
            parent=self.styles["Heading1"],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkgreen,
        )
        
        # Custom normal style
        self.styles.add(
            "CustomNormal",
            parent=self.styles["Normal"],
            fontSize=10,
            spaceAfter=6,
        )
    
    def _create_title_section(self, title: str, subtitle: Optional[str] = None) -> List:
        """Create title section of the report."""
        elements = []
        
        # Main title
        title_paragraph = Paragraph(title, self.styles["CustomTitle"])
        elements.append(title_paragraph)
        elements.append(Spacer(1, 12))
        
        # Subtitle
        if subtitle:
            subtitle_paragraph = Paragraph(subtitle, self.styles["CustomHeading"])
            elements.append(subtitle_paragraph)
            elements.append(Spacer(1, 12))
        
        return elements
    
    def _create_summary_section(self, data: List[Dict[str, Any]]) -> List:
        """Create summary section of the report."""
        elements = []
        
        # Summary heading
        summary_heading = Paragraph("Executive Summary", self.styles["CustomHeading"])
        elements.append(summary_heading)
        elements.append(Spacer(1, 12))
        
        # Summary text
        summary_text = f"""
        This report contains {len(data)} records processed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
        All data has been validated and processed according to the pipeline specifications.
        The report includes detailed information about each processed record, including
        source, processing timestamp, and data content.
        """
        
        summary_paragraph = Paragraph(summary_text, self.styles["CustomNormal"])
        elements.append(summary_paragraph)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_data_table(self, data: List[Dict[str, Any]], max_rows: int = 20) -> List:
        """Create data table section."""
        elements = []
        
        if not data:
            no_data_paragraph = Paragraph("No data available", self.styles["CustomNormal"])
            elements.append(no_data_paragraph)
            return elements
        
        # Table heading
        table_heading = Paragraph("Data Details", self.styles["CustomHeading"])
        elements.append(table_heading)
        elements.append(Spacer(1, 12))
        
        # Prepare table data
        headers = ["#", "Source", "Processed At", "Data Preview"]
        table_data = [headers]
        
        for i, item in enumerate(data[:max_rows]):
            row = [
                str(i + 1),
                str(item.get("source", "N/A")),
                str(item.get("processed_at", "N/A")),
                str(item.get("data", {}))[:100] + "..." if len(str(item.get("data", {}))) > 100 else str(item.get("data", {})),
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, repeatRows=1)
        
        # Style the table
        table.setStyle(
            TableStyle([
                # Header styling
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                
                # Data row styling
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                
                # Grid
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                
                # Column widths
                ("COLWIDTHS", (0, 0), (-1, -1), [30, 80, 120, 300]),
            ])
        )
        
        elements.append(table)
        
        # Add note if data is truncated
        if len(data) > max_rows:
            note_text = f"""
            Note: This table shows the first {max_rows} records. 
            The complete dataset contains {len(data)} records.
            """
            note_paragraph = Paragraph(note_text, self.styles["CustomNormal"])
            elements.append(Spacer(1, 12))
            elements.append(note_paragraph)
        
        return elements
    
    def _create_statistics_section(self, data: List[Dict[str, Any]]) -> List:
        """Create statistics section."""
        elements = []
        
        # Statistics heading
        stats_heading = Paragraph("Statistics", self.styles["CustomHeading"])
        elements.append(stats_heading)
        elements.append(Spacer(1, 12))
        
        # Calculate statistics
        sources = {}
        for item in data:
            source = item.get("source", "Unknown")
            sources[source] = sources.get(source, 0) + 1
        
        # Create statistics table
        stats_data = [["Metric", "Value"]]
        stats_data.append(["Total Records", str(len(data))])
        stats_data.append(["Unique Sources", str(len(sources))])
        
        for source, count in sources.items():
            stats_data.append([f"Source: {source}", str(count)])
        
        stats_table = Table(stats_data)
        stats_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("COLWIDTHS", (0, 0), (-1, -1), [200, 100]),
            ])
        )
        
        elements.append(stats_table)
        return elements
    
    def _create_footer_section(self) -> List:
        """Create footer section."""
        elements = []
        
        elements.append(Spacer(1, 30))
        
        footer_text = f"""
        Report generated by Pipeline Package v1.0.0 on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
        This is an automated report. For questions, please contact the pipeline administrator.
        """
        
        footer_paragraph = Paragraph(footer_text, self.styles["CustomNormal"])
        elements.append(footer_paragraph)
        
        return elements
    
    def generate_report(
        self,
        data: List[Dict[str, Any]],
        filename: Optional[str] = None,
        title: str = "Pipeline Data Report",
        subtitle: Optional[str] = None,
    ) -> Path:
        """
        Generate PDF report from pipeline data.
        
        Args:
            data: List of pipeline data records
            filename: Optional filename (auto-generated if not provided)
            title: Report title
            subtitle: Optional subtitle
            
        Returns:
            Path to generated PDF file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pipeline_report_{timestamp}.pdf"
        
        output_path = self.output_dir / filename
        
        try:
            # Create document
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            story = []
            
            # Build report sections
            story.extend(self._create_title_section(title, subtitle))
            story.extend(self._create_summary_section(data))
            story.extend(self._create_statistics_section(data))
            story.extend(self._create_data_table(data))
            story.extend(self._create_footer_section())
            
            # Build PDF
            doc.build(story)
            
            self.logger.info(
                "PDF report generated successfully",
                output_path=str(output_path),
                record_count=len(data),
                file_size=output_path.stat().st_size,
            )
            
            return output_path
            
        except Exception as e:
            self.logger.error(
                "Failed to generate PDF report",
                filename=filename,
                error=str(e),
            )
            raise
    
    def generate_summary_report(
        self,
        pipeline_data: List[PipelineData],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate PDF report from PipelineData models.
        
        Args:
            pipeline_data: List of PipelineData models
            filename: Optional filename
            
        Returns:
            Path to generated PDF file
        """
        # Convert PipelineData to dictionaries
        data_dicts = []
        for item in pipeline_data:
            data_dict = {
                "source": item.source,
                "processed_at": item.processed_at.isoformat() if item.processed_at else None,
                "processing_version": item.processing_version,
                "data": item.data,
            }
            data_dicts.append(data_dict)
        
        return self.generate_report(
            data=data_dicts,
            filename=filename,
            title="Pipeline Data Summary Report",
            subtitle="Processed Pipeline Data Analysis",
        )
