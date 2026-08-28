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

**GitHub 的定时任务不准时。** 官方说明高负载期会延迟甚至直接丢弃,本仓库实测(2026-08-12/13)延迟分别是 1h05m、1h07m、2h23m,而且三次触发机会里丢了一次。

早期版本把起跑时间卡在 07:55(期望送达前 15 分钟),结果每次定时触发都迟到一到两小时;等它真正跑起来时,人已经等不及手动跑过一遍了,幂等开关便判定「今天已出过日报」直接跳过——于是**定时任务从来没有真正产出过一份日报**,看起来就像压根没自动运行。

现在的策略是**大幅提前起跑,用时间余量吃掉延迟**,再排三道 cron,任意一道活下来就够。早到无害,迟到才是问题:

| 时间 | 正常送达 | 延迟 2.5 小时仍可送达 |
|---|---|---|
| `50 21 * * *` = 北京 **05:50** 起跑 | 06:10 | 08:40 |
| `50 22 * * *` = 北京 **06:50** 起跑 | 07:10 | 09:40 |
| `50 23 * * *` = 北京 **07:50** 起跑 | 08:10 | 10:40 |

当天只会真正执行一次。「判断今天是否已生成」这一步会去查**远端 main 的最新状态**(而不是 checkout 出来的工作区——几道 cron 被延迟后可能挤在一起触发,后触发的那次 checkout 的是旧 SHA,看不到刚推上去的日报),已经有今天的日报就秒退。**手动触发不受此限制**,方便随时补跑。

想改时间的话,记得 cron 用的是 UTC(北京时间减 8 小时),除了算上约 15 分钟运行时长,更要**留足至少 2 小时的延迟余量**。

也可以在 GitHub 仓库的 Actions 页面手动点 **Run workflow** 立即触发一次。

### 外部看门狗(主触发通道)

2026-08-27/28 上面这套余量被击穿了:08-27 三道 cron 全部漂到 4~5 小时之后(`50 21` 那道 02:12 UTC 才触发),08-28 一道都没触发。两天的日报都是人工发现没收到、手动补跑的。往前提起跑时间救不了 08-28 那种情况——那不是触发晚了,是压根没触发。

`workflow_dispatch` 是即时的,从没漂过。所以起跑的决定权移到 GitHub 外面,由一个 Cloudflare Worker 按点去 dispatch:

| Cloudflare cron (UTC) | 北京时间 | 行为 |
|---|---|---|
| `0 22 * * *` | **06:00** | 远端还没有今天的日报、且没有 run 在跑 → dispatch 起跑 |
| `40 0 * * *` | **08:40** | 还没送达 → 钉钉告警 + dispatch 补跑 |

代码在 `workers/radar-watchdog/`。告警走钉钉直发,而不是「再 dispatch 一个告警 workflow」——**被监控的东西不能是告警的前提**,否则 Actions 真出问题时告警会跟着一起哑掉。

GitHub 那三道 cron **原样保留**做兜底:Cloudflare 也挂了的话它们仍可能跑起来,而后触发的 schedule run 会在「判断今天是否已生成」处秒退,不会重复推送。

看门狗自己也不会造成重复推送——dispatch 前会检查有没有 run 正在跑/排队(正常日子里 05:50 那道 cron 到 06:00 时往往已经在跑了)。查不到状态时(网络不通、token 过期)一律**不动作**:多推一次日报到公司群比晚到一次更难收场,何况还有 cron 兜底和 08:40 的哨兵复查。

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
- **改时间**:编辑 [.github/workflows/daily-radar.yml](.github/workflows/daily-radar.yml) 里的 cron(注意是 UTC,北京时间减 8 小时)
- **暂停**:在 GitHub 仓库 Actions 页面点 workflow → 右上角 `···` → Disable workflow

## 排查投递问题

**失败会主动告警**:任何一步出错,workflow 都会往钉钉群推一条带运行日志链接的告警,不用靠「今天没收到日报」事后察觉。收到告警后去 Actions 页面手动 Run workflow 即可补跑。

这条告警覆盖不了「cron 全被 GitHub 丢弃」的情况——那种情况下 workflow 压根没启动,自然也没法告警。这个盲区由 Worker 的 **08:40 哨兵**补上(见「外部看门狗」):它查的是远端有没有今天的日报,不关心 workflow 有没有启动,所以「没跑」和「跑失败」都能兜住。

哨兵也没响、日报也没来,说明 Worker 这条通道也断了。`npx wrangler tail` 看看它有没有在跑,再去 Actions 页面手动 Run workflow 补跑。

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
