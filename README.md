# AI Daily Radar 每日 AI 情报雷达

每天早上自动扫描 19 个国内外信息源,由 AI 筛选出**值得做的机会、赚钱案例、产品灵感**,英文信号自动翻译成中文,汇总成一份日报,推送到钉钉群和邮箱。

**运行在 GitHub Actions 上,不依赖本机开机。**

## 产出与投递

| 产出 | 位置 |
|---|---|
| 日报全文 | `reports/YYYY-MM-DD.md`(自动提交回仓库) |
| 钉钉群版 | `reports/YYYY-MM-DD.dingtalk.md`(凝练版,推送用) |
| 钉钉群消息 | TL;DR + 各条目标题 + 原始链接,每条都可点进原文 |
| 邮件 | HTML 渲染版,直发 nengzongtan@gmail.com |

## 运行时间

日报目标送达时间是**北京 08:30 前后**。

**GitHub 的定时任务并不可靠**——官方明确说明,高负载期定时触发会被延迟,甚至**直接丢弃**。而午夜 UTC(正好是北京早上 8 点前后)是全球 cron 最拥堵的时段。所以这里用了两道 cron 加一个幂等开关:

| | 时间 | 作用 |
|---|---|---|
| 主 | `55 23 * * *` = 北京 **07:55** 起跑 | 压在午夜 UTC 高峰之前,正常情况 08:15–08:25 送达 |
| 备 | `45 0 * * *` = 北京 **08:45** 起跑 | 仅当主触发被丢弃、今天还没出日报时才执行 |

备用触发靠「判断今天是否已生成」这一步兜底:定时触发时如果 `reports/YYYY-MM-DD.md` 已在仓库里,整个流程直接跳过,所以两次都成功也不会重复推送。**手动触发不受此限制**,方便随时补跑。

想改时间的话,记得 cron 用的是 UTC(北京时间减 8 小时),要把约 15 分钟运行时长算进去,并且尽量避开整点和午夜 UTC。

也可以在 GitHub 仓库的 Actions 页面手动点 **Run workflow** 立即触发一次。

## 工作原理

```
.github/workflows/daily-radar.yml
  ├─ 1. checkout 仓库
  ├─ 2. claude-code-action 执行 prompts/daily-radar.md
  │     抓 19 个源 → AI 筛选 → 写日报全文 + 钉钉版 → 更新榜单快照
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

仓库里有一个 **投递链路自检** workflow(`.github/workflows/test-delivery.yml`),在 Actions 页面手动触发即可,约 30 秒跑完。它用假数据在真实 runner 上把钉钉和邮件两条链路各走一遍,不调用 Claude、不消耗订阅额度。

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
├── prompts/daily-radar.md             # 日报生成提示词(受版本管理)
├── sources.md                         # 19 个信息源清单 + 筛选标准
├── scripts/
│   ├── send_dingtalk.py               # 钉钉加签推送
│   ├── send_email.sh                  # Gmail SMTP 直发
│   └── md2html.py                     # Markdown → HTML 邮件转换器(零依赖)
├── docs/superpowers/specs/            # 设计文档
└── reports/                           # 每日日报存档
    └── appstore-snapshot.json         # App Store 榜单快照,用于对比找新进榜应用
```
