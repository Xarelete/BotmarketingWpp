"""
=============================================================================
BotRemarketingIMOB - Segment Manager (Listas internas de leads)
=============================================================================
Segmentos são LISTAS reutilizáveis de leads (ex: "Interessados 3 quartos",
"VIP", "Retorno urgente") usadas para disparos direcionados.

Sempre vinculados a um número (instance_name) e, opcionalmente, a um bolsão.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import BR_TZ
from database import get_supabase

logger = logging.getLogger(__name__)


def _now_br() -> str:
    return datetime.now(BR_TZ).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# CRUD DE SEGMENTOS
# ═══════════════════════════════════════════════════════════════════════

def create_segment(
    name: str,
    instance_name: str,
    pool_id: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    sb = get_supabase()
    seg_id = f"seg_{uuid.uuid4().hex[:8]}"
    data = {
        "id": seg_id,
        "name": name.strip(),
        "instance_name": instance_name,
        "pool_id": pool_id or None,
        "description": (description or "").strip(),
        "created_at": _now_br(),
    }
    result = sb.table("lead_segments").insert(data).execute()
    seg = result.data[0] if result.data else data
    logger.info("Segmento criado: %s (%s)", name, seg_id)
    return seg


def list_segments(instance_name: str) -> List[Dict[str, Any]]:
    sb = get_supabase()
    query = sb.table("lead_segments").select("*")
    if instance_name:
        query = query.eq("instance_name", instance_name)
    result = query.order("created_at", desc=True).execute()
    segments = result.data or []

    # Anexa a contagem de membros de cada segmento
    for seg in segments:
        count_res = sb.table("segment_members").select(
            "lead_id", count="exact"
        ).eq("segment_id", seg["id"]).execute()
        seg["member_count"] = count_res.count or 0
    return segments


def get_segment(segment_id: str) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    result = sb.table("lead_segments").select("*").eq("id", segment_id).execute()
    return result.data[0] if result.data else None


def delete_segment(segment_id: str) -> bool:
    sb = get_supabase()
    result = sb.table("lead_segments").delete().eq("id", segment_id).execute()
    return bool(result.data)


# ═══════════════════════════════════════════════════════════════════════
# MEMBROS
# ═══════════════════════════════════════════════════════════════════════

def add_members(segment_id: str, lead_ids: List[str]) -> int:
    """Adiciona leads a um segmento. Retorna quantos foram adicionados."""
    sb = get_supabase()
    added = 0
    for lead_id in lead_ids:
        try:
            sb.table("segment_members").upsert({
                "segment_id": segment_id,
                "lead_id": lead_id,
                "added_at": _now_br(),
            }, on_conflict="segment_id,lead_id").execute()
            added += 1
        except Exception:
            pass
    logger.info("Segmento %s: %d membros adicionados.", segment_id, added)
    return added


def remove_member(segment_id: str, lead_id: str) -> bool:
    sb = get_supabase()
    result = sb.table("segment_members").delete().eq(
        "segment_id", segment_id
    ).eq("lead_id", lead_id).execute()
    return bool(result.data)


def get_segment_lead_ids(segment_id: str) -> List[str]:
    sb = get_supabase()
    result = sb.table("segment_members").select("lead_id").eq(
        "segment_id", segment_id
    ).execute()
    return [r["lead_id"] for r in (result.data or [])]
