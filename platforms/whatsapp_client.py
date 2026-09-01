"""
=============================================================================
BotRemarketingIMOB - WhatsApp Client (Evolution API Multi-Instâncias)
=============================================================================
Client para envio de mensagens individuais via Evolution API com suporte a:
  • Multi-instâncias / Seleção dinâmica de números remetentes
  • Listagem de instâncias disponíveis e status de conexão
  • Envio de texto e imagem (base64 / URL) com fallback
  • Diagnóstico detalhado de erros de conexão e Render
"""

import os
import re
import base64
import logging
from typing import Optional, Tuple, List, Dict, Any
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configurações do WhatsApp (Evolution API)
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "").rstrip("/")
WHATSAPP_INSTANCE = os.getenv("WHATSAPP_INSTANCE", "")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")


def get_active_instance() -> str:
    """Retorna a instância do WhatsApp ativa (do Supabase ou do .env)."""
    try:
        from database import get_supabase
        sb = get_supabase()
        res = sb.table("engine_state").select("value").eq("key", "active_whatsapp_instance").execute()
        if res.data and res.data[0].get("value"):
            return res.data[0]["value"].strip()
    except Exception as e:
        logger.debug("Falha ao ler active_whatsapp_instance do banco: %s", e)
    
    return os.getenv("WHATSAPP_INSTANCE", WHATSAPP_INSTANCE)


def set_active_instance(instance_name: str) -> bool:
    """Define a instância ativa padrão no banco de dados Supabase."""
    if not instance_name:
        return False
    try:
        from database import get_supabase
        sb = get_supabase()
        sb.table("engine_state").upsert({
            "key": "active_whatsapp_instance",
            "value": instance_name.strip()
        }).execute()
        logger.info("Instância ativa alterada para: %s", instance_name)
        return True
    except Exception as e:
        logger.error("Erro ao salvar active_whatsapp_instance: %s", e)
        return False


def list_whatsapp_instances() -> List[Dict[str, Any]]:
    """
    Busca todas as instâncias cadastradas na Evolution API e seus status de conexão.
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)
    active_inst = get_active_instance()

    if not api_url:
        return []

    try:
        headers = {"apikey": api_key, "User-Agent": "Mozilla/5.0"}
        resp = requests.get(f"{api_url}/instance/fetchInstances", headers=headers, timeout=12)
        if resp.status_code != 200:
            logger.warning("Falha ao buscar instâncias: HTTP %d", resp.status_code)
            return []

        raw_list = resp.json()
        if not isinstance(raw_list, list):
            return []

        instances = []
        for item in raw_list:
            name = item.get("name") or item.get("instanceName") or ""
            if not name:
                continue

            status = item.get("connectionStatus", "close")
            owner_jid = item.get("ownerJid") or ""
            phone = owner_jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
            profile_name = item.get("profileName") or name

            instances.append({
                "id": item.get("id", ""),
                "name": name,
                "status": status,
                "phone": phone,
                "phone_formatted": format_phone_display(phone) if phone else "Sem número",
                "profile_name": profile_name,
                "profile_pic": item.get("profilePicUrl") or "",
                "is_active": name == active_inst,
            })

        return instances

    except Exception as e:
        logger.error("Erro ao listar instâncias do WhatsApp: %s", e)
        return []


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
    Tenta retornar a imagem em Base64 puro para evitar problemas de rede.
    """
    if not image_source:
        return None, "image/jpeg"

    image_source = image_source.strip()
    
    # 1. Se já for data URI, extrai o puro
    if image_source.startswith("data:image"):
        try:
            header, b64data = image_source.split(",", 1)
            mime_match = re.search(r'data:(image/\w+);base64', header)
            mimetype = mime_match.group(1) if mime_match else "image/jpeg"
            return b64data, mimetype
        except Exception:
            pass

    # 2. Se é arquivo local (uploads do painel)
    if "/static/uploads/" in image_source:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
                logger.error("Erro ao converter local_path para base64: %s", e)

    # 3. Fallback: Inferir extensão e retornar a própria URL
    ext = image_source.split(".")[-1].lower() if "." in image_source[-6:] else "jpeg"
    mimetype = f"image/{ext}" if ext in ["png", "webp", "jpeg", "jpg"] else "image/jpeg"
    if ext == "jpg":
        mimetype = "image/jpeg"

    return image_source, mimetype


def send_whatsapp_message_sync(
    phone: str,
    text: str,
    image_url: str = None,
    instance: str = None,
) -> Tuple[bool, str]:
    """
    Envia mensagem síncrona via Evolution API usando a instância especificada ou ativa.
    Retorna: (sucesso: bool, mensagem_erro: str)
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    target_instance = instance.strip() if instance else get_active_instance()
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)

    if not api_url or not target_instance:
        err = "Credenciais ou instância do WhatsApp não configuradas."
        logger.warning(err)
        return False, err

    dest_number = clean_phone_number(phone)
    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
        "User-Agent": "Mozilla/5.0",
    }

    try:
        media_data, mimetype = _get_image_payload(image_url) if image_url else (None, "image/jpeg")

        if media_data:
            endpoint = f"{api_url}/message/sendMedia/{target_instance}"
            payload = {
                "number": dest_number,
                "mediatype": "image",
                "mimetype": mimetype,
                "caption": text,
                "media": media_data,
                "fileName": "imovel.jpg",
                "options": {
                    "delay": 1500,
                    "presence": "composing"
                }
            }
        else:
            endpoint = f"{api_url}/message/sendText/{target_instance}"
            payload = {
                "number": dest_number,
                "text": text,
                "linkPreview": False,
                "options": {
                    "delay": 1500,
                    "presence": "composing"
                }
            }

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=35)

        if resp.status_code in (200, 201):
            logger.info("✅ Mensagem enviada com sucesso para %s via [%s]!", dest_number, target_instance)
            return True, "OK"

        error_detail = f"Evolution API HTTP {resp.status_code}: {resp.text}"
        logger.warning("⚠️ %s", error_detail)

        # Fallback: Se tentou com imagem e falhou, tenta enviar texto puro imediatamente
        if media_data:
            logger.info("🔄 Tentando fallback para envio de texto simples...")
            fb_endpoint = f"{api_url}/message/sendText/{target_instance}"
            fb_payload = {
                "number": dest_number,
                "text": text,
                "linkPreview": False,
                "options": {
                    "delay": 1500,
                    "presence": "composing"
                }
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


def check_whatsapp_connection_sync(instance: str = None) -> Tuple[bool, str]:
    """
    Verifica se a instância do WhatsApp está conectada e retorna diagnóstico detalhado.
    Retorna: (is_connected: bool, status_message: str)
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    target_instance = instance.strip() if instance else get_active_instance()
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)

    if not api_url or not target_instance:
        return False, "Credenciais do WhatsApp não configuradas no .env"

    try:
        resp = requests.get(
            f"{api_url}/instance/connectionState/{target_instance}",
            headers={"apikey": api_key, "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            state = data.get("instance", {}).get("state", "").lower()
            if state == "open":
                return True, f"WhatsApp Conectado ({target_instance})"
            elif state == "connecting":
                return False, f"Instância '{target_instance}' Conectando... Aguarde alguns instantes."
            elif state == "close":
                return False, f"Instância '{target_instance}' Desconectada. Escaneie o QR Code na Evolution API."
            return False, f"Instância '{target_instance}' em estado '{state}'."

        if resp.status_code == 503:
            return False, "Servidor Evolution API no Render está offline ou hibernando (HTTP 503 / hibernate-wake-error). Reinicie o serviço no Dashboard do Render."

        if resp.status_code == 401 or resp.status_code == 403:
            return False, "Chave de API (WHATSAPP_API_KEY) inválida ou não autorizada."

        if resp.status_code == 404:
            return False, f"Instância '{target_instance}' não encontrada na Evolution API."

        return False, f"Evolution API retornou status HTTP {resp.status_code}"

    except requests.exceptions.Timeout:
        return False, "Tempo de resposta esgotado (Timeout). O servidor da Evolution API no Render pode estar reiniciando ou sobrecarregado."
    except requests.exceptions.ConnectionError:
        return False, "Falha de conexão com a Evolution API. Verifique a URL no .env."
    except Exception as e:
        logger.warning("Falha ao verificar conexão WhatsApp: %s", e)
        return False, f"Erro de conexão: {str(e)}"


async def send_whatsapp_message(
    phone: str,
    text: str,
    image_url: str = None,
    instance: str = None,
) -> bool:
    """Wrapper assíncrono para compatibilidade com o motor de funil."""
    import asyncio
    success, _ = await asyncio.to_thread(send_whatsapp_message_sync, phone, text, image_url, instance)
    return success


async def check_whatsapp_connection(instance: str = None) -> bool:
    """Wrapper assíncrono para compatibilidade."""
    import asyncio
    connected, _ = await asyncio.to_thread(check_whatsapp_connection_sync, instance)
    return connected


# ═══════════════════════════════════════════════════════════════════════
# GRUPOS DE WHATSAPP (JORNAL DA CONSTRUTORA + DISPARO PARA GRUPOS)
# ═══════════════════════════════════════════════════════════════════════

def list_whatsapp_groups_sync(instance: str = None) -> List[Dict[str, Any]]:
    """
    Busca todos os grupos reais de que a instância participa, via Evolution API.
    Retorna lista de {group_jid, name, participants_count, picture_url}.
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)
    target_instance = instance.strip() if instance else get_active_instance()

    if not api_url or not target_instance:
        return []

    try:
        headers = {"apikey": api_key, "User-Agent": "Mozilla/5.0"}
        resp = requests.get(
            f"{api_url}/group/fetchAllGroups/{target_instance}",
            params={"getParticipants": "false"},
            headers=headers,
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning("Falha ao buscar grupos: HTTP %d", resp.status_code)
            return []

        raw = resp.json()
        # A Evolution pode retornar lista direta ou um objeto com chave.
        if isinstance(raw, dict):
            raw = raw.get("groups") or raw.get("data") or []
        if not isinstance(raw, list):
            return []

        groups = []
        for item in raw:
            jid = item.get("id") or item.get("jid") or ""
            if not jid:
                continue
            groups.append({
                "group_jid": jid,
                "name": item.get("subject") or item.get("name") or "Grupo sem nome",
                "participants_count": item.get("size")
                    or item.get("participantsCount")
                    or (len(item.get("participants", [])) if isinstance(item.get("participants"), list) else 0)
                    or 0,
                "picture_url": item.get("pictureUrl") or item.get("profilePicUrl") or "",
            })
        return groups

    except Exception as e:
        logger.error("Erro ao listar grupos do WhatsApp: %s", e)
        return []


def send_whatsapp_group_message_sync(
    group_jid: str,
    text: str,
    image_url: str = None,
    instance: str = None,
) -> Tuple[bool, str]:
    """
    Envia mensagem para um GRUPO. Reutiliza exatamente a mesma lógica de
    payload/endpoint do envio individual (send_whatsapp_message_sync),
    apenas usando o group_jid como 'number'. O group_jid já vem no formato
    '...@g.us', então NÃO passa por clean_phone_number.
    """
    api_url = os.getenv("WHATSAPP_API_URL", WHATSAPP_API_URL).rstrip("/")
    target_instance = instance.strip() if instance else get_active_instance()
    api_key = os.getenv("WHATSAPP_API_KEY", WHATSAPP_API_KEY)

    if not api_url or not target_instance:
        return False, "Credenciais ou instância do WhatsApp não configuradas."
    if not group_jid:
        return False, "ID do grupo (group_jid) não informado."

    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
        "User-Agent": "Mozilla/5.0",
    }

    try:
        media_data, mimetype = _get_image_payload(image_url) if image_url else (None, "image/jpeg")

        if media_data:
            endpoint = f"{api_url}/message/sendMedia/{target_instance}"
            payload = {
                "number": group_jid,
                "mediatype": "image",
                "mimetype": mimetype,
                "caption": text,
                "media": media_data,
                "fileName": "imovel.jpg",
                "options": {"delay": 1500, "presence": "composing"},
            }
        else:
            endpoint = f"{api_url}/message/sendText/{target_instance}"
            payload = {
                "number": group_jid,
                "text": text,
                "linkPreview": False,
                "options": {"delay": 1500, "presence": "composing"},
            }

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=35)

        if resp.status_code in (200, 201):
            logger.info("✅ Mensagem enviada ao grupo %s via [%s]!", group_jid, target_instance)
            return True, "OK"

        error_detail = f"Evolution API HTTP {resp.status_code}: {resp.text}"
        logger.warning("⚠️ (grupo) %s", error_detail)

        # Fallback: se tentou com imagem e falhou, tenta texto puro.
        if media_data:
            fb_endpoint = f"{api_url}/message/sendText/{target_instance}"
            fb_payload = {
                "number": group_jid,
                "text": text,
                "linkPreview": False,
                "options": {"delay": 1500, "presence": "composing"},
            }
            fb_resp = requests.post(fb_endpoint, json=fb_payload, headers=headers, timeout=25)
            if fb_resp.status_code in (200, 201):
                return True, "Enviado com sucesso (Fallback Texto)"

        return False, error_detail

    except Exception as e:
        err_msg = f"Exceção no envio ao grupo ({group_jid}): {e}"
        logger.error("❌ %s", err_msg)
        return False, err_msg


async def send_whatsapp_group_message(
    group_jid: str,
    text: str,
    image_url: str = None,
    instance: str = None,
) -> bool:
    """Wrapper assíncrono para envio a grupos."""
    import asyncio
    success, _ = await asyncio.to_thread(
        send_whatsapp_group_message_sync, group_jid, text, image_url, instance
    )
    return success
