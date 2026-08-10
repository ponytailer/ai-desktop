"""认证路由：登录页面 + 登录/登出 API。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..deps import (
    TEST_ACCOUNTS,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    create_session_token,
    verify_session_token,
)

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """登录页面。"""
    # 如果已登录，直接跳转首页
    cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    user = verify_session_token(cookie)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"page": "login"},
    )


@router.post("/api/auth/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    remember: str = Form(""),
):
    """登录验证，设置会话 cookie。"""
    username = username.strip()
    password = password.strip()

    account = TEST_ACCOUNTS.get(username)
    if not account or account[0] != password:
        return Response(
            content='{"detail": "用户名或密码错误"}',
            status_code=401,
            media_type="application/json",
        )

    user = account[1]
    max_age = SESSION_MAX_AGE if remember == "on" else 0  # 勾选 30 天，不勾选为 session cookie
    token = create_session_token(user.id, SESSION_MAX_AGE)

    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age if max_age > 0 else None,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/api/auth/logout")
def logout():
    """退出登录，清除 cookie。"""
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp
