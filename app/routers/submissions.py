"""Skills 提交 / 上传 / 下载 API。"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, \
    Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import CurrentUser
from ..models import (
    Skill,
    SkillVersion,
    SCOPE_PUBLIC,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_PUBLISHED,
)

router = APIRouter()

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"
ATTACHMENT_ROOT = DATA_ROOT / "attachments"

# --------- 工具 ---------

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_segment(s: str, fallback: str = "x") -> str:
    cleaned = _SAFE_NAME.sub("-", s.strip())
    cleaned = cleaned.strip("-") or fallback
    return cleaned[:80]


def _split_tags(text: str) -> list[str]:
    if not text:
        return []
    # 支持中英文逗号、分号、顿号分隔
    parts = re.split(r"[,，;；、]+", text)
    return [p.strip() for p in parts if p.strip()][:8]


def _read_attachment_size(p: Optional[Path]) -> int:
    if not p:
        return 0
    try:
        return p.stat().st_size
    except FileNotFoundError:
        return 0


def _resolve_zip_path(version: SkillVersion) -> Optional[Path]:
    if not version.attachment_path:
        return None
    p = (DATA_ROOT / version.attachment_path).resolve()
    if not p.exists():
        return None
    return p


def _bump_version(current: str) -> str:
    """版本号 patch +1：1.0.0 → 1.0.1；1.2 → 1.2.1；非法 → 1.0.0。"""
    parts = re.split(r"[.\-]", str(current or "1.0.0"))
    nums: list[int] = []
    for p in parts[:3]:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    nums[2] += 1
    return ".".join(str(n) for n in nums)


def _write_placeholder_zip(zip_path: Path, skill_name: str, version: str,
    summary: str) -> None:
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.md",
            f"# {skill_name}\n\n版本：{version}\n\n该包由 SkillHub 演示环境自动生成。\n",
        )
        zf.writestr(
            "SKILL.md",
            f"---\nname: {skill_name}\nversion: {version}\n---\n\n# {skill_name}\n\n{summary}\n",
        )
    zip_path.write_bytes(buf.getvalue())


# --------- API ---------

@router.get("/api/skills/check-name")
def check_name(name: str, db: Session = Depends(get_db)):
    """新建 Skill 时名称查重。"""
    name = (name or "").strip()
    if len(name) < 2:
        return {"exists": False}
    hit = db.query(Skill).filter(Skill.name == name).one_or_none()
    return {"exists": hit is not None}


@router.post("/api/skills/upload")
async def upload_skill(
    request: Request,
    name: str = Form(...),
    version: str = Form(...),
    summary: str = Form(...),
    detail: str = Form(...),
    category: str = Form(...),
    tags: str = Form(""),
    scope: str = Form(SCOPE_PUBLIC),
    publish_now: str = Form("false"),  # "true" 时直接发布
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user: CurrentUser = request.state.current_user
    name = name.strip()
    version = version.strip()
    summary = summary.strip()
    detail = detail.strip()
    if len(name) < 2 or len(version) < 3:
        raise HTTPException(400, "名称 / 版本号不合法")

    skill = db.query(Skill).filter(Skill.name == name).one_or_none()
    if skill is None:
        skill = Skill(
            name=name,
            icon="📦",
            accent_color="#5B6CFF",
            short_description=summary,
            category=category,
            owner_name=user.name,
            owner_team="我的团队",
            downloads=0,
            likes=0,
            is_featured=False,
        )
        db.add(skill)
        db.flush()

    # 已有同版本号？
    exists = (
        db.query(SkillVersion)
        .filter(SkillVersion.skill_id == skill.id,
                SkillVersion.version == version)
        .one_or_none()
    )
    if exists:
        raise HTTPException(409, f"{skill.name} {version} 已存在")

    new_version = SkillVersion(
        skill_id=skill.id,
        version=version,
        summary=summary,
        detail=detail,
        scope=scope,
        status=STATUS_PUBLISHED if publish_now == "true" else STATUS_DRAFT,
        submitted_by=user.name,
        submitted_at=datetime.utcnow(),
        changelog="",
    )
    new_version.set_tags(_split_tags(tags))
    db.add(new_version)
    db.flush()

    # 写附件 zip
    skill_folder = ATTACHMENT_ROOT / str(skill.id)
    skill_folder.mkdir(parents=True, exist_ok=True)
    zip_path = skill_folder / f"{new_version.id}.zip"

    if file is not None and (file.filename or "").lower().endswith(".zip"):
        # 真有上传
        with zip_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    else:
        # 用一份占位 zip，否则下载按钮会 404
        _write_placeholder_zip(zip_path, skill.name, version, summary)

    new_version.attachment_path = str(zip_path.relative_to(DATA_ROOT))
    new_version.attachment_size = zip_path.stat().st_size

    db.commit()

    return JSONResponse(
        {
            "ok": True,
            "skill_id": skill.id,
            "version_id": new_version.id,
            "status": new_version.status,
        }
    )


@router.post("/api/skills/{version_id}/submit")
def submit_version(version_id: int, db: Session = Depends(get_db)):
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    if v.status not in (STATUS_DRAFT, "rejected"):
        raise HTTPException(400, "当前状态不允许提交")
    v.status = STATUS_PENDING
    v.submitted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": v.status}


@router.post("/api/skills/{version_id}/withdraw")
def withdraw_version(version_id: int, db: Session = Depends(get_db)):
    """撤回待审核的提交，状态回到草稿。"""
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    if v.status != STATUS_PENDING:
        raise HTTPException(400, "当前状态不允许撤回（仅待审核版本可撤回）")
    v.status = STATUS_DRAFT
    v.submitted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": v.status}


@router.post("/api/skills/{version_id}/edit")
async def edit_version(
    version_id: int,
    category: str = Form(""),
    tags: str = Form(""),
    scope: str = Form(SCOPE_PUBLIC),
    changelog: str = Form(""),
    detail: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    if category:
        v.skill.category = category
    if detail:
        v.detail = detail
    v.set_tags(_split_tags(tags))
    v.scope = scope
    v.changelog = changelog

    if file is not None and (file.filename or "").lower().endswith(".zip"):
        skill_folder = ATTACHMENT_ROOT / str(v.skill_id)
        skill_folder.mkdir(parents=True, exist_ok=True)
        zip_path = skill_folder / f"{v.id}.zip"
        with zip_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        v.attachment_path = str(zip_path.relative_to(DATA_ROOT))
        v.attachment_size = zip_path.stat().st_size

    # 编辑提交后回到待审核
    v.status = STATUS_PENDING
    v.submitted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": v.status}


@router.get("/api/skills/{version_id}/download")
def download_attachment(version_id: int, db: Session = Depends(get_db)):
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    if v.status not in (STATUS_PUBLISHED, "superseded"):
        raise HTTPException(403, "当前版本未发布，无法下载")
    p = _resolve_zip_path(v)
    if not p:
        raise HTTPException(404, "附件不存在")
    # 真实计数：每次下载 +1
    v.skill.downloads = (v.skill.downloads or 0) + 1
    db.commit()
    return FileResponse(
        p,
        media_type="application/zip",
        filename=f"{_sanitize_segment(v.skill.name)}-{_sanitize_segment(v.version)}.zip",
    )


@router.get("/api/skills/{version_id}/card")
def card_payload(version_id: int, request: Request,
    db: Session = Depends(get_db)):
    """发现页「安装」按钮会拉取这个 JSON 用来填安装弹窗。"""
    v = db.get(SkillVersion, version_id)
    if not v or v.status != STATUS_PUBLISHED:
        raise HTTPException(404)
    return {
        "skill_id": v.skill_id,
        "name": v.skill.name,
        "version": v.version,
        "summary": v.summary,
        "icon": v.skill.icon,
        "accent_color": v.skill.accent_color,
        "download_url": f"/api/skills/{v.id}/download",
        "install_command": f"npx @company/skillhub add {request.url.scheme}://{request.url.netloc}/api/skills/{v.id}/download",
    }


@router.post("/api/skills/{skill_id}/toggle-like")
def toggle_like(skill_id: int, action: str = Form(...),
    db: Session = Depends(get_db)):
    """点赞 / 取消点赞。前端用 localStorage 跟踪当前用户已点赞的 skill。"""
    skill = db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if action == "like":
        skill.likes = (skill.likes or 0) + 1
    else:
        skill.likes = max(0, (skill.likes or 0) - 1)
    db.commit()
    return {"ok": True, "likes": skill.likes}


@router.post("/api/skills/{version_id}/iterate")
async def iterate_version(
    version_id: int,
    request: Request,
    name: str = Form(...),
    version: str = Form(...),
    summary: str = Form(...),
    detail: str = Form(...),
    category: str = Form(""),
    tags: str = Form(""),
    scope: str = Form(SCOPE_PUBLIC),
    changelog: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """基于已发布版本创建新版本（更新迭代）。

    - 名称必须与源 skill 一致（前端禁用，此处校验）
    - 版本号自动迭代或用户手填，需与已有版本不冲突
    - 新版本状态 = pending，提交后进入审核
    """
    user: CurrentUser = request.state.current_user
    src = db.get(SkillVersion, version_id)
    if not src:
        raise HTTPException(404, "源版本不存在")
    if src.status != STATUS_PUBLISHED:
        raise HTTPException(400, "只有已发布版本可以迭代")

    name = name.strip()
    version = version.strip()
    summary = summary.strip()
    detail = detail.strip()
    if name != src.skill.name:
        raise HTTPException(400, "迭代时 Skill 名称不可修改")
    if not changelog.strip():
        raise HTTPException(400, "请填写版本说明")
    if len(version) < 3:
        raise HTTPException(400, "版本号不合法")

    # 版本号查重
    dup = (
        db.query(SkillVersion)
        .filter(SkillVersion.skill_id == src.skill_id,
                SkillVersion.version == version)
        .first()
    )
    if dup:
        raise HTTPException(409,
                            f"版本号 {version} 已存在，请使用 {_bump_version(version)}")

    # 同步分类到 skill 主表
    if category:
        src.skill.category = category
    src.skill.short_description = summary

    new_v = SkillVersion(
        skill_id=src.skill_id,
        version=version,
        summary=summary,
        detail=detail,
        scope=scope,
        status=STATUS_PENDING,
        submitted_by=user.name,
        submitted_at=datetime.utcnow(),
        changelog=changelog,
    )
    new_v.set_tags(_split_tags(tags))
    db.add(new_v)
    db.flush()

    # 附件：有上传则用上传，否则沿用源版本 zip（复制一份）
    skill_folder = ATTACHMENT_ROOT / str(src.skill_id)
    skill_folder.mkdir(parents=True, exist_ok=True)
    zip_path = skill_folder / f"{new_v.id}.zip"

    if file is not None and (file.filename or "").lower().endswith(".zip"):
        with zip_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    else:
        src_zip = _resolve_zip_path(src)
        if src_zip and src_zip.exists():
            shutil.copy2(src_zip, zip_path)
        else:
            _write_placeholder_zip(zip_path, src.skill.name, version, summary)

    new_v.attachment_path = str(zip_path.relative_to(DATA_ROOT))
    new_v.attachment_size = zip_path.stat().st_size

    db.commit()
    return JSONResponse(
        {
            "ok": True,
            "skill_id": src.skill_id,
            "version_id": new_v.id,
            "version": new_v.version,
            "status": new_v.status,
        }
    )
