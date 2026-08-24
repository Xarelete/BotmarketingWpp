"""
=============================================================================
BotRemarketingIMOB - Direct Broadcast Engine (Disparo Rápido / Direto)
=============================================================================
Gerencia filas de disparos diretos e testes em lote com:
  • Intervalos randômicos customizáveis (ex: 20s a 60s)
  • Substituição dinâmica de tags: {nome}, {primeiro_nome}, {telefone}
  • Suporte a Spintax: {Olá|Oi|E aí}
  • Leve variação randômica de emojis/saudações anti-spam
  • Suporte a envio de imagens + texto (caption)
  • Status em tempo real do progresso da fila
  • Capacidade de pausar ou cancelar o disparo a qualquer momento
"""

import re
import random
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from config import BR_TZ
from database import get_supabase
from platforms.whatsapp_client import send_whatsapp_message
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


def get_broadcast_status() -> Dict[str, Any]:
    """Retorna o status atual da fila de envio direto."""
    return dict(_broadcast_state)


def cancel_broadcast() -> bool:
    """Solicita o cancelamento da fila ativa."""
    global _broadcast_state
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

    msg = template
    msg = msg.replace("{nome}", name if name else first_name)
    msg = msg.replace("{primeiro_nome}", first_name)
    msg = msg.replace("{telefone}", phone)

    return _parse_spintax(msg)


def _apply_subtle_variation(text: str) -> str:
    """Aplica leve variação em emojis e pontuação sem alterar o sentido do texto."""
    subtle_emojis = [" ✨", " 🏡", " 🔑", " 👍", " 📲", ""]
    punctuation = ["!", "!!", ".", " 😊", ""]
    
    # Se terminar com pontuação padrão, ocasionalmente varia
    if text.endswith("!") or text.endswith("."):
        text = text[:-1] + random.choice(punctuation)
    else:
        text = text + random.choice(subtle_emojis)
    return text.strip()


async def start_direct_broadcast(
    lead_ids: List[str],
    message_template: str,
    image_url: Optional[str] = None,
    min_delay: int = 15,
    max_delay: int = 45,
    vary_text: bool = True,
) -> bool:
    """
    Inicia o processamento assíncrono da fila de disparo direto.
    """
    global _broadcast_state

    if _broadcast_state["is_running"]:
        logger.warning("Fila de disparo direto já está em execução.")
        return False

    _broadcast_state = {
        "is_running": True,
        "should_cancel": False,
        "total": len(lead_ids),
        "current": 0,
        "success": 0,
        "failed": 0,
        "current_lead_name": "",
        "current_lead_phone": "",
        "next_send_in_seconds": 0,
        "started_at": datetime.now(BR_TZ).isoformat(),
        "log": [],
    }

    # Executa a tarefa assíncrona em background
    asyncio.create_task(
        _run_broadcast_queue(
            lead_ids=lead_ids,
            message_template=message_template,
            image_url=image_url,
            min_delay=max(5, min_delay),
            max_delay=max(min_delay, max_delay),
            vary_text=vary_text,
        )
    )
    return True


async def _run_broadcast_queue(
    lead_ids: List[str],
    message_template: str,
    image_url: Optional[str],
    min_delay: int,
    max_delay: int,
    vary_text: bool,
):
    """Loop executor da fila com intervalos e variações."""
    global _broadcast_state
    sb = get_supabase()

    logger.info("🚀 Iniciando Fila de Disparo Direto para %d leads.", len(lead_ids))

    try:
        for idx, lead_id in enumerate(lead_ids):
            # Verifica cancelamento
            if _broadcast_state["should_cancel"]:
                logger.info("🛑 Disparo direto cancelado pelo usuário.")
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
                _broadcast_state["failed"] += 1
                continue

            # Se lead estiver pausado individualmente, pula
            if lead.get("paused"):
                logger.info("Lead %s está pausado. Pulando da fila.", lead.get("phone"))
                _broadcast_state["log"].append({
                    "time": datetime.now(BR_TZ).strftime("%H:%M:%S"),
                    "lead": lead.get("name") or lead.get("phone"),
                    "status": "skipped",
                    "message": "Lead pausado individualmente."
                })
                continue

            _broadcast_state["current_lead_name"] = lead.get("name") or "Sem nome"
            _broadcast_state["current_lead_phone"] = lead.get("phone")

            # Prepara a mensagem personalizada
            message_text = _apply_lead_tags(message_template, lead)
            if vary_text:
                message_text = _apply_subtle_variation(message_text)

            # Envia mensagem via WhatsApp Evolution API
            success = await send_whatsapp_message(
                phone=lead["phone"],
                text=message_text,
                image_url=image_url,
            )

            now_str = datetime.now(BR_TZ).strftime("%H:%M:%S")

            if success:
                _broadcast_state["success"] += 1
                _broadcast_state["log"].insert(0, {
                    "time": now_str,
                    "lead": lead.get("name") or lead.get("phone"),
                    "phone": lead.get("phone"),
                    "status": "sent",
                    "message": "Enviado com sucesso"
                })
                # Registra no log geral do Supabase
                try:
                    sb.table("dispatch_log").insert({
                        "campaign_id": "disparo_direto",
                        "lead_id": lead.get("id", ""),
                        "lead_phone": lead.get("phone", ""),
                        "lead_name": lead.get("name", ""),
                        "remarketing_day": 0,
                        "status": "sent",
                        "sent_at": datetime.now(BR_TZ).isoformat(),
                    }).execute()
                except Exception as err:
                    logger.debug("Erro ao gravar log no supabase: %s", err)
            else:
                _broadcast_state["failed"] += 1
                _broadcast_state["log"].insert(0, {
                    "time": now_str,
                    "lead": lead.get("name") or lead.get("phone"),
                    "phone": lead.get("phone"),
                    "status": "failed",
                    "message": "Falha no envio WhatsApp"
                })

            # Intervalo randômico antes do próximo envio (exceto após o último)
            if idx < len(lead_ids) - 1:
                wait_seconds = random.randint(min_delay, max_delay)
                _broadcast_state["next_send_in_seconds"] = wait_seconds
                logger.info("⏳ Aguardando %ds para o próximo lead...", wait_seconds)

                # Espera fracionada para checar cancelamento imediato
                for _ in range(wait_seconds):
                    if _broadcast_state["should_cancel"]:
                        break
                    await asyncio.sleep(1)
                    _broadcast_state["next_send_in_seconds"] -= 1

    except Exception as e:
        logger.error("Erro inesperado na fila de disparo direto: %s", e, exc_info=True)
    finally:
        _broadcast_state["is_running"] = False
        _broadcast_state["next_send_in_seconds"] = 0
        logger.info(
            "🏁 Fila finalizada: %d enviados com sucesso, %d falhas.",
            _broadcast_state["success"],
            _broadcast_state["failed"],
        )
