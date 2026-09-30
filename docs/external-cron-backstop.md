# 外部兜底通道:不依赖 Cloudflare 调度器的第二条触发链

## 为什么需要这条通道

2026-09-09 日报没有按时进群。事后查下来是这样:

| 检查项 | 结果 |
| :--- | :--- |
| Worker 的 4 道 cron 触发器 | 都在,`50 23`/`30 0`/`40 0`/`10 1`,最后修改停在 2026-09-06 |
| 脚本版本 | 完好,当前生效的还是 09-06 那次 wrangler 部署,100% 流量 |
| 密钥 | `CONTROL_KEY`/`DINGTALK_SECRET`/`DINGTALK_WEBHOOK`/`GITHUB_TOKEN` 四个都在 |
| handlers | `["scheduled","fetch"]` |
| 账号 | 正常,没超额,静默期间总共就几个请求 |
| **实际调用** | **2026-09-08T10:00:44Z 之后归零** |

Cloudflare 的调用记录(`workersInvocationsAdaptive`):

```
09-08T00:30:40Z  08:30 准点投递   ✅
09-08T00:40:38Z  08:40 哨兵一     ✅
09-08T01:10:42Z  09:10 哨兵二     ✅   ← 最后一次正常的 cron
────────────── 之后完全静默 ──────────────
09-08T23:50      07:50 起跑生成   ❌ 没被调起
09-09T00:30      08:30 准点投递   ❌ 没被调起
09-09T00:40      08:40 哨兵一     ❌ 没被调起
09-09T01:10      09:10 哨兵二     ❌ 没被调起
```

**错误数 0、调用数 0** —— 不是跑起来报错,是压根没被触发。触发器记录还在 API 里,
调度侧却丢了注册。更早还有一次征兆:09-06T23:50 那道也漏过一次,那天 09-07 的日报
同样是人工 dispatch 补的。

最要命的是**告警本身也挂在这个 Worker 上**。看门狗设计的时候特意把告警走钉钉、
不走「再 dispatch 一个告警 workflow」,理由是"被监控的东西不能是告警的前提"——
但这次栽的恰恰是调度器,调度器一哑,哨兵和告警跟着一起哑,外面一点动静都没有。
所以监控这套东西的调度器,必须来自 Cloudflare 之外。

## 设计

Worker 的 `fetch` handler 早就留好了入口(`src/index.js` 末尾),
四条路径和四道 cron 一一对应:

| 路径 | 等价于 |
| :--- | :--- |
| `/run/generate` | 07:50 起跑生成 |
| `/run/deliver` | 08:30 准点投递 |
| `/run/sentinel` | 08:40 哨兵一 |
| `/run/sentinel-last` | 09:10 哨兵二 |

外部定时服务把这四条各打一次,时间比 Cloudflare 的 cron **晚 2 分钟**。

**为什么敢和 Cloudflare 的 cron 撞车:四个分支自己都是幂等的。**

- `runGenerate` 先查远端有没有 `reports/<今天>.md`,再查生成流水线有没有 run 在跑/排队,
  任一命中就直接返回,不 dispatch;
- `runDeliver` 先查 `state/delivered/<今天>.txt` 投递回执,再查投递流水线有没有 run 在跑,
  任一命中就返回;
- `runSentinel` 同样先查回执、再查在跑的投递 run。

Cloudflare 的 cron 正常时,它在 T 时刻已经把 run 建出来了,外部在 T+2min 打进来只会
查到「已经有 run 在跑」然后跳过。**不会重复往公司群推。** 2 分钟的间隔足够 GitHub 的
run 出现在 API 里(实测秒级)。

**外部通道只补救不告警。** 告警每天最多一条(见 README「排查投递问题」),Worker 自己没地方记
「告过警了」,外部 09:12 那道要是也告警,就和 Cloudflare 09:10 那道各来一条。所以兜底告警只由
Cloudflare 自己的 cron 发;代价是 Cloudflare 调度器哑掉、同时 GitHub 那边也出事的那天收不到这条。

**run 秒红的情况。** 投递 run 16 秒就失败时,T+2min 打进来已经查不到在跑的 run 了,早先会再起一道
(2026-09-29/30 钉钉额度用完那两天就是这样,日报邮件一天两封)。现在投递流水线推钉钉失败会留
`state/delivery-failed/<日期>.txt`,Worker 和投递流水线的守卫看到它都不再重投。

**为什么四条都镜像,而不是只留一道哨兵。**
只挂 08:42 一道哨兵的话,Cloudflare 全哑的那天生成要 08:42 才起跑,跑完 ~08:57,
再等 09:12 那道才投出去——迟到 42 分钟。四条全镜像的话,Cloudflare 全哑当天是:
07:52 起跑 → ~08:07 跑完 → 08:32 投递,**只迟到 2 分钟**。

## 配置步骤(cron-job.org)

选它是因为免费、支持自定义请求头、支持时区、任务失败能发邮件。
换成 EasyCron / Val Town 之类同理,只要能按点发 HTTP 请求就行。

### 1. 注册并新建 4 个 Cronjob

到 https://cron-job.org 注册,`Cronjobs` → `Create cronjob`,建四个:

| 任务名 | URL | 北京时间 | UTC |
| :--- | :--- | :--- | :--- |
| radar-generate | `https://ai-daily-radar-watchdog.radar-watchdog.workers.dev/run/generate` | 07:52 | 23:52 |
| radar-deliver | `https://ai-daily-radar-watchdog.radar-watchdog.workers.dev/run/deliver` | 08:32 | 00:32 |
| radar-sentinel | `https://ai-daily-radar-watchdog.radar-watchdog.workers.dev/run/sentinel` | 08:42 | 00:42 |
| radar-sentinel-last | `https://ai-daily-radar-watchdog.radar-watchdog.workers.dev/run/sentinel-last` | 09:12 | 01:12 |

每个任务里:

- **COMMON / Execution schedule**:选 `Every day at`,时分按上表的北京时间填。
- **ADVANCED / Time zone**:设成 `Asia/Shanghai`。**这个是按任务设的,不是账号级的**,
  四个任务都要单独设一遍。新建时默认可能是 `Asia/Singapore`——两者同为 UTC+8 且都没有
  夏令时,功能上等价,但设成 Shanghai 才和本文档、和 wrangler.toml 的注释对得上。
- **ADVANCED / Headers**:加一个请求头
  - Key:`X-Control-Key`
  - Value:本机 `~/.config/ai-daily-radar/worker_control_key` 里那一行
- **COMMON / Notify me when...**:打开「execution of the cronjob fails」。
  这是这条通道自己的哨兵。
- **Request method** 保持 `GET`,**Timeout** 保持 30 秒即可(Worker 只是打几个
  GitHub API 再 dispatch,秒级返回)。

> ⚠️ 密钥走请求头,不要拼在 URL 的 `?key=` 上。拼在 URL 里的话,它会留在
> cron-job.org 的任务配置、执行历史,以及 Cloudflare 的请求日志里。
> 代码两种都认(`?key=` 是给手工 curl 留的),但配置到第三方服务时一律用请求头。

> 📌 **当前状态**:四个任务已建好,请求头的 Key 都填了 `X-Control-Key`,
> 但 Value 是占位符 `PASTE_CONTROL_KEY_HERE`。**四个都要手工替换成真实密钥**
> (在任务的 EDIT → ADVANCED → Headers 里改,改完点 SAVE),否则 Worker 一律返回 404。
> 密钥不放进本文档也不放进仓库,只在 `~/.config/ai-daily-radar/worker_control_key`。

> ⚠️ **建完一定要回头逐个复核**。cron-job.org 的时分下拉是浮层,下拉还开着的时候
> 点到别处会把选中值改掉,而且列表页不会提示。实测发生过:`radar-deliver` 建的时候
> 明明是 08:32,回到列表却变成了 08:30——而 08:30 恰好和 Cloudflare 自己那道
> cron 撞在同一秒,那是唯一可能造成重复推送的情况。逐个点进 EDIT 核对
> 「时分 + Headers + Time zone + Enable job + 失败告警」五项,别只信列表页那一列时间。

### 2. 验证

建完之后手工打一次确认通:

```bash
KEY=$(cat ~/.config/ai-daily-radar/worker_control_key | tr -d '\n')
BASE=https://ai-daily-radar-watchdog.radar-watchdog.workers.dev

# 看当前状态(只读,不触发任何东西)
curl -s -H "X-Control-Key: $KEY" "$BASE/status"

# 验 GitHub 令牌的 Actions: Write 权限(用不存在的 ref 探,不会真建出 run)
curl -s -H "X-Control-Key: $KEY" "$BASE/probe"
```

`/status` 返回今天的 `reportSize`/`receiptSize`,`/probe` 两条都应该是
`"ok": true, "status": 422`。

在 cron-job.org 上对每个任务点一次 `Run now`,应该收到一行中文说明,
且因为今天已经投过,内容会是「已有投递回执,今天已经投过,不重复投递」之类的跳过说明——
**这正是幂等在起作用**,不会真的往群里再推一遍。

### 3. 第二天早上确认

看 GitHub Actions 的 run 列表,判断是哪条通道起的作用:

- Cloudflare 恢复了:run 出现在 23:50 / 00:30 附近(UTC)
- Cloudflare 还哑着,外部通道顶上了:run 出现在 23:52 / 00:32 附近(UTC)

两种都算日报正常送达。要确认 Cloudflare 那条到底活没活,查它的调用记录:

```bash
CFG=~/Library/Preferences/.wrangler/config/default.toml
TOK=$(grep '^oauth_token' "$CFG" | sed -E 's/.*= *"([^"]*)".*/\1/')
ACCT=c5c39151bf168660d753ffe62e8755d8
START=$(date -u -v-2d +%Y-%m-%dT%H:%M:%SZ); END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > /tmp/q.json <<JSON
{"query":"query{viewer{accounts(filter:{accountTag:\"$ACCT\"}){workersInvocationsAdaptive(limit:200, filter:{datetime_geq:\"$START\", datetime_leq:\"$END\", scriptName:\"ai-daily-radar-watchdog\"}, orderBy:[datetime_ASC]){sum{requests errors}dimensions{datetime status}}}}}"}
JSON
curl -s -X POST -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  --data @/tmp/q.json https://api.cloudflare.com/client/v4/graphql | python3 -m json.tool
```

(access token 过期的话,先在 `workers/radar-watchdog/` 下跑一次
`npx wrangler whoami`,它会用 refresh token 自动续期并回写配置。)

## 维护

**改时间的话四个地方要一起改**,漏一个就会出现两条通道时间对不上、
互相不认账的情况:

1. `workers/radar-watchdog/wrangler.toml` 的 `[triggers] crons`
2. `workers/radar-watchdog/src/index.js` 顶部的 `CRON_*` 常量
   (对不上的话 `modeForCron` 会退化成哨兵处理并打日志)
3. cron-job.org 上那四个任务(保持比 Cloudflare 晚 2 分钟)
4. 本文档上面那张表

`.github/workflows/` 里那两道 GitHub cron(生成 09:00 / 投递 09:30)是**第三层**兜底,
留着别删,但也别指望它准点——GitHub 的 schedule 实测能漂 4~5 小时,
投递那条为此加了「过了 10:00 就不推」的闸。
