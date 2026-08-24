"""
=============================================================================
BotRemarketingIMOB - WhatsApp Client (Evolution API)
=============================================================================
Client para envio de mensagens individuais via Evolution API.
Retorna tupla (success: bool, error_message: str) com logs detalhados.
"""

import os
import re
import base64
import logging
from typing import Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configurações do WhatsApp (Evolution API)
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "").rstrip("/")
WHATSAPP_INSTANCE = os.getenv("WHATSAPP_INSTANCE", "")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")


def clean_phone_number(phone: str) -> str:
    """
    Remove caracteres não-numéricos e garante o DDI 55 do Brasil se necessário.
    Ex: '(12) 99181-0835' -> '5512991810835'
    """
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) == 10 or len(digits) == 11:
        digits = f"55{digits}"
    return digits


def format_phone_display(phone: str) -> str:
    """
    Formata número para exibição amigável:
    Ex: '5512991810835' -> '+55 (12) 99181-0835'
    """
    digits = clean_phone_number(phone)
    if digits.startswith("55") and len(digits) == 13:
        return f"+55 ({digits[2:4]}) {digits[4:9]}-{digits[9:]}"
    elif digits.startswith("55") and len(digits) == 12:
        return f"+55 ({digits[2:4]}) {digits[4:8]}-{digits[8:]}"
    elif len(digits) == 11:
        return f"({digits[0:2]}) {digits[2:7]}-{digits[7:]}"
    return digits


def _get_image_payload(image_source: str) -> Tuple[Optional[str], str]:
    """
    Retorna a própria URL pública da imagem e tenta inferir o mimetype.
    A Evolution API v1/v2 trabalha de forma 100% nativa e segura baixando 
    a URL pública diretamente, evitando silent drops que ocorrem com base64 puros longos.
    """
    if not image_source:
        return None, "image/jpeg"

    image_source = image_source.strip()
    
    # Se já for data URI, a API Evolution não aceita bem no sendMedia ou falha no baileys.
    # Mas como vamos reverter o frontend para mandar URL, isso não deve ocorrer.
    if image_source.startswith("data:image"):
        logger.warning("Recebido data URI base64, o que não é ideal para Evolution. Tentando extrair puro...")
        try:
            header, b64data = image_source.split(",", 1)
            mime_match = re.search(r'data:(image/\w+);base64', header)
            mimetype = mime_match.group(1) if mime_match else "image/jpeg"
            return b64data, mimetype
        except Exception:
            pass

    # Inferindo mimetype pela extensão
    ext = image_source.split(".")[-1].lower() if "." in image_source[-6:] else "jpeg"
    mimetype = f"image/{ext}" if ext in ["png", "webp", "jpeg", "jpg"] else "image/jpeg"
    if ext == "jpg":
        mimetype = "image/jpeg"

    return image_source, mimetype


def send_whatsapp_message_sync(
    phone: str,
    text: str,
    image_url: str = None,
) -> Tuple[bool, str]:
    """
    Envia mensagem síncrona via Evolution API.
    Retorna: (sucesso: bool, mensagem_erro: str)
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    instance = os.getenv("WHATSAPP_INSTANCE", WHATSAPP_INSTANCE)
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)

    if not api_url or not instance:
        err = "Credenciais do WhatsApp não configuradas (.env)."
        logger.warning(err)
        return False, err

    dest_number = clean_phone_number(phone)
    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
    }

    try:
        media_data, mimetype = _get_image_payload(image_url) if image_url else (None, "image/jpeg")

        if media_data:
            endpoint = f"{api_url}/message/sendMedia/{instance}"
            payload = {
                "number": dest_number,
                "mediatype": "image",
                "mimetype": mimetype,
                "caption": text,
                "media": media_data,
                "fileName": "imovel.jpg",
            }
        else:
            endpoint = f"{api_url}/message/sendText/{instance}"
            payload = {
                "number": dest_number,
                "text": text,
                "linkPreview": False,
            }

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=35)

        if resp.status_code in (200, 201):
            logger.info("✅ Mensagem enviada com sucesso para %s!", dest_number)
            return True, "OK"

        error_detail = f"Evolution API HTTP {resp.status_code}: {resp.text}"
        logger.warning("⚠️ %s", error_detail)

        # Fallback: Se tentou com imagem e falhou, tenta enviar texto puro imediatamente
        if media_data:
            logger.info("🔄 Tentando fallback para envio de texto simples...")
            fb_endpoint = f"{api_url}/message/sendText/{instance}"
            fb_payload = {
                "number": dest_number,
                "text": text,
                "linkPreview": False,
            }
            fb_resp = requests.post(fb_endpoint, json=fb_payload, headers=headers, timeout=25)
            if fb_resp.status_code in (200, 201):
                logger.info("✅ Fallback de texto enviado com sucesso para %s!", dest_number)
                return True, "Enviado com sucesso (Fallback Texto)"

        return False, error_detail

    except Exception as e:
        err_msg = f"Exceção na requisição ({dest_number}): {e}"
        logger.error("❌ %s", err_msg)
        return False, err_msg


async def send_whatsapp_message(
    phone: str,
    text: str,
    image_url: str = None,
) -> bool:
    """Wrapper assíncrono para compatibilidade com o motor de funil."""
    import asyncio
    success, _ = await asyncio.to_thread(send_whatsapp_message_sync, phone, text, image_url)
    return success


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
