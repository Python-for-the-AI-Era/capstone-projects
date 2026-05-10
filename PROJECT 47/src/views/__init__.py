"""
Views for the data export feature.

This module contains the original junior developer's code with security vulnerabilities
and performance issues that need to be reviewed and fixed.
"""

from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import csv
import io
import os

# Database configuration (HARDCODED - SECURITY ISSUE!)
DB_HOST = "localhost"
DB_USER = "admin"
DB_PASSWORD = "password123"
DB_NAME = "export_db"

app = Flask(__name__)

# Database connection
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


@app.route('/export/users', methods=['GET'])
def export_users():
    """
    Export users and their orders to CSV.
    
    This function contains multiple security and performance issues:
    1. SQL injection vulnerability
    2. N+1 query problem
    3. No error handling
    4. Hardcoded credentials
    5. No input validation
    """
    
    # Get user name from query parameter (NO VALIDATION - SECURITY ISSUE!)
    name = request.args.get('name', '')
    
    # SQL INJECTION VULNERABILITY - Using f-string with user input
    sql_query = f'SELECT * FROM users WHERE name = "{name}"'
    
    session = Session()
    
    # Execute vulnerable SQL query
    users = session.execute(text(sql_query)).fetchall()
    
    # N+1 QUERY PROBLEM - Loading orders separately for each user
    export_data = []
    for user in users:
        user_data = {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'created_at': user[3]
        }
        
        # Separate query for each user's orders (N+1 problem)
        orders_sql = f'SELECT * FROM orders WHERE user_id = {user[0]}'
        orders = session.execute(text(orders_sql)).fetchall()
        
        user_data['orders'] = []
        for order in orders:
            order_data = {
                'id': order[0],
                'user_id': order[1],
                'amount': order[2],
                'status': order[3],
                'created_at': order[4],
                'description': order[5]
            }
            user_data['orders'].append(order_data)
        
        export_data.append(user_data)
    
    session.close()
    
    # Create CSV response
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['User ID', 'Name', 'Email', 'Created At', 'Order Count', 'Total Amount'])
    
    # Write data
    for user_data in export_data:
        order_count = len(user_data['orders'])
        total_amount = sum(order['amount'] for order in user_data['orders'])
        
        writer.writerow([
            user_data['id'],
            user_data['name'],
            user_data['email'],
            user_data['created_at'],
            order_count,
            total_amount
        ])
    
    # Return CSV response (NO ERROR HANDLING)
    output.seek(0)
    return output.getvalue()


@app.route('/export/orders', methods=['GET'])
def export_orders():
    """
    Export orders to CSV.
    
    This function also has security and performance issues.
    """
    
    # Another SQL injection vulnerability
    status = request.args.get('status', '')
    sql_query = f'SELECT * FROM orders WHERE status = "{status}"'
    
    session = Session()
    orders = session.execute(text(sql_query)).fetchall()
    session.close()
    
    # Create CSV response
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Order ID', 'User ID', 'Amount', 'Status', 'Created At', 'Description'])
    
    # Write data
    for order in orders:
        writer.writerow([
            order[0],  # id
            order[1],  # user_id
            order[2],  # amount
            order[3],  # status
            order[4],  # created_at
            order[5]   # description
        ])
    
    output.seek(0)
    return output.getvalue()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
