# Cloudflare 部署与自定义域名 (如 radar.dpdns.org) 配置指南

本项目已内置零依赖的静态网站生成器（`scripts/build_site.py`），已成功部署在 Cloudflare 上：
- **公共访问网址**：`https://ai-daily-radar.radar-watchdog.workers.dev/`
- **0 成本、0 台服务器、免运维**
- 全球 CDN 加速与全自动免费 HTTPS (SSL) 证书
- 只要 GitHub 仓库有新的日报推送（`push` 到 `main` 分支），Cloudflare 会在几十秒内自动构建更新

---

## 一、当前 DNS 记录添加（对应当前界面填写）

你在 **管理 `radar.dpdns.org` 的 DNS** 界面添加 CNAME 记录时，请这样填写：

| 表单字段 | 填写内容 | 说明 |
| :--- | :--- | :--- |
| **类型** | `CNAME` | 下拉框选择 CNAME（已默认选好） |
| **名称 (必需)** | `@` | 输入 `@` 代表直接解析根域名 `radar.dpdns.org` |
| **目标 (必需)** | `ai-daily-radar.radar-watchdog.workers.dev` | 填入你刚刚部署成功的线上网址 |
| **代理状态** | 保持 **开启 (橙色云朵已代理)** | 享受 Cloudflare 全球 CDN 加速与免费 SSL 证书 |
| **TTL** | `自动` | 保持默认即可 |

填写完成后：
1. 点击右侧蓝色的 **「保存」**。
2. 点击页面左下角蓝色的 **「继续前往激活」**。

---

## 二、在 Worker 中绑定自定义域（关键一步）

DNS 保存后，还需要告诉 Cloudflare 将 `radar.dpdns.org` 的流量路由到你的 `ai-daily-radar` 网页应用：

1. 打开 Cloudflare 控制台左侧菜单：**Compute (Workers & Pages)** → 找到并点击进入你的应用 **`ai-daily-radar`**。
2. 点击顶部的 **设置 (Settings)** 选项卡。
3. 点击左侧子菜单中的 **域与路由 (Domains & Routes)**。
4. 点击 **添加 (Add)** → 选择 **自定义域 (Custom Domain)**。
5. 输入你的域名：`radar.dpdns.org`，点击 **添加自定义域 (Add Custom Domain)**。
6. Cloudflare 会自动关联证书与路由，状态变为 **Active**（有效）后，即可直接在浏览器输入 `https://radar.dpdns.org` 打开高颜值日报！

---

## 三、配置钉钉推送自动带上你的域名链接

现在你的独立域名是 `https://radar.dpdns.org`，我们需要让系统自动将此网址注入钉钉推送卡片中：

### 1. 如果走 GitHub Actions 自动推送（每天早上 08:30）
- 打开你的 GitHub 仓库：`Settings` → `Secrets and variables` → `Actions` → `Variables` 选项卡。
- 点击 **New repository variable**：
  - **Name**: `RADAR_BASE_URL`
  - **Value**: `https://radar.dpdns.org`
- 每天早上推送到钉钉群时，文末会自动生成直达链接与卡片：
  ```markdown
  > 🌐 网页版直达: [https://radar.dpdns.org/reports/2026-09-08/](https://radar.dpdns.org/reports/2026-09-08/)

  ---

  ### 🌐 [👉 点击在线阅读网页版完整报告](https://radar.dpdns.org/reports/2026-09-08/)
  ```

### 2. 如果你在本机运行或补发
在终端中执行一次命令写入本地配置：
```bash
echo "https://radar.dpdns.org" > ~/.config/ai-daily-radar/radar_base_url
```
运行 `scripts/send_dingtalk.py` 时便会自动使用该域名。

---

## 四、本地预览与调试

在本地随时可以一键构建并预览网站：

```bash
# 1. 运行构建
python3 scripts/build_site.py

# 2. 启动本地预览服务 (端口 8089)
python3 -m http.server 8089 -d dist
```

浏览器打开 `http://localhost:8089` 即可体验。
