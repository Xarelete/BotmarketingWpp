"""
=============================================================================
BotRemarketingIMOB - Main Entry Point
=============================================================================
Integra o painel admin via Telegram Bot, o painel web Flask, e o motor de
disparos automático de remarketing.

Três componentes rodam simultaneamente:
  1. Flask Web Server (painel admin + API REST)
  2. Telegram Bot (administração via chat)
  3. Dispatch Engine (disparos automáticos com funil)
"""

import os
import sys
import json
import asyncio
import logging
import threading

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("BotRemarketingIMOB")

# Fix Windows encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_TELEGRAM_ID,
    validate_config,
)
from core.lead_manager import (
    add_lead,
    remove_lead,
    list_leads,
    count_leads,
    update_lead_tags,
    get_lead,
    import_leads_from_json,
    import_leads_from_csv_text,
    export_leads_json,
    pause_lead,
    resume_lead,
)
from core.campaign_manager import (
    create_campaign,
    list_campaigns,
    pause_campaign,
    resume_campaign,
    remove_campaign,
    update_campaign_data,
    get_campaign,
)
from core.dispatch_engine import (
    run_dispatch_engine,
    force_dispatch_one,
    set_engine_paused,
    is_engine_paused,
    get_engine_status,
)


# ═══════════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO DO ADMIN
# ═══════════════════════════════════════════════════════════════════════

def is_admin(update: Update) -> bool:
    """Verifica se o remetente é o admin autorizado."""
    user_id = str(update.effective_user.id)
    return user_id == ADMIN_TELEGRAM_ID


def admin_required(func):
    """Decorator que restringe comandos ao admin."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update):
            await update.message.reply_text("⛔ Acesso negado. Apenas o administrador pode usar este bot.")
            return
        return await func(update, context)
    return wrapper


# ═══════════════════════════════════════════════════════════════════════
# FLASK WEB SERVER
# ═══════════════════════════════════════════════════════════════════════

def start_flask_server():
    """Inicia o Flask web server em uma thread separada."""
    from web.app import create_app
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    logger.info("🌐 Painel Web ativo em http://0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ═══════════════════════════════════════════════════════════════════════
# COMANDOS DO TELEGRAM BOT
# ═══════════════════════════════════════════════════════════════════════

@admin_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal com botões inline."""
    keyboard = [
        [
            InlineKeyboardButton("📋 Leads", callback_data="menu_leads"),
            InlineKeyboardButton("🚀 Campanhas", callback_data="menu_campaigns"),
        ],
        [
            InlineKeyboardButton("📊 Status", callback_data="menu_status"),
            InlineKeyboardButton("⚡ Disparar", callback_data="menu_dispatch"),
        ],
        [
            InlineKeyboardButton("⏸️ Pausar Motor" if not is_engine_paused() else "▶️ Retomar Motor", callback_data="toggle_engine"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🏠 *Bot Remarketing Imobiliário*\n\n"
        "Ferramenta de reativação de leads com funil inteligente.\n"
        "Selecione uma opção:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


@admin_required
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard completo do sistema."""
    status = get_engine_status()
    total_leads = count_leads()
    active_leads = count_leads(status="active")

    lines = [
        "📊 *DASHBOARD — Bot Remarketing*\n",
        f"🔌 Motor: {'⏸️ PAUSADO' if status['engine_paused'] else '✅ ATIVO'}",
        f"📅 Data: {status['current_date'] or '—'}",
        f"👥 Leads: {active_leads} ativos / {total_leads} total",
        f"🚀 Campanhas ativas: {status['active_campaigns']}\n",
    ]

    for camp in status.get("campaigns", []):
        lines.append(
            f"  📌 *{camp['name']}* (`{camp['id']}`)\n"
            f"     Hoje: {camp['sent_today']}/{camp['target_today']} | "
            f"Total: {camp['total_sent']}\n"
            f"     Último envio: {camp['last_dispatch'] or 'Nunca'}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─── LEADS ────────────────────────────────────────────────────────────

@admin_required
async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista leads com resumo."""
    args = context.args
    tag_filter = None
    search = None

    if args:
        for arg in args:
            if arg.startswith("tag:"):
                tag_filter = [arg.replace("tag:", "")]
            else:
                search = arg

    leads = list_leads(status="active", tags=tag_filter, search=search, limit=20)
    total = count_leads(status="active")

    if not leads:
        await update.message.reply_text("📭 Nenhum lead encontrado com os filtros aplicados.")
        return

    lines = [f"📋 *Leads Ativos* ({len(leads)} de {total})\n"]
    for lead in leads:
        tags_str = ", ".join(lead.get("tags", [])) or "sem tags"
        day = lead.get("remarketing_day", 0)
        paused_str = " ⏸️" if lead.get("paused") else ""
        lines.append(
            f"• *{lead.get('name') or 'Sem nome'}*{paused_str}\n"
            f"  📱 `{lead.get('phone')}` | 🏷️ {tags_str} | D{day}"
        )

    lines.append(f"\n_Filtros: /leads tag:nome\\_tag ou /leads texto\\_busca_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_required
async def cmd_lead_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona lead: /lead_add 5511999887766 Nome do Lead"""
    args = context.args
    if not args or len(args) < 1:
        await update.message.reply_text(
            "❌ Uso: `/lead_add 5511999887766 Nome do Lead`\n"
            "Ou: `/lead_add 5511999887766 Nome tag1,tag2`",
            parse_mode="Markdown",
        )
        return

    phone = args[0]
    name_parts = []
    tags = []

    for part in args[1:]:
        if "," in part and " " not in part:
            tags = [t.strip() for t in part.split(",")]
        else:
            name_parts.append(part)

    name = " ".join(name_parts)
    result = add_lead(phone=phone, name=name, tags=tags, added_by="telegram_admin")

    if result:
        await update.message.reply_text(
            f"✅ Lead adicionado!\n"
            f"📱 Telefone: `{result['phone']}`\n"
            f"👤 Nome: {result['name'] or 'N/A'}\n"
            f"🏷️ Tags: {', '.join(result['tags']) or 'nenhuma'}\n"
            f"🆔 ID: `{result['id']}`",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("⚠️ Lead já existe na base (telefone duplicado).")


@admin_required
async def cmd_lead_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove lead: /lead_remove 5511999887766"""
    if not context.args:
        await update.message.reply_text("❌ Uso: `/lead_remove <telefone ou ID>`", parse_mode="Markdown")
        return

    identifier = context.args[0]
    if remove_lead(identifier):
        await update.message.reply_text(f"✅ Lead removido: `{identifier}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Lead não encontrado.")


@admin_required
async def cmd_lead_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerenciar tags: /lead_tag 5511999... tag1,tag2"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Uso:\n"
            "`/lead_tag 5511999... tag1,tag2` (adicionar)\n"
            "`/lead_tag 5511999... -tag1,-tag2` (remover)",
            parse_mode="Markdown",
        )
        return

    identifier = context.args[0]
    raw_tags = context.args[1].split(",")

    add_tags = [t.strip() for t in raw_tags if not t.strip().startswith("-")]
    remove_tags = [t.strip().lstrip("-") for t in raw_tags if t.strip().startswith("-")]

    if add_tags:
        update_lead_tags(identifier, add_tags, mode="add")
    if remove_tags:
        update_lead_tags(identifier, remove_tags, mode="remove")

    lead = get_lead(identifier)
    if lead:
        await update.message.reply_text(
            f"✅ Tags atualizadas para `{identifier}`:\n"
            f"🏷️ {', '.join(lead.get('tags', []))}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("⚠️ Lead não encontrado.")


@admin_required
async def cmd_lead_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pausa envios para um lead: /lead_pausar 5511999..."""
    if not context.args:
        await update.message.reply_text("❌ Uso: `/lead_pausar <telefone ou ID>`", parse_mode="Markdown")
        return
    if pause_lead(context.args[0]):
        await update.message.reply_text(f"⏸️ Lead `{context.args[0]}` pausado.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Lead não encontrado.")


@admin_required
async def cmd_lead_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retoma envios para um lead: /lead_retomar 5511999..."""
    if not context.args:
        await update.message.reply_text("❌ Uso: `/lead_retomar <telefone ou ID>`", parse_mode="Markdown")
        return
    if resume_lead(context.args[0]):
        await update.message.reply_text(f"▶️ Lead `{context.args[0]}` retomado!", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Lead não encontrado.")


@admin_required
async def cmd_lead_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Instrui o admin a enviar arquivo para importação."""
    await update.message.reply_text(
        "📥 *Importação de Leads*\n\n"
        "Envie um arquivo `.json` ou `.csv` com os leads.\n\n"
        "*Formato JSON:*\n"
        "```json\n"
        '[\n'
        '  {"phone": "5511999887766", "name": "João", "tags": ["abandonado"]},\n'
        '  {"phone": "5511888776655", "name": "Maria", "tags": ["3quartos"]}\n'
        ']\n'
        "```\n\n"
        "*Formato CSV:*\n"
        "```\n"
        "telefone,nome,tags,notas\n"
        "5511999887766,João Silva,abandonado;3quartos,Não respondeu\n"
        "```",
        parse_mode="Markdown",
    )


@admin_required
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa arquivo de importação de leads (JSON ou CSV)."""
    doc = update.message.document
    if not doc:
        return

    file_name = doc.file_name or ""
    if not (file_name.endswith(".json") or file_name.endswith(".csv")):
        await update.message.reply_text("⚠️ Formato não suportado. Envie `.json` ou `.csv`.")
        return

    await update.message.reply_text("⏳ Processando arquivo...")

    try:
        file = await doc.get_file()
        file_bytes = await file.download_as_bytearray()
        content = file_bytes.decode("utf-8")

        if file_name.endswith(".json"):
            data = json.loads(content)
            if not isinstance(data, list):
                await update.message.reply_text("⚠️ JSON deve ser uma lista de objetos.")
                return
            result = import_leads_from_json(data, added_by="telegram_import")
        else:
            result = import_leads_from_csv_text(content, added_by="telegram_csv_import")

        await update.message.reply_text(
            f"✅ *Importação concluída!*\n\n"
            f"➕ Adicionados: {result['added']}\n"
            f"⏭️ Duplicados (pulados): {result['skipped']}\n"
            f"❌ Erros: {result['errors']}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("Erro na importação: %s", e)
        await update.message.reply_text(f"❌ Erro ao processar arquivo: {e}")


# ─── CAMPANHAS ────────────────────────────────────────────────────────

@admin_required
async def cmd_campanha_criar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cria campanha: /campanha_criar Nome | tags:tag1,tag2 | tipo:reativacao_geral"""
    text = update.message.text.replace("/campanha_criar", "").strip()

    if not text:
        await update.message.reply_text(
            "❌ *Uso:*\n"
            "`/campanha_criar Nome da Campanha | tags:abandonado,3quartos | "
            "empreendimento:Residencial Aurora | destaque:Últimas 5 unidades | "
            "link:https://imob.com/aurora | preco:A partir de R$ 450.000 | "
            "condicoes:Entrada facilitada em até 60x`\n\n"
            "*Tipos disponíveis:* `reativacao_geral`, `evento`, `lancamento`, "
            "`atualizacao`, `condicoes_especiais`",
            parse_mode="Markdown",
        )
        return

    parts = [p.strip() for p in text.split("|")]
    name = parts[0] if parts else "Campanha sem nome"

    tags = []
    tipo = "reativacao_geral"
    custom = {}

    for part in parts[1:]:
        if part.startswith("tags:"):
            tags = [t.strip() for t in part.replace("tags:", "").split(",")]
        elif part.startswith("tipo:"):
            tipo = part.replace("tipo:", "").strip()
        elif ":" in part:
            key, val = part.split(":", 1)
            custom[key.strip()] = val.strip()

    campaign = create_campaign(
        name=name,
        target_tags=tags,
        message_template_key=tipo,
        custom_data=custom if custom else None,
    )

    await update.message.reply_text(
        f"✅ *Campanha criada!*\n\n"
        f"🆔 ID: `{campaign['id']}`\n"
        f"📌 Nome: {campaign['name']}\n"
        f"🏷️ Tags alvo: {', '.join(campaign.get('target_tags', [])) or 'todos'}\n"
        f"📝 Tipo: {campaign.get('message_template_key')}\n"
        f"📊 Status: {campaign['status']}",
        parse_mode="Markdown",
    )


@admin_required
async def cmd_campanha_listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todas as campanhas."""
    campaigns = list_campaigns()

    if not campaigns:
        await update.message.reply_text("📭 Nenhuma campanha cadastrada.")
        return

    lines = ["🚀 *Campanhas*\n"]
    for camp in campaigns:
        status_emoji = "✅" if camp["status"] == "active" else "⏸️"
        stats = camp.get("stats", {})
        funnel = camp.get("funnel_days", [1,2,3,5,7,14,30])
        lines.append(
            f"{status_emoji} *{camp['name']}*\n"
            f"   🆔 `{camp['id']}`\n"
            f"   🏷️ Tags: {', '.join(camp.get('target_tags', []))}\n"
            f"   📊 Enviadas: {stats.get('total_sent', 0)} | "
            f"Falhas: {stats.get('total_failed', 0)}\n"
            f"   📅 Funil: D{', D'.join(str(d) for d in funnel)}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_required
async def cmd_campanha_pausar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Uso: `/campanha_pausar <campaign_id>`", parse_mode="Markdown")
        return
    cid = context.args[0]
    if pause_campaign(cid):
        await update.message.reply_text(f"⏸️ Campanha `{cid}` pausada.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Campanha não encontrada.")


@admin_required
async def cmd_campanha_retomar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Uso: `/campanha_retomar <campaign_id>`", parse_mode="Markdown")
        return
    cid = context.args[0]
    if resume_campaign(cid):
        await update.message.reply_text(f"▶️ Campanha `{cid}` retomada!", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Campanha não encontrada.")


@admin_required
async def cmd_campanha_remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Uso: `/campanha_remover <campaign_id>`", parse_mode="Markdown")
        return
    cid = context.args[0]
    if remove_campaign(cid):
        await update.message.reply_text(f"🗑️ Campanha `{cid}` removida.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Campanha não encontrada.")


@admin_required
async def cmd_campanha_editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edita dados de campanha: /campanha_editar <id> campo1:valor1 | campo2:valor2"""
    text = update.message.text.replace("/campanha_editar", "").strip()

    if not text or " " not in text:
        await update.message.reply_text(
            "❌ Uso: `/campanha_editar camp_id empreendimento:Novo Nome | "
            "destaque:Nova descrição | preco:R$ 500.000`",
            parse_mode="Markdown",
        )
        return

    parts = text.split(" ", 1)
    cid = parts[0]
    data_parts = [p.strip() for p in parts[1].split("|")]

    updates = {}
    for part in data_parts:
        if ":" in part:
            key, val = part.split(":", 1)
            updates[key.strip()] = val.strip()

    if updates:
        if update_campaign_data(cid, updates):
            await update.message.reply_text(
                f"✅ Campanha `{cid}` atualizada:\n" +
                "\n".join(f"  • {k}: {v}" for k, v in updates.items()),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("⚠️ Campanha não encontrada.")
    else:
        await update.message.reply_text("⚠️ Nenhum dado para atualizar.")


# ─── MOTOR DE DISPAROS ───────────────────────────────────────────────

@admin_required
async def cmd_disparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Força envio de 1 mensagem: /disparar <campaign_id>"""
    if not context.args:
        campaigns = list_campaigns(status="active")
        if not campaigns:
            await update.message.reply_text("📭 Nenhuma campanha ativa.")
            return

        lines = ["❌ Informe o ID da campanha:\n"]
        for camp in campaigns:
            lines.append(f"  `{camp['id']}` — {camp['name']}")
        lines.append(f"\nUso: `/disparar <campaign_id>`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    cid = context.args[0]
    await update.message.reply_text(f"⚡ Forçando disparo para campanha `{cid}`...", parse_mode="Markdown")

    result = await force_dispatch_one(cid)
    if result:
        await update.message.reply_text(f"✅ Mensagem enviada para: *{result}*", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Sem leads elegíveis ou campanha não encontrada.")


@admin_required
async def cmd_pausar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_engine_paused(True)
    await update.message.reply_text("⏸️ Motor de disparos *PAUSADO*.", parse_mode="Markdown")


@admin_required
async def cmd_retomar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_engine_paused(False)
    await update.message.reply_text("▶️ Motor de disparos *RETOMADO*!", parse_mode="Markdown")


# ─── CALLBACKS INLINE ────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa cliques nos botões inline do menu."""
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await query.edit_message_text("⛔ Acesso negado.")
        return

    data = query.data

    if data == "menu_leads":
        total = count_leads()
        active = count_leads(status="active")
        await query.edit_message_text(
            f"📋 *Gerenciamento de Leads*\n\n"
            f"👥 Total: {total} | Ativos: {active}\n\n"
            f"*Comandos:*\n"
            f"`/leads` — Listar leads\n"
            f"`/leads tag:abandonado` — Filtrar por tag\n"
            f"`/lead_add 5511... Nome` — Adicionar\n"
            f"`/lead_remove 5511...` — Remover\n"
            f"`/lead_tag 5511... tag1,tag2` — Tags\n"
            f"`/lead_pausar 5511...` — Pausar lead\n"
            f"`/lead_retomar 5511...` — Retomar lead\n"
            f"`/lead_import` — Importar arquivo",
            parse_mode="Markdown",
        )

    elif data == "menu_campaigns":
        camps = list_campaigns()
        active_count = sum(1 for c in camps if c["status"] == "active")
        await query.edit_message_text(
            f"🚀 *Gerenciamento de Campanhas*\n\n"
            f"📊 Total: {len(camps)} | Ativas: {active_count}\n\n"
            f"*Comandos:*\n"
            f"`/campanha_criar Nome | tags:tag1 | empreendimento:X`\n"
            f"`/campanha_listar` — Listar\n"
            f"`/campanha_pausar <id>` — Pausar\n"
            f"`/campanha_retomar <id>` — Retomar\n"
            f"`/campanha_remover <id>` — Remover\n"
            f"`/campanha_editar <id> campo:valor`",
            parse_mode="Markdown",
        )

    elif data == "menu_status":
        status = get_engine_status()
        total_leads = count_leads()
        active_leads = count_leads(status="active")

        lines = [
            "📊 *DASHBOARD*\n",
            f"🔌 Motor: {'⏸️ PAUSADO' if status['engine_paused'] else '✅ ATIVO'}",
            f"👥 Leads: {active_leads}/{total_leads}",
            f"🚀 Campanhas ativas: {status['active_campaigns']}",
        ]

        for camp in status.get("campaigns", []):
            lines.append(
                f"\n📌 *{camp['name']}*\n"
                f"  Hoje: {camp['sent_today']}/{camp['target_today']} | "
                f"Total: {camp['total_sent']}"
            )

        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "menu_dispatch":
        camps = list_campaigns(status="active")
        if not camps:
            await query.edit_message_text("📭 Nenhuma campanha ativa para disparar.")
            return

        lines = ["⚡ *Disparo Manual*\n\nSelecione a campanha:\n"]
        for camp in camps:
            lines.append(f"`/disparar {camp['id']}` — {camp['name']}")

        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "toggle_engine":
        current = is_engine_paused()
        set_engine_paused(not current)
        new_state = "PAUSADO ⏸️" if not current else "ATIVO ✅"
        await query.edit_message_text(
            f"🔌 Motor de disparos agora: *{new_state}*",
            parse_mode="Markdown",
        )


# ═══════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════

async def post_init(application):
    """Inicia o motor de disparos como task assíncrona."""
    logger.info("🚀 Iniciando motor de disparos em background...")
    asyncio.create_task(run_dispatch_engine())


def main():
    """Entry point principal."""
    logger.info("═" * 60)
    logger.info("🏠 BOT REMARKETING IMOBILIÁRIO — Iniciando...")
    logger.info("═" * 60)

    if not validate_config():
        logger.error("Configuração inválida. Verifique o .env")
        return

    # Verificar conexão com Supabase
    from database import check_connection
    if not check_connection():
        logger.error("❌ Falha na conexão com Supabase. Verifique se executou o supabase_setup.sql e se as chaves estão corretas.")
        return
    logger.info("✅ Conexão com Supabase OK!")

    # Flask Web Server em background (thread separada)
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()

    # Se Telegram Token estiver configurado, inicia o Bot do Telegram
    if TELEGRAM_BOT_TOKEN:
        logger.info("🤖 Iniciando Bot do Telegram...")
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

        # Registra handlers
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("leads", cmd_leads))
        app.add_handler(CommandHandler("lead_add", cmd_lead_add))
        app.add_handler(CommandHandler("lead_remove", cmd_lead_remove))
        app.add_handler(CommandHandler("lead_tag", cmd_lead_tag))
        app.add_handler(CommandHandler("lead_pausar", cmd_lead_pause))
        app.add_handler(CommandHandler("lead_retomar", cmd_lead_resume))
        app.add_handler(CommandHandler("lead_import", cmd_lead_import))
        app.add_handler(CommandHandler("campanha_criar", cmd_campanha_criar))
        app.add_handler(CommandHandler("campanha_listar", cmd_campanha_listar))
        app.add_handler(CommandHandler("campanha_pausar", cmd_campanha_pausar))
        app.add_handler(CommandHandler("campanha_retomar", cmd_campanha_retomar))
        app.add_handler(CommandHandler("campanha_remover", cmd_campanha_remover))
        app.add_handler(CommandHandler("campanha_editar", cmd_campanha_editar))
        app.add_handler(CommandHandler("disparar", cmd_disparar))
        app.add_handler(CommandHandler("pausar", cmd_pausar))
        app.add_handler(CommandHandler("retomar", cmd_retomar))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(CallbackQueryHandler(handle_callback))

        logger.info("🤖 Bot Telegram pronto! Aguardando comandos...")
        app.run_polling(drop_pending_updates=True)
    else:
        logger.info("ℹ️ Telegram não configurado. Rodando no modo PAINEL WEB + MOTOR DE DISPAROS.")
        # Executa o loop do motor de disparos diretamente
        asyncio.run(run_dispatch_engine())


if __name__ == "__main__":
    main()
