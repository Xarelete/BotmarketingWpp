"""
=============================================================================
BotRemarketingIMOB - Group Manager (Grupos de WhatsApp + Jornal)
=============================================================================
Gerencia os GRUPOS reais de WhatsApp de cada número (instância):
  • Sincroniza grupos via Evolution API.
  • Marca grupos como "Jornal da Construtora" (para publicações periódicas).
  • Vincula grupos a um bolsão/empreendimento (opcional).

Tudo filtrado por instance_name (número dono do grupo).
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import BR_TZ
from database import get_supabase
from platforms.whatsapp_client import list_whatsapp_groups_sync

logger = logging.getLogger(__name__)


def _now_br() -> str:
    return datetime.now(BR_TZ).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# SINCRONIZAÇÃO COM A EVOLUTION API
# ═══════════════════════════════════════════════════════════════════════

def sync_groups(instance_name: str) -> Dict[str, int]:
    """
    Busca os grupos reais do WhatsApp para uma instância e faz upsert em
    whatsapp_groups. Preserva os campos locais (is_journal, pool_id) dos
    grupos já cadastrados.
    Retorna {'found': N, 'saved': N}.
    """
    sb = get_supabase()
    remote_groups = list_whatsapp_groups_sync(instance_name)

    if not remote_groups:
        return {"found": 0, "saved": 0}

    # Carrega grupos já salvos para preservar flags locais
    existing_res = sb.table("whatsapp_groups").select(
        "id, group_jid, is_journal, pool_id"
    ).eq("instance_name", instance_name).execute()
    existing = {r["group_jid"]: r for r in (existing_res.data or [])}

    saved = 0
    for g in remote_groups:
        jid = g["group_jid"]
        prev = existing.get(jid)
        record = {
            "id": prev["id"] if prev else f"grp_{uuid.uuid4().hex[:8]}",
            "group_jid": jid,
            "name": g.get("name", ""),
            "instance_name": instance_name,
            "participants_count": g.get("participants_count", 0),
            "is_journal": prev["is_journal"] if prev else False,
            "pool_id": prev["pool_id"] if prev else None,
            "picture_url": g.get("picture_url", ""),
            "last_synced_at": _now_br(),
        }
        try:
            sb.table("whatsapp_groups").upsert(
                record, on_conflict="instance_name,group_jid"
            ).execute()
            saved += 1
        except Exception as e:
            logger.warning("Falha ao salvar grupo %s: %s", jid, e)

    logger.info("Sync de grupos [%s]: %d encontrados, %d salvos.", instance_name, len(remote_groups), saved)
    return {"found": len(remote_groups), "saved": saved}


# ═══════════════════════════════════════════════════════════════════════
# CONSULTAS / CRUD
# ═══════════════════════════════════════════════════════════════════════

def list_groups(instance_name: str, journal_only: bool = False) -> List[Dict[str, Any]]:
    sb = get_supabase()
    query = sb.table("whatsapp_groups").select("*")
    if instance_name:
        query = query.eq("instance_name", instance_name)
    if journal_only:
        query = query.eq("is_journal", True)
    result = query.order("name").execute()
    return result.data or []


def get_group(group_id: str) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    result = sb.table("whatsapp_groups").select("*").eq("id", group_id).execute()
    return result.data[0] if result.data else None


def set_group_journal(group_id: str, is_journal: bool) -> bool:
    sb = get_supabase()
    result = sb.table("whatsapp_groups").update(
        {"is_journal": bool(is_journal)}
    ).eq("id", group_id).execute()
    return bool(result.data)


def link_group_pool(group_id: str, pool_id: Optional[str]) -> bool:
    sb = get_supabase()
    result = sb.table("whatsapp_groups").update(
        {"pool_id": pool_id or None}
    ).eq("id", group_id).execute()
    return bool(result.data)


def delete_group(group_id: str) -> bool:
    """Remove o grupo do painel (não sai do grupo real no WhatsApp)."""
    sb = get_supabase()
    result = sb.table("whatsapp_groups").delete().eq("id", group_id).execute()
    return bool(result.data)


def log_group_dispatch(
    instance_name: str,
    group_jid: str,
    group_name: str,
    message_hash: str = "",
    status: str = "sent",
    error_message: str = "",
) -> None:
    sb = get_supabase()
    try:
        sb.table("group_dispatch_log").insert({
            "instance_name": instance_name,
            "group_jid": group_jid,
            "group_name": group_name,
            "message_hash": message_hash,
            "status": status,
            "sent_at": _now_br(),
            "error_message": error_message,
        }).execute()
    except Exception as e:
        logger.error("Erro ao registrar group_dispatch_log: %s", e)
