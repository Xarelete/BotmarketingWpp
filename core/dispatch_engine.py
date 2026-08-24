"""
=============================================================================
BotRemarketingIMOB - Dispatch Engine (Supabase + Funil)
=============================================================================
Motor de disparos inteligente com integração ao funil de remarketing:
  • Leads avançam pelos dias do funil automaticamente
  • Mensagens customizadas por dia ou geradas automaticamente
  • Intervalos aleatórios anti-padrão (30s a 180s)
  • Rajadas naturais (1-3 msgs rápidas + pausa longa)
  • Janela horária configurável
  • Meta diária aleatória por campanha
  • Pausa individual e geral
"""

import random
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from config import (
    BR_TZ,
    DISPATCH_WINDOW_START,
    DISPATCH_WINDOW_END,
    DAILY_TARGET_MIN,
    DAILY_TARGET_MAX,
)
from database import get_supabase
from core.lead_manager import get_leads_for_sending
from core.campaign_manager import (
    get_active_campaigns,
    get_campaign,
    update_campaign_stats,
    get_day_message,
)
from core.message_generator import (
    generate_unique_message,
    generate_day_message,
    register_message_sent,
)
from core.remarketing_funnel import (
    advance_lead,
    get_current_send_day,
    enter_pool,
)
from platforms.whatsapp_client import send_whatsapp_message

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# ESTADO DO ENGINE
# ═══════════════════════════════════════════════════════════════════════

def _get_now_br() -> datetime:
    return datetime.now(BR_TZ)


def set_engine_paused(paused: bool) -> None:
    """Define se o motor está pausado ou ativo."""
    sb = get_supabase()
    sb.table("engine_state").upsert({
        "key": "paused",
        "value": str(paused).lower(),
    }).execute()


def is_engine_paused() -> bool:
    """Retorna se o motor está pausado."""
    sb = get_supabase()
    result = sb.table("engine_state").select("value").eq("key", "paused").execute()
    if result.data:
        return result.data[0]["value"].lower() == "true"
    return False


def _get_state_value(key: str, default: str = "") -> str:
    """Obtém valor do estado do engine."""
    sb = get_supabase()
    result = sb.table("engine_state").select("value").eq("key", key).execute()
    if result.data:
        return result.data[0]["value"]
    return default


def _set_state_value(key: str, value: str) -> None:
    """Define valor do estado do engine."""
    sb = get_supabase()
    sb.table("engine_state").upsert({"key": key, "value": value}).execute()


# ═══════════════════════════════════════════════════════════════════════
# CONTROLE DIÁRIO
# ═══════════════════════════════════════════════════════════════════════

def _today_str() -> str:
    return _get_now_br().strftime("%Y-%m-%d")


def _ensure_daily_reset() -> None:
    """Reseta contadores diários se mudou o dia."""
    today = _today_str()
    current = _get_state_value("current_date", "")
    if current != today:
        _set_state_value("current_date", today)
        # Limpa daily_targets do dia anterior
        _set_state_value("daily_targets", "{}")
        logger.info("📅 [Novo Dia %s] Contadores resetados.", today)


def _get_daily_target(campaign_id: str, campaign: Dict[str, Any]) -> int:
    """Obtém ou sorteia a meta diária para uma campanha."""
    import json
    targets_str = _get_state_value("daily_targets", "{}")
    try:
        targets = json.loads(targets_str)
    except Exception:
        targets = {}

    if campaign_id not in targets:
        schedule = campaign.get("schedule", {})
        min_t = schedule.get("daily_target_min", DAILY_TARGET_MIN)
        max_t = schedule.get("daily_target_max", DAILY_TARGET_MAX)
        targets[campaign_id] = random.randint(min_t, max_t)
        _set_state_value("daily_targets", json.dumps(targets))
        logger.info(
            "🎯 Meta diária sorteada para '%s': %d leads",
            campaign.get("name"), targets[campaign_id],
        )

    return targets[campaign_id]


def _get_daily_sent_count(campaign_id: str) -> int:
    """Retorna quantas mensagens foram enviadas hoje nesta campanha."""
    sb = get_supabase()
    today = _today_str()
    result = sb.table("daily_tracking").select("id", count="exact").eq(
        "campaign_id", campaign_id
    ).eq("sent_date", today).execute()
    return result.count if result.count is not None else 0


def _mark_lead_sent_today(campaign_id: str, phone: str) -> None:
    """Marca que um lead recebeu mensagem hoje nesta campanha."""
    sb = get_supabase()
    today = _today_str()
    try:
        sb.table("daily_tracking").insert({
            "campaign_id": campaign_id,
            "lead_phone": phone,
            "sent_date": today,
        }).execute()
    except Exception:
        pass  # Ignora duplicatas (UNIQUE constraint)


def _log_dispatch(
    campaign_id: str,
    lead: Dict[str, Any],
    remarketing_day: int,
    message_hash: str,
    status: str = "sent",
    error_message: str = "",
) -> None:
    """Registra um disparo no log."""
    sb = get_supabase()
    try:
        sb.table("dispatch_log").insert({
            "campaign_id": campaign_id,
            "lead_id": lead.get("id", ""),
            "lead_phone": lead.get("phone", ""),
            "lead_name": lead.get("name", ""),
            "remarketing_day": remarketing_day,
            "message_hash": message_hash,
            "status": status,
            "sent_at": datetime.now(BR_TZ).isoformat(),
            "error_message": error_message,
        }).execute()
    except Exception as e:
        logger.error("Erro ao registrar dispatch log: %s", e)


# ═══════════════════════════════════════════════════════════════════════
# DISPARO INDIVIDUAL
# ═══════════════════════════════════════════════════════════════════════

async def dispatch_single_lead(
    lead: Dict[str, Any],
    campaign: Dict[str, Any],
) -> bool:
    """
    Dispara mensagem para um lead individual.
    Usa mensagem customizada do dia (se existir) ou gera automaticamente.
    """
    phone = lead.get("phone", "")
    lead_name = lead.get("name", "")
    campaign_id = campaign.get("id")
    campaign_name = campaign.get("name", "")
    custom = campaign.get("custom_data", {})
    image_url = custom.get("image_url", "")

    # Determina qual dia do funil enviar
    send_day = get_current_send_day(lead, campaign)

    # Tenta buscar mensagem customizada para este dia
    custom_message = get_day_message(campaign_id, send_day)

    if custom_message:
        # Usa mensagem customizada (com substituição de variáveis)
        message = custom_message
        first_name = lead_name.split()[0] if lead_name else ""
        message = message.replace("{nome}", first_name)
        message = message.replace("{telefone}", phone)
        message = message.replace("{empreendimento}", custom.get("empreendimento", ""))
        message = message.replace("{destaque}", custom.get("destaque", ""))
        message = message.replace("{preco}", custom.get("preco", ""))
        message = message.replace("{link}", custom.get("link", ""))
        message = message.replace("{dia}", str(send_day))
    else:
        # Gera mensagem automática anti-spam
        message = generate_unique_message(lead, campaign)

    if not message:
        logger.warning("Não foi possível gerar mensagem para %s (%s)", lead_name, phone)
        update_campaign_stats(campaign_id, failed=1)
        _log_dispatch(campaign_id, lead, send_day, "", "failed", "Sem mensagem gerada")
        return False

    # Envia via WhatsApp
    import hashlib
    msg_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()[:12]

    success = await send_whatsapp_message(phone, message, image_url or None)

    if success:
        register_message_sent(phone, message)
        update_campaign_stats(campaign_id, sent=1, leads_reached=1)
        _log_dispatch(campaign_id, lead, send_day, msg_hash, "sent")

        # Avança o lead no funil
        advance_result = advance_lead(lead["id"], campaign)
        if advance_result.get("completed"):
            logger.info("🏁 [%s] Lead %s COMPLETOU o funil!", campaign_name, lead_name or phone)

        logger.info(
            "✅ [%s] D%d → %s (%s)",
            campaign_name, send_day, lead_name or phone, phone,
        )
        return True
    else:
        update_campaign_stats(campaign_id, failed=1)
        _log_dispatch(campaign_id, lead, send_day, msg_hash, "failed", "Falha no envio WhatsApp")
        logger.warning("❌ [%s] Falha D%d → %s (%s)", campaign_name, send_day, lead_name or phone, phone)
        return False


# ═══════════════════════════════════════════════════════════════════════
# DISPARO FORÇADO
# ═══════════════════════════════════════════════════════════════════════

async def force_dispatch_one(campaign_id: str) -> Optional[str]:
    """Força envio de 1 mensagem (bypass de schedule)."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return None

    _ensure_daily_reset()
    target_tags = campaign.get("target_tags", [])
    leads = get_leads_for_sending(campaign_id, target_tags)

    if not leads:
        return None

    # Embaralha e pega o primeiro
    random.shuffle(leads)
    lead = leads[0]

    success = await dispatch_single_lead(lead, campaign)
    if success:
        _mark_lead_sent_today(campaign_id, lead.get("phone", ""))
        return lead.get("name") or lead.get("phone", "")

    return None


# ═══════════════════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

async def run_dispatch_engine():
    """
    Loop mestre de disparos com funil de remarketing.
    """
    logger.info("🚀 Motor de Disparos inicializado!")

    while True:
        try:
            # 0. Verificação de pausa
            if is_engine_paused():
                logger.info("⏸️ Motor PAUSADO. Aguardando retomada...")
                await asyncio.sleep(30)
                continue

            now = _get_now_br()
            current_hour = now.hour

            # 1. Reset diário
            _ensure_daily_reset()

            # 2. Janela de operação
            if current_hour < DISPATCH_WINDOW_START or current_hour >= DISPATCH_WINDOW_END:
                if current_hour >= DISPATCH_WINDOW_END:
                    logger.info(
                        "🌙 [%02d:%02d] Janela encerrada. Pausando até %02d:00...",
                        now.hour, now.minute, DISPATCH_WINDOW_START,
                    )
                else:
                    logger.info(
                        "🌅 [%02d:%02d] Aguardando abertura às %02d:00...",
                        now.hour, now.minute, DISPATCH_WINDOW_START,
                    )
                await asyncio.sleep(600)
                continue

            # 3. Campanhas ativas
            active_campaigns = get_active_campaigns()
            if not active_campaigns:
                logger.info("📭 Nenhuma campanha ativa. Verificando em 5 min...")
                await asyncio.sleep(300)
                continue

            # 4. Processa cada campanha
            any_work_done = False

            for campaign in active_campaigns:
                campaign_id = campaign.get("id")
                campaign_name = campaign.get("name", "")
                target_tags = campaign.get("target_tags", [])

                # Verifica meta diária
                target = _get_daily_target(campaign_id, campaign)
                sent = _get_daily_sent_count(campaign_id)

                if sent >= target:
                    logger.debug("✅ [%s] Meta atingida (%d/%d).", campaign_name, sent, target)
                    continue

                # Rajada de 1-3 mensagens
                remaining = target - sent
                burst_size = min(
                    remaining,
                    random.choices([1, 2, 3], weights=[0.50, 0.35, 0.15])[0],
                )

                # Leads elegíveis
                leads = get_leads_for_sending(campaign_id, target_tags)
                if not leads:
                    logger.info("📭 [%s] Sem leads elegíveis (%d/%d enviados).", campaign_name, sent, target)
                    continue

                random.shuffle(leads)
                leads_batch = leads[:burst_size]

                logger.info(
                    "🎯 [%s] Rajada de %d msg(s) (Progresso: %d/%d)",
                    campaign_name, len(leads_batch), sent, target,
                )

                # Executa rajada
                for i, lead in enumerate(leads_batch):
                    success = await dispatch_single_lead(lead, campaign)

                    if success:
                        _mark_lead_sent_today(campaign_id, lead.get("phone", ""))
                        any_work_done = True

                    # Pausa intra-rajada
                    if i < len(leads_batch) - 1:
                        intra_wait = random.uniform(15, 45)
                        logger.debug("⏳ Pausa intra-rajada: %.0fs", intra_wait)
                        await asyncio.sleep(intra_wait)

            # 5. Intervalo inteligente
            if any_work_done:
                now_after = _get_now_br()
                hours_left = max(0.5, DISPATCH_WINDOW_END - now_after.hour - (now_after.minute / 60.0))

                total_remaining = 0
                for camp in active_campaigns:
                    cid = camp.get("id")
                    t = _get_daily_target(cid, camp)
                    s = _get_daily_sent_count(cid)
                    total_remaining += max(0, t - s)

                if total_remaining > 0:
                    avg_wait = (hours_left * 3600) / max(1, total_remaining)
                    next_wait = random.uniform(avg_wait * 0.65, avg_wait * 1.35)
                    next_wait = max(30, min(next_wait, 480))
                else:
                    next_wait = 600

                logger.info(
                    "⏳ Próxima rajada em ~%.1f min (Restam %d msgs)",
                    next_wait / 60, total_remaining,
                )
                await asyncio.sleep(next_wait)
            else:
                await asyncio.sleep(300)

        except Exception as e:
            logger.error("Erro no dispatch engine: %s", e, exc_info=True)
            await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════════════════
# STATUS / DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

def get_engine_status() -> Dict[str, Any]:
    """Retorna status completo do motor para o dashboard."""
    _ensure_daily_reset()
    active = get_active_campaigns()
    today = _today_str()

    campaigns_status = []
    for camp in active:
        cid = camp.get("id")
        target = _get_daily_target(cid, camp)
        sent = _get_daily_sent_count(cid)

        campaigns_status.append({
            "id": cid,
            "name": camp.get("name"),
            "status": camp.get("status"),
            "target_today": target,
            "sent_today": sent,
            "total_sent": camp.get("total_sent", 0) or 0,
            "last_dispatch": camp.get("last_dispatch"),
            "funnel_days": camp.get("funnel_days", [1, 2, 3, 5, 7, 14, 30]),
        })

    return {
        "engine_paused": is_engine_paused(),
        "current_date": today,
        "active_campaigns": len(active),
        "campaigns": campaigns_status,
    }


def get_dispatch_log(limit: int = 50, campaign_id: str = None) -> List[Dict[str, Any]]:
    """Retorna log de disparos recentes."""
    sb = get_supabase()
    query = sb.table("dispatch_log").select("*")
    if campaign_id:
        query = query.eq("campaign_id", campaign_id)
    result = query.order("sent_at", desc=True).limit(limit).execute()
    return result.data or []
