# AI Daily Radar 每日 AI 情报雷达

每天早上自动扫描 40+ 个国内外信息源(国内媒体社区、海外社区、顶级 AI 实验室官方、一线科技媒体、楼宇/设施管理/能源垂直行业、设计与体验),由 AI 从公司业务视角筛选出**行业动向、技术与案例、产品灵感**,英文信号自动翻译成中文,汇总成一份日报,推送到钉钉群和邮箱。

设计源是周更的,所以日报里的 **🎨 设计动态**栏目只在有新刊的那一两天出现,其余日子整节省略。

**运行在 GitHub Actions 上,不依赖本机开机。**

## 产出与投递

| 产出 | 位置 |
|---|---|
| 日报全文 | `reports/YYYY-MM-DD.md`(自动提交回仓库) |
| 钉钉群版 | `reports/YYYY-MM-DD.dingtalk.md`(凝练版,推送用) |
| 钉钉群消息 | TL;DR + 各条目标题 + 原始链接,每条都可点进原文 |
| 邮件 | HTML 渲染版,直发 nengzongtan@gmail.com |

## 运行时间

日报**北京 08:30 准点**送达。

**生成和投递是两条独立的流水线**,由仓库外面的 **Cloudflare Worker** 按点 `workflow_dispatch` 打进来:

| 通道 | 时间(北京) | 角色 |
|---|---|---|
| Cloudflare cron `50 23 * * *` | **07:50** | 起跑生成:写 `reports/*.md` + 提交存档,**一条消息都不发** |
| Cloudflare cron `30 0 * * *` | **08:30** | **准点投递**:推钉钉 + 发邮件 + 写投递回执 ← 这一道决定日报几点进群 |
| Cloudflare cron `40 0 * * *` | **08:40** | 哨兵一:没有回执 → 缺什么补什么(只补不告警) |
| Cloudflare cron `10 1 * * *` | **09:10** | 哨兵二:最后一次补救(给「08:40 才补跑生成」留出完成时间);到这时还没进群、GitHub 那边也没告过警,就告警一次 |
| GitHub cron `0 1 * * *` | **09:00** | 生成的末端兜底:Cloudflare 整条通道挂掉时才真正干活 |
| GitHub cron `30 1 * * *` | **09:30** | 投递的末端兜底;漂到 10:00 之后会拒投并告警,不往群里推「中午的早报」 |

**为什么要拆成两条。** 合在一起时送达时刻 = 起跑时刻 + 生成耗时,生成快慢直接把送达时间带跑;
想钉死 08:30 就只能在 runner 上 `sleep` 等点,而那正是 2026-08-30 烧穿 Actions 月度额度的原因。
拆开之后两边都不用将就:生成想跑多久跑多久,投递永远 08:30,只跑几十秒。

> **踩过的坑(2026-08-31 ~ 09-06)**:那次删掉 `sleep` 时,把准点机制一起删掉了,
> 送达时刻退化成「07:50 + 生成耗时」。实测生成只要 8~13 分钟,于是日报连着一周
> **每天 08:02~08:03 就发出去了**,比约定的 08:30 早半小时。
> 同期 README 里的目标也被悄悄改写成「08:30 **前**送达」,让这个偏差看起来像达标。
> 这一版把 08:30 拿回来,并且不再用 runner 分钟去买。

**「是否已送达」看的是投递回执,不是日报文件。** 拆分之后 `reports/<今天>.md` 存在只证明**生成完了**,
不代表进群了。投递流水线在钉钉推送成功后立刻提交 `state/delivered/<今天>.txt`,
哨兵和幂等守卫都以它为准。

**GitHub 的定时任务不准时**,所以准点性不能靠它:官方说明高负载期会延迟甚至直接丢弃,
本仓库实测延迟 1h05m、1h07m、2h23m,08-27 三道 cron 全部漂到 4~5 小时之后,08-28 一道都没触发。
(2026-09 实测那道 `0 1 * * *` 的兜底 cron 每天 13:00~13:50 才触发,漂了 4~5 小时,
因为有幂等守卫所以秒退无害。)`workflow_dispatch` 是即时的、从没漂过,所以触发的决定权放在
GitHub 外面(见下)。GitHub 那两道 cron 留着只为「Cloudflare 也挂了」。

两条流水线当天都只会真正执行一次。幂等守卫查的是**远端 main 的最新状态**
(而不是 checkout 出来的工作区——触发被延迟后 checkout 的是旧 SHA,看不到刚推上去的文件):
生成看 `reports/<今天>.md`,投递看 `state/delivered/<今天>.txt`。
生成的守卫**手动触发不受限**(方便随时补跑);投递的守卫**连手动触发也拦**——
重复投递的代价是往公司群重推一遍日报,真要重投得在 Run workflow 时勾上 `force`。

也可以在 GitHub 仓库的 Actions 页面手动点 **Run workflow** 立即触发一次:
`AI Daily Radar 生成` 补生成,`AI Daily Radar 投递` 补投递。

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

现在准点性由「投递单独成一条流水线 + Worker 在 08:30 触发它」负责,workflow 里没有任何等待步骤:
生成 run 约 8~13 分钟,投递 run 几十秒,月耗约 450 分钟,稳在免费额度内。
`timeout-minutes: 60` / `10` 是单次跑飞时的计费封顶。

**所以:不要再加 cron,不要把起跑时间往早挪,不要在 workflow 里 sleep。**
要改送达时间,改 `workers/radar-watchdog/wrangler.toml` 里的**投递** cron `30 0 * * *`
(改完 `index.js` 顶部的 `CRON_DELIVER` 常量必须逐字跟着改,再 `npx wrangler deploy`)。
起跑那道 `50 23 * * *` 只决定生成什么时候开始,和送达时间无关——除非生成慢到 08:30 还没跑完。

额度用完了怎么办:等下个月 1 号自动重置,或去 Settings → Billing 设 spending limit,
或把仓库改成 public(公开仓库 Actions 免费无限,但 `reports/` 是公司业务内容,慎重)。

### 外部看门狗(主触发通道)

2026-08-27/28 上面这套余量被击穿了:08-27 三道 cron 全部漂到 4~5 小时之后(`50 21` 那道 02:12 UTC 才触发),08-28 一道都没触发。两天的日报都是人工发现没收到、手动补跑的。往前提起跑时间救不了 08-28 那种情况——那不是触发晚了,是压根没触发。

`workflow_dispatch` 是即时的,从没漂过。所以触发的决定权移到 GitHub 外面,由一个 Cloudflare Worker 按点去 dispatch:

| Cloudflare cron (UTC) | 北京时间 | 行为 |
|---|---|---|
| `50 23 * * *` | **07:50** | 没有今天的日报、且没有生成 run 在跑 → dispatch 生成 |
| `30 0 * * *` | **08:30** | 没有回执、没有投递 run 在跑、日报已就绪 → dispatch 投递 |
| `40 0 * * *` | **08:40** | 哨兵一:没有回执 → 缺什么补什么(日报在就补投,日报不在就补生成) |
| `10 1 * * *` | **09:10** | 哨兵二:最后一次补救;还没进群、GitHub 那边也没告过警的话,告警一次并说死「需要手动投递」 |

哨兵的补救是**分情况**的,这点比旧版重要:日报在、回执不在 = 投递环节出了问题 → 补投;
两个都不在 = 生成环节出了问题 → 补生成,并由下一道哨兵接着补投。
旧版只有「有没有日报」一个信号,分不出这两种。

代码在 `workers/radar-watchdog/`。告警走钉钉直发,而不是「再 dispatch 一个告警 workflow」——**被监控的东西不能是告警的前提**,否则 Actions 真出问题时告警会跟着一起哑掉。

**告警每天最多一条**(2026-09-30 起)。原则上由 GitHub 那边的流水线发——它们知道是哪一步出错,钉钉挂了能改发邮件,发完留一份 `state/alerted/<日期>.txt`,当天后面谁看到都不再发。Worker 前几道只补救不告警,只在 09:10 最后一道、且 GitHub 那边一声没吭时兜底告警一次;外部兜底通道打进来的 `/run/*` 一律不告警(Worker 没地方记「告过警了」,两边都发就是 09:10、09:12 各来一条)。

GitHub 自己那两道 cron(生成 09:00 / 投递 09:30)**保留**做末端兜底:Cloudflare 也挂了的话它们仍可能跑起来,而 schedule run 会在各自的幂等守卫处秒退,不会重复推送。投递那道还多一道闸——GitHub 的 schedule 实测能漂 4~5 小时,漂到 10:00 之后它会拒投并告警,不往公司群推一份「中午的早报」。

看门狗自己也不会造成重复推送——dispatch 前会检查对应流水线有没有 run 正在跑/排队(比如你刚手动 Run 过一次)。查不到状态时(网络不通、token 过期)一律**不动作**:多推一次日报到公司群比晚到一次更难收场,何况还有 cron 兜底和两道哨兵复查。

#### 外部兜底通道(第二条触发链)

2026-09-09 这套又栽了一次,栽法和 08-27/28 不一样:**Cloudflare 的调度器自己哑了**。
触发器在 API 里查得到、脚本和密钥完好、账号没超额,但从 09-08T10:00Z 之后
Worker 的调用数归零——四道 cron 一道都没发车,错误数也是 0(不是跑起来报错,是没被触发)。
当天日报靠人工补跑。09-06T23:50 那道更早就漏过一次,当时没被当回事。

上面那句「被监控的东西不能是告警的前提」这次被打脸了:告警确实绕开了 Actions,
却仍然挂在这个 Worker 上。**调度器一哑,哨兵和告警跟着一起哑**,外面一点动静都没有。

所以现在多了一条不依赖 Cloudflare 调度器的外部通道:外部定时服务按点打
Worker 的 `/run/generate`、`/run/deliver`、`/run/sentinel`、`/run/sentinel-last`
(比 Cloudflare 的 cron 晚 2 分钟)。四个分支本来就都是幂等的——dispatch 前查日报、
查回执、查在跑的 run——所以和 Cloudflare 的 cron 撞车不会重复往公司群推。

配置步骤、时间表、验证方法和维护注意见 [docs/external-cron-backstop.md](docs/external-cron-backstop.md)。
**改任何一边的时间,四个地方要一起改**(wrangler.toml、index.js 的 `CRON_*` 常量、
外部定时任务、那份文档的表格)。

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

curl "$U/status?key=$KEY"             # 只读:日报字节数、投递回执字节数、两条线在跑的 run 数
curl "$U/probe?key=$KEY"              # 验 token 对两条流水线有没有 Actions: Write(422 = 有)
curl "$U/run/generate?key=$KEY"       # 走一遍起跑决策
curl "$U/run/deliver?key=$KEY"        # 走一遍投递决策  ⚠️ 真会往公司群推
curl "$U/run/sentinel?key=$KEY"       # 走一遍查岗决策
curl "$U/run/sentinel-last?key=$KEY"  # 走一遍「最后一道哨兵」决策
```

换了 token 之后用 `/probe` 确认权限,**别用真触发去试**——真 dispatch 一次的代价是往公司群重推一遍当天日报。探针故意拿一个不存在的 ref 去 dispatch,403 = 没权限、422 = 有权限但 ref 不对,不会真的建出 run。

**PAT 过期这条通道会无声失效**,所以建议建 token 时选 No expiration。真过期了,09:10 那道哨兵会因为查不到状态而发「看门狗异常」告警,不会静默。

#### 备用:本机 launchd

`scripts/radar_watchdog.sh` 是同一套逻辑的 shell 版(四个模式:`generate` / `deliver` / `sentinel` / `sentinel-last`),`scripts/install-launchd.sh` 把它按同一张时刻表装成本机定时任务。**当前未安装**(切到 Worker 时已卸载)——两边时刻表一样,同时跑会各自看到「还没投递」而各 dispatch 一次,往公司群重推两遍日报。**两条通道只能开一条。**

shell 版读的是本机 `gh` 的登录凭据,不用 PAT;告警发 macOS 本地通知,想同时进手机就把钉钉凭据写到 `~/.config/ai-daily-radar/env`(`DINGTALK_WEBHOOK=` / `DINGTALK_SECRET=`)。

Worker 那边出问题时可以临时切回来:

```bash
bash scripts/install-launchd.sh                                            # 启用
launchctl bootout gui/$(id -u)/com.nengzong.ai-daily-radar.{generate,deliver,sentinel,sentinel-last}   # 停用
```

这个 shell 版也能直接当命令行工具用,不依赖 launchd:

```bash
RADAR_DRY_RUN=1 ./scripts/radar_watchdog.sh deliver          # 只打印决策,不真的触发
RADAR_DATE=2026-08-27 ./scripts/radar_watchdog.sh sentinel   # 换个日期查/补跑
```

## 工作原理

```
07:50  .github/workflows/daily-radar.yml    「AI Daily Radar 生成」
         ├─ 1. checkout 仓库
         ├─ 2. 幂等守卫:远端已有今天的日报就秒退
         ├─ 3. claude-code-action 执行 prompts/daily-radar.md
         │     抓 40+ 个源 → AI 筛选 → 写日报全文 + 钉钉版 → 更新榜单快照
         ├─ 4. 校验两个报告文件存在且非空(不满足则中止,绝不让空日报进群)
         └─ 5. 提交日报回仓库  ← push 完成 = 「今天的日报已就绪」

08:30  .github/workflows/daily-deliver.yml  「AI Daily Radar 投递」
         ├─ 1. checkout main 的最新状态
         ├─ 2. 幂等守卫:已有今天的投递回执就跳过(force 才能覆盖)
         ├─ 3. 校验日报文件在且非空
         ├─ 4. 推送钉钉(scripts/send_dingtalk.py)
         ├─ 5. 写投递回执 state/delivered/<今天>.txt 并提交  ← 排在发邮件前面
         └─ 6. 发送邮件(scripts/send_email.sh,钉钉失败也照发)
```

**回执为什么排在发邮件前面。** 群里已经收到、而回执还没落盘的这段窗口里,哨兵会判定「未送达」
并补投一次——那就是往公司群重推。所以钉钉一成功就立刻写回执,把窗口压到最短。
反过来邮件失败不该阻止回执落盘:邮件是发给自己的,补投时重发一封无所谓,
为此让哨兵再往群里推一遍就不划算了。

**投递不由 AI 负责。** Claude 只生成文件,推送和发信是投递流水线里确定性的步骤——这样任何一步失败都会让 workflow 红灯并告警(钉钉优先,钉钉失败改发邮件),而不会出现「AI 以为发了其实没发」的情况。

## 配置(GitHub Secrets)

在仓库 Settings → Secrets and variables → Actions 里配置四个:

| Secret | 来源 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio 生成的 Gemini API 密钥 |
| `DINGTALK_WEBHOOK` | 钉钉群 → 群设置 → 机器人 → 添加自定义机器人,复制 Webhook 地址 |
| `DINGTALK_SECRET` | 添加机器人时勾选「加签」,复制 `SEC` 开头的密钥 |
| `GMAIL_APP_PASSWORD` | Google [应用专用密码页面](https://myaccount.google.com/apppasswords)生成的 16 位密码 |

钉钉机器人的安全设置**必须用「加签」**,不能用 IP 白名单——Actions runner 的出口 IP 是动态的。

## 如何调整

- **改信息源**:编辑 [sources.md](sources.md),每次运行都会重新读取
- **改筛选标准 / 日报结构 / 钉钉版格式**:编辑 [prompts/daily-radar.md](prompts/daily-radar.md)
- **改送达时间**:改 [workers/radar-watchdog/wrangler.toml](workers/radar-watchdog/wrangler.toml) 里的**投递** cron `30 0 * * *`(UTC,北京时间减 8 小时),`src/index.js` 顶部的 `CRON_DELIVER` 常量必须逐字跟着改,然后 `npx wrangler deploy`。**别改成在 workflow 里等**,见「不要在 runner 上挂机等时间」
- **改生成起跑时间**:同一个文件里的 `50 23 * * *` / `CRON_GENERATE`。它只决定生成什么时候开始,和送达时间无关——只要在 08:30 前跑完就行
- **暂停**:在 GitHub 仓库 Actions 页面点 workflow → 右上角 `···` → Disable workflow(**两条都要点**)

## 排查投递问题

**失败会主动告警,每天最多一条**:任何一步出错,workflow 都会发一条带运行日志链接的告警,不用靠「今天没收到日报」事后察觉。告警先推钉钉;钉钉推不出去(比如 2026-09-29/30 那两天企业的 webhook 月度额度用完,`errcode 90030`)就改发邮件。当天已经告过警(`state/alerted/<日期>.txt`)的话,后面的告警一律不再发。

**钉钉推送失败之后当天不再自动重投。** 投递流水线会留一份 `state/delivery-failed/<日期>.txt`,外部兜底、哨兵、兜底 cron 看到它都不再起投递——钉钉那边多半是额度/配置问题,重投只会再失败一次、再发一封日报邮件(那两天就是每天收到两封)。问题解决后想补推:Actions → AI Daily Radar 投递 → Run workflow,**勾上 force**。

这条告警覆盖不了「cron 全被 GitHub 丢弃」的情况——那种情况下 workflow 压根没启动,自然也没法告警。这个盲区由 Worker 的 **08:40 / 09:10 两道哨兵**补上(见「外部看门狗」):它们查的是远端有没有今天的**投递回执**,不关心 workflow 有没有启动,所以「没跑」「跑失败」「生成了但没投出去」都能兜住。

哨兵也没响、日报也没来,说明 Worker 这条通道也断了。`npx wrangler tail` 看看它有没有在跑;
要补救先看 `reports/<今天>.md` 在不在:在的话手动 Run 一次 **AI Daily Radar 投递** 就行,不在的话先 Run **AI Daily Radar 生成**。

**手动 Run 也失败、而且几秒就红**:去 Actions 页面看那道 run 的 annotation。若是
`The job was not started because recent account payments have failed or your spending limit needs to be increased`,
那不是代码问题,是 GitHub Actions 的月度分钟额度用完了,见「不要在 runner 上挂机等时间」。
这种失败 workflow 自己告不了警——job 没启动,告警步骤跑不到;由 Worker 09:10 那道哨兵兜底告警一次(Cloudflare 调度器也哑了的那天就没有)。
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
├── .github/workflows/
│   ├── daily-radar.yml                # 生成:抓源 + 写日报 + 提交存档(不发消息)
│   └── daily-deliver.yml              # 投递:08:30 推钉钉 + 发邮件 + 写回执
├── workers/radar-watchdog/            # Cloudflare Worker:四道 cron(起跑/投递/两道哨兵)
├── prompts/daily-radar.md             # 日报生成提示词(受版本管理)
├── sources.md                         # 45 个信息源清单 + 筛选标准
├── scripts/
│   ├── send_dingtalk.py               # 钉钉加签推送
│   ├── send_email.sh                  # Gmail SMTP 直发
│   ├── md2html.py                     # Markdown → HTML 邮件转换器(零依赖)
│   ├── radar_watchdog.sh              # 看门狗的 shell 版(备用通道 / 命令行工具)
│   └── install-launchd.sh             # 把 shell 版装成 launchd 定时任务(默认不装)
├── docs/superpowers/specs/            # 设计文档
├── reports/                           # 每日日报存档
│   └── appstore-snapshot.json         # App Store 榜单快照,用于对比找新进榜应用
└── state/delivered/                   # 每日投递回执,「是否已送达」以此为准
```
