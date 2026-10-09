#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Daily Radar - 自动化抓取与日报生成脚本
1. 抓取 sources.md 所列各信息源（App Store、QMReader、官方RSS、社区热榜等）
2. 将汇总的一手候选素材提交给 Gemini API (gemini-2.5-flash) 单次推理
3. 输出 reports/YYYY-MM-DD.md 与 reports/YYYY-MM-DD.dingtalk.md
4. 更新 reports/appstore-snapshot.json
"""

import os
import sys
import re
import json
import ssl
import time
import datetime
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

# 禁用全局 SSL 严格证书校验以避免个别源握手异常
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def http_get(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"[WARN] HTTP GET failed for {url}: {e}", file=sys.stderr)
        return None

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def fetch_appstore(date_str):
    print("-> 抓取 App Store 5 区榜单...")
    regions = ['cn', 'us', 'jp', 'gb', 'hk']
    current = {}
    for r in regions:
        url = f"https://rss.applemarketingtools.com/api/v2/{r}/apps/top-free/50/apps.json"
        raw = http_get(url, timeout=10)
        if raw:
            try:
                data = json.loads(raw)
                items = data.get("feed", {}).get("results", [])
                current[r] = [{"rank": i + 1, "id": str(app.get("id")), "name": app.get("name")} for i, app in enumerate(items)]
            except Exception as e:
                print(f"[WARN] App Store JSON parse failed for {r}: {e}", file=sys.stderr)

    snapshot_path = "reports/appstore-snapshot.json"
    old_regions = {}
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                old_regions = old_data.get("regions", {})
        except Exception as e:
            print(f"[WARN] Read old appstore snapshot failed: {e}", file=sys.stderr)

    diffs = {}
    for r in regions:
        old_map = {item["id"]: item for item in old_regions.get(r, [])}
        curr_items = current.get(r, [])
        diffs[r] = []
        for item in curr_items:
            old_item = old_map.get(item["id"])
            if not old_item:
                diffs[r].append(f"新进榜: {item['name']}({item['rank']})")
            elif old_item["rank"] - item["rank"] >= 10:
                diffs[r].append(f"排名跃升: {item['name']} {old_item['rank']}->{item['rank']}")

    # 更新快照
    if current:
        try:
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump({"date": date_str, "note": "top-free 50", "regions": current}, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"[WARN] Write appstore snapshot failed: {e}", file=sys.stderr)

    return diffs

def fetch_qmreader():
    print("-> 抓取 QMReader 海外博主/通讯聚合...")
    url = "https://rss.qiaomu.ai/api/entries"
    raw = http_get(url, timeout=15)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        entries = data.get("entries", [])
        whitelist = {
            'simonwillison', 'importai', 'interconnects', 'oneusefulthing', 
            'latentspace', 'tldrai', 'bensbites', 'superhuman_ai', 'chinai', 
            'construction-physics', 'huggingface'
        }
        filtered = []
        for e in entries:
            if e.get("sourceId") in whitelist:
                filtered.append({
                    "source": f"QMReader/{e.get('sourceId')}",
                    "title": e.get("titleZh") or e.get("title") or "",
                    "link": e.get("link") or "",
                    "summary": clean_html(e.get("summaryZh") or e.get("summary") or "")[:150],
                })
        return filtered[:12]
    except Exception as e:
        print(f"[WARN] QMReader parse error: {e}", file=sys.stderr)
        return []

def fetch_rss_feed(source_name, url, max_items=3):
    raw = http_get(url, timeout=12)
    if not raw:
        return []
    items = []
    try:
        # 尝试标准 XML 解析
        root = ET.fromstring(raw)
        for item in root.findall(".//item")[:max_items]:
            t = item.findtext("title", "").strip()
            l = item.findtext("link", "").strip()
            d = clean_html(item.findtext("description", ""))[:150]
            if t and l:
                items.append({"source": source_name, "title": t, "link": l, "summary": d})
        if not items:
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall("atom:entry", ns)[:max_items]:
                t = entry.findtext("atom:title", "", ns).strip()
                l_elem = entry.find("atom:link", ns)
                l = l_elem.attrib.get("href", "") if l_elem is not None else ""
                d = clean_html(entry.findtext("atom:summary", "", ns))[:150]
                if t and l:
                    items.append({"source": source_name, "title": t, "link": l, "summary": d})
    except Exception:
        # Regex 容错兜底
        item_blocks = re.findall(r'<item>(.*?)</item>', raw, re.DOTALL)
        for block in item_blocks[:max_items]:
            title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
            link_m = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
            desc_m = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
            if title_m and link_m:
                t = clean_html(title_m.group(1))
                l = clean_html(link_m.group(1))
                d = clean_html(desc_m.group(1) if desc_m else "")[:150]
                items.append({"source": source_name, "title": t, "link": l, "summary": d})
    return items

def fetch_hackernews():
    print("-> 抓取 Hacker News 热门...")
    url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    raw = http_get(url, timeout=8)
    if not raw:
        return []
    try:
        ids = json.loads(raw)[:5]
        items = []
        for sid in ids:
            item_raw = http_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=6)
            if item_raw:
                d = json.loads(item_raw)
                title = d.get("title", "")
                link = d.get("url") or f"https://news.ycombinator.com/item?id={sid}"
                items.append({"source": "Hacker News", "title": title, "link": link, "summary": ""})
        return items
    except Exception as e:
        print(f"[WARN] HN fetch error: {e}", file=sys.stderr)
        return []

def fetch_dex_weekly():
    print("-> 检查 DEX 周刊 (G 组)...")
    raw = http_get("https://quaily.com/dingyi/feed/atom", timeout=8)
    if not raw:
        return None
    try:
        root = ET.fromstring(raw)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None
        title = entry.findtext("atom:title", "", ns)
        link = entry.find("atom:link", ns).attrib.get("href", "")
        pub_str = entry.findtext("atom:published", "", ns)
        # 检查是否在 7 天内
        pub_dt = datetime.datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        if (now - pub_dt).days > 7:
            print(f"DEX 周刊最新一期已超 7 天 ({pub_str})，跳过")
            return None
        # 检查是否已取材
        issue_m = re.search(r'/p/(\d+)', link)
        if issue_m:
            issue_id = issue_m.group(1)
            # 查 reports/
            if os.system(f'grep -rl "quaily.com/dingyi/p/{issue_id}" reports/ >/dev/null 2>&1') == 0:
                print(f"DEX 周刊 #{issue_id} 之前已取材，跳过")
                return None
            return {"title": title, "link": link, "issue": issue_id}
    except Exception as e:
        print(f"[WARN] DEX weekly check error: {e}", file=sys.stderr)
    return None

def fetch_all_signals(date_str):
    signals = []
    
    # 1. App Store
    app_diffs = fetch_appstore(date_str)
    
    # 2. 官方与垂直 RSS (高优先：建筑、能源与大厂)
    rss_targets = [
        ("AEC Magazine 建筑数字化 (F组)", "https://aecmag.com/feed/"),
        ("Utility Dive 能源/数据中心 (F组)", "https://www.utilitydive.com/feeds/news/"),
        ("NVIDIA Blog (D组)", "https://blogs.nvidia.com/feed/"),
        ("OpenAI News (D组)", "https://openai.com/news/rss.xml"),
        ("Google DeepMind (D组)", "https://deepmind.google/blog/rss.xml"),
        ("TechCrunch AI (E组)", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ]
    for name, feed_url in rss_targets:
        print(f"-> 抓取 {name}...")
        res = fetch_rss_feed(name, feed_url, max_items=2)
        signals.extend(res)

    # 3. QMReader
    qm_entries = fetch_qmreader()
    signals.extend(qm_entries)
        
    # 4. Hacker News
    signals.extend(fetch_hackernews())
    
    # 5. DEX 周刊
    dex = fetch_dex_weekly()
    
    # 保留精选候选在 25 条以内，保证 Token 控制在 Free Tier 极佳阈值
    print(f"-> 汇总共抓取到 {len(signals)} 条候选素材，保留精选子集以优化提示词上下文")
    signals = signals[:25]
    
    return app_diffs, signals, dex

def call_gemini_text(prompt, api_key, max_retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90, context=SSL_CTX) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                candidate = res_data.get('candidates', [{}])[0]
                text = candidate.get('content', {}).get('parts', [{}])[0].get('text', '').strip()
                return text
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode('utf-8')
            except Exception:
                pass
            print(f"[WARN] HTTP {e.code} on attempt {attempt}:\n{err_body}", file=sys.stderr)
            if e.code in (429, 500, 503) and attempt < max_retries:
                wait_sec = attempt * 15
                print(f"-> 遇到配额或服务波动，等待 {wait_sec} 秒后重试...")
                time.sleep(wait_sec)
            else:
                raise

def format_dingtalk_report(full_report, date_str):
    """
    根据完整版日报，确定性提取出符合钉钉格式的精简版本：
    1. 提取今日 TL;DR
    2. 提取各版块条目：加粗标题 + 关注理由 + 原文链接
    3. 提取 App Store 异动概述
    4. 移除表格，控制在 2000 字内
    """
    lines = full_report.split('\n')
    out = [f"# AI Daily Radar | {date_str}"]
    
    tldr_lines = []
    in_tldr = False
    
    current_section = ''
    items = []
    curr_item = {}
    appstore_lines = []
    in_appstore = False
    
    for line in lines:
        stripped = line.strip()
        if '📌 今日 TL;DR' in line or '今日 TL;DR' in line:
            in_tldr = True
            in_appstore = False
            continue
        elif '📱 App Store' in line:
            in_appstore = True
            in_tldr = False
            current_section = '📱 App Store 榜单异动'
            continue
        elif '📡 源覆盖情况' in line:
            in_appstore = False
            in_tldr = False
            continue
        elif stripped.startswith('## '):
            in_tldr = False
            in_appstore = False
            current_section = stripped.lstrip('#').strip()
            continue
            
        if in_tldr:
            if stripped and not stripped.startswith('##'):
                tldr_lines.append(stripped)
            continue
            
        if in_appstore:
            if stripped and not stripped.startswith('##'):
                appstore_lines.append(stripped)
            continue
            
        if stripped.startswith('### '):
            if curr_item and curr_item.get('title'):
                items.append(curr_item)
            title = stripped.lstrip('#').strip()
            curr_item = {'section': current_section, 'title': title, 'why': '', 'link': ''}
        elif '**为什么值得关注**' in stripped or '**关注理由**' in stripped:
            why_text = re.sub(r'-\s*\*\*.*?\*\*:\s*', '', stripped).strip()
            curr_item['why'] = why_text
        elif '**原文**' in stripped or '**链接**' in stripped or '**来源**' in stripped:
            link_m = re.search(r'https?://[^\s\)]+', stripped)
            curr_item['link'] = link_m.group(0) if link_m else ""

    if curr_item and curr_item.get('title'):
        items.append(curr_item)
        
    if tldr_lines:
        out.append('\n> **今日 TL;DR**\n> ' + '\n> '.join(tldr_lines))
        
    curr_sec = ''
    for it in items:
        if it['section'] != curr_sec:
            curr_sec = it['section']
            out.append(f'\n### {curr_sec}')
        link_str = f" [原文]({it['link']})" if it.get('link') else ""
        why_str = f": {it['why']}" if it.get('why') else ""
        out.append(f"- **{it['title']}**{why_str}{link_str}")
        
    if appstore_lines:
        out.append('\n### 📱 App Store 异动概述')
        out.extend(appstore_lines[:4])
        
    out.append(f'\n---\n[查看完整归档](https://github.com/nengzong/ai-daily-radar/blob/main/reports/{date_str}.md)')
    return '\n'.join(out)

def generate_reports(date_str, app_diffs, signals, dex_item, api_key):
    print("-> 正在调用 Gemini 2.5 Flash 生成完整日报 Markdown (每日仅需 1 次 API 调用)...")
    prompt_full = f"""你是一名 AI 行业情报分析师，为建筑、园区、工厂等「工程物理世界 AI」与设施管理 (FM) 领军企业（博锐尚格 Persagy）的产品经理和技术团队生成每日情报日报。
今天是 {date_str}。请严格按以下要求对提供的当日候选素材进行筛选分析，直接输出符合 reports/{date_str}.md 规范的完整 Markdown 内容（不要输出任何多余的包裹标签或解释）：

### 筛选要求：
1. 精选 8-15 条条目，宁缺毋滥。
2. 硬约束：至少 40% 的条目必须来自海外源（C/D/E/F 组）。所有英文标题与内容必须翻译成高质量中文，保留公司/产品英文原名。
3. 重点分类：
   - 🏭 行业动向：AI 在建筑、园区、工厂、能源、设施管理 (FM) 等空间/资产运营场景的落地信号（优先从 F 组和 D 组取材）。
   - 🤖 技术与案例：Agent、世界模型、AIoT、大模型企业级落地的技术进展与实测案例。
   - 💡 产品灵感：定位、交互范式、展示方式上有借鉴价值的新产品或开源工具。
   {f"- 🎨 设计动态：本期来源为 DEX 周刊 #{dex_item['issue']} ({dex_item['link']})，挑 1-2 条对复杂系统界面或空间可视化有迁移价值的内容。" if dex_item else "- 🎨 设计动态：本周暂无新刊，整节省略。"}
4. 读者背景：读者是公司同事与领导，所有条目都从「对公司物理世界 AI 业务、智能体与系统架构有什么参考价值」的视角来写，严禁出现“值得做”、“赚钱”、“副业”、“独立变现”等个人化措辞。
5. 每条条目格式：加粗标题 + 摘要 + 为什么值得关注（1-2句） + 原文链接（必须是公网真实链接）。

### 输入候选素材：
{json.dumps(signals, ensure_ascii=False, indent=1)}

### App Store 榜单异动：
{json.dumps(app_diffs, ensure_ascii=False, indent=1)}

### 输出结构要求：
1. 标题：# AI Daily Radar | YYYY-MM-DD
2. 摘要行：> 共 N 条 · 覆盖 M 个源 · 海外信源占比 X%
3. 📌 今日 TL;DR（3-4句核心洞察）
4. 🏭 行业动向
5. 🤖 技术与案例
6. 💡 产品灵感
{"" if not dex_item else "7. 🎨 设计动态"}
8. 📱 App Store 榜单异动
9. 📡 源覆盖情况
"""
    full_report = call_gemini_text(prompt_full, api_key)
    # 去除可能的外层 markdown 代码块
    if full_report.startswith("```markdown"):
        full_report = full_report[11:]
    elif full_report.startswith("```"):
        full_report = full_report[3:]
    if full_report.endswith("```"):
        full_report = full_report[:-3]
    full_report = full_report.strip()

    print("-> 正在由脚本本地确定性生成钉钉群精简版 Markdown (不消耗模型配额)...")
    dingtalk_report = format_dingtalk_report(full_report, date_str)

    return full_report, dingtalk_report

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY environment variable not set!", file=sys.stderr)
        sys.exit(1)
        
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"=== 开始生成 AI Daily Radar 日报 ({today_str}) ===")
    
    app_diffs, signals, dex_item = fetch_all_signals(today_str)
    print(f"-> 抓取完成，共获得 {len(signals)} 条候选信号")
    
    try:
        full_md, dingtalk_md = generate_reports(today_str, app_diffs, signals, dex_item, api_key)
        
        if not full_md or not dingtalk_md:
            raise ValueError("Gemini 未能返回完整的 full_report 或 dingtalk_report")
            
        full_path = f"reports/{today_str}.md"
        dingtalk_path = f"reports/{today_str}.dingtalk.md"
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(full_md.strip() + "\n")
        with open(dingtalk_path, "w", encoding="utf-8") as f:
            f.write(dingtalk_md.strip() + "\n")
            
        print(f"[SUCCESS] 成功写入 {full_path} ({os.path.getsize(full_path)} 字节)")
        print(f"[SUCCESS] 成功写入 {dingtalk_path} ({os.path.getsize(dingtalk_path)} 字节)")
    except Exception as e:
        print(f"[ERROR] 日报生成失败: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
