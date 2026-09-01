"""
=============================================================================
BotRemarketingIMOB - Web Session Context
=============================================================================
Centraliza o "número (instância) ativo" da sessão web atual.

Depois que o usuário faz login em um número, TODAS as operações do painel
(leads, bolsões, grupos, campanhas, disparos) são filtradas por essa instância.
Isso garante a separação total de dados por número conectado.
"""

import functools
from flask import session, jsonify


def get_session_instance() -> str:
    """Retorna a instância (número) ativa na sessão, ou string vazia."""
    return session.get("instance", "") or ""


def set_session_instance(instance_name: str) -> None:
    """Define a instância ativa da sessão."""
    session["instance"] = instance_name


def clear_session_instance() -> None:
    """Remove a instância ativa da sessão."""
    session.pop("instance", None)


def instance_required(f):
    """
    Decorator que exige que uma instância (número) esteja selecionada na sessão.
    Deve ser usado APÓS @auth_required nas rotas que operam sobre dados de um número.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not get_session_instance():
            return jsonify({"error": "Nenhum número selecionado. Faça login em um número primeiro.", "code": "no_instance"}), 428
        return f(*args, **kwargs)
    return decorated
