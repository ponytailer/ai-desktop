"""数据库初始化与 Session 管理。"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

# skill_hub/data/skillhub.db
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "skillhub.db"

ENGINE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(
    ENGINE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """SQLAlchemy 2.x 声明基类。"""

    pass


def get_db() -> Session:
    """FastAPI 依赖：每次请求开一个 Session，用完即关。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表 + 种子数据。幂等。"""
    # 导入 models 触发 mapper 注册
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from .seed import seed_if_empty

    seed_if_empty()
