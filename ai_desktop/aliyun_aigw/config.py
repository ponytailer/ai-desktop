"""阿里云 AI Gateway 客户端配置（环境变量 / .env）。

Mock / 生产切换（重要）
============================================================================
为方便本地演示（尚无真实 AK/SK 或网关资源），默认在「未配置 AK/SK」或
环境变量 AIGW_USE_MOCK=1 时走 mock 数据分支，返回结构与真实接口一致，
可直接驱动图表与列表展示。

上生产时：
  1. 设置 AIGW_USE_MOCK=0（或直接删除该变量）
  2. 配置真实凭据：ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET
  3. 配置网关与配额规则 ID：ALIYUN_APIG_GATEWAY_ID / ALIYUN_APIG_QUOTA_RULE_ID
     （以及可选的 ALIYUN_APIG_SUBJECT_ID 作为默认查询主体）
============================================================================
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

API_VERSION = "2024-03-27"
ALGORITHM = "ACS3-HMAC-SHA256"

# 从 .env 加载配置（已存在的环境变量优先，不覆盖）
load_dotenv(override=False)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


ACCESS_KEY_ID = _env("ALIYUN_ACCESS_KEY_ID")
ACCESS_KEY_SECRET = _env("ALIYUN_ACCESS_KEY_SECRET")
REGION = _env("ALIYUN_REGION", "cn-hangzhou")
# AI Gateway 控制面域名，不同账号/环境可能不同，用 ALIYUN_APIG_HOST 覆盖
HOST = _env("ALIYUN_APIG_HOST", f"apig.{REGION}.aliyuncs.com")
GATEWAY_ID = _env("ALIYUN_APIG_GATEWAY_ID")
QUOTA_RULE_ID = _env("ALIYUN_APIG_QUOTA_RULE_ID")
DEFAULT_SUBJECT_ID = _env("ALIYUN_APIG_SUBJECT_ID")

# Mock 开关：显式置 1，或「未配置 AK/SK」时自动 mock（避免无凭据直接报错）
USE_MOCK = _env("AIGW_USE_MOCK", "0") == "1" or not (ACCESS_KEY_ID and ACCESS_KEY_SECRET)

if USE_MOCK:
    print(
        "[aigw] 使用 MOCK 数据（未配置 AK/SK 或 AIGW_USE_MOCK=1）。"
        "上生产请配置凭据并设 AIGW_USE_MOCK=0。"
    )
