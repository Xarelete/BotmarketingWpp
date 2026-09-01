-- =============================================================================
-- BotRemarketingIMOB — Migração V2 (ADITIVA e SEGURA)
-- =============================================================================
-- Execute este SQL no Supabase Dashboard → SQL Editor → New Query.
--
-- ⚠️ Esta migração é 100% ADITIVA:
--   • NÃO apaga nenhuma tabela, coluna ou dado existente.
--   • Apenas CRIA novas tabelas e ADICIONA colunas (com IF NOT EXISTS).
--   • Pode ser executada múltiplas vezes com segurança (idempotente).
--
-- Novidades desta versão:
--   1. Acesso por número conectado (instance_access) — login com senha por número.
--   2. Bolsões por empreendimento (pools).
--   3. Grupos de WhatsApp (whatsapp_groups) — jornal da construtora + disparo.
--   4. Segmentos / listas internas de leads (lead_segments + segment_members).
--   5. Colunas de vínculo: leads.instance_name/pool_id, campaigns.instance_name/pool_id.
-- =============================================================================


-- ══════════════════════════════════════════════════════════════════════════
-- 1. ACESSO POR NÚMERO CONECTADO
--    Cada instância (número) tem senha própria (armazenada como hash) e limites.
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS instance_access (
    instance_name   TEXT PRIMARY KEY,
    display_name    TEXT DEFAULT '',
    password_hash   TEXT NOT NULL,              -- SHA-256 (hex) da senha
    daily_limit     INTEGER DEFAULT 200,        -- teto de envios/dia por número
    warmup_enabled  BOOLEAN DEFAULT true,       -- aquecimento p/ números novos
    active          BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);


-- ══════════════════════════════════════════════════════════════════════════
-- 2. BOLSÕES POR EMPREENDIMENTO (POOLS)
--    Agrupa leads/campanhas por empreendimento, sempre dentro de um número.
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pools (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    instance_name       TEXT NOT NULL DEFAULT '',   -- número dono do bolsão
    description         TEXT DEFAULT '',
    color               TEXT DEFAULT '#25D366',
    empreendimento_data JSONB DEFAULT '{}'::jsonb,   -- preco, link, destaque, image_url...
    status              TEXT DEFAULT 'active',
    created_at          TIMESTAMPTZ DEFAULT now()
);


-- ══════════════════════════════════════════════════════════════════════════
-- 3. GRUPOS DE WHATSAPP (JORNAL + DISPARO)
--    Espelha grupos reais do WhatsApp sincronizados via Evolution API.
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS whatsapp_groups (
    id                  TEXT PRIMARY KEY,           -- id interno (grp_xxxx)
    group_jid           TEXT NOT NULL,              -- id real do grupo na Evolution (...@g.us)
    name                TEXT DEFAULT '',
    instance_name       TEXT NOT NULL DEFAULT '',   -- número que participa do grupo
    participants_count  INTEGER DEFAULT 0,
    is_journal          BOOLEAN DEFAULT false,      -- marcado como "jornal da construtora"
    pool_id             TEXT,                       -- opcional: vincula grupo a um empreendimento
    picture_url         TEXT DEFAULT '',
    last_synced_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE(instance_name, group_jid)
);


-- ══════════════════════════════════════════════════════════════════════════
-- 4. SEGMENTOS / LISTAS INTERNAS DE LEADS
--    Listas reutilizáveis de leads para disparos direcionados.
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS lead_segments (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    instance_name   TEXT NOT NULL DEFAULT '',
    pool_id         TEXT,
    description     TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS segment_members (
    segment_id      TEXT NOT NULL REFERENCES lead_segments(id) ON DELETE CASCADE,
    lead_id         TEXT NOT NULL,
    added_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (segment_id, lead_id)
);


-- ══════════════════════════════════════════════════════════════════════════
-- 5. HISTÓRICO DE DISPAROS PARA GRUPOS (JORNAL)
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS group_dispatch_log (
    id              BIGSERIAL PRIMARY KEY,
    instance_name   TEXT NOT NULL DEFAULT '',
    group_jid       TEXT NOT NULL,
    group_name      TEXT DEFAULT '',
    message_hash    TEXT DEFAULT '',
    status          TEXT DEFAULT 'sent',
    sent_at         TIMESTAMPTZ DEFAULT now(),
    error_message   TEXT DEFAULT ''
);


-- ══════════════════════════════════════════════════════════════════════════
-- 6. COLUNAS DE VÍNCULO (aditivas, nullable — não quebram dados existentes)
-- ══════════════════════════════════════════════════════════════════════════
ALTER TABLE leads     ADD COLUMN IF NOT EXISTS instance_name TEXT;
ALTER TABLE leads     ADD COLUMN IF NOT EXISTS pool_id       TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS instance_name TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS pool_id       TEXT;


-- ══════════════════════════════════════════════════════════════════════════
-- 7. ÍNDICES (aceleram os filtros por número/bolsão)
-- ══════════════════════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_leads_instance      ON leads(instance_name);
CREATE INDEX IF NOT EXISTS idx_leads_pool          ON leads(pool_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_instance  ON campaigns(instance_name);
CREATE INDEX IF NOT EXISTS idx_campaigns_pool      ON campaigns(pool_id);
CREATE INDEX IF NOT EXISTS idx_pools_instance      ON pools(instance_name);
CREATE INDEX IF NOT EXISTS idx_groups_instance     ON whatsapp_groups(instance_name);
CREATE INDEX IF NOT EXISTS idx_segments_instance   ON lead_segments(instance_name);
CREATE INDEX IF NOT EXISTS idx_group_log_instance  ON group_dispatch_log(instance_name);


-- ══════════════════════════════════════════════════════════════════════════
-- 8. RLS + POLICIES PERMISSIVAS (padrão do projeto, service_role)
-- ══════════════════════════════════════════════════════════════════════════
ALTER TABLE instance_access   ENABLE ROW LEVEL SECURITY;
ALTER TABLE pools             ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_groups   ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_segments     ENABLE ROW LEVEL SECURITY;
ALTER TABLE segment_members   ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_dispatch_log ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='instance_access' AND policyname='Allow all for service') THEN
        CREATE POLICY "Allow all for service" ON instance_access FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='pools' AND policyname='Allow all for service') THEN
        CREATE POLICY "Allow all for service" ON pools FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='whatsapp_groups' AND policyname='Allow all for service') THEN
        CREATE POLICY "Allow all for service" ON whatsapp_groups FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='lead_segments' AND policyname='Allow all for service') THEN
        CREATE POLICY "Allow all for service" ON lead_segments FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='segment_members' AND policyname='Allow all for service') THEN
        CREATE POLICY "Allow all for service" ON segment_members FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='group_dispatch_log' AND policyname='Allow all for service') THEN
        CREATE POLICY "Allow all for service" ON group_dispatch_log FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;


-- ══════════════════════════════════════════════════════════════════════════
-- 9. SEED INICIAL — número principal da conta (Lívia) + bolsão Geral
--    Senha inicial "admin" (SHA-256). Troque pelo painel depois.
--    Vincula os leads/campanhas SEM instância ao número principal.
-- ══════════════════════════════════════════════════════════════════════════

-- 9.1 Acesso do número principal (senha "admin")
INSERT INTO instance_access (instance_name, display_name, password_hash, daily_limit)
VALUES (
    'BotMarketingWpp',
    'Número Principal (Lívia)',
    '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',  -- sha256('admin')
    200
)
ON CONFLICT (instance_name) DO NOTHING;

-- 9.2 Bolsão "Geral" do número principal
INSERT INTO pools (id, name, instance_name, description, color)
VALUES (
    'pool_geral_principal',
    'Geral',
    'BotMarketingWpp',
    'Bolsão padrão com todos os leads existentes.',
    '#25D366'
)
ON CONFLICT (id) DO NOTHING;

-- 9.3 Migra leads existentes (sem instância) para o número principal + bolsão Geral
UPDATE leads
   SET instance_name = 'BotMarketingWpp'
 WHERE instance_name IS NULL OR instance_name = '';

UPDATE leads
   SET pool_id = 'pool_geral_principal'
 WHERE pool_id IS NULL OR pool_id = '';

-- 9.4 Migra campanhas existentes (sem instância) para o número principal + bolsão Geral
UPDATE campaigns
   SET instance_name = 'BotMarketingWpp'
 WHERE instance_name IS NULL OR instance_name = '';

UPDATE campaigns
   SET pool_id = 'pool_geral_principal'
 WHERE pool_id IS NULL OR pool_id = '';

-- ✅ Migração V2 concluída com segurança!
