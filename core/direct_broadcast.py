"""
=============================================================================
BotRemarketingIMOB - Direct Broadcast Engine (Thread-Safe)
=============================================================================
Gerencia filas de disparos diretos e testes em lote com:
  • Execução em Thread dedicada (100% segura e contínua)
  • Intervalos randômicos customizáveis (ex: 15s a 40s)
  • Substituição dinâmica de tags: {nome}, {primeiro_nome}, {telefone}
  • Suporte a Spintax: {Olá|Oi|E aí}
  • Variação automática anti-spam
  • Suporte a envio de imagens + texto (caption com base64)
  • Status em tempo real do progresso da fila
  • Capacidade de pausar ou cancelar o disparo a qualquer momento
"""

import re
import time
import random
import threading
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from config import BR_TZ
from database import get_supabase
from platforms.whatsapp_client import send_whatsapp_message_sync, format_phone_display
from core.lead_manager import get_lead

logger = logging.getLogger(__name__)

# Estado global da fila de disparo direto
_broadcast_state: Dict[str, Any] = {
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

_broadcast_lock = threading.Lock()


def get_broadcast_status() -> Dict[str, Any]:
    """Retorna o status atual da fila de envio direto."""
    with _broadcast_lock:
        return dict(_broadcast_state)


def cancel_broadcast() -> bool:
    """Solicita o cancelamento da fila ativa."""
    global _broadcast_state
    with _broadcast_lock:
        if _broadcast_state["is_running"]:
            _broadcast_state["should_cancel"] = True
            logger.info("🛑 Solicitação de cancelamento da fila de disparo direto recebida.")
            return True
    return False


def _parse_spintax(text: str) -> str:
    """Resolve spintax no formato {opcao1|opcao2|opcao3}."""
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        choices = match.group(1).split('|')
        text = text[:match.start()] + random.choice(choices) + text[match.end():]
    return text


def _apply_lead_tags(template: str, lead: Dict[str, Any]) -> str:
    """Substitui variáveis do lead no texto."""
    name = (lead.get("name") or "").strip()
    first_name = name.split()[0] if name else "amigo(a)"
    phone = lead.get("phone", "")
    phone_formatted = format_phone_display(phone)

    msg = template
    msg = msg.replace("{nome}", name if name else first_name)
    msg = msg.replace("{primeiro_nome}", first_name)
    msg = msg.replace("{telefone}", phone_formatted)

    return _parse_spintax(msg)


def _apply_subtle_variation(text: str) -> str:
    """Aplica leve variação em emojis e pontuação sem alterar o sentido do texto."""
    subtle_emojis = [" ✨", " 🏡", " 🔑", " 👍", " 📲", ""]
    punctuation = ["!", "!!", ".", " 😊", ""]
    
    if text.endswith("!") or text.endswith("."):
        text = text[:-1] + random.choice(punctuation)
    else:
        text = text + random.choice(subtle_emojis)
    return text.strip()


def start_direct_broadcast(
    lead_ids: List[str],
    message_template: str,
    image_url: Optional[str] = None,
    min_delay: int = 15,
    max_delay: int = 40,
    vary_text: bool = True,
) -> bool:
    """
    Inicia o processamento em Thread dedicada para não bloquear o servidor Flask.
    """
    global _broadcast_state

    with _broadcast_lock:
        if _broadcast_state["is_running"]:
            logger.warning("Fila de disparo direto já está em execução.")
            return False

        _broadcast_state["is_running"] = True
        _broadcast_state["should_cancel"] = False
        _broadcast_state["total"] = len(lead_ids)
        _broadcast_state["current"] = 0
        _broadcast_state["success"] = 0
        _broadcast_state["failed"] = 0
        _broadcast_state["current_lead_name"] = ""
        _broadcast_state["current_lead_phone"] = ""
        _broadcast_state["next_send_in_seconds"] = 0
        _broadcast_state["started_at"] = datetime.now(BR_TZ).isoformat()
        _broadcast_state["log"] = []

    # Inicia Thread separada
    worker = threading.Thread(
        target=_run_broadcast_thread,
        args=(lead_ids, message_template, image_url, max(5, min_delay), max(min_delay, max_delay), vary_text),
        daemon=True,
    )
    worker.start()
    return True


def _run_broadcast_thread(
    lead_ids: List[str],
    message_template: str,
    image_url: Optional[str],
    min_delay: int,
    max_delay: int,
    vary_text: bool,
):
    """Loop síncrono executor da fila com intervalos e variações."""
    global _broadcast_state
    sb = get_supabase()

    logger.info("🚀 [Broadcast Thread] Iniciando fila para %d leads.", len(lead_ids))

    try:
        for idx, lead_id in enumerate(lead_ids):
            # Verifica se foi solicitado cancelamento
            with _broadcast_lock:
                if _broadcast_state["should_cancel"]:
                    logger.info("🛑 [Broadcast Thread] Disparo cancelado pelo usuário.")
                    _broadcast_state["log"].append({
                        "time": datetime.now(BR_TZ).strftime("%H:%M:%S"),
                        "status": "cancelled",
                        "message": "Fila cancelada pelo administrador."
                    })
                    break

                _broadcast_state["current"] = idx + 1

            # Busca dados do lead
            lead = get_lead(lead_id)
            if not lead:
                with _broadcast_lock:
                    _broadcast_state["failed"] += 1
                continue

            # Se o lead estiver pausado individualmente, pula
            if lead.get("paused"):
                logger.info("Lead %s pausado. Pulando envio.", lead.get("phone"))
                with _broadcast_lock:
                    _broadcast_state["log"].append({
                        "time": datetime.now(BR_TZ).strftime("%H:%M:%S"),
                        "lead": lead.get("name") or lead.get("phone"),
                        "status": "skipped",
                        "message": "Lead com pausa individual ativada."
                    })
                continue

            lead_name = lead.get("name") or "Sem nome"
            lead_phone = lead.get("phone")

            with _broadcast_lock:
                _broadcast_state["current_lead_name"] = lead_name
                _broadcast_state["current_lead_phone"] = format_phone_display(lead_phone)

            # Prepara a mensagem personalizada
            message_text = _apply_lead_tags(message_template, lead)
            if vary_text:
                message_text = _apply_subtle_variation(message_text)

            # Envia via Evolution API de forma síncrona
            success = send_whatsapp_message_sync(
                phone=lead_phone,
                text=message_text,
                image_url=image_url,
            )

            now_str = datetime.now(BR_TZ).strftime("%H:%M:%S")

            with _broadcast_lock:
                if success:
                    _broadcast_state["success"] += 1
                    _broadcast_state["log"].insert(0, {
                        "time": now_str,
                        "lead": lead_name,
                        "phone": format_phone_display(lead_phone),
                        "status": "sent",
                        "message": "Enviado com sucesso"
                    })
                else:
                    _broadcast_state["failed"] += 1
                    _broadcast_state["log"].insert(0, {
                        "time": now_str,
                        "lead": lead_name,
                        "phone": format_phone_display(lead_phone),
                        "status": "failed",
                        "message": "Falha no envio WhatsApp"
                    })

            # Registra no log do Supabase
            try:
                sb.table("dispatch_log").insert({
                    "campaign_id": "disparo_direto",
                    "lead_id": lead.get("id", ""),
                    "lead_phone": lead_phone,
                    "lead_name": lead_name,
                    "remarketing_day": 0,
                    "status": "sent" if success else "failed",
                    "sent_at": datetime.now(BR_TZ).isoformat(),
                }).execute()
            except Exception as err:
                logger.debug("Erro ao gravar log no supabase: %s", err)

            # Intervalo randômico antes do próximo envio (exceto após o último lead)
            if idx < len(lead_ids) - 1:
                wait_seconds = random.randint(min_delay, max_delay)
                logger.info("⏳ [Broadcast Thread] Aguardando %ds para o próximo lead...", wait_seconds)

                for remaining in range(wait_seconds, 0, -1):
                    with _broadcast_lock:
                        if _broadcast_state["should_cancel"]:
                            break
                        _broadcast_state["next_send_in_seconds"] = remaining
                    time.sleep(1)

                with _broadcast_lock:
                    _broadcast_state["next_send_in_seconds"] = 0

    except Exception as e:
        logger.error("❌ Erro inesperado na thread de broadcast: %s", e, exc_info=True)
    finally:
        with _broadcast_lock:
            _broadcast_state["is_running"] = False
            _broadcast_state["next_send_in_seconds"] = 0
        logger.info(
            "🏁 [Broadcast Thread] Fila finalizada: %d sucessos, %d falhas.",
            _broadcast_state["success"],
            _broadcast_state["failed"],
        )
