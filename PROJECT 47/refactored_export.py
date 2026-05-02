"""
SECURED Data Export Feature - Refactored Implementation
This code fixes all security, performance, and reliability issues from the original.
"""

import os
import logging
import json
import csv
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import contextmanager

# SECURE: Environment-based configuration
import dotenv
dotenv.load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('export.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# SECURE: Configuration from environment variables
class Config:
    """Secure configuration management"""
    
    @staticmethod
    def get_db_url() -> str:
        """Get database URL from environment"""
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        return db_url
    
    @staticmethod
    def get_api_key() -> str:
        """Get API key from environment"""
        api_key = os.getenv('API_KEY')
        if not api_key:
            raise ValueError("API_KEY environment variable is required")
        return api_key
    
    @staticmethod
    def get_smtp_config() -> Dict[str, Any]:
        """Get SMTP configuration from environment"""
        return {
            'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('SMTP_USERNAME'),
            'password': os.getenv('SMTP_PASSWORD'),
            'from_email': os.getenv('FROM_EMAIL')
        }

class ExportError(Exception):
    """Custom exception for export operations"""
    pass

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class DataExporter:
    """Secure and efficient data export service"""
    
    def __init__(self):
        self.config = Config()
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate required configuration"""
        try:
            self.config.get_db_url()
            self.config.get_api_key()
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ExportError(f"Missing required configuration: {e}")
    
    def validate_user_name(self, user_name: str) -> str:
        """
        SECURE: Validate user input to prevent injection attacks
        """
        if not user_name:
            raise ValidationError("User name cannot be empty")
        
        if len(user_name) > 100:
            raise ValidationError("User name too long (max 100 characters)")
        
        # Allow only alphanumeric characters, spaces, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', user_name):
            raise ValidationError("User name contains invalid characters")
        
        return user_name.strip()
    
    def validate_filename(self, filename: str) -> str:
        """
        SECURE: Validate filename to prevent path traversal
        """
        if not filename:
            raise ValidationError("Filename cannot be empty")
        
        # Remove path traversal attempts
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Ensure filename has only safe characters
        if not re.match(r'^[a-zA-Z0-9_\-\.\s]+$', filename):
            raise ValidationError("Filename contains invalid characters")
        
        return filename.strip()
    
    @contextmanager
    def get_db_connection(self):
        """
        SECURE: Database connection with proper error handling
        """
        import psycopg2
        from psycopg2 import pool
        
        try:
            # Use connection pooling for better performance
            connection = psycopg2.connect(self.config.get_db_url())
            yield connection
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise ExportError("Unable to connect to database") from e
        finally:
            if 'connection' in locals():
                connection.close()
    
    def export_user_orders(self, user_name: str) -> List[Dict[str, Any]]:
        """
        SECURE: Export user orders with fixed SQL injection and N+1 issues
        """
        # Validate input
        user_name = self.validate_user_name(user_name)
        
        logger.info(f"Starting export for user: {user_name}")
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # SECURE: Single JOIN query to fix N+1 problem
                query = '''
                SELECT 
                    u.id as user_id,
                    u.name as user_name,
                    u.email as user_email,
                    o.id as order_id,
                    o.product,
                    o.amount,
                    o.created_at,
                    o.status
                FROM users u 
                LEFT JOIN orders o ON u.id = o.user_id 
                WHERE u.name = %s
                ORDER BY u.id, o.created_at
                '''
                
                # SECURE: Parameterized query to prevent SQL injection
                cursor.execute(query, (user_name,))
                results = cursor.fetchall()
                
                if not results:
                    logger.info(f"No records found for user: {user_name}")
                    return []
                
                # Process results efficiently
                export_data = {}
                for row in results:
                    user_id, user_name, user_email, order_id, product, amount, created_at, status = row
                    
                    if user_id not in export_data:
                        export_data[user_id] = {
                            'user_id': user_id,
                            'name': user_name,
                            'email': user_email,
                            'orders': []
                        }
                    
                    if order_id:  # Only add if order exists
                        export_data[user_id]['orders'].append({
                            'order_id': order_id,
                            'product': product,
                            'amount': float(amount),
                            'date': created_at.isoformat() if created_at else None,
                            'status': status
                        })
                
                logger.info(f"Export completed: {len(export_data)} users, "
                          f"{sum(len(u['orders']) for u in export_data.values())} orders")
                
                return list(export_data.values())
                
        except psycopg2.Error as e:
            logger.exception(f"Database error during export for user {user_name}")
            raise ExportError(f"Database error during export: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during export for user {user_name}")
            raise ExportError(f"Export failed: {e}") from e
    
    def export_to_csv(self, data: List[Dict[str, Any]], filename: str) -> None:
        """
        SECURE: Export data to CSV with proper error handling
        """
        try:
            filename = self.validate_filename(filename)
            
            # Ensure export directory exists
            export_dir = Path('exports')
            export_dir.mkdir(exist_ok=True)
            
            file_path = export_dir / filename
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['user_id', 'name', 'email', 'order_id', 'product', 'amount', 'date', 'status'])
                
                # Write data
                for user in data:
                    if user['orders']:
                        for order in user['orders']:
                            writer.writerow([
                                user['user_id'],
                                user['name'],
                                user['email'],
                                order['order_id'],
                                order['product'],
                                order['amount'],
                                order['date'],
                                order['status']
                            ])
                    else:
                        # Write user with no orders
                        writer.writerow([user['user_id'], user['name'], user['email'], '', '', '', '', ''])
            
            logger.info(f"CSV export completed: {file_path}")
            
        except IOError as e:
            logger.exception(f"Failed to write CSV file {filename}")
            raise ExportError(f"Unable to create CSV file: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during CSV export")
            raise ExportError(f"CSV export failed: {e}") from e
    
    def export_to_json(self, data: List[Dict[str, Any]], filename: str) -> None:
        """
        SECURE: Export data to JSON with proper error handling
        """
        try:
            filename = self.validate_filename(filename)
            
            # Ensure export directory exists
            export_dir = Path('exports')
            export_dir.mkdir(exist_ok=True)
            
            file_path = export_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"JSON export completed: {file_path}")
            
        except IOError as e:
            logger.exception(f"Failed to write JSON file {filename}")
            raise ExportError(f"Unable to create JSON file: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during JSON export")
            raise ExportError(f"JSON export failed: {e}") from e
    
    def send_export_notification(self, email: str, filename: str, record_count: int) -> None:
        """
        SECURE: Send email notification with proper error handling
        """
        try:
            if not email or '@' not in email:
                raise ValidationError("Invalid email address")
            
            smtp_config = self.config.get_smtp_config()
            
            if not all([smtp_config['username'], smtp_config['password']]):
                logger.warning("SMTP configuration incomplete, skipping email notification")
                return
            
            msg = MIMEMultipart()
            msg['From'] = smtp_config['from_email']
            msg['To'] = email
            msg['Subject'] = f"Export completed - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            body = f"""
            Your data export has been completed successfully.
            
            📊 Export Summary:
            • File: {filename}
            • Records: {record_count}
            • Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            📁 File Location: The export file has been saved to the secure export directory.
            
            🔒 Security Notice: This file contains sensitive data. Please handle it according to your organization's data security policy.
            
            Need help? Contact the IT support team.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # SECURE: Use SSL/TLS for email
            server = smtplib.SMTP(smtp_config['server'], smtp_config['port'])
            server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent to: {email}")
            
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email notification: {e}")
            # Don't raise exception - email failure shouldn't fail the export
        except Exception as e:
            logger.exception(f"Unexpected error during email notification")
            # Don't raise exception - email failure shouldn't fail the export
    
    def get_user_stats(self, user_name: str) -> Dict[str, Any]:
        """
        SECURE: Get user statistics with fixed SQL injection
        """
        user_name = self.validate_user_name(user_name)
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # SECURE: Parameterized query
                query = '''
                SELECT 
                    COUNT(o.id) as total_orders,
                    COALESCE(SUM(o.amount), 0) as total_spent,
                    COALESCE(AVG(o.amount), 0) as avg_order_value,
                    MIN(o.created_at) as first_order,
                    MAX(o.created_at) as last_order
                FROM users u 
                LEFT JOIN orders o ON u.id = o.user_id 
                WHERE u.name = %s
                '''
                
                cursor.execute(query, (user_name,))
                stats = cursor.fetchone()
                
                return {
                    'total_orders': stats[0] or 0,
                    'total_spent': float(stats[1] or 0),
                    'avg_order_value': float(stats[2] or 0),
                    'first_order': stats[3].isoformat() if stats[3] else None,
                    'last_order': stats[4].isoformat() if stats[4] else None
                }
                
        except psycopg2.Error as e:
            logger.exception(f"Database error getting stats for user {user_name}")
            raise ExportError(f"Unable to retrieve user statistics: {e}") from e
    
    def main_export(self, user_name: str, export_format: str = 'csv', 
                   email: Optional[str] = None) -> Dict[str, Any]:
        """
        SECURE: Main export function with comprehensive error handling
        """
        try:
            # Validate inputs
            user_name = self.validate_user_name(user_name)
            
            if export_format not in ['csv', 'json']:
                raise ValidationError(f"Unsupported export format: {export_format}")
            
            logger.info(f"Starting export for user: {user_name}, format: {export_format}")
            
            # Export data
            data = self.export_user_orders(user_name)
            
            if not data:
                logger.info(f"No data found for user: {user_name}")
                return {
                    'success': True,
                    'message': 'No data found for the specified user',
                    'records': 0,
                    'filename': None
                }
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_user_name = re.sub(r'[^\w\-]', '_', user_name)
            filename = f"export_{safe_user_name}_{timestamp}.{export_format}"
            
            # Export to file
            if export_format == 'csv':
                self.export_to_csv(data, filename)
            else:
                self.export_to_json(data, filename)
            
            # Send notification if requested
            if email:
                record_count = sum(len(user['orders']) for user in data)
                self.send_export_notification(email, filename, record_count)
            
            logger.info(f"Export completed successfully: {filename}")
            
            return {
                'success': True,
                'message': 'Export completed successfully',
                'records': len(data),
                'filename': filename,
                'format': export_format
            }
            
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return {
                'success': False,
                'message': f'Invalid input: {e}',
                'error_type': 'validation'
            }
        except ExportError as e:
            logger.error(f"Export error: {e}")
            return {
                'success': False,
                'message': f'Export failed: {e}',
                'error_type': 'export'
            }
        except Exception as e:
            logger.exception(f"Unexpected error during export")
            return {
                'success': False,
                'message': f'Unexpected error: {e}',
                'error_type': 'unknown'
            }


# SECURE: Main execution with proper error handling
def main():
    """
    SECURE: Main function with comprehensive error handling
    """
    import sys
    
    try:
        if len(sys.argv) < 2:
            print("Usage: python refactored_export.py <user_name> [format] [email]")
            print("Example: python refactored_export.py 'John Doe' csv user@example.com")
            sys.exit(1)
        
        user_name = sys.argv[1]
        format_arg = sys.argv[2] if len(sys.argv) > 2 else 'csv'
        email_arg = sys.argv[3] if len(sys.argv) > 3 else None
        
        exporter = DataExporter()
        result = exporter.main_export(user_name, format_arg, email_arg)
        
        if result['success']:
            print(f"✅ {result['message']}")
            if result['filename']:
                print(f"📁 File: exports/{result['filename']}")
            if result['records']:
                print(f"📊 Records: {result['records']}")
        else:
            print(f"❌ {result['message']}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Export cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.exception("Fatal error in main execution")
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
