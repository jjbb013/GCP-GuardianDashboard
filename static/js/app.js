document.addEventListener('DOMContentLoaded', function() {
    // --- 粒子网络背景 ---
    function initParticleNetwork() {
        const canvas = document.getElementById('particle-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        let particles = [];
        const particleCount = 100;
        const maxDistance = 120;

        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });

        class Particle {
            constructor(x, y, directionX, directionY, size, color) {
                this.x = x;
                this.y = y;
                this.directionX = directionX;
                this.directionY = directionY;
                this.size = size;
                this.color = color;
            }

            draw() {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
                ctx.fillStyle = this.color;
                ctx.fill();
            }

            update() {
                if (this.x > canvas.width || this.x < 0) {
                    this.directionX = -this.directionX;
                }
                if (this.y > canvas.height || this.y < 0) {
                    this.directionY = -this.directionY;
                }
                this.x += this.directionX;
                this.y += this.directionY;
                this.draw();
            }
        }

        function init() {
            particles = [];
            for (let i = 0; i < particleCount; i++) {
                const size = Math.random() * 2 + 1;
                const x = Math.random() * (canvas.width - size * 2) + size;
                const y = Math.random() * (canvas.height - size * 2) + size;
                const directionX = (Math.random() * .4) - .2;
                const directionY = (Math.random() * .4) - .2;
                const color = '#888';
                particles.push(new Particle(x, y, directionX, directionY, size, color));
            }
        }

        function connect() {
            for (let a = 0; a < particles.length; a++) {
                for (let b = a; b < particles.length; b++) {
                    const distance = ((particles[a].x - particles[b].x) * (particles[a].x - particles[b].x))
                                 + ((particles[a].y - particles[b].y) * (particles[a].y - particles[b].y));
                    if (distance < (maxDistance * maxDistance)) {
                        const opacity = 1 - (distance / (maxDistance * maxDistance));
                        ctx.strokeStyle = `rgba(150, 150, 150, ${opacity})`;
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.moveTo(particles[a].x, particles[a].y);
                        ctx.lineTo(particles[b].x, particles[b].y);
                        ctx.stroke();
                    }
                }
            }
        }

        function animate() {
            requestAnimationFrame(animate);
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            for (let i = 0; i < particles.length; i++) {
                particles[i].update();
            }
            connect();
        }

        init();
        animate();
    }
    initParticleNetwork();

    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/static/login.html';
        return;
    }

    let servers = []; // To store the list of servers globally

    const fetchWithAuth = async (url, options = {}) => {
        const currentToken = localStorage.getItem('accessToken');
        if (!currentToken) {
            window.location.href = '/static/login.html';
            throw new Error('No token found, redirecting to login.');
        }
        const headers = { ...options.headers, 'Authorization': `Bearer ${currentToken}` };
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            localStorage.removeItem('accessToken');
            window.location.href = '/static/login.html';
            throw new Error('Unauthorized');
        }
        return response;
    };

    const createServerCard = (server) => {
        const cardWrapper = document.createElement('div');
        cardWrapper.className = 'server-card-wrapper';
        cardWrapper.id = `server-card-${server.id}`;
        
        cardWrapper.innerHTML = `
            <div class="dashboard-grid">
                <!-- VM Status Card -->
                <div class="card vm-status-card">
                <h3>VM Status</h3>
                <p><strong>Instance:</strong> <span id="vm-name-${server.id}">Loading...</span></p>
                <p><strong>Status:</strong> <span id="vm-status-${server.id}" class="status-badge">Loading...</span></p>
                <div class="actions">
                    <button id="startButton-${server.id}" class="action-button">Start VM</button>
                    <button id="shutdownButton-${server.id}" class="action-button">Shutdown VM</button>
                </div>
            </div>

            <!-- Traffic Card -->
            <div class="card traffic-card">
                <h3>Monthly Egress Traffic</h3>
                <div class="progress-bar-container">
                    <div id="progress-bar-${server.id}" class="progress-bar"></div>
                </div>
                <p id="traffic-details-${server.id}">Loading...</p>
                <div class="actions">
                    <button id="refreshButton-${server.id}" class="action-button">Refresh Data</button>
                </div>
            </div>

            <!-- Action Logs Card -->
            <div class="card logs-card">
                <h3>Action Logs</h3>
                <ul id="action-logs-${server.id}">
                    <li>Loading logs...</li>
                </ul>
            </div>
        </div> 
        `;
        return cardWrapper;
    };

    const renderDashboardData = (server, data) => {
        document.getElementById(`vm-name-${server.id}`).textContent = data.instance_name;
        const statusBadge = document.getElementById(`vm-status-${server.id}`);
        statusBadge.textContent = data.status;
        statusBadge.className = 'status-badge';
        if (data.status.toLowerCase() === 'running') statusBadge.classList.add('running');
        else if (data.status.toLowerCase() === 'terminated') statusBadge.classList.add('terminated');
        else statusBadge.classList.add('loading');
        document.getElementById(`progress-bar-${server.id}`).style.width = `${data.traffic_usage_percent}%`;
        document.getElementById(`traffic-details-${server.id}`).textContent = 
            `${data.current_traffic_gb.toFixed(2)} GB / ${data.traffic_threshold_gb} GB (${data.traffic_usage_percent}%)`;
    };

    const updateDashboardForServer = async (server, force = false) => {
        const cacheKey = `dashboardData-${server.id}`;
        const cachedData = JSON.parse(localStorage.getItem(cacheKey));
        const now = new Date().getTime();

        if (!force && cachedData && (now - cachedData.timestamp < 3600000)) { // 1 hour cache
            renderDashboardData(server, cachedData.data);
            return;
        }

        try {
            const response = await fetchWithAuth(`/api/v1/servers/${server.id}/status`);
            if (!response.ok) throw new Error(`Failed to fetch status: ${response.statusText}`);
            const data = await response.json();
            renderDashboardData(server, data);
            localStorage.setItem(cacheKey, JSON.stringify({ data: data, timestamp: now }));
        } catch (error) {
            console.error(`Error updating dashboard for ${server.id}:`, error);
            document.getElementById(`traffic-details-${server.id}`).textContent = "Error loading data.";
        }
    };

    const updateActionLogsForServer = async (server) => {
        try {
            const response = await fetchWithAuth(`/api/v1/logs/actions?server_id=${server.id}&limit=10`);
            if (!response.ok) throw new Error('Failed to fetch logs');
            const logs = await response.json();
            const logsList = document.getElementById(`action-logs-${server.id}`);
            logsList.innerHTML = '';
            if (logs.length === 0) {
                logsList.innerHTML = '<li>No actions logged for this server.</li>';
                return;
            }
            logs.forEach(log => {
                const li = document.createElement('li');
                const timestamp = new Date(log.timestamp).toLocaleString();
                li.textContent = `[${timestamp}] ${log.action_type}: ${log.reason || ''}`;
                logsList.appendChild(li);
            });
        } catch (error) {
            console.error(`Error updating action logs for ${server.id}:`, error);
        }
    };

    const handleVmAction = async (server, action) => {
        if (!confirm(`Are you sure you want to ${action} the VM for server ${server.name}?`)) return;
        try {
            const response = await fetchWithAuth(`/api/v1/servers/${server.id}/${action}`, { method: 'POST' });
            if (response.ok) {
                alert(`VM ${action} initiated for server ${server.name}.`);
                setTimeout(() => {
                    updateDashboardForServer(server, true);
                    updateActionLogsForServer(server);
                }, 3000);
            } else {
                const error = await response.json();
                alert(`Error: ${error.detail || 'Failed to perform action'}`);
            }
        } catch (error) {
            console.error(`Error during ${action} for ${server.id}:`, error);
        }
    };

    const initialize = async () => {
        const container = document.getElementById('dashboard-container');
        try {
            const response = await fetchWithAuth('/api/v1/servers');
            if (!response.ok) throw new Error('Failed to fetch servers');
            servers = await response.json(); // Populate the global servers array
            
            container.innerHTML = '';
            if (servers.length === 0) {
                container.innerHTML = '<p>No servers configured. Please check your .env file.</p>';
                return;
            }

            servers.forEach(server => {
                const card = createServerCard(server);
                container.appendChild(card);

                // Add event listeners for the new card's buttons
                document.getElementById(`startButton-${server.id}`).addEventListener('click', () => handleVmAction(server, 'start'));
                document.getElementById(`shutdownButton-${server.id}`).addEventListener('click', () => handleVmAction(server, 'shutdown'));
                document.getElementById(`refreshButton-${server.id}`).addEventListener('click', () => {
                    updateDashboardForServer(server, true);
                    updateActionLogsForServer(server);
                });

                // Initial data load for this card
                updateDashboardForServer(server);
                updateActionLogsForServer(server);
            });

        } catch (error) {
            console.error("Failed to initialize dashboards:", error);
            container.innerHTML = '<p>Error loading server configurations.</p>';
        }
    };

    document.getElementById('logoutButton').addEventListener('click', () => {
        localStorage.clear(); // Clear all cache on logout
        window.location.href = '/static/login.html';
    });

    // Initial load
    initialize();

    // Set up periodic refresh for all servers
    setInterval(() => {
        console.log("Periodic refresh for all servers...");
        servers.forEach(server => {
            updateDashboardForServer(server);
        });
    }, 3600000); // every hour

    setInterval(() => {
        servers.forEach(server => {
            updateActionLogsForServer(server);
        });
    }, 300000); // every 5 minutes
});
