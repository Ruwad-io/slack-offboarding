import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID", "")
    SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET", "")
    SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    APP_URL = os.environ.get("APP_URL", "http://localhost:5000")

    SLACK_USER_SCOPES = [
        "channels:history",
        "channels:read",
        "chat:write",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "mpim:history",
        "mpim:read",
        "users:read",
        "users.profile:read",
    ]

    @property
    def slack_oauth_url(self):
        scopes = ",".join(self.SLACK_USER_SCOPES)
        redirect = f"{self.APP_URL}/auth/callback"
        return (
            f"https://slack.com/oauth/v2/authorize"
            f"?client_id={self.SLACK_CLIENT_ID}"
            f"&user_scope={scopes}"
            f"&redirect_uri={redirect}"
        )
