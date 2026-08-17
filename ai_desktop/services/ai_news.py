"""首页 AI 资讯抓取与缓存服务。

设计目标（用户明确要求）：
- 新闻做服务端缓存，不要每个人进来都爬一遍。
- 因此按「自然日」缓存到 ai_news_cache 表，TTL 内直接返回；
  TTL 过期才触发一次刷新（后台线程，不阻塞访客），首次无缓存时阻塞抓取一次。

数据源：多个公开 RSS（无需 API Key），可在 _FEEDS 调整。
并发抓取（ThreadPoolExecutor）以控制最坏耗时；单源失败不影响其它源。
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import html
import json
import re
import threading
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from ..database import SessionLocal
from ..models import AiNewsCache

# 抓取源（标题, RSS 地址）；均可免 Key 访问，按需增删。
# 说明：本服务部署环境的外网受限，BBC中文 / 纽约时报中文网 / Google News 等
# 海外源均超时不可达；以下为可稳定访问的中文科技媒体（其报道天然覆盖
# 国内 + 海外 AI 动态），再按主题做「国内/国外」地域标注与混排。
_FEEDS = [
    ("量子位", "https://www.qbitai.com/feed"),
    ("爱范儿", "https://www.ifanr.com/feed"),
    ("极客公园", "https://www.geekpark.net/rss"),
    ("钛媒体", "https://www.tmtpost.com/rss.xml"),
]

# 缓存版本：调整 _FEEDS 或分类逻辑后 +1，自动使旧缓存失效（无需手动清库）。
_CACHE_VERSION = 2

_TTL = dt.timedelta(hours=3)          # 同一天最多刷新一次
_FETCH_TIMEOUT = 6                      # 单源超时（秒）
_TOP_N = 5
_SUMMARY_LEN = 110
_USER_AGENT = "Mozilla/5.0 (compatible; AIDesktopNewsBot/1.0)"

# 相关性兜底关键词（部分综合源可能混入非 AI 条目）
# - 中文短语：子串匹配
# - 英文 token：整词匹配（避免 ai 命中 rain/email 等）
_KW_SUBSTR = (
    "人工智能", "大模型", "机器学习", "深度学习", "神经网络", "智能体", "多模态",
    "算力", "芯片", "机器人", "语音",
)
_KW_WORDS = (
    "ai", "llm", "gpt", "chatgpt", "openai", "gemini", "claude", "diffusion",
    "agent", "agents", "aigc", "nlp",
)

# 主题地域分类（用于「国内/国外」标签，确保国内外资讯都有展示）
_REGION_FOREIGN = (
    "openai", "chatgpt", "gpt-", "gpt5", "gpt4", "anthropic", "claude", "google",
    "谷歌", "gemini", "deepmind", "meta", "llama", "microsoft", "微软", "apple",
    "苹果", "nvidia", "英伟达", "xai", "马斯克", "musk", "tesla", "特斯拉",
    "amazon", "亚马逊", "perplexity", "mistral", "sam altman", "altman", "欧盟",
    "美国", "硅谷", "斯坦福", "mit", "英国", "法国", "日本", "韩国", "加拿大",
    "德国", "新加坡",
)
_REGION_DOMESTIC = (
    "百度", "文心", "字节", "豆包", "阿里", "通义", "千问", "腾讯", "混元", "华为",
    "盘古", "智谱", "glm", "月之暗面", "kimi", "小米", "美团", "京东", "商汤",
    "科大讯飞", "讯飞", "阶跃", "百川", "零一万物", "deepseek", "深度求索", "中国",
    "国内", "清华", "北大", "复旦", "阿里云", "百度智能云",
)

_refresh_lock = threading.Lock()
_refreshing = False


# --------------------------------------------------------------------------- #
# 解析辅助
# --------------------------------------------------------------------------- #
def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate(text: str, n: int = _SUMMARY_LEN) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _parse_date(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        d = parsedate_to_datetime(raw)
        if d is not None:
            return d.replace(tzinfo=None) if d.tzinfo else d
    except (TypeError, ValueError):
        pass
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _is_relevant(title: str, summary: str) -> bool:
    blob = (title + " " + summary).lower()
    if any(k in blob for k in _KW_SUBSTR):
        return True
    return any(re.search(rf"\b{re.escape(k)}\b", blob) for k in _KW_WORDS)


def _classify_region(title: str, summary: str) -> str:
    """按主题标注地域：命中境外厂商/地区→国外，命中中国厂商/机构→国内，否则综合。"""
    blob = (title + " " + summary).lower()
    if any(k in blob for k in _REGION_FOREIGN):
        return "国外"
    if any(k in blob for k in _REGION_DOMESTIC):
        return "国内"
    return "综合"


def _parse_feed(xml_bytes: bytes, source: str) -> list[dict]:
    """解析 RSS 2.0 与 Atom，返回 [{title,url,summary,source,published}]。"""
    root = ET.fromstring(xml_bytes)
    items: list[dict] = []

    # RSS 2.0：<rss><channel><item>...
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = _strip_html(item.findtext("description") or "")
        pub = _parse_date(item.findtext("pubDate"))
        if title:
            items.append({"title": title, "url": link, "summary": desc,
                          "source": source, "published": pub})

    if items:
        return items

    # Atom：<feed><entry>...（带命名空间）
    NS = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{NS}entry"):
        title = (entry.findtext(f"{NS}title") or "").strip()
        summary = _strip_html(
            entry.findtext(f"{NS}summary")
            or entry.findtext(f"{NS}content")
            or ""
        )
        link = ""
        for l in entry.findall(f"{NS}link"):
            rel = l.get("rel")
            if rel is None or rel == "alternate":
                link = l.get("href") or ""
                break
        pub = _parse_date(
            entry.findtext(f"{NS}updated") or entry.findtext(f"{NS}published")
        )
        if title:
            items.append({"title": title, "url": link, "summary": summary,
                          "source": source, "published": pub})
    return items


def _fetch_one(url: str, source: str) -> list[dict]:
    resp = requests.get(url, timeout=_FETCH_TIMEOUT,
                        headers={"User-Agent": _USER_AGENT})
    resp.raise_for_status()
    items = _parse_feed(resp.content, source)
    out = []
    for it in items:
        # 仅保留 http/https 链接，过滤 javascript: 等潜在危险值
        if it["url"].startswith(("http://", "https://")) and _is_relevant(
            it["title"], it["summary"]
        ):
            it["region"] = _classify_region(it["title"], it["summary"])
            out.append(it)
    return out


# --------------------------------------------------------------------------- #
# 聚合
# --------------------------------------------------------------------------- #
def _collect() -> list[dict]:
    """并发抓取所有源，合并去重后按时间倒序取 Top N。"""
    collected: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=len(_FEEDS)) as ex:
        futs = {ex.submit(_fetch_one, url, src): src for src, url in _FEEDS}
        for f in cf.as_completed(futs, timeout=_FETCH_TIMEOUT + 2):
            try:
                collected.extend(f.result())
            except Exception:
                # 单源失败不影响其它源
                continue

    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for it in collected:
        key = (it["title"].lower(), it["url"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)

    unique.sort(
        key=lambda x: x["published"] or dt.datetime.min, reverse=True
    )

    picked = _pick_diverse(unique, _TOP_N)

    out = [
        {
            "title": t["title"],
            "url": t["url"],
            "summary": _truncate(t["summary"]),
            "source": t["source"],
            "region": t.get("region", "综合"),
        }
        for t in picked
    ]
    return out


def _pick_diverse(unique: list[dict], top_n: int) -> list[dict]:
    """按时间倒序取 Top N，但尽量同时保留国内与国外，确保两者都出现。"""
    top = unique[:top_n]
    has_domestic = any(i.get("region") == "国内" for i in top)
    has_foreign = any(i.get("region") == "国外" for i in top)

    def _best(region: str) -> dict | None:
        cands = [i for i in unique if i.get("region") == region]
        if not cands:
            return None
        return max(cands, key=lambda x: x["published"] or dt.datetime.min)

    if not has_foreign:
        best = _best("国外")
        if best:
            for k in range(len(top) - 1, -1, -1):
                if top[k].get("region") != "国外":
                    top[k] = best
                    break
    if not has_domestic:
        best = _best("国内")
        if best:
            for k in range(len(top) - 1, -1, -1):
                if top[k].get("region") != "国内":
                    top[k] = best
                    break

    # 替换后重新按时间倒序
    top.sort(key=lambda x: x["published"] or dt.datetime.min, reverse=True)
    return top


def _cache_key() -> str:
    """按自然日 + 缓存版本生成键值；改 _FEEDS/_CACHE_VERSION 后旧缓存自动失效。"""
    return f"{dt.date.today().isoformat()}#v{_CACHE_VERSION}"


def _store(items: list[dict]) -> None:
    key = _cache_key()
    now = dt.datetime.utcnow()
    db = SessionLocal()
    try:
        row = db.query(AiNewsCache).filter(AiNewsCache.news_date == key).first()
        payload = json.dumps(items, ensure_ascii=False)
        if row:
            row.payload = payload
            row.fetched_at = now
        else:
            db.add(AiNewsCache(news_date=key, payload=payload, fetched_at=now))
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# 对外接口
# --------------------------------------------------------------------------- #
def refresh_news() -> list[dict]:
    """抓取并写库；同一时刻只跑一个线程（_refresh_lock + _refreshing 标志）。

    返回本次抓到的结果（可能为空，表示全部源失败）。
    """
    global _refreshing
    with _refresh_lock:
        if _refreshing:
            return []
        _refreshing = True
    try:
        items = _collect()
        if items:
            _store(items)
        return items
    finally:
        with _refresh_lock:
            _refreshing = False


def get_ai_news(db) -> list[dict]:
    """首页调用：优先返回当日缓存；过期则后台刷新并先返回旧值；首次无缓存则阻塞抓一次。"""
    key = _cache_key()
    row = db.query(AiNewsCache).filter(AiNewsCache.news_date == key).first()
    now = dt.datetime.utcnow()

    if row and row.fetched_at and (now - row.fetched_at) < _TTL:
        return json.loads(row.payload)

    if row:
        # 缓存存在但已过期：后台刷新，本次仍返回旧数据，不阻塞访客
        threading.Thread(target=refresh_news, daemon=True).start()
        return json.loads(row.payload)

    # 从未抓取过：阻塞抓取一次（仅首次，之后都走缓存）
    items = refresh_news()
    if items:
        r = db.query(AiNewsCache).filter(AiNewsCache.news_date == key).first()
        if r:
            return json.loads(r.payload)
    return []
