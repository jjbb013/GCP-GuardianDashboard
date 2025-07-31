document.addEventListener('DOMContentLoaded', () => {
    const loginSection = document.getElementById('login-section');
    const dashboardSection = document.getElementById('dashboard-section');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');

    const token = localStorage.getItem('accessToken');

    if (token) {
        showDashboard();
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        try {
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData,
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('accessToken', data.access_token);
                showDashboard();
            } else {
                loginError.textContent = 'Invalid username or password';
            }
        } catch (error) {
            loginError.textContent = 'An error occurred. Please try again.';
        }
    });

    async function showDashboard() {
        loginSection.classList.add('hidden');
        dashboardSection.classList.remove('hidden');
        await updateStatus();
    }

    async function updateStatus() {
        const token = localStorage.getItem('accessToken');
        try {
            const response = await fetch('/api/v1/dashboard/status', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            if (response.ok) {
                const data = await response.json();
                document.getElementById('instance-name').textContent = data.instance_name;
                document.getElementById('vm-status').textContent = data.status;
                document.getElementById('traffic-usage').textContent = 
                    `${data.current_traffic_gb.toFixed(2)} / ${data.traffic_threshold_gb} GB`;
                
                const progress = document.getElementById('traffic-progress');
                progress.style.width = `${data.traffic_usage_percent}%`;
                
                if (data.traffic_usage_percent > 75) {
                    progress.style.backgroundColor = '#dc3545';
                } else {
                    progress.style.backgroundColor = '#28a745';
                }
            } else {
                logout();
            }
        } catch (error) {
            console.error('Error fetching status:', error);
        }
    }

    document.getElementById('shutdown-btn').addEventListener('click', async () => {
        await performAction('/api/v1/vm/shutdown', 'Shutting down VM...');
    });

    document.getElementById('start-btn').addEventListener('click', async () => {
        await performAction('/api/v1/vm/start', 'Starting VM...');
    });

    document.getElementById('logout-btn').addEventListener('click', () => {
        logout();
    });

    async function performAction(url, message) {
        const token = localStorage.getItem('accessToken');
        if (confirm('Are you sure?')) {
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                    },
                });
                if (response.ok) {
                    alert(message);
                    setTimeout(updateStatus, 3000); // Refresh status after 3 seconds
                } else {
                    alert('Action failed.');
                    logout();
                }
            } catch (error) {
                console.error('Error performing action:', error);
            }
        }
    }

    function logout() {
        localStorage.removeItem('accessToken');
        loginSection.classList.remove('hidden');
        dashboardSection.classList.add('hidden');
    }
});
