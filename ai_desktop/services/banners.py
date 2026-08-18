"""首页轮播自定义幻灯片的读取与 CRUD 服务。

- get_active_banner_slides：前台展示用（启用中 + 在有效期内）。
- list_banner_slides：后台管理用（全部，按排序）。
- create / delete / toggle：后台写操作。
链接字段仅允许 http/https，避免 javascript: 等危险值。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import BannerSlide

_ACCENTS = ("orange", "green", "blue", "purple")


def _clean_link(link: str) -> str:
    link = (link or "").strip()
    if link.startswith(("http://", "https://")):
        return link
    return ""


def _parse_dt(value: str | None) -> datetime | None:
    """把 datetime-local 的 "YYYY-MM-DDTHH:MM" 解析为 datetime（naive, UTC）。

    空或格式错误返回 None。
    """
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _within_validity(slide: BannerSlide, now: datetime) -> bool:
    """判断某条幻灯片在给定时刻是否处于有效期内。"""
    if slide.start_at is not None and now < slide.start_at:
        return False
    if slide.end_at is not None and now > slide.end_at:
        return False
    return True


def get_active_banner_slides(db: Session) -> list[BannerSlide]:
    """前台轮播用：只取启用中且在有效期内的，按 sort_order 与创建时间倒序。"""
    now = datetime.utcnow()
    slides = (
        db.query(BannerSlide)
        .filter(BannerSlide.is_active.is_(True))
        .order_by(BannerSlide.sort_order, BannerSlide.created_at.desc())
        .all()
    )
    return [s for s in slides if _within_validity(s, now)]


def list_banner_slides(db: Session) -> list[BannerSlide]:
    """后台管理用：全部幻灯片，按 sort_order 与创建时间倒序。"""
    return (
        db.query(BannerSlide)
        .order_by(BannerSlide.sort_order, BannerSlide.created_at.desc())
        .all()
    )


def create_banner_slide(
    db: Session,
    *,
    title: str,
    content: str,
    link: str = "",
    link_text: str = "",
    accent: str = "orange",
    is_active: bool = True,
    sort_order: int = 0,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> BannerSlide:
    slide = BannerSlide(
        title=(title or "").strip(),
        content=(content or "").strip(),
        link=_clean_link(link),
        link_text=(link_text or "").strip(),
        accent=accent if accent in _ACCENTS else "orange",
        is_active=bool(is_active),
        sort_order=int(sort_order or 0),
        start_at=start_at,
        end_at=end_at,
    )
    db.add(slide)
    db.commit()
    db.refresh(slide)
    return slide


def delete_banner_slide(db: Session, slide_id: int) -> bool:
    slide = db.get(BannerSlide, slide_id)
    if not slide:
        return False
    db.delete(slide)
    db.commit()
    return True


def toggle_banner_slide(db: Session, slide_id: int) -> BannerSlide | None:
    slide = db.get(BannerSlide, slide_id)
    if not slide:
        return None
    slide.is_active = not slide.is_active
    db.commit()
    db.refresh(slide)
    return slide
