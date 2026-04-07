"""
Main application routes — dashboard and cleanup actions.
"""

from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request

from src.services.slack_cleaner import SlackCleaner

main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    """Health check endpoint for Railway."""
    return jsonify({"status": "ok"}), 200


def require_auth(f):
    """Decorator to require Slack authentication."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if "slack_token" not in session:
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    return decorated


@main_bp.route("/")
def index():
    """Landing page."""
    if "slack_token" in session:
        return redirect(url_for("main.dashboard"))
    error = request.args.get("error")
    return render_template("index.html", error=error)


@main_bp.route("/dashboard")
@require_auth
def dashboard():
    """Main dashboard — shows conversations and cleanup options."""
    cleaner = SlackCleaner(session["slack_token"])
    dms = cleaner.list_dm_conversations()
    group_dms = cleaner.list_group_dms()

    return render_template(
        "dashboard.html",
        user_name=session.get("slack_user_name", ""),
        team=session.get("slack_team", ""),
        dms=dms,
        group_dms=group_dms,
    )


# ------------------------------------------------------------------
# API endpoints (called by frontend JS)
# ------------------------------------------------------------------


@main_bp.route("/api/conversations")
@require_auth
def api_conversations():
    """List all DM conversations with message counts."""
    cleaner = SlackCleaner(session["slack_token"])
    dms = cleaner.list_dm_conversations()
    counts = cleaner.count_my_messages_batch([dm["id"] for dm in dms])
    results = [{**dm, "my_message_count": counts.get(dm["id"], 0)} for dm in dms]
    return jsonify(results)


@main_bp.route("/api/preview/<channel_id>")
@require_auth
def api_preview(channel_id: str):
    """Preview messages that would be deleted."""
    cleaner = SlackCleaner(session["slack_token"])
    messages = cleaner.get_my_messages(channel_id)

    preview = [
        {
            "ts": m["ts"],
            "text": m.get("text", "")[:100],
            "date": m.get("ts", ""),
        }
        for m in messages[:50]  # Show max 50 for preview
    ]

    return jsonify({"total": len(messages), "preview": preview})


@main_bp.route("/api/delete/<channel_id>", methods=["POST"])
@require_auth
def api_delete(channel_id: str):
    """Delete all user messages in a specific conversation."""
    dry_run = request.json.get("dry_run", False) if request.is_json else False

    cleaner = SlackCleaner(session["slack_token"])
    stats = cleaner.delete_messages(channel_id, dry_run=dry_run)

    return jsonify(stats.to_dict())


@main_bp.route("/api/delete-all", methods=["POST"])
@require_auth
def api_delete_all():
    """Delete all user messages across all DMs."""
    dry_run = request.json.get("dry_run", False) if request.is_json else False

    cleaner = SlackCleaner(session["slack_token"])
    stats = cleaner.cleanup_all_dms(dry_run=dry_run)

    return jsonify(stats.to_dict())
