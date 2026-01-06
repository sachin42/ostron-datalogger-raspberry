// Main JavaScript for ODAMS Datalogger

// Connection status check
function checkConnection() {
    fetch('/health')
        .then(r => r.json())
        .then(data => {
            const indicator = document.getElementById('connection-status');
            const statusText = document.getElementById('status-text');
            if (indicator && statusText) {
                indicator.className = 'status-indicator status-success';
                statusText.textContent = 'Connected';
            }
        })
        .catch(err => {
            const indicator = document.getElementById('connection-status');
            const statusText = document.getElementById('status-text');
            if (indicator && statusText) {
                indicator.className = 'status-indicator status-danger';
                statusText.textContent = 'Disconnected';
            }
        });
}

// Check connection every 30 seconds
setInterval(checkConnection, 30000);
checkConnection();

// Utility function to format timestamps
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// Utility function to show notifications
function showNotification(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        ${message}
        <button class="alert-close" onclick="this.parentElement.remove()">×</button>
    `;

    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alert, container.firstChild);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }
}

// AJAX helper
function fetchAPI(url, options = {}) {
    return fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    });
}

// Export for use in other scripts
window.datalogger = {
    checkConnection,
    formatTimestamp,
    showNotification,
    fetchAPI
};
