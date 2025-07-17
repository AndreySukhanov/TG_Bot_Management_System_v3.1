/**
 * Dashboard JavaScript
 * Управление интерфейсом дашборда для руководителей
 */

class Dashboard {
    constructor() {
        this.refreshInterval = 30000; // 30 секунд
        this.refreshTimer = null;
        this.charts = {};
        this.isLoading = false;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.startClock();
        this.loadDashboardData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Обработка ошибок
        window.addEventListener('error', (e) => {
            console.error('Dashboard error:', e);
            this.showError('Произошла ошибка в интерфейсе');
        });

        // Обработка изменения размера окна
        window.addEventListener('resize', () => {
            this.resizeCharts();
        });
    }

    startClock() {
        const updateClock = () => {
            const now = new Date();
            const timeString = now.toLocaleString('ru-RU', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            document.getElementById('current-time').textContent = timeString;
        };

        updateClock();
        setInterval(updateClock, 1000);
    }

    async loadDashboardData() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();

        try {
            // Параллельная загрузка данных
            const [statsResponse, paymentsResponse, balanceHistoryResponse] = await Promise.all([
                this.fetchWithAuth('/api/stats'),
                this.fetchWithAuth('/api/payments'),
                this.fetchWithAuth('/api/balance-history')
            ]);

            const stats = await statsResponse.json();
            const payments = await paymentsResponse.json();
            const balanceHistory = await balanceHistoryResponse.json();

            // Обновление интерфейса
            this.updateStats(stats);
            this.updateCharts(stats);
            this.updateRecentActivity(payments.payments);
            this.updateBalanceHistory(balanceHistory.history);

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Ошибка загрузки данных дашборда');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }

    async fetchWithAuth(url) {
        const token = this.getAuthToken();
        const response = await fetch(url, {
            headers: {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response;
    }

    getAuthToken() {
        // В реальном приложении токен должен храниться безопасно
        return localStorage.getItem('dashboard_token') || 'demo_token';
    }

    updateStats(data) {
        // Обновление баланса
        const balanceElement = document.getElementById('current-balance');
        const balanceStatusElement = document.getElementById('balance-status');
        
        if (balanceElement && data.balance) {
            balanceElement.textContent = `$${data.balance.current.toFixed(2)}`;
            
            if (balanceStatusElement) {
                balanceStatusElement.textContent = data.balance.status === 'healthy' ? 'Нормальный' : 'Низкий';
                balanceStatusElement.className = `stat-status ${data.balance.status}`;
            }
        }

        // Обновление ожидающих платежей
        const pendingCountElement = document.getElementById('pending-count');
        const pendingAmountElement = document.getElementById('pending-amount');
        
        if (pendingCountElement && data.payments) {
            pendingCountElement.textContent = data.payments.pending_count;
        }
        
        if (pendingAmountElement && data.payments) {
            pendingAmountElement.textContent = data.payments.pending_amount.toFixed(2);
        }

        // Обновление платежей за сегодня
        const todayPaymentsElement = document.getElementById('today-payments');
        if (todayPaymentsElement && data.payments) {
            todayPaymentsElement.textContent = data.payments.completed_today;
        }

        // Обновление информации о команде
        const teamSizeElement = document.getElementById('team-size');
        if (teamSizeElement && data.summary) {
            teamSizeElement.textContent = data.summary.total_users;
        }
    }

    updateCharts(data) {
        // График платежей за неделю
        if (data.daily && data.daily.length > 0) {
            this.createWeeklyChart(data.daily);
        }

        // График по проектам
        if (data.projects && data.projects.length > 0) {
            this.createProjectsChart(data.projects);
        }
    }

    createWeeklyChart(dailyData) {
        const ctx = document.getElementById('weekly-chart');
        if (!ctx) return;

        // Уничтожаем предыдущий график
        if (this.charts.weekly) {
            this.charts.weekly.destroy();
        }

        // Подготавливаем данные
        const labels = dailyData.map(item => {
            const date = new Date(item.date);
            return date.toLocaleDateString('ru-RU', { month: 'short', day: 'numeric' });
        });
        
        const amounts = dailyData.map(item => item.total);
        const counts = dailyData.map(item => item.count);

        this.charts.weekly = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Сумма ($)',
                    data: amounts,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y'
                }, {
                    label: 'Количество',
                    data: counts,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Сумма ($)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Количество'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                }
            }
        });
    }

    createProjectsChart(projectsData) {
        const ctx = document.getElementById('projects-chart');
        if (!ctx) return;

        // Уничтожаем предыдущий график
        if (this.charts.projects) {
            this.charts.projects.destroy();
        }

        // Берем топ-5 проектов
        const topProjects = projectsData.slice(0, 5);
        const labels = topProjects.map(item => item.name);
        const data = topProjects.map(item => item.total);

        const colors = [
            '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'
        ];

        this.charts.projects = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom'
                    }
                }
            }
        });
    }

    updateRecentActivity(payments) {
        const activityList = document.getElementById('recent-activity');
        if (!activityList) return;

        if (!payments || payments.length === 0) {
            activityList.innerHTML = '<div class="activity-item">Нет недавних операций</div>';
            return;
        }

        const html = payments.slice(0, 10).map(payment => {
            const date = new Date(payment.created_at);
            const timeStr = date.toLocaleString('ru-RU', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            const statusClass = payment.status === 'paid' ? 'positive' : 'negative';
            const statusText = payment.status === 'paid' ? 'Оплачено' : 'Ожидает';

            return `
                <div class="activity-item">
                    <div class="activity-info">
                        <div class="activity-description">
                            ${payment.service_name} - ${payment.project_name || 'Без проекта'}
                        </div>
                        <div class="activity-time">${timeStr} • ${statusText}</div>
                    </div>
                    <div class="activity-amount ${statusClass}">
                        $${payment.amount.toFixed(2)}
                    </div>
                </div>
            `;
        }).join('');

        activityList.innerHTML = html;
    }

    updateBalanceHistory(history) {
        const historyList = document.getElementById('balance-history');
        if (!historyList) return;

        if (!history || history.length === 0) {
            historyList.innerHTML = '<div class="activity-item">Нет истории баланса</div>';
            return;
        }

        const html = history.slice(0, 10).map(item => {
            const date = new Date(item.timestamp);
            const timeStr = date.toLocaleString('ru-RU', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            const amountClass = item.amount > 0 ? 'positive' : 'negative';
            const amountPrefix = item.amount > 0 ? '+' : '';

            return `
                <div class="activity-item">
                    <div class="activity-info">
                        <div class="activity-description">
                            ${item.description}
                        </div>
                        <div class="activity-time">${timeStr}</div>
                    </div>
                    <div class="activity-amount ${amountClass}">
                        ${amountPrefix}$${Math.abs(item.amount).toFixed(2)}
                    </div>
                </div>
            `;
        }).join('');

        historyList.innerHTML = html;
    }

    showLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('visible');
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('visible');
        }
    }

    showError(message) {
        const modal = document.getElementById('error-modal');
        const messageElement = document.getElementById('error-message');
        
        if (modal && messageElement) {
            messageElement.textContent = message;
            modal.classList.add('visible');
        }
    }

    resizeCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.resize();
            }
        });
    }

    startAutoRefresh() {
        this.refreshTimer = setInterval(() => {
            this.loadDashboardData();
        }, this.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
}

// Глобальные функции для модального окна
window.closeErrorModal = function() {
    const modal = document.getElementById('error-modal');
    if (modal) {
        modal.classList.remove('visible');
    }
};

window.retryLoad = function() {
    window.closeErrorModal();
    if (window.dashboard) {
        window.dashboard.loadDashboardData();
    }
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем наличие токена
    const token = localStorage.getItem('dashboard_token');
    if (!token) {
        // Устанавливаем демо-токен для тестирования
        localStorage.setItem('dashboard_token', 'demo_token');
    }

    // Инициализируем дашборд
    window.dashboard = new Dashboard();
});

// Обработка ухода со страницы
window.addEventListener('beforeunload', () => {
    if (window.dashboard) {
        window.dashboard.stopAutoRefresh();
    }
});