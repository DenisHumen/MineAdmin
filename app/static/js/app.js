const API = {
    token: localStorage.getItem('ma_token'),

    async request(url, options = {}) {
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
        const resp = await fetch(url, { ...options, headers });
        if (resp.status === 401) {
            this.token = null;
            localStorage.removeItem('ma_token');
            App.showAuth();
            throw new Error('Unauthorized');
        }
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data.detail || `Error ${resp.status}`);
        }
        return resp.json();
    },

    get(url) { return this.request(url); },
    post(url, body) { return this.request(url, { method: 'POST', body: JSON.stringify(body) }); },
    put(url, body) { return this.request(url, { method: 'PUT', body: JSON.stringify(body) }); },
    del(url) { return this.request(url, { method: 'DELETE' }); },

    async upload(url, formData) {
        const headers = {};
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
        const resp = await fetch(url, { method: 'POST', headers, body: formData });
        if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
        return resp.json();
    },

    setToken(token) {
        this.token = token;
        localStorage.setItem('ma_token', token);
    }
};

const Toast = {
    container: null,
    init() {
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);
    },
    show(message, type = 'info', duration = 4000) {
        const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${icons[type] || ''}</span><span>${message}</span><span class="toast-close" onclick="this.parentElement.remove()">✕</span>`;
        this.container.appendChild(toast);
        setTimeout(() => { if (toast.parentElement) toast.remove(); }, duration);
    },
    success(msg) { this.show(msg, 'success'); },
    error(msg) { this.show(msg, 'error', 6000); },
    warning(msg) { this.show(msg, 'warning'); },
    info(msg) { this.show(msg, 'info'); },
};

const App = {
    currentPage: 'dashboard',
    servers: [],
    systemStats: null,
    networkInfo: null,
    statsInterval: null,

    async init() {
        Toast.init();
        try {
            const { needs_setup } = await fetch('/api/auth/needs-setup').then(r => r.json());
            if (needs_setup) {
                this.showSetup();
                return;
            }
            if (!API.token) {
                this.showAuth();
                return;
            }
            await API.get('/api/auth/check');
            this.showMain();
        } catch (e) {
            this.showAuth();
        }
    },

    showSetup() {
        document.getElementById('app').innerHTML = `
        <div class="auth-screen">
            <div class="auth-card">
                <h1>MineAdmin</h1>
                <p class="subtitle">Создайте аккаунт администратора</p>
                <div class="form-group">
                    <label class="form-label">Имя пользователя</label>
                    <input type="text" class="form-input" id="setup-user" placeholder="admin" autofocus>
                </div>
                <div class="form-group">
                    <label class="form-label">Пароль</label>
                    <input type="password" class="form-input" id="setup-pass" placeholder="Минимум 4 символа">
                </div>
                <button class="btn btn-primary btn-lg" style="width:100%;margin-top:8px" onclick="App.doSetup()">Создать аккаунт</button>
            </div>
        </div>`;
        document.getElementById('setup-pass').addEventListener('keydown', e => { if (e.key === 'Enter') App.doSetup(); });
    },

    async doSetup() {
        const username = document.getElementById('setup-user').value.trim();
        const password = document.getElementById('setup-pass').value;
        if (!username || password.length < 4) { Toast.error('Введите имя и пароль (мин. 4 символа)'); return; }
        try {
            const { token } = await API.post('/api/auth/setup', { username, password });
            API.setToken(token);
            Toast.success('Аккаунт создан!');
            this.showMain();
        } catch (e) { Toast.error(e.message); }
    },

    showAuth() {
        document.getElementById('app').innerHTML = `
        <div class="auth-screen">
            <div class="auth-card">
                <h1>MineAdmin</h1>
                <p class="subtitle">Войдите для продолжения</p>
                <div class="form-group">
                    <label class="form-label">Имя пользователя</label>
                    <input type="text" class="form-input" id="login-user" placeholder="admin" autofocus>
                </div>
                <div class="form-group">
                    <label class="form-label">Пароль</label>
                    <input type="password" class="form-input" id="login-pass" placeholder="Пароль">
                </div>
                <button class="btn btn-primary btn-lg" style="width:100%;margin-top:8px" onclick="App.doLogin()">Войти</button>
            </div>
        </div>`;
        document.getElementById('login-pass').addEventListener('keydown', e => { if (e.key === 'Enter') App.doLogin(); });
    },

    async doLogin() {
        const username = document.getElementById('login-user').value.trim();
        const password = document.getElementById('login-pass').value;
        try {
            const { token } = await API.post('/api/auth/login', { username, password });
            API.setToken(token);
            Toast.success('Добро пожаловать!');
            this.showMain();
        } catch (e) { Toast.error('Неверные данные'); }
    },

    showMain() {
        document.getElementById('app').innerHTML = `
        <button class="mobile-menu-btn" onclick="document.querySelector('.sidebar').classList.toggle('open')">☰</button>
        <div class="main-layout">
            <aside class="sidebar">
                <div class="sidebar-header">
                    <div class="sidebar-logo" style="display:flex;align-items:center;gap:10px"><img src="/static/logo.png" alt="Logo" style="width:32px;height:32px;border-radius:6px;object-fit:cover">MineAdmin</div>
                    <div class="sidebar-version" id="sidebar-version">v...</div>
                </div>
                <nav class="sidebar-nav">
                    <div class="nav-section">
                        <div class="nav-section-title">Основное</div>
                        <div class="nav-item active" data-page="dashboard" onclick="App.navigate('dashboard')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
                            Панель управления
                        </div>
                        <div class="nav-item" data-page="servers" onclick="App.navigate('servers')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>
                            Серверы
                        </div>
                        <div class="nav-item" data-page="create" onclick="App.navigate('create')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
                            Новый сервер
                        </div>
                    </div>
                    <div class="nav-section">
                        <div class="nav-section-title">Система</div>
                        <div class="nav-item" data-page="system-terminal" onclick="App.navigate('system-terminal')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                            Терминал
                        </div>
                        <div class="nav-item" data-page="monitoring" onclick="App.navigate('monitoring')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/></svg>
                            Мониторинг
                        </div>
                        <div class="nav-item" data-page="settings" onclick="App.navigate('settings')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
                            Настройки
                        </div>
                        <div class="nav-item" data-page="docs" onclick="App.navigate('docs')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                            Документация
                        </div>
                    </div>
                </nav>
                <div class="sidebar-footer">
                    <div style="display:flex;align-items:center;justify-content:space-between">
                        <span id="sidebar-user"></span>
                        <button class="btn btn-ghost btn-sm" onclick="App.logout()">Выйти</button>
                    </div>
                </div>
            </aside>
            <main class="content" id="content"></main>
        </div>`;

        try {
            const payload = JSON.parse(atob(API.token.split('.')[1]));
            document.getElementById('sidebar-user').textContent = payload.username;
        } catch(e) {}

        API.get('/api/config/version').then(r => {
            const el = document.getElementById('sidebar-version');
            if (el && r.version) el.textContent = 'v' + r.version;
        }).catch(() => {});

        this.navigate('dashboard');
        this.startStatsPolling();
    },

    logout() {
        API.token = null;
        localStorage.removeItem('ma_token');
        if (this.statsInterval) clearInterval(this.statsInterval);
        this.showAuth();
    },

    navigate(page) {
        this.currentPage = page;
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.page === page);
        });
        document.querySelector('.sidebar')?.classList.remove('open');
        const content = document.getElementById('content');
        if (content) {
            content.innerHTML = '<div class="loading-screen"><div class="spinner spinner-lg"></div><p>Загрузка...</p></div>';
            Pages[page]?.();
        }
    },

    startStatsPolling() {
        this.fetchStats();
        this.statsInterval = setInterval(() => this.fetchStats(), 5000);
    },

    async fetchStats() {
        try {
            this.systemStats = await API.get('/api/monitoring/stats');
            this.networkInfo = await API.get('/api/monitoring/network');
            const { servers } = await API.get('/api/servers');
            this.servers = servers;
            if (this.currentPage === 'dashboard') Pages.updateDashboardStats?.();
        } catch(e) {}
    },
};

const Pages = {
    async dashboard() {
        const content = document.getElementById('content');
        try {
            const [{ servers }, stats, netInfo] = await Promise.all([
                API.get('/api/servers'),
                API.get('/api/monitoring/stats'),
                API.get('/api/monitoring/network'),
            ]);
            App.servers = servers;
            App.systemStats = stats;
            App.networkInfo = netInfo;

            const running = servers.filter(s => s.status === 'running').length;

            content.innerHTML = `
            <div class="fade-in">
                <div class="page-header">
                    <h1 class="page-title">Панель управления</h1>
                    <button class="btn btn-primary" onclick="App.navigate('create')">+ Новый сервер</button>
                </div>
                <div class="grid grid-4" id="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Серверы</div>
                        <div class="stat-value blue">${servers.length}</div>
                        <div class="stat-sub">${running} запущено</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">CPU</div>
                        <div class="stat-value ${stats.cpu.percent > 80 ? 'red' : stats.cpu.percent > 50 ? 'yellow' : 'green'}" id="dash-cpu">${stats.cpu.percent}%</div>
                        <div class="stat-sub">${stats.cpu.count} ядер</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">RAM</div>
                        <div class="stat-value ${stats.memory.percent > 80 ? 'red' : stats.memory.percent > 50 ? 'yellow' : 'green'}" id="dash-ram">${stats.memory.percent}%</div>
                        <div class="stat-sub">${stats.memory.used_formatted.human} / ${stats.memory.total_formatted.human}</div>
                    </div>
                    <div class="stat-card" style="cursor:pointer" onclick="App.navigate('monitoring')" title="Подробнее о дисках">
                        <div class="stat-label">Диск (основной)</div>
                        <div class="stat-value ${stats.disk.percent > 80 ? 'red' : 'green'}" id="dash-disk">${stats.disk.percent}%</div>
                        <div class="stat-sub">${stats.disk.free_formatted.human} свободно</div>
                        ${(stats.disks || []).length > 1 ? `<div class="stat-sub" style="color:var(--text-muted);font-size:11px;margin-top:2px">+${stats.disks.length - 1} дисков</div>` : ''}
                    </div>
                </div>
                <div style="margin-top:16px">
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Сеть</h3>
                        </div>
                        <div style="display:flex;gap:24px;flex-wrap:wrap;font-size:14px">
                            <div><span style="color:var(--text-muted)">Локальный IP:</span> <strong>${netInfo.local_ip}</strong></div>
                            <div><span style="color:var(--text-muted)">Публичный IP:</span> <strong class="public-ip-hidden" style="cursor:pointer;color:var(--primary);text-decoration:underline" onclick="PublicIP.requestReveal(this, '${netInfo.public_ip || ''}')">${netInfo.public_ip ? '••••••••••' : 'Не определён'}</strong></div>
                        </div>
                    </div>
                </div>
                <div style="margin-top:16px">
                    <div class="card-header" style="margin-bottom:12px">
                        <h3 class="card-title">Серверы</h3>
                    </div>
                    <div id="dash-servers">
                        ${servers.length === 0 ? `
                            <div class="empty-state">
                                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
                                <h3>Нет серверов</h3>
                                <p>Создайте свой первый Minecraft сервер</p>
                                <button class="btn btn-primary" onclick="App.navigate('create')">Создать сервер</button>
                            </div>
                        ` : servers.map(s => ServerCard.render(s)).join('')}
                    </div>
                </div>
            </div>`;
        } catch (e) {
            content.innerHTML = `<div class="empty-state"><h3>Ошибка загрузки</h3><p>${e.message}</p></div>`;
        }
    },

    updateDashboardStats() {
        const s = App.systemStats;
        if (!s) return;
        const cpu = document.getElementById('dash-cpu');
        const ram = document.getElementById('dash-ram');
        const disk = document.getElementById('dash-disk');
        if (cpu) cpu.textContent = s.cpu.percent + '%';
        if (ram) ram.textContent = s.memory.percent + '%';
        if (disk) disk.textContent = s.disk.percent + '%';
    },

    async servers() {
        const content = document.getElementById('content');
        try {
            const { servers } = await API.get('/api/servers');
            App.servers = servers;
            content.innerHTML = `
            <div class="fade-in">
                <div class="page-header">
                    <h1 class="page-title">Серверы <small>${servers.length} всего</small></h1>
                    <button class="btn btn-primary" onclick="App.navigate('create')">+ Новый сервер</button>
                </div>
                <div id="servers-list">
                    ${servers.length === 0 ? `
                        <div class="empty-state">
                            <h3>Нет серверов</h3>
                            <p>Создайте ваш первый Minecraft сервер одной кнопкой</p>
                            <button class="btn btn-primary" onclick="App.navigate('create')">Создать сервер</button>
                        </div>
                    ` : servers.map(s => ServerCard.render(s)).join('')}
                </div>
            </div>`;
        } catch (e) { content.innerHTML = `<div class="empty-state"><h3>Ошибка</h3><p>${e.message}</p></div>`; }
    },

    async create() {
        const content = document.getElementById('content');
        content.innerHTML = `
        <div class="fade-in">
            <div class="page-header">
                <h1 class="page-title">Новый сервер</h1>
            </div>
            <div class="card" style="max-width:640px">
                <div class="form-group">
                    <label class="form-label">Название сервера</label>
                    <input type="text" class="form-input" id="new-name" placeholder="My Server">
                </div>
                <div class="form-group">
                    <label class="form-label">Ядро сервера</label>
                    <select class="form-select" id="new-core" onchange="Pages.loadVersions()">
                        <option value="">Выберите ядро...</option>
                    </select>
                    <div id="core-desc" style="font-size:12px;color:var(--text-muted);margin-top:4px"></div>
                </div>
                <div class="form-group">
                    <label class="form-label">Версия Minecraft</label>
                    <select class="form-select" id="new-version" disabled>
                        <option value="">Сначала выберите ядро</option>
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Min RAM</label>
                        <input type="text" class="form-input" id="new-mem-min" value="1G" placeholder="1G">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Max RAM</label>
                        <input type="text" class="form-input" id="new-mem-max" value="2G" placeholder="2G">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Порт</label>
                        <input type="number" class="form-input" id="new-port" placeholder="Авто">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Макс. игроков</label>
                    <input type="number" class="form-input" id="new-players" value="20" min="1" max="1000">
                </div>
                <div id="java-info" style="margin-bottom:16px"></div>
                <button class="btn btn-primary btn-lg" style="width:100%" onclick="Pages.doCreate()" id="create-btn">
                    Установить сервер
                </button>
                <div id="install-progress" style="margin-top:16px;display:none">
                    <div class="progress-bar"><div class="progress-fill" id="install-fill" style="width:0%"></div></div>
                    <div class="progress-info">
                        <span id="install-status">Подготовка...</span>
                        <span class="progress-percent" id="install-percent">0%</span>
                    </div>
                </div>
            </div>
        </div>`;
        await Pages.loadCoreTypes();
    },

    async loadCoreTypes() {
        try {
            const cores = await API.get('/api/servers/core-types');
            const sel = document.getElementById('new-core');
            cores.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id; opt.textContent = c.name;
                opt.dataset.desc = c.description;
                sel.appendChild(opt);
            });
        } catch(e) { Toast.error('Ошибка загрузки ядер'); }
    },

    async loadVersions() {
        const core = document.getElementById('new-core').value;
        const verSel = document.getElementById('new-version');
        const desc = document.getElementById('core-desc');
        const opt = document.querySelector(`#new-core option[value="${core}"]`);
        desc.textContent = opt?.dataset.desc || '';

        if (!core) { verSel.disabled = true; verSel.innerHTML = '<option>Сначала выберите ядро</option>'; return; }

        verSel.innerHTML = '<option>Загрузка версий...</option>';
        verSel.disabled = true;

        try {
            const { versions } = await API.get(`/api/servers/versions/${core}`);
            verSel.innerHTML = '<option value="">Выберите версию...</option>';
            versions.forEach(v => {
                const opt = document.createElement('option');
                opt.value = v.id; opt.textContent = v.id + (v.type === 'snapshot' ? ' (snapshot)' : '');
                verSel.appendChild(opt);
            });
            verSel.disabled = false;
        } catch(e) { Toast.error('Ошибка загрузки версий'); }
    },

    async doCreate() {
        const name = document.getElementById('new-name').value.trim();
        const core = document.getElementById('new-core').value;
        const version = document.getElementById('new-version').value;
        const memMin = document.getElementById('new-mem-min').value;
        const memMax = document.getElementById('new-mem-max').value;
        const port = document.getElementById('new-port').value;
        const maxPlayers = parseInt(document.getElementById('new-players').value) || 20;

        if (!name) { Toast.error('Введите название сервера'); return; }
        if (!core) { Toast.error('Выберите ядро'); return; }
        if (!version) { Toast.error('Выберите версию'); return; }

        try {
            const javaCheck = await API.get(`/api/servers/java/check/${core}/${version}`);
            if (!javaCheck.available) {
                JavaInstaller.show(javaCheck, () => Pages.doCreate());
                return;
            }
        } catch(e) {  }

        const btn = document.getElementById('create-btn');
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Установка...';

        const progressDiv = document.getElementById('install-progress');
        progressDiv.style.display = 'block';

        try {
            const body = { name, core_type: core, mc_version: version, memory_min: memMin, memory_max: memMax, max_players: maxPlayers };
            if (port) body.port = parseInt(port);
            const result = await API.post('/api/servers', body);
            Toast.info('Установка сервера начата...');

            const taskId = result.task_id;
            const checkProgress = async () => {
                try {
                    const p = await API.get(`/api/servers/install-progress/${taskId}`);
                    const fill = document.getElementById('install-fill');
                    const status = document.getElementById('install-status');
                    const percent = document.getElementById('install-percent');
                    if (fill) fill.style.width = p.percent + '%';
                    if (percent) percent.textContent = p.percent + '%';
                    const statusMap = {
                        idle: 'Подготовка...', fetching_info: 'Получение информации...',
                        downloading: `Скачивание ${p.filename}...`,
                        installing_forge: 'Установка Forge...',
                        building_spigot: 'Сборка Spigot (может занять время)...',
                        completed: 'Установка завершена!', error: `Ошибка: ${p.error}`
                    };
                    if (status) status.textContent = statusMap[p.status] || p.status;

                    if (p.status === 'completed') {
                        if (fill) fill.classList.add('done');
                        if (fill) fill.style.width = '100%';
                        if (percent) percent.textContent = '100%';
                        Toast.success('Сервер установлен!');
                        setTimeout(() => App.navigate('servers'), 1500);
                    } else if (p.status === 'error') {
                        Toast.error(p.error);
                        btn.disabled = false;
                        btn.textContent = 'Установить сервер';
                    } else {
                        setTimeout(checkProgress, 1000);
                    }
                } catch(e) { setTimeout(checkProgress, 2000); }
            };
            setTimeout(checkProgress, 1000);
        } catch (e) {
            Toast.error(e.message);
            btn.disabled = false;
            btn.textContent = 'Установить сервер';
            progressDiv.style.display = 'none';
        }
    },

    async monitoring() {
        const content = document.getElementById('content');
        try {
            const [stats, sysInfo, javaProcs] = await Promise.all([
                API.get('/api/monitoring/stats'),
                API.get('/api/monitoring/system'),
                API.get('/api/monitoring/java-processes'),
            ]);

            content.innerHTML = `
            <div class="fade-in">
                <div class="page-header"><h1 class="page-title">Мониторинг системы</h1></div>
                <div class="grid grid-4">
                    <div class="stat-card"><div class="stat-label">CPU</div>
                        <div class="stat-value ${stats.cpu.percent > 80 ? 'red' : 'green'}">${stats.cpu.percent}%</div>
                        <div class="stat-sub">${sysInfo.cpu_count_logical} потоков</div>
                        <div class="progress-bar" style="margin-top:8px"><div class="progress-fill" style="width:${stats.cpu.percent}%"></div></div>
                    </div>
                    <div class="stat-card"><div class="stat-label">RAM</div>
                        <div class="stat-value ${stats.memory.percent > 80 ? 'red' : 'green'}">${stats.memory.percent}%</div>
                        <div class="stat-sub">${stats.memory.used_formatted.human} / ${stats.memory.total_formatted.human}</div>
                        <div class="progress-bar" style="margin-top:8px"><div class="progress-fill" style="width:${stats.memory.percent}%"></div></div>
                    </div>
                    <div class="stat-card"><div class="stat-label">Диск (основной)</div>
                        <div class="stat-value">${stats.disk.percent}%</div>
                        <div class="stat-sub">${stats.disk.used_formatted.human} / ${stats.disk.total_formatted.human}</div>
                        <div class="progress-bar" style="margin-top:8px"><div class="progress-fill" style="width:${stats.disk.percent}%"></div></div>
                    </div>
                    <div class="stat-card"><div class="stat-label">Сеть</div>
                        <div class="stat-value blue">${stats.network.bytes_recv > 1073741824 ? (stats.network.bytes_recv / 1073741824).toFixed(1) + ' GB' : (stats.network.bytes_recv / 1048576).toFixed(0) + ' MB'}</div>
                        <div class="stat-sub">Получено</div>
                    </div>
                </div>
                <div class="card" style="margin-top:16px">
                    <div class="card-header"><h3 class="card-title">Загрузка по ядрам CPU</h3></div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap">
                        ${stats.cpu.per_core.map((p, i) => `
                            <div style="flex:1;min-width:60px;text-align:center">
                                <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">#${i}</div>
                                <div class="progress-bar" style="height:60px;width:24px;margin:0 auto;display:flex;flex-direction:column-reverse;border-radius:4px">
                                    <div style="width:100%;height:${p}%;background:var(--accent-gradient);border-radius:4px;transition:height 0.5s"></div>
                                </div>
                                <div style="font-size:11px;margin-top:4px;color:var(--text-secondary)">${p}%</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ${(stats.disks && stats.disks.length > 0) ? `
                <div class="card" style="margin-top:16px">
                    <div class="card-header"><h3 class="card-title">Все диски</h3></div>
                    <div class="table-container">
                        <table>
                            <thead><tr><th>Устройство</th><th>Точка монтирования</th><th>ФС</th><th>Размер</th><th>Использовано</th><th>Свободно</th><th>%</th><th></th></tr></thead>
                            <tbody>
                                ${stats.disks.map(d => `
                                    <tr style="${d.is_main ? 'background:rgba(var(--primary-rgb,99,102,241),0.1);font-weight:500' : ''}">
                                        <td>${d.device}</td>
                                        <td style="font-family:'JetBrains Mono';font-size:12px">${d.mountpoint}</td>
                                        <td>${d.fstype}</td>
                                        <td>${d.total_formatted.human}</td>
                                        <td>${d.used_formatted.human}</td>
                                        <td>${d.free_formatted.human}</td>
                                        <td>
                                            <div style="display:flex;align-items:center;gap:8px">
                                                <div class="progress-bar" style="width:80px;height:6px"><div class="progress-fill" style="width:${d.percent}%"></div></div>
                                                <span class="${d.percent > 80 ? 'red' : ''}">${d.percent}%</span>
                                            </div>
                                        </td>
                                        <td>${d.is_main ? '<span class="badge badge-blue" style="font-size:10px">Серверы</span>' : ''}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>` : ''}
                <div class="card" style="margin-top:16px">
                    <div class="card-header"><h3 class="card-title">Информация о системе</h3></div>
                    <div class="grid grid-2">
                        <div><span style="color:var(--text-muted)">Платформа:</span> ${sysInfo.platform} ${sysInfo.architecture}</div>
                        <div><span style="color:var(--text-muted)">Хост:</span> ${sysInfo.hostname}</div>
                        <div><span style="color:var(--text-muted)">Python:</span> ${sysInfo.python_version}</div>
                        <div><span style="color:var(--text-muted)">Процессор:</span> ${sysInfo.processor || 'N/A'}</div>
                    </div>
                </div>
                ${javaProcs.processes.length > 0 ? `
                <div class="card" style="margin-top:16px">
                    <div class="card-header"><h3 class="card-title">Java процессы</h3></div>
                    <div class="table-container">
                        <table>
                            <thead><tr><th>PID</th><th>Имя</th><th>CPU</th><th>RAM</th></tr></thead>
                            <tbody>
                                ${javaProcs.processes.map(p => `
                                    <tr><td>${p.pid}</td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">${p.name}</td>
                                    <td>${p.cpu_percent}%</td><td>${p.memory_formatted.human}</td></tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>` : ''}
            </div>`;
        } catch(e) { content.innerHTML = `<div class="empty-state"><h3>Ошибка</h3><p>${e.message}</p></div>`; }
    },

    async settings() {
        const content = document.getElementById('content');
        try {
            const { config } = await API.get('/api/config');
            const dbStatus = await API.get('/api/config/db-status');

            content.innerHTML = `
            <div class="fade-in">
                <div class="page-header"><h1 class="page-title">Настройки</h1></div>
                ${dbStatus.mysql_error ? `
                    <div class="notification-banner warning">
                        <span>⚠</span>
                        <div>
                            <strong>MySQL недоступен</strong>: ${dbStatus.mysql_error}. Используется SQLite.
                            <button class="btn btn-ghost btn-sm" style="margin-left:8px" onclick="App.navigate('docs')">Инструкция</button>
                        </div>
                    </div>` : ''}
                <div class="tabs">
                    <div class="tab active" onclick="Pages.settingsTab('general',this)">Основные</div>
                    <div class="tab" onclick="Pages.settingsTab('database',this)">База данных</div>
                    <div class="tab" onclick="Pages.settingsTab('java',this)">Java</div>
                    <div class="tab" onclick="Pages.settingsTab('backup',this)">Бекапы</div>
                    <div class="tab" onclick="Pages.settingsTab('ssh',this)">SSH / Терминал</div>
                </div>
                <div id="settings-content">
                    <div class="card">
                        <div class="form-group">
                            <label class="form-label">Web хост</label>
                            <input type="text" class="form-input" id="cfg-host" value="${config.web?.host || '0.0.0.0'}">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Web порт</label>
                            <input type="number" class="form-input" id="cfg-port" value="${config.web?.port || 8080}">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Путь хранения серверов</label>
                            <input type="text" class="form-input" id="cfg-servers-dir" value="${config.servers_dir || ''}" placeholder="По умолчанию: data/servers">
                            <div style="font-size:12px;color:var(--text-muted);margin-top:4px">Каталог для хранения файлов серверов. Изменение вступит в силу для новых серверов.</div>
                        </div>
                        <div class="form-group">
                            <label class="form-label">RAM по умолчанию (мин)</label>
                            <input type="text" class="form-input" id="cfg-defmem" value="${config.default_java_memory || '2G'}">
                        </div>
                        <div class="form-group">
                            <label class="form-label">RAM по умолчанию (макс)</label>
                            <input type="text" class="form-input" id="cfg-maxmem" value="${config.max_java_memory || '4G'}">
                        </div>
                        <button class="btn btn-primary" onclick="Pages.saveSettings()">Сохранить</button>
                    </div>
                </div>
            </div>`;
        } catch(e) { content.innerHTML = `<div class="empty-state"><h3>Ошибка</h3><p>${e.message}</p></div>`; }
    },

    settingsTab(tab, el) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        el.classList.add('active');
        if (tab === 'general') Pages.settings();
        else if (tab === 'database') Pages.settingsDatabase();
        else if (tab === 'java') Pages.settingsJava();
        else if (tab === 'backup') Pages.settingsBackup();
        else if (tab === 'ssh') Pages.settingsSSH();
    },

    async settingsDatabase() {
        const { config } = await API.get('/api/config');
        const dbStatus = await API.get('/api/config/db-status');
        document.getElementById('settings-content').innerHTML = `
        <div class="card fade-in">
            <div style="margin-bottom:16px">
                <strong>Текущая БД:</strong> <span class="badge badge-blue">${dbStatus.db_type.toUpperCase()}</span>
            </div>
            <div class="form-group">
                <label class="form-label">Тип базы данных</label>
                <select class="form-select" id="db-type">
                    <option value="sqlite" ${dbStatus.db_type === 'sqlite' ? 'selected' : ''}>SQLite (локальная)</option>
                    <option value="mysql" ${dbStatus.db_type === 'mysql' ? 'selected' : ''}>MySQL</option>
                </select>
            </div>
            <div id="mysql-settings" style="display:${dbStatus.db_type === 'mysql' ? 'block' : 'none'}">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Хост MySQL</label>
                        <input type="text" class="form-input" id="mysql-host" value="${config.mysql?.host || 'localhost'}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Порт</label>
                        <input type="number" class="form-input" id="mysql-port" value="${config.mysql?.port || 3306}">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Пользователь</label>
                        <input type="text" class="form-input" id="mysql-user" value="${config.mysql?.user || 'root'}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Пароль</label>
                        <input type="password" class="form-input" id="mysql-pass" value="">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">База данных</label>
                    <input type="text" class="form-input" id="mysql-db" value="${config.mysql?.database || 'mineadmin'}">
                </div>
            </div>
            <button class="btn btn-primary" onclick="Pages.switchDatabase()">Применить</button>
        </div>`;

        document.getElementById('db-type').addEventListener('change', function() {
            document.getElementById('mysql-settings').style.display = this.value === 'mysql' ? 'block' : 'none';
        });
    },

    async switchDatabase() {
        const dbType = document.getElementById('db-type').value;
        const body = { db_type: dbType };
        if (dbType === 'mysql') {
            body.mysql = {
                host: document.getElementById('mysql-host').value,
                port: parseInt(document.getElementById('mysql-port').value),
                user: document.getElementById('mysql-user').value,
                password: document.getElementById('mysql-pass').value,
                database: document.getElementById('mysql-db').value,
            };
        }
        try {
            const result = await API.post('/api/config/switch-db', body);
            if (result.success) Toast.success(result.message);
            else {
                Toast.warning(result.message);
                if (result.help_url) Toast.info('Перейдите в документацию для решения проблемы');
            }
        } catch(e) { Toast.error(e.message); }
    },

    async settingsJava() {
        try {
            const { installations } = await API.get('/api/servers/java');
            document.getElementById('settings-content').innerHTML = `
            <div class="card fade-in">
                <div class="card-header"><h3 class="card-title">Установленные версии Java</h3></div>
                ${installations.length === 0 ? '<p style="color:var(--text-muted)">Java не найдена</p>' : `
                <div class="table-container">
                    <table>
                        <thead><tr><th>Версия</th><th>Major</th><th>Путь</th></tr></thead>
                        <tbody>
                            ${installations.map(j => `<tr><td>${j.version}</td><td>${j.major_version}</td><td style="font-family:'JetBrains Mono';font-size:12px">${j.path}</td></tr>`).join('')}
                        </tbody>
                    </table>
                </div>`}
            </div>`;
        } catch(e) { Toast.error(e.message); }
    },

    async saveSettings() {
        try {
            await API.put('/api/config', {
                web: {
                    host: document.getElementById('cfg-host').value,
                    port: parseInt(document.getElementById('cfg-port').value),
                },
                servers_dir: document.getElementById('cfg-servers-dir').value,
                default_java_memory: document.getElementById('cfg-defmem').value,
                max_java_memory: document.getElementById('cfg-maxmem').value,
            });
            Toast.success('Настройки сохранены (перезапустите для применения порта/хоста)');
        } catch(e) { Toast.error(e.message); }
    },

    docs() {
        const content = document.getElementById('content');
        const categories = [
            { id: 'getting-started', title: 'Начало работы', content: `
                <h2>Начало работы</h2>
                <p>MineAdmin — инструмент для управления Minecraft серверами через веб-интерфейс.</p>
                <h3>Быстрый старт</h3>
                <ol>
                    <li>Установите Python 3.10+</li>
                    <li>Установите зависимости: <code>pip install -r requirements.txt</code></li>
                    <li>Запустите: <code>python main.py</code></li>
                    <li>Откройте браузер по адресу, показанному при запуске</li>
                    <li>Создайте аккаунт администратора</li>
                    <li>Создайте сервер, выбрав ядро и версию</li>
                </ol>
                <h3>Поддерживаемые ядра</h3>
                <ul>
                    <li><strong>Vanilla</strong> — официальный сервер Mojang</li>
                    <li><strong>Paper</strong> — высокопроизводительный форк Spigot</li>
                    <li><strong>Purpur</strong> — форк Paper с доп. функциями</li>
                    <li><strong>Fabric</strong> — легковесная платформа модов</li>
                    <li><strong>Forge</strong> — популярная платформа модов</li>
                    <li><strong>Spigot</strong> — форк CraftBukkit</li>
                </ul>
            `},
            { id: 'server-management', title: 'Управление серверами', content: `
                <h2>Управление серверами</h2>
                <h3>Создание сервера</h3>
                <p>Перейдите в "Новый сервер", выберите ядро, версию и параметры. Нажмите "Установить" — файлы скачаются автоматически.</p>
                <h3>Запуск и остановка</h3>
                <p>Используйте кнопки на карточке сервера. При запуске автоматически подбирается нужная Java.</p>
                <h3>Несколько серверов</h3>
                <p>Можно запускать несколько серверов параллельно. Порты назначаются автоматически (+1 от базового). Можно изменить порт вручную.</p>
                <h3>Терминал</h3>
                <p>Встроенный терминал с автодополнением команд. Поддерживает все команды Minecraft сервера. Нажмите Tab для автодополнения.</p>
            `},
            { id: 'files', title: 'Файловый менеджер', content: `
                <h2>Файловый менеджер</h2>
                <p>Просматривайте и редактируйте файлы сервера прямо из браузера.</p>
                <h3>Возможности</h3>
                <ul>
                    <li>Просмотр файлов и папок</li>
                    <li>Редактирование текстовых файлов (properties, yml, json и др.)</li>
                    <li>Загрузка файлов через drag&drop или выбор файла</li>
                    <li>Скачивание файлов</li>
                    <li>Создание папок, переименование, удаление</li>
                    <li>Отображение размеров в байтах, КБ, МБ, ГБ</li>
                </ul>
            `},
            { id: 'database-troubleshooting', title: 'Базы данных', content: `
                <h2>Базы данных</h2>
                <h3>SQLite (по умолчанию)</h3>
                <p>Локальная БД, не требует настройки. Файл хранится в <code>data/db/mineadmin.db</code>.</p>
                <h3>MySQL</h3>
                <p>Для использования MySQL:</p>
                <ol>
                    <li>Установите MySQL/MariaDB</li>
                    <li>Создайте базу: <code>CREATE DATABASE mineadmin;</code></li>
                    <li>Перейдите в Настройки → База данных</li>
                    <li>Укажите параметры подключения</li>
                </ol>
                <h3>Синхронизация</h3>
                <p>При переключении БД данные автоматически экспортируются из текущей и импортируются в новую. Если MySQL недоступен, система вернётся к SQLite.</p>
                <h3>Решение проблем</h3>
                <ul>
                    <li><strong>Access denied</strong> — проверьте логин/пароль</li>
                    <li><strong>Can't connect</strong> — убедитесь что MySQL запущен</li>
                    <li><strong>Unknown database</strong> — создайте БД вручную</li>
                </ul>
            `},
            { id: 'java', title: 'Java', content: `
                <h2>Java</h2>
                <h3>Требования по версиям</h3>
                <ul>
                    <li>MC 1.21+ → Java 21</li>
                    <li>MC 1.17-1.20.4 → Java 17</li>
                    <li>MC 1.16 → Java 11</li>
                    <li>MC 1.8-1.15 → Java 8</li>
                </ul>
                <h3>Установка</h3>
                <p>MineAdmin автоматически находит установленные версии Java. Для установки:</p>
                <pre><code># Ubuntu/Debian
sudo apt install openjdk-21-jre-headless

# macOS
brew install openjdk@21

# Windows
winget install EclipseAdoptium.Temurin.21.JRE</code></pre>
            `},
            { id: 'backups', title: 'Бекапы', content: `
                <h2>Бекапы</h2>
                <p>MineAdmin поддерживает создание полных бекапов серверов — вручную и по расписанию, с возможностью выгрузки через SFTP.</p>
                <h3>Быстрый бекап</h3>
                <ol>
                    <li>Откройте карточку сервера</li>
                    <li>Нажмите кнопку <strong>Бекап</strong></li>
                    <li>Укажите путь для сохранения (или оставьте по умолчанию)</li>
                    <li>Нажмите <strong>Начать бекап</strong></li>
                </ol>
                <p>Бекап создаётся в формате ZIP-архива, содержащего все файлы сервера (мир, конфиги, плагины и т.д.).</p>
                <h3>Выгрузка через SFTP</h3>
                <p>При включении SFTP происходит следующий процесс:</p>
                <ol>
                    <li>Сервер <strong>автоматически останавливается</strong> командой <code>stop</code> (корректная остановка с сохранением мира)</li>
                    <li>Создаётся ZIP-архив всех файлов сервера</li>
                    <li>Архив выгружается на удалённый сервер по SFTP</li>
                    <li>Сервер <strong>автоматически запускается</strong> обратно</li>
                </ol>
                <p>Настройки SFTP (хост, порт, логин, пароль/ключ, удалённый путь) можно задать в <strong>Настройки → Бекапы</strong> или при создании каждого бекапа индивидуально.</p>
                <h3>Расписание автобекапов</h3>
                <p>В разделе <strong>Настройки → Бекапы</strong> можно включить автоматические бекапы:</p>
                <ul>
                    <li><strong>Интервал</strong> — как часто создавать бекапы (в часах, по умолчанию 24)</li>
                    <li><strong>Макс. бекапов</strong> — сколько хранить на сервер (старые удаляются автоматически)</li>
                </ul>
                <h3>Управление бекапами</h3>
                <ul>
                    <li>Все бекапы отображаются в <strong>Настройки → Бекапы</strong></li>
                    <li>Можно <strong>скачать</strong> любой бекап через браузер</li>
                    <li>Можно <strong>удалить</strong> ненужные бекапы</li>
                    <li>Путь хранения бекапов настраивается (по умолчанию <code>data/backups</code>)</li>
                </ul>
                <h3>Восстановление из бекапа</h3>
                <p>Для восстановления:</p>
                <ol>
                    <li>Остановите сервер</li>
                    <li>Скачайте нужный бекап</li>
                    <li>Распакуйте ZIP-архив в директорию сервера, заменив файлы</li>
                    <li>Запустите сервер</li>
                </ol>
            `},
            { id: 'docker', title: 'Docker', content: `
                <h2>Docker</h2>
                <h3>Быстрый запуск</h3>
                <pre><code>docker compose up -d</code></pre>
                <h3>Порты</h3>
                <ul>
                    <li>8080 — веб-интерфейс</li>
                    <li>25565-25575 — Minecraft серверы</li>
                </ul>
                <h3>Данные</h3>
                <p>Данные хранятся в папке <code>./data</code> в корне проекта и сохраняются при перезапуске контейнера.</p>
            `},
            { id: 'network', title: 'Сеть', content: `
                <h2>Сеть</h2>
                <h3>Локальная сеть</h3>
                <p>Серверы автоматически доступны в локальной сети по IP, показанному на панели.</p>
                <h3>Из интернета</h3>
                <p>Для доступа из интернета необходимо:</p>
                <ul>
                    <li>Пробросить порт на роутере (25565 → ваш ПК)</li>
                    <li>Или использовать сервисы типа ngrok, playit.gg</li>
                    <li>Проверьте доступность кнопкой "Проверить сеть" на странице сервера</li>
                </ul>
            `},
        ];

        content.innerHTML = `
        <div class="fade-in">
            <div class="page-header"><h1 class="page-title">Документация</h1></div>
            <div style="display:flex;gap:24px">
                <div style="min-width:200px">
                    <ul class="docs-sidebar">
                        ${categories.map((c, i) => `<li class="${i === 0 ? 'active' : ''}" onclick="Pages.showDoc('${c.id}', this)">${c.title}</li>`).join('')}
                    </ul>
                </div>
                <div class="card" style="flex:1" id="docs-body">
                    <div class="docs-content">${categories[0].content}</div>
                </div>
            </div>
        </div>`;

        window._docsData = categories;
    },

    showDoc(id, el) {
        document.querySelectorAll('.docs-sidebar li').forEach(l => l.classList.remove('active'));
        el.classList.add('active');
        const cat = window._docsData.find(c => c.id === id);
        if (cat) document.getElementById('docs-body').innerHTML = `<div class="docs-content fade-in">${cat.content}</div>`;
    },
};

const ServerCard = {
    render(server) {
        const statusMap = {
            running: { badge: 'badge-green', text: 'Запущен' },
            stopped: { badge: 'badge-gray', text: 'Остановлен' },
            starting: { badge: 'badge-yellow', text: 'Запуск...' },
            stopping: { badge: 'badge-yellow', text: 'Остановка...' },
            installing: { badge: 'badge-blue', text: 'Установка...' },
            error: { badge: 'badge-red', text: 'Ошибка' },
        };
        const st = statusMap[server.status] || statusMap.stopped;
        const stats = server.process_stats;

        return `
        <div class="server-card" id="server-${server.id}">
            <div class="server-card-header">
                <div class="server-name">${this.esc(server.name)}</div>
                <span class="badge ${st.badge}"><span class="badge-dot"></span>${st.text}</span>
            </div>
            <div class="server-info">
                <div class="server-info-item">Ядро: <span>${server.core_type}</span></div>
                <div class="server-info-item">Версия: <span>${server.mc_version}</span></div>
                <div class="server-info-item">Порт: <span>${server.port}</span></div>
                <div class="server-info-item">RAM: <span>${server.memory_min}-${server.memory_max}</span></div>
                ${stats ? `<div class="server-info-item">CPU: <span>${stats.cpu_percent}%</span></div>` : ''}
            </div>
            <div class="server-actions">
                ${server.status === 'running' ? `
                    <button class="btn btn-danger btn-sm" onclick="ServerActions.stop(${server.id})">Остановить</button>
                    <button class="btn btn-ghost btn-sm" onclick="ServerActions.openTerminal(${server.id})">Терминал</button>
                ` : server.status === 'stopped' ? `
                    <button class="btn btn-success btn-sm" onclick="ServerActions.start(${server.id})">Запустить</button>
                ` : server.status === 'installing' ? `
                    <button class="btn btn-ghost btn-sm" disabled>Установка...</button>
                ` : ''}
                <button class="btn btn-ghost btn-sm" onclick="ServerActions.openFiles(${server.id})">Файлы</button>
                <button class="btn btn-ghost btn-sm" onclick="ServerActions.openProperties(${server.id})">Настройки</button>
                <button class="btn btn-ghost btn-sm" onclick="ServerActions.checkNetwork(${server.id})">Сеть</button>
                <button class="btn btn-ghost btn-sm" onclick="ServerActions.backupServer(${server.id})">Бекап</button>
                <button class="btn btn-ghost btn-sm" onclick="ServerActions.editServer(${server.id})">Изменить</button>
                <button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="ServerActions.deleteServer(${server.id})">Удалить</button>
            </div>
        </div>`;
    },
    esc(str) { const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
};

const ServerActions = {
    async start(id) {
        try {
            await API.post(`/api/servers/${id}/start`);
            Toast.success('Сервер запускается...');
            setTimeout(() => App.navigate(App.currentPage), 1000);
        } catch(e) { Toast.error(e.message); }
    },

    async stop(id) {
        try {
            await API.post(`/api/servers/${id}/stop`);
            Toast.success('Сервер останавливается...');
            setTimeout(() => App.navigate(App.currentPage), 2000);
        } catch(e) { Toast.error(e.message); }
    },

    openTerminal(id) {
        const server = App.servers.find(s => s.id === id);
        if (!server) return;
        Modal.show(`Терминал — ${server.name}`, `
            <div class="terminal-container">
                <div class="terminal-header">
                    <div class="terminal-title"><div class="terminal-dots"><div class="terminal-dot red"></div><div class="terminal-dot yellow"></div><div class="terminal-dot green"></div></div><span>Terminal</span></div>
                    <span class="badge badge-green"><span class="badge-dot"></span>Connected</span>
                </div>
                <div class="terminal-output" id="term-output"></div>
                <div class="terminal-input-container" style="position:relative">
                    <span class="terminal-prompt">></span>
                    <input type="text" class="terminal-input" id="term-input" placeholder="Введите команду..." autocomplete="off">
                    <div class="terminal-autocomplete" id="term-autocomplete"></div>
                </div>
            </div>
        `, null, '800px');

        Terminal.connect(id);
    },

    async openFiles(id) {
        const server = App.servers.find(s => s.id === id);
        if (!server) return;
        Modal.show(`Файлы — ${server.name}`, '<div id="file-browser-content"><div class="spinner" style="margin:20px auto"></div></div>', null, '900px');
        FileManager.load(id, '');
    },

    async openProperties(id) {
        const server = App.servers.find(s => s.id === id);
        if (!server) return;
        try {
            const { properties } = await API.get(`/api/servers/${id}/properties`);
            const rows = Object.entries(properties).map(([k, v]) =>
                `<div class="property-row"><div class="property-key">${k}</div><div class="property-value"><input data-key="${k}" value="${v.replace(/"/g, '&quot;')}"></div></div>`
            ).join('');
            Modal.show(`Свойства — ${server.name}`, `
                <div style="max-height:60vh;overflow-y:auto">${rows || '<p style="color:var(--text-muted)">server.properties не найден. Запустите сервер хотя бы раз.</p>'}</div>
            `, async () => {
                const props = {};
                document.querySelectorAll('.property-value input').forEach(inp => {
                    props[inp.dataset.key] = inp.value;
                });
                await API.put(`/api/servers/${id}/properties`, { properties: props });
                Toast.success('Свойства сохранены. Перезапустите сервер для применения.');
            }, '700px');
        } catch(e) { Toast.error(e.message); }
    },

    async checkNetwork(id) {
        const server = App.servers.find(s => s.id === id);
        if (!server) return;
        Toast.info('Проверка сети...');
        try {
            const result = await API.get(`/api/servers/${id}/network`);
            Modal.show(`Сеть — ${server.name}`, `
                <div class="grid grid-2" style="gap:12px">
                    <div class="stat-card"><div class="stat-label">Локальный IP</div><div class="stat-value" style="font-size:18px">${result.local_ip}</div></div>
                    <div class="stat-card"><div class="stat-label">Публичный IP</div><div class="stat-value public-ip-hidden" style="font-size:18px;cursor:pointer;color:var(--primary);text-decoration:underline" onclick="PublicIP.requestReveal(this, '${result.public_ip || ''}')">${result.public_ip ? '••••••••••' : 'Не определён'}</div></div>
                    <div class="stat-card"><div class="stat-label">Порт</div><div class="stat-value" style="font-size:18px">${result.port}</div></div>
                    <div class="stat-card"><div class="stat-label">Локальный доступ</div><div class="stat-value ${result.local_accessible ? 'green' : 'red'}" style="font-size:18px">${result.local_accessible ? 'Доступен' : 'Недоступен'}</div>
                        ${result.local_latency_ms ? `<div class="stat-sub">${result.local_latency_ms}ms</div>` : ''}
                    </div>
                    <div class="stat-card"><div class="stat-label">Внешний доступ</div><div class="stat-value ${result.external_accessible ? 'green' : 'red'}" style="font-size:18px">${result.external_accessible === true ? 'Доступен' : result.external_accessible === false ? 'Недоступен' : 'Не проверен'}</div>
                        ${result.external_error ? `<div class="stat-sub">${result.external_error}</div>` : ''}
                    </div>
                </div>
                <div style="margin-top:16px;font-size:13px;color:var(--text-secondary)">
                    <p>Адрес для подключения из локальной сети: <strong>${result.local_ip}:${result.port}</strong></p>
                    ${result.public_ip ? `<p>Адрес для подключения из интернета: <strong class="public-ip-hidden" style="cursor:pointer;color:var(--primary);text-decoration:underline" onclick="PublicIP.requestReveal(this, '${result.public_ip}:${result.port}')">••••••••••</strong></p>` : ''}
                </div>
            `);
        } catch(e) { Toast.error(e.message); }
    },

    async backupServer(id) {
        const server = App.servers.find(s => s.id === id);
        if (!server) return;
        let cfg = {};
        try { cfg = (await API.get('/api/config')).config; } catch(e) {}
        const backupCfg = cfg.backup || {};
        const sftpCfg = backupCfg.sftp || {};

        Modal.show(`Бекап — ${server.name}`, `
            <div class="form-group">
                <label class="form-label">Путь для сохранения бекапа</label>
                <input type="text" class="form-input" id="backup-path" value="${backupCfg.path || ''}" placeholder="/путь/к/бекапам">
            </div>
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
                <label class="form-label" style="margin:0">Выгрузить через SFTP</label>
                <label class="toggle">
                    <input type="checkbox" id="backup-sftp-enable" ${sftpCfg.enabled ? 'checked' : ''} onchange="document.getElementById('backup-sftp-fields').style.display=this.checked?'block':'none'">
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div id="backup-sftp-fields" style="display:${sftpCfg.enabled ? 'block' : 'none'}">
                <div class="notification-banner warning" style="margin-bottom:12px">
                    <span>!</span>
                    <div>При SFTP-бекапе сервер будет остановлен командой <code>stop</code>, после бекапа запустится автоматически.</div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label class="form-label">SFTP хост</label><input type="text" class="form-input" id="backup-sftp-host" value="${sftpCfg.host || ''}"></div>
                    <div class="form-group"><label class="form-label">Порт</label><input type="number" class="form-input" id="backup-sftp-port" value="${sftpCfg.port || 22}"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label class="form-label">Пользователь</label><input type="text" class="form-input" id="backup-sftp-user" value="${sftpCfg.username || ''}"></div>
                    <div class="form-group"><label class="form-label">Пароль</label><input type="password" class="form-input" id="backup-sftp-pass" value="" placeholder="${sftpCfg.password ? 'Сохранён' : ''}"></div>
                </div>
                <div class="form-group"><label class="form-label">Путь SSH ключа</label><input type="text" class="form-input" id="backup-sftp-key" value="${sftpCfg.key_path || ''}" placeholder="/home/user/.ssh/id_rsa"></div>
                <div class="form-group"><label class="form-label">Удалённый путь</label><input type="text" class="form-input" id="backup-sftp-remote" value="${sftpCfg.remote_path || '/backups'}"></div>
            </div>
            <div id="backup-progress-area" style="display:none;margin-top:16px">
                <div class="progress-bar"><div class="progress-fill" id="backup-fill" style="width:0%"></div></div>
                <div class="progress-info"><span id="backup-status">Подготовка...</span><span class="progress-percent" id="backup-percent">0%</span></div>
            </div>
        `, async () => {
            const useSftp = document.getElementById('backup-sftp-enable').checked;
            const body = {
                backup_path: document.getElementById('backup-path').value,
                use_sftp: useSftp,
            };
            if (useSftp) {
                body.sftp = {
                    host: document.getElementById('backup-sftp-host').value,
                    port: parseInt(document.getElementById('backup-sftp-port').value),
                    username: document.getElementById('backup-sftp-user').value,
                    password: document.getElementById('backup-sftp-pass').value || undefined,
                    key_path: document.getElementById('backup-sftp-key').value || undefined,
                    remote_path: document.getElementById('backup-sftp-remote').value,
                };
            }
            const { task_id } = await API.post('/api/backups/' + id, body);
            document.getElementById('backup-progress-area').style.display = 'block';
            document.getElementById('modal-save').disabled = true;
            document.getElementById('modal-save').textContent = 'Выполняется...';
            BackupManager.pollProgress(task_id);
            throw new Error('__suppress_close__');
        }, '640px');

        const saveBtn = document.getElementById('modal-save');
        if (saveBtn) saveBtn.textContent = 'Начать бекап';
    },

    async editServer(id) {
        const server = App.servers.find(s => s.id === id);
        if (!server) return;
        Modal.show(`Изменить — ${server.name}`, `
            <div class="form-group"><label class="form-label">Название</label><input type="text" class="form-input" id="edit-name" value="${server.name}"></div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Порт</label><input type="number" class="form-input" id="edit-port" value="${server.port}"></div>
                <div class="form-group"><label class="form-label">Макс. игроков</label><input type="number" class="form-input" id="edit-players" value="${server.max_players}"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Min RAM</label><input type="text" class="form-input" id="edit-mem-min" value="${server.memory_min}"></div>
                <div class="form-group"><label class="form-label">Max RAM</label><input type="text" class="form-input" id="edit-mem-max" value="${server.memory_max}"></div>
            </div>
            <div class="form-group"><label class="form-label">Путь к Java</label><input type="text" class="form-input" id="edit-java" value="${server.java_path || 'java'}" placeholder="java (авто)"></div>
            <div class="form-group"><label class="form-label">Доп. JVM аргументы</label><input type="text" class="form-input" id="edit-jvm" value="${server.jvm_args || ''}" placeholder="-XX:+UseG1GC"></div>
        `, async () => {
            await API.put(`/api/servers/${id}`, {
                name: document.getElementById('edit-name').value,
                port: parseInt(document.getElementById('edit-port').value),
                max_players: parseInt(document.getElementById('edit-players').value),
                memory_min: document.getElementById('edit-mem-min').value,
                memory_max: document.getElementById('edit-mem-max').value,
                java_path: document.getElementById('edit-java').value,
                jvm_args: document.getElementById('edit-jvm').value,
            });
            Toast.success('Сервер обновлён');
            App.navigate(App.currentPage);
        });
    },

    async deleteServer(id) {
        if (!confirm('Удалить сервер и все его файлы? Это действие необратимо.')) return;
        try {
            await API.del(`/api/servers/${id}`);
            Toast.success('Сервер удалён');
            App.navigate(App.currentPage);
        } catch(e) { Toast.error(e.message); }
    },
};

const Modal = {
    show(title, bodyHtml, onSave = null, width = '560px') {
        const existing = document.querySelector('.modal-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
        <div class="modal" style="max-width:${width}">
            <div class="modal-header">
                <h3 class="modal-title">${title}</h3>
                <button class="btn btn-ghost btn-icon sm" onclick="Modal.close()">✕</button>
            </div>
            <div class="modal-body">${bodyHtml}</div>
            ${onSave ? `<div class="modal-footer"><button class="btn btn-ghost" onclick="Modal.close()">Отмена</button><button class="btn btn-primary" id="modal-save">Сохранить</button></div>` : ''}
        </div>`;
        document.body.appendChild(overlay);
        overlay.addEventListener('click', e => { if (e.target === overlay) Modal.close(); });

        if (onSave) {
            document.getElementById('modal-save').addEventListener('click', async () => {
                try { await onSave(); Modal.close(); } catch(e) { if (e.message !== '__suppress_close__') Toast.error(e.message); }
            });
        }
    },
    close() {
        Terminal.disconnect();
        document.querySelector('.modal-overlay')?.remove();
    }
};

const PublicIP = {
    requestReveal(el, ip) {
        if (!ip) return;
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center';
        overlay.innerHTML = `
            <div style="background:var(--bg-primary,#1a1a2e);border:1px solid var(--border,#333);border-radius:12px;padding:32px;max-width:420px;width:90%;text-align:center;color:var(--text-primary,#fff)">
                <div style="font-size:24px;margin-bottom:12px">⚠️</div>
                <h3 style="margin:0 0 12px;font-size:18px">Показать публичный IP?</h3>
                <p style="margin:0 0 24px;font-size:14px;color:var(--text-secondary,#aaa)">Публичный IP-адрес является конфиденциальной информацией. Убедитесь, что рядом нет посторонних.</p>
                <div style="display:flex;gap:12px;justify-content:center">
                    <button class="btn btn-ghost" id="pip-cancel">Отмена</button>
                    <button class="btn btn-primary" id="pip-confirm">Да, показать</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
        overlay.querySelector('#pip-cancel').addEventListener('click', () => overlay.remove());
        overlay.querySelector('#pip-confirm').addEventListener('click', () => {
            el.textContent = ip;
            el.style.cursor = 'default';
            el.style.textDecoration = 'none';
            el.style.color = '';
            el.onclick = null;
            el.classList.remove('public-ip-hidden');
            overlay.remove();
        });
    }
};

const BackupManager = {
    async pollProgress(taskId) {
        try {
            const p = await API.get(`/api/backups/progress/${taskId}`);
            const fill = document.getElementById('backup-fill');
            const status = document.getElementById('backup-status');
            const percent = document.getElementById('backup-percent');

            if (fill) fill.style.width = p.percent + '%';
            if (percent) percent.textContent = p.percent + '%';
            if (status) status.textContent = p.message || p.status;

            if (p.status === 'completed') {
                if (fill) { fill.style.width = '100%'; fill.classList.add('done'); }
                Toast.success('Бекап завершён!');
                const btn = document.getElementById('modal-save');
                if (btn) { btn.textContent = 'Готово'; btn.disabled = false; btn.onclick = () => Modal.close(); }
            } else if (p.status === 'error') {
                Toast.error(p.message || 'Ошибка бекапа');
                const btn = document.getElementById('modal-save');
                if (btn) { btn.textContent = 'Закрыть'; btn.disabled = false; btn.onclick = () => Modal.close(); }
            } else {
                setTimeout(() => this.pollProgress(taskId), 1000);
            }
        } catch(e) {
            setTimeout(() => this.pollProgress(taskId), 2000);
        }
    },

    async showBackupList(serverId = null) {
        try {
            const url = serverId ? `/api/backups?server_id=${serverId}` : '/api/backups';
            const { backups } = await API.get(url);
            if (backups.length === 0) {
                Toast.info('Бекапов не найдено');
                return;
            }
            const rows = backups.map(b => {
                const size = b.size > 1048576 ? (b.size / 1048576).toFixed(1) + ' MB' : (b.size / 1024).toFixed(0) + ' KB';
                const date = new Date(b.created).toLocaleString();
                return `<tr>
                    <td style="font-size:12px">${b.filename}</td>
                    <td>${size}</td>
                    <td>${date}</td>
                    <td>
                        <a href="/api/backups/download/${b.filename}" class="btn btn-ghost btn-sm" style="font-size:11px">Скачать</a>
                        <button class="btn btn-ghost btn-sm" style="font-size:11px;color:var(--red)" onclick="BackupManager.deleteBackup('${b.filename}')">Удалить</button>
                    </td>
                </tr>`;
            }).join('');
            Modal.show('Список бекапов', `
                <div class="table-container" style="max-height:60vh;overflow-y:auto">
                    <table>
                        <thead><tr><th>Файл</th><th>Размер</th><th>Дата</th><th></th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            `, null, '750px');
        } catch(e) { Toast.error(e.message); }
    },

    async deleteBackup(filename) {
        if (!confirm('Удалить этот бекап?')) return;
        try {
            await API.del(`/api/backups/${filename}`);
            Toast.success('Бекап удалён');
            Modal.close();
        } catch(e) { Toast.error(e.message); }
    }
};

const Terminal = {
    ws: null,
    commands: [],
    historyIndex: -1,
    cmdHistory: [],

    connect(serverId) {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}/ws/terminal/${serverId}?token=${API.token}`);

        this.ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            const output = document.getElementById('term-output');
            if (!output) return;

            if (data.type === 'history') {
                output.innerHTML = data.lines.map(l => `<div class="line">${this.escHtml(l)}</div>`).join('');
                output.scrollTop = output.scrollHeight;
            } else if (data.type === 'output') {
                const line = document.createElement('div');
                line.className = 'line';
                if (data.line.includes('WARN')) line.className += ' warn';
                if (data.line.includes('ERROR')) line.className += ' error';
                if (data.line.includes('INFO')) line.className += ' info';
                line.textContent = data.line;
                output.appendChild(line);
                output.scrollTop = output.scrollHeight;
            } else if (data.type === 'autocomplete_commands') {
                this.commands = data.commands;
            } else if (data.type === 'autocomplete_result') {
                this.showAutocomplete(data.matches);
            } else if (data.type === 'error') {
                Toast.error(data.message);
            }
        };

        const input = document.getElementById('term-input');
        if (input) {
            input.focus();
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const cmd = input.value.trim();
                    if (cmd) {
                        this.send(cmd);
                        this.cmdHistory.unshift(cmd);
                        this.historyIndex = -1;
                        input.value = '';
                    }
                } else if (e.key === 'Tab') {
                    e.preventDefault();
                    const prefix = input.value.split(' ').pop();
                    if (prefix) {
                        const matches = this.commands.filter(c => c.startsWith(prefix.toLowerCase()));
                        if (matches.length === 1) {
                            const parts = input.value.split(' ');
                            parts[parts.length - 1] = matches[0];
                            input.value = parts.join(' ');
                        } else if (matches.length > 1) {
                            this.showAutocomplete(matches);
                        }
                    }
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (this.cmdHistory.length > 0 && this.historyIndex < this.cmdHistory.length - 1) {
                        this.historyIndex++;
                        input.value = this.cmdHistory[this.historyIndex];
                    }
                } else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (this.historyIndex > 0) {
                        this.historyIndex--;
                        input.value = this.cmdHistory[this.historyIndex];
                    } else {
                        this.historyIndex = -1;
                        input.value = '';
                    }
                } else if (e.key === 'Escape') {
                    document.getElementById('term-autocomplete').classList.remove('show');
                }
            });

            input.addEventListener('input', () => {
                document.getElementById('term-autocomplete').classList.remove('show');
            });
        }
    },

    send(cmd) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'command', command: cmd }));
        }
    },

    showAutocomplete(matches) {
        const el = document.getElementById('term-autocomplete');
        if (!el || matches.length === 0) { if (el) el.classList.remove('show'); return; }
        el.innerHTML = matches.map(m => `<div class="autocomplete-item" onclick="Terminal.pickAutocomplete('${m}')">${m}</div>`).join('');
        el.classList.add('show');
    },

    pickAutocomplete(cmd) {
        const input = document.getElementById('term-input');
        if (input) {
            const parts = input.value.split(' ');
            parts[parts.length - 1] = cmd;
            input.value = parts.join(' ');
            input.focus();
        }
        document.getElementById('term-autocomplete')?.classList.remove('show');
    },

    disconnect() {
        if (this.ws) { this.ws.close(); this.ws = null; }
    },

    escHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }
};

const FileManager = {
    currentServer: null,
    currentPath: '',

    async load(serverId, path) {
        this.currentServer = serverId;
        this.currentPath = path;
        const container = document.getElementById('file-browser-content');
        if (!container) return;

        try {
            const data = await API.get(`/api/servers/${serverId}/files?path=${encodeURIComponent(path)}`);
            const segments = path ? path.split('/').filter(Boolean) : [];

            container.innerHTML = `
            <div class="file-browser">
                <div class="file-path-bar">
                    <span class="path-segment" onclick="FileManager.load(${serverId}, '')">/root</span>
                    ${segments.map((s, i) => `<span class="path-separator">/</span><span class="path-segment" onclick="FileManager.load(${serverId}, '${segments.slice(0, i + 1).join('/')}')">${s}</span>`).join('')}
                </div>
                <div style="padding:8px 16px;display:flex;gap:8px;border-bottom:1px solid var(--border)">
                    <button class="btn btn-ghost btn-sm" onclick="FileManager.mkdir(${serverId})">+ Папка</button>
                    <button class="btn btn-ghost btn-sm" onclick="FileManager.showUpload(${serverId})">Загрузить</button>
                    ${path ? `<button class="btn btn-ghost btn-sm" onclick="FileManager.load(${serverId}, '${segments.slice(0, -1).join('/')}')">← Назад</button>` : ''}
                </div>
                <ul class="file-list">
                    ${data.items.length === 0 ? '<li class="file-item"><span style="color:var(--text-muted)">Пустая директория</span></li>' :
                    data.items.map(item => `
                    <li class="file-item" ondblclick="${item.is_dir ?
                        `FileManager.load(${serverId}, '${item.path}')` :
                        `FileManager.openFile(${serverId}, '${item.path}')`}">
                        <span class="file-icon">${item.is_dir ? '📁' : this.fileIcon(item.extension)}</span>
                        <span class="file-name">${item.name}</span>
                        <span class="file-size">${item.size ? item.size.human : (item.children_count !== undefined ? item.children_count + ' элементов' : '')}</span>
                        <span class="file-modified">${item.modified ? new Date(item.modified * 1000).toLocaleString() : ''}</span>
                        <div class="file-actions">
                            ${!item.is_dir ? `<button class="btn btn-ghost btn-icon sm" title="Скачать" onclick="event.stopPropagation();FileManager.download(${serverId},'${item.path}')">↓</button>` : ''}
                            <button class="btn btn-ghost btn-icon sm" title="Переименовать" onclick="event.stopPropagation();FileManager.rename(${serverId},'${item.path}','${item.name}')">✎</button>
                            <button class="btn btn-ghost btn-icon sm" style="color:var(--red)" title="Удалить" onclick="event.stopPropagation();FileManager.del(${serverId},'${item.path}')">✕</button>
                        </div>
                    </li>`).join('')}
                </ul>
            </div>
            <div id="file-upload-zone" style="display:none;margin-top:16px">
                <div class="upload-zone" id="drop-zone">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    <p>Перетащите файлы сюда или кликните</p>
                    <input type="file" id="file-upload-input" style="display:none" multiple onchange="FileManager.uploadFiles(${serverId})">
                </div>
                <div id="upload-progress-list" style="margin-top:8px"></div>
            </div>`;
        } catch(e) { container.innerHTML = `<p style="color:var(--red);padding:20px">${e.message}</p>`; }
    },

    fileIcon(ext) {
        const icons = {
            '.jar': '☕', '.yml': '⚙', '.yaml': '⚙', '.properties': '⚙',
            '.json': '{}', '.txt': '📄', '.log': '📋', '.sh': '🔧',
            '.bat': '🔧', '.conf': '⚙', '.xml': '📑', '.png': '🖼',
            '.jpg': '🖼', '.dat': '💾', '.gz': '📦', '.zip': '📦',
        };
        return icons[ext] || '📄';
    },

    async openFile(serverId, path) {
        try {
            const data = await API.get(`/api/servers/${serverId}/files/read?path=${encodeURIComponent(path)}`);
            const container = document.getElementById('file-browser-content');
            container.innerHTML = `
            <div class="file-editor">
                <div class="file-editor-header">
                    <div>
                        <strong>${data.name}</strong>
                        <span style="margin-left:8px;font-size:12px;color:var(--text-muted)">${data.size.human}</span>
                        <span style="margin-left:8px;font-size:12px;color:var(--text-muted)">(${data.size.bytes} bytes / ${data.size.bits} bits / ${data.size.mb} MB)</span>
                    </div>
                    <div class="btn-group">
                        <button class="btn btn-ghost btn-sm" onclick="FileManager.load(${serverId}, '${path.split('/').slice(0, -1).join('/')}')">← Назад</button>
                        <button class="btn btn-primary btn-sm" onclick="FileManager.saveFile(${serverId}, '${path}')">Сохранить</button>
                    </div>
                </div>
                <textarea id="file-editor-content">${data.content.replace(/</g, '&lt;')}</textarea>
            </div>`;
        } catch(e) { Toast.error(e.message); }
    },

    async saveFile(serverId, path) {
        const content = document.getElementById('file-editor-content').value;
        try {
            await API.post(`/api/servers/${serverId}/files/save`, { path, content });
            Toast.success('Файл сохранён');
        } catch(e) { Toast.error(e.message); }
    },

    download(serverId, path) {
        window.open(`/api/servers/${serverId}/files/download?path=${encodeURIComponent(path)}&token=${API.token}`, '_blank');
    },

    async del(serverId, path) {
        if (!confirm(`Удалить ${path}?`)) return;
        try {
            await API.del(`/api/servers/${serverId}/files?path=${encodeURIComponent(path)}`);
            Toast.success('Удалено');
            FileManager.load(serverId, this.currentPath);
        } catch(e) { Toast.error(e.message); }
    },

    async rename(serverId, path, oldName) {
        const newName = prompt('Новое имя:', oldName);
        if (!newName || newName === oldName) return;
        try {
            await API.post(`/api/servers/${serverId}/files/rename`, { path, new_name: newName });
            Toast.success('Переименовано');
            FileManager.load(serverId, this.currentPath);
        } catch(e) { Toast.error(e.message); }
    },

    async mkdir(serverId) {
        const name = prompt('Имя папки:');
        if (!name) return;
        const path = this.currentPath ? `${this.currentPath}/${name}` : name;
        try {
            await API.post(`/api/servers/${serverId}/files/mkdir`, { path });
            Toast.success('Папка создана');
            FileManager.load(serverId, this.currentPath);
        } catch(e) { Toast.error(e.message); }
    },

    showUpload(serverId) {
        const zone = document.getElementById('file-upload-zone');
        zone.style.display = zone.style.display === 'none' ? 'block' : 'none';

        const dropZone = document.getElementById('drop-zone');
        dropZone.onclick = () => document.getElementById('file-upload-input').click();
        dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragover'); };
        dropZone.ondragleave = () => dropZone.classList.remove('dragover');
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            this._doUpload(serverId, files);
        };
    },

    uploadFiles(serverId) {
        const files = document.getElementById('file-upload-input').files;
        this._doUpload(serverId, files);
    },

    async _doUpload(serverId, files) {
        const list = document.getElementById('upload-progress-list');
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('path', this.currentPath);

            const item = document.createElement('div');
            item.style.cssText = 'margin-bottom:8px';
            item.innerHTML = `<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px"><span>${file.name}</span><span>${this._formatSize(file.size)}</span></div><div class="progress-bar"><div class="progress-fill" style="width:50%"></div></div>`;
            list.appendChild(item);

            try {
                const result = await API.upload(`/api/servers/${serverId}/files/upload`, formData);
                item.querySelector('.progress-fill').style.width = '100%';
                item.querySelector('.progress-fill').classList.add('done');
                Toast.success(`${file.name} загружен (${result.size.human})`);
            } catch(e) {
                item.querySelector('.progress-fill').style.background = 'var(--red)';
                Toast.error(`Ошибка загрузки ${file.name}`);
            }
        }
        setTimeout(() => FileManager.load(serverId, this.currentPath), 1000);
    },

    _formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
        return (bytes / 1073741824).toFixed(2) + ' GB';
    }
};

Pages.settingsSSH = async function() {
    try {
        const { ssh, system, ssh_available } = await API.get('/api/config/ssh');
        document.getElementById('settings-content').innerHTML = `
        <div class="card fade-in">
            ${!ssh_available ? `
                <div class="notification-banner warning">
                    <span>!</span>
                    <div>Системный терминал доступен только на Linux. Текущая система: <strong>${system}</strong></div>
                </div>` : ''}
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
                <label class="form-label" style="margin:0">SSH терминал</label>
                <label class="toggle">
                    <input type="checkbox" id="ssh-enabled" ${ssh.enabled ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
                <span style="font-size:13px;color:var(--text-secondary)">${ssh.enabled ? 'Включён' : 'Выключен'}</span>
            </div>
            <div class="form-group">
                <label class="form-label">Тип авторизации</label>
                <select class="form-select" id="ssh-auth-type" onchange="document.getElementById('ssh-pass-block').style.display=this.value==='password'?'block':'none';document.getElementById('ssh-key-block').style.display=this.value==='key'?'block':'none'">
                    <option value="password" ${ssh.auth_type === 'password' ? 'selected' : ''}>Пароль</option>
                    <option value="key" ${ssh.auth_type === 'key' ? 'selected' : ''}>SSH ключ</option>
                </select>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Хост</label>
                    <input type="text" class="form-input" id="ssh-host" value="${ssh.host || 'localhost'}">
                </div>
                <div class="form-group">
                    <label class="form-label">Порт</label>
                    <input type="number" class="form-input" id="ssh-port" value="${ssh.port || 22}">
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Имя пользователя</label>
                <input type="text" class="form-input" id="ssh-username" value="${ssh.username || ''}">
            </div>
            <div id="ssh-pass-block" style="display:${ssh.auth_type === 'password' ? 'block' : 'none'}">
                <div class="form-group">
                    <label class="form-label">Пароль</label>
                    <input type="password" class="form-input" id="ssh-password" value="" placeholder="${ssh.password === '***' ? 'Сохранён' : ''}">
                </div>
            </div>
            <div id="ssh-key-block" style="display:${ssh.auth_type === 'key' ? 'block' : 'none'}">
                <div class="form-group">
                    <label class="form-label">Путь к SSH ключу</label>
                    <input type="text" class="form-input" id="ssh-key-path" value="${ssh.key_path || ''}" placeholder="/home/user/.ssh/id_rsa">
                </div>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="Pages.saveSSH()">Сохранить</button>
                <button class="btn btn-ghost" onclick="Pages.testSSH()">Тест подключения</button>
            </div>
            <div id="ssh-test-result" style="margin-top:12px"></div>
        </div>`;
    } catch(e) { Toast.error(e.message); }
};

Pages.saveSSH = async function() {
    try {
        const data = {
            enabled: document.getElementById('ssh-enabled').checked,
            host: document.getElementById('ssh-host').value,
            port: parseInt(document.getElementById('ssh-port').value),
            username: document.getElementById('ssh-username').value,
            auth_type: document.getElementById('ssh-auth-type').value,
            key_path: document.getElementById('ssh-key-path')?.value || '',
        };
        const pass = document.getElementById('ssh-password')?.value;
        if (pass) data.password = pass;
        await API.put('/api/config/ssh', data);
        Toast.success('SSH настройки сохранены');
    } catch(e) { Toast.error(e.message); }
};

Pages.testSSH = async function() {
    const el = document.getElementById('ssh-test-result');
    el.innerHTML = '<div class="spinner" style="margin:8px 0"></div>';
    try {
        const result = await API.post('/api/config/ssh/test', {
            host: document.getElementById('ssh-host').value,
            port: parseInt(document.getElementById('ssh-port').value),
            username: document.getElementById('ssh-username').value,
            password: document.getElementById('ssh-password')?.value || undefined,
            key_path: document.getElementById('ssh-key-path')?.value || undefined,
        });
        if (result.success) {
            el.innerHTML = '<div class="notification-banner info">Подключение успешно!</div>';
        } else {
            el.innerHTML = `<div class="notification-banner error">${result.error}</div>`;
        }
    } catch(e) {
        el.innerHTML = `<div class="notification-banner error">${e.message}</div>`;
    }
};

Pages.settingsBackup = async function() {
    try {
        const { config } = await API.get('/api/config');
        const backup = config.backup || {};
        const sftp = backup.sftp || {};
        const schedule = backup.schedule || {};
        const { backups } = await API.get('/api/backups');

        document.getElementById('settings-content').innerHTML = `
        <div class="card fade-in">
            <div class="card-header"><h3 class="card-title">Настройки бекапов</h3></div>
            <div class="form-group">
                <label class="form-label">Путь для бекапов</label>
                <input type="text" class="form-input" id="bk-path" value="${backup.path || ''}" placeholder="data/backups">
            </div>
            <div style="border-top:1px solid var(--border);padding-top:16px;margin-top:16px">
                <h4 style="margin-bottom:12px">Расписание автобекапов</h4>
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
                    <label class="form-label" style="margin:0">Включить</label>
                    <label class="toggle">
                        <input type="checkbox" id="bk-sched-on" ${schedule.enabled ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Интервал (часы)</label>
                        <input type="number" class="form-input" id="bk-sched-hours" value="${schedule.interval_hours || 24}" min="1">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Макс. бекапов на сервер</label>
                        <input type="number" class="form-input" id="bk-sched-max" value="${schedule.max_backups || 10}" min="1">
                    </div>
                </div>
            </div>
            <div style="border-top:1px solid var(--border);padding-top:16px;margin-top:16px">
                <h4 style="margin-bottom:12px">SFTP по умолчанию</h4>
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
                    <label class="form-label" style="margin:0">SFTP выгрузка</label>
                    <label class="toggle">
                        <input type="checkbox" id="bk-sftp-on" ${sftp.enabled ? 'checked' : ''} onchange="document.getElementById('bk-sftp-fields').style.display=this.checked?'block':'none'">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div id="bk-sftp-fields" style="display:${sftp.enabled ? 'block' : 'none'}">
                    <div class="notification-banner warning" style="margin-bottom:12px">
                        <span>!</span>
                        <div>При SFTP-бекапе сервер автоматически остановится (команда <code>stop</code>), после выгрузки запустится заново.</div>
                    </div>
                    <div class="form-row">
                        <div class="form-group"><label class="form-label">Хост</label><input type="text" class="form-input" id="bk-sftp-host" value="${sftp.host || ''}"></div>
                        <div class="form-group"><label class="form-label">Порт</label><input type="number" class="form-input" id="bk-sftp-port" value="${sftp.port || 22}"></div>
                    </div>
                    <div class="form-row">
                        <div class="form-group"><label class="form-label">Пользователь</label><input type="text" class="form-input" id="bk-sftp-user" value="${sftp.username || ''}"></div>
                        <div class="form-group"><label class="form-label">Пароль</label><input type="password" class="form-input" id="bk-sftp-pass" value="" placeholder="${sftp.password ? 'Сохранён' : ''}"></div>
                    </div>
                    <div class="form-group"><label class="form-label">Путь SSH ключа</label><input type="text" class="form-input" id="bk-sftp-key" value="${sftp.key_path || ''}" placeholder="/home/user/.ssh/id_rsa"></div>
                    <div class="form-group"><label class="form-label">Удалённый путь</label><input type="text" class="form-input" id="bk-sftp-remote" value="${sftp.remote_path || '/backups'}"></div>
                </div>
            </div>
            <div style="margin-top:16px">
                <button class="btn btn-primary" onclick="Pages.saveBackupSettings()">Сохранить</button>
            </div>
        </div>
        ${backups.length > 0 ? `
        <div class="card fade-in" style="margin-top:16px">
            <div class="card-header">
                <h3 class="card-title">Существующие бекапы (${backups.length})</h3>
            </div>
            <div class="table-container" style="max-height:300px;overflow-y:auto">
                <table>
                    <thead><tr><th>Файл</th><th>Размер</th><th>Дата</th><th></th></tr></thead>
                    <tbody>
                        ${backups.map(b => {
                            const size = b.size > 1048576 ? (b.size / 1048576).toFixed(1) + ' MB' : (b.size / 1024).toFixed(0) + ' KB';
                            const date = new Date(b.created).toLocaleString();
                            return '<tr><td style="font-size:12px">' + b.filename + '</td><td>' + size + '</td><td>' + date + '</td><td><a href="/api/backups/download/' + b.filename + '" class="btn btn-ghost btn-sm" style="font-size:11px">Скачать</a> <button class="btn btn-ghost btn-sm" style="font-size:11px;color:var(--red)" onclick="Pages.deleteBackupFromSettings(\'' + b.filename + '\')">Удалить</button></td></tr>';
                        }).join('')}
                    </tbody>
                </table>
            </div>
        </div>` : ''}`;
    } catch(e) { Toast.error(e.message); }
};

Pages.saveBackupSettings = async function() {
    try {
        const data = {
            backup: {
                path: document.getElementById('bk-path').value,
                schedule: {
                    enabled: document.getElementById('bk-sched-on').checked,
                    interval_hours: parseInt(document.getElementById('bk-sched-hours').value),
                    max_backups: parseInt(document.getElementById('bk-sched-max').value),
                },
                sftp: {
                    enabled: document.getElementById('bk-sftp-on').checked,
                    host: document.getElementById('bk-sftp-host')?.value || '',
                    port: parseInt(document.getElementById('bk-sftp-port')?.value || 22),
                    username: document.getElementById('bk-sftp-user')?.value || '',
                    key_path: document.getElementById('bk-sftp-key')?.value || '',
                    remote_path: document.getElementById('bk-sftp-remote')?.value || '/backups',
                },
            }
        };
        const pass = document.getElementById('bk-sftp-pass')?.value;
        if (pass) data.backup.sftp.password = pass;
        else data.backup.sftp.password = '***';
        await API.put('/api/config', data);
        Toast.success('Настройки бекапов сохранены');
    } catch(e) { Toast.error(e.message); }
};

Pages.deleteBackupFromSettings = async function(filename) {
    if (!confirm('Удалить этот бекап?')) return;
    try {
        await API.del('/api/backups/' + filename);
        Toast.success('Бекап удалён');
        Pages.settingsBackup();
    } catch(e) { Toast.error(e.message); }
};

Pages['system-terminal'] = async function() {
    const content = document.getElementById('content');
    content.innerHTML = `
    <div class="fade-in">
        <div class="page-header">
            <h1 class="page-title">Системный терминал</h1>
            <div class="btn-group">
                <span class="badge badge-gray" id="sys-term-status"><span class="badge-dot"></span>Отключён</span>
                <button class="btn btn-primary btn-sm" id="sys-term-connect-btn" onclick="SystemTerminal.connect()">Подключить</button>
                <button class="btn btn-danger btn-sm" style="display:none" id="sys-term-disconnect-btn" onclick="SystemTerminal.disconnect()">Отключить</button>
            </div>
        </div>
        <div id="sys-term-container" style="height:calc(100vh - 120px);background:#000;border-radius:var(--radius);overflow:hidden;border:1px solid var(--border)"></div>
    </div>`;
};

const SystemTerminal = {
    ws: null,
    term: null,
    fitAddon: null,

    connect() {
        if (this.ws) this.disconnect();

        const container = document.getElementById('sys-term-container');
        if (!container) return;

        if (typeof Terminal === 'undefined' || !window.Terminal) {
            Toast.error('xterm.js не загружен. Проверьте подключение к интернету.');
            return;
        }

        this.term = new window.Terminal({
            theme: {
                background: '#0a0a0f',
                foreground: '#e2e8f0',
                cursor: '#7c3aed',
                cursorAccent: '#0a0a0f',
                selectionBackground: 'rgba(124, 58, 237, 0.3)',
                black: '#1a1a2e',
                red: '#ef4444',
                green: '#22c55e',
                yellow: '#eab308',
                blue: '#3b82f6',
                magenta: '#a78bfa',
                cyan: '#67e8f9',
                white: '#e2e8f0',
            },
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 14,
            cursorBlink: true,
            allowProposedApi: true,
        });

        if (window.FitAddon) {
            this.fitAddon = new window.FitAddon.FitAddon();
            this.term.loadAddon(this.fitAddon);
        }

        this.term.open(container);
        if (this.fitAddon) this.fitAddon.fit();

        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}/ws/system-terminal?token=${API.token}`);

        this.ws.onopen = () => {
            document.getElementById('sys-term-status').className = 'badge badge-green';
            document.getElementById('sys-term-status').innerHTML = '<span class="badge-dot"></span>Подключён';
            document.getElementById('sys-term-connect-btn').style.display = 'none';
            document.getElementById('sys-term-disconnect-btn').style.display = '';
            if (this.fitAddon) {
                const dims = this.fitAddon.proposeDimensions();
                if (dims) this.ws.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
            }
        };

        this.ws.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            if (msg.type === 'output') {
                this.term.write(msg.data);
            } else if (msg.type === 'connected') {
                this.term.write('\r\n\x1b[32m' + msg.message + '\x1b[0m\r\n');
            } else if (msg.type === 'error') {
                this.term.write('\r\n\x1b[31m' + msg.message + '\x1b[0m\r\n');
                Toast.error(msg.message);
            }
        };

        this.ws.onclose = () => {
            document.getElementById('sys-term-status').className = 'badge badge-gray';
            document.getElementById('sys-term-status').innerHTML = '<span class="badge-dot"></span>Отключён';
            document.getElementById('sys-term-connect-btn').style.display = '';
            document.getElementById('sys-term-disconnect-btn').style.display = 'none';
            this.term?.write('\r\n\x1b[33mСоединение закрыто\x1b[0m\r\n');
        };

        this.ws.onerror = () => Toast.error('Ошибка WebSocket');

        this.term.onData((data) => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'input', data }));
            }
        });

        this.term.onResize(({ cols, rows }) => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'resize', cols, rows }));
            }
        });

        window.addEventListener('resize', () => {
            if (this.fitAddon) this.fitAddon.fit();
        });
    },

    disconnect() {
        if (this.ws) { this.ws.close(); this.ws = null; }
        if (this.term) { this.term.dispose(); this.term = null; }
        this.fitAddon = null;
    }
};

const JavaInstaller = {
    show(javaCheck, onRetry) {
        const inst = javaCheck.install_instructions;
        const spigot = javaCheck.spigot_build;
        const reqText = javaCheck.required_version_text || `Java ${javaCheck.required_version}+`;

        let commandsHtml = inst.commands.map(c =>
            `<div style="background:var(--bg-input);padding:8px 12px;border-radius:6px;margin:4px 0;font-family:'JetBrains Mono';font-size:12px;word-break:break-all">${c}</div>`
        ).join('');

        let linksHtml = inst.links.map(l =>
            `<a href="${l}" target="_blank" style="color:var(--accent-light);font-size:13px;display:block;margin:4px 0">${l}</a>`
        ).join('');

        Modal.show(`Java не найдена`, `
            <div class="notification-banner error">
                <span>!</span>
                <div>Требуется <strong>${reqText}</strong> для этого сервера</div>
            </div>
            ${spigot && !spigot.available ? `
                <div class="notification-banner warning" style="margin-top:8px">
                    <span>!</span>
                    <div>Spigot BuildTools требует Java <strong>${spigot.min_java}-${spigot.max_java}</strong></div>
                </div>` : ''}
            <div style="margin-top:16px">
                <h4 style="margin-bottom:8px">Установленные версии Java:</h4>
                ${javaCheck.installations?.length > 0 ? javaCheck.installations.map(j =>
                    `<div style="font-size:13px;padding:4px 0;color:var(--text-secondary)">Java ${j.major_version} — ${j.path}</div>`
                ).join('') : '<div style="color:var(--text-muted);font-size:13px">Java не найдена</div>'}
            </div>
            <div style="margin-top:16px">
                <h4 style="margin-bottom:8px">Команды для установки:</h4>
                ${commandsHtml}
            </div>
            <div style="margin-top:12px">
                <h4 style="margin-bottom:4px">Ссылки для скачивания:</h4>
                ${linksHtml}
            </div>
            ${inst.auto_available ? `
                <div style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">
                    <button class="btn btn-primary" onclick="JavaInstaller.autoInstall(${javaCheck.required_version})" id="java-auto-btn">
                        Установить автоматически (Java ${javaCheck.required_version})
                    </button>
                    <div id="java-install-progress" style="display:none;margin-top:12px">
                        <div class="progress-bar"><div class="progress-fill" id="java-install-fill" style="width:0%"></div></div>
                        <div class="progress-info">
                            <span id="java-install-status">Подготовка...</span>
                            <span class="progress-percent" id="java-install-percent">0%</span>
                        </div>
                    </div>
                </div>` : ''}
            <div style="margin-top:12px">
                <button class="btn btn-ghost" onclick="Modal.close()">Отмена</button>
                <button class="btn btn-ghost" onclick="Modal.close();${onRetry ? onRetry.name + '()' : ''}">Продолжить всё равно</button>
            </div>
        `, null, '640px');

        this._onRetry = onRetry;
    },

    async autoInstall(version) {
        const btn = document.getElementById('java-auto-btn');
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Установка...';
        document.getElementById('java-install-progress').style.display = 'block';

        try {
            const { task_id } = await API.post('/api/servers/java/install', { required_version: version });
            this._pollInstall(task_id);
        } catch(e) {
            Toast.error(e.message);
            btn.disabled = false;
            btn.textContent = `Установить автоматически (Java ${version})`;
        }
    },

    async _pollInstall(taskId) {
        try {
            const p = await API.get(`/api/servers/java/install-progress/${taskId}`);
            const fill = document.getElementById('java-install-fill');
            const status = document.getElementById('java-install-status');
            const percent = document.getElementById('java-install-percent');

            if (fill) fill.style.width = p.percent + '%';
            if (percent) percent.textContent = p.percent + '%';
            if (status) status.textContent = p.message || p.status;

            if (p.status === 'completed') {
                if (fill) { fill.style.width = '100%'; fill.classList.add('done'); }
                Toast.success('Java установлена!');
                setTimeout(() => {
                    Modal.close();
                    if (this._onRetry) this._onRetry();
                }, 1500);
            } else if (p.status === 'error') {
                Toast.error(p.error);
                const btn = document.getElementById('java-auto-btn');
                if (btn) { btn.disabled = false; btn.textContent = 'Повторить'; }
            } else {
                setTimeout(() => this._pollInstall(taskId), 1000);
            }
        } catch(e) {
            setTimeout(() => this._pollInstall(taskId), 2000);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
