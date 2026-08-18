"""数据库初始化与 Session 管理。"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ai_desktop/data/skillhub.db
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

    # 轻量迁移：为已存在的表补齐新增列（SQLite 不擅长 ALTER，逐个判断）
    _migrate_columns()

    from .seed import seed_api_usage_if_empty, seed_if_empty

    seed_if_empty()
    seed_api_usage_if_empty()


def _migrate_columns() -> None:
    """给现有表补加在 ORM 中新增、但真实库里尚不存在的列。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        # api_keys: consumer_id / consumer_name
        if "api_keys" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("api_keys")}
            for col, ddl in (
                ("consumer_id", "VARCHAR(80)"),
                ("consumer_name", "VARCHAR(120)"),
                ("quota_rule_id", "VARCHAR(80)"),
                ("quota_rule_name", "VARCHAR(120)"),
            ):
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE api_keys ADD COLUMN {col} {ddl}"))

        # todo_items: due_at（预期完成时间）
        if "todo_items" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("todo_items")}
            if "due_at" not in existing:
                conn.execute(text("ALTER TABLE todo_items ADD COLUMN due_at DATETIME"))

        # banner_slide: start_at / end_at（有效期）
        if "banner_slide" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("banner_slide")}
            for col in ("start_at", "end_at"):
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE banner_slide ADD COLUMN {col} DATETIME"))

