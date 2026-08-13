"""页面路由（HTML 渲染）。"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import ROLE_SKILLS_ADMIN, CurrentUser
from ..models import (
    KEY_PENDING,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    ApiKey,
    Category,
    Feedback,
    Skill,
    SkillVersion,
    TodoItem,
)

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _common_ctx(db: Session, request: Request) -> dict:
    """所有页面共享的模板上下文。"""
    user: CurrentUser = request.state.current_user
    pending_skills = db.query(SkillVersion).filter(SkillVersion.status == STATUS_PENDING).count()
    pending_keys = db.query(ApiKey).filter(ApiKey.status == KEY_PENDING).count()
    unread_feedback = db.query(Feedback).filter(Feedback.is_read.is_(False)).count()
    return {
        "current_user": user,
        "pending_reviews_count": pending_skills,
        "pending_key_count": pending_keys,
        "total_feedback": unread_feedback,
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    """首页：个人工作看板（Todo 待办）。"""
    ctx = _common_ctx(db, request)
    user: CurrentUser = request.state.current_user
    items = (
        db.query(TodoItem)
        .filter(TodoItem.user_id == user.id)
        .order_by(
            TodoItem.done.asc(),
            func.coalesce(TodoItem.completed_at, TodoItem.created_at).desc(),
        )
        .all()
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **ctx,
            "page": "home",
            "todos": items,
            "todo_counts": {
                "total": len(items),
                "done": sum(1 for i in items if i.done),
                "pending": sum(1 for i in items if not i.done),
            },
        },
    )


@router.get("/discover", response_class=HTMLResponse)
def discover(request: Request, db: Session = Depends(get_db)):
    """发现页（原首页）。"""
    ctx = _common_ctx(db, request)
    skills = db.query(Skill).order_by(Skill.downloads.desc()).all()
    published_skills = [s for s in skills if s.published_version]
    total_downloads = sum(s.downloads for s in published_skills)
    team_counter = Counter(s.owner_team for s in published_skills)
    categories = [c.name for c in db.query(Category).order_by(Category.sort).all()]

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            **ctx,
            "page": "discover",
            "skills": published_skills,
            "stats": {
                "published": len(published_skills),
                "downloads": total_downloads,
                "teams": len(team_counter),
            },
            "categories": categories,
        },
    )


@router.get("/my-uploads", response_class=HTMLResponse)
def my_uploads(request: Request, db: Session = Depends(get_db)):
    ctx = _common_ctx(db, request)
    user: CurrentUser = request.state.current_user
    versions = (
        db.query(SkillVersion)
        .filter(SkillVersion.submitted_by == user.name)
        .order_by(SkillVersion.submitted_at.desc())
        .all()
    )

    counts = {
        "all": len(versions),
        "pending": sum(1 for v in versions if v.status == STATUS_PENDING),
        "draft": sum(1 for v in versions if v.status == "draft"),
        "approved": sum(1 for v in versions if v.status == STATUS_PUBLISHED),
    }

    # 按 Skill 分组：卡片以「技能」为单位，点击卡片进入查看该技能的版本历史。
    groups_map: dict[int, list[SkillVersion]] = {}
    for v in versions:
        groups_map.setdefault(v.skill_id, []).append(v)

    groups: list[dict] = []
    for skill_id, vs in groups_map.items():
        skill = vs[0].skill
        # 版本历史按创建时间倒序（最新版在最前）
        sorted_vs = sorted(
            vs, key=lambda x: (x.created_at or x.submitted_at), reverse=True
        )
        published = [v for v in vs if v.status == STATUS_PUBLISHED]
        # 最新已发布版本 id（用于限定只有最新版本可「更新迭代」）
        latest_published_id = max((v.id for v in published), default=None)
        # 卡片主版本：优先最新已发布版本，否则取创建时间最新的版本
        primary = (
            next(v for v in sorted_vs if v.status == STATUS_PUBLISHED)
            if published
            else sorted_vs[0]
        )
        groups.append(
            {
                "skill": skill,
                "versions": sorted_vs,
                "primary": primary,
                "latest_published_id": latest_published_id,
                "version_count": len(vs),
                "statuses": sorted({v.status for v in vs}),
                "has_published": bool(published),
            }
        )

    # 排序：已发布的技能优先置顶，其次按主版本提交时间倒序
    groups.sort(
        key=lambda g: (not g["has_published"], g["primary"].submitted_at),
        reverse=True,
    )

    return templates.TemplateResponse(
        request,
        "my_uploads.html",
        {
            **ctx,
            "page": "my_uploads",
            "counts": counts,
            "groups": groups,
        },
    )


@router.get("/reviews", response_class=HTMLResponse)
def reviews_redirect(request: Request):
    """旧 /reviews 路由重定向到管理后台子页面。"""
    user: CurrentUser = request.state.current_user
    if user.has_role(ROLE_SKILLS_ADMIN):
        return RedirectResponse(url="/admin/skill-reviews", status_code=302)
    raise HTTPException(403, "无权限访问 Skills 审核管理")
