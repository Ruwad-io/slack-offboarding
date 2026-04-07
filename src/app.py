"""
Slack OffBoarding — FastAPI application factory.
"""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from src.config import Config
from src.services.job_manager import JobManager


def create_app() -> FastAPI:
    config = Config()

    if config.SENTRY_DSN:
        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.job_manager = JobManager(config.REDIS_URL)
        app.state.config = config
        yield

    app = FastAPI(title="OffBoarding", lifespan=lifespan)

    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)

    app.mount("/static", StaticFiles(directory="static"), name="static")

    from src.routes.auth import auth_router
    from src.routes.main import main_router, AuthRedirect

    app.include_router(auth_router)
    app.include_router(main_router)

    @app.exception_handler(AuthRedirect)
    async def auth_redirect_handler(request: Request, exc: AuthRedirect):
        return RedirectResponse(url="/", status_code=302)

    return app
