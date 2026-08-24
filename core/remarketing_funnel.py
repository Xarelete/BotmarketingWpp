"""
=============================================================================
BotRemarketingIMOB - Remarketing Funnel
=============================================================================
Sistema de bolsão de leads com progressão por dias de remarketing.
Cada campanha tem seu próprio funil customizável (ex: D1, D2, D3, D5, D7, D14, D30).

Fluxo:
  1. Lead entra no bolsão → remarketing_day=0, next_send_date=hoje
  2. Recebe msg do D1 → avança para D2, next_send_date=amanhã
  3. Recebe msg do D2 → avança para D3, next_send_date=amanhã
  4. Recebe msg do D3 → avança para D5, next_send_date=+2 dias
  5. ... até completar todos os dias do funil
  6. Lead "completa" → status=completed
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from config import BR_TZ
from database import get_supabase
from models import DEFAULT_FUNNEL_DAYS

logger = logging.getLogger(__name__)


def _today_br() -> str:
    return datetime.now(BR_TZ).strftime("%Y-%m-%d")


def _get_now_br() -> str:
    return datetime.now(BR_TZ).isoformat()


def _date_plus_days(base_date: str, days: int) -> str:
    """Adiciona N dias a uma data YYYY-MM-DD."""
    dt = datetime.strptime(base_date, "%Y-%m-%d")
    return (dt + timedelta(days=days)).strftime("%Y-%m-%d")


def get_funnel_days(campaign: Dict[str, Any]) -> List[int]:
    """Retorna os dias do funil de uma campanha (ordenados)."""
    days = campaign.get("funnel_days", DEFAULT_FUNNEL_DAYS)
    if isinstance(days, list) and len(days) > 0:
        return sorted(days)
    return DEFAULT_FUNNEL_DAYS


def get_next_funnel_day(campaign: Dict[str, Any], current_day: int) -> Optional[int]:
    """
    Retorna o próximo dia do funil após o dia atual.
    Retorna None se o lead completou o funil.
    """
    funnel_days = get_funnel_days(campaign)

    if current_day == 0:
        # Lead ainda não entrou no funil — começa no primeiro dia
        return funnel_days[0] if funnel_days else None

    # Busca o próximo dia após o atual
    for day in funnel_days:
        if day > current_day:
            return day

    # Completou o funil
    return None


def get_days_until_next(campaign: Dict[str, Any], current_day: int, next_day: int) -> int:
    """
    Calcula quantos dias calendário esperar entre o dia atual e o próximo.
    Ex: Se current=3 e next=5, espera 2 dias.
        Se current=7 e next=14, espera 7 dias.
        Se current=0 e next=1, espera 0 dias (envia hoje).
    """
    if current_day == 0:
        return 0  # Primeiro contato é imediato

    return max(1, next_day - current_day)


def enter_pool(lead_id: str, campaign: Dict[str, Any]) -> bool:
    """
    Coloca um lead no bolsão de remarketing.
    Define remarketing_day=0 e next_send_date=hoje (pronto para envio).
    """
    sb = get_supabase()
    today = _today_br()
    now = _get_now_br()

    result = sb.table("leads").update({
        "remarketing_day": 0,
        "next_send_date": today,
        "entered_pool_at": now,
        "status": "active",
    }).eq("id", lead_id).execute()

    if result.data:
        logger.info("Lead %s entrou no bolsão de remarketing", lead_id)
        return True
    return False


def advance_lead(lead_id: str, campaign: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avança um lead para o próximo dia do funil após envio bem-sucedido.

    Retorna:
        {"advanced": True/False, "next_day": int|None, "completed": bool}
    """
    sb = get_supabase()
    today = _today_br()

    # Busca lead atual
    lead_result = sb.table("leads").select("*").eq("id", lead_id).execute()
    if not lead_result.data:
        return {"advanced": False, "next_day": None, "completed": False}

    lead = lead_result.data[0]
    current_day = lead.get("remarketing_day", 0)

    # Determina próximo dia do funil
    funnel_days = get_funnel_days(campaign)
    next_day = get_next_funnel_day(campaign, current_day)

    if next_day is None:
        # Lead completou o funil!
        sb.table("leads").update({
            "status": "completed",
            "completed_at": _get_now_br(),
        }).eq("id", lead_id).execute()
        logger.info("Lead %s completou o funil de remarketing!", lead_id)
        return {"advanced": True, "next_day": None, "completed": True}

    # Calcula data do próximo envio
    # O current_day agora é o dia que ACABOU de ser enviado
    # Precisamos do dia APÓS next_day para calcular a espera
    if current_day == 0:
        # Primeiro contato aconteceu agora, próximo é o segundo dia do funil
        actual_current = funnel_days[0] if funnel_days else 1
    else:
        actual_current = current_day

    # Encontra o dia que acabou de ser enviado e o próximo
    days_to_wait = get_days_until_next(campaign, actual_current, next_day)
    next_send = _date_plus_days(today, days_to_wait)

    # Atualiza lead
    sb.table("leads").update({
        "remarketing_day": actual_current if current_day == 0 else next_day,
        "next_send_date": next_send,
    }).eq("id", lead_id).execute()

    logger.info(
        "Lead %s avançou: D%d → D%d (próximo envio: %s)",
        lead_id, actual_current, next_day, next_send,
    )
    return {"advanced": True, "next_day": next_day, "completed": False}


def get_current_send_day(lead: Dict[str, Any], campaign: Dict[str, Any]) -> int:
    """
    Retorna qual dia do funil este lead deve receber AGORA.
    Considera o remarketing_day atual do lead.
    """
    current_day = lead.get("remarketing_day", 0)
    funnel_days = get_funnel_days(campaign)

    if current_day == 0:
        # Primeiro contato
        return funnel_days[0] if funnel_days else 1

    # Retorna o próximo dia que ele precisa receber
    next_day = get_next_funnel_day(campaign, current_day)
    return next_day if next_day else current_day


def get_funnel_stats(campaign_id: str) -> Dict[str, Any]:
    """Retorna estatísticas do funil de uma campanha."""
    sb = get_supabase()

    campaign = sb.table("campaigns").select("funnel_days").eq("id", campaign_id).execute()
    if not campaign.data:
        return {}

    funnel_days = campaign.data[0].get("funnel_days", DEFAULT_FUNNEL_DAYS)

    # Conta leads em cada dia do funil
    leads = sb.table("leads").select("remarketing_day, status").eq(
        "status", "active"
    ).execute()
    all_leads = leads.data or []

    day_counts = {}
    for day in funnel_days:
        day_counts[day] = sum(1 for l in all_leads if l.get("remarketing_day", 0) == day)

    # Leads que ainda não entraram (day=0)
    waiting = sum(1 for l in all_leads if l.get("remarketing_day", 0) == 0)

    # Leads completados
    completed = sb.table("leads").select("id", count="exact").eq("status", "completed").execute()

    return {
        "funnel_days": funnel_days,
        "day_counts": day_counts,
        "waiting": waiting,
        "completed": completed.count or 0,
    }


def reset_lead_funnel(lead_id: str) -> bool:
    """Reseta um lead para o início do funil."""
    sb = get_supabase()
    result = sb.table("leads").update({
        "remarketing_day": 0,
        "next_send_date": _today_br(),
        "status": "active",
        "completed_at": None,
    }).eq("id", lead_id).execute()

    if result.data:
        logger.info("Lead %s resetado para início do funil", lead_id)
        return True
    return False


def bulk_enter_pool(campaign_id: str) -> int:
    """
    Coloca TODOS os leads elegíveis de uma campanha no bolsão.
    Retorna quantos leads foram adicionados.
    """
    sb = get_supabase()
    campaign = sb.table("campaigns").select("*").eq("id", campaign_id).execute()
    if not campaign.data:
        return 0

    camp = campaign.data[0]
    target_tags = camp.get("target_tags", [])
    today = _today_br()
    now = _get_now_br()

    # Busca leads ativos que ainda não entraram no funil
    query = sb.table("leads").select("*").eq("status", "active").eq("remarketing_day", 0)
    result = query.execute()
    leads = result.data or []

    count = 0
    for lead in leads:
        # Filtro por tags (se campanha tem tags definidas)
        if target_tags:
            lead_tags = set(lead.get("tags", []))
            search_tags = set(t.strip().lower() for t in target_tags)
            if not lead_tags.intersection(search_tags):
                continue

        # Já tem data de envio definida? Pula
        if lead.get("next_send_date") and lead.get("entered_pool_at"):
            continue

        sb.table("leads").update({
            "next_send_date": today,
            "entered_pool_at": now,
        }).eq("id", lead["id"]).execute()
        count += 1

    logger.info("Bulk enter pool: %d leads adicionados ao bolsão da campanha %s", count, campaign_id)
    return count
