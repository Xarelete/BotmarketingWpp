"""
=============================================================================
BotRemarketingIMOB - Direct Broadcast Engine (Thread-Safe & Humanizado)
=============================================================================
Gerencia filas de disparos diretos e testes em lote com:
  • Execução em Thread dedicada (100% segura e contínua)
  • Intervalos randômicos customizáveis (ex: 15s a 40s)
  • Substituição dinâmica e inteligente de tags: {nome}, {primeiro_nome}, {telefone}
  • Tratamento natural para leads sem nome (sem placeholders robóticos)
  • Motor de Variação Inteligente de Sinônimos (Humanizador Anti-Spam de Alta Fidelidade)
  • Suporte a Spintax nativo: {Olá|Oi|Tudo bem?}
  • Suporte a envio de imagens + texto (caption com base64 ou URL)
  • Status em tempo real do progresso da fila e logs
  • Capacidade de pausar ou cancelar o disparo a qualquer momento
"""

import re
import time
import random
import threading
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

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


# ═══════════════════════════════════════════════════════════════════════
# DICIONÁRIO DE SINÔNIMOS & VARIAÇÕES CONTEXTUAIS (PORTUGUÊS / IMOB)
# ═══════════════════════════════════════════════════════════════════════

# Mapeamento de termos / expressões para variações perfeitamente equivalentes
SYNONYM_DICTIONARY: Dict[str, List[str]] = {
    # Saudações & Aberturas
    "tudo bem com você?": ["tudo bem com você?", "tudo bem?", "como você está?", "tudo certo por aí?"],
    "tudo bem por aí?": ["tudo bem por aí?", "tudo bem com você?", "tudo certo?", "como vão as coisas?"],
    "como você está?": ["como você está?", "tudo bem com você?", "tudo bem?", "tudo certo?"],
    "tudo bem?": ["tudo bem?", "tudo bem com você?", "tudo certo?", "como estão as coisas?", "tudo bem por aí?"],
    "tudo certo?": ["tudo certo?", "tudo bem?", "tudo bem com você?", "como vão as coisas?"],
    "olá": ["Olá", "Oi", "Olá", "Oi"],
    "oi": ["Oi", "Olá", "Oi", "Olá"],
    "bom dia": ["Bom dia", "Olá, bom dia", "Oi, bom dia"],
    "boa tarde": ["Boa tarde", "Olá, boa tarde", "Oi, boa tarde"],

    # Conectores & Intenção
    "passando aqui para te mostrar": ["passando aqui para te mostrar", "passando para te apresentar", "quis passar para te mostrar", "estou passando para te apresentar"],
    "passando para te mostrar": ["passando para te mostrar", "passando aqui para te apresentar", "mando mensagem para te mostrar", "quis passar para te apresentar"],
    "passando para te apresentar": ["passando para te apresentar", "passando para te mostrar", "quis passar para compartilhar com você"],
    "passando para": ["passando para", "passando aqui para", "estou passando para", "quis passar para"],
    "passando pra": ["passando pra", "passando para", "passando aqui pra", "estou passando pra"],
    "te mostrar": ["te mostrar", "te apresentar", "compartilhar com você", "te passar"],
    "te apresentar": ["te apresentar", "te mostrar", "compartilhar com você", "te passar"],
    "uma oportunidade exclusiva": ["uma oportunidade exclusiva", "uma excelente oportunidade", "uma novidade exclusiva", "uma oportunidade especial"],
    "oportunidade exclusiva": ["oportunidade exclusiva", "excelente oportunidade", "oportunidade especial", "opção exclusiva"],
    "uma excelente oportunidade": ["uma excelente oportunidade", "uma ótima oportunidade", "uma oportunidade exclusiva", "uma oportunidade especial"],
    "uma oportunidade": ["uma oportunidade", "uma excelente oportunidade", "uma ótima opção", "uma oportunidade especial"],
    "oportunidade": ["oportunidade", "excelente opção", "ótima oportunidade", "opção especial"],
    "acabou de entrar no nosso portfólio": ["acabou de entrar no nosso portfólio", "acabou de chegar no nosso catálogo", "está disponível na nossa carteira de imóveis", "acaba de ser liberado no nosso portfólio"],
    "acabou de entrar": ["acabou de entrar", "acabou de chegar", "está disponível", "acaba de ser liberado"],
    "no nosso portfólio": ["no nosso portfólio", "no nosso catálogo", "na nossa carteira de imóveis", "na nossa seleção"],
    "nosso portfólio": ["nosso portfólio", "nosso catálogo", "nossa carteira de imóveis", "nossa seleção"],
    "imóvel que acabou de": ["imóvel que acabou de", "projeto que acabou de", "unidade que acabou de", "opção que acabou de"],
    "de imóvel": ["de imóvel", "de empreendimento", "de projeto", "de unidade"],
    "imóvel": ["imóvel", "opção", "projeto", "unidade"],
    "imóveis": ["imóveis", "opções", "projetos", "unidades"],

    # CTAs & Perguntas de Interesse
    "gostaria de receber as fotos e condições?": ["Gostaria de receber as fotos e condições?", "Quer que eu te envie as fotos e detalhes?", "Tem interesse em ver as fotos e informações?", "Posso te mandar as fotos e condições?"],
    "gostaria de receber as fotos e valores?": ["Gostaria de receber as fotos e valores?", "Quer que eu te envie as fotos e condições?", "Tem interesse em ver as fotos e valores?"],
    "gostaria de receber": ["gostaria de receber", "tem interesse em ver", "gostaria de conferir", "quer que eu te envie", "posso te enviar"],
    "gostaria de ver": ["gostaria de ver", "gostaria de receber", "quer conhecer", "posso te mandar", "tem interesse em conferir"],
    "as fotos e condições": ["as fotos e condições", "as fotos e detalhes", "mais informações e fotos", "todas as fotos e valores", "os detalhes e condições"],
    "fotos e condições": ["fotos e condições", "fotos e detalhes", "mais informações e fotos", "detalhes e condições"],
    "fotos e valores": ["fotos e valores", "fotos e condições", "detalhes e fotos", "mais informações"],
    "as fotos": ["as fotos", "as imagens", "as fotos da unidade"],
    
    # Fechamentos & Interação
    "me avisa por aqui": ["me avisa por aqui", "me dá um toque por aqui", "me responde por aqui", "só me avisar"],
    "me avisa aqui": ["me avisa aqui", "me dá um toque", "me responde por aqui", "só me avisar", "me dá um retorno por aqui"],
    "me avisa": ["me avisa", "me dá um toque", "me responde", "só me avisar"],
    "qualquer dúvida": ["qualquer dúvida", "se precisar de algo", "qualquer dúvida estou aqui", "se tiver qualquer dúvida"],
    "estou à disposição": ["estou à disposição", "fico à disposição", "qualquer coisa estou por aqui", "conte comigo"],
    "um abraço": ["um abraço", "ótimo dia", "abraço", "ótima semana"],
    "abraço": ["abraço", "um abraço", "ótimo dia", "ótima semana"],
}


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


# ═══════════════════════════════════════════════════════════════════════
# PROCESSAMENTO DE MENSAGENS E HUMANIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════

def _parse_spintax(text: str) -> str:
    """Resolve spintax recursivamente no formato {opcao1|opcao2|opcao3}."""
    pattern = re.compile(r'\{([^{}]+)\}')
    max_loops = 10
    loop = 0
    while loop < max_loops:
        match = pattern.search(text)
        if not match:
            break
        content = match.group(1)
        if '|' in content:
            choices = [c.strip() for c in content.split('|')]
            text = text[:match.start()] + random.choice(choices) + text[match.end():]
        else:
            text = text[:match.start()] + content + text[match.end():]
        loop += 1
    return text


def _apply_synonym_variation(text: str) -> str:
    """
    Substitui frases e termos por sinônimos contextualizados de forma segura (sem substituições aninhadas).
    """
    sorted_phrases = sorted(SYNONYM_DICTIONARY.keys(), key=lambda x: len(x), reverse=True)

    # Identifica correspondências não-sobrepostas no texto
    result = text
    tokens: Dict[str, str] = {}
    token_counter = 0

    for phrase in sorted_phrases:
        if random.random() < 0.70:  # 70% de chance de variar cada termo
            options = SYNONYM_DICTIONARY[phrase]
            escaped = re.escape(phrase)
            pattern = re.compile(r'(?i)(?<![\w])' + escaped + r'(?![\w])')
            
            def replace_with_token(match):
                nonlocal token_counter
                matched_str = match.group(0)
                replacement = random.choice(options)
                
                # Preserva Capitalização Inicial se o original começava com Maiúscula
                if matched_str and matched_str[0].isupper():
                    replacement = replacement[0].upper() + replacement[1:]
                elif matched_str and matched_str[0].islower():
                    replacement = replacement[0].lower() + replacement[1:]

                token = f"__SYN_{token_counter}__"
                tokens[token] = replacement
                token_counter += 1
                return token

            result = pattern.sub(replace_with_token, result, count=1)

    # Restaura todos os tokens
    for token, replacement in tokens.items():
        result = result.replace(token, replacement)

    # Limpeza de palavras adjacentes repetidas acidentalmente (ex: "aqui aqui", "de de")
    result = re.sub(r'\b(aqui|por aqui|de|para|em|no|na)\s+\1\b', r'\1', result, flags=re.IGNORECASE)

    return result


def _format_lead_message(
    template: str,
    lead: Dict[str, Any],
    vary_synonyms: bool = True,
    vary_text: bool = True,
) -> str:
    """
    Substitui variáveis do lead, trata ausência de nome, aplica sinônimos e spintax.
    """
    raw_name = (lead.get("name") or "").strip()
    phone = lead.get("phone", "")
    phone_formatted = format_phone_display(phone)

    msg = template

    # Tratamento de Nome
    if raw_name:
        first_name = raw_name.split()[0]
        msg = msg.replace("{nome}", raw_name)
        msg = msg.replace("{primeiro_nome}", first_name)
    else:
        # Lead NÃO TEM NOME: trata saudações comuns de forma 100% fluida e humana
        natural_openings = [
            "Olá, tudo bem?",
            "Oi! Tudo bem com você?",
            "Oi, tudo bem?",
            "Olá, tudo certo?",
            "Oi! Como vai?",
            "Olá! Tudo bem por aí?",
        ]
        
        # Substitui padrões de abertura conhecidos
        msg = re.sub(
            r'(?i)(olá|oi|bom dia|boa tarde)\s*\{?(?:primeiro_nome|nome)\}?\s*,?\s*tudo bem\??',
            lambda m: random.choice(natural_openings),
            msg
        )
        
        # Remove tags restantes sem deixar espaços duplos
        msg = msg.replace("{primeiro_nome}", "")
        msg = msg.replace("{nome}", "")
        msg = re.sub(r'\s+([,!?.])', r'\1', msg)
        msg = re.sub(r'([,!?.])\s*,', r'\1', msg)

    # Substitui telefone
    msg = msg.replace("{telefone}", phone_formatted)

    # Aplica Variação Inteligente de Sinônimos (se ativado)
    if vary_synonyms:
        msg = _apply_synonym_variation(msg)

    # Resolve Spintax nativo {A|B|C}
    msg = _parse_spintax(msg)

    # Aplica Variação Leve de Emojis/Pontuação (se ativado)
    if vary_text:
        msg = _apply_subtle_variation(msg)

    # Limpeza final de espaçamentos extras
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in msg.split('\n')]
    cleaned_msg = '\n'.join(lines).strip()
    cleaned_msg = re.sub(r'\n{3,}', '\n\n', cleaned_msg)

    return cleaned_msg


def _apply_subtle_variation(text: str) -> str:
    """Aplica leve variação em emojis e pontuação sem alterar o sentido do texto."""
    subtle_emojis = [" ✨", " 🏡", " 🔑", " 👍", " 📲", " 📍", ""]
    punctuation = ["!", "!!", ".", " 😊", ""]
    
    if text.endswith("!") or text.endswith("."):
        text = text[:-1] + random.choice(punctuation)
    else:
        text = text + random.choice(subtle_emojis)
    return text.strip()


def preview_humanized_message(
    template: str,
    sample_lead: Optional[Dict[str, Any]] = None,
    vary_synonyms: bool = True,
    vary_text: bool = True,
) -> str:
    """
    Gera uma prévia da mensagem para teste/simulação em tempo real.
    """
    if sample_lead is None:
        sample_lead = {
            "name": "",
            "phone": "5512988265141",
        }
    return _format_lead_message(template, sample_lead, vary_synonyms=vary_synonyms, vary_text=vary_text)


# ═══════════════════════════════════════════════════════════════════════
# EXECUÇÃO DO DISPARO EM MASSA (THREAD DEDICADA)
# ═══════════════════════════════════════════════════════════════════════

def start_direct_broadcast(
    lead_ids: List[str],
    message_template: str,
    image_url: Optional[str] = None,
    min_delay: int = 15,
    max_delay: int = 40,
    vary_text: bool = True,
    vary_synonyms: bool = True,
    instance: Optional[str] = None,
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
        args=(
            lead_ids,
            message_template,
            image_url,
            max(5, min_delay),
            max(min_delay, max_delay),
            vary_text,
            vary_synonyms,
            instance,
        ),
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
    vary_synonyms: bool,
    instance: Optional[str] = None,
):
    """Loop síncrono executor da fila com intervalos e variações humanizadas."""
    global _broadcast_state
    sb = get_supabase()

    logger.info("🚀 [Broadcast Thread] Iniciando fila para %d leads via [%s].", len(lead_ids), instance or "padrão")

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

            # Prepara a mensagem única humanizada para este lead
            message_text = _format_lead_message(
                template=message_template,
                lead=lead,
                vary_synonyms=vary_synonyms,
                vary_text=vary_text,
            )

            # Envia via Evolution API de forma síncrona
            success, err_detail = send_whatsapp_message_sync(
                phone=lead_phone,
                text=message_text,
                image_url=image_url,
                instance=instance,
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
                        "message": err_detail
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
                    "error_message": "" if success else err_detail,
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
