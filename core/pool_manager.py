"""
=============================================================================
BotRemarketingIMOB - Pool Manager (Bolsões por Empreendimento)
=============================================================================
Cada bolsão (pool) agrupa leads e campanhas de um EMPREENDIMENTO específico,
sempre vinculado a um NÚMERO conectado (instance_name).

Tudo aqui é filtrado por instância para garantir separação total dos dados
por número.
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


DEFAULT_EMPREENDIMENTO = {
    "empreendimento": "",
    "destaque": "",
    "link": "",
    "image_url": "",
    "preco": "",
    "condicoes": "",
}


# ═══════════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════════

def create_pool(
    name: str,
    instance_name: str,
    description: str = "",
    color: str = "#25D366",
    empreendimento_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Cria um novo bolsão (empreendimento) para um número."""
    sb = get_supabase()
    pool_id = f"pool_{uuid.uuid4().hex[:8]}"
    data = {
        "id": pool_id,
        "name": name.strip(),
        "instance_name": instance_name,
        "description": (description or "").strip(),
        "color": color or "#25D366",
        "empreendimento_data": empreendimento_data or dict(DEFAULT_EMPREENDIMENTO),
        "status": "active",
        "created_at": _now_br(),
    }
    result = sb.table("pools").insert(data).execute()
    pool = result.data[0] if result.data else data
    logger.info("Bolsão criado: %s (%s) para número %s", name, pool_id, instance_name)
    return pool


def get_pool(pool_id: str) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    result = sb.table("pools").select("*").eq("id", pool_id).execute()
    return result.data[0] if result.data else None


def list_pools(instance_name: str) -> List[Dict[str, Any]]:
    """Lista bolsões de um número (instância)."""
    sb = get_supabase()
    query = sb.table("pools").select("*")
    if instance_name:
        query = query.eq("instance_name", instance_name)
    result = query.order("created_at", desc=True).execute()
    return result.data or []


def update_pool(pool_id: str, **fields) -> bool:
    """Atualiza campos de um bolsão. Campos aceitos: name, description, color,
    empreendimento_data, status."""
    sb = get_supabase()
    allowed = {"name", "description", "color", "empreendimento_data", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    result = sb.table("pools").update(updates).eq("id", pool_id).execute()
    return bool(result.data)


def delete_pool(pool_id: str) -> bool:
    """
    Remove um bolsão. Os leads NÃO são apagados — apenas desvinculados
    (pool_id volta a NULL), preservando os dados.
    """
    sb = get_supabase()
    # Desvincula leads e campanhas deste bolsão
    try:
        sb.table("leads").update({"pool_id": None}).eq("pool_id", pool_id).execute()
        sb.table("campaigns").update({"pool_id": None}).eq("pool_id", pool_id).execute()
    except Exception as e:
        logger.warning("Falha ao desvincular itens do bolsão %s: %s", pool_id, e)

    result = sb.table("pools").delete().eq("id", pool_id).execute()
    if result.data:
        logger.info("Bolsão removido: %s", pool_id)
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# ESTATÍSTICAS
# ═══════════════════════════════════════════════════════════════════════

def get_pool_stats(pool_id: str) -> Dict[str, Any]:
    """Contagens de leads de um bolsão."""
    sb = get_supabase()

    total = sb.table("leads").select("id", count="exact").eq("pool_id", pool_id).execute()
    active = sb.table("leads").select("id", count="exact").eq(
        "pool_id", pool_id
    ).eq("status", "active").execute()
    in_funnel = sb.table("leads").select("id", count="exact").eq(
        "pool_id", pool_id
    ).eq("status", "active").gt("remarketing_day", 0).execute()

    converted = sb.table("leads").select("id", count="exact").eq("pool_id", pool_id).eq("status", "converted").execute()

    return {
        "pool_id": pool_id,
        "total": total.count or 0,
        "active": active.count or 0,
        "in_funnel": in_funnel.count or 0,
        "converted": converted.count or 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# ASSOCIAÇÃO DE LEADS
# ═══════════════════════════════════════════════════════════════════════

def add_leads_to_pool(pool_id, lead_ids):
    """Associate existing leads to a pool by setting their pool_id."""
    if not lead_ids:
        return 0
    sb = get_supabase()
    res = sb.table("leads").update({"pool_id": pool_id}).in_("id", lead_ids).execute()
    return len(res.data) if getattr(res, "data", None) else 0

def add_number_to_pool(pool_id, instance_name, phone, name="", tags=None):
    """Create a new lead already tied to this pool."""
    from core.lead_manager import add_lead
    return add_lead(phone=phone, name=name, tags=tags or [], added_by="web_admin", instance_name=instance_name, pool_id=pool_id)
