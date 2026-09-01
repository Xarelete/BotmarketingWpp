"""
=============================================================================
BotRemarketingIMOB - Lead Manager (Supabase)
=============================================================================
CRUD completo de leads com suporte a importação em lote, tags de segmentação,
controle de pausa individual, e integração com o funil de remarketing.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import BR_TZ
from database import get_supabase

logger = logging.getLogger(__name__)


def _get_now_br() -> str:
    """Retorna datetime atual (Brasília) como string ISO."""
    return datetime.now(BR_TZ).isoformat()


def _today_br() -> str:
    """Retorna data atual (Brasília) como string YYYY-MM-DD."""
    return datetime.now(BR_TZ).strftime("%Y-%m-%d")


def _normalize_phone(phone: str) -> str:
    """Normaliza telefone para apenas dígitos com código do país."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10 or len(digits) == 11:
        digits = f"55{digits}"
    return digits


# ═══════════════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════════════

def add_lead(
    phone: str,
    name: str = "",
    source: str = "manual",
    tags: List[str] = None,
    added_by: str = "admin",
    notes: str = "",
    instance_name: str = None,
    pool_id: str = None,
) -> Optional[Dict[str, Any]]:
    """Adiciona um lead. Retorna o lead criado ou None se duplicado.

    instance_name/pool_id (opcionais) vinculam o lead a um número e bolsão.
    """
    sb = get_supabase()
    normalized = _normalize_phone(phone)

    # Verifica duplicata
    existing = sb.table("leads").select("id").eq("phone", normalized).execute()
    if existing.data:
        logger.warning("Lead com telefone %s já existe.", phone)
        return None

    lead_id = f"lead_{uuid.uuid4().hex[:8]}"
    clean_tags = [t.strip().lower() for t in (tags or [])]
    now = _get_now_br()

    lead_data = {
        "id": lead_id,
        "name": name.strip(),
        "phone": normalized,
        "source": source.strip(),
        "tags": clean_tags,
        "added_at": now,
        "added_by": added_by,
        "status": "active",
        "notes": notes.strip(),
        "paused": False,
        "remarketing_day": 0,
    }
    if instance_name:
        lead_data["instance_name"] = instance_name
    if pool_id:
        lead_data["pool_id"] = pool_id

    result = sb.table("leads").insert(lead_data).execute()
    if result.data:
        logger.info("Lead adicionado: %s (%s)", name, normalized)
        return result.data[0]
    return None


def remove_lead(identifier: str) -> bool:
    """Remove lead por ID ou telefone."""
    sb = get_supabase()
    normalized = _normalize_phone(identifier)

    # Tenta por ID
    result = sb.table("leads").delete().eq("id", identifier).execute()
    if result.data:
        logger.info("Lead removido por ID: %s", identifier)
        return True

    # Tenta por telefone
    result = sb.table("leads").delete().eq("phone", normalized).execute()
    if result.data:
        logger.info("Lead removido por telefone: %s", normalized)
        return True

    return False


def deactivate_lead(identifier: str) -> bool:
    """Desativa lead (soft delete)."""
    sb = get_supabase()
    normalized = _normalize_phone(identifier)

    result = sb.table("leads").update({"status": "inactive"}).or_(
        f"id.eq.{identifier},phone.eq.{normalized}"
    ).execute()
    if result.data:
        logger.info("Lead desativado: %s", identifier)
        return True
    return False


def reactivate_lead(identifier: str) -> bool:
    """Reativa lead previamente desativado."""
    sb = get_supabase()
    normalized = _normalize_phone(identifier)

    result = sb.table("leads").update({"status": "active"}).or_(
        f"id.eq.{identifier},phone.eq.{normalized}"
    ).execute()
    if result.data:
        logger.info("Lead reativado: %s", identifier)
        return True
    return False


def pause_lead(identifier: str, reason: str = "") -> bool:
    """Pausa envios para um lead (não perde progresso no funil)."""
    sb = get_supabase()
    lead = get_lead(identifier)
    if not lead:
        return False

    sb.table("leads").update({"paused": True}).eq("id", lead["id"]).execute()
    sb.table("paused_numbers").upsert({
        "phone": lead["phone"],
        "paused_at": _get_now_br(),
        "reason": reason,
    }).execute()
    logger.info("Lead pausado: %s", identifier)
    return True


def resume_lead(identifier: str) -> bool:
    """Retoma envios para um lead pausado."""
    sb = get_supabase()
    lead = get_lead(identifier)
    if not lead:
        return False

    sb.table("leads").update({"paused": False}).eq("id", lead["id"]).execute()
    sb.table("paused_numbers").delete().eq("phone", lead["phone"]).execute()
    logger.info("Lead retomado: %s", identifier)
    return True


def update_lead_tags(identifier: str, tags: List[str], mode: str = "add") -> bool:
    """Atualiza tags. mode: 'add', 'remove', 'set'."""
    sb = get_supabase()
    lead = get_lead(identifier)
    if not lead:
        return False

    current_tags = lead.get("tags", [])
    clean_tags = [t.strip().lower() for t in tags if t.strip()]

    if mode == "add":
        new_tags = list(set(current_tags + clean_tags))
    elif mode == "remove":
        new_tags = [t for t in current_tags if t not in clean_tags]
    elif mode == "set":
        new_tags = clean_tags
    else:
        return False

    sb.table("leads").update({"tags": new_tags}).eq("id", lead["id"]).execute()
    logger.info("Tags atualizadas para %s: %s", identifier, new_tags)
    return True


def update_lead_remarketing(
    lead_id: str,
    remarketing_day: int = None,
    next_send_date: str = None,
    entered_pool_at: str = None,
    status: str = None,
    completed_at: str = None,
) -> bool:
    """Atualiza campos de remarketing de um lead."""
    sb = get_supabase()
    updates = {}

    if remarketing_day is not None:
        updates["remarketing_day"] = remarketing_day
    if next_send_date is not None:
        updates["next_send_date"] = next_send_date if next_send_date else None
    if entered_pool_at is not None:
        updates["entered_pool_at"] = entered_pool_at
    if status is not None:
        updates["status"] = status
    if completed_at is not None:
        updates["completed_at"] = completed_at

    if not updates:
        return False

    result = sb.table("leads").update(updates).eq("id", lead_id).execute()
    return bool(result.data)


# ═══════════════════════════════════════════════════════════════════════
# CONSULTAS
# ═══════════════════════════════════════════════════════════════════════

def list_leads(
    status: str = None,
    tags: List[str] = None,
    search: str = None,
    limit: int = 50,
    paused_only: bool = False,
    instance_name: str = None,
    pool_id: str = None,
) -> List[Dict[str, Any]]:
    """Lista leads com filtros. instance_name/pool_id filtram por número/bolsão."""
    sb = get_supabase()
    query = sb.table("leads").select("*")

    if status:
        query = query.eq("status", status)
    if instance_name:
        query = query.eq("instance_name", instance_name)
    if pool_id:
        query = query.eq("pool_id", pool_id)
    if paused_only:
        query = query.eq("paused", True)
    if search:
        query = query.or_(
            f"name.ilike.%{search}%,phone.ilike.%{search}%,notes.ilike.%{search}%"
        )

    query = query.order("added_at", desc=True).limit(limit)
    result = query.execute()
    leads = result.data or []

    # Filtro por tags (feito em Python para suportar JSONB contains)
    if tags:
        search_tags = set(t.strip().lower() for t in tags)
        leads = [
            l for l in leads
            if set(l.get("tags", [])).intersection(search_tags)
        ]

    return leads


def get_lead(identifier: str) -> Optional[Dict[str, Any]]:
    """Busca lead por ID ou telefone."""
    sb = get_supabase()
    normalized = _normalize_phone(identifier)

    # Tenta por ID
    result = sb.table("leads").select("*").eq("id", identifier).execute()
    if result.data:
        return result.data[0]

    # Tenta por telefone
    result = sb.table("leads").select("*").eq("phone", normalized).execute()
    if result.data:
        return result.data[0]

    return None


def count_leads(status: str = None) -> int:
    """Conta leads."""
    sb = get_supabase()
    query = sb.table("leads").select("id", count="exact")
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.count if result.count is not None else len(result.data or [])


def get_leads_by_tags(tags: List[str], status: str = "active") -> List[Dict[str, Any]]:
    """Retorna leads ativos com pelo menos uma das tags."""
    return list_leads(status=status, tags=tags, limit=99999)


def get_leads_for_sending(
    campaign_id: str,
    target_tags: List[str] = None,
    today: str = None,
    instance_name: str = None,
    pool_id: str = None,
) -> List[Dict[str, Any]]:
    """
    Retorna leads elegíveis para envio HOJE:
    - Status ativo, não pausado
    - next_send_date <= hoje (ou nulo = ainda não no funil)
    - Não enviado hoje nesta campanha
    - (opcional) filtrado por número (instance_name) e bolsão (pool_id)
    """
    sb = get_supabase()
    if today is None:
        today = _today_br()

    # Busca leads que já receberam hoje nesta campanha
    sent_today = sb.table("daily_tracking").select("lead_phone").eq(
        "campaign_id", campaign_id
    ).eq("sent_date", today).execute()
    sent_phones = set(r["lead_phone"] for r in (sent_today.data or []))

    # Busca leads ativos e não pausados
    query = sb.table("leads").select("*").eq("status", "active").eq("paused", False)
    if instance_name:
        query = query.eq("instance_name", instance_name)
    if pool_id:
        query = query.eq("pool_id", pool_id)
    result = query.order("remarketing_day", desc=False).execute()
    leads = result.data or []

    eligible = []
    for lead in leads:
        # Pula se já enviou hoje
        if lead["phone"] in sent_phones:
            continue

        # Verifica data de próximo envio
        next_date = lead.get("next_send_date")
        if next_date and str(next_date) > today:
            continue

        # Filtro por tags
        if target_tags:
            lead_tags = set(lead.get("tags", []))
            search_tags = set(t.strip().lower() for t in target_tags)
            if not lead_tags.intersection(search_tags):
                continue

        eligible.append(lead)

    return eligible


def get_leads_stats() -> Dict[str, Any]:
    """Estatísticas gerais dos leads."""
    sb = get_supabase()

    total = sb.table("leads").select("id", count="exact").execute()
    active = sb.table("leads").select("id", count="exact").eq("status", "active").execute()
    paused = sb.table("leads").select("id", count="exact").eq("paused", True).execute()
    in_funnel = sb.table("leads").select("id", count="exact").eq(
        "status", "active"
    ).gt("remarketing_day", 0).execute()
    completed = sb.table("leads").select("id", count="exact").eq("status", "completed").execute()
    converted = sb.table("leads").select("id", count="exact").eq("status", "converted").execute()

    return {
        "total": total.count or 0,
        "active": active.count or 0,
        "paused": paused.count or 0,
        "in_funnel": in_funnel.count or 0,
        "completed": completed.count or 0,
        "converted": converted.count or 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# IMPORTAÇÃO EM LOTE
# ═══════════════════════════════════════════════════════════════════════

def import_leads_from_json(json_data: List[Dict[str, Any]], added_by: str = "import") -> Dict[str, int]:
    """Importa leads em lote a partir de lista JSON."""
    counters = {"added": 0, "skipped": 0, "errors": 0}

    for item in json_data:
        try:
            phone = str(item.get("phone", "")).strip()
            name = str(item.get("name", "")).strip()
            if not phone:
                counters["errors"] += 1
                continue

            result = add_lead(
                phone=phone, name=name,
                source=str(item.get("source", "import")),
                tags=item.get("tags", []),
                added_by=added_by,
                notes=str(item.get("notes", "")),
            )
            if result:
                counters["added"] += 1
            else:
                counters["skipped"] += 1
        except Exception as e:
            logger.error("Erro ao importar lead: %s", e)
            counters["errors"] += 1

    logger.info(
        "Importação: %d adicionados, %d duplicados, %d erros",
        counters["added"], counters["skipped"], counters["errors"],
    )
    return counters


def import_leads_from_csv_text(csv_text: str, added_by: str = "csv_import") -> Dict[str, int]:
    """Importa leads a partir de texto CSV."""
    lines = csv_text.strip().split("\n")
    counters = {"added": 0, "skipped": 0, "errors": 0}

    for i, line in enumerate(lines):
        if i == 0:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 1 or not parts[0]:
            counters["errors"] += 1
            continue

        phone = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        tags = [t.strip() for t in parts[2].split(";")] if len(parts) > 2 and parts[2] else []
        notes = parts[3] if len(parts) > 3 else ""

        result = add_lead(phone=phone, name=name, tags=tags, added_by=added_by, notes=notes)
        if result:
            counters["added"] += 1
        else:
            counters["skipped"] += 1

    return counters


def export_leads_json() -> str:
    """Exporta todos os leads como JSON."""
    leads = list_leads(limit=99999)
    return json.dumps(leads, indent=2, ensure_ascii=False, default=str)
