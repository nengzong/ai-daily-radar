#!/bin/bash
# 用 Gmail SMTP 直发邮件(依赖系统自带 curl + python3,无需安装任何东西)
# 用法: ./send_email.sh "邮件主题" 正文文件路径(Markdown)
# 密码优先读环境变量 GMAIL_APP_PASSWORD(CI 用),回落到
# ~/.config/ai-daily-radar/gmail_app_password(本机用),两处都是 Google App 专用密码(16 位)
# 正文会经 md2html.py 转成 HTML,以 multipart/alternative 发送:
# 邮件客户端渲染 HTML 版,不支持 HTML 的客户端回退到纯文本版
set -euo pipefail

PASS_FILE="$HOME/.config/ai-daily-radar/gmail_app_password"
EMAIL_FILE="$HOME/.config/ai-daily-radar/email_address"
ADDR="${GMAIL_TO:-}"
if [ -z "$ADDR" ] && [ -s "$EMAIL_FILE" ]; then
  ADDR=$(tr -d ' \r\n' < "$EMAIL_FILE")
fi

if [ -z "$ADDR" ]; then
  echo "NO_RECIPIENT: 未设置 GMAIL_TO 环境变量，且未在 $EMAIL_FILE 找到接收邮箱"
  exit 2
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -n "${GMAIL_APP_PASSWORD:-}" ]; then
  PASS=$(printf '%s' "$GMAIL_APP_PASSWORD" | tr -d ' \r\n')
elif [ -s "$PASS_FILE" ]; then
  PASS=$(tr -d ' \r\n' < "$PASS_FILE")
else
  echo "NO_PASSWORD: 环境变量 GMAIL_APP_PASSWORD 未设置且 $PASS_FILE 不存在或为空"
  exit 2
fi

# base64 换行参数在 BSD(-b)和 GNU(-w)上不兼容,统一先去掉换行再用 fold 折行
b64_wrap() { base64 < "$1" | tr -d '\n' | fold -w 76; }

SUBJECT_B64=$(printf '%s' "$1" | base64 | tr -d '\n')
BOUNDARY="=_radar_$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"

MSG=$(mktemp)
HTML=$(mktemp)
trap 'rm -f "$MSG" "$HTML"' EXIT

if command -v python3 >/dev/null 2>&1 && python3 "$SCRIPT_DIR/md2html.py" < "$2" > "$HTML" 2>/dev/null; then
  {
    printf 'From: %s\r\n' "$ADDR"
    printf 'To: %s\r\n' "$ADDR"
    printf 'Subject: =?UTF-8?B?%s?=\r\n' "$SUBJECT_B64"
    printf 'MIME-Version: 1.0\r\n'
    printf 'Content-Type: multipart/alternative; boundary="%s"\r\n' "$BOUNDARY"
    printf '\r\n'
    printf -- '--%s\r\n' "$BOUNDARY"
    printf 'Content-Type: text/plain; charset=UTF-8\r\n'
    printf 'Content-Transfer-Encoding: base64\r\n'
    printf '\r\n'
    b64_wrap "$2" | sed -e 's/$/\r/'
    printf '\r\n'
    printf -- '--%s\r\n' "$BOUNDARY"
    printf 'Content-Type: text/html; charset=UTF-8\r\n'
    printf 'Content-Transfer-Encoding: base64\r\n'
    printf '\r\n'
    b64_wrap "$HTML" | sed -e 's/$/\r/'
    printf '\r\n'
    printf -- '--%s--\r\n' "$BOUNDARY"
  } > "$MSG"
else
  # python3 不可用或转换失败时,退回原来的纯文本发送
  {
    printf 'From: %s\r\n' "$ADDR"
    printf 'To: %s\r\n' "$ADDR"
    printf 'Subject: =?UTF-8?B?%s?=\r\n' "$SUBJECT_B64"
    printf 'MIME-Version: 1.0\r\n'
    printf 'Content-Type: text/plain; charset=UTF-8\r\n'
    printf 'Content-Transfer-Encoding: 8bit\r\n'
    printf '\r\n'
    cat "$2"
  } > "$MSG"
fi

curl -sS --url 'smtps://smtp.gmail.com:465' \
  --mail-from "$ADDR" --mail-rcpt "$ADDR" \
  --user "$ADDR:$PASS" \
  --upload-file "$MSG"

echo "SENT"
