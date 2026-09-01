# Bot Remarketing IMOB — Planejamento & Roadmap

> Documento vivo de acompanhamento do projeto. Atualize sempre que concluir uma etapa.
> **Portável:** este arquivo não depende de nenhuma conta ou ferramenta específica. Pode ser aberto em qualquer IDE, máquina ou editor.
> Última atualização: 2026-09-01

---

## 1. Visão Geral do Projeto

**Bot Remarketing IMOB** é um sistema de **remarketing imobiliário via WhatsApp** (Evolution API) para corretores. Reativa leads "frios" com um **funil inteligente de mensagens** ao longo de dias (D1, D2, D3, D5, D7, D14, D30 — customizável por campanha), com **motor anti-bloqueio** (janela de horário comercial, intervalos aleatórios, rajadas naturais de 1–3 mensagens, hash anti-repetição por lead).

Inclui: bolsão de leads, importação em lote (CSV/JSON), painel web admin (SPA dark mode), bot administrativo no Telegram e backend no Supabase (PostgreSQL). Deploy pensado para Render.

## 2. Stack / Tecnologias

- **Backend:** Python + Flask 3.0.3 (API REST + serve a SPA)
- **Bot admin:** python-telegram-bot 21.3 (async)
- **Banco:** Supabase 2.10.0 (PostgreSQL na nuvem)
- **WhatsApp:** Evolution API (via httpx 0.27.2 / requests 2.32.3)
- **Frontend:** HTML + CSS + Vanilla JS (SPA, sem framework)
- **Config:** python-dotenv 1.0.1 (.env)
- **Fuso horário:** Brasília (UTC-3)
- **Deploy:** Render (Procfile)

## 3. Arquitetura

`main.py` sobe 3 componentes que rodam juntos:
1. **Servidor Web Flask** (thread separada) — painel admin + API REST.
2. **Bot do Telegram** (se `TELEGRAM_BOT_TOKEN` definido) — administração via chat com menu inline.
3. **Dispatch Engine** (loop assíncrono em background) — disparos automáticos do funil.

Se não houver token do Telegram, roda apenas WEB + MOTOR.

### Camadas principais
- `config.py` — carrega/valida `.env`.
- `database.py` — singleton do client Supabase + `check_connection`.
- `models.py` — dataclasses `Lead`, `Campaign`, `DayMessage`, `DispatchLogEntry` + constantes (`DEFAULT_FUNNEL_DAYS = [1,2,3,5,7,14,30]`).
- `core/` — regras de negócio:
  - `lead_manager.py` — CRUD de leads, tags, pausa individual, importação CSV/JSON, elegibilidade de envio.
  - `campaign_manager.py` — CRUD de campanhas, schedule, funnel_days, mensagens por dia, stats.
  - `dispatch_engine.py` — motor mestre: reset diário, janela horária, meta diária sorteada, rajadas, avanço no funil, logs, dashboard.
  - `message_generator.py` — gerador anti-spam (templates, saudações, emojis, CTAs, hash anti-repetição).
  - `remarketing_funnel.py` — lógica do funil (enter_pool, advance_lead, get_current_send_day, bulk_enter_pool, stats, reset).
  - `direct_broadcast.py` — disparo direto/teste em massa com Spintax `{A|B|C}`, sinônimos PT-BR (humanizador), variação de emoji/pontuação.
  - `parallel_broadcast.py` — disparo PARALELO por número/instância (multi-fila, trava anti-ban por instância); suporta leads E grupos.
  - `group_manager.py` — grupos de WhatsApp (sync via Evolution, "Jornal da Construtora", vínculo a bolsão).
  - `instance_access.py` — acesso por número (senha hash SHA-256 por instância, limite diário, warmup).
  - `pool_manager.py` — bolsões por empreendimento (pools) vinculados a instância.
  - `segment_manager.py` — segmentos/listas internas de leads + membros.
- `platforms/whatsapp_client.py` — client Evolution API multi-instância (texto/imagem, listar instâncias, status de conexão, grupos, instância ativa persistida).
- `web/` — `app.py` (Flask factory + rotas REST), `auth.py` (login global + login por instância), `context.py` (instância ativa na sessão), `templates/index.html` (SPA), `static/js/app.js`, `static/css/style.css`.

## 4. Variáveis de Ambiente (.env)

**Obrigatórias:**
- `WHATSAPP_API_URL`, `WHATSAPP_INSTANCE`, `WHATSAPP_API_KEY`
- `SUPABASE_URL`, `SUPABASE_KEY`

**Opcionais:**
- `TELEGRAM_BOT_TOKEN`, `ADMIN_TELEGRAM_ID`
- `DISPATCH_WINDOW_START`, `DISPATCH_WINDOW_END`
- `DAILY_TARGET_MIN`, `DAILY_TARGET_MAX`
- `WEB_PASSWORD` (default: `admin123`), `WEB_SECRET_KEY`
- `PORT`

## 5. Banco de Dados (Supabase)

- **V1 — `supabase_setup.sql`:** tabelas `leads`, `campaigns`, `day_messages`, `dispatch_log`, `message_hashes`, `engine_state`, `paused_numbers`, `daily_tracking`.
- **V2 — `supabase_migration_v2.sql` (aditiva):** `instance_access`, `pools`, `whatsapp_groups`, `lead_segments`, `segment_members`, `group_dispatch_log` + colunas `instance_name`/`pool_id` em `leads` e `campaigns`. Seed cria número principal `BotMarketingWpp` (senha `admin`) e bolsão `Geral`, migrando dados antigos.

---

## 6. ROADMAP POR ETAPAS

Legenda: ✅ concluído · 🚧 em andamento · ⬜ pendente

### Etapa 1 — Núcleo do Funil de Remarketing (V1) ✅
- [x] Modelos de dados (Lead, Campaign, DayMessage, DispatchLog)
- [x] Motor de disparo com janela horária, meta diária e rajadas
- [x] Gerador de mensagens anti-spam com hash anti-repetição
- [x] Lógica do funil (D1…D30) e avanço de leads
- [x] Importação de leads (CSV/JSON) e gestão de bolsão
- [x] Schema V1 no Supabase (`supabase_setup.sql`)

### Etapa 2 — Painel Web + Bot Telegram (V1) ✅
- [x] SPA admin (dashboard, broadcast, leads, campaigns, messages, control, log)
- [x] Login global por senha (`WEB_PASSWORD`)
- [x] API REST V1 (`/api/broadcast/*`, leads, campaigns, messages, control, log)
- [x] Bot administrativo no Telegram com menu inline
- [x] Integração com Evolution API (envio texto/imagem, status de instância)

### Etapa 3 — Backend V2: Multi-número, Bolsões, Grupos, Segmentos, Disparo Paralelo ✅
- [x] Migração aditiva no Supabase (`supabase_migration_v2.sql`)
- [x] `instance_access.py` — login/senha por número + limite diário + warmup
- [x] `pool_manager.py` — bolsões por empreendimento
- [x] `group_manager.py` — grupos de WhatsApp / Jornal da Construtora
- [x] `segment_manager.py` — segmentos e membros
- [x] `parallel_broadcast.py` — disparo paralelo por instância (anti-ban por número)
- [x] Rotas REST V2 (`/api/pools`, `/api/groups`, `/api/segments`, `/api/instances/available`, `/api/instance/login`, `/api/instance/settings`, `/api/broadcast2/*`)

### Etapa 4 — Integração do Frontend com a V2 ✅
- [x] Tela de seleção/login por número (instância) usando `/api/instances/available` + `/api/instance/login` (com fallback para admin global)
- [x] Nova página **Bolsões** na navegação (consumir `/api/pools` com listagem, criação, edição e exclusão)
- [x] Nova página **Grupos / Jornal da Construtora** (consumir `/api/groups` com sync, filtro de jornal, toggle e vínculo a bolsão)
- [x] Nova página **Segmentos** (consumir `/api/segments` com criação, listagem, visualização/remoção de membros)
- [x] Atualizar navegação do `index.html` e a versão dos assets (`?v=2.6.0`)
- [x] ✅ Migrar o disparo da UI de `/api/broadcast/*` para `/api/broadcast2/*` (paralelo por número)
- [x] ✅ Tela de configurações por instância (`/api/instance/settings`)

### Etapa 5 — Documentação & Testes da API (opcional, futuro) ⬜
- [ ] Coleção de testes da API REST do Flask (pasta `postman/` hoje vazia) — portável/exportável, sem travar em conta específica
- [ ] Environment de exemplo com as variáveis (sem segredos reais)
- [ ] Testes automatizados das rotas principais

### Etapa 6 — Deploy & Operação ⬜
- [ ] Revisar `Procfile` e variáveis no Render
- [ ] Checklist de saúde (`check_connection`, status das instâncias)
- [ ] Monitoramento de disparos e limites diários por número

---

## 7. Notas Técnicas / Pendências Observadas

- Vestígios em `core/__pycache__`: `journey_engine.cpython-311.pyc` e `services.cpython-311.pyc` sem `.py` correspondente — indicam módulos antigos removidos/renomeados. Confirmar se algo ainda depende deles.
- Mistura de bytecode Python 3.11 e 3.12 no `__pycache__` — padronizar a versão do Python do ambiente.
- Pasta `data/` vazia — paths legados de JSON mantidos só por compatibilidade; storage agora é 100% Supabase.
- Comentário em `app.js` indica que "o servidor precisa ser reiniciado para carregar as novas rotas" — as rotas V2 são recentes.
- Versão atual dos assets no HTML: `?v=2.5.0`.

## 8. Como Retomar (Quick Start)

1. Criar/preencher o `.env` com as variáveis obrigatórias (ver seção 4).
2. Rodar o schema no Supabase: `supabase_setup.sql` e depois `supabase_migration_v2.sql`.
3. Instalar dependências: `pip install -r requirements.txt`.
4. Subir localmente: `python main.py`.
5. **Etapa 4 concluída ✅** — Próximo passo: **Etapa 5** — Documentação & Testes da API (coleção Postman, environment de exemplo e testes automatizados das rotas principais).

---
*Mantenha este arquivo atualizado ao final de cada sessão de trabalho, marcando os checkboxes e ajustando "Última atualização".*
