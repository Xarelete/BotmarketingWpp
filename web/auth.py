"""
=============================================================================
BotRemarketingIMOB - Web Auth
=============================================================================
Autenticação simples por senha para o painel admin.
"""

import functools
import hmac
import hashlib
import time
from flask import request, jsonify, session

from config import WEB_PASSWORD, WEB_SECRET_KEY


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def check_auth() -> bool:
    """Verifica se a sessão atual está autenticada."""
    return session.get("authenticated", False)


def login(password: str) -> bool:
    """
    Login GLOBAL de administrador (fallback), usando WEB_PASSWORD.
    Comparação em tempo constante para evitar timing attacks.
    O fluxo principal de acesso é por número (login_instance).
    """
    if hmac.compare_digest(_hash(password), _hash(WEB_PASSWORD)):
        session["authenticated"] = True
        session["is_admin"] = True
        session["login_at"] = time.time()
        return True
    return False


def login_instance(instance_name: str, password: str) -> bool:
    """
    Login por NÚMERO conectado. Valida a senha específica da instância
    (armazenada como hash em instance_access) e, se ok, marca a sessão
    como autenticada e define o número ativo.
    """
    from core.instance_access import verify_instance_password
    from web.context import set_session_instance

    if not instance_name:
        return False

    if verify_instance_password(instance_name, password):
        session["authenticated"] = True
        session["is_admin"] = False
        session["login_at"] = time.time()
        set_session_instance(instance_name)
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
