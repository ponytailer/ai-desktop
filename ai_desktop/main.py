"""FastAPI 入口文件。

启动：
    .venv/bin/python -m uvicorn ai_desktop.main:app --reload --port 8001
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .deps import (
    PUBLIC_PATHS,
    PUBLIC_PREFIXES,
    SESSION_COOKIE_NAME,
    verify_session_token,
)
from .routers import admin, auth, feedback, keys, pages, reviews, submissions

APP_ROOT = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="SkillHub", version="0.1.0")

    # 静态资源
    app.mount(
        "/static",
        StaticFiles(directory=str(APP_ROOT / "static")),
        name="static",
    )

    # ---------- 认证中间件 ----------
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # 公开路径直接放行
        path = request.url.path
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # 验证会话 cookie
        cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
        user = verify_session_token(cookie)

        if user:
            request.state.current_user = user
        else:
            # 未登录 → 重定向到登录页
            if path.startswith("/api/"):
                # API 请求返回 401 JSON
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "未登录"}, status_code=401)
            return RedirectResponse(url="/login", status_code=302)

        response = await call_next(request)
        return response

    # 路由
    app.include_router(auth.router)
    app.include_router(pages.router)
    app.include_router(submissions.router)
    app.include_router(reviews.router)
    app.include_router(keys.router)
    app.include_router(admin.router)
    app.include_router(feedback.router)

    @app.on_event("startup")
    def _on_start() -> None:  # noqa: D401
        init_db()

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
