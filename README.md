# 🏠 Bot Remarketing IMOB

Sistema profissional de **Remarketing Imobiliário para Corretores** com funil inteligente de mensagens, bolsão de leads, painel administrativo web dark mode e motor de disparos anti-bloqueio via WhatsApp (Evolution API).

---

## 🌟 Principais Funcionalidades

- **Bolsão de Leads:** Cadastro, busca, segmentação por tags, status de conversão e importação em lote (CSV ou JSON).
- **Funil de Remarketing Inteligente:**
  - Dias configuráveis por campanha (ex: `D1, D2, D3, D5, D7, D14, D30` ou dias personalizados).
  - Leads avançam de dia automaticamente após cada envio bem-sucedido.
  - Mensagens personalizadas por dia ou geração automática anti-spam com variáveis `{nome}`, `{empreendimento}`, `{preco}`, `{link}`, etc.
- **Painel Administrativo Web (SPA):**
  - Dashboard completo em tempo real com métricas do funil.
  - CRUD de leads com controle de pausa individual.
  - CRUD de campanhas com editor visual de mensagens por dia.
  - Controle central do motor (pausar geral / retomar).
  - Log detalhado de todos os disparos com status e horários.
- **Motor Anti-Bloqueio WhatsApp:**
  - Janela de horário comercial customizável.
  - Intervalos randômicos e rajadas naturais (1-3 mensagens com pausas).
  - Hash anti-repetição por lead (nunca repete mensagens idênticas).
- **Backend Robusto com Supabase:** Banco de dados PostgreSQL na nuvem com alta disponibilidade e concorrência segura.

---

## 🚀 Como Rodar Localmente

1. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure o `.env`:**
   Copie `.env.example` para `.env` e preencha as credenciais do Supabase, Evolution API e a senha do painel web.

3. **Inicie o sistema:**
   ```bash
   python main.py
   ```

4. **Acesse o Painel Web:**
   Abra no seu navegador: `http://localhost:8080` (ou a porta configurada no seu `.env`).
   - Senha padrão definida no `.env`: `WEB_PASSWORD` (ex: `admin123`).

---

## ☁️ Como Fazer o Deploy no Render

1. Crie um novo **Web Service** no [Render Dashboard](https://dashboard.render.com/).
2. Conecte o repositório GitHub deste projeto.
3. Configure:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
4. Na aba **Environment Variables** do Render, adicione as mesmas variáveis do seu `.env`:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `WHATSAPP_API_URL`
   - `WHATSAPP_INSTANCE`
   - `WHATSAPP_API_KEY`
   - `WEB_PASSWORD`
   - `WEB_SECRET_KEY`
   - `DISPATCH_WINDOW_START` (ex: 8)
   - `DISPATCH_WINDOW_END` (ex: 20)
   - `PORT` (8080)
5. Clique em **Create Web Service**. Assim que finalizar, acesse a URL gerada pelo Render para usar seu painel web em qualquer lugar!
