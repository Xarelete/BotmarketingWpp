"""
=============================================================================
BotRemarketingIMOB - Flask Web App (API + Painel)
=============================================================================
API REST + serve o painel admin como SPA estática.
"""

import json
import logging
from flask import Flask, request, jsonify, session, send_from_directory, render_template

from config import WEB_SECRET_KEY
from web.auth import auth_required, login, logout, check_auth

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Factory para criar o Flask app."""
    import os
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.secret_key = WEB_SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # ═══════════════════════════════════════════════════════════════
    # ROTAS DE PÁGINAS
    # ═══════════════════════════════════════════════════════════════

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/health")
    def health():
        return "BotRemarketingIMOB is Online!", 200

    # ═══════════════════════════════════════════════════════════════
    # AUTH
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/auth/login", methods=["POST"])
    def api_login():
        data = request.get_json(silent=True) or {}
        password = data.get("password", "")
        if login(password):
            return jsonify({"ok": True})
        return jsonify({"error": "Senha incorreta"}), 401

    @app.route("/api/auth/check")
    def api_auth_check():
        return jsonify({"authenticated": check_auth()})

    @app.route("/api/auth/logout", methods=["POST"])
    def api_logout():
        logout()
        return jsonify({"ok": True})

    # ═══════════════════════════════════════════════════════════════
    # DASHBOARD
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/dashboard")
    @auth_required
    def api_dashboard():
        from core.dispatch_engine import get_engine_status, get_dispatch_log
        from core.lead_manager import get_leads_stats
        from core.campaign_manager import list_campaigns

        status = get_engine_status()
        leads_stats = get_leads_stats()
        campaigns = list_campaigns()
        recent_log = get_dispatch_log(limit=10)

        return jsonify({
            "engine": status,
            "leads": leads_stats,
            "campaigns_count": len(campaigns),
            "recent_dispatches": recent_log,
        })

    # ═══════════════════════════════════════════════════════════════
    # LEADS
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/leads")
    @auth_required
    def api_leads_list():
        from core.lead_manager import list_leads, count_leads

        status = request.args.get("status")
        search = request.args.get("search")
        tag = request.args.get("tag")
        limit = int(request.args.get("limit", 100))
        paused = request.args.get("paused") == "true"

        tags = [tag] if tag else None
        leads = list_leads(status=status, tags=tags, search=search, limit=limit, paused_only=paused)
        total = count_leads()

        return jsonify({"leads": leads, "total": total})

    @app.route("/api/leads", methods=["POST"])
    @auth_required
    def api_leads_add():
        from core.lead_manager import add_lead

        data = request.get_json(silent=True) or {}
        phone = data.get("phone", "").strip()
        name = data.get("name", "").strip()
        tags = data.get("tags", [])
        notes = data.get("notes", "")

        if not phone:
            return jsonify({"error": "Telefone é obrigatório"}), 400

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        result = add_lead(phone=phone, name=name, tags=tags, added_by="web_admin", notes=notes)
        if result:
            return jsonify({"ok": True, "lead": result})
        return jsonify({"error": "Lead já existe (telefone duplicado)"}), 409

    @app.route("/api/leads/<lead_id>", methods=["PUT"])
    @auth_required
    def api_leads_update(lead_id):
        from core.lead_manager import get_lead, update_lead_tags
        from database import get_supabase

        data = request.get_json(silent=True) or {}
        lead = get_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead não encontrado"}), 404

        sb = get_supabase()
        updates = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "notes" in data:
            updates["notes"] = data["notes"]
        if "status" in data:
            updates["status"] = data["status"]

        if updates:
            sb.table("leads").update(updates).eq("id", lead_id).execute()

        if "tags" in data:
            tags = data["tags"]
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            update_lead_tags(lead_id, tags, mode="set")

        updated = get_lead(lead_id)
        return jsonify({"ok": True, "lead": updated})

    @app.route("/api/leads/<lead_id>", methods=["DELETE"])
    @auth_required
    def api_leads_delete(lead_id):
        from core.lead_manager import remove_lead
        if remove_lead(lead_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Lead não encontrado"}), 404

    @app.route("/api/leads/<lead_id>/pause", methods=["POST"])
    @auth_required
    def api_leads_pause(lead_id):
        from core.lead_manager import pause_lead
        data = request.get_json(silent=True) or {}
        if pause_lead(lead_id, data.get("reason", "")):
            return jsonify({"ok": True})
        return jsonify({"error": "Lead não encontrado"}), 404

    @app.route("/api/leads/<lead_id>/resume", methods=["POST"])
    @auth_required
    def api_leads_resume(lead_id):
        from core.lead_manager import resume_lead
        if resume_lead(lead_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Lead não encontrado"}), 404

    @app.route("/api/leads/<lead_id>/convert", methods=["POST"])
    @auth_required
    def api_leads_convert(lead_id):
        from core.lead_manager import update_lead_remarketing
        from datetime import datetime
        from config import BR_TZ
        if update_lead_remarketing(lead_id, status="converted", completed_at=datetime.now(BR_TZ).isoformat()):
            return jsonify({"ok": True})
        return jsonify({"error": "Lead não encontrado"}), 404

    @app.route("/api/leads/<lead_id>/reset-funnel", methods=["POST"])
    @auth_required
    def api_leads_reset_funnel(lead_id):
        from core.remarketing_funnel import reset_lead_funnel
        if reset_lead_funnel(lead_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Lead não encontrado"}), 404

    @app.route("/api/leads/import", methods=["POST"])
    @auth_required
    def api_leads_import():
        from core.lead_manager import import_leads_from_json, import_leads_from_csv_text

        # JSON body
        if request.is_json:
            data = request.get_json()
            if isinstance(data, list):
                result = import_leads_from_json(data, added_by="web_import")
                return jsonify({"ok": True, **result})
            return jsonify({"error": "Envie um array JSON de leads"}), 400

        # File upload
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "Envie um arquivo ou JSON"}), 400

        filename = file.filename or ""
        content = file.read().decode("utf-8")

        if filename.endswith(".json"):
            data = json.loads(content)
            result = import_leads_from_json(data, added_by="web_file_import")
        elif filename.endswith(".csv"):
            result = import_leads_from_csv_text(content, added_by="web_csv_import")
        else:
            return jsonify({"error": "Formato não suportado. Use .json ou .csv"}), 400

        return jsonify({"ok": True, **result})

    @app.route("/api/leads/bulk-pool", methods=["POST"])
    @auth_required
    def api_leads_bulk_pool():
        from core.remarketing_funnel import bulk_enter_pool
        data = request.get_json(silent=True) or {}
        campaign_id = data.get("campaign_id", "")
        if not campaign_id:
            return jsonify({"error": "campaign_id é obrigatório"}), 400
        count = bulk_enter_pool(campaign_id)
        return jsonify({"ok": True, "entered": count})

    # ═══════════════════════════════════════════════════════════════
    # CAMPANHAS
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/campaigns")
    @auth_required
    def api_campaigns_list():
        from core.campaign_manager import list_campaigns
        status = request.args.get("status")
        campaigns = list_campaigns(status=status)
        return jsonify({"campaigns": campaigns})

    @app.route("/api/campaigns", methods=["POST"])
    @auth_required
    def api_campaigns_create():
        from core.campaign_manager import create_campaign

        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Nome é obrigatório"}), 400

        tags = data.get("target_tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        campaign = create_campaign(
            name=name,
            target_tags=tags,
            message_template_key=data.get("message_template_key", "reativacao_geral"),
            custom_data=data.get("custom_data"),
            schedule=data.get("schedule"),
            funnel_days=data.get("funnel_days"),
        )
        return jsonify({"ok": True, "campaign": campaign})

    @app.route("/api/campaigns/<camp_id>", methods=["PUT"])
    @auth_required
    def api_campaigns_update(camp_id):
        from core.campaign_manager import (
            get_campaign, update_campaign_data, update_campaign_schedule,
            update_campaign_funnel_days,
        )
        from database import get_supabase

        data = request.get_json(silent=True) or {}
        campaign = get_campaign(camp_id)
        if not campaign:
            return jsonify({"error": "Campanha não encontrada"}), 404

        sb = get_supabase()

        # Atualiza campos diretos
        direct_updates = {}
        if "name" in data:
            direct_updates["name"] = data["name"]
        if "message_template_key" in data:
            direct_updates["message_template_key"] = data["message_template_key"]
        if "target_tags" in data:
            tags = data["target_tags"]
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            direct_updates["target_tags"] = tags

        if direct_updates:
            sb.table("campaigns").update(direct_updates).eq("id", camp_id).execute()

        if "custom_data" in data:
            update_campaign_data(camp_id, data["custom_data"])
        if "schedule" in data:
            update_campaign_schedule(camp_id, data["schedule"])
        if "funnel_days" in data:
            update_campaign_funnel_days(camp_id, data["funnel_days"])

        updated = get_campaign(camp_id)
        return jsonify({"ok": True, "campaign": updated})

    @app.route("/api/campaigns/<camp_id>", methods=["DELETE"])
    @auth_required
    def api_campaigns_delete(camp_id):
        from core.campaign_manager import remove_campaign
        if remove_campaign(camp_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Campanha não encontrada"}), 404

    @app.route("/api/campaigns/<camp_id>/pause", methods=["POST"])
    @auth_required
    def api_campaigns_pause(camp_id):
        from core.campaign_manager import pause_campaign
        if pause_campaign(camp_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Campanha não encontrada"}), 404

    @app.route("/api/campaigns/<camp_id>/resume", methods=["POST"])
    @auth_required
    def api_campaigns_resume(camp_id):
        from core.campaign_manager import resume_campaign
        if resume_campaign(camp_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Campanha não encontrada"}), 404

    # ─── Mensagens por dia ─────────────────────────────────────────

    @app.route("/api/campaigns/<camp_id>/messages")
    @auth_required
    def api_campaign_messages(camp_id):
        from core.campaign_manager import get_all_day_messages, get_campaign
        campaign = get_campaign(camp_id)
        if not campaign:
            return jsonify({"error": "Campanha não encontrada"}), 404

        messages = get_all_day_messages(camp_id)
        funnel_days = campaign.get("funnel_days", [1, 2, 3, 5, 7, 14, 30])
        return jsonify({"messages": messages, "funnel_days": funnel_days})

    @app.route("/api/campaigns/<camp_id>/messages/<int:day>", methods=["PUT"])
    @auth_required
    def api_campaign_message_set(camp_id, day):
        from core.campaign_manager import set_day_message
        data = request.get_json(silent=True) or {}
        text = data.get("message_text", "").strip()
        if not text:
            return jsonify({"error": "message_text é obrigatório"}), 400
        if set_day_message(camp_id, day, text):
            return jsonify({"ok": True})
        return jsonify({"error": "Erro ao salvar mensagem"}), 500

    @app.route("/api/campaigns/<camp_id>/messages/<int:day>", methods=["DELETE"])
    @auth_required
    def api_campaign_message_delete(camp_id, day):
        from core.campaign_manager import delete_day_message
        if delete_day_message(camp_id, day):
            return jsonify({"ok": True})
        return jsonify({"error": "Mensagem não encontrada"}), 404

    # ═══════════════════════════════════════════════════════════════
    # ENGINE CONTROL
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/engine/status")
    @auth_required
    def api_engine_status():
        from core.dispatch_engine import get_engine_status
        return jsonify(get_engine_status())

    @app.route("/api/engine/pause", methods=["POST"])
    @auth_required
    def api_engine_pause():
        from core.dispatch_engine import set_engine_paused
        set_engine_paused(True)
        return jsonify({"ok": True, "paused": True})

    @app.route("/api/engine/resume", methods=["POST"])
    @auth_required
    def api_engine_resume():
        from core.dispatch_engine import set_engine_paused
        set_engine_paused(False)
        return jsonify({"ok": True, "paused": False})

    # ═══════════════════════════════════════════════════════════════
    # DISPATCH LOG
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/dispatch/log")
    @auth_required
    def api_dispatch_log():
        from core.dispatch_engine import get_dispatch_log
        limit = int(request.args.get("limit", 50))
        campaign_id = request.args.get("campaign_id")
        log = get_dispatch_log(limit=limit, campaign_id=campaign_id)
        return jsonify({"log": log})

    # ═══════════════════════════════════════════════════════════════
    # DIRECT BROADCAST (DISPARO RÁPIDO & TESTE)
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/broadcast/start", methods=["POST"])
    @auth_required
    def api_broadcast_start():
        import asyncio
        from core.direct_broadcast import start_direct_broadcast

        data = request.get_json(silent=True) or {}
        lead_ids = data.get("lead_ids", [])
        message_template = data.get("message_template", "").strip()
        image_url = data.get("image_url", "").strip() or None
        min_delay = int(data.get("min_delay", 15))
        max_delay = int(data.get("max_delay", 45))
        vary_text = bool(data.get("vary_text", True))

        if not lead_ids:
            return jsonify({"error": "Nenhum lead selecionado."}), 400
        if not message_template:
            return jsonify({"error": "Texto da mensagem é obrigatório."}), 400

        # Roda a função assíncrona na thread do Flask
        success = asyncio.run(
            start_direct_broadcast(
                lead_ids=lead_ids,
                message_template=message_template,
                image_url=image_url,
                min_delay=min_delay,
                max_delay=max_delay,
                vary_text=vary_text,
            )
        )

        if success:
            return jsonify({"ok": True, "total": len(lead_ids)})
        return jsonify({"error": "Já existe um disparo em andamento."}), 409

    @app.route("/api/broadcast/status")
    @auth_required
    def api_broadcast_status():
        from core.direct_broadcast import get_broadcast_status
        return jsonify(get_broadcast_status())

    @app.route("/api/broadcast/cancel", methods=["POST"])
    @auth_required
    def api_broadcast_cancel():
        from core.direct_broadcast import cancel_broadcast
        if cancel_broadcast():
            return jsonify({"ok": True, "message": "Cancelamento solicitado."})
        return jsonify({"error": "Nenhum disparo em andamento para cancelar."}), 400

    # ═══════════════════════════════════════════════════════════════
    # UPLOAD DE IMAGEM
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/upload/image", methods=["POST"])
    @auth_required
    def api_upload_image():
        import uuid
        import os

        if "image" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"error": "Arquivo vazio"}), 400

        uploads_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            return jsonify({"error": "Formato de imagem inválido. Use JPG, PNG ou WEBP"}), 400

        filename = f"img_{uuid.uuid4().hex[:10]}{ext}"
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)

        # Gera URL completa da imagem baseada no host da requisição
        host_url = request.host_url.rstrip("/")
        image_url = f"{host_url}/static/uploads/{filename}"

        return jsonify({"ok": True, "image_url": image_url, "filename": filename})

    return app
