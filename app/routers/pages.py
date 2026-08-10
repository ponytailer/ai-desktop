"""页面路由（HTML 渲染）。"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Skill, SkillVersion, Category, ApiKey, STATUS_PUBLISHED, STATUS_PENDING, KEY_PENDING
from ..deps import ROLE_SKILLS_ADMIN, ROLE_SUPER_ADMIN, ROLE_KEY_ADMIN, CurrentUser

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _common_ctx(db: Session, request: Request) -> dict:
    """所有页面共享的模板上下文。"""
    user: CurrentUser = request.state.current_user
    pending_skills = db.query(SkillVersion).filter(SkillVersion.status == STATUS_PENDING).count()
    pending_keys = db.query(ApiKey).filter(ApiKey.status == KEY_PENDING).count()
    return {
        "current_user": user,
        "pending_reviews_count": pending_skills,
        "pending_key_count": pending_keys,
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
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

    return templates.TemplateResponse(
        request,
        "my_uploads.html",
        {
            **ctx,
            "page": "my_uploads",
            "versions": versions,
            "counts": counts,
        },
    )


@router.get("/reviews", response_class=HTMLResponse)
def reviews_redirect(request: Request):
    """旧 /reviews 路由重定向到管理后台子页面。"""
    user: CurrentUser = request.state.current_user
    if user.has_role(ROLE_SKILLS_ADMIN):
        return RedirectResponse(url="/admin/skill-reviews", status_code=302)
    raise HTTPException(403, "无权限访问 Skills 审核管理")
