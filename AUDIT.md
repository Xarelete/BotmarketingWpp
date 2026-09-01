# AUDIT.md — Auditoria de Preservação e Inventário de Módulos (BotRemarketingIMOB)
*Gerado conforme as diretrizes da skill `whatsapp-remarketing-panel-redesign` (Fase 1 e Fase 2).*

---

## 🔒 FASE 1 — Mapeamento de Itens Críticos e Intocáveis

A tabela abaixo classifica todos os componentes do backend, motores e integrações para garantir **zero regressão funcional** durante qualquer refinamento de UI/UX.

### 1. Camada de Envio Real (Evolution API / WhatsApp)
| Arquivo | Função / Endpoint | Assinatura Exata | Classificação | Observações |
| :--- | :--- | :--- | :--- | :--- |
| `platforms/whatsapp_client.py` | `send_whatsapp_message_sync` | `(phone, text, image_url=None, instance=None) -> (bool, str)` | **`PRESERVAR INTACTO`** | Envio direto de texto/imagem para leads individuais. |
| `platforms/whatsapp_client.py` | `send_whatsapp_group_message_sync` | `(group_jid, text, image_url=None, instance=None) -> (bool, str)` | **`PRESERVAR INTACTO`** | Envio de mensagens e mídias para grupos de WhatsApp. |
| `platforms/whatsapp_client.py` | `check_whatsapp_connection_sync` | `(instance=None) -> (bool, str)` | **`PRESERVAR INTACTO`** | Checagem de status da Evolution API. |
| `platforms/whatsapp_client.py` | `list_whatsapp_instances` | `() -> List[Dict[str, Any]]` | **`PRESERVAR INTACTO`** | Listagem de instâncias da Evolution. |
| `platforms/whatsapp_client.py` | `get_active_instance` / `set_active_instance` | `(name: str)` | **`PRESERVAR INTACTO`** | Controle de instância ativa. |

---

### 2. Motores Anti-Bloqueio & Disparo em Massa
| Arquivo | Função / Componente | Assinatura / Papel | Classificação | Observações |
| :--- | :--- | :--- | :--- | :--- |
| `core/direct_broadcast.py` | `_format_lead_message` | `(template, lead, vary_synonyms=True, vary_text=True)` | **`PRESERVAR INTACTO`** | Resolve tags `{primeiro_nome}`, `{telefone}`, `{empreendimento}`, Spintax `{A|B}` e sinônimos. |
| `core/direct_broadcast.py` | `preview_humanized_message` | `(template, sample_lead, vary_synonyms, vary_text) -> str` | **`PRESERVAR INTACTO`** | Usado pelo botão "🎲 Gerar Variação" no simulador. |
| `core/parallel_broadcast.py` | `start_broadcast` | `(instance_name, targets, message_template, image_url, min_delay, max_delay, vary_text, vary_synonyms, kind='leads')` | **`PRESERVAR INTACTO`** | Fila assíncrona com threading por número e delays randômicos. |
| `core/parallel_broadcast.py` | `get_broadcast_status` / `cancel_broadcast` | `(instance_name)` | **`PRESERVAR INTACTO`** | Polling de progresso e cancelamento de emergência. |

---

### 3. Motor do Funil Diário D1–D30
| Arquivo | Função / Componente | Assinatura / Papel | Classificação | Observações |
| :--- | :--- | :--- | :--- | :--- |
| `core/dispatch_engine.py` | `run_dispatch_cycle` | `() -> Coroutine` | **`PRESERVAR INTACTO`** | Worker que processa o envio das mensagens do dia do funil. |
| `core/dispatch_engine.py` | `force_dispatch_one` | `(campaign_id) -> Coroutine` | **`PRESERVAR INTACTO`** | Botão "⚡ Forçar 1" para envio imediato de teste. |
| `core/remarketing_funnel.py` | `process_lead_funnel` | `(lead) -> Dict` | **`PRESERVAR INTACTO`** | Calcula dia do funil (D1, D2, D3, D5, D7, D14, D30). |
| `core/remarketing_funnel.py` | `reset_lead_funnel` | `(lead_id) -> bool` | **`PRESERVAR INTACTO`** | Reinicia o funil do lead para D1. |

---

### 4. Schema do Banco de Dados (Supabase)
| Tabela | Colunas Chave | Classificação | Observações |
| :--- | :--- | :--- | :--- |
| `leads` | `id`, `phone`, `name`, `tags`, `status`, `remarketing_day`, `pool_id`, `paused` | **`PRESERVAR INTACTO`** | Nenhuma coluna deve ser renomeada. |
| `pools` | `id`, `name`, `description`, `color`, `instance_name`, `status` | **`PRESERVAR INTACTO`** | Bolsões por empreendimento. |
| `campaigns` | `id`, `name`, `funnel_days`, `target_tags`, `custom_data`, `status` | **`PRESERVAR INTACTO`** | Configuração dos funis. |
| `campaign_messages` | `campaign_id`, `day`, `message_text` | **`PRESERVAR INTACTO`** | Mensagens customizadas D1..D30. |
| `dispatch_logs` | `lead_id`, `lead_name`, `lead_phone`, `campaign_id`, `remarketing_day`, `status`, `sent_at` | **`PRESERVAR INTACTO`** | Histórico de auditoria de disparos. |
| `groups` | `id`, `instance_name`, `name`, `participants`, `is_journal`, `pool_id` | **`PRESERVAR INTACTO`** | Grupos e canais do WhatsApp. |
| `segments` / `segment_members`| `id`, `name`, `pool_id`, `lead_id` | **`PRESERVAR INTACTO`** | Segmentos customizados. |
| `instance_access` | `instance_name`, `display_name`, `password_hash`, `daily_limit`, `warmup_enabled` | **`PRESERVAR INTACTO`** | Acesso e segurança por número. |

---

### 5. Sessão e Autenticação
| Arquivo | Função / Decorator | Classificação |
| :--- | :--- | :--- |
| `web/auth.py` | `login`, `login_instance`, `logout`, `auth_required` | **`PRESERVAR INTACTO`** |
| `web/context.py` | `get_session_instance`, `set_session_instance`, `instance_required` | **`PRESERVAR INTACTO`** |

---

## 🗺️ FASE 2 — Inventário de Telas e Fluxos da Aplicação

| Tela / Módulo | Arquivos de Front-end | Endpoints REST Conectados | Risco de Regressão |
| :--- | :--- | :--- | :--- |
| **Login & Seleção** | `#login-screen`, `#instance-screen` | `POST /api/auth/login`, `GET /api/instances/available`, `POST /api/instance/login` | Baixo |
| **Dashboard** | `#page-dashboard` | `GET /api/dashboard` | Baixo (Somente leitura) |
| **Bolsões (Pools)** | `#page-pools` | `GET /api/pools`, `POST /api/pools`, `PUT /api/pools/<id>`, `DELETE /api/pools/<id>`, `POST /api/pools/<id>/leads`, `POST /api/pools/<id>/add-number` | Médio |
| **Leads (CRM)** | `#page-leads` | `GET /api/leads`, `POST /api/leads`, `PUT /api/leads/<id>`, `DELETE /api/leads/<id>`, `POST /api/leads/<id>/pause`, `POST /api/leads/<id>/resume`, `POST /api/leads/import`, `POST /api/leads/<id>/test-message` | Médio |
| **Grupos & Canais** | `#page-groups` | `GET /api/groups`, `POST /api/groups/sync`, `POST /api/groups/<id>/journal`, `POST /api/groups/<id>/pool`, `DELETE /api/groups/<id>` | Médio |
| **Segmentos** | `#page-segments` | `GET /api/segments`, `POST /api/segments`, `DELETE /api/segments/<id>`, `GET /api/segments/<id>/members`, `POST /api/segments/<id>/members`, `DELETE /api/segments/<id>/members/<lead_id>` | Baixo |
| **Campanhas & D1-D30**| `#page-campaigns`, `#page-messages` | `GET /api/campaigns`, `POST /api/campaigns`, `PUT /api/campaigns/<id>`, `DELETE /api/campaigns/<id>`, `GET/PUT/DELETE /api/campaigns/<id>/messages/<day>`, `POST /api/campaigns/<id>/dispatch-one` | **Alto** (Automação do funil) |
| **Disparo Rápido** | `#page-broadcast` | `POST /api/broadcast/preview`, `POST /api/upload/image`, `POST /api/broadcast2/start`, `GET /api/broadcast2/status`, `POST /api/broadcast2/cancel` | **Alto** (Disparos reais) |
| **Central de Controle**| `#page-control`, `#page-log` | `GET /api/engine/status`, `POST /api/engine/pause`, `POST /api/engine/resume`, `GET /api/dispatch/log` | Médio |
| **Configurações** | `#page-settings` | `GET/PUT /api/instance/settings`, `POST /api/instance/password` | Baixo |
