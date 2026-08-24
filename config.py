"""
=============================================================================
BotRemarketingIMOB - Módulo de Configuração Central
=============================================================================
Carrega e valida as variáveis de ambiente do arquivo .env.
"""

import os
import sys
from typing import Dict

from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações do Telegram Admin ---
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_TELEGRAM_ID: str = os.environ.get("ADMIN_TELEGRAM_ID", "").strip()

# --- Configurações do WhatsApp (Evolution API) ---
WHATSAPP_API_URL: str = os.environ.get("WHATSAPP_API_URL", "").strip()
WHATSAPP_INSTANCE: str = os.environ.get("WHATSAPP_INSTANCE", "").strip()
WHATSAPP_API_KEY: str = os.environ.get("WHATSAPP_API_KEY", "").strip()

# --- Configurações do Supabase ---
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "").strip()

# --- Configurações do Motor de Disparos ---
DISPATCH_WINDOW_START: int = int(os.environ.get("DISPATCH_WINDOW_START", "8"))
DISPATCH_WINDOW_END: int = int(os.environ.get("DISPATCH_WINDOW_END", "20"))
DAILY_TARGET_MIN: int = int(os.environ.get("DAILY_TARGET_MIN", "15"))
DAILY_TARGET_MAX: int = int(os.environ.get("DAILY_TARGET_MAX", "40"))

# --- Configurações do Painel Web ---
WEB_PASSWORD: str = os.environ.get("WEB_PASSWORD", "admin123").strip()
WEB_SECRET_KEY: str = os.environ.get("WEB_SECRET_KEY", "change-me-in-production").strip()

# --- Fuso Horário de Brasília (UTC-3) ---
from datetime import timezone, timedelta
BR_TZ = timezone(timedelta(hours=-3))

# --- Paths de Dados (para compatibilidade e backups locais) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Cria diretório de dados se não existir
os.makedirs(DATA_DIR, exist_ok=True)

# Paths legados (mantidos para migração de dados antigos)
LEADS_FILE = os.path.join(DATA_DIR, "leads.json")
CAMPAIGNS_FILE = os.path.join(DATA_DIR, "campaigns.json")
DISPATCH_HISTORY_FILE = os.path.join(DATA_DIR, "dispatch_history.json")
ENGINE_STATE_FILE = os.path.join(DATA_DIR, "engine_state.json")

# --- Validação de Variáveis Obrigatórias ---
_REQUIRED_VARS: Dict[str, str] = {
    "WHATSAPP_API_URL": WHATSAPP_API_URL,
    "WHATSAPP_INSTANCE": WHATSAPP_INSTANCE,
    "WHATSAPP_API_KEY": WHATSAPP_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
}


def validate_config() -> bool:
    """Verifica se todas as variáveis obrigatórias estão configuradas."""
    missing = [key for key, val in _REQUIRED_VARS.items() if not val]
    if missing:
        print(
            f"⚠️ [Config Alert] Variáveis ausentes no .env: {', '.join(missing)}\n"
            f"   Preencha o arquivo .env com suas credenciais antes de iniciar.",
            file=sys.stderr,
        )
        return False
    return True
