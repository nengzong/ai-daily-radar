#!/usr/bin/env python3
"""把日报 Markdown 转成邮件可渲染的 HTML(只用标准库,零依赖)。

支持的语法子集:# ## ### 标题、**加粗**、`代码`、[文字](链接)、裸链接、
> 引用块、- / 数字. 列表、--- 分隔线、普通段落。
用法: python3 md2html.py < input.md > output.html
"""
import html
import re
import sys

LINK_STYLE = 'color:#1a73e8;text-decoration:none;word-break:break-all'


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background:#f2f2f2;padding:1px 5px;border-radius:3px;'
        r'font-size:90%">\1</code>',
        text,
    )
    text = re.sub(
        r'\[([^\]]+)\]\((https?://[^\s)]+)\)',
        rf'<a href="\2" style="{LINK_STYLE}">\1</a>',
        text,
    )
    # 裸链接;负向断言避免二次处理上面已生成的 href="..." 和 >url</a>
    text = re.sub(
        r'(?<!["\>])(https?://[^\s<>"·]+)',
        rf'<a href="\1" style="{LINK_STYLE}">\1</a>',
        text,
    )
    return text


def flush_para(buf, out):
    if buf:
        out.append('<p style="margin:8px 0">%s</p>' % '<br>'.join(buf))
        buf.clear()


def flush_list(items, out):
    if items:
        lis = ''.join('<li style="margin:4px 0">%s</li>' % i for i in items)
        out.append('<ul style="margin:8px 0;padding-left:22px">%s</ul>' % lis)
        items.clear()


CELL_STYLE = 'padding:6px 10px;border:1px solid #ddd;text-align:left'


def flush_table(rows, out):
    if not rows:
        return
    # 第二行若是 |---|---| 分隔行则第一行作为表头
    header = None
    body = rows
    if len(rows) >= 2 and all(re.match(r'^:?-+:?$', c) for c in rows[1]):
        header, body = rows[0], rows[2:]
    parts = ['<table style="border-collapse:collapse;margin:12px 0;font-size:13px">']
    if header:
        parts.append(
            '<tr>%s</tr>'
            % ''.join(
                '<th style="%s;background:#f5f5f5">%s</th>' % (CELL_STYLE, c)
                for c in header
            )
        )
    for row in body:
        parts.append(
            '<tr>%s</tr>'
            % ''.join('<td style="%s">%s</td>' % (CELL_STYLE, c) for c in row)
        )
    parts.append('</table>')
    out.append(''.join(parts))
    rows.clear()


def convert(md):
    out, para, items, quote, table = [], [], [], [], []
    for raw in md.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|') and len(stripped) > 1:
            flush_para(para, out)
            flush_list(items, out)
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if all(re.match(r'^:?-+:?$', c) for c in cells):
                table.append(cells)  # 分隔行,flush_table 里识别
            else:
                table.append([inline(c) for c in cells])
            continue
        flush_table(table, out)
        if stripped.startswith('&gt;') or stripped.startswith('>'):
            flush_para(para, out)
            flush_list(items, out)
            quote.append(inline(stripped.lstrip('>').strip()))
            continue
        if quote:
            out.append(
                '<blockquote style="margin:12px 0;padding:8px 14px;'
                'border-left:3px solid #f0ad4e;background:#fdf7ec;color:#664d03">'
                '%s</blockquote>' % '<br>'.join(quote)
            )
            quote.clear()
        if not stripped:
            flush_para(para, out)
            flush_list(items, out)
            continue
        m = re.match(r'^(#{1,3})\s+(.*)$', stripped)
        if m:
            flush_para(para, out)
            flush_list(items, out)
            level = len(m.group(1))
            style = {
                1: 'font-size:22px;margin:4px 0 16px;padding-bottom:10px;'
                   'border-bottom:2px solid #e8e8e8',
                2: 'font-size:18px;margin:28px 0 10px',
                3: 'font-size:15px;margin:20px 0 6px',
            }[level]
            out.append(
                '<h%d style="%s">%s</h%d>' % (level, style, inline(m.group(2)), level)
            )
            continue
        if re.match(r'^(-{3,}|\*{3,})$', stripped):
            flush_para(para, out)
            flush_list(items, out)
            out.append(
                '<hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0">'
            )
            continue
        m = re.match(r'^[-*]\s+(.*)$', stripped)
        if m:
            flush_para(para, out)
            items.append(inline(m.group(1)))
            continue
        flush_list(items, out)
        para.append(inline(stripped))
    flush_para(para, out)
    flush_list(items, out)
    flush_table(table, out)
    if quote:
        out.append(
            '<blockquote style="margin:12px 0;padding:8px 14px;'
            'border-left:3px solid #f0ad4e;background:#fdf7ec;color:#664d03">'
            '%s</blockquote>' % '<br>'.join(quote)
        )
    body = '\n'.join(out)
    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,'
        "'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;"
        'font-size:14px;line-height:1.7;color:#333;max-width:740px;'
        'margin:0 auto;padding:16px">%s</div>' % body
    )


if __name__ == '__main__':
    sys.stdout.write(convert(sys.stdin.read()))
