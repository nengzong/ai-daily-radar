#!/usr/bin/env python3
"""AI Daily Radar 静态网页生成器 (Zero-dependency SSG - 移动端深度优化版)

扫描 reports/*.md (排除 .dingtalk.md), 生成高颜值的现代静态网站至 dist/ 目录。
适配 Cloudflare Pages 静态托管，完美兼容 iPhone/Android 手机移动端与宽屏桌面端。

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
    # 裸链接
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

        if "TL;DR" in sec_title or "今日导读" in sec_title:
            data["tldr"] = sec_text.replace("\n", " ").strip()

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
    """渲染分类章节内部条目"""
    output = []
    items_buf = []
    current_item = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_item:
                items_buf.append(current_item)
                current_item = None
            continue

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
                current_item["link"] = re.sub(r'^链接[：:]\s*', '', stripped)
            else:
                current_item["others"].append(stripped)
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            content = stripped[2:].strip()
            output.append(f'<li class="list-item">{parse_inline_markdown(content)}</li>')
            continue

        if stripped.startswith("> "):
            content = stripped[2:].strip()
            output.append(f'<blockquote class="quote-box">{parse_inline_markdown(content)}</blockquote>')
            continue

        output.append(f'<p class="text-paragraph">{parse_inline_markdown(stripped)}</p>')

    if current_item:
        items_buf.append(current_item)

    if items_buf:
        item_cards = []
        for idx, itm in enumerate(items_buf, 1):
            title_html = parse_inline_markdown(itm["title"])
            summary_html = f'<div class="item-summary"><span class="badge badge-summary">摘要</span> {parse_inline_markdown(itm["summary"])}</div>' if itm["summary"] else ""
            why_html = f'<div class="item-why"><span class="badge badge-why">为什么值得关注</span> {parse_inline_markdown(itm["why"])}</div>' if itm["why"] else ""
            
            link_html = ""
            if itm["link"]:
                url = itm["link"].strip()
                domain = re.sub(r'^https?://(?:www\.)?([^/]+).*$', r'\1', url)
                link_html = f'<div class="item-footer"><a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" class="source-button"><svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7zm-2 16H5V7h7V5H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h7v-2z"/></svg> 查看原文 · {html.escape(domain)}</a></div>'

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
    """收集 reports/*.md"""
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
    """生成统一骨架的 HTML 页面（移动端 Safe-Area + 原生手感）"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#090d16">
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
    <!-- 顶部极简导航栏 (手机端紧凑) -->
    <header class="site-header">
        <div class="header-container">
            <a href="/" class="brand-logo">
                <span class="logo-icon">📡</span>
                <span class="logo-text">AI Radar</span>
                <span class="logo-badge">每日早报</span>
            </a>
            <nav class="main-nav">
                <a href="/" class="nav-link {'active' if active_nav == 'home' else ''}">首页</a>
                <a href="/#archive" class="nav-link {'active' if active_nav == 'archive' else ''}">往期</a>
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

    <!-- 手机端轻量吐司通知 -->
    <div id="toast" class="toast-notify" role="alert">已复制报告链接</div>

    <!-- 页脚 -->
    <footer class="site-footer">
        <div class="footer-container">
            <div class="footer-left">
                <p class="footer-brand">📡 AI Daily Radar</p>
                <p class="footer-desc">每天自动扫描 40+ 个前沿信息源 · 业务视角提炼</p>
            </div>
            <div class="footer-right">
                <p>托管于 Cloudflare Pages · 全球加速</p>
                <p class="copyright">&copy; 2026 AI Daily Radar</p>
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
    total_reports = len(reports)
    total_items = sum(r.get("item_count", 0) for r in reports)

    archive_cards = []
    for r in reports:
        date_str = r["date"]
        subtitle = r.get("subtitle", "")
        item_count = r.get("item_count", 0)
        tldr_snippet = r.get("tldr", "")[:120] + ("..." if len(r.get("tldr", "")) > 120 else "")
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
                <span>今日送达 · {latest['date']}</span>
            </div>
            <h1 class="hero-title">AI Daily Radar</h1>
            <p class="hero-subtitle">每日雷达精选全球 AI 行业动向、前沿技术与产品灵感</p>
            
            <div class="hero-actions">
                <a href="{latest_url}" class="primary-btn">
                    <span>阅读今日最新早报</span>
                    <svg class="icon" viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M5 12h14M12 5l7 7-7 7"/></svg>
                </a>
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
                    <span class="stat-label">监控信源</span>
                </div>
                <div class="stat-card">
                    <span class="stat-num">08:30</span>
                    <span class="stat-label">准点推送</span>
                </div>
            </div>
        </div>
    </section>

    <!-- 今日速览 -->
    <section class="latest-featured-section">
        <div class="section-top">
            <h2 class="section-title">今日早报速览</h2>
            <a href="{latest_url}" class="view-all-link">进入完整版 &rarr;</a>
        </div>
        <div class="featured-card">
            <div class="featured-header">
                <div>
                    <span class="badge badge-featured">TODAY'S HIGHLIGHT</span>
                    <h3 class="featured-title">{latest['title']}</h3>
                    <p class="featured-meta">{html.escape(latest.get('subtitle', ''))}</p>
                </div>
                <a href="{latest_url}" class="featured-btn">完整版 &rarr;</a>
            </div>
            <div class="featured-tldr">
                <div class="tldr-label">📌 核心概要 (TL;DR)</div>
                <p>{parse_inline_markdown(latest.get('tldr', ''))}</p>
            </div>
        </div>
    </section>

    <!-- 往期归档与快速检索 -->
    <section id="archive" class="archive-section">
        <div class="section-top">
            <div>
                <h2 class="section-title">往期情报归档</h2>
                <p class="section-desc">共计 {total_reports} 期日报可供随时查阅</p>
            </div>
            <div class="search-box">
                <svg class="search-icon" viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                <input type="text" id="archive-search" placeholder="输入日期或关键词搜索..." aria-label="搜索往期日报">
            </div>
        </div>

        <div id="archive-grid" class="archive-grid">
            {archive_html}
        </div>
        <div id="no-search-results" class="no-results hidden">
            <p>未找到符合搜索条件的日报</p>
        </div>
    </section>
    """
    return render_html_page("AI Daily Radar · 每日 AI 情报雷达", content, active_nav="home")


def build_report_page(report: dict, prev_report: dict = None, next_report: dict = None) -> str:
    """生成日报详情页 reports/YYYY-MM-DD/index.html"""
    date_str = report["date"]
    title = report["title"]
    subtitle = report.get("subtitle", "")

    # 目录导航与手机水平药丸胶囊
    toc_items = []
    mobile_pills = []
    for item in report.get("toc", []):
        raw_t = item["title"]
        clean_name = re.sub(r'^[^\w\u4e00-\u9fa5]+', '', raw_t)
        clean_name = clean_name.split()[0] if clean_name else raw_t
        toc_items.append(f'<li><a href="#{item["id"]}" class="toc-link">{parse_inline_markdown(item["title"])}</a></li>')
        mobile_pills.append(f'<a href="#{item["id"]}" class="mobile-pill">{html.escape(clean_name)}</a>')

    toc_html = "\n".join(toc_items)
    mobile_pills_html = "\n".join(mobile_pills)

    # 翻页按钮
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
        <!-- 面包屑与标题 -->
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
                <button class="share-btn" onclick="handleShare('{html.escape(title)}', '{date_str}')">
                    <svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>
                    分享 / 复制
                </button>
            </div>

            <!-- 手机端横向快捷章节滑动条 -->
            <div class="mobile-section-nav">
                <div class="mobile-pills-scroll">
                    {mobile_pills_html}
                </div>
            </div>
        </div>

        <div class="report-layout">
            <!-- 桌面端吸顶大纲 -->
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

            <!-- 正文内容 -->
            <article class="report-article-body">
                {report["html_body"]}

                <!-- 翻页 -->
                <div class="report-nav-footer">
                    {"".join(nav_buttons)}
                </div>
            </article>
        </div>
    </div>

    <!-- 手机端专用悬浮操作栏 (底部安全区友好) -->
    <div class="mobile-bottom-bar">
        <button class="mobile-bar-btn" onclick="toggleMobileToc()">
            <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>
            <span>大纲目录</span>
        </button>
        <button class="mobile-bar-btn" onclick="handleShare('{html.escape(title)}', '{date_str}')">
            <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>
            <span>一键分享</span>
        </button>
        <button class="mobile-bar-btn" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">
            <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z"/></svg>
            <span>回到顶部</span>
        </button>
    </div>

    <!-- 手机端目录抽屉 -->
    <div id="mobile-toc-drawer" class="mobile-toc-drawer" onclick="if(event.target === this) toggleMobileToc()">
        <div class="drawer-panel">
            <div class="drawer-header">
                <span class="drawer-title">📑 报告大纲</span>
                <button class="drawer-close" onclick="toggleMobileToc()">&times;</button>
            </div>
            <ul class="drawer-list">
                {toc_html}
            </ul>
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
    """写入 CSS 与 JS 静态资源（移动端极致优化）"""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    css_content = """/* AI Daily Radar - Mobile & Desktop Responsive Design System */

:root {
    --font-main: 'Plus Jakarta Sans', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 深色模式默认 (Sleek OLED-Friendly Dark) */
body.theme-dark {
    --bg: #090d16;
    --surface: #111726;
    --surface-hover: #172035;
    --surface-glass: rgba(17, 23, 38, 0.85);
    --border: #1f2a44;
    --border-light: rgba(255, 255, 255, 0.08);
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --primary: #38bdf8;
    --primary-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
    --accent: #f59e0b;
    --accent-bg: rgba(245, 158, 11, 0.14);
    --badge-bg: rgba(56, 189, 248, 0.14);
    --badge-text: #38bdf8;
    --card-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    --bottom-bar-bg: rgba(17, 23, 38, 0.92);
}

/* 浅色模式 */
body.theme-light {
    --bg: #f8fafc;
    --surface: #ffffff;
    --surface-hover: #f1f5f9;
    --surface-glass: rgba(255, 255, 255, 0.9);
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
    --card-shadow: 0 8px 25px -5px rgba(0, 0, 0, 0.05);
    --bottom-bar-bg: rgba(255, 255, 255, 0.95);
}

/* 基础重置与手机体验适配 */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-tap-highlight-color: transparent;
}

html {
    scroll-behavior: smooth;
    font-size: 16px;
    height: 100%;
}

body {
    background-color: var(--bg);
    color: var(--text);
    font-family: var(--font-main);
    line-height: 1.72;
    transition: background-color 0.25s ease, color 0.25s ease;
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
    min-height: 100%;
    display: flex;
    flex-direction: column;
    padding-top: env(safe-area-inset-top);
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
    max-width: 1200px;
    margin: 0 auto;
    padding: 12px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.brand-logo {
    display: flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    color: var(--text);
}

.logo-icon {
    font-size: 22px;
}

.logo-text {
    font-size: 18px;
    font-weight: 800;
    letter-spacing: -0.4px;
    background: var(--primary-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.logo-badge {
    font-size: 11px;
    font-weight: 600;
    background: var(--badge-bg);
    color: var(--badge-text);
    padding: 2px 7px;
    border-radius: 99px;
}

.main-nav {
    display: flex;
    align-items: center;
    gap: 16px;
}

.nav-link {
    text-decoration: none;
    color: var(--text-muted);
    font-weight: 600;
    font-size: 14px;
    padding: 6px 4px;
}

.nav-link.active, .nav-link:hover {
    color: var(--primary);
}

.theme-toggle-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    width: 36px;
    height: 36px;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: var(--transition);
}

/* 主容器 */
.site-main {
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
    padding: 24px 20px 80px;
    flex: 1;
}

/* Hero Section */
.hero-section {
    padding: 32px 0 20px;
    text-align: center;
}

.hero-content {
    max-width: 780px;
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
    padding: 5px 14px;
    border-radius: 99px;
    margin-bottom: 16px;
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
    font-size: clamp(28px, 6vw, 48px);
    font-weight: 800;
    letter-spacing: -1px;
    line-height: 1.15;
    margin-bottom: 12px;
    background: var(--primary-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-subtitle {
    font-size: 16px;
    color: var(--text-muted);
    max-width: 580px;
    margin: 0 auto 24px;
    line-height: 1.6;
}

.hero-actions {
    display: flex;
    justify-content: center;
    margin-bottom: 32px;
}

.primary-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--primary-gradient);
    color: #ffffff;
    font-weight: 600;
    font-size: 15px;
    padding: 13px 28px;
    border-radius: 12px;
    text-decoration: none;
    box-shadow: 0 4px 18px rgba(56, 189, 248, 0.35);
    min-height: 48px;
}

/* 统计卡片条 */
.stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    max-width: 720px;
    margin: 0 auto;
}

.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 8px;
    text-align: center;
}

.stat-num {
    font-size: 22px;
    font-weight: 800;
    color: var(--primary);
    line-height: 1.1;
    display: block;
}

.stat-label {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
    display: block;
}

/* 今日头条速览卡片 */
.latest-featured-section {
    margin: 36px 0;
}

.section-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 16px;
    gap: 12px;
}

.section-title {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.4px;
}

.section-desc {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 3px;
}

.view-all-link {
    font-size: 14px;
    font-weight: 600;
    color: var(--primary);
    text-decoration: none;
    white-space: nowrap;
}

.featured-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 22px;
    box-shadow: var(--card-shadow);
}

.featured-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
    gap: 16px;
}

.badge-featured {
    font-size: 11px;
    font-weight: 700;
    background: var(--accent-bg);
    color: var(--accent);
    padding: 3px 8px;
    border-radius: 6px;
    display: inline-block;
    margin-bottom: 8px;
}

.featured-title {
    font-size: 20px;
    font-weight: 700;
    line-height: 1.35;
}

.featured-meta {
    font-size: 13px;
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
    white-space: nowrap;
}

.featured-tldr {
    background: rgba(0, 0, 0, 0.18);
    border-radius: 12px;
    padding: 16px 18px;
    border-left: 4px solid var(--primary);
    font-size: 15px;
    line-height: 1.7;
}

body.theme-light .featured-tldr {
    background: #f1f5f9;
}

.tldr-label {
    font-weight: 700;
    font-size: 13.5px;
    color: var(--primary);
    margin-bottom: 6px;
}

/* 往期归档卡片 */
.archive-section {
    margin: 48px 0;
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
    padding: 10px 12px 10px 36px;
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
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
    margin-top: 16px;
}

.archive-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
    text-decoration: none;
    color: var(--text);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: var(--transition);
}

.archive-card:active {
    transform: scale(0.98);
}

.archive-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.archive-date {
    font-size: 17px;
    font-weight: 700;
}

.archive-count {
    font-size: 11.5px;
    font-weight: 600;
    background: var(--badge-bg);
    color: var(--badge-text);
    padding: 2px 7px;
    border-radius: 6px;
}

.archive-subtitle {
    font-size: 12.5px;
    color: var(--text-muted);
    margin-bottom: 10px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.archive-snippet {
    font-size: 13.5px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-bottom: 14px;
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
    padding: 48px 0;
    color: var(--text-muted);
}

.hidden {
    display: none;
}

/* ================= 报告详情页 ================= */

.report-container {
    max-width: 1080px;
    margin: 0 auto;
}

.report-header {
    margin-bottom: 24px;
    padding-bottom: 18px;
    border-bottom: 1px solid var(--border);
}

.breadcrumb {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12.5px;
    color: var(--text-muted);
    margin-bottom: 12px;
}

.breadcrumb a {
    color: var(--text-muted);
    text-decoration: none;
}

.report-main-title {
    font-size: clamp(22px, 5vw, 32px);
    font-weight: 800;
    letter-spacing: -0.5px;
    line-height: 1.25;
    margin-bottom: 12px;
}

.report-meta-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
}

.report-date-badge, .report-subtitle-badge {
    font-size: 12.5px;
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 4px 10px;
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
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    min-height: 32px;
}

/* 手机端横向滑动快速跳转药丸 */
.mobile-section-nav {
    display: none; /* 桌面端隐藏，手机端显示 */
    margin-top: 14px;
    width: 100%;
}

.mobile-pills-scroll {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 4px 0;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
}

.mobile-pills-scroll::-webkit-scrollbar {
    display: none;
}

.mobile-pill {
    white-space: nowrap;
    font-size: 12.5px;
    font-weight: 600;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 14px;
    border-radius: 99px;
    text-decoration: none;
    flex-shrink: 0;
}

.mobile-pill:active {
    background: var(--primary);
    color: #fff;
    border-color: var(--primary);
}

/* 详情页布局 */
.report-layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: 36px;
    align-items: start;
}

.report-toc-aside {
    position: sticky;
    top: 80px;
}

.toc-sticky-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
}

.toc-header {
    font-size: 13.5px;
    font-weight: 700;
    margin-bottom: 10px;
    color: var(--text);
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-light);
}

.toc-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
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
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid var(--border-light);
}

.back-to-top {
    font-size: 12px;
    color: var(--text-muted);
    text-decoration: none;
}

/* 报告正文区块 */
.report-article-body {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.content-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 22px;
    box-shadow: var(--card-shadow);
}

.tldr-card {
    border-left: 4px solid var(--primary);
}

.card-header {
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-light);
}

.section-heading {
    font-size: 19px;
    font-weight: 700;
}

.items-grid {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.article-item {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 16px;
}

body.theme-light .article-item {
    background: #f8fafc;
}

.item-header {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 10px;
}

.item-number {
    font-size: 12px;
    font-weight: 800;
    color: var(--primary);
    background: var(--badge-bg);
    padding: 2px 7px;
    border-radius: 5px;
    margin-top: 2px;
}

.item-title {
    font-size: 16px;
    font-weight: 700;
    line-height: 1.45;
}

.item-summary, .item-why {
    font-size: 14.5px;
    line-height: 1.7;
    margin-top: 8px;
    word-break: break-word;
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
    margin-right: 5px;
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
    margin-top: 6px;
}

.item-footer {
    margin-top: 14px;
    padding-top: 10px;
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
    padding: 6px 14px;
    border-radius: 8px;
    background: var(--badge-bg);
    min-height: 36px;
}

.source-button:active {
    background: var(--primary);
    color: #fff;
}

.list-item {
    font-size: 14.5px;
    line-height: 1.7;
    margin-bottom: 8px;
    margin-left: 20px;
    word-break: break-word;
}

.quote-box {
    margin: 12px 0;
    padding: 10px 14px;
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

.link, .link-bare {
    color: var(--primary);
    word-break: break-all;
}

/* 翻页按钮 */
.report-nav-footer {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 20px;
}

.prev-next-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
    text-decoration: none;
    color: var(--text);
    display: flex;
    flex-direction: column;
}

.prev-next-btn.next {
    align-items: flex-end;
}

.btn-label {
    font-size: 11.5px;
    color: var(--text-muted);
}

.btn-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--primary);
    margin-top: 2px;
}

/* 手机底部常驻悬浮栏 */
.mobile-bottom-bar {
    display: none; /* 桌面端隐藏 */
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bottom-bar-bg);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-top: 1px solid var(--border);
    padding: 8px 16px calc(8px + env(safe-area-inset-bottom));
    z-index: 99;
    justify-content: space-around;
    align-items: center;
}

.mobile-bar-btn {
    background: none;
    border: none;
    color: var(--text);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 12px;
    cursor: pointer;
    min-height: 44px;
    min-width: 56px;
    justify-content: center;
}

.mobile-bar-btn:active {
    color: var(--primary);
}

/* 手机端目录抽屉 */
.mobile-toc-drawer {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.65);
    z-index: 200;
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    align-items: flex-end;
}

.mobile-toc-drawer.open {
    display: flex;
}

.drawer-panel {
    background: var(--surface);
    border-top: 1px solid var(--border);
    border-radius: 20px 20px 0 0;
    width: 100%;
    max-height: 75vh;
    padding: 20px 20px calc(24px + env(safe-area-inset-bottom));
    display: flex;
    flex-direction: column;
    animation: slideUp 0.24s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideUp {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
}

.drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-light);
}

.drawer-title {
    font-size: 16px;
    font-weight: 700;
}

.drawer-close {
    background: var(--surface-hover);
    border: none;
    color: var(--text);
    font-size: 24px;
    line-height: 1;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.drawer-list {
    list-style: none;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.drawer-list .toc-link {
    font-size: 15px;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--surface-hover);
    color: var(--text);
}

/* 吐司通知 */
.toast-notify {
    position: fixed;
    top: 72px;
    left: 50%;
    transform: translateX(-50%) translateY(-20px);
    background: var(--primary);
    color: #ffffff;
    font-size: 13.5px;
    font-weight: 600;
    padding: 8px 18px;
    border-radius: 99px;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
    z-index: 300;
    opacity: 0;
    pointer-events: none;
    transition: all 0.25s ease;
}

.toast-notify.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
}

/* 404 */
.not-found-container {
    text-align: center;
    padding: 80px 0;
}

.not-found-code {
    font-size: 80px;
    font-weight: 900;
    color: var(--primary);
    line-height: 1;
}

.not-found-title {
    font-size: 24px;
    margin: 14px 0 8px;
}

.not-found-desc {
    color: var(--text-muted);
    margin-bottom: 20px;
}

/* 页脚 */
.site-footer {
    border-top: 1px solid var(--border);
    background: var(--surface);
    padding: 28px 0;
    margin-top: 48px;
}

.footer-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12.5px;
    color: var(--text-muted);
}

.footer-brand {
    font-size: 14px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 2px;
}

/* ================= 移动端响应式核心断点 (< 860px) ================= */
@media (max-width: 860px) {
    .site-main {
        padding: 16px 14px calc(76px + env(safe-area-inset-bottom));
    }
    .report-layout {
        grid-template-columns: 1fr;
    }
    .report-toc-aside {
        display: none; /* 桌面侧边栏隐藏 */
    }
    .mobile-section-nav {
        display: block; /* 顶部快捷药丸显示 */
    }
    .mobile-bottom-bar {
        display: flex; /* 底部常驻悬浮栏显示 */
    }
    .stats-row {
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
    }
    .featured-card, .content-card {
        padding: 18px 16px;
        border-radius: 14px;
    }
    .featured-header {
        flex-direction: column;
        gap: 12px;
    }
    .featured-btn {
        width: 100%;
        text-align: center;
        padding: 10px;
    }
    .archive-grid {
        grid-template-columns: 1fr;
    }
    .section-top {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    .search-box {
        width: 100%;
    }
    #archive-search {
        font-size: 16px; /* 防止 iOS Safari 自动缩放页面 */
    }
    .footer-container {
        flex-direction: column;
        gap: 12px;
        text-align: center;
        padding-bottom: calc(56px + env(safe-area-inset-bottom));
    }
    .report-main-title {
        font-size: 22px;
    }
    .item-title {
        font-size: 15.5px;
    }
    .source-button {
        width: 100%;
        justify-content: center;
    }
}
"""
    (ASSETS_DIR / "style.css").write_text(css_content, encoding="utf-8")

    js_content = """// AI Daily Radar - Client-side & Mobile Interactions
document.addEventListener('DOMContentLoaded', () => {
    // 1. 主题切换 (Light / Dark)
    const themeBtn = document.getElementById('theme-toggle');
    const savedTheme = localStorage.getItem('radar_theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    
    function applyTheme(theme) {
        document.body.className = theme === 'light' ? 'theme-light' : 'theme-dark';
        if (themeBtn) {
            themeBtn.querySelector('.theme-icon').textContent = theme === 'light' ? '☀️' : '🌙';
        }
        localStorage.setItem('radar_theme', theme);
        const metaTheme = document.querySelector('meta[name="theme-color"]');
        if (metaTheme) {
            metaTheme.setAttribute('content', theme === 'light' ? '#f8fafc' : '#090d16');
        }
    }

    applyTheme(savedTheme);

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const current = document.body.classList.contains('theme-light') ? 'light' : 'dark';
            applyTheme(current === 'light' ? 'dark' : 'light');
        });
    }

    // 2. 往期快速实时搜索过滤
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

// 轻量 Toast 提示
function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2000);
}

// 手机原生分享或剪贴板兜底
function handleShare(title, date) {
    if (navigator.share) {
        navigator.share({
            title: title + ' · AI Daily Radar',
            text: 'AI Daily Radar · ' + date + ' 每日前沿情报速递',
            url: window.location.href,
        }).catch(() => {});
    } else {
        navigator.clipboard.writeText(window.location.href).then(() => {
            showToast('已复制报告链接到剪贴板！');
        }).catch(() => {
            showToast('链接复制失败，请手动复制浏览器地址栏');
        });
    }
}

// 手机端目录抽屉开关
function toggleMobileToc() {
    const drawer = document.getElementById('mobile-toc-drawer');
    if (!drawer) return;
    drawer.classList.toggle('open');
}

// 抽屉内点击任意目录项自动收起
document.addEventListener('click', (e) => {
    if (e.target.closest('.drawer-list a')) {
        const drawer = document.getElementById('mobile-toc-drawer');
        if (drawer && drawer.classList.contains('open')) {
            drawer.classList.remove('open');
        }
    }
});
"""
    (ASSETS_DIR / "app.js").write_text(js_content, encoding="utf-8")


def main():
    print(f"🚀 开始构建 AI Daily Radar 静态网站 (移动端优化版)...")
    start_time = datetime.now()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    write_assets()

    reports = get_all_reports()
    print(f"📦 成功读取 {len(reports)} 份历史日报")

    index_html = build_index_page(reports)
    (DIST_DIR / "index.html").write_text(index_html, encoding="utf-8")

    not_found_html = build_404_page()
    (DIST_DIR / "404.html").write_text(not_found_html, encoding="utf-8")

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
