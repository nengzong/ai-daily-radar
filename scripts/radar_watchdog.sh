#!/usr/bin/env bash
# 本机看门狗:给日报流水线补一条不会漂的触发通道。
#
# 为什么需要它:GitHub Actions 的 cron 触发时刻完全不受我们控制。本仓库实测
# 2026-08-17~26 延迟稳定在 10 分钟上下,但 08-27 三道 cron 全部漂到 4~5 小时之后
# (21:50 UTC 那道 02:12 才触发),08-28 更是一道都没触发,连着两天靠人工补跑。
# 工作流里「提前 2.5 小时起跑吃掉延迟」的余量已经被击穿,且再往前提也没用
# ——08-28 是压根没触发,不是触发晚了。
#
# workflow_dispatch 是即时的,从没漂过。所以把起跑的决定权拿回本机:launchd 按点
# 调用本脚本去 dispatch。GitHub 那三道 cron 原样保留,本机关机/出差时它们仍是兜底
# (后触发的 schedule run 会在工作流的「判断今天是否已生成」处秒退,不会重复推送)。
#
# 用法:
#   radar_watchdog.sh trigger    # 每天 06:00,起跑今天的日报
#   radar_watchdog.sh sentinel   # 每天 08:40,查岗;没送达就告警并补跑
#
# 两个调试开关:
#   RADAR_DATE=2026-08-01   查的日期换成别的(补跑历史日期、或演练未送达分支)
#   RADAR_DRY_RUN=1         只打印决策不真的 dispatch / 不真的发钉钉
#
# 可选:把钉钉凭据写到 ~/.config/ai-daily-radar/env,哨兵告警会同时发到手机:
#   DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=...
#   DINGTALK_SECRET=SECxxxx

set -euo pipefail

export TZ=Asia/Shanghai
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="nengzong/ai-daily-radar"
WORKFLOW="daily-radar.yml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HOME/.config/ai-daily-radar/env"

log() { printf '%s [%s] %s\n' "$(date '+%F %T')" "${MODE:-?}" "$*"; }

# 远端 main 上某天日报的字节数。查远端而不是本地工作区:日报是 Actions 直接推到
# main 的,本地未必 fetch 过。
#
# 三种结果必须分开,不能都当成「没有」:
#   文件存在   → 打印字节数,退出 0
#   确实没有   → 打印 0,退出 0
#   查不到     → 退出 1(网络不通、gh 鉴权过期、限流……)
# 之所以较真:gh api 遇 404 会把错误 JSON 打到 stdout 且以非零退出,早先写成
# `... || echo 0` 会拼出 `{"message":"Not Found"...}0`,而任何一种失败都会被读成
# 「今天还没出日报」从而 dispatch 补跑——网络抖一下就往公司群重复推一遍日报。
report_size() {
  local out rc=0
  out="$(gh api "repos/$REPO/contents/reports/$1.md" --jq '.size' 2>&1)" || rc=$?
  if [ "$rc" -eq 0 ]; then
    case "$out" in
      '' | *[!0-9]*) echo 0 ;;
      *) echo "$out" ;;
    esac
    return 0
  fi
  case "$out" in
    *'"status":"404"'* | *'Not Found'*) echo 0; return 0 ;;
    *) log "查询远端日报失败:$out" >&2; return 1 ;;
  esac
}

# 有几道 run 正在跑或排队。同样区分 0 和「查不到」。
#
# 这是防重复推送的关键:正常日子里 GitHub 的 21:50 UTC(北京 05:50)那道 cron 只
# 延迟十来分钟,06:00 我们来看的时候它往往已经在跑了。而 workflow_dispatch 会绕过
# 工作流里那个「今天已生成就跳过」的守卫(守卫只拦 schedule),所以这里不自己拦一道,
# 就会变成两道 run 各推一次钉钉。
active_runs() {
  local out rc=0
  out="$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --limit 20 \
          --json status \
          --jq '[.[] | select(.status == "in_progress" or .status == "queued" or .status == "waiting" or .status == "pending")] | length' 2>&1)" || rc=$?
  case "$out" in
    '' | *[!0-9]*) rc=1 ;;
  esac
  if [ "$rc" -ne 0 ]; then
    log "查询运行中的 run 失败:$out" >&2
    return 1
  fi
  echo "$out"
}

dispatch() {
  if [ -n "${RADAR_DRY_RUN:-}" ]; then
    log "DRY_RUN:本应 dispatch $WORKFLOW,已跳过"
    return 0
  fi
  gh workflow run "$WORKFLOW" --repo "$REPO" --ref main
}

# osascript 的参数用 `on run` 收,避免把消息内容拼进 AppleScript 源码被引号截断。
notify_local() {
  /usr/bin/osascript \
    -e 'on run {t, m}' \
    -e 'display notification m with title t' \
    -e 'end run' \
    -- "$1" "$2" 2>/dev/null || true
}

notify_dingtalk() {
  if [ -n "${RADAR_DRY_RUN:-}" ]; then
    log "DRY_RUN:本应发钉钉告警「$1」,已跳过"
    return 0
  fi
  [ -f "$ENV_FILE" ] || return 0
  set -a; . "$ENV_FILE"; set +a
  [ -n "${DINGTALK_WEBHOOK:-}" ] && [ -n "${DINGTALK_SECRET:-}" ] || return 0
  local body; body="$(mktemp)"
  printf '%s\n' "$2" > "$body"
  python3 "$SCRIPT_DIR/send_dingtalk.py" "$1" "$body" || log "钉钉告警发送失败"
  rm -f "$body"
}

# 查不到状态时一律不 dispatch:多推一次日报到公司群,比晚到一次更难收场,
# 何况 GitHub 那三道 cron 还在兜底,08:40 的哨兵也会再查一次。
bail_unknown() {
  log "状态查不到,本次不动作,交给 GitHub 的 cron 兜底"
  exit 1
}

MODE="${1:-}"
TODAY="${RADAR_DATE:-$(date +%F)}"

case "$MODE" in
  trigger)
    size="$(report_size "$TODAY")" || bail_unknown
    if [ "$size" -gt 0 ]; then
      log "远端已有 reports/$TODAY.md($size 字节),无需起跑"
      exit 0
    fi
    running="$(active_runs)" || bail_unknown
    if [ "$running" -gt 0 ]; then
      log "已有 $running 道 run 在跑/排队(多半是 GitHub 的 cron 已经触发),不重复起跑"
      exit 0
    fi
    log "远端无今天的日报且无 run 在跑,dispatch 起跑"
    dispatch
    log "已 dispatch,预计 08:30 准点投递"
    ;;

  sentinel)
    if ! size="$(report_size "$TODAY")"; then
      notify_local "AI 日报哨兵异常" "查不到 $TODAY 的送达状态,请手动确认"
      bail_unknown
    fi
    if [ "$size" -gt 0 ]; then
      log "reports/$TODAY.md 已在远端($size 字节),日报已送达"
      exit 0
    fi
    if ! running="$(active_runs)"; then
      notify_local "AI 日报哨兵异常" "$TODAY 未送达,且查不到运行状态,请手动确认"
      bail_unknown
    fi
    if [ "$running" -gt 0 ]; then
      # 已过 08:30,工作流的等待步骤不会再挂机,生成完会立刻投递,不用补跑。
      log "日报尚未送达,但有 $running 道 run 正在跑,等它自己投递"
      notify_local "AI 日报延迟" "$TODAY 的日报还在生成中,稍后送达"
      exit 0
    fi
    log "已过 08:40 仍无 reports/$TODAY.md,且没有任何 run 在跑,告警并补跑"
    notify_local "⚠️ AI 日报未送达" "$TODAY 08:40 仍未送达,已自动补跑"
    notify_dingtalk "⚠️ AI 日报未送达 $TODAY" "$(cat <<MSG
## ⚠️ AI 日报未送达

- 日期:$TODAY
- 现象:08:40 仍无 reports/$TODAY.md,且 GitHub 上没有任何 run 在跑
- 判断:GitHub 的 cron 又没触发,本机看门狗已自动 dispatch 补跑
- [查看运行](https://github.com/$REPO/actions)
MSG
)"
    dispatch
    log "已 dispatch 补跑"
    ;;

  *)
    echo "USAGE: $(basename "$0") {trigger|sentinel}" >&2
    exit 2
    ;;
esac
