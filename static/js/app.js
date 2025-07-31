document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/static/login.html';
        return;
    }

    const fetchWithAuth = async (url, options = {}) => {
        const currentToken = localStorage.getItem('accessToken');
        if (!currentToken) {
            window.location.href = '/static/login.html';
            throw new Error('No token found, redirecting to login.');
        }

        const headers = {
            ...options.headers,
            'Authorization': `Bearer ${currentToken}`
        };

        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            localStorage.removeItem('accessToken');
            window.location.href = '/static/login.html';
            throw new Error('Unauthorized');
        }
        return response;
    };

    const updateDashboard = async () => {
        try {
            const response = await fetchWithAuth('/api/v1/dashboard/status');
            if (!response.ok) throw new Error(`Failed to fetch status: ${response.statusText}`);
            const data = await response.json();

            document.getElementById('vm-name').textContent = data.instance_name;
            
            const statusBadge = document.getElementById('vm-status');
            statusBadge.textContent = data.status;
            statusBadge.className = 'status-badge'; // Reset classes
            if (data.status.toLowerCase() === 'running') {
                statusBadge.classList.add('running');
            } else if (data.status.toLowerCase() === 'terminated') {
                statusBadge.classList.add('terminated');
            } else {
                statusBadge.classList.add('loading');
            }

            const progressBar = document.getElementById('progress-bar');
            progressBar.style.width = `${data.traffic_usage_percent}%`;
            
            document.getElementById('traffic-details').textContent = 
                `${data.current_traffic_gb.toFixed(2)} GB / ${data.traffic_threshold_gb} GB (${data.traffic_usage_percent}%)`;

        } catch (error) {
            console.error('Error updating dashboard:', error);
            // Also display an error on the dashboard itself
            document.getElementById('traffic-details').textContent = "Error loading data.";
        }
    };

    const updateActionLogs = async () => {
        try {
            const response = await fetchWithAuth('/api/v1/logs/actions?limit=10');
            if (!response.ok) throw new Error('Failed to fetch logs');
            const logs = await response.json();
            const logsList = document.getElementById('action-logs');
            logsList.innerHTML = '';
            if (logs.length === 0) {
                logsList.innerHTML = '<li>No actions logged yet.</li>';
                return;
            }
            logs.forEach(log => {
                const li = document.createElement('li');
                const timestamp = new Date(log.timestamp).toLocaleString();
                li.textContent = `[${timestamp}] ${log.action_type}: ${log.reason || ''}`;
                logsList.appendChild(li);
            });
        } catch (error) {
            console.error('Error updating action logs:', error);
        }
    };

    const handleVmAction = async (url, actionName) => {
        if (!confirm(`Are you sure you want to ${actionName} the VM?`)) return;
        try {
            const response = await fetchWithAuth(url, { method: 'POST' });
            if (response.ok) {
                alert(`VM ${actionName} initiated.`);
                setTimeout(() => {
                    updateDashboard();
                    updateActionLogs();
                }, 3000); // Refresh after 3 seconds
            } else {
                const error = await response.json();
                alert(`Error: ${error.detail || 'Failed to perform action'}`);
            }
        } catch (error) {
            console.error(`Error during ${actionName}:`, error);
        }
    };

    document.getElementById('logoutButton').addEventListener('click', () => {
        localStorage.removeItem('accessToken');
        window.location.href = '/static/login.html';
    });

    document.getElementById('startButton').addEventListener('click', () => handleVmAction('/api/v1/vm/start', 'start'));
    document.getElementById('shutdownButton').addEventListener('click', () => handleVmAction('/api/v1/vm/shutdown', 'shutdown'));

    // Initial data load
    updateDashboard();
    updateActionLogs();

    // Refresh data every 30 seconds
    setInterval(() => {
        updateDashboard();
        updateActionLogs();
    }, 30000);
});
