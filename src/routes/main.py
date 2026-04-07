"""
Main application routes — dashboard, cleanup actions, and SSE streaming.
"""

from flask import (
    Blueprint, render_template, session, redirect, url_for,
    jsonify, request, Response, current_app, stream_with_context,
)

from src.services.slack_cleaner import SlackCleaner
from src.services.job_manager import start_cleanup_job

main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@main_bp.route("/robots.txt")
def robots():
    return Response(
        "User-agent: *\nAllow: /\nSitemap: https://slack-offboarding.ruwad.io/sitemap.xml\n",
        mimetype="text/plain",
    )


@main_bp.route("/sitemap.xml")
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://slack-offboarding.ruwad.io</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(xml, mimetype="application/xml")


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
    channels = cleaner.list_channels()

    # Check if there's an active job
    jm = current_app.job_manager
    active_job = jm.get_active_job(session.get("slack_user_id", ""))

    return render_template(
        "dashboard.html",
        user_name=session.get("slack_user_name", ""),
        team=session.get("slack_team", ""),
        dms=dms,
        group_dms=group_dms,
        channels=channels,
        active_job=active_job,
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
        for m in messages[:50]
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


# ------------------------------------------------------------------
# Background job endpoints
# ------------------------------------------------------------------


@main_bp.route("/api/nuke", methods=["POST"])
@require_auth
def api_nuke():
    """Start a full nuke job in the background. Returns job ID."""
    jm = current_app.job_manager
    user_id = session.get("slack_user_id", "")

    # Check for existing active job
    active = jm.get_active_job(user_id)
    if active:
        return jsonify({"error": "A job is already running", "job_id": active["id"]}), 409

    job_id = jm.create_job(
        user_id=user_id,
        job_type="nuke",
        token=session["slack_token"],
    )
    start_cleanup_job(jm, job_id)

    return jsonify({"job_id": job_id}), 202


@main_bp.route("/api/job/<job_id>")
@require_auth
def api_job_status(job_id: str):
    """Get current job status."""
    jm = current_app.job_manager
    job = jm.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@main_bp.route("/api/job/<job_id>/stream")
@require_auth
def api_job_stream(job_id: str):
    """SSE stream of job progress."""
    jm = current_app.job_manager

    job = jm.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        yield from jm.stream_progress(job_id)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
