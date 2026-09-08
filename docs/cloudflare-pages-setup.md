# Cloudflare Pages 部署与免费域名 (如 xxx.dpdns.org) 配置指南

本项目已内置零依赖的静态网站生成器（[scripts/build_site.py](file:///Users/nengzongtan/persagy/ai-daily-radar/scripts/build_site.py)），可直接托管在 **Cloudflare Pages** 上，享受：
- **0 成本、0 台服务器、免运维**
- 全球 CDN 加速与全自动免费 HTTPS (SSL) 证书
- 只要 GitHub 仓库有新的日报推送（`push` 到 `main` 分支），Cloudflare 会在几十秒内自动构建发布

---

## 一、在 Cloudflare Pages 托管网站（5 分钟完成）

1. **登录 Cloudflare 控制台**：
   访问 [dash.cloudflare.com](https://dash.cloudflare.com/) 并登录你的账号（免费注册）。

2. **新建 Pages 项目**：
   - 在左侧菜单点击 **Compute (Workers & Pages)** → **Overview**（或 Workers 和 Pages）。
   - 点击 **Create application**（创建应用程序）→ 切换到 **Pages** 选项卡。
   - 选择 **Connect to Git**（连接到 Git）。

3. **授权并选择 GitHub 仓库**：
   - 授权 Cloudflare 访问你的 GitHub 账号。
   - 在仓库列表中选择 `ai-daily-radar`（私有仓库同样支持且完全免费）。

4. **填写构建配置**：
   - **Project name（项目名称）**：`ai-daily-radar`（默认分配域名形如 `https://ai-daily-radar.pages.dev`）
   - **Production branch（生产分支）**：`main`
   - **Framework preset（框架预设）**：选择 `None`
   - **Build command（构建命令）**：`python3 scripts/build_site.py`
   - **Build output directory（构建输出目录）**：`dist`
   - **Root directory（根目录）**：留空（即 `/`）

5. **点击保存并部署**：
   - 点击 **Save and Deploy**（保存并部署）。
   - 首次部署通常耗时 20~30 秒，完成后会显示一个绿色的成功标志以及你的公共网址（如 `https://ai-daily-radar.pages.dev`）。

---

## 二、绑定自定义免费域名（如 xxx.dpdns.org）

Cloudflare Pages 支持绑定任何二级或顶级域名，无需购买付费域名。

1. **在 Cloudflare Pages 添加自定义域**：
   - 进入你刚刚创建的 Pages 项目（`ai-daily-radar`）。
   - 点击顶部的 **Custom domains（自定义域）** 选项卡。
   - 点击 **Set up a custom domain（设置自定义域）**。
   - 输入你的域名，例如 `radar.dpdns.org` 或 `xxx.dpdns.org`，点击继续。

2. **在你的域名 DNS 提供商处添加 CNAME 记录**：
   - 登录提供 `xxx.dpdns.org` 的 DNS 服务商后台。
   - 添加一条 DNS 解析记录：
     - **记录类型**：`CNAME`
     - **主机名 / 别名 (Name/Host)**：`xxx`（或对应的子域名）
     - **目标地址 (Target/Value)**：`ai-daily-radar.pages.dev`（即你的 Pages 默认域名）
     - **TTL**：默认或 `60` / `Auto`
   - 保存解析。

3. **等待 SSL 证书签发与生效**：
   - Cloudflare Pages 会检测该 CNAME 解析，通常在 2~10 分钟内自动完成验证并签发全球通用的 SSL 证书。
   - 状态变为 **Active** 后，浏览器直接访问 `https://xxx.dpdns.org` 即可打开高颜值日报网站！

---

## 三、配置钉钉推送自动带上网页版链接

构建脚本和推送脚本已升级支持 `RADAR_BASE_URL`：

### 1. 如果走 GitHub Actions 自动推送（推荐）
- 打开你的 GitHub 仓库：`Settings` → `Secrets and variables` → `Actions` → `Variables` 选项卡。
- 点击 **New repository variable**：
  - **Name**: `RADAR_BASE_URL`
  - **Value**: 你的网址，例如 `https://xxx.dpdns.org`（或 `https://ai-daily-radar.pages.dev`）
- 每天 08:30 投递流水线推送到钉钉群时，文末会自动生成：
  `> 🌐 网页版直达: https://xxx.dpdns.org/reports/2026-09-08/`
  以及醒目的高亮跳转卡片：
  `### 🌐 [👉 点击在线阅读网页版完整报告](https://xxx.dpdns.org/reports/2026-09-08/)`

### 2. 如果你在本地运行或测试
只需在本地配置一行：
```bash
echo "https://xxx.dpdns.org" > ~/.config/ai-daily-radar/radar_base_url
```
或者在终端中临时设置：
```bash
export RADAR_BASE_URL="https://xxx.dpdns.org"
```
运行 [scripts/send_dingtalk.py](file:///Users/nengzongtan/persagy/ai-daily-radar/scripts/send_dingtalk.py) 时就会自动附带网页链接。

---

## 四、本地预览与调试

在本地随时可以一键构建并预览网站：

```bash
# 1. 运行构建
python3 scripts/build_site.py

# 2. 启动本地预览服务 (端口 8089)
python3 -m http.server 8089 -d dist
```

浏览器打开 `http://localhost:8089` 即可查看所有历史日报列表与今日详情页，支持深浅色模式切换与全站搜索。
