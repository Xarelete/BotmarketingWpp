"""
=============================================================================
BotRemarketingIMOB - Message Generator (Anti-Spam Inteligente)
=============================================================================
Gera mensagens únicas para cada lead, com variações de:
  • Template base (10+ por tipo de campanha)
  • Saudação aleatória (20+ variações)
  • Emojis, pontuação, ordem variáveis
  • Hash anti-repetição por lead
  • Suporte a mensagens customizadas por dia do funil
"""

import hashlib
import random
import logging
from typing import Dict, Any, Optional, List

from database import get_supabase

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# POOLS DE VARIAÇÃO
# ═══════════════════════════════════════════════════════════════════════

SAUDACOES = [
    "Olá{nome}!",
    "Oi{nome}!",
    "Oi{nome}, tudo bem?",
    "Olá{nome}, tudo certo?",
    "Bom dia{nome}!",
    "Boa tarde{nome}!",
    "E aí{nome}, beleza?",
    "Oi{nome}! Como vai?",
    "Olá{nome}, como está?",
    "Oi{nome}! Espero que esteja bem",
    "Olá{nome}! Passando aqui para",
    "Oi{nome}, vim te contar uma novidade",
    "Ei{nome}! Tenho uma novidade",
    "{nome}, tudo bem?",
    "Oi{nome}! Lembrei de você",
    "Olá{nome}! Tenho algo especial",
    "Oi{nome}! Surgiu uma oportunidade",
    "Olá{nome}, espero não incomodar",
    "Oi{nome}! Queria compartilhar algo",
    "Olá{nome}! Vi algo que pode te interessar",
]

EMOJIS_ABERTURA = ["🏠", "🏡", "🌟", "✨", "🔑", "📍", "💎", "🏗️", "🏢", "🌇", "🏘️", "🎯"]
EMOJIS_DESTAQUE = ["🔥", "⚡", "💥", "🚀", "🌟", "✨", "💎", "👉", "📌", "🎯"]
EMOJIS_PRECO = ["💰", "💵", "💲", "🏷️", "🤑", "📊"]
EMOJIS_CTA = ["📱", "📲", "💬", "👋", "🤝", "😊", "📞", "📩"]

PONTUACAO_FIM = ["!", "!!", ".", " 😊", " 🏠", "! ✨", ""]

CONECTORES = [
    "Tenho uma novidade incrível",
    "Surgiu uma oportunidade imperdível",
    "Quero te mostrar algo especial",
    "Lembrei de você quando vi isso",
    "Preciso te contar sobre isso",
    "Você precisa ver isso",
    "Olha que oportunidade",
    "Isso pode te interessar",
    "Achei algo perfeito para você",
    "Não podia deixar de compartilhar",
]

CTA_TEMPLATES = [
    "Me chama se quiser saber mais{p}",
    "Quer conhecer? Me manda uma mensagem{p}",
    "Posso te contar mais detalhes{p}",
    "Interesse? Estou à disposição{p}",
    "Quer agendar uma visita{p}",
    "Me avisa se tiver interesse{p}",
    "Posso te ajudar com mais informações{p}",
    "Qualquer dúvida, estou aqui{p}",
    "Vamos conversar sobre isso{p}",
    "Quer que eu te envie mais detalhes{p}",
    "Te espero para um bate-papo{p}",
    "Posso te passar todas as condições{p}",
]

# ═══════════════════════════════════════════════════════════════════════
# TEMPLATES POR TIPO DE CAMPANHA
# ═══════════════════════════════════════════════════════════════════════

TEMPLATES_REATIVACAO = [
    lambda s, d, e, c: (
        f"{s} {e[0]} {d['conector']}: o *{d['empreendimento']}* {d['destaque']}\n\n"
        f"{e[1]} *Condições:* {d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{e[2]} {c}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"{e[0]} *{d['empreendimento']}*\n"
        f"{d['destaque']}\n\n"
        f"{d['preco_line']}"
        f"{e[1]} {d['condicoes']}\n"
        f"\n{d['link_line']}"
        f"\n\n{c}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"{d['conector']}! {e[0]}\n\n"
        f"*{d['empreendimento']}* — {d['destaque']}\n"
        f"\n{d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{e[1]} {c}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"{e[0]} O *{d['empreendimento']}* está com condições incríveis!\n\n"
        f"{d['preco_line']}"
        f"{e[1]} {d['condicoes']}\n"
        f"\n{d['destaque']}\n"
        f"\n{d['link_line']}"
        f"\n\n{c}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"Lembrei da nossa conversa e quis te atualizar {e[0]}\n\n"
        f"O *{d['empreendimento']}* {d['destaque']}\n"
        f"\n{d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{e[1]} {c}"
    ),
    lambda s, d, e, c: (
        f"{s} {d['conector']}!\n\n"
        f"{e[0]} *{d['empreendimento']}*\n"
        f"➤ {d['destaque']}\n"
        f"➤ {d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{c} {e[1]}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"Você ainda está procurando imóvel? {e[0]}\n\n"
        f"Se sim, o *{d['empreendimento']}* pode ser perfeito!\n"
        f"{d['destaque']}\n"
        f"\n{d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{c}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"{e[0]} *Atualização:* O *{d['empreendimento']}* tem novidades!\n\n"
        f"{d['destaque']}\n"
        f"{d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{e[1]} {c}"
    ),
    lambda s, d, e, c: (
        f"{s} {e[0]}\n\n"
        f"*{d['empreendimento']}* — {d['destaque']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{c}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"Sabe aquele imóvel que todo mundo procura? {e[0]}\n\n"
        f"O *{d['empreendimento']}* é exatamente assim:\n"
        f"• {d['destaque']}\n"
        f"• {d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{c} {e[1]}"
    ),
]

TEMPLATES_EVENTO = [
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"🎉 *{d['empreendimento']}* — Evento Especial!\n\n"
        f"{d['destaque']}\n"
        f"\n📅 {d['condicoes']}\n"
        f"\n{d['link_line']}"
        f"\n\n{c}"
    ),
    lambda s, d, e, c: (
        f"{s} {e[0]}\n\n"
        f"*Grande Novidade:* {d['empreendimento']}\n\n"
        f"{d['destaque']}\n"
        f"{d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{e[1]} {c}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"⚠️ *Últimas oportunidades* no *{d['empreendimento']}*!\n\n"
        f"{d['destaque']}\n"
        f"{d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{c} {e[0]}"
    ),
    lambda s, d, e, c: (
        f"{s}\n\n"
        f"{e[0]} *Condições especiais* no *{d['empreendimento']}*!\n\n"
        f"✅ {d['destaque']}\n"
        f"✅ {d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{c}"
    ),
    lambda s, d, e, c: (
        f"{s} {d['conector']}!\n\n"
        f"{e[0]} *{d['empreendimento']}*\n\n"
        f"{d['destaque']}\n"
        f"{d['condicoes']}\n"
        f"{d['preco_line']}"
        f"\n{d['link_line']}"
        f"\n\n{c} {e[1]}"
    ),
]

TEMPLATE_MAP = {
    "reativacao_geral": TEMPLATES_REATIVACAO,
    "evento": TEMPLATES_EVENTO,
    "lancamento": TEMPLATES_EVENTO,
    "atualizacao": TEMPLATES_REATIVACAO,
    "condicoes_especiais": TEMPLATES_EVENTO,
}


# ═══════════════════════════════════════════════════════════════════════
# HASH ANTI-REPETIÇÃO (via Supabase)
# ═══════════════════════════════════════════════════════════════════════

def _compute_message_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _is_message_repeated(phone: str, msg_hash: str) -> bool:
    sb = get_supabase()
    result = sb.table("message_hashes").select("id").eq(
        "phone", phone
    ).eq("msg_hash", msg_hash).execute()
    return bool(result.data)


def register_message_sent(phone: str, message: str) -> None:
    """Registra hash de mensagem enviada."""
    sb = get_supabase()
    msg_hash = _compute_message_hash(message)
    from datetime import datetime
    from config import BR_TZ
    try:
        sb.table("message_hashes").insert({
            "phone": phone,
            "msg_hash": msg_hash,
            "created_at": datetime.now(BR_TZ).isoformat(),
        }).execute()
    except Exception as e:
        logger.error("Erro ao registrar hash: %s", e)


def get_lead_message_count(phone: str) -> int:
    """Retorna quantas mensagens o lead já recebeu."""
    sb = get_supabase()
    result = sb.table("message_hashes").select("id", count="exact").eq("phone", phone).execute()
    return result.count if result.count is not None else 0


# ═══════════════════════════════════════════════════════════════════════
# GERADOR DE MENSAGEM ÚNICA
# ═══════════════════════════════════════════════════════════════════════

def generate_unique_message(
    lead: Dict[str, Any],
    campaign: Dict[str, Any],
    max_attempts: int = 30,
) -> Optional[str]:
    """Gera mensagem ÚNICA para o lead (nunca repete hash)."""
    phone = lead.get("phone", "")
    lead_name = lead.get("name", "").strip()
    template_key = campaign.get("message_template_key", "reativacao_geral")
    custom = campaign.get("custom_data", {})

    templates = TEMPLATE_MAP.get(template_key, TEMPLATES_REATIVACAO)

    for attempt in range(max_attempts):
        template_fn = random.choice(templates)

        # Saudação
        saudacao_base = random.choice(SAUDACOES)
        if lead_name and random.random() < 0.7:
            nome_str = f" {lead_name.split()[0]}"
        else:
            nome_str = ""
        saudacao = saudacao_base.replace("{nome}", nome_str)

        # Emojis
        emoji_set = [
            random.choice(EMOJIS_ABERTURA),
            random.choice(EMOJIS_DESTAQUE),
            random.choice(EMOJIS_CTA),
        ]

        # CTA
        cta_base = random.choice(CTA_TEMPLATES)
        pontuacao = random.choice(PONTUACAO_FIM)
        cta = cta_base.replace("{p}", pontuacao)

        # Dados
        conector = random.choice(CONECTORES)
        preco = custom.get("preco", "")
        if preco:
            preco_prefixos = [
                f"{random.choice(EMOJIS_PRECO)} *A partir de:* {preco}\n",
                f"{random.choice(EMOJIS_PRECO)} *Investimento:* {preco}\n",
                f"{random.choice(EMOJIS_PRECO)} *Valor:* {preco}\n",
                f"{random.choice(EMOJIS_PRECO)} *Preço especial:* {preco}\n",
            ]
            preco_line = random.choice(preco_prefixos)
        else:
            preco_line = ""

        link = custom.get("link", "")
        if link:
            link_labels = [
                f"🔗 *Saiba mais:* {link}",
                f"🔗 *Veja detalhes:* {link}",
                f"🔗 *Conheça:* {link}",
                f"🔗 *Confira:* {link}",
                f"🔗 {link}",
            ]
            link_line = random.choice(link_labels)
        else:
            link_line = ""

        template_data = {
            "empreendimento": custom.get("empreendimento", "nosso empreendimento"),
            "destaque": custom.get("destaque", ""),
            "condicoes": custom.get("condicoes", "Condições especiais disponíveis"),
            "preco_line": preco_line,
            "link_line": link_line,
            "conector": conector,
        }

        try:
            message = template_fn(saudacao, template_data, emoji_set, cta)
        except Exception as e:
            logger.warning("Erro ao gerar mensagem (tentativa %d): %s", attempt + 1, e)
            continue

        # Limpa linhas vazias consecutivas
        lines = message.split("\n")
        cleaned = []
        prev_empty = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not prev_empty:
                    cleaned.append("")
                    prev_empty = True
            else:
                cleaned.append(line)
                prev_empty = False
        message = "\n".join(cleaned).strip()

        # Verifica hash
        msg_hash = _compute_message_hash(message)
        if _is_message_repeated(phone, msg_hash):
            continue

        logger.info("Mensagem gerada para %s (hash=%s, tentativa=%d)", phone, msg_hash, attempt + 1)
        return message

    logger.warning("Não foi possível gerar mensagem única para %s após %d tentativas", phone, max_attempts)
    return None


def generate_day_message(
    lead: Dict[str, Any],
    campaign: Dict[str, Any],
    day: int,
) -> Optional[str]:
    """
    Gera mensagem para um dia específico do funil.
    Primeiro busca mensagem customizada, se não existir gera automática.
    """
    from core.campaign_manager import get_day_message
    custom_msg = get_day_message(campaign.get("id", ""), day)

    if custom_msg:
        # Substitui variáveis
        lead_name = lead.get("name", "").strip()
        first_name = lead_name.split()[0] if lead_name else ""
        custom = campaign.get("custom_data", {})

        msg = custom_msg
        msg = msg.replace("{nome}", first_name)
        msg = msg.replace("{telefone}", lead.get("phone", ""))
        msg = msg.replace("{empreendimento}", custom.get("empreendimento", ""))
        msg = msg.replace("{destaque}", custom.get("destaque", ""))
        msg = msg.replace("{preco}", custom.get("preco", ""))
        msg = msg.replace("{link}", custom.get("link", ""))
        msg = msg.replace("{dia}", str(day))
        return msg

    # Gera automática
    return generate_unique_message(lead, campaign)
