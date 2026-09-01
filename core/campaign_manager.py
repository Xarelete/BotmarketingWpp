"""
=============================================================================
BotRemarketingIMOB - Campaign Manager (Supabase)
=============================================================================
Gerenciamento de campanhas de remarketing: criar, pausar, retomar, remover,
listar, editar. Cada campanha tem dias de funil customizáveis e mensagens
configuráveis por dia.
"""

import uuid
import random
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import BR_TZ, DAILY_TARGET_MIN, DAILY_TARGET_MAX
from database import get_supabase
from models import DEFAULT_FUNNEL_DAYS

logger = logging.getLogger(__name__)


def _get_now_br() -> str:
    return datetime.now(BR_TZ).isoformat()


def _today_br() -> str:
    return datetime.now(BR_TZ).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════════════

def create_campaign(
    name: str,
    target_tags: List[str],
    message_template_key: str = "reativacao_geral",
    custom_data: Dict[str, Any] = None,
    schedule: Dict[str, Any] = None,
    funnel_days: List[int] = None,
    instance_name: str = None,
    pool_id: str = None,
) -> Dict[str, Any]:
    """Cria uma nova campanha de remarketing.

    instance_name/pool_id (opcionais) vinculam a campanha a um número/bolsão.
    """
    sb = get_supabase()

    default_schedule = {
        "window_start": 8,
        "window_end": 20,
        "daily_target_min": DAILY_TARGET_MIN,
        "daily_target_max": DAILY_TARGET_MAX,
        "interval_min_seconds": 30,
        "interval_max_seconds": 180,
    }
    if schedule:
        default_schedule.update(schedule)

    campaign_data = {
        "id": f"camp_{uuid.uuid4().hex[:8]}",
        "name": name.strip(),
        "status": "active",
        "type": "remarketing",
        "target_tags": [t.strip().lower() for t in target_tags],
        "message_template_key": message_template_key,
        "custom_data": custom_data or {
            "empreendimento": "",
            "destaque": "",
            "link": "",
            "image_url": "",
            "preco": "",
            "condicoes": "",
        },
        "schedule": default_schedule,
        "funnel_days": funnel_days or DEFAULT_FUNNEL_DAYS,
        "created_at": _get_now_br(),
        "total_sent": 0,
        "total_failed": 0,
        "total_leads_reached": 0,
        "daily_sent_today": 0,
        "stats_current_date": _today_br(),
    }

    result = sb.table("campaigns").insert(campaign_data).execute()
    campaign = result.data[0] if result.data else campaign_data
    logger.info("Campanha criada: %s (ID: %s)", name, campaign_data["id"])
    return campaign


def get_campaign(campaign_id: str) -> Optional[Dict[str, Any]]:
    """Busca campanha por ID."""
    sb = get_supabase()
    result = sb.table("campaigns").select("*").eq("id", campaign_id).execute()
    return result.data[0] if result.data else None


def pause_campaign(campaign_id: str) -> bool:
    """Pausa uma campanha."""
    sb = get_supabase()
    result = sb.table("campaigns").update({"status": "paused"}).eq("id", campaign_id).execute()
    if result.data:
        logger.info("Campanha pausada: %s", campaign_id)
        return True
    return False


def resume_campaign(campaign_id: str) -> bool:
    """Retoma uma campanha pausada."""
    sb = get_supabase()
    result = sb.table("campaigns").update({"status": "active"}).eq("id", campaign_id).execute()
    if result.data:
        logger.info("Campanha retomada: %s", campaign_id)
        return True
    return False


def remove_campaign(campaign_id: str) -> bool:
    """Remove uma campanha definitivamente."""
    sb = get_supabase()
    result = sb.table("campaigns").delete().eq("id", campaign_id).execute()
    if result.data:
        logger.info("Campanha removida: %s", campaign_id)
        return True
    return False


def update_campaign_data(campaign_id: str, custom_data: Dict[str, Any]) -> bool:
    """Atualiza dados customizados de uma campanha (merge)."""
    sb = get_supabase()
    campaign = get_campaign(campaign_id)
    if not campaign:
        return False

    existing = campaign.get("custom_data", {})
    existing.update(custom_data)

    result = sb.table("campaigns").update({"custom_data": existing}).eq("id", campaign_id).execute()
    if result.data:
        logger.info("Dados da campanha %s atualizados", campaign_id)
        return True
    return False


def update_campaign_schedule(campaign_id: str, schedule_updates: Dict[str, Any]) -> bool:
    """Atualiza configurações de agendamento."""
    sb = get_supabase()
    campaign = get_campaign(campaign_id)
    if not campaign:
        return False

    existing = campaign.get("schedule", {})
    existing.update(schedule_updates)

    result = sb.table("campaigns").update({"schedule": existing}).eq("id", campaign_id).execute()
    return bool(result.data)


def update_campaign_funnel_days(campaign_id: str, days: List[int]) -> bool:
    """Atualiza os dias do funil de uma campanha."""
    sb = get_supabase()
    sorted_days = sorted(set(days))
    result = sb.table("campaigns").update({"funnel_days": sorted_days}).eq("id", campaign_id).execute()
    if result.data:
        logger.info("Funil da campanha %s atualizado: %s", campaign_id, sorted_days)
        return True
    return False


def update_campaign_stats(
    campaign_id: str,
    sent: int = 0,
    failed: int = 0,
    leads_reached: int = 0,
) -> None:
    """Incrementa estatísticas de uma campanha."""
    sb = get_supabase()
    campaign = get_campaign(campaign_id)
    if not campaign:
        return

    today = _today_br()
    now = _get_now_br()

    # Reset diário
    daily_today = campaign.get("daily_sent_today", 0)
    if campaign.get("stats_current_date") != today:
        daily_today = 0

    updates = {
        "total_sent": (campaign.get("total_sent", 0) or 0) + sent,
        "total_failed": (campaign.get("total_failed", 0) or 0) + failed,
        "total_leads_reached": (campaign.get("total_leads_reached", 0) or 0) + leads_reached,
        "daily_sent_today": daily_today + sent,
        "stats_current_date": today,
        "last_dispatch": now,
    }

    sb.table("campaigns").update(updates).eq("id", campaign_id).execute()


# ═══════════════════════════════════════════════════════════════════════
# MENSAGENS POR DIA DO FUNIL
# ═══════════════════════════════════════════════════════════════════════

def set_day_message(campaign_id: str, day: int, message_text: str) -> bool:
    """Define/atualiza a mensagem customizada para um dia do funil."""
    sb = get_supabase()
    now = _get_now_br()

    result = sb.table("day_messages").upsert({
        "campaign_id": campaign_id,
        "day": day,
        "message_text": message_text,
        "is_custom": True,
        "created_at": now,
        "updated_at": now,
    }, on_conflict="campaign_id,day").execute()

    if result.data:
        logger.info("Mensagem do dia %d atualizada para campanha %s", day, campaign_id)
        return True
    return False


def get_day_message(campaign_id: str, day: int) -> Optional[str]:
    """Retorna a mensagem customizada para um dia específico."""
    sb = get_supabase()
    result = sb.table("day_messages").select("message_text").eq(
        "campaign_id", campaign_id
    ).eq("day", day).execute()

    if result.data:
        return result.data[0]["message_text"]
    return None


def get_all_day_messages(campaign_id: str) -> List[Dict[str, Any]]:
    """Retorna todas as mensagens customizadas de uma campanha."""
    sb = get_supabase()
    result = sb.table("day_messages").select("*").eq(
        "campaign_id", campaign_id
    ).order("day").execute()
    return result.data or []


def delete_day_message(campaign_id: str, day: int) -> bool:
    """Remove a mensagem customizada de um dia."""
    sb = get_supabase()
    result = sb.table("day_messages").delete().eq(
        "campaign_id", campaign_id
    ).eq("day", day).execute()
    return bool(result.data)


# ═══════════════════════════════════════════════════════════════════════
# CONSULTAS
# ═══════════════════════════════════════════════════════════════════════

def list_campaigns(status: str = None, instance_name: str = None) -> List[Dict[str, Any]]:
    """Lista campanhas, opcionalmente filtrando por status e/ou número."""
    sb = get_supabase()
    query = sb.table("campaigns").select("*")
    if status:
        query = query.eq("status", status)
    if instance_name:
        query = query.eq("instance_name", instance_name)
    result = query.order("created_at", desc=True).execute()

    campaigns = result.data or []
    # Adiciona campo "stats" para compatibilidade
    for camp in campaigns:
        camp["stats"] = {
            "total_sent": camp.get("total_sent", 0),
            "total_failed": camp.get("total_failed", 0),
            "total_leads_reached": camp.get("total_leads_reached", 0),
            "last_dispatch": camp.get("last_dispatch"),
            "daily_sent_today": camp.get("daily_sent_today", 0),
            "current_date": camp.get("stats_current_date"),
        }
    return campaigns


def get_active_campaigns() -> List[Dict[str, Any]]:
    """Retorna apenas campanhas ativas."""
    return list_campaigns(status="active")


def get_campaign_daily_sent(campaign_id: str) -> int:
    """Retorna quantas mensagens foram enviadas hoje."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return 0

    today = _today_br()
    if campaign.get("stats_current_date") != today:
        return 0
    return campaign.get("daily_sent_today", 0) or 0


def get_campaign_daily_target(campaign_id: str) -> int:
    """Retorna a meta diária (sorteada entre min e max)."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return 0

    schedule = campaign.get("schedule", {})
    return random.randint(
        schedule.get("daily_target_min", DAILY_TARGET_MIN),
        schedule.get("daily_target_max", DAILY_TARGET_MAX),
    )
