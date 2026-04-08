"""
OAuth routes for Slack authentication.
"""

import logging

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import Config

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
config = Config()


@auth_router.get("/login")
def login():
    """Redirect user to Slack OAuth."""
    return RedirectResponse(url=config.slack_oauth_url, status_code=302)


@auth_router.get("/callback")
def callback(request: Request, code: str = None, error: str = None):
    """Handle OAuth callback from Slack."""
    if error:
        return RedirectResponse(url=f"/?error={error}", status_code=302)

    if not code:
        return RedirectResponse(url="/?error=no_code", status_code=302)

    try:
        client = WebClient()
        resp = client.oauth_v2_access(
            client_id=config.SLACK_CLIENT_ID,
            client_secret=config.SLACK_CLIENT_SECRET,
            code=code,
            redirect_uri=f"{config.APP_URL}/auth/callback",
        )

        authed_user = resp.get("authed_user", {})
        request.session["slack_token"] = authed_user.get("access_token")
        request.session["slack_user_id"] = authed_user.get("id")

        user_client = WebClient(token=request.session["slack_token"])
        identity = user_client.auth_test()
        request.session["slack_user_name"] = identity.get("user", "")
        request.session["slack_team"] = identity.get("team", "")

        return RedirectResponse(url="/dashboard", status_code=302)

    except SlackApiError as e:
        logger.error(f"OAuth callback failed: {e}")
        return RedirectResponse(url="/?error=auth_failed", status_code=302)


@auth_router.get("/logout")
def logout(request: Request):
    """Clear session and log out."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)
