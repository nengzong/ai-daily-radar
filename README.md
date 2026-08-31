# AI Daily Radar 每日 AI 情报雷达

每天早上自动扫描 40+ 个国内外信息源(国内媒体社区、海外社区、顶级 AI 实验室官方、一线科技媒体、楼宇/设施管理/能源垂直行业),由 AI 从公司业务视角筛选出**行业动向、技术与案例、产品灵感**,英文信号自动翻译成中文,汇总成一份日报,推送到钉钉群和邮箱。

**运行在 GitHub Actions 上,不依赖本机开机。**

## 产出与投递

| 产出 | 位置 |
|---|---|
| 日报全文 | `reports/YYYY-MM-DD.md`(自动提交回仓库) |
| 钉钉群版 | `reports/YYYY-MM-DD.dingtalk.md`(凝练版,推送用) |
| 钉钉群消息 | TL;DR + 各条目标题 + 原始链接,每条都可点进原文 |
| 邮件 | HTML 渲染版,直发 nengzongtan@gmail.com |

## 运行时间

日报要在**北京 08:30 前**送达。

起跑由仓库外面的 **Cloudflare Worker** 负责,北京 **07:50** 用 `workflow_dispatch` 打进来;
workflow 生成完(实测 15~25 分钟)**立刻投递**,日报约 08:05~08:15 到。

| 通道 | 时间(北京) | 角色 |
|---|---|---|
| Cloudflare cron `50 23 * * *` | **07:50** | 主触发:远端还没有今天的日报、且没有 run 在跑 → dispatch |
| Cloudflare cron `40 0 * * *` | **08:40** | 哨兵:还没送达 → 钉钉告警 + dispatch 补跑 |
| GitHub cron `0 1 * * *` | **09:00** | 末端兜底:Cloudflare 整条通道挂掉时才真正干活 |

**GitHub 的定时任务不准时**,所以准点性不能靠它:官方说明高负载期会延迟甚至直接丢弃,
本仓库实测延迟 1h05m、1h07m、2h23m,08-27 三道 cron 全部漂到 4~5 小时之后,08-28 一道都没触发。
`workflow_dispatch` 是即时的、从没漂过,所以起跑的决定权放在 GitHub 外面(见下)。
GitHub 那道 09:00 的 cron 留着只为「Cloudflare 也挂了」,正常日子里它会在
「判断今天是否已生成」处秒退,不会重复推送。

当天只会真正执行一次。「判断今天是否已生成」这一步会去查**远端 main 的最新状态**
(而不是 checkout 出来的工作区——触发被延迟后 checkout 的是旧 SHA,看不到刚推上去的日报),
已经有今天的日报就秒退。**手动触发不受此限制**,方便随时补跑。

也可以在 GitHub 仓库的 Actions 页面手动点 **Run workflow** 立即触发一次。

### ⚠️ 不要在 runner 上挂机等时间

早先的版本为了「08:30 准点送达」,在 workflow 里加了一步 `sleep` 到 08:30 才投递,
起跑则大幅提前到 05:50 用来吃掉 cron 延迟。结果单次 run 挂机 2.5 小时:

```
2026-08-29T22:00:08Z  success  150 分钟   ← 生成只用了约 20 分钟,其余全在 sleep
2026-08-28T22:00:06Z  success  150 分钟
...8 月这样的 run 有 13 道,全月 3062 分钟
```

**GitHub Actions 按 runner 分钟计费,私有仓库免费额度 2000 分钟/月。**
2026-08-30 额度耗尽,此后所有 run 秒退,报
`The job was not started because recent account payments have failed or your spending limit needs to be increased`——
连着两天日报没送达,而且这种失败**连钉钉告警都发不出来**(job 根本没启动,告警步骤在 job 里)。

现在准点性由 Worker 的 cron 负责,workflow 里没有任何等待步骤,单次 run 约 25 分钟,
月耗约 750 分钟,稳在免费额度内。`timeout-minutes: 60` 是单次跑飞时的计费封顶。

**所以:不要再加 cron,不要把起跑时间往早挪,不要在 workflow 里 sleep。**
要改送达时间,改 `workers/radar-watchdog/wrangler.toml` 里的起跑 cron
(改完 `index.js` 顶部的 `CRON_TRIGGER` 常量必须逐字跟着改,再 `npx wrangler deploy`)。

额度用完了怎么办:等下个月 1 号自动重置,或去 Settings → Billing 设 spending limit,
或把仓库改成 public(公开仓库 Actions 免费无限,但 `reports/` 是公司业务内容,慎重)。

### 外部看门狗(主触发通道)

2026-08-27/28 上面这套余量被击穿了:08-27 三道 cron 全部漂到 4~5 小时之后(`50 21` 那道 02:12 UTC 才触发),08-28 一道都没触发。两天的日报都是人工发现没收到、手动补跑的。往前提起跑时间救不了 08-28 那种情况——那不是触发晚了,是压根没触发。

`workflow_dispatch` 是即时的,从没漂过。所以起跑的决定权移到 GitHub 外面,由一个 Cloudflare Worker 按点去 dispatch:

| Cloudflare cron (UTC) | 北京时间 | 行为 |
|---|---|---|
| `50 23 * * *` | **07:50** | 远端还没有今天的日报、且没有 run 在跑 → dispatch 起跑 |
| `40 0 * * *` | **08:40** | 还没送达 → 钉钉告警 + dispatch 补跑 |

代码在 `workers/radar-watchdog/`。告警走钉钉直发,而不是「再 dispatch 一个告警 workflow」——**被监控的东西不能是告警的前提**,否则 Actions 真出问题时告警会跟着一起哑掉。

GitHub 自己那道 09:00 的 cron **保留**做末端兜底:Cloudflare 也挂了的话它仍可能跑起来,而 schedule run 会在「判断今天是否已生成」处秒退,不会重复推送。

看门狗自己也不会造成重复推送——dispatch 前会检查有没有 run 正在跑/排队(比如你刚手动 Run 过一次)。查不到状态时(网络不通、token 过期)一律**不动作**:多推一次日报到公司群比晚到一次更难收场,何况还有 cron 兜底和 08:40 的哨兵复查。

#### 部署与运维

```bash
cd workers/radar-watchdog
npx wrangler deploy
npx wrangler tail                      # 实时看日志
```

三个 Secret(`npx wrangler secret put <名字>`):

| 名字 | 说明 |
|---|---|
| `GITHUB_TOKEN` | 细粒度 PAT,仅本仓库,`Actions: Read and write` + `Contents: Read-only` |
| `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` | 群机器人凭据,和 GitHub Secrets 里那份同源 |
| `CONTROL_KEY` | 控制端点的密钥,随机串即可 |

部署后可以用控制端点在线上演练(密钥不对一律 404)。`$KEY` 存在 `~/.config/ai-daily-radar/worker_control_key`:

```bash
U=https://ai-daily-radar-watchdog.radar-watchdog.workers.dev
KEY=$(cat ~/.config/ai-daily-radar/worker_control_key)

curl "$U/status?key=$KEY"        # 只读:今天的日报字节数 + 在跑的 run 数
curl "$U/probe?key=$KEY"         # 验 token 有没有 Actions: Write(422 = 有)
curl "$U/run/trigger?key=$KEY"   # 走一遍起跑决策
curl "$U/run/sentinel?key=$KEY"  # 走一遍查岗决策
```

换了 token 之后用 `/probe` 确认权限,**别用真触发去试**——真 dispatch 一次的代价是往公司群重推一遍当天日报。探针故意拿一个不存在的 ref 去 dispatch,403 = 没权限、422 = 有权限但 ref 不对,不会真的建出 run。

**PAT 过期这条通道会无声失效**,所以建议建 token 时选 No expiration。真过期了,哨兵那一步会因为查不到状态而发「哨兵异常」告警,不会静默。

#### 备用:本机 launchd

`scripts/radar_watchdog.sh` 是同一套逻辑的 shell 版,`scripts/install-launchd.sh` 把它装成本机定时任务。**当前未安装**(切到 Worker 时已卸载)——它和 Worker 都在 06:00 触发,同时跑会各自看到「没有 run 在跑」而各 dispatch 一次,往公司群重推两遍日报。**两条通道只能开一条。**

shell 版读的是本机 `gh` 的登录凭据,不用 PAT;告警发 macOS 本地通知,想同时进手机就把钉钉凭据写到 `~/.config/ai-daily-radar/env`(`DINGTALK_WEBHOOK=` / `DINGTALK_SECRET=`)。

Worker 那边出问题时可以临时切回来:

```bash
bash scripts/install-launchd.sh                                            # 启用
launchctl bootout gui/$(id -u)/com.nengzong.ai-daily-radar.{trigger,sentinel}   # 停用
```

这个 shell 版也能直接当命令行工具用,不依赖 launchd:

```bash
RADAR_DRY_RUN=1 ./scripts/radar_watchdog.sh trigger          # 只打印决策,不真的触发
RADAR_DATE=2026-08-27 ./scripts/radar_watchdog.sh sentinel   # 换个日期查/补跑
```

## 工作原理

```
.github/workflows/daily-radar.yml
  ├─ 1. checkout 仓库
  ├─ 2. claude-code-action 执行 prompts/daily-radar.md
  │     抓 40+ 个源 → AI 筛选 → 写日报全文 + 钉钉版 → 更新榜单快照
  ├─ 3. 校验两个报告文件存在且非空(不满足则中止,绝不推空消息)
  ├─ 4. 推送钉钉(scripts/send_dingtalk.py)
  ├─ 5. 发送邮件(scripts/send_email.sh,钉钉失败也照发)
  └─ 6. 提交日报回仓库
```

**投递不由 AI 负责。** Claude 只生成文件,推送和发信是 workflow 里确定性的步骤——这样任何一步失败都会让 workflow 红灯,GitHub 会发失败告警邮件,而不会出现「AI 以为发了其实没发」的情况。

## 配置(GitHub Secrets)

在仓库 Settings → Secrets and variables → Actions 里配置四个:

| Secret | 来源 |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | 本机运行 `claude setup-token` 生成,走 Claude 订阅额度,不按 token 计费 |
| `DINGTALK_WEBHOOK` | 钉钉群 → 群设置 → 机器人 → 添加自定义机器人,复制 Webhook 地址 |
| `DINGTALK_SECRET` | 添加机器人时勾选「加签」,复制 `SEC` 开头的密钥 |
| `GMAIL_APP_PASSWORD` | Google [应用专用密码页面](https://myaccount.google.com/apppasswords)生成的 16 位密码 |

钉钉机器人的安全设置**必须用「加签」**,不能用 IP 白名单——Actions runner 的出口 IP 是动态的。

## 如何调整

- **改信息源**:编辑 [sources.md](sources.md),每次运行都会重新读取
- **改筛选标准 / 日报结构 / 钉钉版格式**:编辑 [prompts/daily-radar.md](prompts/daily-radar.md)
- **改时间**:改 [workers/radar-watchdog/wrangler.toml](workers/radar-watchdog/wrangler.toml) 里的起跑 cron(UTC,北京时间减 8 小时),`src/index.js` 顶部的 `CRON_TRIGGER` 常量必须逐字跟着改,然后 `npx wrangler deploy`。**别改成在 workflow 里等**,见「不要在 runner 上挂机等时间」
- **暂停**:在 GitHub 仓库 Actions 页面点 workflow → 右上角 `···` → Disable workflow

## 排查投递问题

**失败会主动告警**:任何一步出错,workflow 都会往钉钉群推一条带运行日志链接的告警,不用靠「今天没收到日报」事后察觉。收到告警后去 Actions 页面手动 Run workflow 即可补跑。

这条告警覆盖不了「cron 全被 GitHub 丢弃」的情况——那种情况下 workflow 压根没启动,自然也没法告警。这个盲区由 Worker 的 **08:40 哨兵**补上(见「外部看门狗」):它查的是远端有没有今天的日报,不关心 workflow 有没有启动,所以「没跑」和「跑失败」都能兜住。

哨兵也没响、日报也没来,说明 Worker 这条通道也断了。`npx wrangler tail` 看看它有没有在跑,再去 Actions 页面手动 Run workflow 补跑。

**手动 Run 也失败、而且几秒就红**:去 Actions 页面看那道 run 的 annotation。若是
`The job was not started because recent account payments have failed or your spending limit needs to be increased`,
那不是代码问题,是 GitHub Actions 的月度分钟额度用完了,见「不要在 runner 上挂机等时间」。
这种失败没有任何告警——job 没启动,workflow 里的告警步骤跑不到,Worker 哨兵也只会说「已 dispatch 补跑」。
可以用 `gh run list --limit 5` 和 `gh run view <id>` 在本机快速确认。

仓库里还有一个 **投递链路自检** workflow(`.github/workflows/test-delivery.yml`),在 Actions 页面手动触发即可,约 30 秒跑完。它用假数据在真实 runner 上把钉钉和邮件两条链路各走一遍,不调用 Claude、不消耗订阅额度。

换了钉钉机器人、改了 Gmail 密码、或者日报没收到想先排除投递环节时,先跑它。

## 本地调试

两个投递脚本都能在本机单独跑:

```bash
# 钉钉(凭据从环境变量读)
DINGTALK_WEBHOOK=... DINGTALK_SECRET=... python3 scripts/send_dingtalk.py "标题" reports/2026-08-10.dingtalk.md

# 邮件(优先读环境变量,回落到 ~/.config/ai-daily-radar/gmail_app_password)
bash scripts/send_email.sh "标题" reports/2026-08-10.md
```

## 目录结构

```
ai-daily-radar/
├── .github/workflows/daily-radar.yml  # 定时任务定义
├── workers/radar-watchdog/            # Cloudflare Worker:主触发通道 + 08:40 哨兵
├── prompts/daily-radar.md             # 日报生成提示词(受版本管理)
├── sources.md                         # 43 个信息源清单 + 筛选标准
├── scripts/
│   ├── send_dingtalk.py               # 钉钉加签推送
│   ├── send_email.sh                  # Gmail SMTP 直发
│   ├── md2html.py                     # Markdown → HTML 邮件转换器(零依赖)
│   ├── radar_watchdog.sh              # 看门狗的 shell 版(备用通道 / 命令行工具)
│   └── install-launchd.sh             # 把 shell 版装成 launchd 定时任务(默认不装)
├── docs/superpowers/specs/            # 设计文档
└── reports/                           # 每日日报存档
    └── appstore-snapshot.json         # App Store 榜单快照,用于对比找新进榜应用
```
