"""
=============================================================================
BotRemarketingIMOB - WhatsApp Client (Evolution API)
=============================================================================
Client para envio de mensagens individuais via Evolution API.
Suporta envio de texto simples e envio de mídia (com suporte nativo a Base64
para imagens locais ou URLs externas).
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
        # Celular Brasil 9 dígitos: 55 + DDD (2) + 9 + 4
        return f"+55 ({digits[2:4]}) {digits[4:9]}-{digits[9:]}"
    elif digits.startswith("55") and len(digits) == 12:
        # Fixo Brasil 8 dígitos: 55 + DDD (2) + 4 + 4
        return f"+55 ({digits[2:4]}) {digits[4:8]}-{digits[8:]}"
    elif len(digits) == 11:
        return f"({digits[0:2]}) {digits[2:7]}-{digits[7:]}"
    return digits


def _get_image_payload(image_source: str) -> tuple[Optional[str], str]:
    """
    Processa a fonte da imagem e retorna (media_data, mimetype).
    Converte arquivos locais ou URLs locais em Base64 para garantir entrega.
    """
    if not image_source:
        return None, "image/jpeg"

    image_source = image_source.strip()

    # Se já é base64 puro ou data URI
    if image_source.startswith("data:image"):
        parts = image_source.split(",")
        mime_match = re.search(r'data:(image/\w+);base64', parts[0])
        mimetype = mime_match.group(1) if mime_match else "image/jpeg"
        return parts[1], mimetype

    # Se é um arquivo local em static/uploads
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "/static/uploads/" in image_source:
        filename = image_source.split("/static/uploads/")[-1]
        local_path = os.path.join(base_dir, "web", "static", "uploads", filename)
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                ext = os.path.splitext(filename)[1].lower().replace(".", "")
                mimetype = "image/png" if ext == "png" else "image/webp" if ext == "webp" else "image/jpeg"
                return encoded, mimetype
            except Exception as e:
                logger.error("Erro ao ler imagem local para base64: %s", e)

    # Se é URL pública HTTP/HTTPS que não seja localhost
    if image_source.startswith("http://") or image_source.startswith("https://"):
        if "localhost" not in image_source and "127.0.0.1" not in image_source:
            return image_source, "image/jpeg"

    return None, "image/jpeg"


def send_whatsapp_message_sync(
    phone: str,
    text: str,
    image_url: str = None,
) -> bool:
    """
    Envia mensagem síncrona via Evolution API.
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    instance = os.getenv("WHATSAPP_INSTANCE", WHATSAPP_INSTANCE)
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)

    if not api_url or not instance:
        logger.warning("Credenciais do WhatsApp não configuradas. Pulando envio.")
        return False

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

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=25)

        if resp.status_code in (200, 201):
            logger.info("✅ Mensagem enviada com sucesso para %s!", dest_number)
            return True

        logger.warning("⚠️ Evolution API retornou (%d): %s", resp.status_code, resp.text)

        # Fallback: Se tentou com imagem e falhou, tenta enviar o texto puro
        if media_data:
            logger.info("🔄 Tentando fallback para envio de texto simples...")
            fb_endpoint = f"{api_url}/message/sendText/{instance}"
            fb_payload = {
                "number": dest_number,
                "text": text,
                "linkPreview": False,
            }
            fb_resp = requests.post(fb_endpoint, json=fb_payload, headers=headers, timeout=20)
            if fb_resp.status_code in (200, 201):
                logger.info("✅ Fallback de texto enviado com sucesso para %s!", dest_number)
                return True

        return False

    except Exception as e:
        logger.error("❌ Falha na requisição para WhatsApp (%s): %s", dest_number, e)
        return False


async def send_whatsapp_message(
    phone: str,
    text: str,
    image_url: str = None,
) -> bool:
    """Wrapper assíncrono para compatibilidade."""
    import asyncio
    return await asyncio.to_thread(send_whatsapp_message_sync, phone, text, image_url)


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
