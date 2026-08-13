"""Skills 提交 / 上传 / 下载 API。"""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, \
    UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import CurrentUser
from ..models import (
    SCOPE_PUBLIC,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    Skill,
    SkillVersion
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


def _read_attachment_size(p: Path | None) -> int:
    if not p:
        return 0
    try:
        return p.stat().st_size
    except FileNotFoundError:
        return 0


def _resolve_zip_path(version: SkillVersion) -> Path | None:
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


def _version_key(v: str) -> tuple[int, int, int]:
    """将版本号解析为可比较的 (major, minor, patch) 元组，便于语义排序。"""
    parts = re.split(r"[.\-]", str(v or "0.0.0"))
    nums: list[int] = []
    for p in parts[:3]:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def _latest_version_string(db: Session, skill_id: int) -> str:
    """返回该 skill 所有版本中语义最大的版本号（无版本则返回 '0.0.0'）。"""
    rows = db.query(SkillVersion.version).filter(
        SkillVersion.skill_id == skill_id).all()
    if not rows:
        return "0.0.0"
    return max((r[0] for r in rows), key=_version_key)


def _suggest_next_version(db: Session, skill_id: int,
    current_version: str) -> str:
    """被拒绝 / 草稿重新提交时建议的版本号：

    - 若该版本已 >= 全量最新版本，保持原版本号（没有更新的版本迭代上去）
    - 否则（已有更新的版本发布）自动 patch +1，避免与已发布版本冲突
    """
    latest = _latest_version_string(db, skill_id)
    if _version_key(current_version) >= _version_key(latest):
        return current_version
    return _bump_version(latest)


def _write_placeholder_zip(zip_path: Path, skill_name: str, version: str,
    summary: str) -> None:
    import io
    import zipfile
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
        # 新创建默认进入「待审核」，不再先落草稿（草稿仅由撤回产生）
        status=STATUS_PUBLISHED if publish_now == "true" else STATUS_PENDING,
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


@router.post("/api/skills/{version_id}/discard")
def discard_version(version_id: int, db: Session = Depends(get_db)):
    """废弃版本：彻底删除该版本（含附件文件）。

    - 仅「草稿」或「被拒绝」状态可废弃（已提交/已发布版本不允许）
    - 若该技能在删除此版本后已无任何版本，则一并删除孤儿 Skill 主记录
    """
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    if v.status not in (STATUS_DRAFT, STATUS_REJECTED):
        raise HTTPException(400, "只有草稿或被拒绝的版本可以废弃")
    skill = v.skill

    # 清理附件 zip 文件
    zip_path = _resolve_zip_path(v)
    if zip_path and zip_path.exists():
        try:
            zip_path.unlink()
        except OSError:
            pass

    # 删除版本行；若该技能已无任何版本，连带删除孤儿主记录
    db.delete(v)
    db.flush()
    remaining = (
        db.query(SkillVersion)
        .filter(SkillVersion.skill_id == skill.id)
        .count()
    )
    if remaining == 0:
        db.delete(skill)
    db.commit()
    return {"ok": True}


@router.post("/api/skills/{version_id}/edit")
async def edit_version(
    version_id: int,
    category: str = Form(""),
    tags: str = Form(""),
    scope: str = Form(SCOPE_PUBLIC),
    changelog: str = Form(""),
    detail: str = Form(""),
    version: str = Form(""),
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

    # 版本号重新检查：重新编辑提交时，若已有更新的版本迭代上去，
    # 必须顺延，避免与已发布版本冲突。
    if version and version.strip():
        version = version.strip()
        if len(version) < 3:
            raise HTTPException(400, "版本号不合法")
        others = (
            db.query(SkillVersion)
            .filter(SkillVersion.skill_id == v.skill_id,
                    SkillVersion.id != v.id)
            .all()
        )
        others_max_key = max((_version_key(o.version) for o in others),
                             default=None)
        if others_max_key is not None and _version_key(
            version) <= others_max_key:
            suggested = _suggest_next_version(db, v.skill_id, version)
            raise HTTPException(
                400,
                f"版本号 {version} 低于或等于已有版本，请使用 {suggested}",
            )
        v.version = version

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
    }


@router.get("/api/skills/{version_id}/detail")
def skill_detail(version_id: int, db: Session = Depends(get_db)):
    """Skill 详情：元信息 + zip 内 SKILL.md 原文（前端用 marked 渲染）。"""
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    s = v.skill

    # 从附件 zip 内读取 SKILL.md（不区分大小写）
    skill_md = ""
    has_md = False
    zip_path = _resolve_zip_path(v)
    if zip_path:
        try:
            import zipfile
            with zipfile.ZipFile(zip_path) as zf:
                md_name = next(
                    (n for n in zf.namelist() if
                     n.upper().endswith("SKILL.MD")), None
                )
                if md_name:
                    skill_md = zf.read(md_name).decode("utf-8", "replace")
                    has_md = True
        except (zipfile.BadZipFile, OSError):
            skill_md = ""
            has_md = False

    return {
        "id": v.id,
        "name": s.name,
        "icon": s.icon,
        "accent_color": s.accent_color,
        "short_description": s.short_description,
        "category": s.category,
        "owner_name": s.owner_name,
        "owner_team": s.owner_team,
        "downloads": s.downloads,
        "likes": s.likes,
        "version": v.version,
        "tags": v.tags_list,
        "summary": v.summary,
        "detail": v.detail,
        "changelog": v.changelog,
        "status_label": v.status_label,
        "scope_label": v.scope_label,
        "submitted_at": v.submitted_at.strftime(
            "%Y-%m-%d") if v.submitted_at else "",
        "skill_md": skill_md,
        "has_md": has_md,
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
    # 仅「最新已发布版本」可迭代：历史版本只能查看记录，不能再次迭代。
    # 以「已发布版本中 id 最大者」作为最新（自增 id 单调递增，判定确定无歧义）。
    latest = (
        db.query(SkillVersion)
        .filter(SkillVersion.skill_id == src.skill_id,
                SkillVersion.status == STATUS_PUBLISHED)
        .order_by(SkillVersion.id.desc())
        .first()
    )
    if latest is None or latest.id != src.id:
        raise HTTPException(400, "只有最新版本可以更新迭代，历史版本仅可查看")

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
