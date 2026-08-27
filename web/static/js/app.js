/* =============================================================================
   BotRemarketingIMOB — SPA App & Simulador WhatsApp (Vanilla JS)
   ============================================================================= */

// Estado global da aplicação
let allLeadsCache = [];
let selectedLeadIds = new Set();
let broadcastPollingInterval = null;
let currentUploadedImageUrl = null;

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
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
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
        const data = await api('/api/auth/check');
        if (data.authenticated) { showApp(); } else { showLogin(); }
    } catch { showLogin(); }
}

function showLogin() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('app').classList.add('hidden');
}

function showApp() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    loadDashboard();
    checkActiveBroadcast();
    checkWhatsAppStatus();
}

async function checkWhatsAppStatus() {
    try {
        const data = await api('/api/whatsapp/status');
        const dot = document.getElementById('wpp-status-dot');
        const label = document.getElementById('wpp-status-label');
        if (data.connected) {
            if (dot) dot.style.background = 'var(--success)';
            if (label) label.textContent = 'WhatsApp Conectado';
        } else {
            if (dot) dot.style.background = 'var(--danger)';
            if (label) label.textContent = 'WhatsApp Desconectado';
        }
    } catch { }
}

async function handleLogin(e) {
    e.preventDefault();
    const pw = document.getElementById('login-password').value;
    try {
        await api('/api/auth/login', { method: 'POST', body: { password: pw } });
        showApp();
    } catch (err) {
        document.getElementById('login-error').textContent = 'Senha incorreta';
    }
    return false;
}

async function handleLogout() {
    await api('/api/auth/logout', { method: 'POST' });
    showLogin();
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

        const loaders = {
            dashboard: loadDashboard,
            broadcast: loadBroadcastPage,
            leads: loadLeads,
            campaigns: loadCampaigns,
            messages: loadMessagesPage,
            control: loadControlPage,
            log: loadDispatchLog,
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
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-value">${leads.active || 0}</div>
                <div class="stat-label">Leads no Bolsão</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-value">${leads.in_funnel || 0}</div>
                <div class="stat-label">Em Remarketing Ativo</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⏸️</div>
                <div class="stat-value">${leads.paused || 0}</div>
                <div class="stat-label">Envios Pausados</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🚀</div>
                <div class="stat-value">${engine.active_campaigns || 0}</div>
                <div class="stat-label">Campanhas Ativas</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-value">${leads.completed || 0}</div>
                <div class="stat-label">Completaram Funil</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🏆</div>
                <div class="stat-value">${leads.converted || 0}</div>
                <div class="stat-label">Leads Convertidos</div>
            </div>
        `;

        const paused = engine.engine_paused;
        document.getElementById('engine-status-panel').innerHTML = `
            <div class="engine-toggle" style="background:var(--bg-input);padding:1rem;border-radius:var(--radius-sm);display:flex;align-items:center;gap:1rem;margin-bottom:1rem">
                <div class="status-pulse-dot" style="background:${paused ? 'var(--warning)' : 'var(--success)'};box-shadow:0 0 10px ${paused ? 'var(--warning)' : 'var(--success)'}"></div>
                <div style="flex:1">
                    <strong style="font-size:0.95rem">${paused ? '⏸️ Motor Geral PAUSADO' : '✅ Motor de Disparos ATIVO'}</strong>
                    <div class="text-muted text-sm">Data de operação: ${engine.current_date || 'Hoje'}</div>
                </div>
            </div>
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
            document.getElementById('recent-dispatches').innerHTML = `
                <div class="table-responsive"><table>
                    <tr><th>Hora</th><th>Lead</th><th>Campanha</th><th>Dia</th><th>Status</th></tr>
                    ${log.map(l => `
                        <tr>
                            <td>${formatTime(l.sent_at)}</td>
                            <td><strong>${l.lead_name || l.lead_phone}</strong></td>
                            <td><span class="tag">${l.campaign_id}</span></td>
                            <td>D${l.remarketing_day || 0}</td>
                            <td><span class="badge badge-${l.status}">${l.status}</span></td>
                        </tr>
                    `).join('')}
                </table></div>
            `;
        }
    } catch (err) { console.error(err); }
}

// ═══════════════════════════════════════════
// DISPARO RÁPIDO & SIMULADOR WHATSAPP
// ═══════════════════════════════════════════

async function loadBroadcastPage() {
    updateWhatsappPreview();
    await fetchAllLeadsForBroadcast();
    checkActiveBroadcast();
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

function updateWhatsappPreview() {
    const rawText = document.getElementById('bc-message-text')?.value || '';
    const imageUrl = currentUploadedImageUrl || document.getElementById('bc-image-url')?.value || '';

    let previewText = rawText
        .replace(/\{primeiro_nome\}/gi, 'João')
        .replace(/\{nome\}/gi, 'João Silva')
        .replace(/\{telefone\}/gi, '+55 (12) 99181-0835')
        .replace(/\{([^{}]+)\}/g, (match, choices) => choices.split('|')[0]);

    if (!previewText.trim()) {
        previewText = 'Olá João, tudo bem?\n\nPassando para te mostrar uma oportunidade exclusiva de imóvel!';
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
    const imageUrl = currentUploadedImageUrl || document.getElementById('bc-image-url')?.value.trim() || null;

    if (!confirm(`🚀 Iniciar disparo em massa para ${selectedLeadIds.size} leads selecionados com intervalos entre ${minDelay}s e ${maxDelay}s?`)) {
        return;
    }

    try {
        const resp = await api('/api/broadcast/start', {
            method: 'POST',
            body: {
                lead_ids: Array.from(selectedLeadIds),
                message_template: text,
                image_url: imageUrl,
                min_delay: minDelay,
                max_delay: maxDelay,
                vary_text: varyText,
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
            const status = await api('/api/broadcast/status');
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
        const status = await api('/api/broadcast/status');
        if (status.is_running) {
            startBroadcastPolling();
        }
    } catch { }
}

async function cancelActiveBroadcast() {
    if (!confirm('Deseja realmente interromper a fila de envios?')) return;
    try {
        await api('/api/broadcast/cancel', { method: 'POST' });
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
            const funnelDays = (c.funnel_days || [1,2,3,5,7,14,30]).join(', ');
            return `
                <div class="card mb-3">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
                        <h3 style="margin:0">${isActive ? '✅' : '⏸️'} ${c.name}</h3>
                        <span class="badge badge-${c.status}">${c.status}</span>
                    </div>
                    <div style="display:flex;gap:1.25rem;font-size:0.82rem;color:var(--text-secondary);flex-wrap:wrap;margin-bottom:0.75rem">
                        <span>🏷️ Tags: ${(c.target_tags || []).join(', ') || 'todos os leads'}</span>
                        <span>📊 Enviadas: <strong>${stats.total_sent || 0}</strong></span>
                        <span>📅 Dias do Funil: D${funnelDays}</span>
                    </div>
                    <div style="display:flex;gap:0.4rem;flex-wrap:wrap">
                        <button class="btn btn-primary btn-xs" title="Disparar para 1 lead elegível agora" onclick="forceDispatchCampaign('${c.id}', '${c.name}')">⚡ Forçar 1 Disparo</button>
                        ${isActive
                            ? `<button class="btn btn-secondary btn-xs" onclick="pauseCampaign('${c.id}')">⏸️ Pausar</button>`
                            : `<button class="btn btn-success btn-xs" onclick="resumeCampaign('${c.id}')">▶️ Retomar</button>`
                        }
                        <button class="btn btn-secondary btn-xs" onclick="editCampaignModal('${c.id}')">✏️ Editar</button>
                        <button class="btn btn-secondary btn-xs" onclick="bulkEnterPool('${c.id}')">📥 Jogar Leads no Bolsão</button>
                        <button class="btn btn-danger btn-xs" onclick="deleteCampaign('${c.id}')">🗑️ Remover</button>
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
                <div class="card mb-3">
                    <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.75rem">
                        <span style="background:var(--accent);color:#000;width:28px;height:28px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.82rem">${day}</span>
                        <strong style="color:var(--accent);font-size:0.95rem">Dia ${day} do Remarketing</strong>
                    </div>
                    <div class="form-group">
                        <textarea id="msg-day-${day}" rows="4" placeholder="Mensagem para o dia ${day}... Use {nome}, {empreendimento}, {preco}, {link} como variáveis.">${existing}</textarea>
                    </div>
                    <div style="display:flex;gap:0.5rem">
                        <button class="btn btn-primary btn-sm" onclick="saveDayMessage('${campId}', ${day})">💾 Salvar Mensagem</button>
                        ${existing ? `<button class="btn btn-danger btn-sm" onclick="deleteDayMessage('${campId}', ${day})">🗑️ Usar Automática</button>` : ''}
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

        document.getElementById('engine-control').innerHTML = `
            <div class="engine-toggle" style="background:var(--bg-input);padding:1.25rem;border-radius:var(--radius-sm);display:flex;align-items:center;gap:1rem;margin-bottom:1rem">
                <div class="status-pulse-dot" style="background:${paused ? 'var(--warning)' : 'var(--success)'};box-shadow:0 0 10px ${paused ? 'var(--warning)' : 'var(--success)'}"></div>
                <div style="flex:1">
                    <strong style="font-size:1rem">${paused ? '⏸️ Motor Geral PAUSADO' : '✅ Motor Geral ATIVO'}</strong>
                    <div class="text-muted text-sm">${status.active_campaigns || 0} campanhas ativas</div>
                </div>
                ${paused
                    ? `<button class="btn btn-success btn-sm" onclick="engineResume()">▶️ Retomar Motor</button>`
                    : `<button class="btn btn-danger btn-sm" onclick="enginePause()">⏸️ Pausar Motor</button>`
                }
            </div>
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
// INIT
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', checkAuth);
