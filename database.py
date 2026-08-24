"""
=============================================================================
BotRemarketingIMOB - Database (Supabase Client)
=============================================================================
Wrapper para o Supabase Python client. Fornece acesso centralizado ao banco
de dados PostgreSQL hospedado no Supabase.
"""

import logging
from typing import Optional

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def get_supabase() -> Client:
    """Retorna a instância global do cliente Supabase (singleton)."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "⚠️ SUPABASE_URL e SUPABASE_KEY são obrigatórios no .env\n"
                "   Acesse o Supabase Dashboard → Settings → API para obter as credenciais."
            )
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("📦 Supabase client inicializado: %s", SUPABASE_URL)
    return _client


def check_connection() -> bool:
    """Verifica se a conexão com o Supabase está funcionando."""
    try:
        sb = get_supabase()
        sb.table("engine_state").select("key").limit(1).execute()
        return True
    except Exception as e:
        logger.error("❌ Falha na conexão com Supabase: %s", e)
        return False
