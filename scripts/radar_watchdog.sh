#!/usr/bin/env bash
# 本机看门狗:Cloudflare Worker 那条通道的 shell 版备用通道 + 命令行工具。
#
# 和 workers/radar-watchdog/src/index.js 是同一套决策逻辑,读的是本机 gh 的登录凭据,
# 不用 PAT。两条通道【只能开一条】——同时跑会各自看到「还没投递」而各 dispatch 一次,
# 往公司群重推两遍日报。
#
# 【2026-09-30 起和 Worker 不再一致】Worker 改成了「只补不喊、09:10 兜底告警一次、认
# state/delivery-failed 和 state/alerted」,本脚本没跟着改(当时这条通道没启用)。
# 重新启用之前先对照 index.js 的 runDeliver / runSentinel / finalAlert 同步一遍。
#
# 为什么需要外部触发:GitHub Actions 的 cron 触发时刻完全不受我们控制。本仓库实测
# 2026-08-17~26 延迟稳定在 10 分钟上下,但 08-27 三道 cron 全部漂到 4~5 小时之后,
# 08-28 一道都没触发。workflow_dispatch 是即时的,从没漂过。
#
# 生成和投递是两条独立的流水线(拆分理由见 .github/workflows/daily-deliver.yml 顶部):
# 生成想跑多久跑多久,投递由「按点触发」保证准点。
#
# 用法:
#   radar_watchdog.sh generate        # 07:50  起跑今天的生成
#   radar_watchdog.sh deliver         # 08:30  准点投递  ← 这一道决定日报几点进群
#   radar_watchdog.sh sentinel        # 08:40  查岗,缺什么补什么
#   radar_watchdog.sh sentinel-last   # 09:10  最后一次补救
#
# 两个调试开关:
#   RADAR_DATE=2026-08-01   查的日期换成别的(补跑历史日期、或演练未送达分支)
#   RADAR_DRY_RUN=1         只打印决策不真的 dispatch / 不真的发钉钉
#
# 可选:把钉钉凭据写到 ~/.config/ai-daily-radar/env,告警会同时发到手机:
#   DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=...
#   DINGTALK_SECRET=SECxxxx

set -euo pipefail

export TZ=Asia/Shanghai
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="nengzong/ai-daily-radar"
WF_GENERATE="daily-radar.yml"
WF_DELIVER="daily-deliver.yml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HOME/.config/ai-daily-radar/env"

log() { printf '%s [%s] %s\n' "$(date '+%F %T')" "${MODE:-?}" "$*"; }

# 远端 main 上某个文件的字节数。查远端而不是本地工作区:日报和回执都是 Actions
# 直接推到 main 的,本地未必 fetch 过。
#
# 三种结果必须分开,不能都当成「没有」:
#   文件存在   → 打印字节数,退出 0
#   确实没有   → 打印 0,退出 0
#   查不到     → 退出 1(网络不通、gh 鉴权过期、限流……)
# 之所以较真:gh api 遇 404 会把错误 JSON 打到 stdout 且以非零退出,早先写成
# `... || echo 0` 会拼出 `{"message":"Not Found"...}0`,而任何一种失败都会被读成
# 「今天还没投」从而 dispatch 补投——网络抖一下就往公司群重复推一遍日报。
remote_size() {
  local out rc=0
  out="$(gh api "repos/$REPO/contents/$1" --jq '.size' 2>&1)" || rc=$?
  if [ "$rc" -eq 0 ]; then
    case "$out" in
      '' | *[!0-9]*) echo 0 ;;
      *) echo "$out" ;;
    esac
    return 0
  fi
  case "$out" in
    *'"status":"404"'* | *'Not Found'*) echo 0; return 0 ;;
    *) log "查询 $1 失败:$out" >&2; return 1 ;;
  esac
}

# 今天的日报生成好了没。注意:拆成两条流水线之后,这【只证明生成完了】,不代表进群了。
report_size() { remote_size "reports/$1.md"; }

# 今天的日报投递出去了没。判断「是否送达」必须看这份回执——投递流水线在钉钉推送
# 成功之后立刻提交它。早先生成即投递,那时查的就是日报文件本身。
receipt_size() { remote_size "state/delivered/$1.txt"; }

# 某条流水线有几道 run 正在跑或排队。同样区分 0 和「查不到」。
# 这是防重复推送的关键:GitHub 那两道兜底 cron 万一已经在跑,或者你刚手动 Run 过一次,
# 这时候再 dispatch 就是两道 run 各推一次钉钉。
active_runs() {
  local out rc=0
  out="$(gh run list --repo "$REPO" --workflow "$1" --limit 20 \
          --json status \
          --jq '[.[] | select(.status == "in_progress" or .status == "queued" or .status == "waiting" or .status == "pending")] | length' 2>&1)" || rc=$?
  case "$out" in
    '' | *[!0-9]*) rc=1 ;;
  esac
  if [ "$rc" -ne 0 ]; then
    log "查询 $1 的 run 失败:$out" >&2
    return 1
  fi
  echo "$out"
}

dispatch() {
  if [ -n "${RADAR_DRY_RUN:-}" ]; then
    log "DRY_RUN:本应 dispatch $1,已跳过"
    return 0
  fi
  gh workflow run "$1" --repo "$REPO" --ref main
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
# 何况 GitHub 那两道兜底 cron 还在,后面的哨兵也会再查一次。
bail_unknown() {
  log "状态查不到,本次不动作,交给 GitHub 的兜底 cron"
  exit 1
}

# 08:40 和 09:10 共用的查岗逻辑。$1 = last(当天最后一次机会)时把话说死。
sentinel() {
  local last="$1" size running

  if ! size="$(receipt_size "$TODAY")"; then
    notify_local "AI 日报哨兵异常" "查不到 $TODAY 的送达状态,请手动确认"
    bail_unknown
  fi
  if [ "$size" -gt 0 ]; then
    log "$TODAY 已有投递回执,日报已送达"
    exit 0
  fi

  # 投递 run 还在跑就等它,别再 dispatch 一道,那是往公司群重复推送。
  if ! running="$(active_runs "$WF_DELIVER")"; then bail_unknown; fi
  if [ "$running" -gt 0 ]; then
    log "尚无回执,但有 $running 道投递 run 正在跑,等它自己完成"
    exit 0
  fi

  if ! size="$(report_size "$TODAY")"; then bail_unknown; fi

  # 日报已就绪却没投出去:08:30 那道投递没成事。
  if [ "$size" -gt 0 ]; then
    log "日报已就绪($size 字节)却无回执,告警并补投"
    notify_local "⚠️ AI 日报未按时投递" "$TODAY 的日报已生成但没进群,已自动补投"
    notify_dingtalk "⚠️ AI 日报未按时投递 $TODAY" "$(cat <<MSG
## ⚠️ 日报已生成,但没能按时进群

- 日期:$TODAY
- 现象:日报早已就绪($size 字节),却查不到投递回执
- 判断:08:30 那道投递没成事(没触发,或投递 run 失败了)
- 处理:本机看门狗已自动补投
- [查看运行](https://github.com/$REPO/actions)
MSG
)"
    dispatch "$WF_DELIVER"
    exit 0
  fi

  # 连日报都还没有。
  if ! running="$(active_runs "$WF_GENERATE")"; then bail_unknown; fi
  if [ "$running" -gt 0 ]; then
    if [ "$last" = "last" ]; then
      log "仍在生成中($running 道 run),已是最后一道哨兵,生成完需要手动投递"
      notify_local "⚠️ AI 日报仍在生成" "$TODAY 生成完后需手动 Run 一次投递流水线"
    else
      log "尚未生成完,但有 $running 道生成 run 正在跑,等下一道哨兵再看"
      notify_local "AI 日报延迟" "$TODAY 的日报还在生成中,稍后送达"
    fi
    exit 0
  fi

  log "既无日报也无 run 在跑,告警并补跑生成"
  notify_local "⚠️ AI 日报未送达" "$TODAY 仍未生成,已自动补跑"
  notify_dingtalk "⚠️ AI 日报未送达 $TODAY" "$(cat <<MSG
## ⚠️ AI 日报未送达

- 日期:$TODAY
- 现象:仍无 reports/$TODAY.md,且 GitHub 上没有任何 run 在跑
- 判断:07:50 那道起跑没成事(或 run 已失败退出),本机看门狗已自动补跑生成
$([ "$last" = "last" ] \
  && echo "- ⚠️ 这已是当天最后一道哨兵:生成完之后【不会】再自动投递,需要手动 Run 一次投递流水线" \
  || echo "- 生成好之后,09:10 那道哨兵会自动补投")
- [查看运行](https://github.com/$REPO/actions)
MSG
)"
  dispatch "$WF_GENERATE"
}

MODE="${1:-}"
TODAY="${RADAR_DATE:-$(date +%F)}"

case "$MODE" in
  # trigger 是旧名字,留作别名,免得老的 launchd plist 静默失效
  generate | trigger)
    size="$(report_size "$TODAY")" || bail_unknown
    if [ "$size" -gt 0 ]; then
      log "远端已有 reports/$TODAY.md($size 字节),无需起跑"
      exit 0
    fi
    running="$(active_runs "$WF_GENERATE")" || bail_unknown
    if [ "$running" -gt 0 ]; then
      log "已有 $running 道生成 run 在跑/排队(多半是 GitHub 的兜底 cron 已触发),不重复起跑"
      exit 0
    fi
    log "远端无今天的日报且无 run 在跑,dispatch 生成"
    dispatch "$WF_GENERATE"
    log "已 dispatch 生成,08:30 由 deliver 那道准点投递"
    ;;

  deliver)
    size="$(receipt_size "$TODAY")" || bail_unknown
    if [ "$size" -gt 0 ]; then
      log "$TODAY 已有投递回执,今天已经投过,不重复投递"
      exit 0
    fi
    running="$(active_runs "$WF_DELIVER")" || bail_unknown
    if [ "$running" -gt 0 ]; then
      log "已有 $running 道投递 run 在跑/排队,不重复投递"
      exit 0
    fi
    size="$(report_size "$TODAY")" || bail_unknown
    if [ "$size" -eq 0 ]; then
      # 生成还没跑完就别硬投,投递流水线拿不到文件只会红一次。补救交给哨兵。
      log "到点了但 reports/$TODAY.md 还没有,无法投递,等哨兵补救"
      notify_local "⚠️ AI 日报 08:30 无法投递" "$TODAY 还没生成完,哨兵会继续补救"
      notify_dingtalk "⚠️ AI 日报 08:30 无法投递 $TODAY" "$(cat <<MSG
## ⚠️ 到点了但日报还没生成好

- 日期:$TODAY
- 现象:08:30 该投递了,远端却还没有 reports/$TODAY.md
- 处理:08:40 和 09:10 两道哨兵会继续补救,生成一好就自动补投
- [查看运行](https://github.com/$REPO/actions)
MSG
)"
      exit 0
    fi
    log "日报已就绪($size 字节),dispatch 投递"
    dispatch "$WF_DELIVER"
    ;;

  sentinel)      sentinel notlast ;;
  sentinel-last) sentinel last ;;

  *)
    echo "USAGE: $(basename "$0") {generate|deliver|sentinel|sentinel-last}" >&2
    exit 2
    ;;
esac
