#!/usr/bin/env python3
"""把日报的钉钉版推送到群机器人。

用法: send_dingtalk.py <标题> <markdown文件路径>

需要环境变量:
  DINGTALK_WEBHOOK  群机器人 webhook URL(含 access_token)
  DINGTALK_SECRET   加签密钥(SEC 开头)

钉钉失败时 HTTP 状态码仍是 200,真正的成败看响应体的 errcode,所以必须解析。
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request

# 钉钉单条消息上限 20000 字节。留出余量给截断提示和多字节边界。
MAX_BYTES = 18000
TIMEOUT = 20


def truncate(text: str) -> str:
    """按 UTF-8 字节数截断,避免把多字节字符切成半个。"""
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_BYTES:
        return text
    note = "\n\n> ⚠️ 内容过长已截断,完整日报见仓库。"
    budget = MAX_BYTES - len(note.encode("utf-8"))
    return encoded[:budget].decode("utf-8", errors="ignore") + note


def signed_url(webhook: str, secret: str) -> str:
    timestamp = str(round(time.time() * 1000))
    payload = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={timestamp}&sign={sign}"


def main() -> int:
    if len(sys.argv) != 3:
        print("USAGE: send_dingtalk.py <title> <markdown-file>", file=sys.stderr)
        return 2

    title, path = sys.argv[1], sys.argv[2]
    webhook = os.environ.get("DINGTALK_WEBHOOK", "").strip()
    secret = os.environ.get("DINGTALK_SECRET", "").strip()

    if not webhook or not secret:
        print("MISSING_CREDENTIALS: 需要 DINGTALK_WEBHOOK 和 DINGTALK_SECRET", file=sys.stderr)
        return 2

    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        print(f"EMPTY_CONTENT: {path} 为空,拒绝推送", file=sys.stderr)
        return 1

    # 如果配置了 RADAR_BASE_URL (环境变量或本地配置)，将 GitHub 仓库限制链接替换为网页版公开链接
    base_url = os.environ.get("RADAR_BASE_URL", "").strip()
    base_url_file = os.path.expanduser("~/.config/ai-daily-radar/radar_base_url")
    if not base_url and os.path.isfile(base_url_file):
        try:
            with open(base_url_file, "r", encoding="utf-8") as f:
                base_url = f.read().strip()
        except Exception:
            pass

    if base_url:
        import re
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', path)
        if date_match:
            web_link = f"{base_url.rstrip('/')}/reports/{date_match.group(1)}/"
        else:
            web_link = base_url.rstrip('/')
        
        web_btn = f"\n\n---\n\n### 🌐 [👉 点击在线阅读网页版完整报告]({web_link})\n"
        github_pattern = r'> 完整日报:https://github\.com/[^\s\n]+(?:\s*\(需仓库权限\))?'
        if re.search(github_pattern, text):
            text = re.sub(github_pattern, f"> 🌐 网页版直达: [{web_link}]({web_link})", text) + web_btn
        else:
            text = text + web_btn

    body = json.dumps(
        {"msgtype": "markdown", "markdown": {"title": title, "text": truncate(text)}},
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        signed_url(webhook, secret),
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"REQUEST_FAILED: {exc}", file=sys.stderr)
        return 1

    if result.get("errcode") != 0:
        print(f"DINGTALK_ERROR: {result}", file=sys.stderr)
        return 1

    print("SENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
