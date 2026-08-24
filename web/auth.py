"""
=============================================================================
BotRemarketingIMOB - Web Auth
=============================================================================
Autenticação simples por senha para o painel admin.
"""

import functools
import hashlib
import secrets
import time
from flask import request, jsonify, session

from config import WEB_PASSWORD, WEB_SECRET_KEY


def check_auth() -> bool:
    """Verifica se a sessão atual está autenticada."""
    return session.get("authenticated", False)


def login(password: str) -> bool:
    """Tenta login com a senha fornecida."""
    if password == WEB_PASSWORD:
        session["authenticated"] = True
        session["login_at"] = time.time()
        return True
    return False


def logout():
    """Encerra a sessão."""
    session.clear()


def auth_required(f):
    """Decorator que protege rotas da API."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            return jsonify({"error": "Não autenticado"}), 401
        return f(*args, **kwargs)
    return decorated
