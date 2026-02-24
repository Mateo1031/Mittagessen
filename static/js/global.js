/**
 * GlobalCore: Menü, Timer, Toasts und Basis-Modal-Logik.
 */
const GlobalCore = {
    init: function() {
        this.initTimer();
        this.initAlertAutohide();
        this.initGlobalModals();
    },

    toggleMenu: function() {
        const nav = document.getElementById('nav-links-container');
        if (nav) nav.classList.toggle('active');
    },

    showToast: function(message, type = 'info') {
        let container = document.querySelector('.toast-container') || document.querySelector('.message-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container message-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `alert-toast toast-message toast-${type} alert-${type === 'error' ? 'error' : 'info'}`;
        
        const icons = { 'error': '⛔', 'success': '✅', 'info': 'ℹ️', 'warning': '⚠️' };
        toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span> <span>${message}</span><button class="close-btn" onclick="this.parentElement.remove()">×</button>`;
        
        container.appendChild(toast);
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 500);
        }, 4000);
    },

    initAlertAutohide: function() {
        const alerts = document.querySelectorAll('.alert-toast, .django-message');
        alerts.forEach(alert => {
            setTimeout(() => {
                alert.style.transition = "opacity 0.5s";
                alert.style.opacity = "0";
                setTimeout(() => alert.remove(), 500);
            }, 4000);
        });
    },

    initTimer: function() {
        const timerElement = document.getElementById('deadline-timer');
        if (!timerElement) return;

        const timeDisplay = document.getElementById('time-remaining');
        const timerLabel = document.querySelector('.timer-text-label');

        const update = () => {
            const now = new Date();
            const deadline = new Date();
            deadline.setHours(deadlineHour, deadlineMinute, 0, 0);
            const diff = deadline - now;

            if (diff <= 0) {
                if (timeDisplay) timeDisplay.innerText = "Bestellschluss";
                if (timerLabel) timerLabel.style.display = 'none';
                timerElement.classList.add('timer-finished');
                return;
            }

            const h = String(Math.floor((diff / (1000 * 60 * 60)) % 24)).padStart(2, '0');
            const m = String(Math.floor((diff / (1000 * 60)) % 60)).padStart(2, '0');
            const s = String(Math.floor((diff / 1000) % 60)).padStart(2, '0');
            
            if (timeDisplay) timeDisplay.innerText = `${h}:${m}:${s}`;
            
            const totalMin = Math.floor(diff / 1000 / 60);
            timerElement.classList.toggle('timer-critical', totalMin < 15);
            timerElement.classList.toggle('timer-warning', totalMin >= 15 && totalMin < 60);
        };
        setInterval(update, 1000);
        update();
    },

    initGlobalModals: function() {
        const modal = document.getElementById('confirm-modal');
        if (!modal) return;
        window.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
        const cancelBtn = document.getElementById('modal-cancel-btn');
        if (cancelBtn) cancelBtn.addEventListener('click', () => modal.style.display = 'none');
    }
};

// Global verfügbar machen für onclick-Attribute
window.toggleMenu = GlobalCore.toggleMenu;
window.showToast = GlobalCore.showToast;
document.addEventListener("DOMContentLoaded", () => GlobalCore.init());
