"""
=============================================================================
BotRemarketingIMOB - WhatsApp Client (Evolution API)
=============================================================================
Client para envio de mensagens individuais via Evolution API.
Adaptado do projeto BotWhatsAppALX para envios 1-a-1 com leads.
"""

import logging
import requests
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente de múltiplos caminhos possíveis
env_candidates = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
    os.path.join(os.getcwd(), ".env"),
]
for env_path in env_candidates:
    if os.path.exists(env_path):
        load_dotenv(env_path, override=False)

load_dotenv()

logger = logging.getLogger(__name__)

# Configurações do WhatsApp (Evolution API)
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_INSTANCE = os.getenv("WHATSAPP_INSTANCE", "")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")


def _format_whatsapp_number(phone: str) -> str:
    """
    Formata número de telefone para o padrão WhatsApp:
    - Remove caracteres não-numéricos
    - Adiciona sufixo @s.whatsapp.net para envios individuais
    - Detecta e preserva @g.us para grupos
    """
    phone = phone.strip()

    # Se já tem sufixo, retorna como está
    if "@" in phone:
        return phone

    # Remove tudo que não é dígito
    digits = "".join(c for c in phone if c.isdigit())

    # Se o número brasileiro não tem código do país, adiciona 55
    if len(digits) == 10 or len(digits) == 11:
        digits = f"55{digits}"

    return f"{digits}@s.whatsapp.net"


async def send_whatsapp_message(
    phone: str,
    text: str,
    image_url: str = None,
) -> bool:
    """
    Envia mensagem individual para um lead via Evolution API.
    
    Args:
        phone: Número do lead (ex: "5511999887766" ou "+55 11 99988-7766")
        text: Corpo da mensagem
        image_url: URL opcional de imagem (render, planta, etc.)
    
    Returns:
        True se enviado com sucesso, False caso contrário
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    instance = os.getenv("WHATSAPP_INSTANCE", WHATSAPP_INSTANCE)
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)

    if not api_url or not instance:
        logger.warning("Credenciais do WhatsApp não configuradas. Pulando envio.")
        return False

    dest_number = _format_whatsapp_number(phone)

    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
    }

    try:
        if image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
            # Envia como imagem + caption
            endpoint = f"{api_url}/message/sendMedia/{instance}"
            payload = {
                "number": dest_number,
                "mediatype": "image",
                "mimetype": "image/jpeg",
                "caption": text,
                "media": image_url,
                "fileName": "empreendimento.jpg",
            }
        else:
            # Envia como texto simples
            endpoint = f"{api_url}/message/sendText/{instance}"
            payload = {
                "number": dest_number,
                "text": text,
                "linkPreview": True,
            }

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=25)

        if resp.status_code not in (200, 201):
            logger.warning(
                "Aviso Evolution API (%d): %s", resp.status_code, resp.text
            )
            # Fallback: se tentou com imagem e falhou, tenta como texto puro
            if image_url:
                logger.info("Tentando fallback com envio de texto simples...")
                fallback_endpoint = f"{api_url}/message/sendText/{instance}"
                fallback_payload = {
                    "number": dest_number,
                    "text": text,
                    "linkPreview": True,
                }
                fb_resp = requests.post(
                    fallback_endpoint, json=fallback_payload, headers=headers, timeout=20
                )
                if fb_resp.status_code in (200, 201):
                    logger.info(
                        "Mensagem enviada com sucesso (Fallback Texto) para %s",
                        dest_number,
                    )
                    return True
            return False

        logger.info("Mensagem enviada com sucesso para %s!", dest_number)
        return True

    except requests.exceptions.Timeout:
        logger.error("Timeout ao enviar mensagem para %s", dest_number)
        return False
    except Exception as e:
        logger.error("Falha ao enviar para o WhatsApp (%s): %s", dest_number, e)
        return False


async def check_whatsapp_connection() -> bool:
    """Verifica se a instância do WhatsApp está conectada."""
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    instance = os.getenv("WHATSAPP_INSTANCE", WHATSAPP_INSTANCE)
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)

    if not api_url or not instance:
        return False

    try:
        resp = requests.get(
            f"{api_url}/instance/connectionState/{instance}",
            headers={"apikey": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            state = data.get("instance", {}).get("state", "")
            return state.lower() == "open"
    except Exception as e:
        logger.warning("Falha ao verificar conexão WhatsApp: %s", e)

    return False
