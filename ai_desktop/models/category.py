"""首页筛选用分类集合。"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Category(Base):
    """首页筛选下拉「全部分类」用的二级分类集合，名字自取即可。"""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
