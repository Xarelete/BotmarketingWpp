/* =============================================================================
   BotRemarketingIMOB — SPA App & Simulador WhatsApp (Vanilla JS)
   ============================================================================= */

// Estado global da aplicação
let allLeadsCache = [];
let selectedLeadIds = new Set();
let broadcastPollingInterval = null;
let currentUploadedImageUrl = null;
let poolsCache = [];

// ═══════════════════════════════════════════
// FORMATAÇÃO E MÁSCARA DE TELEFONE
// ═══════════════════════════════════════════

function formatPhoneDisplay(raw) {
    if (!raw) return '—';
    const digits = String(raw).replace(/\D/g, '');
    if (digits.startsWith('55') && digits.length === 13) {
        return `+55 (${digits.substring(2, 4)}) ${digits.substring(4, 9)}-${digits.substring(9)}`;
    } else if (digits.startsWith('55') && digits.length === 12) {
        return `+55 (${digits.substring(2, 4)}) ${digits.substring(4, 8)}-${digits.substring(8)}`;
    } else if (digits.length === 11) {
        return `(${digits.substring(0, 2)}) ${digits.substring(2, 7)}-${digits.substring(7)}`;
    } else if (digits.length === 10) {
        return `(${digits.substring(0, 2)}) ${digits.substring(2, 6)}-${digits.substring(6)}`;
    }
    return raw;
}

function applyPhoneMask(input) {
    input.addEventListener('input', (e) => {
        let val = e.target.value.replace(/\D/g, '');
        if (val.length > 13) val = val.substring(0, 13);

        if (val.startsWith('55') && val.length > 2) {
            const ddd = val.substring(2, 4);
            const rest = val.substring(4);
            if (rest.length > 5) {
                e.target.value = `+55 (${ddd}) ${rest.substring(0, 5)}-${rest.substring(5, 9)}`;
            } else if (rest.length > 0) {
                e.target.value = `+55 (${ddd}) ${rest}`;
            } else {
                e.target.value = `+55 (${ddd}`;
            }
        } else if (val.length > 10) {
            e.target.value = `(${val.substring(0, 2)}) ${val.substring(2, 7)}-${val.substring(7, 11)}`;
        } else if (val.length > 6) {
            e.target.value = `(${val.substring(0, 2)}) ${val.substring(2, 6)}-${val.substring(6, 10)}`;
        } else if (val.length > 2) {
            e.target.value = `(${val.substring(0, 2)}) ${val.substring(2)}`;
        } else if (val.length > 0) {
            e.target.value = `(${val}`;
        }
    });
}

// ═══════════════════════════════════════════
// API HELPERS
// ═══════════════════════════════════════════

async function api(url, options = {}) {
    const defaults = {
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
    };
    const opts = { ...defaults, ...options };
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
        opts.body = JSON.stringify(opts.body);
    }
    if (opts.body instanceof FormData) {
        delete opts.headers['Content-Type'];
    }
    try {
        const resp = await fetch(url, opts);

        if (resp.status === 401) {
            showLogin();
            throw new Error('Sessão expirada. Por favor, faça login novamente.');
        }

        if (resp.status === 428) {
            let data = {};
            try { data = await resp.json(); } catch { }
            if (data.code === 'no_instance') {
                showInstanceSelection();
            }
            throw new Error(data.error || 'Nenhum número selecionado');
        }

        const contentType = resp.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            if (!resp.ok) {
                if (resp.status === 404) {
                    throw new Error('Servidor precisa ser reiniciado para carregar as novas rotas. Reinicie o python main.py no terminal.');
                }
                throw new Error(`Servidor retornou erro HTTP ${resp.status}. O serviço pode estar reiniciando.`);
            }
            return { ok: true };
        }

        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `Erro ${resp.status}`);
        return data;
    } catch (err) {
        throw err;
    }
}

// ═══════════════════════════════════════════
// TOAST & MODAL
// ═══════════════════════════════════════════

function toast(message, type = 'info') {
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const container = document.getElementById('toast-container');
    if (!container) return;
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `
        <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
        <div class="toast-body">
            <div class="toast-title">${type === 'success' ? 'Sucesso' : type === 'error' ? 'Erro' : type === 'warning' ? 'Atenção' : 'Info'}</div>
            <div class="toast-msg">${message}</div>
        </div>
    `;
    container.appendChild(t);
    setTimeout(() => {
        t.classList.add('fade-out');
        setTimeout(() => t.remove(), 350);
    }, 3500);
}

function openModal(title, bodyHTML) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = bodyHTML;
    document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
}

// ═══════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════

async function checkAuth() {
    try {
        const data = await api('/api/session');
        if (data.authenticated && data.instance) {
            setActiveInstanceBadge(data.instance);
            showApp();
        } else if (data.authenticated) {
            // Admin logado globalmente, sem número selecionado (fallback)
            setActiveInstanceBadge('');
            showApp();
        } else {
            showInstanceSelection();
        }
    } catch { showInstanceSelection(); }
}

function setActiveInstanceBadge(instanceName) {
    const badge = document.getElementById('active-instance-badge');
    if (badge) {
        badge.textContent = instanceName ? `📱 ${instanceName}` : '👤 Admin';
    }
    // Sync topbar
    syncTopbarInstance(instanceName);
}

function showLogin() {
    document.getElementById('instance-screen').classList.add('hidden');
    document.getElementById('app').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
}

function showInstanceSelection() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app').classList.add('hidden');
    document.getElementById('instance-screen').classList.remove('hidden');
    loadAvailableInstances();
}

function showApp() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('instance-screen').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    initSidebar();
    updateBreadcrumb('dashboard');
    loadDashboard();
    checkActiveBroadcast();
    checkWhatsAppStatus();
}

// ═══════════════════════════════════════════
// SELEÇÃO / LOGIN POR NÚMERO (INSTÂNCIA)
// ═══════════════════════════════════════════

async function loadAvailableInstances() {
    const list = document.getElementById('instance-list');
    if (!list) return;
    list.innerHTML = '<div style="text-align:center;padding:1.5rem;color:var(--text-muted)">Carregando números...</div>';

    try {
        const data = await api('/api/instances/available');
        const instances = data.instances || [];

        if (instances.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:1.5rem;color:var(--text-muted)">Nenhum número disponível no momento.</div>';
            return;
        }

        list.innerHTML = instances.map(inst => {
            const online = inst.status === 'open' || inst.status === 'connected';
            const dotClass = online ? 'instance-dot online' : 'instance-dot offline';
            const statusLabel = online ? 'Online' : 'Offline';
            const name = inst.display_name || inst.profile_name || inst.name;
            const phone = inst.phone_formatted ? `<div class="instance-phone">${inst.phone_formatted}</div>` : '';
            const profile = inst.profile_name && inst.profile_name !== name ? `<div class="instance-profile">${inst.profile_name}</div>` : '';
            const offlineNote = !online ? '<span class="instance-offline-note">offline — login ainda possível</span>' : '';
            const escapedName = (inst.name || '').replace(/'/g, "\\'");
            const escapedDisplayName = (name || '').replace(/'/g, "\\'");
            return `
                <div class="instance-card" onclick="promptInstancePassword('${escapedName}', '${escapedDisplayName}')">
                    <span class="${dotClass}" title="${statusLabel}"></span>
                    <div class="instance-info">
                        <div class="instance-name">${name}</div>
                        ${phone}
                        ${profile}
                        ${offlineNote}
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        list.innerHTML = `<div style="text-align:center;padding:1.5rem;color:var(--danger)">Erro ao carregar números: ${err.message}</div>`;
    }
}

function promptInstancePassword(instanceName, displayName) {
    openModal(`📱 Acessar: ${displayName}`, `
        <div class="form-group">
            <label style="display:block;margin-bottom:0.4rem;font-weight:600">Senha deste número</label>
            <input type="password" id="instance-password-input" value="admin" placeholder="Digite a senha (padrão: admin)" autocomplete="current-password" style="width:100%;padding:0.75rem 1rem">
            <small style="color:var(--text-muted);font-size:0.75rem;margin-top:0.35rem;display:block">Senha inicial padrão: <code style="color:var(--accent)">admin</code></small>
        </div>
        <div id="instance-login-error" style="color:var(--danger);font-size:0.82rem;margin-top:0.35rem;min-height:1.2rem"></div>
        <button type="button" class="btn btn-primary btn-full mt-2" onclick="submitInstanceLogin('${instanceName.replace(/'/g, "\\'")}')">Entrar no Painel</button>
    `);
    setTimeout(() => {
        const input = document.getElementById('instance-password-input');
        if (input) {
            input.focus();
            input.select();
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') submitInstanceLogin(instanceName);
            });
        }
    }, 100);
}

function submitInstanceLogin(instanceName) {
    const input = document.getElementById('instance-password-input');
    const password = input ? input.value : '';
    loginInstance(instanceName, password);
}

async function loginInstance(instanceName, password) {
    try {
        const data = await api('/api/instance/login', {
            method: 'POST',
            body: { instance: instanceName, password }
        });
        toast(`Número ${data.instance || instanceName} conectado com sucesso!`, 'success');
        setActiveInstanceBadge(data.instance || instanceName);
        closeModal();
        showApp();
    } catch (err) {
        const errEl = document.getElementById('instance-login-error');
        if (errEl) errEl.textContent = err.message || 'Senha incorreta para este número';
        toast(err.message || 'Senha incorreta para este número', 'error');
    }
}

function switchInstance() {
    showInstanceSelection();
}

let wppStatusInterval = null;

async function checkWhatsAppStatus() {
    try {
        const data = await api('/api/whatsapp/status');
        const dot = document.getElementById('wpp-status-dot');
        const label = document.getElementById('wpp-status-label');
        const pill = document.getElementById('wpp-connection-pill');
        const wppLabel = data.message && data.message.includes('Render') ? 'Render Offline (503)' : (data.connected ? 'WhatsApp Conectado' : 'WhatsApp Desconectado');
        if (data.connected) {
            if (dot) dot.style.background = 'var(--success)';
            if (label) label.textContent = 'WhatsApp Conectado';
            if (pill) {
                pill.style.borderColor = 'rgba(34, 197, 94, 0.4)';
                pill.title = data.message || 'Instância ativa e conectada';
            }
        } else {
            if (dot) dot.style.background = 'var(--danger)';
            if (label) label.textContent = wppLabel;
            if (pill) {
                pill.style.borderColor = 'rgba(239, 68, 68, 0.4)';
                pill.title = data.message || 'Instância desconectada ou serviço offline';
            }
        }
        // Sync topbar
        syncTopbarWpp(data.connected, data.connected ? 'Conectado' : 'Desconectado');
    } catch { }

    if (!wppStatusInterval) {
        wppStatusInterval = setInterval(checkWhatsAppStatus, 10000);
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const pw = document.getElementById('login-password').value;
    try {
        await api('/api/auth/login', { method: 'POST', body: { password: pw } });
        setActiveInstanceBadge('');
        showApp();
    } catch (err) {
        document.getElementById('login-error').textContent = 'Senha incorreta';
    }
    return false;
}

async function handleLogout() {
    await api('/api/auth/logout', { method: 'POST' });
    setActiveInstanceBadge('');
    showInstanceSelection();
}

// ═══════════════════════════════════════════
// SIDEBAR TOGGLE & PERSISTENCE
// ═══════════════════════════════════════════

const SIDEBAR_KEY = 'imob_sidebar_collapsed';

function isMobile() {
    return window.innerWidth <= 768;
}

function initSidebar() {
    const app = document.getElementById('app');
    if (!app) return;
    if (isMobile()) return; // mobile: always starts closed
    const saved = localStorage.getItem(SIDEBAR_KEY);
    if (saved === 'true') {
        app.classList.add('sidebar-collapsed');
    }
}

function toggleSidebar() {
    const app = document.getElementById('app');
    if (!app) return;
    if (isMobile()) {
        // Mobile: toggle overlay mode
        app.classList.toggle('sidebar-mobile-open');
    } else {
        // Desktop: toggle collapsed
        const isCollapsed = app.classList.toggle('sidebar-collapsed');
        localStorage.setItem(SIDEBAR_KEY, isCollapsed ? 'true' : 'false');
    }
}

function closeSidebarMobile() {
    const app = document.getElementById('app');
    if (app) app.classList.remove('sidebar-mobile-open');
}

// Close mobile sidebar on resize to desktop
window.addEventListener('resize', () => {
    if (!isMobile()) {
        const app = document.getElementById('app');
        if (app) app.classList.remove('sidebar-mobile-open');
    }
});

// ═══════════════════════════════════════════
// BREADCRUMB
// ═══════════════════════════════════════════

const PAGE_LABELS = {
    dashboard: 'Dashboard',
    broadcast: 'Disparo Rápido',
    leads: 'Leads',
    pools: 'Bolsões',
    groups: 'Grupos WA',
    segments: 'Segmentos',
    campaigns: 'Campanhas',
    messages: 'Editor D1–D30',
    control: 'Central de Controle',
    log: 'Histórico de Envios',
    settings: 'Configurações',
};

function updateBreadcrumb(page) {
    const el = document.getElementById('breadcrumb-current');
    if (el) el.textContent = PAGE_LABELS[page] || page;
}

// ═══════════════════════════════════════════
// TOPBAR SYNC (instance + wpp status)
// ═══════════════════════════════════════════

function syncTopbarInstance(name) {
    const el = document.getElementById('topbar-instance-badge');
    if (!el) return;
    el.textContent = name ? `📱 ${name}` : '👤 Admin';
}

function syncTopbarWpp(connected, label) {
    const dot = document.getElementById('topbar-wpp-dot');
    const lbl = document.getElementById('topbar-wpp-label');
    if (dot) {
        dot.style.background = connected ? 'var(--success)' : 'var(--danger)';
        if (connected) {
            dot.classList.add('connected');
        } else {
            dot.classList.remove('connected');
        }
    }
    if (lbl) lbl.textContent = label || (connected ? 'Conectado' : 'Desconectado');
}

// ═══════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════

document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const page = item.dataset.page;
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById(`page-${page}`).classList.add('active');

        // Update breadcrumb
        updateBreadcrumb(page);

        // Close mobile sidebar on nav
        if (isMobile()) closeSidebarMobile();

        const loaders = {
            dashboard: loadDashboard,
            broadcast: loadBroadcastPage,
            leads: loadLeads,
            campaigns: loadCampaigns,
            messages: loadMessagesPage,
            control: loadControlPage,
            log: loadDispatchLog,
            pools: loadPools,
            groups: loadGroups,
            segments: loadSegments,
            settings: loadInstanceSettings,
        };
        if (loaders[page]) loaders[page]();
    });
});

// ═══════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════

async function loadDashboard() {
    try {
        const data = await api('/api/dashboard');
        const leads = data.leads || {};
        const engine = data.engine || {};

        document.getElementById('stats-grid').innerHTML = `
            <div class="stat-card" data-color="purple">
                <div class="stat-icon">👥</div>
                <div class="stat-value" data-target="${leads.active || 0}">0</div>
                <div class="stat-label">Leads no Bolsão</div>
            </div>
            <div class="stat-card" data-color="blue">
                <div class="stat-icon">🔄</div>
                <div class="stat-value" data-target="${leads.in_funnel || 0}">0</div>
                <div class="stat-label">Em Remarketing Ativo</div>
            </div>
            <div class="stat-card" data-color="gold">
                <div class="stat-icon">⏸️</div>
                <div class="stat-value" data-target="${leads.paused || 0}">0</div>
                <div class="stat-label">Envios Pausados</div>
            </div>
            <div class="stat-card" data-color="green">
                <div class="stat-icon">🚀</div>
                <div class="stat-value" data-target="${engine.active_campaigns || 0}">0</div>
                <div class="stat-label">Campanhas Ativas</div>
            </div>
            <div class="stat-card" data-color="info">
                <div class="stat-icon">✅</div>
                <div class="stat-value" data-target="${leads.completed || 0}">0</div>
                <div class="stat-label">Completaram Funil</div>
            </div>
            <div class="stat-card" data-color="danger">
                <div class="stat-icon">🏆</div>
                <div class="stat-value" data-target="${leads.converted || 0}">0</div>
                <div class="stat-label">Leads Convertidos</div>
            </div>
        `;

        // Animate stat counters
        document.querySelectorAll('.stat-value[data-target]').forEach(el => {
            const target = parseInt(el.dataset.target) || 0;
            if (target === 0) { el.textContent = '0'; return; }
            const duration = 800;
            const start = performance.now();
            function step(now) {
                const elapsed = now - start;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
                el.textContent = Math.round(eased * target);
                if (progress < 1) requestAnimationFrame(step);
            }
            requestAnimationFrame(step);
        });

        const paused = engine.engine_paused;
        const statusClass = paused ? 'paused' : 'running';
        const statusText = paused ? '⏸️ Motor PAUSADO' : '▶️ Motor ATIVO';
        document.getElementById('engine-status-panel').innerHTML = `
            <div class="engine-status-indicator ${statusClass}">
                <span class="dot"></span>${statusText}
            </div>
            <div class="text-sm text-muted" style="margin-bottom:0.5rem">Data de operação: ${engine.current_date || 'Hoje'}</div>
            ${(engine.campaigns || []).map(c => `
                <div style="display:flex;justify-content:space-between;align-items:center;padding:0.6rem 0;border-bottom:1px solid var(--border);font-size:0.85rem">
                    <span>📌 <strong>${c.name}</strong></span>
                    <span>Hoje: <strong style="color:var(--accent)">${c.sent_today}</strong>/${c.target_today} | Total: ${c.total_sent}</span>
                </div>
            `).join('')}
        `;

        const log = data.recent_dispatches || [];
        if (log.length === 0) {
            document.getElementById('recent-dispatches').innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">📭 Nenhum envio registrado ainda</div>';
        } else {
            document.getElementById('recent-dispatches').innerHTML = log.map(l => {
                const dotClass = l.status === 'sent' ? 'sent' : l.status === 'failed' ? 'failed' : 'pending';
                return `
                <div class="activity-item">
                    <span class="activity-dot ${dotClass}"></span>
                    <div class="activity-info">
                        <div class="activity-name">${l.lead_name || l.lead_phone}</div>
                        <div class="activity-meta">${l.campaign_id} · D${l.remarketing_day || 0}</div>
                    </div>
                    <span class="activity-time">${formatTime(l.sent_at)}</span>
                </div>
            `}).join('');
        }
    } catch (err) { console.error(err); }
}

// ═══════════════════════════════════════════
// DISPARO RÁPIDO & SIMULADOR WHATSAPP
// ═══════════════════════════════════════════

let availableInstances = [];

async function loadBroadcastPage() {
    const textarea = document.getElementById('bc-message-text');
    if (textarea && !textarea.value.trim()) {
        textarea.value = `Olá {primeiro_nome}, tudo bem?\n\nPassando aqui para te mostrar uma oportunidade exclusiva de imóvel que acabou de entrar no nosso portfólio!\n\nGostaria de receber as fotos e condições? Me avisa aqui!`;
    }
    updateWhatsappPreview();
    await loadWhatsAppInstances();
    await fetchAllLeadsForBroadcast();
    checkActiveBroadcast();
}

async function loadWhatsAppInstances() {
    const select = document.getElementById('bc-instance-select');
    const badge = document.getElementById('instance-badge-status');
    if (!select) return;

    try {
        const data = await api('/api/whatsapp/instances');
        availableInstances = data.instances || [];
        const active = data.active_instance || '';

        if (availableInstances.length === 0) {
            select.innerHTML = `<option value="${active}">${active} (Padrão)</option>`;
            return;
        }

        select.innerHTML = availableInstances.map(inst => {
            const isSelected = inst.name === active || inst.is_active;
            const statusEmoji = inst.status === 'open' ? '🟢 Conectado' : (inst.status === 'connecting' ? '🟡 Conectando' : '🔴 Desconectado');
            const phoneInfo = inst.phone_formatted && inst.phone_formatted !== 'Sem número' ? ` [${inst.phone_formatted}]` : '';
            const profile = inst.profile_name && inst.profile_name !== inst.name ? ` - ${inst.profile_name}` : '';
            return `<option value="${inst.name}" ${isSelected ? 'selected' : ''}>${inst.name}${phoneInfo}${profile} (${statusEmoji})</option>`;
        }).join('');

        updateInstanceBadgeStatus(active);
    } catch (err) {
        console.error('Erro ao carregar instâncias:', err);
    }
}

function updateInstanceBadgeStatus(instanceName) {
    const badge = document.getElementById('instance-badge-status');
    if (!badge) return;
    const inst = availableInstances.find(i => i.name === instanceName);
    if (!inst) {
        badge.className = 'badge badge-active';
        badge.textContent = 'Ativo';
        return;
    }

    if (inst.status === 'open') {
        badge.className = 'badge badge-active';
        badge.textContent = '🟢 Online';
    } else if (inst.status === 'connecting') {
        badge.className = 'badge badge-paused';
        badge.textContent = '🟡 Conectando';
    } else {
        badge.className = 'badge badge-inactive';
        badge.textContent = '🔴 Desconectado';
    }
}

async function handleInstanceChange(instanceName) {
    if (!instanceName) return;
    updateInstanceBadgeStatus(instanceName);
    try {
        const res = await api('/api/whatsapp/select-instance', {
            method: 'POST',
            body: { instance: instanceName }
        });
        toast(`Número remetente alterado para: ${instanceName}`, 'success');
        checkWhatsAppStatus();
    } catch (err) {
        toast('Erro ao alterar instância: ' + err.message, 'error');
    }
}

async function fetchAllLeadsForBroadcast() {
    try {
        const data = await api('/api/leads?limit=500&status=active');
        allLeadsCache = data.leads || [];

        const tagSet = new Set();
        allLeadsCache.forEach(l => (l.tags || []).forEach(t => tagSet.add(t)));

        const tagSelect = document.getElementById('bc-lead-tag-filter');
        if (tagSelect) {
            tagSelect.innerHTML = '<option value="">Todas as Tags</option>' +
                Array.from(tagSet).map(t => `<option value="${t}">${t}</option>`).join('');
        }

        renderBroadcastLeadsTable();
    } catch (err) { console.error(err); }
}

function renderBroadcastLeadsTable() {
    const search = (document.getElementById('bc-lead-search')?.value || '').toLowerCase();
    const tagFilter = document.getElementById('bc-lead-tag-filter')?.value || '';

    const filtered = allLeadsCache.filter(l => {
        const nameMatch = (l.name || '').toLowerCase().includes(search);
        const phoneMatch = (l.phone || '').includes(search);
        const tagMatch = !tagFilter || (l.tags || []).includes(tagFilter);
        return (nameMatch || phoneMatch) && tagMatch;
    });

    const container = document.getElementById('bc-leads-table-container');
    if (!container) return;

    if (filtered.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:1.5rem;color:var(--text-muted)">Nenhum lead encontrado com estes filtros</div>';
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th style="width:36px"></th>
                    <th>Nome</th>
                    <th>Telefone</th>
                    <th>Tags</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${filtered.map(l => {
                    const isChecked = selectedLeadIds.has(l.id);
                    return `
                        <tr>
                            <td>
                                <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleLeadSelection('${l.id}', this.checked)">
                            </td>
                            <td><strong>${l.name || 'Sem nome'}</strong></td>
                            <td style="font-family:monospace;font-size:0.85rem;color:var(--accent)">${formatPhoneDisplay(l.phone)}</td>
                            <td>${(l.tags || []).map(t => `<span class="tag">${t}</span>`).join(' ') || '—'}</td>
                            <td>
                                ${l.paused ? '<span class="badge badge-paused">pausado</span>' : '<span class="badge badge-active">ativo</span>'}
                            </td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;

    updateBroadcastSelectedCount();
}

function toggleLeadSelection(leadId, isSelected) {
    if (isSelected) {
        selectedLeadIds.add(leadId);
    } else {
        selectedLeadIds.delete(leadId);
    }
    updateBroadcastSelectedCount();
}

function toggleSelectAllBroadcastLeads(checkbox) {
    const search = (document.getElementById('bc-lead-search')?.value || '').toLowerCase();
    const tagFilter = document.getElementById('bc-lead-tag-filter')?.value || '';

    const visibleLeads = allLeadsCache.filter(l => {
        const nameMatch = (l.name || '').toLowerCase().includes(search);
        const phoneMatch = (l.phone || '').includes(search);
        const tagMatch = !tagFilter || (l.tags || []).includes(tagFilter);
        return (nameMatch || phoneMatch) && tagMatch;
    });

    visibleLeads.forEach(l => {
        if (checkbox.checked) {
            selectedLeadIds.add(l.id);
        } else {
            selectedLeadIds.delete(l.id);
        }
    });

    renderBroadcastLeadsTable();
}

function clearBroadcastSelection() {
    selectedLeadIds.clear();
    const selectAllBox = document.getElementById('bc-select-all');
    if (selectAllBox) selectAllBox.checked = false;
    renderBroadcastLeadsTable();
}

function updateBroadcastSelectedCount() {
    const el = document.getElementById('bc-selected-count');
    if (el) el.textContent = selectedLeadIds.size;
}

function loadDefaultTemplate() {
    const textarea = document.getElementById('bc-message-text');
    if (!textarea) return;
    textarea.value = `Olá {primeiro_nome}, tudo bem?\n\nPassando aqui para te mostrar uma oportunidade exclusiva de imóvel que acabou de entrar no nosso portfólio!\n\nGostaria de receber as fotos e condições? Me avisa aqui!`;
    updateWhatsappPreview();
    toast('Modelo humanizado pronto carregado!', 'success');
}

function insertTag(tag) {
    const textarea = document.getElementById('bc-message-text');
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    textarea.value = text.substring(0, start) + tag + text.substring(end);
    textarea.focus();
    textarea.selectionStart = textarea.selectionEnd = start + tag.length;
    updateWhatsappPreview();
}

function updateWhatsappPreview(customPreview = null) {
    const rawText = document.getElementById('bc-message-text')?.value || '';
    const imageUrl = currentUploadedImageUrl || document.getElementById('bc-image-url')?.value || '';

    let previewText = customPreview;

    if (!previewText) {
        // Se o lead não tem nome, faz saudação fluida sem "João" e sem "amigo(a)"
        previewText = rawText
            .replace(/\{primeiro_nome\}/gi, '')
            .replace(/\{nome\}/gi, '')
            .replace(/\{telefone\}/gi, '+55 (12) 98826-5141')
            .replace(/\{([^{}]+)\}/g, (match, choices) => choices.split('|')[0]);

        // Ajusta espaços e pontuação residual
        previewText = previewText.replace(/(olá|oi|bom dia|boa tarde)\s*,?\s*tudo bem\??/gi, 'Olá, tudo bem?');
        previewText = previewText.replace(/\s+([,!?.])/g, '$1');

        if (!previewText.trim()) {
            previewText = 'Olá, tudo bem?\n\nPassando aqui para te mostrar uma oportunidade exclusiva de imóvel que acabou de entrar no nosso portfólio!\n\nGostaria de receber as fotos e condições? Me avisa aqui!';
        }
    }

    const previewContainer = document.getElementById('preview-message-text');
    if (previewContainer) previewContainer.textContent = previewText;

    const imgContainer = document.getElementById('preview-img-container');
    const imgTag = document.getElementById('preview-img-tag');
    if (imageUrl) {
        imgTag.src = imageUrl;
        imgContainer.classList.remove('hidden');
    } else {
        imgContainer.classList.add('hidden');
    }

    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const timeEl = document.getElementById('preview-time');
    if (timeEl) timeEl.textContent = timeStr;
}

async function generateRandomPreview() {
    const text = document.getElementById('bc-message-text')?.value.trim();
    if (!text) {
        toast('Digite uma mensagem primeiro.', 'info');
        return;
    }

    const varySynonyms = document.getElementById('bc-vary-synonyms')?.checked ?? true;
    const varyText = document.getElementById('bc-vary-text')?.checked ?? true;

    try {
        const resp = await api('/api/broadcast/preview', {
            method: 'POST',
            body: {
                message_template: text,
                vary_synonyms: varySynonyms,
                vary_text: varyText,
            }
        });

        if (resp.preview) {
            updateWhatsappPreview(resp.preview);
            
            // Efeito visual de atualização na bolha
            const bubble = document.getElementById('whatsapp-bubble');
            if (bubble) {
                bubble.classList.remove('bubble-highlight');
                void bubble.offsetWidth; // trigger reflow
                bubble.classList.add('bubble-highlight');
            }
            toast('Nova variação gerada para simulação!', 'info');
        }
    } catch (err) {
        toast('Erro ao gerar prévia: ' + err.message, 'error');
    }
}

async function handleImageSelected(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Preview imediato local via FileReader (só visual)
    const reader = new FileReader();
    reader.onload = (event) => {
        currentUploadedImageUrl = event.target.result;
        updateWhatsappPreview();
    };
    reader.readAsDataURL(file);

    const formData = new FormData();
    formData.append('image', file);

    try {
        toast('Fazendo upload da imagem...', 'info');
        const data = await api('/api/upload/image', { method: 'POST', body: formData });
        
        // Agora armazenamos a URL PÚBLICA que a API retornou
        currentUploadedImageUrl = data.image_url; 
        
        const badge = document.getElementById('bc-image-preview-badge');
        if (badge) badge.classList.remove('hidden');
        
        updateWhatsappPreview();
        toast('Imagem carregada com sucesso!', 'success');
    } catch (err) {
        toast(err.message, 'error');
    }
}

function clearSelectedImage() {
    currentUploadedImageUrl = null;
    const fileInput = document.getElementById('bc-image-file');
    if (fileInput) fileInput.value = '';
    const urlInput = document.getElementById('bc-image-url');
    if (urlInput) urlInput.value = '';
    const badge = document.getElementById('bc-image-preview-badge');
    if (badge) badge.classList.add('hidden');
    updateWhatsappPreview();
}

async function confirmAndStartBroadcast() {
    const text = document.getElementById('bc-message-text')?.value.trim();
    if (!text) {
        toast('Digite a mensagem antes de disparar.', 'error');
        return;
    }

    if (selectedLeadIds.size === 0) {
        toast('Selecione pelo menos 1 lead para enviar.', 'error');
        return;
    }

    const minDelay = parseInt(document.getElementById('bc-min-delay')?.value || 15);
    const maxDelay = parseInt(document.getElementById('bc-max-delay')?.value || 40);
    const varyText = document.getElementById('bc-vary-text')?.checked ?? true;
    const varySynonyms = document.getElementById('bc-vary-synonyms')?.checked ?? true;
    const imageUrl = currentUploadedImageUrl || document.getElementById('bc-image-url')?.value.trim() || null;

    if (!confirm(`🚀 Iniciar disparo em massa para ${selectedLeadIds.size} leads selecionados com intervalos entre ${minDelay}s e ${maxDelay}s?`)) {
        return;
    }

    try {
        const resp = await api('/api/broadcast2/start', {
            method: 'POST',
            body: {
                kind: 'leads',
                lead_ids: Array.from(selectedLeadIds),
                message_template: text,
                image_url: imageUrl,
                min_delay: minDelay,
                max_delay: maxDelay,
                vary_text: varyText,
                vary_synonyms: varySynonyms,
            }
        });

        toast(`Disparo iniciado para ${resp.total} leads!`, 'success');
        startBroadcastPolling();
    } catch (err) {
        toast(err.message, 'error');
    }
}

function startBroadcastPolling() {
    const container = document.getElementById('broadcast-progress-container');
    if (container) container.classList.remove('hidden');

    if (broadcastPollingInterval) clearInterval(broadcastPollingInterval);

    broadcastPollingInterval = setInterval(async () => {
        try {
            const status = await api('/api/broadcast2/status');
            updateBroadcastProgressUI(status);

            if (!status.is_running) {
                clearInterval(broadcastPollingInterval);
                broadcastPollingInterval = null;
                toast('Fila de disparo finalizada!', 'success');
            }
        } catch (err) {
            console.error('Erro ao consultar status da fila:', err);
        }
    }, 1200);
}

function updateBroadcastProgressUI(status) {
    const container = document.getElementById('broadcast-progress-container');
    if (!container) return;

    if (!status.is_running && status.total === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');

    const total = status.total || 1;
    const current = status.current || 0;
    const percent = Math.min(100, Math.round((current / total) * 100));

    document.getElementById('broadcast-progress-bar').style.width = `${percent}%`;
    document.getElementById('prog-current').textContent = current;
    document.getElementById('prog-total').textContent = total;
    document.getElementById('prog-success').textContent = status.success || 0;
    document.getElementById('prog-failed').textContent = status.failed || 0;
    document.getElementById('prog-countdown').textContent = `${status.next_send_in_seconds || 0}s`;

    const titleEl = document.getElementById('broadcast-progress-title');
    const subtitleEl = document.getElementById('broadcast-progress-subtitle');

    if (status.is_running) {
        titleEl.textContent = `🚀 Enviando para: ${status.current_lead_name || '...'} (${percent}%)`;
        subtitleEl.textContent = `Número: ${status.current_lead_phone || ''} | Fila em andamento com pausas naturais...`;
    } else {
        titleEl.textContent = `🏁 Disparo Finalizado (${status.success} enviados com sucesso, ${status.failed} falhas)`;
        subtitleEl.textContent = `Todos os ${total} contatos foram processados.`;
    }
}

async function checkActiveBroadcast() {
    try {
        const status = await api('/api/broadcast2/status');
        if (status.is_running) {
            startBroadcastPolling();
        }
    } catch { }
}

async function cancelActiveBroadcast() {
    if (!confirm('Deseja realmente interromper a fila de envios?')) return;
    try {
        await api('/api/broadcast2/cancel', { method: 'POST' });
        toast('Solicitação de cancelamento enviada!', 'info');
    } catch (err) {
        toast(err.message, 'error');
    }
}

// ═══════════════════════════════════════════
// LEADS (CRUD)
// ═══════════════════════════════════════════

let leadsSearchTimer;
function debounceLeadSearch() {
    clearTimeout(leadsSearchTimer);
    leadsSearchTimer = setTimeout(loadLeads, 400);
}

async function loadLeads() {
    try {
        const search = document.getElementById('leads-search')?.value || '';
        const status = document.getElementById('leads-status-filter')?.value || '';
        const params = new URLSearchParams();
        if (search) params.set('search', search);
        if (status) params.set('status', status);
        params.set('limit', '200');

        const data = await api(`/api/leads?${params}`);
        const leads = data.leads || [];

        if (leads.length === 0) {
            document.getElementById('leads-table-container').innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">📭 Nenhum lead encontrado</div>';
            return;
        }

        document.getElementById('leads-table-container').innerHTML = `
            <div class="table-responsive"><table>
                <thead>
                    <tr><th>Nome</th><th>Telefone</th><th>Tags</th><th>Funil</th><th>Status</th><th>Ações</th></tr>
                </thead>
                <tbody>
                    ${leads.map(l => `
                        <tr>
                            <td><strong>${l.name || 'Sem nome'}</strong></td>
                            <td style="font-family:monospace;font-size:0.85rem;color:var(--accent)">${formatPhoneDisplay(l.phone)}</td>
                            <td>${(l.tags || []).map(t => `<span class="tag">${t}</span>`).join(' ') || '—'}</td>
                            <td>D${l.remarketing_day || 0}${l.next_send_date ? ` → ${l.next_send_date}` : ''}</td>
                            <td>
                                <span class="badge badge-${l.status}">${l.status}</span>
                                ${l.paused ? '<span class="badge badge-paused">pausado</span>' : ''}
                            </td>
                            <td>
                                <div style="display:flex;gap:0.35rem">
                                    <button class="btn btn-secondary btn-xs" title="Enviar Mensagem de Teste no WhatsApp" onclick="testLeadMessageModal('${l.id}', '${l.name || ''}', '${l.phone}')">💬 Testar</button>
                                    ${l.paused
                                        ? `<button class="btn btn-success btn-xs" title="Retomar Envios" onclick="resumeLead('${l.id}')">▶️</button>`
                                        : `<button class="btn btn-secondary btn-xs" title="Pausar Envios" onclick="pauseLead('${l.id}')">⏸️</button>`
                                    }
                                    <button class="btn btn-secondary btn-xs" title="Editar Lead" onclick="editLeadModal('${l.id}')">✏️</button>
                                    <button class="btn btn-danger btn-xs" title="Remover Lead" onclick="deleteLead('${l.id}')">🗑️</button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table></div>
            <div class="text-muted text-sm" style="margin-top:0.75rem">
                Mostrando ${leads.length} leads de ${data.total} cadastrados
            </div>
        `;
    } catch (err) { console.error(err); }
}

function showAddLeadModal() {
    openModal('Adicionar Novo Lead', `
        <form onsubmit="return addLead(event)">
            <div class="form-row">
                <div class="form-group">
                    <label>Telefone *</label>
                    <input type="text" id="add-phone" placeholder="(12) 99988-7766" required>
                </div>
                <div class="form-group">
                    <label>Nome do Cliente</label>
                    <input type="text" id="add-name" placeholder="Ex: Roberto Carlos">
                </div>
            </div>
            <div class="form-group">
                <label>Tags de Interesse (separadas por vírgula)</label>
                <input type="text" id="add-tags" placeholder="luxo, 3quartos, zona-sul">
            </div>
            <div class="form-group">
                <label>Observações / Perfil</label>
                <textarea id="add-notes" rows="3" placeholder="Interessado em cobertura com vista para o mar..."></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Salvar Lead no Bolsão</button>
        </form>
    `);

    setTimeout(() => {
        const phoneInput = document.getElementById('add-phone');
        if (phoneInput) applyPhoneMask(phoneInput);
    }, 100);
}

async function addLead(e) {
    e.preventDefault();
    try {
        await api('/api/leads', {
            method: 'POST',
            body: {
                phone: document.getElementById('add-phone').value,
                name: document.getElementById('add-name').value,
                tags: document.getElementById('add-tags').value,
                notes: document.getElementById('add-notes').value,
            }
        });
        toast('Lead adicionado com sucesso!', 'success');
        closeModal();
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
    return false;
}

async function pauseLead(id) {
    try {
        await api(`/api/leads/${id}/pause`, { method: 'POST', body: {} });
        toast('Envios pausados para este lead', 'info');
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
}

async function resumeLead(id) {
    try {
        await api(`/api/leads/${id}/resume`, { method: 'POST' });
        toast('Envios retomados!', 'success');
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
}

async function deleteLead(id) {
    if (!confirm('Remover este lead permanentemente?')) return;
    try {
        await api(`/api/leads/${id}`, { method: 'DELETE' });
        toast('Lead removido', 'info');
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
}

async function editLeadModal(id) {
    try {
        const data = await api(`/api/leads?search=${id}&limit=1`);
        const lead = (data.leads || []).find(l => l.id === id);
        if (!lead) { toast('Lead não encontrado', 'error'); return; }

        openModal('Editar Lead', `
            <form onsubmit="return updateLead(event, '${id}')">
                <div class="form-group">
                    <label>Nome</label>
                    <input type="text" id="edit-name" value="${lead.name || ''}">
                </div>
                <div class="form-group">
                    <label>Tags</label>
                    <input type="text" id="edit-tags" value="${(lead.tags || []).join(', ')}">
                </div>
                <div class="form-group">
                    <label>Observações</label>
                    <textarea id="edit-notes" rows="3">${lead.notes || ''}</textarea>
                </div>
                <div class="form-group">
                    <label>Status no Funil</label>
                    <select id="edit-status">
                        <option value="active" ${lead.status === 'active' ? 'selected' : ''}>Ativo no Funil</option>
                        <option value="inactive" ${lead.status === 'inactive' ? 'selected' : ''}>Inativo</option>
                        <option value="converted" ${lead.status === 'converted' ? 'selected' : ''}>Convertido / Comprou</option>
                    </select>
                </div>
                <div style="display:flex;gap:0.5rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Salvar Alterações</button>
                    <button type="button" class="btn btn-secondary" onclick="resetFunnel('${id}')" style="flex:1">🔄 Reiniciar Funil (D1)</button>
                </div>
            </form>
        `);
    } catch (err) { toast(err.message, 'error'); }
}

async function updateLead(e, id) {
    e.preventDefault();
    try {
        await api(`/api/leads/${id}`, {
            method: 'PUT',
            body: {
                name: document.getElementById('edit-name').value,
                tags: document.getElementById('edit-tags').value,
                notes: document.getElementById('edit-notes').value,
                status: document.getElementById('edit-status').value,
            }
        });
        toast('Lead atualizado!', 'success');
        closeModal();
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
    return false;
}

async function resetFunnel(id) {
    try {
        await api(`/api/leads/${id}/reset-funnel`, { method: 'POST' });
        toast('Funil do lead reiniciado para D1!', 'success');
        closeModal();
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
}

function testLeadMessageModal(id, name, phone) {
    const displayName = name || 'Lead';
    const formattedPhone = formatPhoneDisplay(phone);
    const firstName = name ? name.split(' ')[0] : 'amigo(a)';
    const defaultText = `🤖 Olá ${firstName}, este é um teste de conexão do Bot Remarketing IMOB!`;

    openModal(`Testar Envio no WhatsApp: ${displayName}`, `
        <form onsubmit="return sendLeadTestMessage(event, '${id}')">
            <div class="form-group">
                <label>Destinatário</label>
                <div style="font-family:monospace;color:var(--accent);font-weight:600;margin-bottom:0.75rem">${displayName} (${formattedPhone})</div>
            </div>
            <div class="form-group">
                <label>Texto da Mensagem de Teste</label>
                <textarea id="lead-test-text" rows="4" required>${defaultText}</textarea>
            </div>
            <button type="submit" id="btn-send-lead-test" class="btn btn-primary btn-full">🚀 Enviar Mensagem Agora</button>
        </form>
    `);
}

async function sendLeadTestMessage(e, id) {
    e.preventDefault();
    const text = document.getElementById('lead-test-text')?.value.trim();
    if (!text) { toast('Digite o texto da mensagem', 'error'); return false; }

    const btn = document.getElementById('btn-send-lead-test');
    if (btn) { btn.disabled = true; btn.textContent = 'Enviando... ⏳'; }

    try {
        toast('Enviando mensagem via WhatsApp...', 'info');
        const res = await api(`/api/leads/${id}/test-message`, {
            method: 'POST',
            body: { text }
        });
        toast(`✅ Mensagem enviada com sucesso para ${formatPhoneDisplay(res.phone)}!`, 'success');
        closeModal();
    } catch (err) {
        toast(`Erro no envio: ${err.message}`, 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🚀 Enviar Mensagem Agora'; }
    }
    return false;
}

async function forceDispatchCampaign(campId, campName) {
    if (!confirm(`⚡ Deseja forçar o envio imediato de 1 mensagem do funil da campanha "${campName}" para o próximo lead elegível?`)) {
        return;
    }

    try {
        toast(`Processando disparo para a campanha "${campName}"...`, 'info');
        const res = await api(`/api/campaigns/${campId}/dispatch-one`, { method: 'POST' });
        toast(`✅ Disparo realizado com sucesso para: ${res.lead_name}`, 'success');
        loadCampaigns();
        loadDashboard();
    } catch (err) {
        toast(err.message, 'error');
    }
}

function showImportModal() {
    openModal('Importar Lista de Leads', `
        <div class="form-group">
            <label>Selecione arquivo CSV ou JSON</label>
            <input type="file" id="import-file" accept=".json,.csv" class="file-input-styled">
        </div>
        <button onclick="importLeads()" class="btn btn-primary btn-full mt-3">📥 Iniciar Importação</button>
        <div class="text-muted text-sm mt-3">
            <strong>Exemplo CSV:</strong> telefone,nome,tags,notas<br>
            <code>5511999887766,Carlos Silva,alto-padrao;investidor,Interessado em Moema</code>
        </div>
    `);
}

async function importLeads() {
    const file = document.getElementById('import-file').files[0];
    if (!file) { toast('Selecione um arquivo primeiro', 'error'); return; }
    const formData = new FormData();
    formData.append('file', file);
    try {
        const data = await api('/api/leads/import', { method: 'POST', body: formData });
        toast(`Importação: ${data.added} adicionados, ${data.skipped} duplicados, ${data.errors} erros`, 'success');
        closeModal();
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
}

// ═══════════════════════════════════════════
// CAMPANHAS & FUNIS
// ═══════════════════════════════════════════

async function loadCampaigns() {
    try {
        const data = await api('/api/campaigns');
        const campaigns = data.campaigns || [];

        if (campaigns.length === 0) {
            document.getElementById('campaigns-list').innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">📭 Nenhuma campanha cadastrada</div>';
            return;
        }

        document.getElementById('campaigns-list').innerHTML = campaigns.map(c => {
            const stats = c.stats || {};
            const isActive = c.status === 'active';
            const funnelDays = c.funnel_days || [1,2,3,5,7,14,30];
            const statusBadge = `<span class="badge badge-${c.status}">${c.status}</span>`;
            const actionButtons = `
                <button class="btn btn-primary btn-xs" title="Disparar para 1 lead elegível agora" onclick="forceDispatchCampaign('${c.id}', '${c.name}')">⚡ Forçar</button>
                ${isActive
                    ? `<button class="btn btn-secondary btn-xs" onclick="pauseCampaign('${c.id}')">⏸️ Pausar</button>`
                    : `<button class="btn btn-success btn-xs" onclick="resumeCampaign('${c.id}')">▶️ Retomar</button>`
                }
                <button class="btn btn-secondary btn-xs" onclick="editCampaignModal('${c.id}')">✏️ Editar</button>
                <button class="btn btn-secondary btn-xs" onclick="bulkEnterPool('${c.id}')">📥 Bolsão</button>
                <button class="btn btn-danger btn-xs" onclick="deleteCampaign('${c.id}')">🗑️</button>
            `;
            const funnelDivs = funnelDays.map(() => `<div class="funnel-day active"></div>`).join('');
            return `
                <div class="campaign-card">
                    <div class="campaign-header">
                        <div>
                            <div class="campaign-name">${c.name}</div>
                            <div class="campaign-meta">
                                <span>Leads: <strong>${stats.total_leads || 0}</strong></span>
                                <span>Enviados: <strong>${stats.total_sent || 0}</strong></span>
                                <span>Hoje: <strong>${stats.sent_today || 0}</strong></span>
                            </div>
                        </div>
                        <div style="display:flex;gap:0.4rem;align-items:center;flex-wrap:wrap">
                            ${statusBadge}
                            ${actionButtons}
                        </div>
                    </div>
                    <div class="funnel-progress">
                        ${funnelDivs}
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) { console.error(err); }
}

function showCampaignModal() {
    openModal('Criar Campanha de Remarketing', `
        <form onsubmit="return createCampaign(event)">
            <div class="form-group">
                <label>Nome da Campanha *</label>
                <input type="text" id="camp-name" placeholder="Ex: Lançamento Grand Reserva" required>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Tags Alvo (separadas por vírgula)</label>
                    <input type="text" id="camp-tags" placeholder="alto-padrao, 3quartos">
                </div>
                <div class="form-group">
                    <label>Dias do Funil</label>
                    <input type="text" id="camp-funnel" value="1, 2, 3, 5, 7, 14, 30">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Empreendimento</label>
                    <input type="text" id="camp-empreendimento" placeholder="Residencial Grand Reserva">
                </div>
                <div class="form-group">
                    <label>Destaque / Benefício</label>
                    <input type="text" id="camp-destaque" placeholder="Últimas 4 unidades promocionais">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Preço / Condições</label>
                    <input type="text" id="camp-preco" placeholder="A partir de R$ 890.000">
                </div>
                <div class="form-group">
                    <label>Link do Imóvel</label>
                    <input type="text" id="camp-link" placeholder="https://imob.com/imovel">
                </div>
            </div>
            <button type="submit" class="btn btn-primary btn-full mt-3">Criar e Ativar Campanha</button>
        </form>
    `);
}

async function createCampaign(e) {
    e.preventDefault();
    const funnelStr = document.getElementById('camp-funnel').value;
    const funnel = funnelStr.split(',').map(d => parseInt(d.trim())).filter(d => !isNaN(d));

    try {
        await api('/api/campaigns', {
            method: 'POST',
            body: {
                name: document.getElementById('camp-name').value,
                target_tags: document.getElementById('camp-tags').value,
                funnel_days: funnel.length > 0 ? funnel : undefined,
                custom_data: {
                    empreendimento: document.getElementById('camp-empreendimento').value,
                    destaque: document.getElementById('camp-destaque').value,
                    preco: document.getElementById('camp-preco').value,
                    link: document.getElementById('camp-link').value,
                },
            }
        });
        toast('Campanha criada com sucesso!', 'success');
        closeModal();
        loadCampaigns();
    } catch (err) { toast(err.message, 'error'); }
    return false;
}

async function pauseCampaign(id) {
    try {
        await api(`/api/campaigns/${id}/pause`, { method: 'POST' });
        toast('Campanha pausada', 'info');
        loadCampaigns();
    } catch (err) { toast(err.message, 'error'); }
}

async function resumeCampaign(id) {
    try {
        await api(`/api/campaigns/${id}/resume`, { method: 'POST' });
        toast('Campanha retomada!', 'success');
        loadCampaigns();
    } catch (err) { toast(err.message, 'error'); }
}

async function deleteCampaign(id) {
    if (!confirm('Remover esta campanha permanentemente?')) return;
    try {
        await api(`/api/campaigns/${id}`, { method: 'DELETE' });
        toast('Campanha removida', 'info');
        loadCampaigns();
    } catch (err) { toast(err.message, 'error'); }
}

async function editCampaignModal(id) {
    try {
        const data = await api('/api/campaigns');
        const camp = (data.campaigns || []).find(c => c.id === id);
        if (!camp) { toast('Campanha não encontrada', 'error'); return; }

        const cd = camp.custom_data || {};
        const funnel = (camp.funnel_days || [1,2,3,5,7,14,30]).join(', ');

        openModal('Editar Campanha', `
            <form onsubmit="return updateCampaign(event, '${id}')">
                <div class="form-group">
                    <label>Nome</label>
                    <input type="text" id="edit-camp-name" value="${camp.name}">
                </div>
                <div class="form-group">
                    <label>Tags Alvo</label>
                    <input type="text" id="edit-camp-tags" value="${(camp.target_tags || []).join(', ')}">
                </div>
                <div class="form-group">
                    <label>Dias do Funil</label>
                    <input type="text" id="edit-camp-funnel" value="${funnel}">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Empreendimento</label>
                        <input type="text" id="edit-camp-emp" value="${cd.empreendimento || ''}">
                    </div>
                    <div class="form-group">
                        <label>Destaque</label>
                        <input type="text" id="edit-camp-dest" value="${cd.destaque || ''}">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Preço</label>
                        <input type="text" id="edit-camp-preco" value="${cd.preco || ''}">
                    </div>
                    <div class="form-group">
                        <label>Link</label>
                        <input type="text" id="edit-camp-link" value="${cd.link || ''}">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary btn-full mt-3">Salvar Alterações</button>
            </form>
        `);
    } catch (err) { toast(err.message, 'error'); }
}

async function updateCampaign(e, id) {
    e.preventDefault();
    const funnelStr = document.getElementById('edit-camp-funnel').value;
    const funnel = funnelStr.split(',').map(d => parseInt(d.trim())).filter(d => !isNaN(d));

    try {
        await api(`/api/campaigns/${id}`, {
            method: 'PUT',
            body: {
                name: document.getElementById('edit-camp-name').value,
                target_tags: document.getElementById('edit-camp-tags').value,
                funnel_days: funnel,
                custom_data: {
                    empreendimento: document.getElementById('edit-camp-emp').value,
                    destaque: document.getElementById('edit-camp-dest').value,
                    preco: document.getElementById('edit-camp-preco').value,
                    link: document.getElementById('edit-camp-link').value,
                },
            }
        });
        toast('Campanha atualizada!', 'success');
        closeModal();
        loadCampaigns();
    } catch (err) { toast(err.message, 'error'); }
    return false;
}

async function bulkEnterPool(campaignId) {
    if (!confirm('Jogar todos os leads elegíveis para o início do funil desta campanha?')) return;
    try {
        const data = await api('/api/leads/bulk-pool', {
            method: 'POST',
            body: { campaign_id: campaignId }
        });
        toast(`${data.entered} leads entraram no bolsão de remarketing!`, 'success');
    } catch (err) { toast(err.message, 'error'); }
}

// ═══════════════════════════════════════════
// MESSAGES D1...D30
// ═══════════════════════════════════════════

async function loadMessagesPage() {
    try {
        const data = await api('/api/campaigns');
        const sel = document.getElementById('msg-campaign-select');
        sel.innerHTML = '<option value="">Selecione uma campanha...</option>' +
            (data.campaigns || []).map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    } catch (err) { console.error(err); }
}

async function loadCampaignMessages() {
    const campId = document.getElementById('msg-campaign-select').value;
    if (!campId) {
        document.getElementById('messages-editor').innerHTML = '';
        return;
    }

    try {
        const data = await api(`/api/campaigns/${campId}/messages`);
        const funnelDays = data.funnel_days || [1,2,3,5,7,14,30];
        const messages = data.messages || [];

        const msgMap = {};
        messages.forEach(m => { msgMap[m.day] = m.message_text; });

        document.getElementById('messages-editor').innerHTML = funnelDays.map(day => {
            const existing = msgMap[day] || '';
            return `
                <div class="day-message-card">
                    <div class="day-message-header">
                        <span class="day-badge">📅 Dia ${day}</span>
                        <div style="display:flex;gap:0.4rem">
                            <button class="btn btn-ghost btn-xs" onclick="saveDayMessage('${campId}', ${day})">💾 Salvar</button>
                            <button class="btn btn-danger btn-xs" onclick="deleteDayMessage('${campId}', ${day})">🗑️</button>
                        </div>
                    </div>
                    <div class="day-message-body">
                        <textarea id="msg-day-${day}" rows="4" placeholder="Mensagem para o Dia ${day}...">${existing}</textarea>
                        <p class="text-muted text-xs" style="margin-top:0.4rem">Use {primeiro_nome}, {empreendimento}, {link}, {preco}</p>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) { toast(err.message, 'error'); }
}

async function saveDayMessage(campId, day) {
    const text = document.getElementById(`msg-day-${day}`).value.trim();
    if (!text) { toast('Escreva a mensagem antes de salvar', 'error'); return; }
    try {
        await api(`/api/campaigns/${campId}/messages/${day}`, {
            method: 'PUT',
            body: { message_text: text }
        });
        toast(`Mensagem do dia ${day} salva com sucesso!`, 'success');
    } catch (err) { toast(err.message, 'error'); }
}

async function deleteDayMessage(campId, day) {
    try {
        await api(`/api/campaigns/${campId}/messages/${day}`, { method: 'DELETE' });
        toast(`Dia ${day} voltou para a mensagem inteligente automática`, 'info');
        loadCampaignMessages();
    } catch (err) { toast(err.message, 'error'); }
}

// ═══════════════════════════════════════════
// CONTROL & LOG
// ═══════════════════════════════════════════

async function loadControlPage() {
    try {
        const status = await api('/api/engine/status');
        const paused = status.engine_paused;

        const statusClass = paused ? 'paused' : 'running';
        const statusText = paused ? '⏸️ Motor PAUSADO' : '▶️ Motor ATIVO';
        const btnHtml = paused
            ? `<button class="btn btn-success btn-sm mt-3" onclick="engineResume()">▶️ Retomar Motor</button>`
            : `<button class="btn btn-danger btn-sm mt-3" onclick="enginePause()">⏸️ Pausar Motor</button>`;
        document.getElementById('engine-control').innerHTML = `
            <div class="engine-status-indicator ${statusClass}" style="margin-bottom:1rem">
                <span class="dot"></span>${statusText}
            </div>
            <div class="text-sm text-muted">Disparos hoje: <strong>${status.daily_sent || 0}</strong></div>
            ${btnHtml}
        `;

        const leadsData = await api('/api/leads?paused=true&limit=50');
        const pausedLeads = leadsData.leads || [];

        if (pausedLeads.length === 0) {
            document.getElementById('paused-leads-list').innerHTML = '<div style="text-align:center;padding:1.5rem;color:var(--text-muted)">Nenhum lead com pausa individual</div>';
        } else {
            document.getElementById('paused-leads-list').innerHTML = `
                <div class="table-responsive"><table>
                    <thead><tr><th>Nome</th><th>Telefone</th><th>Ação</th></tr></thead>
                    <tbody>
                        ${pausedLeads.map(l => `
                            <tr>
                                <td>${l.name || 'Sem nome'}</td>
                                <td style="font-family:monospace;font-size:0.85rem;color:var(--accent)">${formatPhoneDisplay(l.phone)}</td>
                                <td><button class="btn btn-success btn-xs" onclick="resumeLead('${l.id}')">▶️ Retomar</button></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table></div>
            `;
        }
    } catch (err) { console.error(err); }
}

async function enginePause() {
    try {
        await api('/api/engine/pause', { method: 'POST' });
        toast('Motor de disparos pausado!', 'info');
        loadControlPage();
    } catch (err) { toast(err.message, 'error'); }
}

async function engineResume() {
    try {
        await api('/api/engine/resume', { method: 'POST' });
        toast('Motor de disparos retomado com sucesso!', 'success');
        loadControlPage();
    } catch (err) { toast(err.message, 'error'); }
}

async function loadDispatchLog() {
    try {
        const data = await api('/api/dispatch/log?limit=100');
        const log = data.log || [];

        if (log.length === 0) {
            document.getElementById('dispatch-log-table').innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">📋 Nenhum registro de envio encontrado</div>';
            return;
        }

        document.getElementById('dispatch-log-table').innerHTML = `
            <div class="table-responsive"><table>
                <thead>
                    <tr><th>Data & Hora</th><th>Lead</th><th>Telefone</th><th>Campanha</th><th>Dia</th><th>Status</th></tr>
                </thead>
                <tbody>
                    ${log.map(l => `
                        <tr>
                            <td style="white-space:nowrap">${formatDateTime(l.sent_at)}</td>
                            <td><strong>${l.lead_name || '—'}</strong></td>
                            <td style="font-family:monospace;font-size:0.85rem;color:var(--accent)">${formatPhoneDisplay(l.lead_phone)}</td>
                            <td><span class="tag">${l.campaign_id}</span></td>
                            <td>D${l.remarketing_day || 0}</td>
                            <td><span class="badge badge-${l.status}">${l.status}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table></div>
        `;
    } catch (err) { console.error(err); }
}

// ═══════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════

function formatTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    } catch { return isoStr; }
}

function formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleString('pt-BR', {
            day: '2-digit', month: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return isoStr; }
}

// ═══════════════════════════════════════════
// BOLSÕES / GRUPOS / SEGMENTOS (V2)
// ═══════════════════════════════════════════

// ---------- BOLSÕES (POOLS) ----------

async function loadPools() {
    const container = document.getElementById('pools-list');
    if (!container) return;
    try {
        const data = await api('/api/pools');
        poolsCache = data.pools || [];

        if (poolsCache.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">📦 Nenhum bolsão criado ainda. Clique em "Novo Bolsão" para começar.</div>';
            return;
        }

        container.innerHTML = poolsCache.map(pool => {
            const color = pool.color || 'var(--accent)';
            const statsObj = pool.stats || {};
            const totalLeads = statsObj.total ?? statsObj.leads ?? 0;
            const activeLeads = statsObj.active ?? statsObj.ativos ?? 0;
            const convertedLeads = statsObj.converted ?? statsObj.convertidos ?? 0;
            return `
                <div class="pool-card">
                    <div class="card-header">
                        <h3><span class="pool-dot" style="background:${color}"></span> ${pool.name || 'Sem nome'}</h3>
                        <div style="display:flex;gap:0.4rem">
                            <button class="btn btn-ghost btn-xs" onclick="editPoolModal('${pool.id}')">✏️</button>
                            <button class="btn btn-danger btn-xs" onclick="deletePool('${pool.id}','${(pool.name || '').replace(/'/g, "\\'")}')">🗑️</button>
                        </div>
                    </div>
                    <p class="text-muted text-sm">${pool.description || ''}</p>
                    <div class="pool-stats">
                        <div class="pool-stat"><span class="value">${totalLeads}</span><span class="label">Leads</span></div>
                        <div class="pool-stat"><span class="value">${activeLeads}</span><span class="label">Ativos</span></div>
                        <div class="pool-stat"><span class="value">${convertedLeads}</span><span class="label">Convertidos</span></div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) { toast(err.message, 'error'); }
}

function showAddPoolModal() {
    openModal('Novo Bolsão', `
        <div class="form-group">
            <label>Nome *</label>
            <input type="text" id="pool-name" placeholder="Nome do bolsão">
        </div>
        <div class="form-group">
            <label>Descrição</label>
            <textarea id="pool-description" rows="3" placeholder="Descrição do bolsão..."></textarea>
        </div>
        <div class="form-group">
            <label>Cor</label>
            <input type="color" id="pool-color" value="#25D366">
        </div>
        <button type="button" class="btn btn-primary btn-full mt-2" onclick="createPool()">Criar Bolsão</button>
    `);
}

async function createPool() {
    const name = document.getElementById('pool-name').value.trim();
    const description = document.getElementById('pool-description').value.trim();
    const color = document.getElementById('pool-color').value;
    if (!name) { toast('Informe o nome do bolsão', 'error'); return; }
    try {
        await api('/api/pools', { method: 'POST', body: { name, description, color } });
        toast('Bolsão criado', 'success');
        closeModal();
        loadPools();
    } catch (err) { toast(err.message, 'error'); }
}

function editPoolModal(poolId) {
    const pool = poolsCache.find(p => String(p.id) === String(poolId));
    if (!pool) { toast('Bolsão não encontrado', 'error'); return; }
    openModal('Editar Bolsão', `
        <div class="form-group">
            <label>Nome *</label>
            <input type="text" id="pool-edit-name" value="${(pool.name || '').replace(/"/g, '&quot;')}">
        </div>
        <div class="form-group">
            <label>Descrição</label>
            <textarea id="pool-edit-description" rows="3">${pool.description || ''}</textarea>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Cor</label>
                <input type="color" id="pool-edit-color" value="${pool.color || '#25D366'}">
            </div>
            <div class="form-group">
                <label>Status</label>
                <input type="text" id="pool-edit-status" value="${pool.status || ''}" placeholder="ativo / inativo">
            </div>
        </div>
        <button type="button" class="btn btn-primary btn-full mt-2" onclick="updatePool('${pool.id}')">Salvar Alterações</button>
    `);
}

async function updatePool(poolId) {
    const name = document.getElementById('pool-edit-name').value.trim();
    const description = document.getElementById('pool-edit-description').value.trim();
    const color = document.getElementById('pool-edit-color').value;
    const status = document.getElementById('pool-edit-status').value.trim();
    if (!name) { toast('Informe o nome do bolsão', 'error'); return; }
    try {
        await api(`/api/pools/${poolId}`, { method: 'PUT', body: { name, description, color, status } });
        toast('Bolsão atualizado', 'success');
        closeModal();
        loadPools();
    } catch (err) { toast(err.message, 'error'); }
}

async function deletePool(poolId, name) {
    if (!confirm(`Excluir o bolsão "${name}"?`)) return;
    try {
        await api(`/api/pools/${poolId}`, { method: 'DELETE' });
        toast('Bolsão excluído', 'info');
        loadPools();
    } catch (err) { toast(err.message, 'error'); }
}

// ---------- GRUPOS (GROUPS) ----------

async function loadGroups() {
    const container = document.getElementById('groups-list');
    if (!container) return;
    const journalOnlyEl = document.getElementById('groups-journal-only');
    const journalOnly = journalOnlyEl ? journalOnlyEl.checked : false;
    try {
        const data = await api(journalOnly ? '/api/groups?journal=true' : '/api/groups');
        const groups = data.groups || [];

        if (groups.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">💬 Nenhum grupo encontrado. Clique em "Sincronizar grupos" para importar do WhatsApp.</div>';
            return;
        }

        container.innerHTML = groups.map(g => {
            const gname = g.name || g.subject || 'Grupo sem nome';
            const count = (g.participants != null ? g.participants : (g.size != null ? g.size : null));
            const isJournal = !!g.is_journal;
            let poolBadge = '';
            if (g.pool_id) {
                const linkedPool = poolsCache.find(p => String(p.id) === String(g.pool_id));
                poolBadge = `<span class="tag">📦 ${linkedPool ? linkedPool.name : g.pool_id}</span>`;
            }
            const journalBadge = isJournal ? '<span class="group-badge journal">📰 Jornal</span>' : '';
            return `
                <div class="group-card">
                    <div class="card-header">
                        <h3>${gname}</h3>
                        <div style="display:flex;gap:0.4rem;align-items:center">
                            ${journalBadge}
                            <button class="btn btn-ghost btn-xs" onclick="toggleJournal('${g.id}', ${!isJournal})">📰</button>
                            <button class="btn btn-ghost btn-xs" onclick="assignGroupPoolModal('${g.id}')">🗂️</button>
                            <button class="btn btn-danger btn-xs" onclick="deleteGroup('${g.id}','${gname.replace(/'/g, "\\'")}')">🗑️</button>
                        </div>
                    </div>
                    <p class="text-muted text-sm">${count != null ? count : '—'} participantes</p>
                    ${poolBadge}
                </div>
            `;
        }).join('');
    } catch (err) { toast(err.message, 'error'); }
}

async function syncGroups() {
    toast('Sincronizando grupos...', 'info');
    try {
        const data = await api('/api/groups/sync', { method: 'POST' });
        const count = (data.synced != null ? data.synced : (data.total != null ? data.total : null));
        toast(count != null ? `${count} grupos sincronizados!` : 'Grupos sincronizados com sucesso!', 'success');
        loadGroups();
    } catch (err) { toast(err.message, 'error'); }
}

async function toggleJournal(id, isJournal) {
    try {
        await api(`/api/groups/${id}/journal`, { method: 'POST', body: { is_journal: isJournal } });
        toast(isJournal ? 'Grupo marcado como Jornal' : 'Grupo desmarcado', 'success');
        loadGroups();
    } catch (err) { toast(err.message, 'error'); }
}

async function assignGroupPoolModal(id) {
    try {
        const data = await api('/api/pools');
        const pools = data.pools || [];
        if (pools.length === 0) {
            openModal('Vincular a bolsão', '<div class="text-muted" style="padding:1rem 0">Nenhum bolsão disponível. Crie um bolsão primeiro na aba Bolsões.</div>');
            return;
        }
        openModal('Vincular a bolsão', `
            <div class="form-group">
                <label>Bolsão</label>
                <select id="group-pool-select">
                    ${pools.map(p => `<option value="${p.id}">${p.name || p.id}</option>`).join('')}
                </select>
            </div>
            <button type="button" class="btn btn-primary btn-full mt-2" onclick="assignGroupPool('${id}')">Vincular</button>
        `);
    } catch (err) { toast(err.message, 'error'); }
}

async function assignGroupPool(id) {
    const sel = document.getElementById('group-pool-select');
    const poolId = sel ? sel.value : '';
    if (!poolId) { toast('Selecione um bolsão', 'error'); return; }
    try {
        await api(`/api/groups/${id}/pool`, { method: 'POST', body: { pool_id: poolId } });
        toast('Grupo vinculado ao bolsão', 'success');
        closeModal();
        loadGroups();
    } catch (err) { toast(err.message, 'error'); }
}

async function deleteGroup(id, name) {
    if (!confirm(`Remover o grupo "${name}"?`)) return;
    try {
        await api(`/api/groups/${id}`, { method: 'DELETE' });
        toast('Grupo removido', 'info');
        loadGroups();
    } catch (err) { toast(err.message, 'error'); }
}

// ---------- SEGMENTOS (SEGMENTS) ----------

async function loadSegments() {
    const container = document.getElementById('segments-list');
    if (!container) return;
    try {
        const data = await api('/api/segments');
        const segments = data.segments || [];

        if (segments.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">🎯 Nenhum segmento criado ainda. Clique em "Novo Segmento" para começar.</div>';
            return;
        }

        container.innerHTML = segments.map(seg => {
            const memberCount = seg.member_count ?? seg.members ?? 0;
            return `
                <div class="segment-card">
                    <div class="card-header">
                        <h3>${seg.name || 'Sem nome'}</h3>
                        <div style="display:flex;gap:0.4rem">
                            <button class="btn btn-ghost btn-xs" onclick="viewSegmentMembers('${seg.id}','${(seg.name || '').replace(/'/g, "\\'")}')">👥 Membros</button>
                            <button class="btn btn-danger btn-xs" onclick="deleteSegment('${seg.id}','${(seg.name || '').replace(/'/g, "\\'")}')">🗑️</button>
                        </div>
                    </div>
                    <p class="segment-description">${seg.description || ''}</p>
                    <div style="font-size:0.78rem;color:var(--text-muted)">${memberCount} membros</div>
                </div>
            `;
        }).join('');
    } catch (err) { toast(err.message, 'error'); }
}

async function showAddSegmentModal() {
    let poolOptions = '<option value="">— Sem bolsão —</option>';
    try {
        const data = await api('/api/pools');
        (data.pools || []).forEach(p => {
            poolOptions += `<option value="${p.id}">${p.name || p.id}</option>`;
        });
    } catch (err) { /* segue sem opções de bolsão */ }
    openModal('Novo Segmento', `
        <div class="form-group">
            <label>Nome *</label>
            <input type="text" id="segment-name" placeholder="Nome do segmento">
        </div>
        <div class="form-group">
            <label>Descrição</label>
            <textarea id="segment-description" rows="3" placeholder="Descrição do segmento..."></textarea>
        </div>
        <div class="form-group">
            <label>Bolsão</label>
            <select id="segment-pool">${poolOptions}</select>
        </div>
        <button type="button" class="btn btn-primary btn-full mt-2" onclick="createSegment()">Criar Segmento</button>
    `);
}

async function createSegment() {
    const name = document.getElementById('segment-name').value.trim();
    const description = document.getElementById('segment-description').value.trim();
    const poolSel = document.getElementById('segment-pool');
    const poolId = poolSel ? poolSel.value : '';
    if (!name) { toast('Informe o nome do segmento', 'error'); return; }
    const body = { name, description };
    if (poolId) body.pool_id = poolId;
    try {
        await api('/api/segments', { method: 'POST', body });
        toast('Segmento criado', 'success');
        closeModal();
        loadSegments();
    } catch (err) { toast(err.message, 'error'); }
}

async function viewSegmentMembers(id, name) {
    try {
        const data = await api(`/api/segments/${id}/members`);
        const leadIds = data.lead_ids || [];
        const title = name ? `Membros — ${name}` : 'Membros do segmento';
        if (leadIds.length === 0) {
            openModal(title, '<div class="text-muted" style="padding:1rem 0">Nenhum membro neste segmento ainda.</div>');
            return;
        }
        openModal(title, `
            <div class="text-muted text-sm" style="margin-bottom:0.75rem">${leadIds.length} membro(s)</div>
            <div>
                ${leadIds.map(leadId => `
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:0.5rem 0;border-bottom:1px solid var(--border)">
                        <span style="font-family:monospace;font-size:0.85rem">${leadId}</span>
                        <button class="btn btn-danger btn-xs" onclick="removeSegmentMember('${id}', '${leadId}')">Remover</button>
                    </div>
                `).join('')}
            </div>
        `);
    } catch (err) { toast(err.message, 'error'); }
}

async function removeSegmentMember(segId, leadId) {
    try {
        await api(`/api/segments/${segId}/members/${leadId}`, { method: 'DELETE' });
        toast('Membro removido', 'info');
        viewSegmentMembers(segId, currentSegmentName);
    } catch (err) { toast(err.message, 'error'); }
}

async function deleteSegment(id, name) {
    if (!confirm(`Excluir o segmento "${name}"?`)) return;
    try {
        await api(`/api/segments/${id}`, { method: 'DELETE' });
        toast('Segmento excluído', 'info');
        loadSegments();
    } catch (err) { toast(err.message, 'error'); }
}

// ═══ CONFIGURAÇÕES DA INSTÂNCIA ═══

async function loadInstanceSettings() {
  const container = document.getElementById('settings-container');
  if (!container) return;
  container.innerHTML = '<p class="text-muted">Carregando configurações...</p>';
  try {
    const data = await api('/api/instance/settings');
    container.innerHTML = `
        <div class="settings-section" style="max-width:600px">
            <div class="settings-section-header">⚙️ Configurações da Instância</div>
            <div class="settings-section-body">
                <div class="settings-row">
                    <div class="settings-row-info">
                        <label>Nome de exibição</label>
                        <p>Como este número aparece no painel</p>
                    </div>
                    <input type="text" id="settings-display-name" style="width:200px" value="${data.display_name || ''}" placeholder="Ex: Corretor João">
                </div>
                <div class="settings-row">
                    <div class="settings-row-info">
                        <label>Limite diário de disparos</label>
                        <p>Máximo de mensagens por dia neste número</p>
                    </div>
                    <input type="number" id="settings-daily-limit" style="width:100px" value="${data.daily_limit ?? 40}" min="1" max="500">
                </div>
                <div class="settings-row">
                    <div class="settings-row-info">
                        <label>Modo warmup</label>
                        <p>Aquecimento gradual para números novos</p>
                    </div>
                    <label class="toggle-switch">
                        <input type="checkbox" id="settings-warmup" ${data.warmup_enabled ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            </div>
        </div>
        <div style="display:flex;gap:0.75rem;margin-top:1rem;max-width:600px">
            <button class="btn btn-primary" onclick="saveInstanceSettings()">💾 Salvar</button>
            <button class="btn btn-secondary" onclick="openChangePasswordModal()">🔑 Alterar Senha</button>
        </div>
        <div id="settings-feedback" style="margin-top:0.75rem"></div>
    `;
  } catch (err) {
    container.innerHTML = `<p class="text-danger">Erro ao carregar configurações: ${err.message}</p>`;
  }
}

async function saveInstanceSettings() {
  const display_name = document.getElementById('settings-display-name')?.value.trim() || null;
  const daily_limit = parseInt(document.getElementById('settings-daily-limit')?.value) || null;
  const warmup_enabled = document.getElementById('settings-warmup')?.checked ?? null;
  const feedback = document.getElementById('settings-feedback');
  try {
    await api('/api/instance/settings', {
      method: 'PUT',
      body: JSON.stringify({ display_name, daily_limit, warmup_enabled })
    });
    toast('Configurações salvas com sucesso!', 'success');
    if (feedback) feedback.innerHTML = '<span class="text-success text-sm">✔ Salvo</span>';
    setTimeout(() => { if (feedback) feedback.innerHTML = ''; }, 3000);
    if (display_name) setActiveInstanceBadge(display_name);
  } catch (err) {
    toast('Erro ao salvar: ' + err.message, 'error');
  }
}

function openChangePasswordModal() {
  openModal('🔑 Alterar Senha da Instância', `
    <div class="form-group">
      <label>Nova senha (mínimo 3 caracteres)</label>
      <input type="password" id="new-instance-password" class="form-control" placeholder="Nova senha" autocomplete="new-password">
    </div>
    <div class="form-group">
      <label>Confirmar nova senha</label>
      <input type="password" id="confirm-instance-password" class="form-control" placeholder="Confirmar senha">
    </div>
    <div id="password-change-error" class="text-danger text-sm" style="min-height:1.2rem"></div>
    <div style="display:flex;gap:.75rem;margin-top:1rem">
      <button class="btn btn-primary" onclick="submitChangePassword()">Confirmar</button>
      <button class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
    </div>
  `);
}

async function submitChangePassword() {
  const newPwd = document.getElementById('new-instance-password')?.value || '';
  const confirmPwd = document.getElementById('confirm-instance-password')?.value || '';
  const errEl = document.getElementById('password-change-error');
  if (newPwd.length < 3) { if (errEl) errEl.textContent = 'A senha deve ter pelo menos 3 caracteres.'; return; }
  if (newPwd !== confirmPwd) { if (errEl) errEl.textContent = 'As senhas não coincidem.'; return; }
  try {
    await api('/api/instance/password', { method: 'POST', body: JSON.stringify({ new_password: newPwd }) });
    toast('Senha alterada com sucesso!', 'success');
    closeModal();
  } catch (err) {
    if (errEl) errEl.textContent = err.message;
  }
}

// ═══════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', checkAuth);
