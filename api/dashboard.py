from http.server import BaseHTTPRequestHandler
import json
import sqlite3
import os
import sys
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
import traceback

# Добавляем корневую директорию в path для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Импорты
try:
    from utils.config import Config
    from db.database import BalanceDB, PaymentDB
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    Config = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработка GET запросов для дашборда"""
        try:
            path = urlparse(self.path).path
            query_params = parse_qs(urlparse(self.path).query)
            
            # Проверка авторизации
            if not self._check_dashboard_auth(query_params):
                self._send_response(401, {"error": "Unauthorized. Add ?token=demo_token"})
                return
            
            # Главная страница дашборда
            if path == '/dashboard':
                self._send_dashboard_page()
                return
            
            # API для статистики
            if path == '/dashboard/api/stats':
                stats = self._get_dashboard_stats()
                self._send_response(200, stats)
                return
            
            # API для платежей
            if path == '/dashboard/api/payments':
                payments = self._get_payments_data()
                self._send_response(200, payments)
                return
            
            # API для истории баланса
            if path == '/dashboard/api/balance-history':
                history = self._get_balance_history()
                self._send_response(200, history)
                return
            
            # 404 для остальных путей
            self._send_response(404, {"error": "Not found", "path": path})
            
        except Exception as e:
            self._send_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    
    def _check_dashboard_auth(self, query_params):
        """Проверка авторизации для дашборда"""
        # Проверяем токен в параметрах запроса
        token = query_params.get('token', [None])[0]
        return token == 'demo_token'
    
    def _send_dashboard_page(self):
        """Отправка HTML страницы дашборда"""
        html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manager Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        .stat-card { 
            background: white; 
            padding: 25px; 
            border-radius: 12px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-title { font-size: 14px; color: #666; margin-bottom: 10px; text-transform: uppercase; }
        .stat-value { font-size: 32px; font-weight: bold; color: #333; }
        .stat-trend { font-size: 12px; margin-top: 8px; }
        .positive { color: #10b981; }
        .negative { color: #ef4444; }
        .neutral { color: #6b7280; }
        .section { 
            background: white; 
            border-radius: 12px; 
            padding: 25px; 
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .section h2 { color: #333; margin-bottom: 20px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }
        .table { width: 100%; border-collapse: collapse; }
        .table th, .table td { text-align: left; padding: 12px; border-bottom: 1px solid #f0f0f0; }
        .table th { background: #f8f9fa; font-weight: 600; }
        .status-badge { 
            padding: 4px 8px; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: 500;
        }
        .status-pending { background: #fef3c7; color: #d97706; }
        .status-paid { background: #d1fae5; color: #059669; }
        .loading { text-align: center; padding: 40px; color: #666; }
        .error { background: #fee2e2; color: #dc2626; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .refresh-btn {
            background: #4f46e5;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-bottom: 20px;
            transition: background 0.3s;
        }
        .refresh-btn:hover { background: #4338ca; }
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: 1fr 1fr; }
            .table { font-size: 14px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Manager Dashboard</h1>
            <p>Управление финансами и аналитика</p>
        </div>
        
        <button class="refresh-btn" onclick="loadDashboard()">🔄 Обновить данные</button>
        
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="stat-title">💰 Текущий баланс</div>
                <div class="stat-value" id="currentBalance">Загрузка...</div>
                <div class="stat-trend neutral" id="balanceStatus">Проверка статуса...</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">⏳ Ожидающие заявки</div>
                <div class="stat-value" id="pendingCount">-</div>
                <div class="stat-trend neutral" id="pendingAmount">$0.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">✅ Оплачено сегодня</div>
                <div class="stat-value" id="completedToday">-</div>
                <div class="stat-trend positive">платежей завершено</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">👥 Команда</div>
                <div class="stat-value" id="totalUsers">-</div>
                <div class="stat-trend neutral" id="teamBreakdown">Загрузка...</div>
            </div>
        </div>

        <div class="section">
            <h2>📊 Последние платежи</h2>
            <div id="paymentsSection">
                <div class="loading">Загрузка данных о платежах...</div>
            </div>
        </div>

        <div class="section">
            <h2>📈 История баланса</h2>
            <div id="balanceHistorySection">
                <div class="loading">Загрузка истории баланса...</div>
            </div>
        </div>
    </div>

    <script>
        async function loadDashboard() {
            try {
                // Получаем токен из URL
                const urlParams = new URLSearchParams(window.location.search);
                const token = urlParams.get('token') || 'demo_token';
                
                // Загружаем статистику
                const statsResponse = await fetch(`/dashboard/api/stats?token=${token}`);
                if (!statsResponse.ok) throw new Error('Ошибка загрузки статистики');
                const stats = await statsResponse.json();
                
                // Обновляем статистические карточки
                document.getElementById('currentBalance').textContent = `$${stats.balance.current}`;
                document.getElementById('balanceStatus').textContent = stats.balance.status === 'healthy' ? '✅ Норма' : '⚠️ Низкий';
                document.getElementById('balanceStatus').className = `stat-trend ${stats.balance.status === 'healthy' ? 'positive' : 'negative'}`;
                
                document.getElementById('pendingCount').textContent = stats.payments.pending_count;
                document.getElementById('pendingAmount').textContent = `$${stats.payments.pending_amount} на рассмотрении`;
                
                document.getElementById('completedToday').textContent = stats.payments.completed_today;
                
                document.getElementById('totalUsers').textContent = stats.summary.total_users;
                document.getElementById('teamBreakdown').textContent = 
                    `${stats.summary.marketers}M • ${stats.summary.financiers}F • ${stats.summary.managers}R`;
                
                // Загружаем платежи
                const paymentsResponse = await fetch(`/dashboard/api/payments?token=${token}`);
                if (paymentsResponse.ok) {
                    const paymentsData = await paymentsResponse.json();
                    displayPayments(paymentsData.payments);
                }
                
                // Загружаем историю баланса
                const historyResponse = await fetch(`/dashboard/api/balance-history?token=${token}`);
                if (historyResponse.ok) {
                    const historyData = await historyResponse.json();
                    displayBalanceHistory(historyData.history);
                }
                
            } catch (error) {
                console.error('Ошибка загрузки дашборда:', error);
                document.getElementById('statsGrid').innerHTML = 
                    `<div class="error">❌ Ошибка загрузки данных: ${error.message}</div>`;
            }
        }
        
        function displayPayments(payments) {
            const section = document.getElementById('paymentsSection');
            if (!payments || payments.length === 0) {
                section.innerHTML = '<p>Платежи не найдены</p>';
                return;
            }
            
            let html = '<table class="table"><thead><tr><th>ID</th><th>Сервис</th><th>Сумма</th><th>Проект</th><th>Статус</th><th>Дата</th></tr></thead><tbody>';
            
            payments.slice(0, 10).forEach(payment => {
                const statusClass = payment.status === 'paid' ? 'status-paid' : 'status-pending';
                const statusText = payment.status === 'paid' ? 'Оплачено' : 'Ожидание';
                html += `<tr>
                    <td>#${payment.id}</td>
                    <td>${payment.service_name}</td>
                    <td>$${payment.amount}</td>
                    <td>${payment.project_name || '-'}</td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td>${new Date(payment.created_at).toLocaleDateString('ru')}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            section.innerHTML = html;
        }
        
        function displayBalanceHistory(history) {
            const section = document.getElementById('balanceHistorySection');
            if (!history || history.length === 0) {
                section.innerHTML = '<p>История баланса не найдена</p>';
                return;
            }
            
            let html = '<table class="table"><thead><tr><th>Сумма</th><th>Описание</th><th>Дата</th></tr></thead><tbody>';
            
            history.slice(0, 10).forEach(entry => {
                const amountClass = entry.amount > 0 ? 'positive' : 'negative';
                html += `<tr>
                    <td class="${amountClass}">${entry.amount > 0 ? '+' : ''}$${entry.amount}</td>
                    <td>${entry.description}</td>
                    <td>${new Date(entry.timestamp).toLocaleDateString('ru')}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            section.innerHTML = html;
        }
        
        // Загружаем дашборд при загрузке страницы
        window.onload = loadDashboard;
        
        // Автообновление каждые 30 секунд
        setInterval(loadDashboard, 30000);
    </script>
</body>
</html>
        """
        
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except Exception as e:
            self._send_response(500, {"error": f"Error sending HTML: {str(e)}"})
    
    def _get_dashboard_stats(self):
        """Получение статистики для дашборда"""
        try:
            if not Config:
                return {"error": "Config not available"}
            
            config = Config()
            
            # Получаем текущий баланс
            current_balance = self._get_current_balance()
            
            # Получаем ожидающие платежи
            pending_payments = self._get_pending_payments()
            total_pending = sum(payment["amount"] for payment in pending_payments)
            pending_count = len(pending_payments)
            
            # Получаем платежи за сегодня
            completed_today = self._get_payments_today()
            
            return {
                "balance": {
                    "current": round(current_balance, 2),
                    "threshold": config.LOW_BALANCE_THRESHOLD,
                    "status": "healthy" if current_balance >= config.LOW_BALANCE_THRESHOLD else "low"
                },
                "payments": {
                    "pending_count": pending_count,
                    "pending_amount": round(total_pending, 2),
                    "completed_today": completed_today
                },
                "summary": {
                    "total_users": len(config.MARKETERS) + len(config.FINANCIERS) + len(config.MANAGERS),
                    "marketers": len(config.MARKETERS),
                    "financiers": len(config.FINANCIERS),
                    "managers": len(config.MANAGERS)
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_current_balance(self):
        """Получение текущего баланса"""
        try:
            config = Config()
            db_path = config.DATABASE_PATH
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM balance ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0.0
        except:
            return 0.0
    
    def _get_pending_payments(self):
        """Получение ожидающих платежей"""
        try:
            config = Config()
            db_path = config.DATABASE_PATH
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC")
            payments = []
            for row in cursor.fetchall():
                payments.append(dict(row))
            conn.close()
            return payments
        except:
            return []
    
    def _get_payments_today(self):
        """Получение количества платежей за сегодня"""
        try:
            config = Config()
            db_path = config.DATABASE_PATH
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM payments 
                WHERE DATE(created_at) = DATE('now') AND status = 'paid'
            """)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0
        except:
            return 0
    
    def _get_payments_data(self):
        """Получение данных о платежах"""
        try:
            config = Config()
            db_path = config.DATABASE_PATH
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id, service_name, amount, project_name, 
                    payment_method, status, created_at, marketer_id
                FROM payments 
                ORDER BY created_at DESC 
                LIMIT 50
            """)
            
            payments = []
            for row in cursor.fetchall():
                payments.append(dict(row))
            
            conn.close()
            return {"payments": payments}
        except Exception as e:
            return {"error": str(e), "payments": []}
    
    def _get_balance_history(self):
        """Получение истории баланса"""
        try:
            config = Config()
            db_path = config.DATABASE_PATH
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT amount, description, timestamp, user_id
                FROM balance_history 
                ORDER BY timestamp DESC 
                LIMIT 30
            """)
            
            history = []
            for row in cursor.fetchall():
                history.append(dict(row))
            
            conn.close()
            return {"history": history}
        except Exception as e:
            return {"error": str(e), "history": []}
    
    def _send_response(self, status_code, data):
        """Отправка JSON ответа"""
        try:
            response_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            
        except Exception as e:
            print(f"Ошибка отправки ответа: {e}")