"""
=============================================================================
BotRemarketingIMOB - Models (Dataclasses)
=============================================================================
Estruturas de dados para leads, campanhas, mensagens e funil de remarketing.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class Lead:
    """Representa um lead no bolsão de remarketing."""
    id: str = ""
    name: str = ""
    phone: str = ""
    source: str = "manual"
    tags: List[str] = field(default_factory=list)
    added_at: str = ""
    added_by: str = "admin"
    status: str = "active"          # active, inactive, completed, converted
    notes: str = ""
    paused: bool = False            # Pausado individualmente
    remarketing_day: int = 0        # Dia atual no funil (0 = não entrou)
    next_send_date: str = ""        # Próxima data de envio (YYYY-MM-DD)
    entered_pool_at: str = ""       # Quando entrou no bolsão
    completed_at: str = ""          # Quando completou o funil

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário (compatível com API/JSON)."""
        return asdict(self)


@dataclass
class Campaign:
    """Representa uma campanha de remarketing."""
    id: str = ""
    name: str = ""
    status: str = "active"          # active, paused, completed
    type: str = "remarketing"
    target_tags: List[str] = field(default_factory=list)
    message_template_key: str = "reativacao_geral"
    custom_data: Dict[str, Any] = field(default_factory=dict)
    schedule: Dict[str, Any] = field(default_factory=dict)
    days_config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    total_sent: int = 0
    total_failed: int = 0
    total_leads_reached: int = 0
    last_dispatch: str = ""
    daily_sent_today: int = 0
    stats_current_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário (compatível com API/JSON)."""
        d = asdict(self)
        # Adiciona campo "stats" para compatibilidade com o formato antigo
        d["stats"] = {
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "total_leads_reached": self.total_leads_reached,
            "last_dispatch": self.last_dispatch,
            "daily_sent_today": self.daily_sent_today,
            "current_date": self.stats_current_date,
        }
        return d


@dataclass
class DayMessage:
    """Mensagem customizada para um dia específico do funil."""
    id: int = 0
    campaign_id: str = ""
    day: int = 1
    message_text: str = ""
    is_custom: bool = True
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchLogEntry:
    """Registro de um disparo individual."""
    id: int = 0
    campaign_id: str = ""
    lead_id: str = ""
    lead_phone: str = ""
    lead_name: str = ""
    remarketing_day: int = 0
    message_hash: str = ""
    status: str = "sent"            # sent, failed, skipped
    sent_at: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES DO FUNIL
# ═══════════════════════════════════════════════════════════════════════

# Dias padrão do funil de remarketing (customizável por campanha)
DEFAULT_FUNNEL_DAYS = [1, 2, 3, 5, 7, 14, 30]

# Status possíveis do lead
LEAD_STATUS_ACTIVE = "active"
LEAD_STATUS_INACTIVE = "inactive"
LEAD_STATUS_COMPLETED = "completed"
LEAD_STATUS_CONVERTED = "converted"

# Status possíveis da campanha
CAMPAIGN_STATUS_ACTIVE = "active"
CAMPAIGN_STATUS_PAUSED = "paused"
CAMPAIGN_STATUS_COMPLETED = "completed"
