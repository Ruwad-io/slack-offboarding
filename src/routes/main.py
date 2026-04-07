"""
Main application routes — dashboard, cleanup actions, and SSE streaming.
"""

import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.templating import Jinja2Templates

from src.services.slack_cleaner import SlackCleaner
from src.services.job_manager import start_cleanup_job

main_router = APIRouter()
templates = Jinja2Templates(directory="templates")


class DeleteRequest(BaseModel):
    dry_run: bool = False


# ------------------------------------------------------------------
# Auth dependency
# ------------------------------------------------------------------


def require_auth(request: Request) -> dict:
    """Check session for Slack token, redirect to index if missing."""
    if "slack_token" not in request.session:
        raise AuthRedirect()
    return request.session


class AuthRedirect(Exception):
    pass


# ------------------------------------------------------------------
# Static pages
# ------------------------------------------------------------------


@main_router.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@main_router.get("/robots.txt")
def robots():
    return Response(
        "User-agent: *\nAllow: /\nSitemap: https://slack-offboarding.ruwad.io/sitemap.xml\n",
        media_type="text/plain",
    )


@main_router.get("/sitemap.xml")
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://slack-offboarding.ruwad.io</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(xml, media_type="application/xml")


@main_router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Landing page."""
    if "slack_token" in request.session:
        return RedirectResponse(url="/dashboard", status_code=302)
    error = request.query_params.get("error")
    return templates.TemplateResponse(request, "index.html", {"error": error})


@main_router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, session: dict = Depends(require_auth)):
    """Main dashboard — shows conversations and cleanup options."""
    cleaner = SlackCleaner(session["slack_token"])
    dms = cleaner.list_dm_conversations()
    group_dms = cleaner.list_group_dms()
    channels = cleaner.list_channels()

    jm = request.app.state.job_manager
    active_job = jm.get_active_job(session.get("slack_user_id", ""))

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user_name": session.get("slack_user_name", ""),
            "team": session.get("slack_team", ""),
            "dms": dms,
            "group_dms": group_dms,
            "channels": channels,
            "active_job": active_job,
        },
    )


# ------------------------------------------------------------------
# API endpoints (called by frontend JS)
# ------------------------------------------------------------------


@main_router.get("/api/conversations")
def api_conversations(session: dict = Depends(require_auth)):
    """List all DM conversations with message counts."""
    cleaner = SlackCleaner(session["slack_token"])
    dms = cleaner.list_dm_conversations()
    counts = cleaner.count_my_messages_batch([dm["id"] for dm in dms])
    return [{**dm, "my_message_count": counts.get(dm["id"], 0)} for dm in dms]


@main_router.get("/api/counts/stream")
def api_counts_stream(request: Request, session: dict = Depends(require_auth)):
    """SSE stream that counts messages per conversation one by one."""
    token = session["slack_token"]

    def generate():
        cleaner = SlackCleaner(token)
        dms = cleaner.list_dm_conversations()
        for dm in dms:
            count = cleaner.count_my_messages(dm["id"])
            yield f"data: {json.dumps({'id': dm['id'], 'count': count})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@main_router.get("/api/preview/{channel_id}")
def api_preview(channel_id: str, session: dict = Depends(require_auth)):
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

    return {"total": len(messages), "preview": preview}


@main_router.post("/api/delete/{channel_id}")
def api_delete(
    channel_id: str, body: DeleteRequest = DeleteRequest(), session: dict = Depends(require_auth)
):
    """Delete all user messages in a specific conversation."""
    cleaner = SlackCleaner(session["slack_token"])
    stats = cleaner.delete_messages(channel_id, dry_run=body.dry_run)
    return stats.to_dict()


# ------------------------------------------------------------------
# Background job endpoints
# ------------------------------------------------------------------


@main_router.post("/api/nuke", status_code=202)
def api_nuke(request: Request, session: dict = Depends(require_auth)):
    """Start a full nuke job in the background. Returns job ID."""
    jm = request.app.state.job_manager
    user_id = session.get("slack_user_id", "")

    active = jm.get_active_job(user_id)
    if active:
        return JSONResponse(
            {"error": "A job is already running", "job_id": active["id"]},
            status_code=409,
        )

    job_id = jm.create_job(
        user_id=user_id,
        job_type="nuke",
        token=session["slack_token"],
    )
    start_cleanup_job(jm, job_id)

    return {"job_id": job_id}


@main_router.get("/api/job/{job_id}")
def api_job_status(job_id: str, request: Request, session: dict = Depends(require_auth)):
    """Get current job status."""
    jm = request.app.state.job_manager
    job = jm.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return job


@main_router.get("/api/job/{job_id}/stream")
def api_job_stream(job_id: str, request: Request, session: dict = Depends(require_auth)):
    """SSE stream of job progress."""
    jm = request.app.state.job_manager

    job = jm.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    return StreamingResponse(
        jm.stream_progress(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
