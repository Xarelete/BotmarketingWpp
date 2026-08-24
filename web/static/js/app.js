/* =============================================================================
   BotRemarketingIMOB — SPA App (Vanilla JS)
   ============================================================================= */

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
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `Erro ${resp.status}`);
        return data;
    } catch (err) {
        if (err.message.includes('Não autenticado') || err.message.includes('401')) {
            showLogin();
        }
        throw err;
    }
}

// ═══════════════════════════════════════════
// TOAST
// ═══════════════════════════════════════════

function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
}

// ═══════════════════════════════════════════
// MODAL
// ═══════════════════════════════════════════

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

        // Load data for the page
        const loaders = {
            dashboard: loadDashboard,
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
                <div class="stat-label">Leads Ativos</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-value">${leads.in_funnel || 0}</div>
                <div class="stat-label">No Funil</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⏸️</div>
                <div class="stat-value">${leads.paused || 0}</div>
                <div class="stat-label">Pausados</div>
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
                <div class="stat-label">Convertidos</div>
            </div>
        `;

        // Engine status
        const paused = engine.engine_paused;
        document.getElementById('engine-status-panel').innerHTML = `
            <div class="engine-toggle">
                <div class="status-dot ${paused ? 'paused' : 'active'}"></div>
                <div>
                    <strong>${paused ? '⏸️ Motor PAUSADO' : '✅ Motor ATIVO'}</strong>
                    <div class="text-muted" style="font-size:0.8rem">${engine.current_date || ''}</div>
                </div>
            </div>
            ${(engine.campaigns || []).map(c => `
                <div style="display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid var(--border);font-size:0.85rem">
                    <span>📌 <strong>${c.name}</strong></span>
                    <span>Hoje: <strong>${c.sent_today}</strong>/${c.target_today} | Total: ${c.total_sent}</span>
                </div>
            `).join('')}
        `;

        // Recent dispatches
        const log = data.recent_dispatches || [];
        if (log.length === 0) {
            document.getElementById('recent-dispatches').innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><p>Nenhum envio registrado ainda</p></div>';
        } else {
            document.getElementById('recent-dispatches').innerHTML = `
                <div class="table-responsive"><table>
                    <tr><th>Hora</th><th>Lead</th><th>Campanha</th><th>Dia</th><th>Status</th></tr>
                    ${log.map(l => `
                        <tr>
                            <td>${formatTime(l.sent_at)}</td>
                            <td>${l.lead_name || l.lead_phone}</td>
                            <td>${l.campaign_id}</td>
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
// LEADS
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
            document.getElementById('leads-table-container').innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><p>Nenhum lead encontrado</p></div>';
            return;
        }

        document.getElementById('leads-table-container').innerHTML = `
            <div class="table-responsive"><table>
                <tr><th>Nome</th><th>Telefone</th><th>Tags</th><th>Funil</th><th>Status</th><th>Ações</th></tr>
                ${leads.map(l => `
                    <tr>
                        <td><strong>${l.name || 'Sem nome'}</strong></td>
                        <td style="font-family:monospace;font-size:0.8rem">${l.phone}</td>
                        <td>${(l.tags || []).map(t => `<span class="tag">${t}</span>`).join(' ') || '—'}</td>
                        <td>D${l.remarketing_day || 0}${l.next_send_date ? ` → ${l.next_send_date}` : ''}</td>
                        <td>
                            <span class="badge badge-${l.status}">${l.status}</span>
                            ${l.paused ? '<span class="badge badge-paused">pausado</span>' : ''}
                        </td>
                        <td>
                            <div class="actions-cell">
                                ${l.paused
                                    ? `<button class="btn btn-success btn-xs" onclick="resumeLead('${l.id}')">▶️</button>`
                                    : `<button class="btn btn-secondary btn-xs" onclick="pauseLead('${l.id}')">⏸️</button>`
                                }
                                <button class="btn btn-secondary btn-xs" onclick="editLeadModal('${l.id}')">✏️</button>
                                <button class="btn btn-danger btn-xs" onclick="deleteLead('${l.id}')">🗑️</button>
                            </div>
                        </td>
                    </tr>
                `).join('')}
            </table></div>
            <div class="text-muted" style="font-size:0.78rem;margin-top:0.75rem">
                Mostrando ${leads.length} leads | Total: ${data.total}
            </div>
        `;
    } catch (err) { console.error(err); }
}

function showAddLeadModal() {
    openModal('Adicionar Lead', `
        <form onsubmit="return addLead(event)">
            <div class="form-row">
                <div class="form-group">
                    <label>Telefone *</label>
                    <input type="text" id="add-phone" placeholder="5511999887766" required>
                </div>
                <div class="form-group">
                    <label>Nome</label>
                    <input type="text" id="add-name" placeholder="Nome do lead">
                </div>
            </div>
            <div class="form-group">
                <label>Tags (separadas por vírgula)</label>
                <input type="text" id="add-tags" placeholder="abandonado, 3quartos">
            </div>
            <div class="form-group">
                <label>Observações</label>
                <textarea id="add-notes" placeholder="Notas sobre o lead"></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Adicionar Lead</button>
        </form>
    `);
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
        toast('Lead adicionado!', 'success');
        closeModal();
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
    return false;
}

async function pauseLead(id) {
    try {
        await api(`/api/leads/${id}/pause`, { method: 'POST', body: {} });
        toast('Lead pausado', 'info');
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
}

async function resumeLead(id) {
    try {
        await api(`/api/leads/${id}/resume`, { method: 'POST' });
        toast('Lead retomado', 'success');
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
                    <textarea id="edit-notes">${lead.notes || ''}</textarea>
                </div>
                <div class="form-group">
                    <label>Status</label>
                    <select id="edit-status">
                        <option value="active" ${lead.status === 'active' ? 'selected' : ''}>Ativo</option>
                        <option value="inactive" ${lead.status === 'inactive' ? 'selected' : ''}>Inativo</option>
                        <option value="converted" ${lead.status === 'converted' ? 'selected' : ''}>Convertido</option>
                    </select>
                </div>
                <div style="display:flex;gap:0.5rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Salvar</button>
                    <button type="button" class="btn btn-secondary" onclick="resetFunnel('${id}')" style="flex:1">🔄 Resetar Funil</button>
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
        toast('Funil resetado!', 'success');
        closeModal();
        loadLeads();
    } catch (err) { toast(err.message, 'error'); }
}

function showImportModal() {
    openModal('Importar Leads', `
        <div class="form-group">
            <label>Arquivo CSV ou JSON</label>
            <input type="file" id="import-file" accept=".json,.csv" style="padding:0.5rem">
        </div>
        <button onclick="importLeads()" class="btn btn-primary btn-full">📥 Importar</button>
        <div class="text-muted" style="font-size:0.78rem;margin-top:1rem">
            <strong>CSV:</strong> telefone,nome,tags(separadas por ;),notas<br>
            <strong>JSON:</strong> [{"phone":"5511...", "name":"Nome", "tags":["tag1"]}]
        </div>
    `);
}

async function importLeads() {
    const file = document.getElementById('import-file').files[0];
    if (!file) { toast('Selecione um arquivo', 'error'); return; }
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
// CAMPAIGNS
// ═══════════════════════════════════════════

async function loadCampaigns() {
    try {
        const data = await api('/api/campaigns');
        const campaigns = data.campaigns || [];

        if (campaigns.length === 0) {
            document.getElementById('campaigns-list').innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><p>Nenhuma campanha criada ainda</p></div>';
            return;
        }

        document.getElementById('campaigns-list').innerHTML = campaigns.map(c => {
            const stats = c.stats || {};
            const isActive = c.status === 'active';
            const funnelDays = (c.funnel_days || [1,2,3,5,7,14,30]).join(', ');
            return `
                <div class="campaign-card">
                    <div class="campaign-header">
                        <h3>${isActive ? '✅' : '⏸️'} ${c.name}</h3>
                        <span class="badge badge-${c.status}">${c.status}</span>
                    </div>
                    <div class="campaign-meta">
                        <span>🆔 <code style="font-size:0.75rem">${c.id}</code></span>
                        <span>🏷️ ${(c.target_tags || []).join(', ') || 'todos'}</span>
                        <span>📊 ${stats.total_sent || 0} enviadas</span>
                        <span>📅 Funil: D${funnelDays}</span>
                    </div>
                    <div class="campaign-actions">
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
    openModal('Nova Campanha', `
        <form onsubmit="return createCampaign(event)">
            <div class="form-group">
                <label>Nome da Campanha *</label>
                <input type="text" id="camp-name" placeholder="Reativação Zona Sul" required>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Tags Alvo (vírgula)</label>
                    <input type="text" id="camp-tags" placeholder="abandonado, zona-sul">
                </div>
                <div class="form-group">
                    <label>Tipo</label>
                    <select id="camp-type">
                        <option value="reativacao_geral">Reativação Geral</option>
                        <option value="lancamento">Lançamento</option>
                        <option value="evento">Evento</option>
                        <option value="condicoes_especiais">Condições Especiais</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label>Dias do Funil (separados por vírgula)</label>
                <input type="text" id="camp-funnel" placeholder="1, 2, 3, 5, 7, 14, 30" value="1, 2, 3, 5, 7, 14, 30">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Empreendimento</label>
                    <input type="text" id="camp-empreendimento" placeholder="Residencial Aurora">
                </div>
                <div class="form-group">
                    <label>Destaque</label>
                    <input type="text" id="camp-destaque" placeholder="Últimas 5 unidades">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Preço</label>
                    <input type="text" id="camp-preco" placeholder="A partir de R$ 450.000">
                </div>
                <div class="form-group">
                    <label>Link</label>
                    <input type="text" id="camp-link" placeholder="https://...">
                </div>
            </div>
            <div class="form-group">
                <label>Condições</label>
                <input type="text" id="camp-condicoes" placeholder="Entrada facilitada em até 60x">
            </div>
            <button type="submit" class="btn btn-primary btn-full">Criar Campanha</button>
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
                message_template_key: document.getElementById('camp-type').value,
                funnel_days: funnel.length > 0 ? funnel : undefined,
                custom_data: {
                    empreendimento: document.getElementById('camp-empreendimento').value,
                    destaque: document.getElementById('camp-destaque').value,
                    preco: document.getElementById('camp-preco').value,
                    link: document.getElementById('camp-link').value,
                    condicoes: document.getElementById('camp-condicoes').value,
                },
            }
        });
        toast('Campanha criada!', 'success');
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
                <div class="form-group">
                    <label>Condições</label>
                    <input type="text" id="edit-camp-cond" value="${cd.condicoes || ''}">
                </div>
                <button type="submit" class="btn btn-primary btn-full">Salvar Alterações</button>
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
                    condicoes: document.getElementById('edit-camp-cond').value,
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
    if (!confirm('Colocar todos os leads elegíveis no bolsão de remarketing desta campanha?')) return;
    try {
        const data = await api('/api/leads/bulk-pool', {
            method: 'POST',
            body: { campaign_id: campaignId }
        });
        toast(`${data.entered} leads entraram no bolsão!`, 'success');
    } catch (err) { toast(err.message, 'error'); }
}

// ═══════════════════════════════════════════
// MESSAGES EDITOR
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
                    <div class="day-label">
                        <span class="day-number">${day}</span>
                        Dia ${day} do Remarketing
                    </div>
                    <div class="form-group">
                        <textarea id="msg-day-${day}" placeholder="Mensagem para o dia ${day}... Use {nome}, {empreendimento}, {preco}, {link}, {destaque} como variáveis.\n\nDeixe vazio para usar mensagem automática anti-spam.">${existing}</textarea>
                    </div>
                    <div style="display:flex;gap:0.5rem">
                        <button class="btn btn-primary btn-sm" onclick="saveDayMessage('${campId}', ${day})">💾 Salvar</button>
                        ${existing ? `<button class="btn btn-danger btn-sm" onclick="deleteDayMessage('${campId}', ${day})">🗑️ Remover (usar auto)</button>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) { toast(err.message, 'error'); }
}

async function saveDayMessage(campId, day) {
    const text = document.getElementById(`msg-day-${day}`).value.trim();
    if (!text) { toast('Escreva uma mensagem', 'error'); return; }
    try {
        await api(`/api/campaigns/${campId}/messages/${day}`, {
            method: 'PUT',
            body: { message_text: text }
        });
        toast(`Mensagem do dia ${day} salva!`, 'success');
    } catch (err) { toast(err.message, 'error'); }
}

async function deleteDayMessage(campId, day) {
    try {
        await api(`/api/campaigns/${campId}/messages/${day}`, { method: 'DELETE' });
        toast(`Dia ${day} voltou para mensagem automática`, 'info');
        loadCampaignMessages();
    } catch (err) { toast(err.message, 'error'); }
}

// ═══════════════════════════════════════════
// CONTROL
// ═══════════════════════════════════════════

async function loadControlPage() {
    try {
        const status = await api('/api/engine/status');
        const paused = status.engine_paused;

        document.getElementById('engine-control').innerHTML = `
            <div class="engine-toggle">
                <div class="status-dot ${paused ? 'paused' : 'active'}"></div>
                <div style="flex:1">
                    <strong>${paused ? '⏸️ Motor PAUSADO' : '✅ Motor ATIVO'}</strong>
                    <div class="text-muted" style="font-size:0.8rem">
                        ${status.active_campaigns || 0} campanhas ativas | ${status.current_date}
                    </div>
                </div>
                ${paused
                    ? `<button class="btn btn-success btn-sm" onclick="engineResume()">▶️ Retomar</button>`
                    : `<button class="btn btn-danger btn-sm" onclick="enginePause()">⏸️ Pausar</button>`
                }
            </div>
        `;

        // Leads pausados
        const leadsData = await api('/api/leads?paused=true&limit=50');
        const pausedLeads = leadsData.leads || [];

        if (pausedLeads.length === 0) {
            document.getElementById('paused-leads-list').innerHTML = '<div class="empty-state"><p>Nenhum lead pausado</p></div>';
        } else {
            document.getElementById('paused-leads-list').innerHTML = `
                <div class="table-responsive"><table>
                    <tr><th>Nome</th><th>Telefone</th><th>Ação</th></tr>
                    ${pausedLeads.map(l => `
                        <tr>
                            <td>${l.name || 'Sem nome'}</td>
                            <td style="font-family:monospace;font-size:0.8rem">${l.phone}</td>
                            <td><button class="btn btn-success btn-xs" onclick="resumeLead('${l.id}')">▶️ Retomar</button></td>
                        </tr>
                    `).join('')}
                </table></div>
            `;
        }
    } catch (err) { console.error(err); }
}

async function enginePause() {
    try {
        await api('/api/engine/pause', { method: 'POST' });
        toast('Motor pausado!', 'info');
        loadControlPage();
        loadDashboard();
    } catch (err) { toast(err.message, 'error'); }
}

async function engineResume() {
    try {
        await api('/api/engine/resume', { method: 'POST' });
        toast('Motor retomado!', 'success');
        loadControlPage();
        loadDashboard();
    } catch (err) { toast(err.message, 'error'); }
}

// ═══════════════════════════════════════════
// DISPATCH LOG
// ═══════════════════════════════════════════

async function loadDispatchLog() {
    try {
        const data = await api('/api/dispatch/log?limit=100');
        const log = data.log || [];

        if (log.length === 0) {
            document.getElementById('dispatch-log-table').innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div><p>Nenhum envio registrado</p></div>';
            return;
        }

        document.getElementById('dispatch-log-table').innerHTML = `
            <div class="table-responsive"><table>
                <tr><th>Data/Hora</th><th>Lead</th><th>Telefone</th><th>Campanha</th><th>Dia</th><th>Status</th></tr>
                ${log.map(l => `
                    <tr>
                        <td style="white-space:nowrap">${formatDateTime(l.sent_at)}</td>
                        <td>${l.lead_name || '—'}</td>
                        <td style="font-family:monospace;font-size:0.8rem">${l.lead_phone}</td>
                        <td>${l.campaign_id}</td>
                        <td>D${l.remarketing_day || 0}</td>
                        <td><span class="badge badge-${l.status}">${l.status}</span></td>
                    </tr>
                `).join('')}
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
