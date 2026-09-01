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
from web.auth import auth_required, login, login_instance, logout, check_auth
from web.context import get_session_instance, set_session_instance, instance_required

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

    @app.route("/api/campaigns/<camp_id>/dispatch-one", methods=["POST"])
    @auth_required
    def api_campaigns_dispatch_one(camp_id):
        import asyncio
        from core.dispatch_engine import force_dispatch_one
        result = asyncio.run(force_dispatch_one(camp_id))
        if result:
            return jsonify({"ok": True, "lead_name": result})
        return jsonify({"error": "Sem leads elegíveis no momento ou todos já receberam mensagem hoje nesta campanha."}), 400

    @app.route("/api/leads/<lead_id>/test-message", methods=["POST"])
    @auth_required
    def api_leads_test_message(lead_id):
        from core.lead_manager import get_lead
        from platforms.whatsapp_client import send_whatsapp_message_sync

        lead = get_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead não encontrado"}), 404

        data = request.get_json(silent=True) or {}
        custom_text = data.get("text", "").strip()
        first_name = (lead.get("name") or "").split()[0] if lead.get("name") else "cliente"
        text = custom_text or f"🤖 Olá {first_name}, este é um teste de conexão do Bot Remarketing IMOB!"

        success, err = send_whatsapp_message_sync(lead["phone"], text)
        if success:
            return jsonify({"ok": True, "phone": lead["phone"], "message": text})
        return jsonify({"error": f"Falha no envio: {err}"}), 500

    @app.route("/api/whatsapp/status")
    @auth_required
    def api_whatsapp_status():
        from platforms.whatsapp_client import check_whatsapp_connection_sync, get_active_instance, WHATSAPP_API_URL
        target_instance = request.args.get("instance") or get_active_instance()
        is_connected, status_msg = check_whatsapp_connection_sync(target_instance)
        return jsonify({
            "connected": is_connected,
            "message": status_msg,
            "instance": target_instance,
            "api_url": WHATSAPP_API_URL,
        })

    @app.route("/api/whatsapp/instances")
    @auth_required
    def api_whatsapp_instances():
        from platforms.whatsapp_client import list_whatsapp_instances, get_active_instance
        instances = list_whatsapp_instances()
        active = get_active_instance()
        return jsonify({
            "instances": instances,
            "active_instance": active,
        })

    @app.route("/api/whatsapp/select-instance", methods=["POST"])
    @auth_required
    def api_whatsapp_select_instance():
        from platforms.whatsapp_client import set_active_instance, check_whatsapp_connection_sync
        data = request.get_json(silent=True) or {}
        instance_name = str(data.get("instance") or "").strip()
        if not instance_name:
            return jsonify({"error": "Nome da instância é obrigatório"}), 400
        set_active_instance(instance_name)
        is_connected, msg = check_whatsapp_connection_sync(instance_name)
        return jsonify({
            "ok": True,
            "active_instance": instance_name,
            "connected": is_connected,
            "message": msg,
        })

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
        try:
            from core.direct_broadcast import start_direct_broadcast
            from platforms.whatsapp_client import check_whatsapp_connection_sync, get_active_instance

            data = request.get_json(silent=True) or {}
            lead_ids = data.get("lead_ids", [])
            message_template = str(data.get("message_template") or "").strip()
            raw_image_url = data.get("image_url")
            image_url = str(raw_image_url).strip() if raw_image_url else None
            min_delay = int(data.get("min_delay") or 15)
            max_delay = int(data.get("max_delay") or 40)
            vary_text = bool(data.get("vary_text", True))
            vary_synonyms = bool(data.get("vary_synonyms", True))
            selected_instance = str(data.get("instance") or "").strip() or get_active_instance()

            if not lead_ids:
                return jsonify({"error": "Nenhum lead selecionado."}), 400
            if not message_template:
                return jsonify({"error": "Texto da mensagem é obrigatório."}), 400

            # Pré-validação da conexão com o WhatsApp / Evolution API
            is_connected, status_msg = check_whatsapp_connection_sync(selected_instance)
            if not is_connected:
                return jsonify({"error": f"⚠️ Não foi possível iniciar o disparo: {status_msg}"}), 503

            # Inicia a fila em thread separada segura
            success = start_direct_broadcast(
                lead_ids=lead_ids,
                message_template=message_template,
                image_url=image_url,
                min_delay=min_delay,
                max_delay=max_delay,
                vary_text=vary_text,
                vary_synonyms=vary_synonyms,
                instance=selected_instance,
            )

            if success:
                return jsonify({"ok": True, "total": len(lead_ids)})
            return jsonify({"error": "Já existe um disparo em andamento. Aguarde finalizar ou cancele antes de iniciar outro."}), 409
        except Exception as e:
            logger.error("❌ Erro interno ao iniciar disparo direto: %s", e, exc_info=True)
            return jsonify({"error": f"Erro interno no servidor: {str(e)}"}), 500

    @app.route("/api/broadcast/preview", methods=["POST"])
    @auth_required
    def api_broadcast_preview():
        from core.direct_broadcast import preview_humanized_message
        from core.lead_manager import get_lead

        data = request.get_json(silent=True) or {}
        message_template = str(data.get("message_template") or "").strip()
        lead_id = data.get("lead_id")
        sample_lead = get_lead(lead_id) if lead_id else {"name": "", "phone": "5512988265141"}
        vary_synonyms = bool(data.get("vary_synonyms", True))
        vary_text = bool(data.get("vary_text", True))

        preview = preview_humanized_message(
            template=message_template,
            sample_lead=sample_lead,
            vary_synonyms=vary_synonyms,
            vary_text=vary_text,
        )
        return jsonify({"ok": True, "preview": preview})

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

        # Usa URL relativa para forçar o fallback de leitura local (base64) no envio
        image_url = f"/static/uploads/{filename}"

        return jsonify({"ok": True, "image_url": image_url, "filename": filename})

    # ═══════════════════════════════════════════════════════════════
    # ACESSO POR NÚMERO (INSTÂNCIA) — LOGIN, SESSÃO, CONFIGURAÇÕES
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/instances/available")
    def api_instances_available():
        """Lista os números conectados (Evolution) mesclados com o acesso
        configurado. Não exige login — alimenta a tela de seleção de número."""
        from platforms.whatsapp_client import list_whatsapp_instances
        from core.instance_access import list_instance_access
        try:
            evo = list_whatsapp_instances()
        except Exception:
            evo = []
        access = {a["instance_name"]: a for a in list_instance_access()}
        merged = []
        for inst in evo:
            acc = access.get(inst["name"], {})
            merged.append({
                "name": inst["name"],
                "status": inst.get("status"),
                "phone_formatted": inst.get("phone_formatted"),
                "profile_name": inst.get("profile_name"),
                "profile_pic": inst.get("profile_pic"),
                "display_name": acc.get("display_name") or inst.get("profile_name") or inst["name"],
                "has_access": bool(acc),
            })
        # Inclui números com acesso mas que não voltaram da Evolution (offline)
        evo_names = {i["name"] for i in evo}
        for name, acc in access.items():
            if name not in evo_names:
                merged.append({
                    "name": name, "status": "close",
                    "phone_formatted": "", "profile_name": acc.get("display_name"),
                    "profile_pic": "", "display_name": acc.get("display_name") or name,
                    "has_access": True,
                })
        return jsonify({"instances": merged})

    @app.route("/api/instance/login", methods=["POST"])
    def api_instance_login():
        from platforms.whatsapp_client import set_active_instance
        data = request.get_json(silent=True) or {}
        instance_name = str(data.get("instance") or "").strip()
        password = data.get("password", "")
        if not instance_name:
            return jsonify({"error": "Número (instância) é obrigatório"}), 400
        if login_instance(instance_name, password):
            # Define também a instância ativa global de envio para este número
            set_active_instance(instance_name)
            return jsonify({"ok": True, "instance": instance_name})
        return jsonify({"error": "Senha incorreta para este número"}), 401

    @app.route("/api/session")
    def api_session():
        return jsonify({
            "authenticated": check_auth(),
            "instance": get_session_instance(),
            "is_admin": session.get("is_admin", False),
        })

    @app.route("/api/instance/password", methods=["POST"])
    @auth_required
    @instance_required
    def api_instance_password():
        from core.instance_access import set_instance_password
        data = request.get_json(silent=True) or {}
        new_password = data.get("new_password", "")
        if not new_password or len(new_password) < 3:
            return jsonify({"error": "A nova senha deve ter ao menos 3 caracteres"}), 400
        if set_instance_password(get_session_instance(), new_password):
            return jsonify({"ok": True})
        return jsonify({"error": "Falha ao atualizar senha"}), 500

    @app.route("/api/instance/settings")
    @auth_required
    @instance_required
    def api_instance_settings_get():
        from core.instance_access import get_instance_access, ensure_instance_access
        inst = get_session_instance()
        acc = get_instance_access(inst) or ensure_instance_access(inst)
        acc = dict(acc)
        acc.pop("password_hash", None)
        return jsonify(acc)

    @app.route("/api/instance/settings", methods=["PUT"])
    @auth_required
    @instance_required
    def api_instance_settings_put():
        from core.instance_access import update_instance_settings
        data = request.get_json(silent=True) or {}
        ok = update_instance_settings(
            get_session_instance(),
            display_name=data.get("display_name"),
            daily_limit=data.get("daily_limit"),
            warmup_enabled=data.get("warmup_enabled"),
        )
        return jsonify({"ok": ok})

    # ═══════════════════════════════════════════════════════════════
    # BOLSÕES (POOLS) POR EMPREENDIMENTO
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/pools")
    @auth_required
    @instance_required
    def api_pools_list():
        from core.pool_manager import list_pools, get_pool_stats
        pools = list_pools(get_session_instance())
        for p in pools:
            p["stats"] = get_pool_stats(p["id"])
        return jsonify({"pools": pools})

    @app.route("/api/pools", methods=["POST"])
    @auth_required
    @instance_required
    def api_pools_create():
        from core.pool_manager import create_pool
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Nome do bolsão é obrigatório"}), 400
        pool = create_pool(
            name=name,
            instance_name=get_session_instance(),
            description=data.get("description", ""),
            color=data.get("color", "#25D366"),
            empreendimento_data=data.get("empreendimento_data"),
        )
        return jsonify({"ok": True, "pool": pool})

    @app.route("/api/pools/<pool_id>", methods=["PUT"])
    @auth_required
    @instance_required
    def api_pools_update(pool_id):
        from core.pool_manager import update_pool
        data = request.get_json(silent=True) or {}
        ok = update_pool(
            pool_id,
            name=data.get("name"),
            description=data.get("description"),
            color=data.get("color"),
            empreendimento_data=data.get("empreendimento_data"),
            status=data.get("status"),
        )
        return jsonify({"ok": ok})

    @app.route("/api/pools/<pool_id>", methods=["DELETE"])
    @auth_required
    @instance_required
    def api_pools_delete(pool_id):
        from core.pool_manager import delete_pool
        if delete_pool(pool_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Bolsão não encontrado"}), 404

    @app.route("/api/pools/<pool_id>/stats")
    @auth_required
    @instance_required
    def api_pools_stats(pool_id):
        from core.pool_manager import get_pool_stats
        return jsonify(get_pool_stats(pool_id))

    # ═══════════════════════════════════════════════════════════════
    # GRUPOS DE WHATSAPP (JORNAL DA CONSTRUTORA)
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/groups/sync", methods=["POST"])
    @auth_required
    @instance_required
    def api_groups_sync():
        from core.group_manager import sync_groups
        result = sync_groups(get_session_instance())
        return jsonify({"ok": True, **result})

    @app.route("/api/groups")
    @auth_required
    @instance_required
    def api_groups_list():
        from core.group_manager import list_groups
        journal_only = request.args.get("journal") == "true"
        groups = list_groups(get_session_instance(), journal_only=journal_only)
        return jsonify({"groups": groups})

    @app.route("/api/groups/<group_id>/journal", methods=["POST"])
    @auth_required
    @instance_required
    def api_groups_journal(group_id):
        from core.group_manager import set_group_journal
        data = request.get_json(silent=True) or {}
        ok = set_group_journal(group_id, bool(data.get("is_journal", True)))
        return jsonify({"ok": ok})

    @app.route("/api/groups/<group_id>/pool", methods=["POST"])
    @auth_required
    @instance_required
    def api_groups_pool(group_id):
        from core.group_manager import link_group_pool
        data = request.get_json(silent=True) or {}
        ok = link_group_pool(group_id, data.get("pool_id"))
        return jsonify({"ok": ok})

    @app.route("/api/groups/<group_id>", methods=["DELETE"])
    @auth_required
    @instance_required
    def api_groups_delete(group_id):
        from core.group_manager import delete_group
        if delete_group(group_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Grupo não encontrado"}), 404

    # ═══════════════════════════════════════════════════════════════
    # SEGMENTOS (LISTAS INTERNAS DE LEADS)
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/segments")
    @auth_required
    @instance_required
    def api_segments_list():
        from core.segment_manager import list_segments
        return jsonify({"segments": list_segments(get_session_instance())})

    @app.route("/api/segments", methods=["POST"])
    @auth_required
    @instance_required
    def api_segments_create():
        from core.segment_manager import create_segment
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Nome do segmento é obrigatório"}), 400
        seg = create_segment(
            name=name,
            instance_name=get_session_instance(),
            pool_id=data.get("pool_id"),
            description=data.get("description", ""),
        )
        return jsonify({"ok": True, "segment": seg})

    @app.route("/api/segments/<segment_id>", methods=["DELETE"])
    @auth_required
    @instance_required
    def api_segments_delete(segment_id):
        from core.segment_manager import delete_segment
        if delete_segment(segment_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Segmento não encontrado"}), 404

    @app.route("/api/segments/<segment_id>/members", methods=["GET"])
    @auth_required
    @instance_required
    def api_segments_members_get(segment_id):
        from core.segment_manager import get_segment_lead_ids
        return jsonify({"lead_ids": get_segment_lead_ids(segment_id)})

    @app.route("/api/segments/<segment_id>/members", methods=["POST"])
    @auth_required
    @instance_required
    def api_segments_members_add(segment_id):
        from core.segment_manager import add_members
        data = request.get_json(silent=True) or {}
        lead_ids = data.get("lead_ids", [])
        if not lead_ids:
            return jsonify({"error": "lead_ids é obrigatório"}), 400
        added = add_members(segment_id, lead_ids)
        return jsonify({"ok": True, "added": added})

    @app.route("/api/segments/<segment_id>/members/<lead_id>", methods=["DELETE"])
    @auth_required
    @instance_required
    def api_segments_members_remove(segment_id, lead_id):
        from core.segment_manager import remove_member
        if remove_member(segment_id, lead_id):
            return jsonify({"ok": True})
        return jsonify({"error": "Membro não encontrado"}), 404

    # ═══════════════════════════════════════════════════════════════
    # DISPARO PARALELO (POR NÚMERO) — LEADS OU GRUPOS
    # ═══════════════════════════════════════════════════════════════

    @app.route("/api/broadcast2/start", methods=["POST"])
    @auth_required
    @instance_required
    def api_broadcast2_start():
        from core.parallel_broadcast import start_broadcast, is_instance_busy
        from platforms.whatsapp_client import check_whatsapp_connection_sync
        from core.segment_manager import get_segment_lead_ids

        data = request.get_json(silent=True) or {}
        instance = get_session_instance()
        kind = data.get("kind", "leads")
        message_template = str(data.get("message_template") or "").strip()
        raw_image = data.get("image_url")
        image_url = str(raw_image).strip() if raw_image else None
        min_delay = int(data.get("min_delay") or 15)
        max_delay = int(data.get("max_delay") or 40)
        vary_text = bool(data.get("vary_text", True))
        vary_synonyms = bool(data.get("vary_synonyms", True))

        if not message_template:
            return jsonify({"error": "Texto da mensagem é obrigatório."}), 400

        if is_instance_busy(instance):
            return jsonify({"error": "Este número já tem um disparo em andamento. Aguarde finalizar ou cancele."}), 409

        # Monta a lista de alvos conforme o tipo
        if kind == "groups":
            targets = data.get("group_jids") or data.get("targets") or []
        else:
            targets = data.get("lead_ids") or data.get("targets") or []
            segment_id = data.get("segment_id")
            if segment_id and not targets:
                targets = get_segment_lead_ids(segment_id)

        if not targets:
            return jsonify({"error": "Nenhum destinatário selecionado."}), 400

        is_connected, status_msg = check_whatsapp_connection_sync(instance)
        if not is_connected:
            return jsonify({"error": f"⚠️ Não foi possível iniciar: {status_msg}"}), 503

        ok = start_broadcast(
            instance_name=instance, targets=targets,
            message_template=message_template, image_url=image_url,
            min_delay=min_delay, max_delay=max_delay,
            vary_text=vary_text, vary_synonyms=vary_synonyms, kind=kind,
        )
        if ok:
            return jsonify({"ok": True, "total": len(targets), "instance": instance})
        return jsonify({"error": "Não foi possível iniciar o disparo."}), 409

    @app.route("/api/broadcast2/status")
    @auth_required
    @instance_required
    def api_broadcast2_status():
        from core.parallel_broadcast import get_broadcast_status
        return jsonify(get_broadcast_status(get_session_instance()))

    @app.route("/api/broadcast2/status-all")
    @auth_required
    def api_broadcast2_status_all():
        from core.parallel_broadcast import get_all_broadcast_status
        return jsonify(get_all_broadcast_status())

    @app.route("/api/broadcast2/cancel", methods=["POST"])
    @auth_required
    @instance_required
    def api_broadcast2_cancel():
        from core.parallel_broadcast import cancel_broadcast
        if cancel_broadcast(get_session_instance()):
            return jsonify({"ok": True})
        return jsonify({"error": "Nenhum disparo em andamento para este número."}), 400

    return app
