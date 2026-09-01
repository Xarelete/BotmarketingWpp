---
name: whatsapp-remarketing-panel-redesign
description: Use esta skill sempre que o usuário pedir para analisar, auditar, reestruturar ou redesenhar o BotRemarketingIMOB (painel admin de remarketing WhatsApp para o mercado imobiliário — Aurora Glass UI, backend Flask, Supabase, Evolution API) dentro do Antigravity ou de qualquer outro ambiente de código. Também acione quando o usuário mencionar "redesign do painel de WhatsApp", "refazer o layout do bot de remarketing", "painel premium para o BotRemarketingIMOB", ou pedir para "modernizar"/"deixar bonito" um painel de disparo/funil de leads que já existe e funciona. Esta skill cobre o processo completo: auditoria do código existente para mapear tudo que já funciona (conexão WhatsApp, motor anti-bloqueio, funil D1-D30, disparos), definição de um novo design system premium, e reestruturação de telas/rotas SEM quebrar as integrações de envio de mensagem já operacionais. Use mesmo que o usuário peça só "uma parte" do redesign (ex: só uma tela), pois a auditoria de preservação é obrigatória antes de qualquer mudança visual.
---

# Redesign do BotRemarketingIMOB (Painel de Remarketing WhatsApp Imobiliário)

## Contexto do projeto

O BotRemarketingIMOB é uma plataforma de remarketing inteligente via WhatsApp para o mercado imobiliário, já funcional, em desenvolvimento no Antigravity. Arquitetura atual:

```
Corretor/Admin → Painel SPA (Aurora Glass UI)
                → API REST / Flask (backend Python)
                → Supabase (persistência)
                → Evolution API (envio/sincronização WhatsApp)
                → Motor Diário (Funil D1–D30)
                → Fila Paralela (Disparo Rápido / Broadcast)
```

Módulos existentes: multi-instância por número, bolsões de leads (pools), CRM de leads com status (ativo/pausado/completo/convertido), disparo rápido multi-alvo (leads, bolsões, grupos, canais, segmentos), composer com tags inteligentes ({primeiro_nome}, {telefone}, {empreendimento}, {destaque}, {preco}, {link}), simulador de WhatsApp ao vivo, motor anti-bloqueio (spintax, sinônimos, delays randômicos, isolamento de filas por número), editor de campanhas D1–D30, central de controle (pausa geral/pânico) e logs de histórico.

**Regra de ouro desta skill: o objetivo é 100% visual/estrutural (design, IA de telas, componentes), nunca funcional.** A lógica de negócio que já roda em produção (ou já testada) não pode ser reescrita "de brinde" durante o redesign — apenas replugada em uma nova casca.

## Fluxo de trabalho obrigatório

### Fase 1 — Auditoria de preservação (sempre primeiro, sem exceção)

Antes de tocar em qualquer CSS, componente ou rota, mapeie e liste explicitamente para o usuário (ou em um arquivo `AUDIT.md` na raiz do projeto) tudo que é **crítico e intocável**:

1. **Camada de envio real**: toda chamada à Evolution API (endpoints de envio de texto, envio de imagem, status de conexão, QR code/pareamento, webhooks de recebimento). Anote arquivo, função e assinatura exata.
2. **Motor anti-bloqueio**: função(ões) de spintax `{opção1|opção2}`, dicionário de sinônimos, geração de delay randômico, isolamento de fila por número (threading/queue).
3. **Motor de funil D1–D30**: o job/cron/worker que decide "que dia do funil o lead está" e dispara a mensagem certa — geralmente a parte mais frágil e mais fácil de quebrar sem perceber.
4. **Schema do Supabase**: tabelas de leads, bolsões, jornadas, logs, instâncias/números. Não alterar nomes de colunas/tabelas usadas por essas funções sem migração explícita.
5. **Autenticação/sessão** por número e por corretor.
6. **Variáveis de ambiente e configs de deploy** (Render).

Para cada item, classifique como:
- `PRESERVAR INTACTO` — só a UI que chama isso muda, a função/endpoint fica idêntica.
- `PRESERVAR COM ADAPTAÇÃO` — a lógica fica, mas o contrato de dados (payload) muda porque a nova tela pede algo diferente; aqui é preciso atualizar os dois lados juntos, no mesmo commit/etapa.
- `LIVRE PARA REFAZER` — puramente visual (componentes de UI, layout, roteamento de páginas, estado de front-end).

Não avance para a Fase 2 sem essa lista. Se o código real não estiver disponível no contexto (ex: conversa sem acesso ao repositório), primeiro peça acesso ao projeto/repositório do Antigravity ou aos arquivos relevantes — não invente a estrutura do backend.

### Fase 2 — Inventário de telas e fluxos atuais

Liste todas as rotas/páginas existentes com sua função (ex: Dashboard, Bolsões, Gestão de Leads, Disparo Rápido, Campanhas D1-D30, Central de Controle/Logs, Configurações de Instância). Para cada uma, anote quais ações do usuário disparam quais chamadas de API da Fase 1 — isso vira o mapa de "o que não pode sumir" na nova IA de navegação.

### Fase 3 — Definir o design system premium

Proponha (e confirme com o usuário se houver ambiguidade) uma direção visual coesa — não misture estilos. Duas direções de referência já usadas em projetos do usuário, escolha uma ou combine deliberadamente:

- **Soft UI / dashboard premium**: sidebar em cápsula escura, cards brancos arredondados, paleta quase P&B com um accent color, sombras suaves, tipografia forte — sensação "produto SaaS caro".
- **Glassmorphism refinado (evolução do Aurora Glass UI atual)**: manter a identidade "Aurora" mas elevar: vidro fosco com mais contraste, gradientes sutis, profundidade em camadas, micro-animações de transição, dark mode como base.

Defina antes de codar:
- Paleta (cor base + accent + estados: sucesso/conectado, aviso/pausado, erro/desconectado, neutro).
- Tipografia (par de fontes ou uma família com pesos variados).
- Grid/spacing system, raio de borda, elevação (sombras) consistentes.
- Estados de componente: conectado/desconectado do WhatsApp (indicador em tempo real), lead ativo/pausado/completo/convertido, fila rodando/pausada.
- Micro-interações: o simulador de WhatsApp ao vivo e o botão "🎲 Gerar Variação" merecem destaque especial — são o diferencial do produto, não podem virar um componente genérico.

Consulte a skill `frontend-design` (se disponível no ambiente) para tokens de design e evitar UI genérica "default".

### Fase 4 — Reestruturar telas e caminhos (IA)

Com a Fase 1 e 3 prontas, redesenhe a arquitetura de informação. Sugestão de agrupamento por intenção (adapte ao que a auditoria revelou):

1. **Visão Geral** — status das instâncias (online/offline), leads ativos no funil, conversões recentes, alerta de fila.
2. **Leads** — bolsões (pools) + CRM de contatos individuais, unificados numa navegação só, com o card de bolsão levando direto ao disparo pré-selecionado.
3. **Disparos** — disparo rápido (multi-alvo) e simulador vivendo juntos numa mesma tela, já que um alimenta o outro.
4. **Campanhas (Funil D1–D30)** — editor de régua por dia, separado do disparo avulso para não confundir automação com ação pontual.
5. **Central de Controle** — pausa geral, logs, limites diários, modo warmup — tudo que é "operação/segurança" agrupado.
6. **Configurações** — números conectados, controle de acesso por corretor.

Cada tela nova deve declarar explicitamente, no código ou em comentário, a quais itens `PRESERVAR` da Fase 1 ela está conectada — isso facilita revisão e evita quebra silenciosa.

### Fase 5 — Implementação incremental

Implemente tela por tela (não o app inteiro de uma vez), na ordem: telas que só leem dados (Visão Geral, Logs) → telas que escrevem mas são de baixo risco (Configurações, Leads/CRM) → telas de alto risco que disparam mensagens reais (Disparo Rápido, Campanhas D1-D30). Isso limita o raio de dano de qualquer regressão. Após cada tela, rode o checklist de verificação da Fase 6 antes de seguir para a próxima.

### Fase 6 — Checklist de verificação (rodar após cada etapa de alto risco)

- [ ] Indicador de conexão do WhatsApp reflete o status real (não mockado).
- [ ] Envio de mensagem de teste avulsa chega de fato ao número de destino.
- [ ] Envio com imagem continua funcionando (upload + entrega).
- [ ] Tags inteligentes ({primeiro_nome}, {telefone}, etc.) continuam sendo substituídas corretamente no payload real.
- [ ] Spintax/variação de texto e delay randômico continuam ativos (não virou envio idêntico/sem delay).
- [ ] Pausa individual de lead e botão de pânico/pausa geral realmente interrompem o motor.
- [ ] Funil D1–D30 continua calculando o dia certo por lead (testar com lead simulado em dias diferentes).
- [ ] Logs de histórico continuam sendo gravados com os mesmos campos que telas de relatório/outras partes do sistema esperam.
- [ ] Nenhum nome de coluna/tabela do Supabase usado pelo backend foi renomeado sem migração.

Se qualquer item falhar, o problema é tratado como regressão bloqueante — não se avança para a próxima tela até corrigir.

## Erros comuns a evitar

- Reescrever a lógica de envio "só para deixar o código mais bonito" — risco alto, ganho zero para o usuário.
- Trocar a biblioteca/forma de chamar a Evolution API sem necessidade — mantenha o client/wrapper existente, só troque a UI ao redor.
- Misturar dois estilos visuais (ex: parte soft UI, parte glass) por pressa — gera sensação de produto quebrado, o oposto de "premium".
- Redesenhar todas as telas de uma vez sem testar as de alto risco isoladamente — dificulta achar qual mudança quebrou o quê.
- Assumir a estrutura do backend sem ler o código real — sempre confirmar contra o projeto real no Antigravity antes de propor o mapa da Fase 1.