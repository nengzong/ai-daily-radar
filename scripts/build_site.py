#!/usr/bin/env python3
"""AI Daily Radar 静态网页生成器 (Zero-dependency SSG)

扫描 reports/*.md (排除 .dingtalk.md), 生成高颜值的现代静态网站至 dist/ 目录。
适配 Cloudflare Pages 静态托管, 无需任何第三方 npm/pip 依赖。

用法:
    python3 scripts/build_site.py
"""

import html
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / "reports"
DIST_DIR = ROOT_DIR / "dist"
ASSETS_DIR = DIST_DIR / "assets"


def parse_inline_markdown(text: str) -> str:
    """将内联 markdown 转为语义化 HTML"""
    # 避免重复转义，先做特殊字符转义
    text = html.escape(text, quote=False)
    # **粗体**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # *斜体*
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # `代码`
    text = re.sub(
        r'`([^`]+)`',
        r'<code class="code-inline">\1</code>',
        text,
    )
    # [文字](链接)
    text = re.sub(
        r'\[([^\]]+)\]\((https?://[^\s)]+)\)',
        r'<a href="\2" target="_blank" rel="noopener noreferrer" class="link">\1</a>',
        text,
    )
    # 裸链接 (带协议)
    text = re.sub(
        r'(?<!["\>])(https?://[^\s<>"·]+)',
        r'<a href="\1" target="_blank" rel="noopener noreferrer" class="link-bare">\1</a>',
        text,
    )
    return text


def parse_report_content(md_text: str) -> dict:
    """解析单份日报的 Markdown 内容为结构化数据与 HTML 片段"""
    lines = md_text.splitlines()
    data = {
        "title": "AI 日报",
        "date": "",
        "subtitle": "",
        "tldr": "",
        "item_count": 0,
        "sections": [],
        "toc": [],
        "html_body": "",
    }

    # 提取标题与副标题
    body_lines = []
    current_section = None
    section_index = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section:
                current_section["lines"].append("")
            continue

        # 一级标题 # AI 日报 · 2026-09-08
        if stripped.startswith("# "):
            data["title"] = stripped.lstrip("# ").strip()
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', data["title"])
            if date_match:
                data["date"] = date_match.group(0)
            continue

        # 副标题引用块: > 12 条精选 ｜ 源覆盖 31/45 ...
        if stripped.startswith(">") and not data["subtitle"] and ("条精选" in stripped or "源覆盖" in stripped):
            data["subtitle"] = stripped.lstrip("> ").strip()
            count_match = re.search(r'(\d+)\s*条精选', data["subtitle"])
            if count_match:
                data["item_count"] = int(count_match.group(1))
            continue

        # 二级标题 ## 📌 今日 TL;DR / ## 🏭 行业动向
        if stripped.startswith("## "):
            sec_title = stripped.lstrip("# ").strip()
            sec_id = f"section-{section_index}"
            section_index += 1
            current_section = {
                "id": sec_id,
                "title": sec_title,
                "lines": [],
            }
            data["sections"].append(current_section)
            data["toc"].append({"id": sec_id, "title": sec_title})
            continue

        if current_section:
            current_section["lines"].append(stripped)
        else:
            body_lines.append(stripped)

    # 渲染各个 Section
    rendered_sections = []
    for sec in data["sections"]:
        sec_title = sec["title"]
        sec_id = sec["id"]
        sec_content_lines = sec["lines"]
        sec_text = "\n".join(sec_content_lines)

        # 提取 TL;DR 纯文本作为摘要
        if "TL;DR" in sec_title or "今日导读" in sec_title:
            data["tldr"] = sec_text.replace("\n", " ").strip()

        # 渲染 Section 内部元素
        sec_html = render_section_content(sec_title, sec_content_lines)
        is_tldr = "TL;DR" in sec_title
        section_card_class = "content-card tldr-card" if is_tldr else "content-card"

        rendered_sections.append(f"""
        <section id="{sec_id}" class="{section_card_class}">
            <div class="card-header">
                <h2 class="section-heading">{parse_inline_markdown(sec_title)}</h2>
            </div>
            <div class="card-body">
                {sec_html}
            </div>
        </section>
        """)

    data["html_body"] = "\n".join(rendered_sections)
    return data


def render_section_content(title: str, lines: list) -> str:
    """渲染分类章节的内部内容（条目、列表、表格、普通段落）"""
    output = []
    items_buf = []
    in_list = False
    current_item = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_item:
                items_buf.append(current_item)
                current_item = None
            continue

        # 识别条目开头: **1. Caterpillar 与 FieldAI 合作...** 或 ### 标题
        item_match = re.match(r'^(?:\*\*\d+\.|\d+\.|\#{3})\s*(.+)$', stripped)
        if item_match and ("行业动向" in title or "技术与案例" in title or "产品灵感" in title):
            if current_item:
                items_buf.append(current_item)
            heading_text = item_match.group(1).rstrip('*').strip()
            current_item = {
                "title": heading_text,
                "summary": "",
                "why": "",
                "link": "",
                "others": [],
            }
            continue

        if current_item:
            if stripped.startswith("摘要：") or stripped.startswith("摘要:"):
                current_item["summary"] = re.sub(r'^摘要[：:]\s*', '', stripped)
            elif stripped.startswith("为什么值得关注：") or stripped.startswith("为什么值得关注:"):
                current_item["why"] = re.sub(r'^为什么值得关注[：:]\s*', '', stripped)
            elif stripped.startswith("链接：") or stripped.startswith("链接:"):
                raw_url = re.sub(r'^链接[：:]\s*', '', stripped)
                current_item["link"] = raw_url
            else:
                current_item["others"].append(stripped)
            continue

        # 列表项: - 🇺🇸 美国区：...
        if stripped.startswith("- ") or stripped.startswith("* "):
            content = stripped[2:].strip()
            output.append(f'<li class="list-item">{parse_inline_markdown(content)}</li>')
            continue

        # 引用块
        if stripped.startswith("> "):
            content = stripped[2:].strip()
            output.append(f'<blockquote class="quote-box">{parse_inline_markdown(content)}</blockquote>')
            continue

        # 普通段落
        output.append(f'<p class="text-paragraph">{parse_inline_markdown(stripped)}</p>')

    if current_item:
        items_buf.append(current_item)

    # 如果有结构化条目，渲染为条目卡片
    if items_buf:
        item_cards = []
        for idx, itm in enumerate(items_buf, 1):
            title_html = parse_inline_markdown(itm["title"])
            summary_html = f'<div class="item-summary"><span class="badge badge-summary">摘要</span> {parse_inline_markdown(itm["summary"])}</div>' if itm["summary"] else ""
            why_html = f'<div class="item-why"><span class="badge badge-why">为什么值得关注</span> {parse_inline_markdown(itm["why"])}</div>' if itm["why"] else ""
            
            link_html = ""
            if itm["link"]:
                url = itm["link"].strip()
                # 尝试提取域名简写
                domain = re.sub(r'^https?://(?:www\.)?([^/]+).*$', r'\1', url)
                link_html = f'<div class="item-footer"><a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" class="source-button"><svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7zm-2 16H5V7h7V5H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h7v-2z"/></svg> 来源: {html.escape(domain)}</a></div>'

            others_html = "".join(f'<p class="item-other">{parse_inline_markdown(o)}</p>' for o in itm["others"])

            item_cards.append(f"""
            <article class="article-item">
                <div class="item-header">
                    <span class="item-number">#{idx}</span>
                    <h3 class="item-title">{title_html}</h3>
                </div>
                {summary_html}
                {why_html}
                {others_html}
                {link_html}
            </article>
            """)
        return f'<div class="items-grid">{"".join(item_cards)}</div>'

    return "\n".join(output)


def get_all_reports() -> list:
    """按日期倒序收集所有 reports/*.md"""
    reports = []
    if not REPORTS_DIR.exists():
        return reports

    for file_path in sorted(REPORTS_DIR.glob("*.md"), reverse=True):
        if file_path.name.endswith(".dingtalk.md"):
            continue
        date_match = re.search(r'^\d{4}-\d{2}-\d{2}', file_path.stem)
        if not date_match:
            continue
        
        date_str = date_match.group(0)
        content = file_path.read_text(encoding="utf-8")
        parsed = parse_report_content(content)
        parsed["filename"] = file_path.name
        parsed["date"] = date_str
        reports.append(parsed)

    return reports


def render_html_page(title: str, content: str, active_nav: str = "home", extra_head: str = "") -> str:
    """生成统一骨架的 HTML 页面"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="AI Daily Radar - 每日 AI 情报雷达，聚焦行业动向、前沿技术与产品灵感。">
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/style.css">
    {extra_head}
</head>
<body class="theme-dark">
    <!-- 顶部导航栏 -->
    <header class="site-header">
        <div class="header-container">
            <a href="/" class="brand-logo">
                <span class="logo-icon">📡</span>
                <span class="logo-text">AI Daily Radar</span>
                <span class="logo-badge">每日情报</span>
            </a>
            <nav class="main-nav">
                <a href="/" class="nav-link {'active' if active_nav == 'home' else ''}">首页</a>
                <a href="/#archive" class="nav-link {'active' if active_nav == 'archive' else ''}">往期归档</a>
                <a href="https://github.com/nengzong/ai-daily-radar" target="_blank" rel="noopener noreferrer" class="nav-link icon-link" title="GitHub 仓库">
                    <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M12 2A10 10 0 0 0 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.1-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0 0 12 2z"/></svg>
                </a>
                <button id="theme-toggle" class="theme-toggle-btn" aria-label="切换明暗主题">
                    <span class="theme-icon">🌙</span>
                </button>
            </nav>
        </div>
    </header>

    <!-- 主体区域 -->
    <main class="site-main">
        {content}
    </main>

    <!-- 页脚 -->
    <footer class="site-footer">
        <div class="footer-container">
            <div class="footer-left">
                <p class="footer-brand">📡 AI Daily Radar</p>
                <p class="footer-desc">每天自动扫描 40+ 个全球信息源 · 业务视角提炼 AI 商业与技术落地</p>
            </div>
            <div class="footer-right">
                <p>托管于 Cloudflare Pages · 全球低延迟访问</p>
                <p class="copyright">&copy; 2026 AI Daily Radar. All rights reserved.</p>
            </div>
        </div>
    </footer>

    <!-- 交互脚本 -->
    <script src="/assets/app.js"></script>
</body>
</html>
"""


def build_index_page(reports: list) -> str:
    """生成网站首页 index.html"""
    if not reports:
        return render_html_page("AI Daily Radar - 暂无报告", "<div class='empty-state'>暂无已发布的日报</div>")

    latest = reports[0]
    latest_url = f"/reports/{latest['date']}/"
    
    # 统计数据
    total_reports = len(reports)
    total_items = sum(r.get("item_count", 0) for r in reports)

    # 归档卡片列表
    archive_cards = []
    for r in reports:
        date_str = r["date"]
        subtitle = r.get("subtitle", "")
        item_count = r.get("item_count", 0)
        tldr_snippet = r.get("tldr", "")[:130] + ("..." if len(r.get("tldr", "")) > 130 else "")
        archive_cards.append(f"""
        <a href="/reports/{date_str}/" class="archive-card" data-date="{date_str}" data-search="{html.escape(date_str + ' ' + subtitle + ' ' + tldr_snippet)}">
            <div class="archive-card-header">
                <span class="archive-date">{date_str}</span>
                <span class="archive-count">{item_count} 条精选</span>
            </div>
            <p class="archive-subtitle">{html.escape(subtitle)}</p>
            <p class="archive-snippet">{html.escape(tldr_snippet)}</p>
            <div class="archive-footer">
                <span class="read-more">阅读整期 &rarr;</span>
            </div>
        </a>
        """)

    archive_html = "\n".join(archive_cards)

    content = f"""
    <!-- Hero 区域 -->
    <section class="hero-section">
        <div class="hero-content">
            <div class="hero-badge">
                <span class="pulse-dot"></span>
                <span>最新发布 · {latest['date']}</span>
            </div>
            <h1 class="hero-title">AI Daily Radar</h1>
            <p class="hero-subtitle">每天自动扫描 40+ 个全球信息源，深度提炼行业动向、前沿技术与产品灵感</p>
            
            <div class="hero-actions">
                <a href="{latest_url}" class="primary-btn">
                    <span>阅读今日最新早报</span>
                    <svg class="icon" viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M5 12h14M12 5l7 7-7 7"/></svg>
                </a>
                <a href="#archive" class="secondary-btn">浏览历史归档 ({total_reports} 期)</a>
            </div>

            <!-- 数据概览 -->
            <div class="stats-row">
                <div class="stat-card">
                    <span class="stat-num">{total_reports}</span>
                    <span class="stat-label">期日报积累</span>
                </div>
                <div class="stat-card">
                    <span class="stat-num">{total_items}+</span>
                    <span class="stat-label">条精选情报</span>
                </div>
                <div class="stat-card">
                    <span class="stat-num">45</span>
                    <span class="stat-label">个监控信源</span>
                </div>
                <div class="stat-card">
                    <span class="stat-num">08:30</span>
                    <span class="stat-label">每日准点送达</span>
                </div>
            </div>
        </div>
    </section>

    <!-- 最新一期速递 -->
    <section class="latest-featured-section">
        <div class="section-top">
            <h2 class="section-title">今日早报速览</h2>
            <a href="{latest_url}" class="view-all-link">进入完整版 &rarr;</a>
        </div>
        <div class="featured-card">
            <div class="featured-header">
                <div>
                    <span class="badge badge-featured">TOP STORY</span>
                    <h3 class="featured-title">{latest['title']}</h3>
                    <p class="featured-meta">{html.escape(latest.get('subtitle', ''))}</p>
                </div>
                <a href="{latest_url}" class="featured-btn">阅读全文</a>
            </div>
            <div class="featured-tldr">
                <div class="tldr-label">📌 核心概要</div>
                <p>{parse_inline_markdown(latest.get('tldr', ''))}</p>
            </div>
        </div>
    </section>

    <!-- 往期归档与搜索 -->
    <section id="archive" class="archive-section">
        <div class="section-top">
            <div>
                <h2 class="section-title">往期情报归档</h2>
                <p class="section-desc">查阅历史日报，洞察 AI 商业落地演进轨迹</p>
            </div>
            <!-- 客户端实时搜索框 -->
            <div class="search-box">
                <svg class="search-icon" viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                <input type="text" id="archive-search" placeholder="输入日期或关键词快速检索..." aria-label="搜索往期日报">
            </div>
        </div>

        <div id="archive-grid" class="archive-grid">
            {archive_html}
        </div>
        <div id="no-search-results" class="no-results hidden">
            <p>未找到符合条件的日报记录</p>
        </div>
    </section>
    """
    return render_html_page("AI Daily Radar · 每日 AI 情报雷达", content, active_nav="home")


def build_report_page(report: dict, prev_report: dict = None, next_report: dict = None) -> str:
    """生成具体某天日报的详情页 reports/YYYY-MM-DD/index.html"""
    date_str = report["date"]
    title = report["title"]
    subtitle = report.get("subtitle", "")

    # 目录导航项
    toc_items = []
    for item in report.get("toc", []):
        toc_items.append(f'<li><a href="#{item["id"]}" class="toc-link">{parse_inline_markdown(item["title"])}</a></li>')
    toc_html = "\n".join(toc_items)

    # 底部上下篇导航
    nav_buttons = []
    if prev_report:
        nav_buttons.append(f"""
        <a href="/reports/{prev_report['date']}/" class="prev-next-btn prev">
            <span class="btn-label">&larr; 前一天</span>
            <span class="btn-title">{prev_report['date']}</span>
        </a>
        """)
    else:
        nav_buttons.append('<div class="prev-next-placeholder"></div>')

    if next_report:
        nav_buttons.append(f"""
        <a href="/reports/{next_report['date']}/" class="prev-next-btn next">
            <span class="btn-label">后一天 &rarr;</span>
            <span class="btn-title">{next_report['date']}</span>
        </a>
        """)
    else:
        nav_buttons.append('<div class="prev-next-placeholder"></div>')

    content = f"""
    <div class="report-container">
        <!-- 顶部面包屑与标题区 -->
        <div class="report-header">
            <div class="breadcrumb">
                <a href="/">首页</a>
                <span class="separator">/</span>
                <a href="/#archive">往期归档</a>
                <span class="separator">/</span>
                <span class="current">{date_str}</span>
            </div>

            <h1 class="report-main-title">{title}</h1>
            <div class="report-meta-row">
                <span class="report-date-badge">📅 {date_str}</span>
                <span class="report-subtitle-badge">{html.escape(subtitle)}</span>
                <button class="share-btn" onclick="navigator.clipboard.writeText(window.location.href); alert('已复制链接到剪贴板！');">
                    <svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
                    复制链接
                </button>
            </div>
        </div>

        <div class="report-layout">
            <!-- 左侧目录导航 (桌面端吸顶) -->
            <aside class="report-toc-aside">
                <div class="toc-sticky-box">
                    <div class="toc-header">
                        <span>📑 报告大纲</span>
                    </div>
                    <ul class="toc-list">
                        {toc_html}
                    </ul>
                    <div class="toc-footer">
                        <a href="#top" class="back-to-top">&uarr; 返回顶部</a>
                    </div>
                </div>
            </aside>

            <!-- 右侧正文内容 -->
            <article class="report-article-body">
                {report["html_body"]}

                <!-- 上一篇 / 下一篇导航 -->
                <div class="report-nav-footer">
                    {"".join(nav_buttons)}
                </div>
            </article>
        </div>
    </div>
    """
    return render_html_page(f"{title} - AI Daily Radar", content, active_nav="detail")


def build_404_page() -> str:
    """生成 404 页面"""
    content = """
    <div class="not-found-container">
        <h1 class="not-found-code">404</h1>
        <h2 class="not-found-title">页面未找到</h2>
        <p class="not-found-desc">您访问的日报可能已被归档或链接输入有误。</p>
        <a href="/" class="primary-btn">返回网站首页</a>
    </div>
    """
    return render_html_page("404 - 页面未找到 · AI Daily Radar", content)


def write_assets():
    """写入 CSS 与 JS 静态资源"""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    css_content = """/* AI Daily Radar - Modern Theme & Layout System */

:root {
    --font-main: 'Plus Jakarta Sans', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 深色模式默认 (Sleek Dark Mode) */
body.theme-dark {
    --bg: #090d16;
    --surface: #111726;
    --surface-hover: #162035;
    --surface-glass: rgba(17, 23, 38, 0.75);
    --border: #1f2a44;
    --border-light: rgba(255, 255, 255, 0.08);
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --primary: #38bdf8;
    --primary-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
    --accent: #f59e0b;
    --accent-bg: rgba(245, 158, 11, 0.12);
    --badge-bg: rgba(56, 189, 248, 0.12);
    --badge-text: #38bdf8;
    --card-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
}

/* 浅色模式 */
body.theme-light {
    --bg: #f8fafc;
    --surface: #ffffff;
    --surface-hover: #f1f5f9;
    --surface-glass: rgba(255, 255, 255, 0.85);
    --border: #e2e8f0;
    --border-light: rgba(0, 0, 0, 0.06);
    --text: #0f172a;
    --text-muted: #64748b;
    --primary: #0284c7;
    --primary-gradient: linear-gradient(135deg, #0284c7 0%, #6366f1 100%);
    --accent: #d97706;
    --accent-bg: #fef3c7;
    --badge-bg: #e0f2fe;
    --badge-text: #0369a1;
    --card-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
}

/* 全局基底 */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html {
    scroll-behavior: smooth;
    font-size: 16px;
}

body {
    background-color: var(--bg);
    color: var(--text);
    font-family: var(--font-main);
    line-height: 1.68;
    transition: background-color 0.3s ease, color 0.3s ease;
    -webkit-font-smoothing: antialiased;
}

/* 顶部导航 */
.site-header {
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    background: var(--surface-glass);
    border-bottom: 1px solid var(--border);
}

.header-container {
    max-width: 1240px;
    margin: 0 auto;
    padding: 14px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.brand-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    color: var(--text);
}

.logo-icon {
    font-size: 24px;
}

.logo-text {
    font-size: 19px;
    font-weight: 800;
    letter-spacing: -0.5px;
    background: var(--primary-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.logo-badge {
    font-size: 11px;
    font-weight: 600;
    background: var(--badge-bg);
    color: var(--badge-text);
    padding: 2px 8px;
    border-radius: 99px;
    border: 1px solid var(--border-light);
}

.main-nav {
    display: flex;
    align-items: center;
    gap: 18px;
}

.nav-link {
    text-decoration: none;
    color: var(--text-muted);
    font-weight: 500;
    font-size: 14px;
    transition: var(--transition);
}

.nav-link:hover, .nav-link.active {
    color: var(--primary);
}

.icon-link {
    display: flex;
    align-items: center;
}

.theme-toggle-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 10px;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    transition: var(--transition);
}

.theme-toggle-btn:hover {
    border-color: var(--primary);
    transform: scale(1.05);
}

/* 主内容区容器 */
.site-main {
    max-width: 1240px;
    margin: 0 auto;
    padding: 32px 24px 80px;
}

/* Hero 区域 */
.hero-section {
    padding: 48px 0 36px;
    text-align: center;
}

.hero-content {
    max-width: 820px;
    margin: 0 auto;
}

.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    background: var(--badge-bg);
    color: var(--badge-text);
    padding: 6px 14px;
    border-radius: 99px;
    border: 1px solid var(--border-light);
    margin-bottom: 20px;
}

.pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--primary);
    box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7); }
    70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(56, 189, 248, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
}

.hero-title {
    font-size: clamp(32px, 5vw, 54px);
    font-weight: 800;
    letter-spacing: -1.5px;
    line-height: 1.15;
    margin-bottom: 16px;
    background: var(--primary-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-subtitle {
    font-size: 18px;
    color: var(--text-muted);
    max-width: 620px;
    margin: 0 auto 32px;
}

.hero-actions {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-bottom: 48px;
}

.primary-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--primary-gradient);
    color: #ffffff;
    font-weight: 600;
    font-size: 15px;
    padding: 12px 24px;
    border-radius: 12px;
    text-decoration: none;
    box-shadow: 0 4px 20px rgba(56, 189, 248, 0.35);
    transition: var(--transition);
}

.primary-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 25px rgba(56, 189, 248, 0.5);
}

.secondary-btn {
    display: inline-flex;
    align-items: center;
    background: var(--surface);
    color: var(--text);
    font-weight: 600;
    font-size: 15px;
    padding: 12px 24px;
    border-radius: 12px;
    text-decoration: none;
    border: 1px solid var(--border);
    transition: var(--transition);
}

.secondary-btn:hover {
    background: var(--surface-hover);
    border-color: var(--primary);
}

/* 统计卡片条 */
.stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    max-width: 760px;
    margin: 0 auto;
}

.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.stat-num {
    font-size: 26px;
    font-weight: 800;
    color: var(--primary);
    line-height: 1.2;
}

.stat-label {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* 今日头条速览卡片 */
.latest-featured-section {
    margin: 48px 0;
}

.section-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 20px;
}

.section-title {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.5px;
}

.section-desc {
    font-size: 14px;
    color: var(--text-muted);
    margin-top: 4px;
}

.view-all-link {
    font-size: 14px;
    font-weight: 600;
    color: var(--primary);
    text-decoration: none;
}

.featured-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 28px;
    box-shadow: var(--card-shadow);
    transition: var(--transition);
}

.featured-card:hover {
    border-color: var(--primary);
}

.featured-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
}

.badge-featured {
    font-size: 11px;
    font-weight: 700;
    background: var(--accent-bg);
    color: var(--accent);
    padding: 4px 10px;
    border-radius: 99px;
    display: inline-block;
    margin-bottom: 8px;
}

.featured-title {
    font-size: 22px;
    font-weight: 700;
}

.featured-meta {
    font-size: 14px;
    color: var(--text-muted);
    margin-top: 4px;
}

.featured-btn {
    background: var(--surface-hover);
    color: var(--text);
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    border: 1px solid var(--border);
    transition: var(--transition);
}

.featured-btn:hover {
    background: var(--primary);
    color: #fff;
    border-color: var(--primary);
}

.featured-tldr {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 12px;
    padding: 18px 20px;
    border-left: 4px solid var(--primary);
}

body.theme-light .featured-tldr {
    background: #f1f5f9;
}

.tldr-label {
    font-weight: 700;
    font-size: 14px;
    color: var(--primary);
    margin-bottom: 6px;
}

/* 往期归档卡片网格 */
.archive-section {
    margin: 60px 0;
}

.search-box {
    position: relative;
    width: 280px;
}

.search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
}

#archive-search {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 9px 12px 9px 36px;
    color: var(--text);
    font-size: 14px;
    outline: none;
    transition: var(--transition);
}

#archive-search:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
}

.archive-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 20px;
    margin-top: 24px;
}

.archive-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 22px;
    text-decoration: none;
    color: var(--text);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: var(--transition);
    box-shadow: var(--card-shadow);
}

.archive-card:hover {
    transform: translateY(-4px);
    border-color: var(--primary);
}

.archive-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.archive-date {
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
}

.archive-count {
    font-size: 12px;
    font-weight: 600;
    background: var(--badge-bg);
    color: var(--badge-text);
    padding: 3px 8px;
    border-radius: 6px;
}

.archive-subtitle {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.archive-snippet {
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-bottom: 18px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.archive-footer {
    display: flex;
    justify-content: flex-end;
}

.read-more {
    font-size: 13px;
    font-weight: 600;
    color: var(--primary);
}

.no-results {
    text-align: center;
    padding: 60px 0;
    color: var(--text-muted);
}

.hidden {
    display: none;
}

/* ================= 报告详情页样式 ================= */

.report-container {
    max-width: 1140px;
    margin: 0 auto;
}

.report-header {
    margin-bottom: 36px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
}

.breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 16px;
}

.breadcrumb a {
    color: var(--text-muted);
    text-decoration: none;
}

.breadcrumb a:hover {
    color: var(--primary);
}

.report-main-title {
    font-size: clamp(26px, 4vw, 36px);
    font-weight: 800;
    letter-spacing: -0.8px;
    margin-bottom: 14px;
}

.report-meta-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
}

.report-date-badge, .report-subtitle-badge {
    font-size: 13px;
    font-weight: 500;
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 4px 12px;
    border-radius: 8px;
    color: var(--text-muted);
}

.share-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 5px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: var(--transition);
}

.share-btn:hover {
    border-color: var(--primary);
    color: var(--primary);
}

.report-layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: 40px;
    align-items: start;
}

/* 目录大纲侧边栏 */
.report-toc-aside {
    position: sticky;
    top: 90px;
}

.toc-sticky-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 16px;
}

.toc-header {
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 12px;
    color: var(--text);
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-light);
}

.toc-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.toc-link {
    font-size: 13px;
    color: var(--text-muted);
    text-decoration: none;
    display: block;
    padding: 4px 8px;
    border-radius: 6px;
    transition: var(--transition);
}

.toc-link:hover {
    color: var(--primary);
    background: var(--surface-hover);
}

.toc-footer {
    margin-top: 14px;
    padding-top: 10px;
    border-top: 1px solid var(--border-light);
}

.back-to-top {
    font-size: 12px;
    color: var(--text-muted);
    text-decoration: none;
}

.back-to-top:hover {
    color: var(--primary);
}

/* 报告正文区块 */
.report-article-body {
    display: flex;
    flex-direction: column;
    gap: 32px;
}

.content-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 28px;
    box-shadow: var(--card-shadow);
}

.tldr-card {
    border-left: 5px solid var(--primary);
    background: linear-gradient(180deg, var(--surface) 0%, rgba(56, 189, 248, 0.03) 100%);
}

.card-header {
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-light);
}

.section-heading {
    font-size: 20px;
    font-weight: 700;
    color: var(--text);
}

/* 条目卡片网格 */
.items-grid {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.article-item {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border-light);
    border-radius: 14px;
    padding: 20px;
    transition: var(--transition);
}

body.theme-light .article-item {
    background: #f8fafc;
}

.article-item:hover {
    border-color: var(--border);
}

.item-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 12px;
}

.item-number {
    font-size: 13px;
    font-weight: 800;
    color: var(--primary);
    background: var(--badge-bg);
    padding: 2px 8px;
    border-radius: 6px;
    margin-top: 2px;
}

.item-title {
    font-size: 17px;
    font-weight: 700;
    line-height: 1.45;
}

.item-summary, .item-why {
    font-size: 14.5px;
    line-height: 1.7;
    margin-top: 10px;
}

.item-summary {
    color: var(--text);
}

.item-why {
    color: var(--text-muted);
}

.badge {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    margin-right: 6px;
    display: inline-block;
}

.badge-summary {
    background: rgba(56, 189, 248, 0.15);
    color: var(--primary);
}

.badge-why {
    background: var(--accent-bg);
    color: var(--accent);
}

.item-other {
    font-size: 14px;
    color: var(--text-muted);
    margin-top: 8px;
}

.item-footer {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--border-light);
    display: flex;
    justify-content: flex-end;
}

.source-button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--primary);
    text-decoration: none;
    padding: 5px 12px;
    border-radius: 6px;
    background: var(--badge-bg);
    transition: var(--transition);
}

.source-button:hover {
    background: var(--primary);
    color: #fff;
}

/* 列表与引用 */
.list-item {
    font-size: 14.5px;
    line-height: 1.7;
    margin-bottom: 10px;
    margin-left: 20px;
}

.quote-box {
    margin: 14px 0;
    padding: 10px 16px;
    background: var(--accent-bg);
    border-left: 3px solid var(--accent);
    color: var(--accent);
    border-radius: 0 8px 8px 0;
    font-size: 13.5px;
}

.code-inline {
    background: rgba(255, 255, 255, 0.08);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    font-family: monospace;
}

body.theme-light .code-inline {
    background: #e2e8f0;
}

.link {
    color: var(--primary);
    text-decoration: underline;
    text-underline-offset: 3px;
}

.link-bare {
    color: var(--primary);
    text-decoration: none;
    word-break: break-all;
}

/* 报告底部翻页按钮 */
.report-nav-footer {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 24px;
}

.prev-next-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    text-decoration: none;
    color: var(--text);
    display: flex;
    flex-direction: column;
    transition: var(--transition);
}

.prev-next-btn.next {
    align-items: flex-end;
}

.prev-next-btn:hover {
    border-color: var(--primary);
    transform: translateY(-2px);
}

.btn-label {
    font-size: 12px;
    color: var(--text-muted);
}

.btn-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--primary);
    margin-top: 4px;
}

/* 404 页面 */
.not-found-container {
    text-align: center;
    padding: 100px 0;
}

.not-found-code {
    font-size: 96px;
    font-weight: 900;
    color: var(--primary);
    line-height: 1;
}

.not-found-title {
    font-size: 28px;
    margin: 16px 0 8px;
}

.not-found-desc {
    color: var(--text-muted);
    margin-bottom: 24px;
}

/* 页脚 */
.site-footer {
    border-top: 1px solid var(--border);
    background: var(--surface);
    padding: 40px 0;
    margin-top: 60px;
}

.footer-container {
    max-width: 1240px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    color: var(--text-muted);
}

.footer-brand {
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 4px;
}

/* 响应式适配 (Mobile & Tablet) */
@media (max-width: 860px) {
    .report-layout {
        grid-template-columns: 1fr;
    }
    .report-toc-aside {
        display: none; /* 移动端隐藏吸顶大纲，保持干净单栏 */
    }
    .stats-row {
        grid-template-columns: repeat(2, 1fr);
    }
    .featured-header {
        flex-direction: column;
        gap: 16px;
    }
    .archive-grid {
        grid-template-columns: 1fr;
    }
    .section-top {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
    }
    .search-box {
        width: 100%;
    }
    .footer-container {
        flex-direction: column;
        gap: 16px;
        text-align: center;
    }
}
"""
    (ASSETS_DIR / "style.css").write_text(css_content, encoding="utf-8")

    js_content = """// AI Daily Radar - Client-side Interactions
document.addEventListener('DOMContentLoaded', () => {
    // 1. 主题切换 (Light / Dark mode)
    const themeBtn = document.getElementById('theme-toggle');
    const savedTheme = localStorage.getItem('radar_theme') || 'dark';
    
    function applyTheme(theme) {
        document.body.className = theme === 'light' ? 'theme-light' : 'theme-dark';
        if (themeBtn) {
            themeBtn.querySelector('.theme-icon').textContent = theme === 'light' ? '☀️' : '🌙';
        }
        localStorage.setItem('radar_theme', theme);
    }

    applyTheme(savedTheme);

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const current = document.body.classList.contains('theme-light') ? 'light' : 'dark';
            applyTheme(current === 'light' ? 'dark' : 'light');
        });
    }

    // 2. 往期归档快速搜索过滤
    const searchInput = document.getElementById('archive-search');
    const archiveGrid = document.getElementById('archive-grid');
    const noResults = document.getElementById('no-search-results');

    if (searchInput && archiveGrid) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim().toLowerCase();
            const cards = archiveGrid.querySelectorAll('.archive-card');
            let visibleCount = 0;

            cards.forEach(card => {
                const searchContent = card.getAttribute('data-search').toLowerCase();
                if (!query || searchContent.includes(query)) {
                    card.style.display = 'flex';
                    visibleCount++;
                } else {
                    card.style.display = 'none';
                }
            });

            if (noResults) {
                noResults.className = visibleCount === 0 ? 'no-results' : 'no-results hidden';
            }
        });
    }
});
"""
    (ASSETS_DIR / "app.js").write_text(js_content, encoding="utf-8")


def main():
    print(f"🚀 开始构建 AI Daily Radar 静态网站...")
    start_time = datetime.now()

    # 清理并重置 dist 目录
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 写入静态 CSS/JS
    write_assets()

    # 读取并解析全部日报
    reports = get_all_reports()
    print(f"📦 成功读取 {len(reports)} 份历史日报")

    # 生成首页
    index_html = build_index_page(reports)
    (DIST_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # 生成 404 页面
    not_found_html = build_404_page()
    (DIST_DIR / "404.html").write_text(not_found_html, encoding="utf-8")

    # 生成各期详情页 /reports/YYYY-MM-DD/index.html
    for idx, report in enumerate(reports):
        date_str = report["date"]
        report_dir = DIST_DIR / "reports" / date_str
        report_dir.mkdir(parents=True, exist_ok=True)

        prev_report = reports[idx + 1] if idx + 1 < len(reports) else None
        next_report = reports[idx - 1] if idx > 0 else None

        page_html = build_report_page(report, prev_report, next_report)
        (report_dir / "index.html").write_text(page_html, encoding="utf-8")

    duration = (datetime.now() - start_time).total_seconds()
    print(f"✅ 构建完成！耗时 {duration:.2f}s，静态站点已就绪于: {DIST_DIR}")


if __name__ == "__main__":
    main()
