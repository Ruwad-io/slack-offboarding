"""
OAuth routes for Slack authentication.
"""

from flask import Blueprint, redirect, request, session, url_for
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import Config

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
config = Config()


@auth_bp.route("/login")
def login():
    """Redirect user to Slack OAuth."""
    return redirect(config.slack_oauth_url)


@auth_bp.route("/callback")
def callback():
    """Handle OAuth callback from Slack."""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return redirect(url_for("main.index", error=error))

    if not code:
        return redirect(url_for("main.index", error="no_code"))

    try:
        client = WebClient()
        resp = client.oauth_v2_access(
            client_id=config.SLACK_CLIENT_ID,
            client_secret=config.SLACK_CLIENT_SECRET,
            code=code,
            redirect_uri=f"{config.APP_URL}/auth/callback",
        )

        # Store user token in session
        authed_user = resp.get("authed_user", {})
        session["slack_token"] = authed_user.get("access_token")
        session["slack_user_id"] = authed_user.get("id")

        # Get user info
        user_client = WebClient(token=session["slack_token"])
        identity = user_client.auth_test()
        session["slack_user_name"] = identity.get("user", "")
        session["slack_team"] = identity.get("team", "")

        return redirect(url_for("main.dashboard"))

    except SlackApiError as e:
        return redirect(url_for("main.index", error=str(e)))


@auth_bp.route("/logout")
def logout():
    """Clear session and log out."""
    session.clear()
    return redirect(url_for("main.index"))
