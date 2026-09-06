#!/usr/bin/env bash
# 把 radar_watchdog.sh 装成四个 launchd 定时任务。可重复执行(会先卸载旧的)。
#
#   07:50  generate       起跑今天的生成(GitHub 的兜底 cron 已经在跑就让路)
#   08:30  deliver        准点投递  ← 这一道决定日报几点进群
#   08:40  sentinel       查岗;缺什么补什么,并本地通知 + 钉钉告警
#   09:10  sentinel-last  最后一次补救
#
# 时刻表和 Cloudflare Worker 那条通道一致(workers/radar-watchdog/wrangler.toml)。
# 【两条通道只能开一条】——同时跑会各自 dispatch 一次,往公司群重推两遍日报。
#
# launchd 的 StartCalendarInterval 在 Mac 睡眠时不会丢任务:醒来后会补跑一次错过的。
# 但彻底关机/不在身边时这条通道是断的——那时靠 GitHub 自己那两道兜底 cron。

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/ai-daily-radar"
DOMAIN="gui/$(id -u)"

mkdir -p "$AGENT_DIR" "$LOG_DIR"

install_agent() {
  local mode="$1" hour="$2" minute="$3"
  local label="com.nengzong.ai-daily-radar.$mode"
  local plist="$AGENT_DIR/$label.plist"

  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO_DIR/scripts/radar_watchdog.sh</string>
    <string>$mode</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$hour</integer>
    <key>Minute</key><integer>$minute</integer>
  </dict>
  <key>EnvironmentVariables</key>
  <dict>
    <!-- launchd 的 PATH 极简,gh 在 /opt/homebrew/bin 里,不给就找不到 -->
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>TZ</key><string>Asia/Shanghai</string>
  </dict>
  <key>StandardOutPath</key><string>$LOG_DIR/$mode.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/$mode.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLIST

  plutil -lint "$plist" >/dev/null
  launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$plist"
  printf '已装载 %-10s %02d:%02d  %s\n' "$mode" "$hour" "$minute" "$plist"
}

install_agent generate      7 50
install_agent deliver       8 30
install_agent sentinel      8 40
install_agent sentinel-last 9 10

echo
echo "日志:$LOG_DIR/{generate,deliver,sentinel,sentinel-last}.log"
echo "手动演练:launchctl kickstart -p $DOMAIN/com.nengzong.ai-daily-radar.deliver"
echo "卸载:    launchctl bootout $DOMAIN/com.nengzong.ai-daily-radar.{generate,deliver,sentinel,sentinel-last}"
