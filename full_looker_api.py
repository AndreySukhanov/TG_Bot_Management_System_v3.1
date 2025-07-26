from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os, sys
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, '/opt/telegram-bot')

app = FastAPI(title='Looker Studio API', version='1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://lookerstudio.google.com',
        'https://datastudio.google.com', 
        'https://accounts.google.com',
        'https://googleusercontent.com'
    ],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*'],
)

API_TOKEN = 'RfgLep4Y7nWjXky5qA0lpwV2E6kyZiOBkrKrHo7cl3k'

def verify_token(authorization: Optional[str] = Header(None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail='Authorization header missing')
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail='Invalid authentication scheme')
        if token != API_TOKEN:
            raise HTTPException(status_code=401, detail='Invalid token')
    except ValueError:
        raise HTTPException(status_code=401, detail='Invalid authorization header')
    
    return True

def get_db_connection():
    # Используем правильный путь к базе данных бота
    db_path = '/opt/telegram-bot/db/bot.db'
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail=f'Database not found at {db_path}')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.get('/')
async def root():
    return {'service': 'Looker Studio API', 'status': 'working', 'version': '1.0'}

@app.get('/payments')
async def get_payments(token_valid: bool = Depends(verify_token)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                id, service_name, amount, project_name, 
                payment_method, status, created_at, marketer_id
            FROM payments 
            ORDER BY created_at DESC
        ''')
        
        payments = []
        for row in cursor.fetchall():
            payments.append({
                'id': row['id'],
                'service_name': row['service_name'],
                'amount': float(row['amount']),
                'project_name': row['project_name'],
                'payment_method': row['payment_method'],
                'status': row['status'],
                'created_at': row['created_at'],
                'marketer_id': row['marketer_id']
            })
        
        return {'payments': payments}
    finally:
        conn.close()

@app.get('/balance-history')
async def get_balance_history(token_valid: bool = Depends(verify_token)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT amount, description, timestamp, user_id
            FROM balance_history 
            ORDER BY timestamp DESC
        ''')
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'amount': float(row['amount']),
                'description': row['description'],
                'timestamp': row['timestamp'],
                'user_id': row['user_id']
            })
        
        return {'balance_history': history}
    finally:
        conn.close()

@app.get('/projects')
async def get_projects(token_valid: bool = Depends(verify_token)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                project_name,
                COUNT(*) as payment_count,
                SUM(amount) as total_amount,
                AVG(amount) as avg_amount,
                MAX(created_at) as last_payment
            FROM payments 
            WHERE project_name IS NOT NULL
            GROUP BY project_name 
            ORDER BY total_amount DESC
        ''')
        
        projects = []
        for row in cursor.fetchall():
            projects.append({
                'project_name': row['project_name'],
                'payment_count': row['payment_count'],
                'total_amount': float(row['total_amount']),
                'avg_amount': float(row['avg_amount']),
                'last_payment': row['last_payment']
            })
        
        return {'projects': projects}
    finally:
        conn.close()

@app.get('/daily-stats')
async def get_daily_stats(token_valid: bool = Depends(verify_token)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as payment_count,
                SUM(amount) as total_amount,
                COUNT(DISTINCT project_name) as unique_projects
            FROM payments 
            WHERE created_at >= date('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        ''')
        
        daily_stats = []
        for row in cursor.fetchall():
            daily_stats.append({
                'date': row['date'],
                'payment_count': row['payment_count'],
                'total_amount': float(row['total_amount']),
                'unique_projects': row['unique_projects']
            })
        
        return {'daily_stats': daily_stats}
    finally:
        conn.close()

@app.get('/users')
async def get_users(token_valid: bool = Depends(verify_token)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                marketer_id,
                COUNT(*) as total_payments,
                SUM(amount) as total_spent,
                AVG(amount) as avg_payment,
                MAX(created_at) as last_activity
            FROM payments 
            GROUP BY marketer_id 
            ORDER BY total_spent DESC
        ''')
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'marketer_id': row['marketer_id'],
                'total_payments': row['total_payments'],
                'total_spent': float(row['total_spent']),
                'avg_payment': float(row['avg_payment']),
                'last_activity': row['last_activity']
            })
        
        return {'users': users}
    finally:
        conn.close()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8002)