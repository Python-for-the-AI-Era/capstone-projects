"""
Tests for PDF generation service.

This module tests PDF generation functionality including
table creation, styling, and report generation.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict, List

import pytest
from reportlab.platypus import SimpleDocTemplate

from pipeline_pkg.services.pdf import PDFGenerator
from pipeline_pkg.models import PipelineData


class TestPDFGenerator:
    """Test cases for PDFGenerator."""
    
    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.output_dir = Path("/tmp/test_output")
        self.generator = PDFGenerator(self.output_dir)
    
    def test_initialization(self) -> None:
        """Test PDFGenerator initialization."""
        assert self.generator.output_dir == self.output_dir
        assert self.output_dir.exists()
        assert self.generator.styles is not None
    
    def test_setup_custom_styles(self) -> None:
        """Test custom styles setup."""
        # Check that custom styles were added
        assert "CustomTitle" in self.generator.styles
        assert "CustomHeading" in self.generator.styles
        assert "CustomNormal" in self.generator.styles
    
    def test_create_title_section(self) -> None:
        """Test title section creation."""
        elements = self.generator._create_title_section("Test Title", "Test Subtitle")
        
        assert len(elements) == 3  # Title, spacer, subtitle
        assert elements[0].text == "Test Title"
        assert elements[2].text == "Test Subtitle"
    
    def test_create_title_section_no_subtitle(self) -> None:
        """Test title section creation without subtitle."""
        elements = self.generator._create_title_section("Test Title")
        
        assert len(elements) == 2  # Title, spacer
        assert elements[0].text == "Test Title"
    
    def test_create_summary_section(self) -> None:
        """Test summary section creation."""
        test_data = [
            {"id": 1, "name": "Test 1"},
            {"id": 2, "name": "Test 2"},
        ]
        
        elements = self.generator._create_summary_section(test_data)
        
        assert len(elements) >= 2  # Heading + content
        assert any("2 records" in str(element) for element in elements)
    
    def test_create_summary_section_empty_data(self) -> None:
        """Test summary section creation with empty data."""
        elements = self.generator._create_summary_section([])
        
        assert len(elements) >= 2  # Heading + content
        assert any("0 records" in str(element) for element in elements)
    
    def test_create_data_table(self) -> None:
        """Test data table creation."""
        test_data = [
            {"source": "api1", "processed_at": "2023-01-01", "data": {"key": "value"}},
            {"source": "api2", "processed_at": "2023-01-02", "data": {"key2": "value2"}},
        ]
        
        elements = self.generator._create_data_table(test_data)
        
        assert len(elements) >= 2  # Heading + table
        # Should have header + 2 data rows
        table = elements[-1]
        assert hasattr(table, '_arg')  # Table object
    
    def test_create_data_table_empty(self) -> None:
        """Test data table creation with empty data."""
        elements = self.generator._create_data_table([])
        
        assert len(elements) >= 1  # At least heading
        assert any("No data available" in str(element) for element in elements)
    
    def test_create_data_table_truncated(self) -> None:
        """Test data table creation with truncated data."""
        # Create data with more than max_rows (default 20)
        test_data = [{"id": i, "name": f"Test {i}"} for i in range(25)]
        
        elements = self.generator._create_data_table(test_data)
        
        # Should include truncation note
        assert any("first 20 records" in str(element) for element in elements)
    
    def test_create_statistics_section(self) -> None:
        """Test statistics section creation."""
        test_data = [
            {"source": "api1", "data": {}},
            {"source": "api1", "data": {}},
            {"source": "api2", "data": {}},
        ]
        
        elements = self.generator._create_statistics_section(test_data)
        
        assert len(elements) >= 2  # Heading + table
        # Should include statistics about sources
        stats_text = str(elements)
        assert "Total Records: 3" in stats_text
        assert "Unique Sources: 2" in stats_text
    
    def test_create_statistics_section_empty(self) -> None:
        """Test statistics section creation with empty data."""
        elements = self.generator._create_statistics_section([])
        
        assert len(elements) >= 2  # Heading + table
        stats_text = str(elements)
        assert "Total Records: 0" in stats_text
        assert "Unique Sources: 0" in stats_text
    
    def test_create_footer_section(self) -> None:
        """Test footer section creation."""
        elements = self.generator._create_footer_section()
        
        assert len(elements) >= 2  # Spacer + footer content
        footer_text = str(elements[-1])
        assert "Pipeline Package v1.0.0" in footer_text
        assert datetime.now().strftime('%Y-%m-%d') in footer_text
    
    @patch("pipeline_pkg.services.pdf.SimpleDocTemplate")
    def test_generate_report_success(self, mock_doc_template: Mock) -> None:
        """Test successful PDF report generation."""
        mock_doc = Mock()
        mock_doc_template.return_value = mock_doc
        
        test_data = [
            {"source": "api1", "processed_at": "2023-01-01", "data": {"key": "value"}},
        ]
        
        result_path = self.generator.generate_report(
            data=test_data,
            filename="test_report.pdf",
            title="Test Report",
        )
        
        # Check that SimpleDocTemplate was called
        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()
        
        # Check return path
        assert result_path == self.output_dir / "test_report.pdf"
    
    @patch("pipeline_pkg.services.pdf.SimpleDocTemplate")
    def test_generate_report_auto_filename(self, mock_doc_template: Mock) -> None:
        """Test PDF report generation with auto-generated filename."""
        mock_doc = Mock()
        mock_doc_template.return_value = mock_doc
        
        test_data = [{"source": "api1", "data": {}}]
        
        with patch('pipeline_pkg.services.pdf.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20231201_120000"
            
            result_path = self.generator.generate_report(data=test_data)
            
            expected_filename = "pipeline_report_20231201_120000.pdf"
            assert result_path == self.output_dir / expected_filename
    
    @patch("pipeline_pkg.services.pdf.SimpleDocTemplate")
    def test_generate_report_failure(self, mock_doc_template: Mock) -> None:
        """Test PDF report generation failure."""
        mock_doc_template.side_effect = Exception("PDF generation failed")
        
        test_data = [{"source": "api1", "data": {}}]
        
        with pytest.raises(Exception, match="PDF generation failed"):
            self.generator.generate_report(data=test_data)
    
    @patch("pipeline_pkg.services.pdf.SimpleDocTemplate")
    def test_generate_summary_report(self, mock_doc_template: Mock) -> None:
        """Test generating report from PipelineData models."""
        mock_doc = Mock()
        mock_doc_template.return_value = mock_doc
        
        # Create PipelineData objects
        pipeline_data = [
            PipelineData(
                source="api1",
                data={"key": "value"},
                processed_at=datetime(2023, 1, 1),
            ),
            PipelineData(
                source="api2",
                data={"key2": "value2"},
                processed_at=datetime(2023, 1, 2),
            ),
        ]
        
        result_path = self.generator.generate_summary_report(pipeline_data)
        
        # Check that SimpleDocTemplate was called
        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()
        
        # Check return path
        assert result_path.name.startswith("pipeline_summary_report_")
        assert result_path.suffix == ".pdf"
    
    def test_generate_summary_report_empty(self) -> None:
        """Test generating summary report with empty data."""
        with patch("pipeline_pkg.services.pdf.SimpleDocTemplate") as mock_doc_template:
            mock_doc = Mock()
            mock_doc_template.return_value = mock_doc
            
            result_path = self.generator.generate_summary_report([])
            
            mock_doc.build.assert_called_once()
            assert result_path.name.startswith("pipeline_summary_report_")
    
    def test_data_preview_truncation(self) -> None:
        """Test that data preview is properly truncated."""
        # Create data with long content
        long_data = {"key": "x" * 200}  # 200 characters
        test_data = [{"source": "api1", "data": long_data}]
        
        elements = self.generator._create_data_table(test_data)
        
        # Find the table and check data truncation
        table = None
        for element in elements:
            if hasattr(element, '_arg'):  # Table object
                table = element
                break
        
        assert table is not None
        # The data should be truncated and end with "..."
        table_data = str(table)
        assert "..." in table_data
    
    def test_special_characters_in_data(self) -> None:
        """Test handling of special characters in data."""
        test_data = [
            {
                "source": "api1",
                "data": {
                    "special_chars": "Hello & <world>! @#$%^&*()",
                    "unicode": "Café naïve résumé",
                }
            }
        ]
        
        # Should not raise an exception
        elements = self.generator._create_data_table(test_data)
        assert len(elements) >= 2
    
    def test_none_values_in_data(self) -> None:
        """Test handling of None values in data."""
        test_data = [
            {
                "source": "api1",
                "data": {
                    "null_value": None,
                    "missing_value": "N/A",
                }
            }
        ]
        
        elements = self.generator._create_data_table(test_data)
        assert len(elements) >= 2
    
    @patch("pipeline_pkg.services.pdf.SimpleDocTemplate")
    def test_large_dataset_handling(self, mock_doc_template: Mock) -> None:
        """Test handling of large datasets."""
        mock_doc = Mock()
        mock_doc_template.return_value = mock_doc
        
        # Create large dataset
        test_data = [{"id": i, "name": f"Item {i}"} for i in range(100)]
        
        result_path = self.generator.generate_report(data=test_data)
        
        mock_doc.build.assert_called_once()
        assert result_path == self.output_dir / "pipeline_report_20231201_120000.pdf"
