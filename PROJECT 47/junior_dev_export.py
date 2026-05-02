"""
VULNERABLE Data Export Feature - Junior Developer Implementation
This code contains multiple security and performance issues for educational purposes.
"""

import psycopg2
import json
from datetime import datetime
from typing import List, Dict, Any

# VULNERABILITY: Hardcoded credentials - CRITICAL SECURITY ISSUE
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "company_prod"
DB_USER = "admin"
DB_PASSWORD = "super_secret_password_123"

# VULNERABILITY: Hardcoded API key
API_KEY = "sk-1234567890abcdef1234567890abcdef12345678"

def export_user_orders(user_name: str) -> List[Dict[str, Any]]:
    """
    VULNERABLE: Export user orders with multiple security and performance issues
    """
    # Connect to database with hardcoded credentials
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cursor = conn.cursor()
    
    # VULNERABILITY: SQL Injection - CRITICAL SECURITY ISSUE
    # Using f-string to inject user input directly into SQL query
    query = f'SELECT * FROM users WHERE name = "{user_name}"'
    cursor.execute(query)
    
    users = cursor.fetchall()
    
    export_data = []
    
    # VULNERABILITY: N+1 Query Problem - MAJOR PERFORMANCE ISSUE
    # This makes a separate database call for each user's orders
    for user in users:
        user_id = user[0]
        user_name = user[1]
        
        # Separate query for each user's orders - this is the N+1 problem
        orders_query = f'SELECT * FROM orders WHERE user_id = {user_id}'
        cursor.execute(orders_query)
        orders = cursor.fetchall()
        
        user_data = {
            'user_id': user_id,
            'name': user_name,
            'orders': []
        }
        
        for order in orders:
            order_data = {
                'order_id': order[0],
                'product': order[2],
                'amount': order[3],
                'date': order[4].isoformat() if order[4] else None
            }
            user_data['orders'].append(order_data)
        
        export_data.append(user_data)
    
    conn.close()
    
    return export_data

def export_to_csv(data: List[Dict[str, Any]], filename: str) -> None:
    """
    VULNERABILITY: No error handling - MAJOR RELIABILITY ISSUE
    """
    # No try/catch block - any error will crash the entire process
    with open(filename, 'w') as f:
        # Write CSV header
        f.write('user_id,name,order_id,product,amount,date\n')
        
        for user in data:
            for order in user['orders']:
                f.write(f"{user['user_id']},{user['name']},{order['order_id']},"
                       f"{order['product']},{order['amount']},{order['date']}\n")

def export_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    """
    VULNERABILITY: No error handling - MAJOR RELIABILITY ISSUE
    """
    # No validation of filename - potential path traversal
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def send_export_notification(email: str, filename: str) -> None:
    """
    VULNERABILITY: No error handling and hardcoded credentials
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # VULNERABILITY: Hardcoded email credentials
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_username = "company@gmail.com"
    smtp_password = "email_password_123"
    
    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = email
    msg['Subject'] = f"Export completed - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = f"""
    Your data export has been completed.
    
    File: {filename}
    Records: {len(data)}
    
    Please download the file from the secure location.
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    # VULNERABILITY: No error handling for email sending
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_username, smtp_password)
    server.send_message(msg)
    server.quit()

def main_export(user_name: str, export_format: str = 'csv', email: str = None):
    """
    VULNERABILITY: Main function with multiple issues
    """
    print(f"Starting export for user: {user_name}")
    
    # VULNERABILITY: No input validation
    data = export_user_orders(user_name)
    
    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"export_{user_name}_{timestamp}.{export_format}"
    
    # VULNERABILITY: No error handling for export operations
    if export_format == 'csv':
        export_to_csv(data, filename)
    elif export_format == 'json':
        export_to_json(data, filename)
    else:
        print(f"Unsupported format: {export_format}")
        return
    
    print(f"Export completed: {filename}")
    
    # VULNERABILITY: No error handling for notification
    if email:
        send_export_notification(email, filename)
    
    return filename

# VULNERABILITY: No logging anywhere in the application
def get_user_stats(user_name: str) -> Dict[str, Any]:
    """
    VULNERABILITY: More SQL injection and no error handling
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cursor = conn.cursor()
    
    # VULNERABILITY: Another SQL injection vulnerability
    stats_query = f'''
    SELECT 
        COUNT(*) as total_orders,
        SUM(amount) as total_spent,
        AVG(amount) as avg_order_value
    FROM orders o 
    JOIN users u ON o.user_id = u.id 
    WHERE u.name = "{user_name}"
    '''
    
    cursor.execute(stats_query)
    stats = cursor.fetchone()
    
    conn.close()
    
    return {
        'total_orders': stats[0],
        'total_spent': stats[1],
        'avg_order_value': stats[2]
    }

# VULNERABILITY: No input validation on user input
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python junior_dev_export.py <user_name> [format] [email]")
        sys.exit(1)
    
    user_name = sys.argv[1]
    format_arg = sys.argv[2] if len(sys.argv) > 2 else 'csv'
    email_arg = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        result = main_export(user_name, format_arg, email_arg)
        print(f"Export successful: {result}")
    except Exception as e:
        # VULNERABILITY: Poor error handling - just prints to console
        print(f"Export failed: {e}")
        sys.exit(1)
