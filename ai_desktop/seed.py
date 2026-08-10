"""启动种子数据。

幂等：只在表为空时插入。会在 data/attachments/<skill_id>/<version_id>.zip 写一些占位包，
仅用于「直接下载」按钮能拿到字节流。
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from .database import SessionLocal
from .deps import CURRENT_USER  # 当前登录用户，对应截图中的「管理员 48890023」
from .models import (
    CATEGORY_OPTIONS,
    SCOPE_DEPARTMENT,
    SCOPE_PUBLIC,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    Category,
    Skill,
    SkillVersion,
)

ATTACHMENT_DIR = Path(__file__).resolve().parent.parent / "data" / "attachments"


def _make_zip_bytes(skill_name: str, version: str) -> tuple[bytes, int]:
    """生成一个最小可下载的 zip。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        readme = (
            f"# {skill_name}\n\n版本：{version}\n\n由 SkillHub 演示用占位包构成。\n"
        )
        zf.writestr("README.md", readme)
        zf.writestr(
            "SKILL.md",
            f"---\nname: {skill_name}\nversion: {version}\n---\n\n# {skill_name}\n",
        )
    return buf.getvalue(), buf.tell()


def _write_attachment(skill_id: int, version_id: int, skill_name: str, version: str) -> Path:
    ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    folder = ATTACHMENT_DIR / str(skill_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{version_id}.zip"
    data, size = _make_zip_bytes(skill_name, version)
    path.write_bytes(data)
    return path


# --------- Skill 详情文档（用于弹窗显示，非必要）---------
DETAIL_REVIEW = """**输入**：当前变更 diff、相关文件路径、可选的自定义评审清单。
**流程**：先调用 `git diff` 抓取差异，按风险面归类；再由 LLM 给出结构化评论，最后生成可执行的改进建议。
**输出**：Markdown 评审报告（含优点 / 风险 / 建议）、可直接执行的 patch。
**适用边界**：单仓 1 万行以内的差异；不适合二进制或巨型重构。"""

DETAIL_SQL = """**输入**：自然语言业务问题、可选的库表 schema。
**流程**：问题归一化 → 枚举候选 SQL → 静态分析（命中索引、行数估算）→ 用样本数据回放 → 生成结论与可视化建议。
**输出**：可执行的 SQL（含 EXPLAIN）、分析摘要、折线/柱状图草稿。
**适用边界**：OLAP 场景、查询耗时 < 30s；不适合 OLTP 高频写入路径。"""

DETAIL_MEETING = """**输入**：会议录音或纪要文本。
**流程**：转写 → 议题拆分 → 决策与待办抽取 → 输出结构化纪要。
**输出**：议题清单、结论、责任人 + 截止时间。
**适用边界**：中文 / 英文混合，< 90 分钟的会议。"""

DETAIL_CAMPAIGN = """**输入**：产品定位、目标人群画像、投放渠道。
**流程**：卖点提炼 → 文案风格选择（小红书 / 公众号 / 邮件）→ 多版本生成 → A/B 建议。
**输出**：3-5 版文案、投放时间建议、效果预估。"""

DETAIL_SIGNAL = """**输入**：客服会话、工单、问卷原始文本。
**流程**：情感识别 → 主题聚类 → 紧急度打分 → 关联产品模块。
**输出**：客户声音看板、Top3 风险信号、行动建议。"""

DETAIL_SECURITY = """**输入**：依赖列表、仓库代码片段。
**流程**：CVE 库匹配 → 静态扫描 → 漏洞利用路径分析 → 修复建议。
**输出**：漏洞清单 + 修复 patch、风险等级、回归测试用例。"""

DETAIL_INCIDENT = """**输入**：故障描述、时间线、监控指标快照。
**流程**：5W1H 还原 → 根因假设 → 验证 → 输出复盘文档 + 改进项。
**输出**：故障复盘 Markdown、行动项跟踪表、客户致歉模板。"""

DETAIL_KNOWLEDGE = """**输入**：知识库索引、用户查询语句。
**流程**：多路召回 → 重排序 → 可信度标注 → 引用原文片段。
**输出**：问题答案、来源链接、置信度。"""


def seed_if_empty() -> None:
    """如果 skills 表为空则插入示例数据，否则跳过。"""
    db = SessionLocal()
    try:
        if db.query(Skill).count() > 0:
            return

        # ---------------- Categories ----------------
        for idx, name in enumerate(CATEGORY_OPTIONS):
            db.add(Category(name=name, sort=idx * 10))
        db.flush()

        # ---------------- 工具函数 ----------------
        def add_skill_version(
            skill: Skill,
            version: str,
            status: str,
            summary: str,
            detail: str,
            tags: list[str],
            scope: str = SCOPE_PUBLIC,
            featured: bool = False,
            submitted_by: str = "林远",
            days_ago: int = 6,
            decided: bool | None = None,
            note: str | None = None,
        ) -> SkillVersion:
            v = SkillVersion(
                skill_id=skill.id,
                version=version,
                summary=summary,
                detail=detail,
                scope=scope,
                status=status,
                submitted_by=submitted_by,
                submitted_at=datetime.utcnow() - timedelta(days=days_ago, hours=2),
                featured_badge=featured,
            )
            v.set_tags(tags)
            db.add(v)
            db.flush()
            if decided is True:
                v.decided_by = CURRENT_USER.name
                v.decided_at = datetime.utcnow() - timedelta(days=days_ago, hours=1)
            if note:
                v.decision_note = note
            # 写一个示例 zip
            data, size = _make_zip_bytes(skill.name, version)
            ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
            folder = ATTACHMENT_DIR / str(skill.id)
            folder.mkdir(parents=True, exist_ok=True)
            zip_path = folder / f"{v.id}.zip"
            zip_path.write_bytes(data)
            v.attachment_path = str(zip_path.relative_to(ATTACHMENT_DIR.parent))
            v.attachment_size = size
            return v

        def build_skill(
            name: str,
            icon: str,
            accent: str,
            short_desc: str,
            category: str,
            owner_name: str,
            owner_team: str,
            downloads: int,
            likes: int,
            featured: bool,
        ) -> Skill:
            s = Skill(
                name=name,
                icon=icon,
                accent_color=accent,
                short_description=short_desc,
                category=category,
                owner_name=owner_name,
                owner_team=owner_team,
                downloads=downloads,
                likes=likes,
                is_featured=featured,
            )
            db.add(s)
            db.flush()
            return s

        # ---------------- 已发布的 Skills（首页卡片） ----------------

        # Code Review Companion —— v2.4.1 已发布，由别人提交；v2.5.0 待审核（管理员）
        cr = build_skill(
            "Code Review Companion", "</>", "#5B6CFF",
            "自动检查变更风险，生成结构化评审意见与可执行建议。",
            "代码质量", "林远", "研发平台",
            downloads=1286, likes=86, featured=True,
        )
        add_skill_version(
            cr, "v2.4.1", STATUS_PUBLISHED,
            "自动检查变更风险，生成结构化评审意见与可执行建议。",
            DETAIL_REVIEW, ["代码评审", "Git", "质量"],
            featured=True, decided=True, days_ago=10, submitted_by="林远",
        )
        add_skill_version(
            cr, "v2.5.0", STATUS_PENDING,
            "新增单元测试定位建议；支持自定义评审清单。",
            DETAIL_REVIEW, ["代码评审", "Git", "质量"],
            submitted_by="林远", days_ago=1, decided=False,
        )

        # SQL Insight —— v1.8.0 已发布, v1.9.0 待审核（管理员）
        si = build_skill(
            "SQL Insight", "📈", "#3F66FF",
            "把自然语言业务问题转成可审阅的 SQL 与分析摘要。",
            "数据与分析", "周宁", "数据智能",
            downloads=963, likes=64, featured=True,
        )
        add_skill_version(
            si, "v1.8.0", STATUS_PUBLISHED,
            "把自然语言业务问题转成可审阅的 SQL 与分析摘要。",
            DETAIL_SQL, ["SQL", "数据分析", "指标"],
            featured=True, decided=True, days_ago=12, submitted_by="周宁",
        )
        add_skill_version(
            si, "v1.9.0", STATUS_PENDING,
            "新增漏斗分析模板和日期口径检查。",
            DETAIL_SQL, ["SQL", "数据分析", "指标"],
            submitted_by="周宁", days_ago=1, decided=False,
        )

        # Meeting Brief
        mb = build_skill(
            "Meeting Brief", "💬", "#0D9488",
            "从会议材料中整理议题、决策与待办事项。",
            "会议与协作", "陈晨", "总经办",
            downloads=742, likes=58, featured=True,
        )
        add_skill_version(
            mb, "v3.1.0", STATUS_PUBLISHED,
            "从会议材料中整理议题、决策与待办事项。",
            DETAIL_MEETING, ["会议", "摘要", "待办"],
            featured=True, decided=True, days_ago=15,
        )

        # Campaign Writer
        cw = build_skill(
            "Campaign Writer", "📣", "#F97316",
            "基于产品定位生成多渠道营销文案，并给出 A/B 测试建议。",
            "运营增长", "顾潇", "市场中心",
            downloads=531, likes=41, featured=False,
        )
        add_skill_version(
            cw, "v1.5.2", STATUS_PUBLISHED,
            "基于产品定位生成多渠道营销文案，并给出 A/B 测试建议。",
            DETAIL_CAMPAIGN, ["文案", "投放", "A/B"],
            featured=False, decided=True, days_ago=20,
        )

        # Customer Signal
        cs = build_skill(
            "Customer Signal", "🛎", "#7C3AED",
            "汇总客服与工单反馈，识别客户紧急信号与产品改进点。",
            "客服与支持", "苏蕊", "客户成功",
            downloads=489, likes=37, featured=False,
        )
        add_skill_version(
            cs, "v2.0.0", STATUS_PUBLISHED,
            "汇总客服与工单反馈，识别客户紧急信号与产品改进点。",
            DETAIL_SIGNAL, ["客户", "反馈", "聚类"],
            featured=False, decided=True, days_ago=18,
        )

        # Security Gate
        sg = build_skill(
            "Security Gate", "🛡", "#E11D48",
            "扫描依赖与代码中的已知漏洞并产出可执行的修复 patch。",
            "安全合规", "邓岩", "安全工程",
            downloads=317, likes=29, featured=False,
        )
        add_skill_version(
            sg, "v1.3.4", STATUS_PUBLISHED,
            "扫描依赖与代码中的已知漏洞并产出可执行的修复 patch。",
            DETAIL_SECURITY, ["漏洞", "依赖", "修复"],
            featured=False, decided=True, days_ago=22,
        )

        # Incident Update —— 仅 v0.9.0 待审核（首页卡片不出现）
        iu = build_skill(
            "Incident Update", "🚨", "#DC2626",
            "首个可用版本，包含管理层、客户与内部三类通报模板。",
            "研发工具", "赵可", "SRE",
            downloads=0, likes=0, featured=False,
        )
        add_skill_version(
            iu, "v0.9.0", STATUS_PENDING,
            "首个可用版本，包含管理层、客户与内部三类通报模板。",
            DETAIL_INCIDENT, ["故障", "复盘", "通报"],
            submitted_by="赵可", days_ago=2, decided=False,
        )

        # Knowledge Finder —— 全部由管理员 / 顾潇 上传（演示「我的上传」）
        kf = build_skill(
            "Knowledge Finder", "📚", "#0EA5E9",
            "改进部门知识检索并增加来源时效检查。",
            "业务运营", "顾潇", "知识中台",
            downloads=210, likes=15, featured=True,
        )
        # v0.8.1 已通过 公开 —— 截图里挂在「我的上传」
        add_skill_version(
            kf, "v0.8.1", STATUS_PUBLISHED,
            "改进引用去重，并增加过期内容提醒。",
            DETAIL_KNOWLEDGE, ["知识库", "检索", "问答"],
            scope=SCOPE_PUBLIC, featured=False,
            submitted_by=CURRENT_USER.name,  # 管理员
            days_ago=14, decided=True,
            note="检查通过，准予发布。",
        )
        # v0.8.2 已通过 部门内可见 精选
        add_skill_version(
            kf, "v0.8.2", STATUS_PUBLISHED,
            "增加部门权限范围并准备员工目录集成；草稿重做。",
            DETAIL_KNOWLEDGE, ["知识库", "检索", "问答"],
            scope=SCOPE_DEPARTMENT, featured=True,
            submitted_by=CURRENT_USER.name,
            days_ago=7, decided=True,
            note="生命周期与部门权限验证通过。",
        )
        # v0.9.0 草稿 部门内可见 —— 仍在管理员手中
        add_skill_version(
            kf, "v0.9.0", STATUS_DRAFT,
            "改进部门知识检索并增加来源时效检查。",
            DETAIL_KNOWLEDGE, ["知识库", "检索", "问答"],
            scope=SCOPE_DEPARTMENT, featured=False,
            submitted_by=CURRENT_USER.name,
            days_ago=0, decided=None,
        )
        # v0.8.0 历史被拒绝 —— 让 "全部提交" 与 "等待审核+草稿+审核通过=3" 之差对得上
        add_skill_version(
            kf, "v0.8.0", STATUS_REJECTED,
            "首次集成外部知识库，还在验证权限与频控。",
            DETAIL_KNOWLEDGE, ["知识库"],
            scope=SCOPE_PUBLIC, featured=False,
            submitted_by=CURRENT_USER.name,
            days_ago=20, decided=True,
            note="未引入所需的写入频控；下次版本请增加。",
        )

        db.commit()
    finally:
        db.close()
