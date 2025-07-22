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
    def do_POST(self):
        """Обработка POST запросов (вход в систему)"""
        try:
            path = urlparse(self.path).path
            
            # Обработка входа в систему
            if path == '/dashboard/login':
                self._handle_login()
                return
                
            # Для всех остальных POST запросов требуется авторизация
            query_params = parse_qs(urlparse(self.path).query)
            if not self._check_dashboard_auth(query_params):
                self._send_response(401, {"error": "Unauthorized"})
                return
                
            self._send_response(404, {"error": "Not found"})
            
        except Exception as e:
            self._send_response(500, {"error": str(e)})
    
    def do_GET(self):
        """Обработка GET запросов для дашборда"""
        try:
            path = urlparse(self.path).path
            query_params = parse_qs(urlparse(self.path).query)
            
            # Страница входа
            if path == '/dashboard/login':
                self._send_login_page()
                return
            
            # Проверка авторизации для всех остальных страниц дашборда
            if not self._check_dashboard_auth(query_params):
                self._send_login_redirect()
                return
            
            # Главная страница дашборда
            if path == '/dashboard':
                self._send_dashboard_page()
                return
            
            # Выход из системы
            if path == '/dashboard/logout':
                self._send_logout()
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
        # Проверяем сессионный токен в куки
        cookies = self.headers.get('Cookie', '')
        if 'dashboard_session=' in cookies:
            session_token = None
            for cookie in cookies.split('; '):
                if cookie.startswith('dashboard_session='):
                    session_token = cookie.split('=')[1]
                    break
            
            # Простая проверка сессии (в реальном проекте использовать JWT или Redis)
            if session_token == 'authenticated_user_session':
                return True
        
        return False
    
    def _handle_login(self):
        """Обработка входа в систему"""
        try:
            # Получаем данные POST запроса
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            # Парсим форму
            login_data = parse_qs(post_data)
            username = login_data.get('username', [None])[0]
            password = login_data.get('password', [None])[0]
            
            # Проверяем учетные данные
            if self._validate_credentials(username, password):
                # Успешный вход - устанавливаем куки и редирект
                self.send_response(302)
                self.send_header('Location', '/dashboard')
                self.send_header('Set-Cookie', 'dashboard_session=authenticated_user_session; HttpOnly; Path=/dashboard; Max-Age=86400')
                self.end_headers()
                return
            else:
                # Неуспешный вход - возвращаем страницу входа с ошибкой
                self._send_login_page(error="Неверный логин или пароль")
                return
                
        except Exception as e:
            self._send_response(500, {"error": f"Login error: {str(e)}"})
    
    def _validate_credentials(self, username, password):
        """Проверка учетных данных"""
        # Получаем учетные данные из переменных окружения или используем дефолтные
        valid_username = os.getenv('DASHBOARD_USERNAME', 'admin')
        valid_password = os.getenv('DASHBOARD_PASSWORD', 'manager123')
        
        return username == valid_username and password == valid_password
    
    def _send_login_page(self, error=None):
        """Отправка страницы входа"""
        error_html = f'<div class="error-message">{error}</div>' if error else ''
        
        html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в Manager Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .login-container {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.15);
            width: 100%;
            max-width: 400px;
        }}
        .login-header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .login-header h1 {{
            color: #333;
            font-size: 2em;
            margin-bottom: 10px;
        }}
        .login-header p {{
            color: #666;
            font-size: 14px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }}
        .form-group input {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }}
        .form-group input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        .login-btn {{
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .login-btn:hover {{
            transform: translateY(-1px);
        }}
        .login-btn:active {{
            transform: translateY(0);
        }}
        .error-message {{
            background: #fee2e2;
            color: #dc2626;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 14px;
        }}
        .credentials-info {{
            background: #f0f9ff;
            color: #0369a1;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 13px;
            text-align: center;
        }}
        .credentials-info strong {{
            display: block;
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🔐 Авторизация</h1>
            <p>Вход в Manager Dashboard</p>
        </div>
        
        {error_html}
        
        <form method="POST" action="/dashboard/login">
            <div class="form-group">
                <label for="username">Логин</label>
                <input type="text" id="username" name="username" required>
            </div>
            
            <div class="form-group">
                <label for="password">Пароль</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" class="login-btn">
                Войти в систему
            </button>
        </form>
        
        <div class="credentials-info">
            <strong>Тестовые данные для входа:</strong>
            Логин: <strong>admin</strong><br>
            Пароль: <strong>manager123</strong><br>
            <small>(можно изменить через переменные DASHBOARD_USERNAME и DASHBOARD_PASSWORD)</small>
        </div>
    </div>
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
            self._send_response(500, {"error": f"Error sending login page: {str(e)}"})
    
    def _send_login_redirect(self):
        """Редирект на страницу входа"""
        try:
            self.send_response(302)
            self.send_header('Location', '/dashboard/login')
            self.end_headers()
        except Exception as e:
            self._send_response(401, {"error": "Unauthorized", "redirect": "/dashboard/login"})
    
    def _send_logout(self):
        """Выход из системы"""
        try:
            self.send_response(302)
            self.send_header('Location', '/dashboard/login')
            self.send_header('Set-Cookie', 'dashboard_session=; HttpOnly; Path=/dashboard; Max-Age=0')
            self.end_headers()
        except Exception as e:
            self._send_response(500, {"error": f"Logout error: {str(e)}"})
    
    def _send_dashboard_page(self):
        """Отправка HTML страницы дашборда с оригинальным дизайном"""
        html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Дашборд руководителя</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        /* Modern Minimalistic Dashboard Styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            /* Color Palette */
            --primary-color: #2563eb;
            --primary-light: #3b82f6;
            --primary-dark: #1d4ed8;
            --secondary-color: #64748b;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --info-color: #06b6d4;
            
            /* Background Colors */
            --bg-primary: #ffffff;
            --bg-secondary: #f8fafc;
            --bg-tertiary: #f1f5f9;
            --bg-card: #ffffff;
            
            /* Text Colors */
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --text-muted: #94a3b8;
            
            /* Border Colors */
            --border-light: #e2e8f0;
            --border-medium: #cbd5e1;
            
            /* Shadows */
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            
            /* Spacing */
            --spacing-xs: 0.25rem;
            --spacing-sm: 0.5rem;
            --spacing-md: 1rem;
            --spacing-lg: 1.5rem;
            --spacing-xl: 2rem;
            --spacing-2xl: 3rem;
            
            /* Border Radius */
            --radius-sm: 0.375rem;
            --radius-md: 0.5rem;
            --radius-lg: 0.75rem;
            --radius-xl: 1rem;
            
            /* Font Sizes */
            --text-xs: 0.75rem;
            --text-sm: 0.875rem;
            --text-base: 1rem;
            --text-lg: 1.125rem;
            --text-xl: 1.25rem;
            --text-2xl: 1.5rem;
            --text-3xl: 1.875rem;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.6;
            font-size: var(--text-base);
        }

        /* Dashboard Container */
        .dashboard-container {
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Header */
        .dashboard-header {
            background: var(--bg-primary);
            border-bottom: 1px solid var(--border-light);
            padding: var(--spacing-lg) var(--spacing-xl);
            box-shadow: var(--shadow-sm);
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1400px;
            margin: 0 auto;
        }

        .dashboard-title {
            font-size: var(--text-2xl);
            font-weight: 600;
            color: var(--text-primary);
        }

        .header-info {
            display: flex;
            align-items: center;
            gap: var(--spacing-lg);
        }

        .current-time {
            font-size: var(--text-sm);
            color: var(--text-secondary);
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: var(--spacing-sm);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--success-color);
        }

        .status-text {
            font-size: var(--text-sm);
            color: var(--text-secondary);
        }

        .logout-btn {
            background: var(--danger-color);
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: var(--radius-md);
            font-size: var(--text-sm);
            font-weight: 500;
            transition: background-color 0.2s;
        }

        .logout-btn:hover {
            background: #dc2626;
        }

        /* Main Content */
        .dashboard-main {
            flex: 1;
            padding: var(--spacing-xl);
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: var(--spacing-lg);
            margin-bottom: var(--spacing-2xl);
        }

        .stat-card {
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: var(--spacing-lg);
            box-shadow: var(--shadow-md);
            display: flex;
            align-items: center;
            gap: var(--spacing-md);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }

        .stat-icon {
            font-size: 2rem;
            width: 64px;
            height: 64px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius-lg);
            background: var(--bg-tertiary);
        }

        .balance-card .stat-icon {
            background: linear-gradient(135deg, #10b981, #059669);
        }

        .payments-card .stat-icon {
            background: linear-gradient(135deg, #f59e0b, #d97706);
        }

        .today-card .stat-icon {
            background: linear-gradient(135deg, #3b82f6, #2563eb);
        }

        .team-card .stat-icon {
            background: linear-gradient(135deg, #8b5cf6, #7c3aed);
        }

        .stat-content {
            flex: 1;
        }

        .stat-title {
            font-size: var(--text-sm);
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: var(--spacing-xs);
        }

        .stat-value {
            font-size: var(--text-2xl);
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: var(--spacing-xs);
        }

        .stat-meta, .stat-status {
            font-size: var(--text-xs);
            color: var(--text-muted);
        }

        /* Charts Section */
        .charts-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: var(--spacing-lg);
            margin-bottom: var(--spacing-2xl);
        }

        .chart-container {
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: var(--spacing-lg);
            box-shadow: var(--shadow-md);
        }

        .chart-title {
            font-size: var(--text-lg);
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: var(--spacing-md);
        }

        .chart-card canvas {
            max-height: 300px;
        }

        /* Activity Section */
        .activity-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: var(--spacing-lg);
        }

        .activity-card {
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: var(--spacing-lg);
            box-shadow: var(--shadow-md);
        }

        .activity-title {
            font-size: var(--text-lg);
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: var(--spacing-md);
        }

        .activity-list {
            max-height: 400px;
            overflow-y: auto;
        }

        .activity-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: var(--spacing-md);
            border-bottom: 1px solid var(--border-light);
            transition: background-color 0.2s;
        }

        .activity-item:hover {
            background-color: var(--bg-tertiary);
        }

        .activity-item:last-child {
            border-bottom: none;
        }

        .activity-description {
            flex: 1;
            margin-right: var(--spacing-md);
        }

        .activity-description h4 {
            font-size: var(--text-sm);
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: var(--spacing-xs);
        }

        .activity-description p {
            font-size: var(--text-xs);
            color: var(--text-secondary);
        }

        .activity-amount {
            font-size: var(--text-sm);
            font-weight: 600;
        }

        .activity-amount.positive {
            color: var(--success-color);
        }

        .activity-amount.negative {
            color: var(--danger-color);
        }

        .activity-time {
            font-size: var(--text-xs);
            color: var(--text-muted);
            margin-left: var(--spacing-md);
        }

        /* Table Styles */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: var(--spacing-md);
        }

        .data-table th,
        .data-table td {
            text-align: left;
            padding: var(--spacing-md);
            border-bottom: 1px solid var(--border-light);
        }

        .data-table th {
            background-color: var(--bg-tertiary);
            font-weight: 600;
            font-size: var(--text-sm);
            color: var(--text-secondary);
        }

        .data-table td {
            font-size: var(--text-sm);
            color: var(--text-primary);
        }

        .status-badge {
            padding: var(--spacing-xs) var(--spacing-sm);
            border-radius: var(--radius-sm);
            font-size: var(--text-xs);
            font-weight: 500;
        }

        .status-pending {
            background-color: #fef3c7;
            color: #d97706;
        }

        .status-paid {
            background-color: #d1fae5;
            color: #059669;
        }

        /* Loading States */
        .loading {
            text-align: center;
            padding: var(--spacing-2xl);
            color: var(--text-muted);
        }

        .loading-placeholder {
            height: 20px;
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: loading 1.5s infinite;
            border-radius: var(--radius-sm);
        }

        @keyframes loading {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        /* Responsive Design */
        @media (max-width: 1024px) {
            .dashboard-main {
                padding: var(--spacing-lg);
            }
            
            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            }
            
            .charts-section {
                grid-template-columns: 1fr;
            }
            
            .activity-section {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                gap: var(--spacing-md);
                text-align: center;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .stat-card {
                flex-direction: column;
                text-align: center;
            }
            
            .data-table {
                font-size: var(--text-xs);
            }
        }

        /* Error Styles */
        .error {
            background: #fee2e2;
            color: #dc2626;
            padding: var(--spacing-lg);
            border-radius: var(--radius-lg);
            margin: var(--spacing-lg) 0;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Header -->
        <header class="dashboard-header">
            <div class="header-content">
                <h1 class="dashboard-title">Панель управления</h1>
                <div class="header-info">
                    <span class="current-time" id="current-time"></span>
                    <div class="status-indicator">
                        <span class="status-dot" id="status-dot"></span>
                        <span class="status-text" id="status-text">Онлайн</span>
                    </div>
                    <a href="/dashboard/logout" class="logout-btn">🚪 Выйти</a>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="dashboard-main">
            <!-- Stats Cards -->
            <section class="stats-grid">
                <div class="stat-card balance-card">
                    <div class="stat-icon">💰</div>
                    <div class="stat-content">
                        <h3 class="stat-title">Текущий баланс</h3>
                        <div class="stat-value" id="current-balance">$0.00</div>
                        <div class="stat-status" id="balance-status">Загрузка...</div>
                    </div>
                </div>

                <div class="stat-card payments-card">
                    <div class="stat-icon">📝</div>
                    <div class="stat-content">
                        <h3 class="stat-title">Ожидающие оплаты</h3>
                        <div class="stat-value" id="pending-count">0</div>
                        <div class="stat-meta">на сумму $<span id="pending-amount">0.00</span></div>
                    </div>
                </div>

                <div class="stat-card today-card">
                    <div class="stat-icon">📊</div>
                    <div class="stat-content">
                        <h3 class="stat-title">Платежи сегодня</h3>
                        <div class="stat-value" id="today-payments">0</div>
                        <div class="stat-meta">завершено</div>
                    </div>
                </div>

                <div class="stat-card team-card">
                    <div class="stat-icon">👥</div>
                    <div class="stat-content">
                        <h3 class="stat-title">Команда</h3>
                        <div class="stat-value" id="team-size">0</div>
                        <div class="stat-meta">активных пользователей</div>
                    </div>
                </div>
            </section>

            <!-- Charts Section -->
            <section class="charts-section">
                <div class="chart-container">
                    <div class="chart-card">
                        <h3 class="chart-title">Платежи за неделю</h3>
                        <canvas id="weekly-chart"></canvas>
                    </div>
                </div>

                <div class="chart-container">
                    <div class="chart-card">
                        <h3 class="chart-title">Топ проекты</h3>
                        <canvas id="projects-chart"></canvas>
                    </div>
                </div>
            </section>

            <!-- Recent Activity -->
            <section class="activity-section">
                <div class="activity-card">
                    <h3 class="activity-title">Последние операции</h3>
                    <div class="activity-list" id="recent-activity">
                        <div class="loading">Загрузка данных о платежах...</div>
                    </div>
                </div>

                <div class="activity-card">
                    <h3 class="activity-title">История баланса</h3>
                    <div class="activity-list" id="balance-history">
                        <div class="loading">Загрузка истории баланса...</div>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <script>
        // Текущее время
        function updateTime() {
            const now = new Date();
            document.getElementById('current-time').textContent = now.toLocaleTimeString('ru');
        }
        
        // Загрузка данных дашборда
        async function loadDashboard() {
            try {
                // Обновляем время
                updateTime();
                
                // Загружаем статистику
                const statsResponse = await fetch('/dashboard/api/stats');
                if (!statsResponse.ok) {
                    throw new Error(`HTTP ${statsResponse.status}: ${statsResponse.statusText}`);
                }
                
                const stats = await statsResponse.json();
                
                // Проверяем наличие ошибок
                if (stats.error) {
                    throw new Error(`API Error: ${stats.error}`);
                }
                
                // Обновляем статистические карточки
                document.getElementById('current-balance').textContent = `$${stats.balance?.current || 0}`;
                document.getElementById('balance-status').textContent = stats.balance?.status === 'healthy' ? 'Здоровый баланс' : 'Низкий баланс';
                
                document.getElementById('pending-count').textContent = stats.payments?.pending_count || 0;
                document.getElementById('pending-amount').textContent = stats.payments?.pending_amount || 0;
                
                document.getElementById('today-payments').textContent = stats.payments?.completed_today || 0;
                
                document.getElementById('team-size').textContent = stats.summary?.total_users || 0;
                
                // Загружаем платежи для списка операций
                const paymentsResponse = await fetch('/dashboard/api/payments');
                if (paymentsResponse.ok) {
                    const paymentsData = await paymentsResponse.json();
                    displayRecentActivity(paymentsData.payments || []);
                }
                
                // Загружаем историю баланса
                const historyResponse = await fetch('/dashboard/api/balance-history');
                if (historyResponse.ok) {
                    const historyData = await historyResponse.json();
                    displayBalanceHistory(historyData.history || []);
                }
                
                // Создаем графики
                await createCharts(stats);
                
            } catch (error) {
                console.error('Ошибка загрузки дашборда:', error);
                showError('Ошибка загрузки данных: ' + error.message);
            }
        }
        
        // Отображение последних операций
        function displayRecentActivity(payments) {
            const container = document.getElementById('recent-activity');
            if (!payments || payments.length === 0) {
                container.innerHTML = '<div class="loading">Нет данных о платежах</div>';
                return;
            }
            
            let html = '';
            payments.slice(0, 8).forEach(payment => {
                const amount = payment.amount || 0;
                const amountClass = payment.status === 'paid' ? 'negative' : '';
                html += `
                    <div class="activity-item">
                        <div class="activity-description">
                            <h4>${payment.service_name || 'Неизвестный сервис'}</h4>
                            <p>${payment.project_name || 'Без проекта'} • ${payment.status === 'paid' ? 'Оплачено' : 'Ожидание'}</p>
                        </div>
                        <div class="activity-amount ${amountClass}">$${amount}</div>
                        <div class="activity-time">${new Date(payment.created_at).toLocaleDateString('ru')}</div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        }
        
        // Отображение истории баланса
        function displayBalanceHistory(history) {
            const container = document.getElementById('balance-history');
            if (!history || history.length === 0) {
                container.innerHTML = '<div class="loading">Нет данных об истории баланса</div>';
                return;
            }
            
            let html = '';
            history.slice(0, 8).forEach(entry => {
                const amount = entry.amount || 0;
                const amountClass = amount > 0 ? 'positive' : 'negative';
                html += `
                    <div class="activity-item">
                        <div class="activity-description">
                            <h4>${amount > 0 ? 'Пополнение баланса' : 'Списание с баланса'}</h4>
                            <p>${entry.description || 'Операция с балансом'}</p>
                        </div>
                        <div class="activity-amount ${amountClass}">${amount > 0 ? '+' : ''}$${Math.abs(amount)}</div>
                        <div class="activity-time">${new Date(entry.timestamp).toLocaleDateString('ru')}</div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        }
        
        // Создание графиков
        async function createCharts(stats) {
            try {
                // График платежей за неделю
                const weeklyCtx = document.getElementById('weekly-chart').getContext('2d');
                new Chart(weeklyCtx, {
                    type: 'line',
                    data: {
                        labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
                        datasets: [{
                            label: 'Платежи',
                            data: [12, 19, 3, 5, 2, 3, 15], // Тестовые данные
                            borderColor: 'rgb(59, 130, 246)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });
                
                // График топ проектов
                const projectsCtx = document.getElementById('projects-chart').getContext('2d');
                new Chart(projectsCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Проект А', 'Проект Б', 'Проект В', 'Другие'],
                        datasets: [{
                            data: [300, 200, 100, 150], // Тестовые данные
                            backgroundColor: [
                                'rgb(59, 130, 246)',
                                'rgb(16, 185, 129)',
                                'rgb(245, 158, 11)',
                                'rgb(139, 92, 246)'
                            ]
                        }]
                    },
                    options: {
                        responsive: true
                    }
                });
            } catch (error) {
                console.error('Ошибка создания графиков:', error);
            }
        }
        
        // Отображение ошибок
        function showError(message) {
            const main = document.querySelector('.dashboard-main');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = message;
            main.insertBefore(errorDiv, main.firstChild);
        }
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', function() {
            loadDashboard();
            
            // Обновляем время каждую секунду
            setInterval(updateTime, 1000);
            
            // Автообновление данных каждые 30 секунд
            setInterval(loadDashboard, 30000);
        });
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
            # Получаем текущий баланс
            current_balance = self._get_current_balance()
            
            # Получаем ожидающие платежи
            pending_payments = self._get_pending_payments()
            total_pending = sum(payment.get("amount", 0) for payment in pending_payments)
            pending_count = len(pending_payments)
            
            # Получаем платежи за сегодня
            completed_today = self._get_payments_today()
            
            # Получаем количество пользователей из переменных окружения
            marketers_count = len(os.getenv('MARKETERS', '').split(',')) if os.getenv('MARKETERS') else 0
            financiers_count = len(os.getenv('FINANCIERS', '').split(',')) if os.getenv('FINANCIERS') else 0
            managers_count = len(os.getenv('MANAGERS', '').split(',')) if os.getenv('MANAGERS') else 0
            
            return {
                "balance": {
                    "current": round(float(current_balance), 2),
                    "threshold": 100.0,
                    "status": "healthy" if float(current_balance) >= 100.0 else "low"
                },
                "payments": {
                    "pending_count": int(pending_count),
                    "pending_amount": round(float(total_pending), 2),
                    "completed_today": int(completed_today)
                },
                "summary": {
                    "total_users": marketers_count + financiers_count + managers_count,
                    "marketers": marketers_count,
                    "financiers": financiers_count,
                    "managers": managers_count
                }
            }
        except Exception as e:
            return {
                "error": str(e),
                "balance": {
                    "current": 0.0,
                    "threshold": 100.0,
                    "status": "unknown"
                },
                "payments": {
                    "pending_count": 0,
                    "pending_amount": 0.0,
                    "completed_today": 0
                },
                "summary": {
                    "total_users": 0,
                    "marketers": 0,
                    "financiers": 0,
                    "managers": 0
                }
            }
    
    def _get_current_balance(self):
        """Получение текущего баланса"""
        try:
            # Используем путь к базе данных из переменных окружения или дефолтный
            db_path = os.getenv('DATABASE_PATH', '/tmp/bot.db')
            
            # Проверяем существование файла базы данных
            if not os.path.exists(db_path):
                # Создаем базу данных если её нет
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS balance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        balance REAL DEFAULT 0.0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute("INSERT INTO balance (balance) VALUES (0.0)")
                conn.commit()
                conn.close()
                return 0.0
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM balance ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return float(result[0]) if result else 0.0
        except Exception as e:
            print(f"Ошибка получения баланса: {e}")
            return 0.0
    
    def _get_pending_payments(self):
        """Получение ожидающих платежей"""
        try:
            db_path = os.getenv('DATABASE_PATH', '/tmp/bot.db')
            
            if not os.path.exists(db_path):
                # Создаем таблицу платежей если её нет
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_name TEXT NOT NULL,
                        amount REAL NOT NULL,
                        project_name TEXT,
                        payment_method TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        marketer_id INTEGER
                    )
                ''')
                conn.commit()
                conn.close()
                return []
            
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC")
            payments = []
            for row in cursor.fetchall():
                payments.append(dict(row))
            conn.close()
            return payments
        except Exception as e:
            print(f"Ошибка получения платежей: {e}")
            return []
    
    def _get_payments_today(self):
        """Получение количества платежей за сегодня"""
        try:
            db_path = os.getenv('DATABASE_PATH', '/tmp/bot.db')
            
            if not os.path.exists(db_path):
                return 0
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM payments 
                WHERE DATE(created_at) = DATE('now') AND status = 'paid'
            """)
            result = cursor.fetchone()
            conn.close()
            return int(result[0]) if result else 0
        except Exception as e:
            print(f"Ошибка получения платежей за сегодня: {e}")
            return 0
    
    def _get_payments_data(self):
        """Получение данных о платежах"""
        try:
            db_path = os.getenv('DATABASE_PATH', '/tmp/bot.db')
            
            if not os.path.exists(db_path):
                return {"payments": []}
            
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
            print(f"Ошибка получения данных о платежах: {e}")
            return {"error": str(e), "payments": []}
    
    def _get_balance_history(self):
        """Получение истории баланса"""
        try:
            db_path = os.getenv('DATABASE_PATH', '/tmp/bot.db')
            
            if not os.path.exists(db_path):
                return {"history": []}
            
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Сначала проверим, существует ли таблица
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='balance_history'
            """)
            
            if not cursor.fetchone():
                # Создаем таблицу истории баланса
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS balance_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        amount REAL NOT NULL,
                        description TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        user_id INTEGER
                    )
                ''')
                conn.commit()
                conn.close()
                return {"history": []}
            
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
            print(f"Ошибка получения истории баланса: {e}")
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