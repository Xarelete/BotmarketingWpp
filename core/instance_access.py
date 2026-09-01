"""
=============================================================================
BotRemarketingIMOB - Instance Access Manager
=============================================================================
Controla o acesso ao painel POR NÚMERO CONECTADO (instância da Evolution API).

Cada número tem:
  • Senha própria (armazenada como hash SHA-256 — nunca em texto plano).
  • Limite diário de envios (proteção anti-bloqueio por número).
  • Flag de aquecimento (warmup) para números novos.

Fluxo de acesso no painel:
  1. Usuário escolhe o número (instância).
  2. Informa a senha daquele número.
  3. Backend valida o hash e grava a instância na sessão.
  4. Todas as consultas passam a ser filtradas por essa instância.

Senha inicial de todos os números neste primeiro momento: "admin".
"""

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from config import BR_TZ
from database import get_supabase

logger = logging.getLogger(__name__)

# Senha padrão inicial (o usuário troca depois pelo painel)
DEFAULT_PASSWORD = "admin"


def hash_password(password: str) -> str:
    """Gera o hash SHA-256 (hex) de uma senha."""
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def _now_br() -> str:
    return datetime.now(BR_TZ).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# LEITURA / LISTAGEM
# ═══════════════════════════════════════════════════════════════════════

def get_instance_access(instance_name: str) -> Optional[Dict[str, Any]]:
    """Retorna o registro de acesso de um número, ou None se não existir."""
    if not instance_name:
        return None
    sb = get_supabase()
    res = sb.table("instance_access").select("*").eq("instance_name", instance_name).execute()
    return res.data[0] if res.data else None


def list_instance_access() -> List[Dict[str, Any]]:
    """Lista todos os números com acesso configurado (sem expor o hash)."""
    sb = get_supabase()
    res = sb.table("instance_access").select(
        "instance_name, display_name, daily_limit, warmup_enabled, active, created_at"
    ).order("created_at").execute()
    return res.data or []


# ═══════════════════════════════════════════════════════════════════════
# CRIAÇÃO / ATUALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════

def ensure_instance_access(instance_name: str, display_name: str = "") -> Dict[str, Any]:
    """
    Garante que um número tenha um registro de acesso.
    Se não existir, cria com a senha padrão "admin".
    Idempotente e seguro para chamar a qualquer momento.
    """
    existing = get_instance_access(instance_name)
    if existing:
        return existing

    sb = get_supabase()
    record = {
        "instance_name": instance_name,
        "display_name": display_name or instance_name,
        "password_hash": hash_password(DEFAULT_PASSWORD),
        "daily_limit": 200,
        "warmup_enabled": True,
        "active": True,
        "created_at": _now_br(),
        "updated_at": _now_br(),
    }
    sb.table("instance_access").upsert(record, on_conflict="instance_name").execute()
    logger.info("🔐 Acesso criado para número '%s' (senha padrão).", instance_name)
    return record


def set_instance_password(instance_name: str, new_password: str) -> bool:
    """Define/atualiza a senha de um número (armazena como hash)."""
    if not instance_name or not new_password:
        return False
    sb = get_supabase()
    ensure_instance_access(instance_name)
    sb.table("instance_access").update({
        "password_hash": hash_password(new_password),
        "updated_at": _now_br(),
    }).eq("instance_name", instance_name).execute()
    logger.info("🔑 Senha do número '%s' atualizada.", instance_name)
    return True


def update_instance_settings(
    instance_name: str,
    display_name: str = None,
    daily_limit: int = None,
    warmup_enabled: bool = None,
    active: bool = None,
) -> bool:
    """Atualiza configurações do número (limites, nome de exibição, etc.)."""
    sb = get_supabase()
    updates: Dict[str, Any] = {"updated_at": _now_br()}
    if display_name is not None:
        updates["display_name"] = display_name
    if daily_limit is not None:
        updates["daily_limit"] = int(daily_limit)
    if warmup_enabled is not None:
        updates["warmup_enabled"] = bool(warmup_enabled)
    if active is not None:
        updates["active"] = bool(active)

    if len(updates) == 1:  # só o updated_at
        return False

    res = sb.table("instance_access").update(updates).eq("instance_name", instance_name).execute()
    return bool(res.data)


# ═══════════════════════════════════════════════════════════════════════
# VALIDAÇÃO DE LOGIN
# ═══════════════════════════════════════════════════════════════════════

def verify_instance_password(instance_name: str, password: str) -> bool:
    """
    Valida a senha de um número. Se o número ainda não tem registro de acesso,
    cria automaticamente com a senha padrão "admin" e valida contra ela.
    Usa comparação de tempo constante (hmac.compare_digest) contra timing attacks.
    """
    if not instance_name:
        return False

    record = get_instance_access(instance_name)
    if not record:
        # Primeiro acesso a este número: cria com senha padrão.
        record = ensure_instance_access(instance_name)

    if not record.get("active", True):
        logger.warning("Tentativa de login em número inativo: %s", instance_name)
        return False

    stored_hash = record.get("password_hash", "")
    provided_hash = hash_password(password)
    return hmac.compare_digest(stored_hash, provided_hash)
