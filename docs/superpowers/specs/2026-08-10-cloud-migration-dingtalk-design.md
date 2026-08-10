# AI Daily Radar 云端化 + 钉钉推送 设计文档

日期：2026-08-10

## 背景与问题

现有的日报任务以 Claude Code 本机定时任务（`~/.claude/scheduled-tasks/ai-daily-radar/SKILL.md`）的形式运行，带来两个限制：

1. **依赖本机在线**：只有电脑开机、联网、Claude 应用运行时才触发；早上没开机就得等下次打开补跑，日报时效性丢失。
2. **投递渠道单一**：只有 Gmail 邮件，没有即时通知渠道。

## 目标

- 日报生成完全脱离本机，在云端按时执行。
- 新增钉钉群推送，作为即时阅读渠道；邮件保留为存档渠道。

## 已确认的决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 云端方案 | GitHub Actions + `claude-code-action@v1` | Runner 有完整公网出口，抓 19 个源最稳；日报可直接 commit 回仓库 |
| 仓库可见性 | 私有 | 日报含楼宇/FM 方向的业务判断，不宜公开；Actions 免费额度足够 |
| 钉钉内容 | TL;DR + 分类条目标题 + 原始链接 | 钉钉自定义机器人消息有长度上限，日报正文约 200 行必然超限 |
| 邮件通道 | 保留，与钉钉并行 | 邮件存档，钉钉即时 |
| 认证方式 | `CLAUDE_CODE_OAUTH_TOKEN` | 走订阅额度，不额外按 token 计费 |

## 架构

```
仓库 nengzong/ai-daily-radar（私有）
├── .github/workflows/daily-radar.yml   # cron 23:30 UTC（北京 07:30）+ workflow_dispatch
├── prompts/daily-radar.md              # 提示词纳入版本管理
├── sources.md                          # 信息源清单（不变）
├── scripts/
│   ├── send_dingtalk.py                # 加签 + markdown 推送
│   ├── send_email.sh                   # 密码改为优先读环境变量
│   └── md2html.py                      # Markdown → HTML（不变）
└── reports/
    ├── YYYY-MM-DD.md                   # 日报全文
    ├── YYYY-MM-DD.dingtalk.md          # 钉钉专用凝练版
    └── appstore-snapshot.json          # 榜单快照
```

### 核心设计：投递职责从 Claude 收回到 workflow

现有提示词的第五步让 Claude 自己调用发信脚本并发桌面通知。这有三个问题：Claude 可能跳过该步骤、可能发送失败而不自知、可能声称已发送但实际没有。

新设计中，**Claude 只负责生成日报文件**，投递由 workflow 中确定性的步骤完成。任何一步失败都会让 workflow 红灯，GitHub 会自动发失败告警邮件。

### 执行流程

1. checkout 仓库
2. `claude-code-action@v1` 执行 `prompts/daily-radar.md`：抓源 → 筛选 → 写 `reports/YYYY-MM-DD.md` → 写 `reports/YYYY-MM-DD.dingtalk.md` → 更新 `appstore-snapshot.json`
3. 校验两个报告文件存在且非空；不满足则失败退出，绝不推送空消息
4. 推送钉钉（`scripts/send_dingtalk.py`，脚本内含长度硬截断兜底）
5. 发送邮件（`if: always()`，钉钉失败不影响邮件）
6. commit & push `reports/` 回仓库

### 为什么让 Claude 额外产出钉钉版

替代方案是用脚本从日报 Markdown 里机械提取 TL;DR 段和 `###` 标题行。但那样会丢掉「为什么值得关注」这类最有价值的判断，群里只剩干巴巴的标题。Claude 生成日报时本就理解当天内容，让它顺手凝练一份成本极低，可读性高得多。

### 钉钉消息设计

- 使用**加签**安全模式：HMAC-SHA256(`{timestamp}\n{secret}`) → base64 → urlencode，附加 `&timestamp=&sign=`。不用 IP 白名单，因为 Actions runner 出口 IP 是动态的。
- 每个条目都带**公网原始来源链接**，群成员无需仓库权限即可阅读并跳转原文。
- 末尾附完整日报的仓库链接，并标注需要仓库权限。
- 脚本检查响应体的 `errcode`，非 0 视为失败（钉钉失败时 HTTP 状态码仍是 200）。

## 密钥管理

四个 GitHub Secrets：

| Secret | 用途 |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | 本机 `claude setup-token` 生成 |
| `DINGTALK_WEBHOOK` | 钉钉群机器人 webhook URL |
| `DINGTALK_SECRET` | 钉钉加签密钥（`SEC` 开头） |
| `GMAIL_APP_PASSWORD` | Gmail 16 位应用专用密码 |

`scripts/send_email.sh` 改为优先读环境变量 `GMAIL_APP_PASSWORD`，读不到再回落本地文件 `~/.config/ai-daily-radar/gmail_app_password`，使同一脚本在本机和 CI 都可用。

任何密钥都不得写入仓库文件。

## 已知技术风险与对策

| 风险 | 对策 |
|---|---|
| `base64 -b 76` 是 BSD 语法，GNU coreutils 上会失败 | 改为 `base64 \| tr -d '\n' \| fold -w 76` 的跨平台写法 |
| Actions cron 在整点高峰排队延迟 5–30 分钟 | 定在 23:30 UTC（北京 07:30），留出缓冲，使日报在 8 点前后到达 |
| UTC 日期与北京日期跨天不一致 | workflow 设 `TZ=Asia/Shanghai`，日期计算基于北京时间 |
| 订阅额度在 CI 中消耗，耗尽会导致失败 | 已知取舍；失败时 GitHub 发告警邮件 |
| 单个信息源抓取失败 | 沿用现有策略：标记「今日未获取」，继续执行 |
| 私有仓库链接对群成员是死链 | 钉钉消息中每条自带公网原文链接，仓库链接仅作补充并标注需权限 |

## 配额

私有仓库 Actions 免费额度 2000 分钟/月。本任务约 15 分钟/天 ≈ 465 分钟/月，余量充足。

## 迁移与验证

1. `git init` + `.gitignore`
2. 重组目录（`scripts/`、`prompts/`）
3. 提交并推送到 `github.com/nengzong/ai-daily-radar`
4. `claude setup-token` 生成订阅 token
5. 配置 4 个 Secrets
6. **手动 `workflow_dispatch` 触发一次完整验证**
7. 确认钉钉与邮件均收到后，停用本机定时任务

本机定时任务在验证通过前保持运行，避免出现断档日。
