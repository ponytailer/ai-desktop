"""批量注入 Mock 数据，用于演示和测试。

幂等：以 skill.name 为唯一键，已存在则跳过。
执行方式：
    cd /Users/hs/work/ai-desktop
    .venv/bin/python -m ai_desktop.mock_data
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta

from .database import DATA_DIR, SessionLocal
from .deps import CURRENT_USER, ROLE_KEY_ADMIN, ROLE_SKILLS_ADMIN, ROLE_SUPER_ADMIN
from .models import (
    CATEGORY_OPTIONS,
    KEY_APPROVED,
    KEY_PENDING,
    KEY_REJECTED,
    KEY_REVOKED,
    SCOPE_DEPARTMENT,
    SCOPE_PUBLIC,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    STATUS_SUPERSEDED,
    ApiKey,
    Category,
    Employee,
    Skill,
    SkillVersion,
)

ATTACHMENT_DIR = DATA_DIR / "attachments"

# ---------- 工具 ----------

def _zip_bytes(name: str, version: str) -> tuple[bytes, int]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", f"# {name}\n\n版本：{version}\nMock 演示数据。\n")
        zf.writestr("SKILL.md", f"---\nname: {name}\nversion: {version}\n---\n\n# {name}\n")
        zf.writestr("CHANGELOG.md", f"## {version}\n\n- Mock 演示条目\n")
    return buf.getvalue(), buf.tell()


def _save_attachment(skill_id: int, version_id: int, name: str, version: str) -> str:
    ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    folder = ATTACHMENT_DIR / str(skill_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{version_id}.zip"
    data, size = _zip_bytes(name, version)
    path.write_bytes(data)
    return str(path.relative_to(ATTACHMENT_DIR.parent)), size


# ---------- 详情模板 ----------

D_GENERIC = """**输入**：结构化文本或 API 响应。
**流程**：解析 → 规则匹配 → LLM 增强 → 格式化输出。
**输出**：Markdown 报告 + 可操作建议。
**适用边界**：单次请求 < 50KB；需要网络访问。"""

D_DOC = """**输入**：文档链接或上传的 Markdown。
**流程**：分块 → 语义索引 → 按问题检索 → 生成摘要。
**输出**：答案 + 来源引用 + 相关文档推荐。
**适用边界**：文档总量 < 500 篇；支持中文 / 英文。"""

D_TEST = """**输入**：代码文件路径、测试框架配置。
**流程**：分析函数签名 → 生成边界用例 → 覆盖率预估 → 输出测试文件。
**输出**：可直接运行的测试代码、覆盖率报告。
**适用边界**：Python / TypeScript；单文件 < 2000 行。"""

D_API = """**输入**：OpenAPI / Swagger JSON。
**流程**：解析端点 → 生成参数组合 → Mock 响应 → 集成测试。
**输出**：测试集合、Mock Server 配置。
**适用边界**：REST API；不支持 GraphQL。"""

D_DEPLOY = """**输入**：CI/CD 流水线配置、环境变量清单。
**流程**：解析依赖 → 安全扫描 → 部署计划 → 回滚预案。
**输出**：部署清单、风险评估、回滚脚本。
**适用边界**：K8s / Docker；单服务部署。"""

D_FINANCE = """**输入**：财务报表数据（Excel / CSV）。
**流程**：数据清洗 → 异常检测 → 趋势分析 → 可视化。
**输出**：分析报告、图表、预警清单。
**适用边界**：月度 / 季度数据；单表 < 10 万行。"""

D_TRANSLATE = """**输入**：源文本、目标语言对。
**流程**：术语库匹配 → 机器翻译 → 人工校对建议 → 术语一致性检查。
**输出**：译文 + 术语表 + 质量评分。
**适用边界**：支持 12 种语言；单次 < 5000 字。"""

D_EMAIL = """**输入**：邮件主题、收件人画像、沟通目的。
**流程**：语气分析 → 模板匹配 → 多版本生成 → 礼仪检查。
**输出**：3 版邮件草稿、发送时机建议。
**适用边界**：中英文商务邮件；不处理法律条款。"""

D_ONBOARD = """**输入**：新员工角色、部门、入职日期。
**流程**：生成入职清单 → 配置权限 → 推送学习资料 → 设置 7/30/90 天检查点。
**输出**：入职计划表、权限申请单、学习路径。
**适用边界**：标准岗位；不覆盖特殊审批流。"""

D_CONTRACT = """**输入**：合同 PDF 或文本。
**流程**：OCR / 文本提取 → 条款分类 → 风险识别 → 合规比对。
**输出**：风险清单、修改建议、合规报告。
**适用边界**：中文合同；< 100 页。"""

D_MONITOR = """**输入**：Prometheus 指标、日志流。
**流程**：基线学习 → 异常检测 → 根因关联 → 告警去噪。
**输出**：告警面板、根因路径、静默建议。
**适用边界**：时序数据；采样间隔 ≥ 15s。"""

D_DESIGN = """**输入**：Figma 设计稿链接、组件清单。
**流程**：解析设计 Token → 生成前端组件 → Storybook 文档 → 对齐检查。
**输出**：React / Vue 组件代码、Storybook 故事。
**适用边界**：Figma；React 18+ / Vue 3+。"""

D_REPORT = """**输入**：数据源配置、报表模板。
**流程**：数据拉取 → 指标计算 → 图表生成 → 定时推送。
**输出**：PDF / HTML 报表、定时任务配置。
**适用边界**：SQL 数据源；日 / 周 / 月粒度。"""

D_TRAINING = """**输入**：课程大纲、学员画像。
**流程**：内容拆分 → 练习题生成 → 学习路径推荐 → 进度跟踪。
**输出**：课程结构、练习题集、学习路径。
**适用边界**：技术类课程；单课程 < 50 课时。"""


# ---------- Mock 技能定义 ----------

MOCK_SKILLS: list[dict] = [
    # --- 已发布 + 部分有版本历史 ---
    {
        "name": "Test Genie",
        "icon": "🧪",
        "accent": "#8B5CF6",
        "category": "代码质量",
        "owner_name": "张拓",
        "owner_team": "质量保障",
        "downloads": 845, "likes": 72, "featured": True,
        "versions": [
            {"ver": "v1.2.0", "status": STATUS_PUBLISHED, "summary": "自动生成单元测试并预估覆盖率。", "detail": D_TEST, "tags": ["测试", "覆盖率", "自动化"], "scope": SCOPE_PUBLIC, "featured": True, "submitted_by": "张拓", "days_ago": 8, "decided": True, "note": "覆盖率达标，准予发布。"},
            {"ver": "v1.1.0", "status": STATUS_SUPERSEDED, "summary": "支持 Python 单元测试生成。", "detail": D_TEST, "tags": ["测试", "Python"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "张拓", "days_ago": 30, "decided": True, "note": "已被 v1.2.0 替代。"},
        ],
    },
    {
        "name": "API Guardian",
        "icon": "🔌",
        "accent": "#06B6D4",
        "category": "研发工具",
        "owner_name": "李维",
        "owner_team": "基础架构",
        "downloads": 612, "likes": 48, "featured": False,
        "versions": [
            {"ver": "v2.0.1", "status": STATUS_PUBLISHED, "summary": "从 OpenAPI 规范自动生成集成测试和 Mock Server。", "detail": D_API, "tags": ["API", "测试", "Mock"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "李维", "days_ago": 11, "decided": True, "note": "通过。"},
            {"ver": "v2.1.0", "status": STATUS_PENDING, "summary": "增加 GraphQL 支持和 WebSocket 测试。", "detail": D_API, "tags": ["API", "GraphQL", "WebSocket"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "李维", "days_ago": 1, "decided": False},
        ],
    },
    {
        "name": "Deploy Planner",
        "icon": "🚀",
        "accent": "#F59E0B",
        "category": "研发工具",
        "owner_name": "王硕",
        "owner_team": "DevOps",
        "downloads": 398, "likes": 31, "featured": False,
        "versions": [
            {"ver": "v1.0.3", "status": STATUS_PUBLISHED, "summary": "分析 CI/CD 流水线并生成部署计划与回滚预案。", "detail": D_DEPLOY, "tags": ["部署", "CI/CD", "K8s"], "scope": SCOPE_DEPARTMENT, "featured": False, "submitted_by": "王硕", "days_ago": 14, "decided": True, "note": "部门内可见，准予发布。"},
        ],
    },
    {
        "name": "FinLens",
        "icon": "💰",
        "accent": "#10B981",
        "category": "数据与分析",
        "owner_name": "刘倩",
        "owner_team": "财务数字化",
        "downloads": 276, "likes": 22, "featured": False,
        "versions": [
            {"ver": "v0.9.2", "status": STATUS_PUBLISHED, "summary": "财务报表异常检测与趋势可视化。", "detail": D_FINANCE, "tags": ["财务", "异常检测", "可视化"], "scope": SCOPE_DEPARTMENT, "featured": False, "submitted_by": "刘倩", "days_ago": 16, "decided": True, "note": "通过。"},
        ],
    },
    {
        "name": "Lingo Bridge",
        "icon": "🌐",
        "accent": "#6366F1",
        "category": "业务运营",
        "owner_name": "陈雨桐",
        "owner_team": "国际化",
        "downloads": 354, "likes": 28, "featured": False,
        "versions": [
            {"ver": "v1.4.0", "status": STATUS_PUBLISHED, "summary": "术语库驱动的多语言翻译与一致性检查。", "detail": D_TRANSLATE, "tags": ["翻译", "多语言", "术语"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "陈雨桐", "days_ago": 9, "decided": True, "note": "通过。"},
            {"ver": "v1.5.0", "status": STATUS_PENDING, "summary": "新增同声传译辅助模式和实时术语推荐。", "detail": D_TRANSLATE, "tags": ["翻译", "实时", "术语"], "scope": SCOPE_PUBLIC, "featured": True, "submitted_by": "陈雨桐", "days_ago": 1, "decided": False},
        ],
    },
    {
        "name": "Mail Craft",
        "icon": "✉️",
        "accent": "#EC4899",
        "category": "运营增长",
        "owner_name": "顾潇",
        "owner_team": "市场中心",
        "downloads": 423, "likes": 35, "featured": True,
        "versions": [
            {"ver": "v2.2.0", "status": STATUS_PUBLISHED, "summary": "根据收件人画像生成多版本商务邮件草稿。", "detail": D_EMAIL, "tags": ["邮件", "文案", "商务"], "scope": SCOPE_PUBLIC, "featured": True, "submitted_by": "顾潇", "days_ago": 7, "decided": True, "note": "精选推荐，通过。"},
        ],
    },
    {
        "name": "Onboard Flow",
        "icon": "🎯",
        "accent": "#14B8A6",
        "category": "业务运营",
        "owner_name": "孙怡",
        "owner_team": "人力资源",
        "downloads": 187, "likes": 14, "featured": False,
        "versions": [
            {"ver": "v1.0.0", "status": STATUS_PUBLISHED, "summary": "新员工入职清单、权限配置与学习路径生成。", "detail": D_ONBOARD, "tags": ["入职", "HR", "自动化"], "scope": SCOPE_DEPARTMENT, "featured": False, "submitted_by": "孙怡", "days_ago": 19, "decided": True, "note": "部门内可见，通过。"},
        ],
    },
    {
        "name": "Contract Lens",
        "icon": "📋",
        "accent": "#A855F7",
        "category": "安全合规",
        "owner_name": "周宁",
        "owner_team": "法务科技",
        "downloads": 156, "likes": 12, "featured": False,
        "versions": [
            {"ver": "v0.7.0", "status": STATUS_PUBLISHED, "summary": "合同条款风险识别与合规比对。", "detail": D_CONTRACT, "tags": ["合同", "风险", "合规"], "scope": SCOPE_DEPARTMENT, "featured": False, "submitted_by": "周宁", "days_ago": 21, "decided": True, "note": "通过，注意保密。"},
        ],
    },
    {
        "name": "Metric Watch",
        "icon": "📊",
        "accent": "#3B82F6",
        "category": "研发工具",
        "owner_name": "赵可",
        "owner_team": "SRE",
        "downloads": 305, "likes": 24, "featured": False,
        "versions": [
            {"ver": "v1.1.2", "status": STATUS_PUBLISHED, "summary": "基于基线学习的指标异常检测与告警去噪。", "detail": D_MONITOR, "tags": ["监控", "告警", "SRE"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "赵可", "days_ago": 13, "decided": True, "note": "通过。"},
        ],
    },
    {
        "name": "Design to Code",
        "icon": "🎨",
        "accent": "#F43F5E",
        "category": "研发工具",
        "owner_name": "林远",
        "owner_team": "前端工程",
        "downloads": 689, "likes": 55, "featured": True,
        "versions": [
            {"ver": "v2.3.0", "status": STATUS_PUBLISHED, "summary": "从 Figma 设计稿生成前端组件与 Storybook 文档。", "detail": D_DESIGN, "tags": ["设计", "前端", "Figma"], "scope": SCOPE_PUBLIC, "featured": True, "submitted_by": "林远", "days_ago": 6, "decided": True, "note": "精选推荐，通过。"},
            {"ver": "v2.2.0", "status": STATUS_SUPERSEDED, "summary": "支持 React 组件生成。", "detail": D_DESIGN, "tags": ["设计", "React"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "林远", "days_ago": 35, "decided": True, "note": "已被 v2.3.0 替代。"},
        ],
    },
    {
        "name": "Report Forge",
        "icon": "📈",
        "accent": "#0EA5E9",
        "category": "数据与分析",
        "owner_name": "周宁",
        "owner_team": "数据智能",
        "downloads": 258, "likes": 19, "featured": False,
        "versions": [
            {"ver": "v1.6.0", "status": STATUS_PUBLISHED, "summary": "定时数据报表生成与多渠道推送。", "detail": D_REPORT, "tags": ["报表", "自动化", "定时"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "周宁", "days_ago": 17, "decided": True, "note": "通过。"},
        ],
    },
    {
        "name": "Path Mentor",
        "icon": "🎓",
        "accent": "#8B5CF6",
        "category": "业务运营",
        "owner_name": "孙怡",
        "owner_team": "培训发展",
        "downloads": 142, "likes": 11, "featured": False,
        "versions": [
            {"ver": "v0.5.1", "status": STATUS_PUBLISHED, "summary": "技术课程拆分与个性化学习路径推荐。", "detail": D_TRAINING, "tags": ["培训", "学习路径", "课程"], "scope": SCOPE_DEPARTMENT, "featured": False, "submitted_by": "孙怡", "days_ago": 23, "decided": True, "note": "通过。"},
        ],
    },
    # --- 管理员（当前用户）提交的更多版本，丰富「我的上传」 ---
    {
        "name": "Doc Digest",
        "icon": "📄",
        "accent": "#64748B",
        "category": "业务运营",
        "owner_name": CURRENT_USER.name,
        "owner_team": "知识中台",
        "downloads": 98, "likes": 8, "featured": False,
        "versions": [
            {"ver": "v1.0.0", "status": STATUS_PUBLISHED, "summary": "文档摘要与智能问答。", "detail": D_DOC, "tags": ["文档", "摘要", "问答"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": CURRENT_USER.name, "days_ago": 25, "decided": True, "note": "通过。"},
            {"ver": "v1.1.0", "status": STATUS_PENDING, "summary": "增加多文档对比和知识图谱可视化。", "detail": D_DOC, "tags": ["文档", "对比", "知识图谱"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": CURRENT_USER.name, "days_ago": 1, "decided": False},
            {"ver": "v0.9.0", "status": STATUS_REJECTED, "summary": "首个原型版本。", "detail": D_DOC, "tags": ["文档"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": CURRENT_USER.name, "days_ago": 40, "decided": True, "note": "摘要准确率不达标，请优化 prompt 后重新提交。"},
        ],
    },
    {
        "name": "Smart Triage",
        "icon": "🔀",
        "accent": "#F97316",
        "category": "客服与支持",
        "owner_name": CURRENT_USER.name,
        "owner_team": "客户成功",
        "downloads": 0, "likes": 0, "featured": False,
        "versions": [
            {"ver": "v0.3.0", "status": STATUS_DRAFT, "summary": "工单自动分类与优先级评分草稿。", "detail": D_GENERIC, "tags": ["工单", "分类", "优先级"], "scope": SCOPE_DEPARTMENT, "featured": False, "submitted_by": CURRENT_USER.name, "days_ago": 0, "decided": None},
        ],
    },
    # --- 更多待审核（其他用户提交） ---
    {
        "name": "Release Drafter",
        "icon": "📝",
        "accent": "#6366F1",
        "category": "研发工具",
        "owner_name": "张拓",
        "owner_team": "质量保障",
        "downloads": 0, "likes": 0, "featured": False,
        "versions": [
            {"ver": "v1.0.0", "status": STATUS_PENDING, "summary": "从 Git log 和 PR 列表自动生成版本发布说明。", "detail": D_GENERIC, "tags": ["发版", "Git", "文档"], "scope": SCOPE_PUBLIC, "featured": False, "submitted_by": "张拓", "days_ago": 2, "decided": False},
        ],
    },
    {
        "name": "Compliance Checker",
        "icon": "✅",
        "accent": "#059669",
        "category": "安全合规",
        "owner_name": "邓岩",
        "owner_team": "安全工程",
        "downloads": 0, "likes": 0, "featured": False,
        "versions": [
            {"ver": "v0.8.0", "status": STATUS_PENDING, "summary": "代码合规性自动检查与修复建议。", "detail": D_GENERIC, "tags": ["合规", "安全", "扫描"], "scope": SCOPE_DEPARTMENT, "featured": True, "submitted_by": "邓岩", "days_ago": 3, "decided": False},
        ],
    },
]


def inject_mock_data() -> None:
    """幂等注入 mock 数据。"""
    db = SessionLocal()
    try:
        # 确保分类存在
        existing_cats = {c.name for c in db.query(Category).all()}
        if not existing_cats:
            for idx, name in enumerate(CATEGORY_OPTIONS):
                db.add(Category(name=name, sort=idx * 10))
            db.flush()

        added_skills = 0
        added_versions = 0

        for item in MOCK_SKILLS:
            # 跳过已存在
            if db.query(Skill).filter(Skill.name == item["name"]).first():
                continue

            skill = Skill(
                name=item["name"],
                icon=item["icon"],
                accent_color=item["accent"],
                short_description=item["versions"][0]["summary"],
                category=item["category"],
                owner_name=item["owner_name"],
                owner_team=item["owner_team"],
                downloads=item["downloads"],
                likes=item["likes"],
                is_featured=item["featured"],
            )
            db.add(skill)
            db.flush()
            added_skills += 1

            for vd in item["versions"]:
                v = SkillVersion(
                    skill_id=skill.id,
                    version=vd["ver"],
                    summary=vd["summary"],
                    detail=vd["detail"],
                    scope=vd.get("scope", SCOPE_PUBLIC),
                    status=vd["status"],
                    submitted_by=vd.get("submitted_by", item["owner_name"]),
                    submitted_at=datetime.utcnow() - timedelta(days=vd.get("days_ago", 6), hours=2),
                    featured_badge=vd.get("featured", False),
                )
                v.set_tags(vd["tags"])
                db.add(v)
                db.flush()

                if vd.get("decided") is True:
                    v.decided_by = CURRENT_USER.name
                    v.decided_at = datetime.utcnow() - timedelta(days=vd["days_ago"], hours=1)
                if vd.get("note"):
                    v.decision_note = vd["note"]

                # 写 zip 附件
                rel_path, size = _save_attachment(skill.id, v.id, skill.name, vd["ver"])
                v.attachment_path = rel_path
                v.attachment_size = size
                added_versions += 1

        db.commit()
        print(f"✅ Mock 数据注入完成：新增 {added_skills} 个 Skill，{added_versions} 个版本。")
        if added_skills == 0:
            print("   （数据库中已存在同名 Skill，跳过。如需重新注入请先清库。）")

        # 密钥 mock 数据
        inject_mock_keys(db)

        # 员工 mock 数据
        inject_mock_employees(db)
    finally:
        db.close()


# ---------- 密钥 mock 数据 ----------

MOCK_KEYS = [
    # 当前用户（管理员）的申请
    {"applicant_id": "48890023", "applicant_name": "管理员", "purpose": "对接内部知识库检索 API，用于 SkillHub 的知识搜索功能。", "status": KEY_APPROVED, "days_ago": 15, "reviewed_by": "管理员", "note": "已分配"},
    {"applicant_id": "48890023", "applicant_name": "管理员", "purpose": "测试阿里云通义千问大模型接口连通性。", "status": KEY_PENDING, "days_ago": 1, "reviewed_by": None, "note": ""},
    {"applicant_id": "48890023", "applicant_name": "管理员", "purpose": "调用企业内部数据看板 API 做报表自动化。", "status": KEY_REJECTED, "days_ago": 20, "reviewed_by": "李娜", "note": "用途不明确，请补充具体使用场景和调用频率。"},
    # 其他用户的申请（供密钥管理员审核）
    {"applicant_id": "10020001", "applicant_name": "张伟", "purpose": "开发智能客服机器人，需要调用大模型对话接口。", "status": KEY_PENDING, "days_ago": 2, "reviewed_by": None, "note": ""},
    {"applicant_id": "10020004", "applicant_name": "陈芳", "purpose": "用于自动化报表生成工具的 API 集成，预计每日调用 500 次。", "status": KEY_PENDING, "days_ago": 3, "reviewed_by": None, "note": ""},
    {"applicant_id": "10020005", "applicant_name": "刘洋", "purpose": "搭建内部代码搜索服务，需要 Embedding API。", "status": KEY_APPROVED, "days_ago": 10, "reviewed_by": "李娜", "note": "已分配标准配额"},
    {"applicant_id": "10020006", "applicant_name": "赵敏", "purpose": "用于测试环境的接口联调，短期使用。", "status": KEY_REVOKED, "days_ago": 30, "reviewed_by": "李娜", "note": "测试已完成，密钥已吊销"},
    {"applicant_id": "10020007", "applicant_name": "孙杰", "purpose": "数据分析平台接入大模型做自然语言查询。", "status": KEY_PENDING, "days_ago": 0, "reviewed_by": None, "note": ""},
    {"applicant_id": "10020008", "applicant_name": "周婷", "purpose": "用于营销文案自动生成工具的 API 调用。", "status": KEY_APPROVED, "days_ago": 8, "reviewed_by": "管理员", "note": "已分配"},
    {"applicant_id": "10020009", "applicant_name": "吴磊", "purpose": "不知道用来干嘛，就是想要一个。", "status": KEY_REJECTED, "days_ago": 12, "reviewed_by": "李娜", "note": "申请用途不明确，请详细说明使用场景。"},
]


def inject_mock_keys(db) -> None:
    """幂等注入密钥 mock 数据。"""
    existing = db.query(ApiKey).count()
    if existing > 0:
        print(f"   密钥数据已存在（{existing} 条），跳过注入。")
        return

    import secrets as _sec
    added = 0
    for kd in MOCK_KEYS:
        k = ApiKey(
            applicant_id=kd["applicant_id"],
            applicant_name=kd["applicant_name"],
            purpose=kd["purpose"],
            status=kd["status"],
            created_at=datetime.utcnow() - timedelta(days=kd["days_ago"], hours=3),
        )
        if kd["status"] == KEY_APPROVED:
            k.api_key_value = "sk-" + _sec.token_hex(16)
            k.reviewed_by = kd["reviewed_by"]
            k.reviewed_at = datetime.utcnow() - timedelta(days=kd["days_ago"], hours=2)
            k.review_note = kd["note"]
        elif kd["status"] in (KEY_REJECTED, KEY_REVOKED):
            k.reviewed_by = kd["reviewed_by"]
            k.reviewed_at = datetime.utcnow() - timedelta(days=kd["days_ago"], hours=2)
            k.review_note = kd["note"]
        db.add(k)
        added += 1

    db.commit()
    print(f"   ✅ 密钥 mock 数据注入完成：新增 {added} 条申请记录。")


# ---------- 员工 mock 数据 ----------

MOCK_EMPLOYEES = [
    {"id": "48890023", "name": "管理员",   "department": "数字化工作台", "roles": [ROLE_SUPER_ADMIN]},
    {"id": "10020001", "name": "张伟",     "department": "客户成功部",   "roles": []},
    {"id": "10020002", "name": "李娜",     "department": "信息安全部",   "roles": [ROLE_KEY_ADMIN]},
    {"id": "10020003", "name": "王强",     "department": "质量保障部",   "roles": [ROLE_SKILLS_ADMIN]},
    {"id": "10020004", "name": "陈芳",     "department": "数据分析部",   "roles": []},
    {"id": "10020005", "name": "刘洋",     "department": "基础架构部",   "roles": []},
    {"id": "10020006", "name": "赵敏",     "department": "市场中心",     "roles": []},
    {"id": "10020007", "name": "孙杰",     "department": "数据智能部",   "roles": []},
    {"id": "10020008", "name": "周婷",     "department": "运营增长部",   "roles": []},
    {"id": "10020009", "name": "吴磊",     "department": "法务科技部",   "roles": []},
    {"id": "10020010", "name": "张拓",     "department": "质量保障部",   "roles": []},
    {"id": "10020011", "name": "李维",     "department": "基础架构部",   "roles": []},
    {"id": "10020012", "name": "王硕",     "department": "DevOps",       "roles": []},
    {"id": "10020013", "name": "刘倩",     "department": "财务数字化",   "roles": []},
    {"id": "10020014", "name": "陈雨桐",   "department": "国际化部",     "roles": []},
    {"id": "10020015", "name": "顾潇",     "department": "市场中心",     "roles": []},
    {"id": "10020016", "name": "林远",     "department": "前端工程部",   "roles": []},
    {"id": "10020017", "name": "邓岩",     "department": "安全工程部",   "roles": []},
]


def inject_mock_employees(db) -> None:
    """幂等注入员工 mock 数据。"""
    existing = db.query(Employee).count()
    if existing > 0:
        print(f"   员工数据已存在（{existing} 条），跳过注入。")
        return

    added = 0
    for ed in MOCK_EMPLOYEES:
        emp = Employee(id=ed["id"], name=ed["name"], department=ed["department"])
        emp.set_roles(ed["roles"])
        emp.is_test_data = True
        db.add(emp)
        added += 1

    db.commit()
    print(f"   ✅ 员工 mock 数据注入完成：新增 {added} 名员工。")


if __name__ == "__main__":
    inject_mock_data()
