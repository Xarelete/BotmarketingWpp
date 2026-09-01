"""
=============================================================================
BotRemarketingIMOB - Parallel Broadcast Manager (Multi-Fila por Número)
=============================================================================
Permite DISPAROS SIMULTÂNEOS em números (instâncias) diferentes, cada um em
sua própria thread e com seu próprio estado — sem colidir.

⚠️ SEGURANÇA ANTI-BLOQUEIO:
  • Um MESMO número NUNCA roda duas filas ao mesmo tempo (trava por instância).
  • Números diferentes PODEM disparar em paralelo.
  • Intervalos randômicos entre envios (humanização).
  • Grupos usam intervalo maior que leads individuais.

Reutiliza 100% o pipeline de envio que já funciona:
  • core.direct_broadcast._format_lead_message (spintax + sinônimos + emojis)
  • platforms.whatsapp_client.send_whatsapp_message_sync (leads)
  • platforms.whatsapp_client.send_whatsapp_group_message_sync (grupos)
"""

import time
import random
import hashlib
import threading
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from config import BR_TZ
from database import get_supabase
from core.lead_manager import get_lead
from core.direct_broadcast import _format_lead_message
from core.group_manager import log_group_dispatch
from platforms.whatsapp_client import (
    send_whatsapp_message_sync,
    send_whatsapp_group_message_sync,
    format_phone_display,
)

logger = logging.getLogger(__name__)

# Uma fila (estado) por instância. Chave = instance_name.
_queues: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _blank_state(instance_name: str, kind: str = "leads") -> Dict[str, Any]:
    return {
        "instance": instance_name,
        "kind": kind,
        "is_running": False,
        "should_cancel": False,
        "total": 0,
        "current": 0,
        "success": 0,
        "failed": 0,
        "current_lead_name": "",
        "current_lead_phone": "",
        "next_send_in_seconds": 0,
        "started_at": "",
        "log": [],
    }


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════════
# STATUS / CONTROLE
# ═══════════════════════════════════════════════════════════════════════

def get_broadcast_status(instance_name: str) -> Dict[str, Any]:
    with _lock:
        state = _queues.get(instance_name)
        return dict(state) if state else _blank_state(instance_name)


def get_all_broadcast_status() -> Dict[str, Any]:
    with _lock:
        return {k: dict(v) for k, v in _queues.items()}


def cancel_broadcast(instance_name: str) -> bool:
    with _lock:
        state = _queues.get(instance_name)
        if state and state["is_running"]:
            state["should_cancel"] = True
            logger.info("🛑 Cancelamento solicitado para fila [%s].", instance_name)
            return True
    return False


def is_instance_busy(instance_name: str) -> bool:
    with _lock:
        state = _queues.get(instance_name)
        return bool(state and state["is_running"])


# ═══════════════════════════════════════════════════════════════════════
# INÍCIO DA FILA
# ═══════════════════════════════════════════════════════════════════════

def start_broadcast(
    instance_name: str,
    targets: List[Any],
    message_template: str,
    image_url: Optional[str] = None,
    min_delay: int = 15,
    max_delay: int = 40,
    vary_text: bool = True,
    vary_synonyms: bool = True,
    kind: str = "leads",
) -> bool:
    """
    Inicia uma fila de disparo para um número. Retorna False se aquele número
    já tem uma fila em andamento (trava anti-ban) ou se targets vazio.

    kind='leads'  -> targets = lista de lead_ids
    kind='groups' -> targets = lista de group_jids (str) ou dicts {group_jid, name}
    """
    if not instance_name or not targets:
        return False

    with _lock:
        state = _queues.get(instance_name)
        if state and state["is_running"]:
            logger.warning("Número [%s] já tem fila em execução.", instance_name)
            return False

        # Grupos exigem intervalo mínimo maior por segurança
        if kind == "groups":
            min_delay = max(40, min_delay)
            max_delay = max(min_delay + 20, max_delay)

        new_state = _blank_state(instance_name, kind)
        new_state.update({
            "is_running": True,
            "total": len(targets),
            "started_at": datetime.now(BR_TZ).isoformat(),
        })
        _queues[instance_name] = new_state

    worker = threading.Thread(
        target=_run_thread,
        args=(instance_name, list(targets), message_template, image_url,
              max(5, int(min_delay)), max(int(min_delay), int(max_delay)),
              vary_text, vary_synonyms, kind),
        daemon=True,
    )
    worker.start()
    logger.info("🚀 Fila [%s] iniciada: %d alvos (kind=%s).", instance_name, len(targets), kind)
    return True


# ═══════════════════════════════════════════════════════════════════════
# EXECUÇÃO
# ═══════════════════════════════════════════════════════════════════════

def _update(instance_name: str, **fields):
    with _lock:
        state = _queues.get(instance_name)
        if state:
            state.update(fields)


def _append_log(instance_name: str, entry: Dict[str, Any]):
    with _lock:
        state = _queues.get(instance_name)
        if state:
            state["log"].insert(0, entry)
            state["log"] = state["log"][:100]


def _cancelled(instance_name: str) -> bool:
    with _lock:
        state = _queues.get(instance_name)
        return bool(state and state["should_cancel"])


def _sleep_interval(instance_name: str, seconds: float):
    """Dorme em passos de 1s atualizando o countdown e respeitando cancelamento."""
    remaining = int(seconds)
    while remaining > 0:
        if _cancelled(instance_name):
            return
        _update(instance_name, next_send_in_seconds=remaining)
        time.sleep(1)
        remaining -= 1
    _update(instance_name, next_send_in_seconds=0)


def _run_thread(
    instance_name: str,
    targets: List[Any],
    message_template: str,
    image_url: Optional[str],
    min_delay: int,
    max_delay: int,
    vary_text: bool,
    vary_synonyms: bool,
    kind: str,
):
    sb = get_supabase()
    try:
        for idx, target in enumerate(targets):
            if _cancelled(instance_name):
                _append_log(instance_name, {
                    "time": datetime.now(BR_TZ).strftime("%H:%M:%S"),
                    "status": "cancelled",
                    "message": "Fila cancelada pelo administrador.",
                })
                break

            _update(instance_name, current=idx + 1)

            if kind == "groups":
                ok = _send_to_group(instance_name, target, message_template, image_url,
                                     vary_text, vary_synonyms)
            else:
                ok = _send_to_lead(instance_name, target, message_template, image_url,
                                   vary_text, vary_synonyms, sb)

            # Intervalo randômico humanizado até o próximo (exceto no último)
            if idx < len(targets) - 1 and not _cancelled(instance_name):
                wait = random.uniform(min_delay, max_delay)
                _sleep_interval(instance_name, wait)

    except Exception as e:
        logger.error("Erro na fila [%s]: %s", instance_name, e, exc_info=True)
    finally:
        _update(instance_name, is_running=False, next_send_in_seconds=0)
        logger.info("🏁 Fila [%s] finalizada.", instance_name)


def _send_to_lead(instance_name, lead_id, template, image_url, vary_text, vary_synonyms, sb) -> bool:
    lead = get_lead(lead_id)
    now_str = datetime.now(BR_TZ).strftime("%H:%M:%S")

    if not lead:
        with _lock:
            if instance_name in _queues:
                _queues[instance_name]["failed"] += 1
        return False

    if lead.get("paused"):
        _append_log(instance_name, {
            "time": now_str, "lead": lead.get("name") or lead.get("phone"),
            "status": "skipped", "message": "Lead com pausa individual.",
        })
        return False

    lead_name = lead.get("name") or "Sem nome"
    lead_phone = lead.get("phone")
    _update(instance_name, current_lead_name=lead_name,
            current_lead_phone=format_phone_display(lead_phone))

    message = _format_lead_message(
        template=template, lead=lead,
        vary_synonyms=vary_synonyms, vary_text=vary_text,
    )

    success, err = send_whatsapp_message_sync(
        phone=lead_phone, text=message, image_url=image_url, instance=instance_name,
    )

    with _lock:
        st = _queues.get(instance_name)
        if st:
            if success:
                st["success"] += 1
            else:
                st["failed"] += 1

    _append_log(instance_name, {
        "time": now_str, "lead": lead_name,
        "phone": format_phone_display(lead_phone),
        "status": "sent" if success else "failed",
        "message": "Enviado com sucesso" if success else err,
    })

    # Registra no dispatch_log (mesma tabela do disparo direto)
    try:
        sb.table("dispatch_log").insert({
            "campaign_id": "broadcast_direto",
            "lead_id": lead.get("id", ""),
            "lead_phone": lead_phone,
            "lead_name": lead_name,
            "remarketing_day": lead.get("remarketing_day", 0) or 0,
            "message_hash": _hash(message),
            "status": "sent" if success else "failed",
            "sent_at": datetime.now(BR_TZ).isoformat(),
            "error_message": "" if success else err,
        }).execute()
    except Exception:
        pass

    return success


def _send_to_group(instance_name, target, template, image_url, vary_text, vary_synonyms) -> bool:
    if isinstance(target, dict):
        group_jid = target.get("group_jid") or target.get("jid") or ""
        group_name = target.get("name", "")
    else:
        group_jid = str(target)
        group_name = group_jid

    now_str = datetime.now(BR_TZ).strftime("%H:%M:%S")
    _update(instance_name, current_lead_name=group_name or "Grupo",
            current_lead_phone=group_jid)

    # Humaniza usando lead vazio (aplica spintax/sinônimos/variação sem nome)
    message = _format_lead_message(
        template=template, lead={"name": "", "phone": ""},
        vary_synonyms=vary_synonyms, vary_text=vary_text,
    )

    success, err = send_whatsapp_group_message_sync(
        group_jid=group_jid, text=message, image_url=image_url, instance=instance_name,
    )

    with _lock:
        st = _queues.get(instance_name)
        if st:
            if success:
                st["success"] += 1
            else:
                st["failed"] += 1

    _append_log(instance_name, {
        "time": now_str, "lead": group_name or group_jid,
        "phone": group_jid,
        "status": "sent" if success else "failed",
        "message": "Publicado no grupo" if success else err,
    })

    log_group_dispatch(
        instance_name=instance_name, group_jid=group_jid, group_name=group_name,
        message_hash=_hash(message), status="sent" if success else "failed",
        error_message="" if success else err,
    )
    return success
