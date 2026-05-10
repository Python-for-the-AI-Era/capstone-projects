#!/usr/bin/env python3
"""
Main entry point for the Competitive Intelligence System
"""

import argparse
import logging
import asyncio
from datetime import datetime
from tasks import run_weekly_intelligence_report, test_scraping_task
from reporter import create_sample_report, validate_template
from delivery import EmailDelivery
from deduplicator import ContentDeduplicator
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_test_scraping():
    """Run a test scraping task"""
    logger.info("Running test scraping task...")
    
    task = test_scraping_task.delay()
    result = task.get(timeout=300)  # 5 minute timeout
    
    logger.info(f"Test scraping result: {result}")
    return result


def run_full_report():
    """Run the full competitive intelligence report"""
    logger.info("Starting full competitive intelligence report...")
    
    task = run_weekly_intelligence_report.delay()
    result = task.get(timeout=1800)  # 30 minute timeout
    
    logger.info(f"Full report result: {result}")
    return result


def test_email_delivery():
    """Test email delivery system"""
    logger.info("Testing email delivery...")
    
    delivery = EmailDelivery()
    
    # Test connection
    connection_test = delivery.test_connection()
    logger.info(f"SES connection test: {connection_test}")
    
    # Send test email
    email_sent = delivery.send_test_email()
    logger.info(f"Test email sent: {email_sent}")
    
    return connection_test, email_sent


def test_template_validation():
    """Test Jinja2 template validation"""
    logger.info("Testing template validation...")
    
    is_valid = validate_template()
    logger.info(f"Template validation: {'PASSED' if is_valid else 'FAILED'}")
    
    return is_valid


def test_sample_report():
    """Generate a sample report for testing"""
    logger.info("Generating sample report...")
    
    try:
        html_content, pdf_path = create_sample_report()
        logger.info(f"Sample report generated. PDF: {pdf_path}")
        return html_content, pdf_path
    except Exception as e:
        logger.error(f"Error generating sample report: {e}")
        return None, None


def test_redis_connection():
    """Test Redis connection and deduplication"""
    logger.info("Testing Redis connection...")
    
    deduplicator = ContentDeduplicator()
    stats = deduplicator.get_statistics()
    logger.info(f"Redis stats: {stats}")
    
    return stats


def run_all_tests():
    """Run all system tests"""
    logger.info("Running comprehensive system tests...")
    
    results = {}
    
    # Test template validation
    results['template_validation'] = test_template_validation()
    
    # Test Redis connection
    results['redis_connection'] = test_redis_connection()
    
    # Test email delivery
    results['email_delivery'] = test_email_delivery()
    
    # Test sample report generation
    results['sample_report'] = test_sample_report()
    
    # Test scraping (if OpenAI API key is available)
    if settings.openai_api_key:
        results['test_scraping'] = run_test_scraping()
    else:
        results['test_scraping'] = "Skipped - No OpenAI API key"
    
    logger.info("=== TEST RESULTS ===")
    for test_name, result in results.items():
        status = "✅ PASSED" if result is True else "❌ FAILED" if result is False else "⚠️ SKIPPED"
        logger.info(f"{test_name}: {status}")
        if isinstance(result, dict) and 'error' in result:
            logger.error(f"  Error: {result['error']}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Competitive Intelligence System")
    parser.add_argument("--test", action="store_true", help="Run all system tests")
    parser.add_argument("--test-scraping", action="store_true", help="Run test scraping task")
    parser.add_argument("--test-email", action="store_true", help="Test email delivery")
    parser.add_argument("--test-template", action="store_true", help="Test template validation")
    parser.add_argument("--test-redis", action="store_true", help="Test Redis connection")
    parser.add_argument("--sample-report", action="store_true", help="Generate sample report")
    parser.add_argument("--run-report", action="store_true", help="Run full intelligence report")
    parser.add_argument("--validate-config", action="store_true", help="Validate configuration")
    
    args = parser.parse_args()
    
    if args.validate_config:
        print("Configuration validation:")
        print(f"OpenAI API Key: {'✅ Set' if settings.openai_api_key else '❌ Not set'}")
        print(f"AWS Access Key: {'✅ Set' if settings.aws_access_key_id else '❌ Not set'}")
        print(f"Competitors: {len(settings.competitors)} configured")
        print(f"Email recipients: {len(settings.email_to) if isinstance(settings.email_to, list) else 1}")
        return
    
    if args.test:
        run_all_tests()
    elif args.test_scraping:
        run_test_scraping()
    elif args.test_email:
        test_email_delivery()
    elif args.test_template:
        test_template_validation()
    elif args.test_redis:
        test_redis_connection()
    elif args.sample_report:
        test_sample_report()
    elif args.run_report:
        run_full_report()
    else:
        print("Competitive Intelligence System")
        print("Usage examples:")
        print("  python main.py --test              # Run all tests")
        print("  python main.py --test-scraping     # Test scraping")
        print("  python main.py --test-email        # Test email delivery")
        print("  python main.py --sample-report     # Generate sample report")
        print("  python main.py --run-report        # Run full report")
        print("  python main.py --validate-config   # Validate configuration")


if __name__ == "__main__":
    main()
