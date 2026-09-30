#!/usr/bin/env bash
# 发告警:每天最多一条。先推钉钉,钉钉失败就改发邮件。
# 用法: send_alert.sh <日期> <标题> <markdown文件路径>
#
# 只在 GitHub Actions 里用——发出去之后要往 main 推一份 state/alerted/<日期>.txt。
# 当天后面所有告警(生成/投递流水线、Worker 09:10 那道哨兵)看到它就不再发。
#
# 为什么要去重:2026-09-29/30 钉钉的 webhook 月度额度用完,一天里两道投递 run、
# 08:40/08:42/09:10/09:12 四道哨兵、下午漂过来的兜底 cron 都各自告警一次,
# 前后十来条。那两天钉钉全拒了所以没人收到;要是直接换成邮件,就是一天十来封。
#
# 为什么钉钉失败要改发邮件:钉钉本身挂掉时,告警也走钉钉的话会跟着一起哑——
# 那两天就是这样,Gmail 照常收到日报,但「没进群」这件事没有任何提醒。
#
# 需要环境变量:DINGTALK_WEBHOOK / DINGTALK_SECRET / GMAIL_APP_PASSWORD;可选 RUN_URL。
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "USAGE: send_alert.sh <日期> <标题> <markdown文件路径>" >&2
  exit 2
fi

day="$1" title="$2" body="$3"
marker="state/alerted/$day.txt"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 查远端 main 而不是工作区,理由同投递守卫:别的 run 刚推上去的记录,本 run 的 checkout 里看不到。
# 查不到远端时照发:多一条告警比漏一条强。
if git fetch --quiet --depth=1 origin main \
   && [ "$(git cat-file -s "FETCH_HEAD:$marker" 2>/dev/null || echo 0)" -gt 0 ]; then
  echo "$marker 已存在,今天已经告警过,不再重复发"
  exit 0
fi

if python3 "$SCRIPT_DIR/send_dingtalk.py" "$title" "$body"; then
  channel=dingtalk
else
  echo "钉钉告警没发出去,改发邮件"
  if bash "$SCRIPT_DIR/send_email.sh" "$title" "$body"; then
    channel=email
  else
    # 不写记录:后面的告警方还能再试一次
    echo "::error::钉钉和邮件都没发出去,今天的告警丢了"
    exit 1
  fi
fi

# 告警已经发出去了,记录推不上去也不算这一步失败——最坏是今天后面再来一条。
# 用 && 串而不是靠 set -e:函数放在 || 左边时 set -e 不生效,中间一步失败会接着往下跑。
record() {
  mkdir -p state/alerted &&
    printf 'alerted_at=%s\nchannel=%s\ntitle=%s\nrun=%s\n' \
      "$(date '+%F %T %Z')" "$channel" "$title" "${RUN_URL:-}" > "$marker" &&
    git config user.name "github-actions[bot]" &&
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com" &&
    git add "$marker" &&
    git commit -m "告警记录 $day" &&
    git pull --rebase --autostash origin main &&
    git push origin HEAD:main
}
record || echo "::warning::告警已通过 $channel 发出,但 $marker 没推上去,今天后面可能还会再告警一次"
