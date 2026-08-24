-- =============================================================================
-- BotRemarketingIMOB — Supabase Setup SQL
-- =============================================================================
-- Execute este SQL no Supabase Dashboard → SQL Editor → New Query
-- Isso cria todas as tabelas necessárias para o bot de remarketing.
-- =============================================================================

-- ══════════════════════════════════════════
-- LEADS (bolsão de remarketing)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    phone TEXT UNIQUE NOT NULL,
    source TEXT DEFAULT 'manual',
    tags JSONB DEFAULT '[]'::jsonb,
    added_at TIMESTAMPTZ DEFAULT now(),
    added_by TEXT DEFAULT 'admin',
    status TEXT DEFAULT 'active',
    notes TEXT DEFAULT '',
    paused BOOLEAN DEFAULT false,
    remarketing_day INTEGER DEFAULT 0,
    next_send_date DATE,
    entered_pool_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- ══════════════════════════════════════════
-- CAMPANHAS
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    type TEXT DEFAULT 'remarketing',
    target_tags JSONB DEFAULT '[]'::jsonb,
    message_template_key TEXT DEFAULT 'reativacao_geral',
    custom_data JSONB DEFAULT '{}'::jsonb,
    schedule JSONB DEFAULT '{}'::jsonb,
    funnel_days JSONB DEFAULT '[1,2,3,5,7,14,30]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    total_sent INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    total_leads_reached INTEGER DEFAULT 0,
    last_dispatch TIMESTAMPTZ,
    daily_sent_today INTEGER DEFAULT 0,
    stats_current_date DATE
);

-- ══════════════════════════════════════════
-- MENSAGENS POR DIA (campanha × dia do funil)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS day_messages (
    id BIGSERIAL PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    message_text TEXT NOT NULL,
    is_custom BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(campaign_id, day)
);

-- ══════════════════════════════════════════
-- LOG DE DISPAROS
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS dispatch_log (
    id BIGSERIAL PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    lead_id TEXT NOT NULL,
    lead_phone TEXT NOT NULL,
    lead_name TEXT DEFAULT '',
    remarketing_day INTEGER DEFAULT 0,
    message_hash TEXT DEFAULT '',
    status TEXT DEFAULT 'sent',
    sent_at TIMESTAMPTZ DEFAULT now(),
    error_message TEXT DEFAULT ''
);

-- ══════════════════════════════════════════
-- HASHES DE MENSAGENS (anti-repetição)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS message_hashes (
    id BIGSERIAL PRIMARY KEY,
    phone TEXT NOT NULL,
    msg_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ══════════════════════════════════════════
-- ESTADO DO ENGINE (key-value)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS engine_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ══════════════════════════════════════════
-- NÚMEROS PAUSADOS
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS paused_numbers (
    phone TEXT PRIMARY KEY,
    paused_at TIMESTAMPTZ DEFAULT now(),
    reason TEXT DEFAULT ''
);

-- ══════════════════════════════════════════
-- CONTROLE DIÁRIO (leads enviados hoje)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS daily_tracking (
    id BIGSERIAL PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    lead_phone TEXT NOT NULL,
    sent_date DATE NOT NULL,
    UNIQUE(campaign_id, lead_phone, sent_date)
);

-- ══════════════════════════════════════════
-- ÍNDICES
-- ══════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_next_send ON leads(next_send_date);
CREATE INDEX IF NOT EXISTS idx_leads_remarketing_day ON leads(remarketing_day);
CREATE INDEX IF NOT EXISTS idx_dispatch_log_campaign ON dispatch_log(campaign_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_log_sent_at ON dispatch_log(sent_at);
CREATE INDEX IF NOT EXISTS idx_daily_tracking_date ON daily_tracking(sent_date);
CREATE INDEX IF NOT EXISTS idx_message_hashes_phone ON message_hashes(phone);
CREATE INDEX IF NOT EXISTS idx_day_messages_campaign ON day_messages(campaign_id);

-- ══════════════════════════════════════════
-- DESABILITAR RLS (Row Level Security)
-- Para operações do backend sem restrição
-- ══════════════════════════════════════════
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE day_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispatch_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_hashes ENABLE ROW LEVEL SECURITY;
ALTER TABLE engine_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE paused_numbers ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_tracking ENABLE ROW LEVEL SECURITY;

-- Policies permissivas para o service_role
CREATE POLICY "Allow all for service" ON leads FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service" ON campaigns FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service" ON day_messages FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service" ON dispatch_log FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service" ON message_hashes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service" ON engine_state FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service" ON paused_numbers FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service" ON daily_tracking FOR ALL USING (true) WITH CHECK (true);

-- ══════════════════════════════════════════
-- VALORES INICIAIS
-- ══════════════════════════════════════════
INSERT INTO engine_state (key, value) VALUES ('paused', 'false') ON CONFLICT (key) DO NOTHING;
INSERT INTO engine_state (key, value) VALUES ('current_date', '') ON CONFLICT (key) DO NOTHING;

-- ✅ Setup concluído!
