"""Pydantic schemas（表单校验用）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import SCOPE_PUBLIC


class NewSkillSubmission(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    version: str = Field(..., min_length=3, max_length=40)
    summary: str = Field(..., min_length=4, max_length=400)
    detail: str = Field(..., min_length=10, max_length=4000)
    category: str = Field(..., min_length=1, max_length=40)
    tags: str = ""  # 逗号分隔字符串
    scope: Literal["public", "department"] = SCOPE_PUBLIC
    feature_badge: bool = False
    publish_now: bool = False  # 演示场景：发布者能直接上架（跳过审核）


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = None
    feature_badge: bool = False
