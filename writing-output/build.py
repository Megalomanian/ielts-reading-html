#!/usr/bin/env python3
"""Render the IELTS Writing sample library into a single-file HTML page.

Only the JSON content files are edited by hand; index.html is generated.

Usage:
    python -X utf8 build.py --check
    python -X utf8 build.py
"""

from __future__ import annotations

import argparse
import html
import math
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template.html"
CONTENT = ROOT / "content"
OUTPUT = ROOT / "index.html"

MARKER_RE = re.compile(r"\{\{([^{}]+)\}\}")


class Issues:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warns.append(f"{where}: {msg}")


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def load(name: str):
    path = CONTENT / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"缺少内容文件: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} 不是合法 JSON: {exc}")


def words(text: str) -> int:
    """Count words the way an examiner would: whitespace tokens that contain a
    letter or digit. Numbers such as 600,000 count once, and a bare dash or
    ellipsis is not a word."""
    return sum(1 for tok in (text or "").split() if re.search(r"[A-Za-z0-9]", tok))


def para_dom(case_id: str, index: int) -> str:
    return f"essay-{case_id}-{index}"


# ---------------------------------------------------------------- validation


def validate_case(case: dict, issues: Issues) -> dict:
    cid = case.get("id") or "?"
    where = f"case[{cid}]"

    for key in ("id", "cat", "catLabel", "title", "promptZh", "essay", "scores", "structure",
                "lexis", "grammar", "examiner", "pitfalls", "keywords"):
        if not case.get(key):
            issues.err(where, f"缺少字段 {key}")

    essay = case.get("essay") or []
    if len(essay) < 3:
        issues.err(where, "范文至少需要 3 段")
    for i, para in enumerate(essay):
        if not (para.get("text") or "").strip():
            issues.err(where, f"第 {i + 1} 段正文为空")
        if not (para.get("gist") or "").strip():
            issues.warn(where, f"第 {i + 1} 段缺少段意")

    counts = [words(p.get("text", "")) for p in essay]
    total = sum(counts)
    case["_counts"] = counts
    case["_words"] = total

    band = "task1" if case.get("task") == "task1" else "task2"
    low, high = (140, 210) if band == "task1" else (255, 330)
    if total < low or total > high:
        issues.warn(where, f"范文 {total} 词，建议区间 {low}-{high}")

    if len(case.get("scores") or []) not in (4, 5):
        issues.err(where, "scores 需要 4-5 条评分维度")
    kws = case.get("keywords") or []
    seen = set()
    for kw in kws:
        term = (kw.get("term") or "").strip()
        if not term:
            issues.err(where, "存在空关键词")
            continue
        if term in seen:
            issues.err(where, f"关键词重复: {term}")
        seen.add(term)
        idx = kw.get("para")
        if not isinstance(idx, int) or idx < 0 or idx >= len(essay):
            issues.err(where, f"关键词 {term} 的 para 索引越界")
            continue
        quote = kw.get("quote") or ""
        if not quote:
            issues.err(where, f"关键词 {term} 缺少 quote")
            continue
        body = essay[idx].get("text", "")
        if quote not in body:
            issues.err(where, f"关键词 {term} 的 quote 未逐字出现在第 {idx + 1} 段：{quote[:48]}...")

    # every {{marker}} in analysis text must resolve
    blob = json.dumps({k: case.get(k) for k in ("scores", "structure", "grammar", "examiner", "pitfalls", "lexis")},
                      ensure_ascii=False)
    for marker in MARKER_RE.findall(blob):
        if marker.strip() not in seen:
            issues.err(where, f"解析里的标记 {{{{{marker}}}}} 没有对应关键词")

    used = set()
    for marker in MARKER_RE.findall(blob):
        used.add(marker.strip())
    for kw in kws:
        if kw.get("term") not in used:
            issues.warn(where, f"关键词 {kw.get('term')} 未在解析中使用")

    return case


# ---------------------------------------------------------------- rendering


ALLOWED_TAGS = {
    "b": ("<b>", "</b>"),
    "strong": ("<strong>", "</strong>"),
    "em": ("<em>", "</em>"),
    "code": ("<code>", "</code>"),
    "br": ("<br>", ""),
}


def inline(text: str) -> str:
    """Escape text, then restore a small whitelist of inline tags."""
    out = esc(text)
    for tag, (open_tag, close_tag) in ALLOWED_TAGS.items():
        out = out.replace(f"&lt;{tag}&gt;", open_tag)
        if close_tag:
            out = out.replace(f"&lt;/{tag}&gt;", close_tag)
    return out


def render_text(text: str, kws: dict[str, dict]) -> str:
    out: list[str] = []
    pos = 0
    for match in MARKER_RE.finditer(text or ""):
        out.append(inline((text or "")[pos:match.start()]))
        term = match.group(1).strip()
        info = kws.get(term)
        if not info:
            out.append(esc(term))
        else:
            out.append(
                '<button type="button" class="kw"'
                f' data-para="{esc(para_dom(info["_cid"], info["para"]))}"'
                f' data-quote="{esc(info["quote"])}"'
                f' data-label="{esc(info.get("label") or ("定位第 " + "ABCDE"[info["para"]] + " 段"))}">{esc(term)}</button>'
            )
        pos = match.end()
    out.append(inline((text or "")[pos:]))
    return "".join(out)


PALETTE = ["#0f766e", "#d97706", "#7c3a6d", "#2563eb", "#b91c1c", "#4d7c0f"]
CHART_W, CHART_H = 420, 210
PAD_L, PAD_R, PAD_T, PAD_B = 40, 12, 16, 34


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(value))
    for mult in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= mult * exp:
            return mult * exp
    return 10 * exp


def _svg_open(title: str) -> list[str]:
    return [
        f'<svg class="chart-svg" viewBox="0 0 {CHART_W} {CHART_H}" role="img" '
        f'aria-label="{esc(title)}" preserveAspectRatio="xMidYMid meet">'
    ]


def _grid(top: float, unit: str = "") -> list[str]:
    out = []
    for i in range(5):
        y = PAD_T + (CHART_H - PAD_T - PAD_B) * i / 4
        val = top * (4 - i) / 4
        txt = f"{val:g}"
        out.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{CHART_W - PAD_R}" y2="{y:.1f}" '
                   f'stroke="#e8e1d4" stroke-width="1"/>')
        out.append(f'<text x="{PAD_L - 6}" y="{y + 3.5:.1f}" text-anchor="end" '
                   f'fill="#8a8375" font-size="8.5">{esc(txt)}</text>')
    if unit:
        out.append(f'<text x="{PAD_L - 6}" y="{PAD_T - 6}" text-anchor="end" '
                   f'fill="#8a8375" font-size="7.5">{esc(unit)}</text>')
    return out


def _legend(series: list[dict]) -> list[str]:
    out = []
    x = PAD_L
    for i, s in enumerate(series):
        color = PALETTE[i % len(PALETTE)]
        out.append(f'<rect x="{x}" y="{CHART_H - 15}" width="8" height="8" rx="2" fill="{color}"/>')
        out.append(f'<text x="{x + 11}" y="{CHART_H - 8}" fill="#5b6672" font-size="8.5">{esc(s["name"])}</text>')
        x += 16 + len(str(s["name"])) * 5.4
    return out


def render_bar(chart: dict) -> str:
    cats = [str(c) for c in chart.get("categories", [])]
    series = chart.get("series", [])
    peak = max((max(s.get("values") or [0]) for s in series), default=1)
    top = _nice_max(float(chart.get("yMax") or peak))
    plot_w = CHART_W - PAD_L - PAD_R
    plot_h = CHART_H - PAD_T - PAD_B - 14
    slot = plot_w / max(1, len(cats))
    bw = slot * 0.62 / max(1, len(series))
    out = _svg_open(chart.get("caption") or "bar chart")
    out += _grid(top, chart.get("unit", ""))
    for ci, cat in enumerate(cats):
        base_x = PAD_L + slot * ci + slot * 0.19
        for si, s in enumerate(series):
            val = (s.get("values") or [0])[ci] if ci < len(s.get("values") or []) else 0
            h = plot_h * (float(val) / top)
            x = base_x + bw * si
            out.append(
                f'<rect x="{x:.1f}" y="{PAD_T + plot_h - h:.1f}" width="{bw - 1.5:.1f}" height="{h:.1f}" '
                f'rx="2" fill="{PALETTE[si % len(PALETTE)]}" opacity=".9"/>'
            )
        out.append(f'<text x="{PAD_L + slot * ci + slot / 2:.1f}" y="{CHART_H - 22}" text-anchor="middle" '
                   f'fill="#5b6672" font-size="8.5">{esc(cat)}</text>')
    if len(series) > 1:
        out += _legend(series)
    out.append("</svg>")
    return "".join(out)


def render_line(chart: dict) -> str:
    cats = [str(c) for c in chart.get("categories", [])]
    series = chart.get("series", [])
    peak = max((max(s.get("values") or [0]) for s in series), default=1)
    top = _nice_max(float(chart.get("yMax") or peak))
    plot_w = CHART_W - PAD_L - PAD_R
    plot_h = CHART_H - PAD_T - PAD_B - 14
    step = plot_w / max(1, len(cats) - 1)
    out = _svg_open(chart.get("caption") or "line graph")
    out += _grid(top, chart.get("unit", ""))
    for si, s in enumerate(series):
        pts = []
        for ci, val in enumerate(s.get("values") or []):
            x = PAD_L + step * ci
            y = PAD_T + plot_h - plot_h * (float(val) / top)
            pts.append(f"{x:.1f},{y:.1f}")
        color = PALETTE[si % len(PALETTE)]
        out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
                   f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for p in pts:
            x, y = p.split(",")
            out.append(f'<circle cx="{x}" cy="{y}" r="2.4" fill="#fffdf8" stroke="{color}" stroke-width="1.6"/>')
    for ci, cat in enumerate(cats):
        out.append(f'<text x="{PAD_L + step * ci:.1f}" y="{CHART_H - 22}" text-anchor="middle" '
                   f'fill="#5b6672" font-size="8.5">{esc(cat)}</text>')
    out += _legend(series)
    out.append("</svg>")
    return "".join(out)


def _pie_slice(cx: float, cy: float, r: float, a0: float, a1: float, color: str) -> str:
    import math
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    large = 1 if (a1 - a0) > math.pi else 0
    return (f'<path d="M{cx:.1f},{cy:.1f} L{x0:.1f},{y0:.1f} A{r:.1f},{r:.1f} 0 {large} 1 '
            f'{x1:.1f},{y1:.1f} Z" fill="{color}" stroke="#fffdf8" stroke-width="1.2"/>')


def render_pie(chart: dict) -> str:
    panels = chart.get("panels") or []
    out = ['<div class="pie-row">']
    for panel in panels:
        slices = panel.get("slices", [])
        total = sum(float(s.get("value") or 0) for s in slices) or 1
        size = 150
        r = 62
        cx = cy = size / 2
        out.append(f'<div class="pie-panel"><svg class="chart-svg pie-svg" viewBox="0 0 {size} {size}" '
                   f'role="img" aria-label="{esc(panel.get("title") or "pie chart")}">')
        angle = -math.pi / 2
        for si, sl in enumerate(slices):
            span = 2 * math.pi * (float(sl.get("value") or 0) / total)
            out.append(_pie_slice(cx, cy, r, angle, angle + span, PALETTE[si % len(PALETTE)]))
            mid = angle + span / 2
            if span > 0.35:
                lx = cx + r * 0.66 * math.cos(mid)
                ly = cy + r * 0.66 * math.sin(mid)
                out.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="middle" fill="#fffdf8" '
                           f'font-size="9" font-weight="700">{esc(sl.get("value"))}</text>')
            angle += span
        out.append("</svg>")
        legend = "".join(
            f'<span class="lg"><i style="background:{PALETTE[si % len(PALETTE)]}"></i>'
            f'{esc(sl.get("label"))} <b>{esc(sl.get("value"))}%</b></span>'
            for si, sl in enumerate(slices)
        )
        out.append(f'<div class="pie-title">{esc(panel.get("title", ""))}</div>')
        out.append(f'<div class="chart-legend pie-legend">{legend}</div>')
        out.append("</div>")
    out.append("</div>")
    out.append(f'<p class="chart-cap">{esc(chart.get("caption", ""))}</p>')
    return "".join(out)


def render_flow(chart: dict) -> str:
    steps = chart.get("steps") or []
    out = ['<ol class="flow-chain">']
    for i, step in enumerate(steps):
        out.append(
            f'<li><span class="fs">{i + 1}</span><span class="ft">{esc(step.get("label"))}'
            + (f'<em>{esc(step.get("detail"))}</em>' if step.get("detail") else "")
            + "</span></li>"
        )
    out.append("</ol>")
    if chart.get("caption"):
        out.append(f'<p class="chart-cap">{esc(chart["caption"])}</p>')
    return "".join(out)


def render_map(chart: dict) -> str:
    out = ['<div class="map-pair">']
    for pane in chart.get("panes") or []:
        rows = "".join(
            f'<li><b>{esc(z.get("zone"))}</b><span>{esc(z.get("state"))}</span></li>'
            for z in pane.get("zones", [])
        )
        out.append(
            f'<div class="map-pane"><h5>{esc(pane.get("title"))}</h5><ul>{rows}</ul></div>'
        )
    out.append("</div>")
    if chart.get("caption"):
        out.append(f'<p class="chart-cap">{esc(chart["caption"])}</p>')
    return "".join(out)




def render_chart(chart: dict) -> str:
    kind = chart.get("kind", "table")
    if kind == "bar":
        return render_bar(chart)
    if kind == "line":
        return render_line(chart)
    if kind == "pie":
        return render_pie(chart)
    if kind == "flow":
        return render_flow(chart)
    if kind == "map":
        return render_map(chart)
    head = chart.get("head") or []
    rows = chart.get("rows") or []
    cap = f"<caption>{esc(chart.get('caption'))}</caption>" if chart.get("caption") else ""
    if not head or not rows:
        return cap
    thead = "".join(f'<th scope="col">{esc(h)}</th>' for h in head)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows
    )
    return f'<div class="tbl-wrap"><table class="data-table">{cap}<thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table></div>'


def render_prompt(case: dict) -> str:
    parts: list[str] = []
    en = (case.get("promptEn") or "").strip()
    if en:
        parts.append(f'<p class="prompt-en">{esc(en)}</p>')
    chart = case.get("chart")
    if chart:
        inner = render_chart(chart)
        if inner:
            parts.append(f'<figure class="chart-figure">{inner}</figure>')
        if chart.get("note"):
            parts.append(f'<p class="chart-note">{esc(chart["note"])}</p>')
    if case.get("promptZh"):
        parts.append(f'<p class="prompt-zh">{inline(case["promptZh"])}</p>')
    return "".join(parts)


def render_essay(case: dict) -> str:
    cid = case["id"]
    out = [
        f'<div class="essay-card" id="essay-{cid}">',
        '<div class="essay-head"><span class="t">Model answer · 原创范文</span>'
        f'<span class="wc">{case["_words"]} words</span></div>',
    ]
    for i, para in enumerate(case["essay"]):
        label = "ABCDEFGH"[i]
        out.append(
            f'<p class="epara" id="{para_dom(cid, i)}">'
            f'<span class="plabel" aria-hidden="true">{label}</span>'
            f'{esc(para["text"])}'
            f'<span class="gist">{esc(para.get("gist", ""))}</span>'
            "</p>"
        )
    out.append('<div class="essay-tools">')
    out.append(f'<button type="button" class="mini-btn copy-essay" data-copy="essay-{cid}">复制范文</button>')
    counts = " · ".join(str(n) for n in case["_counts"])
    out.append(f'<button type="button" class="mini-btn" disabled style="cursor:default">各段词数 {counts}</button>')
    out.append("</div></div>")
    return "".join(out)


def render_scores(case: dict, kws: dict) -> str:
    cells = []
    for s in case["scores"]:
        cells.append(
            '<div class="score"><div class="k">'
            f'<b>{esc(s.get("k"))}</b><i>{esc(s.get("v"))}</i></div>'
            f'<p>{render_text(s.get("p", ""), kws)}</p></div>'
        )
    return "".join(cells)


def render_structure(case: dict, kws: dict) -> str:
    items = []
    for s in case["structure"]:
        items.append(
            '<li><span class="sn">' + esc(s.get("n")) + "</span>"
            '<span class="sd">' + render_text(s.get("d", ""), kws) + "</span></li>"
        )
    return "".join(items)


def render_lexis(case: dict, kws: dict) -> str:
    rows = []
    for row in case["lexis"]:
        note = row.get("note", "")
        rows.append(
            '<div class="lex-item">'
            f'<div class="lex-w">{esc(row.get("w"))}</div>'
            f'<div class="lex-m">{render_text(row.get("m", ""), kws)}</div>'
            + (f'<div class="lex-note">{render_text(note, kws)}</div>' if note else "")
            + "</div>"
        )
    return f'<div class="lex-list">{"".join(rows)}</div>'


def render_grammar(case: dict, kws: dict) -> str:
    return "".join(f"<li>{render_text(g, kws)}</li>" for g in case["grammar"])


def render_pitfalls(case: dict, kws: dict) -> str:
    return "".join(f"<li>{render_text(p, kws)}</li>" for p in case["pitfalls"])


def render_case(case: dict, index: int) -> str:
    cid = case["id"]
    kws = {}
    for kw in case["keywords"]:
        info = dict(kw)
        info["_cid"] = cid
        kws[kw["term"]] = info

    task_label = "Task 1 · Academic" if case.get("task") == "task1" else "Task 2"
    kicker = [
        f"<span>{esc(task_label)}</span>",
        '<span class="sep"></span>',
        f'<span>{esc(case["catLabel"])}</span>',
    ]
    exam = case.get("exam") or {}
    if exam.get("date"):
        kicker.append('<span class="sep"></span>')
        kicker.append(f'<span>{esc(exam["date"])} 考场回忆</span>')

    tags = [f'<span class="chip chip-accent">{esc(case["catLabel"])}</span>']
    for tag in case.get("tags") or []:
        tags.append(f'<span class="chip">{esc(tag)}</span>')
    tags.append(f'<span class="chip">建议 {esc(case.get("minutes", "20"))} 分钟</span>')
    tags.append(f'<span class="chip chip-plum">目标 Band {esc(case.get("band", "7.5+"))}</span>')
    if exam.get("venue"):
        tags.append(f'<span class="chip chip-optional">来源：{esc(exam["venue"])}</span>')

    out = [
        f'<article class="case" id="case-{cid}" data-cat="{esc(case["cat"])}" '
        f'data-task="{esc(case.get("task", "task2"))}">',
        '<div class="case-head">',
        f'<div class="case-kicker">{"".join(kicker)}</div>',
        f'<h4 class="case-title">{esc(case["title"])}'
        + (f'<span class="en">{esc(case["titleEn"])}</span>' if case.get("titleEn") else "")
        + "</h4>",
        f'<div class="case-tags">{"".join(tags)}</div>',
        "</div>",
        '<div class="case-grid">',
        '<div class="col-left">',
        '<div class="card-label"><span>题目 <em>Prompt</em></span></div>',
        f'<div class="prompt-card">{render_prompt(case)}</div>',
        '<div class="card-label"><span>范文 <em>Model answer</em></span></div>',
        render_essay(case),
        "</div>",
        '<div class="col-right">',
        f'<div class="analysis-body" id="analysis-{cid}">',
        '<div class="card-label"><span>评分维度 <em>Scoring</em></span>'
        f'<button type="button" class="mini-btn fold-btn" data-fold="analysis-{cid}" '
        f'aria-expanded="true">收起解析</button></div>',
        f'<div class="score-grid">{render_scores(case, kws)}</div>',
        '<div class="block"><div class="bl">结构拆解 <em>Sentence by sentence</em></div>'
        f'<ul class="struct">{render_structure(case, kws)}</ul></div>',
        '<div class="block"><div class="bl">词汇与搭配 <em>Lexical resource</em></div>'
        f'{render_lexis(case, kws)}</div>',
        '<div class="block"><div class="bl">语法亮点 <em>Grammatical range</em></div>'
        f'<ul class="gram-list">{render_grammar(case, kws)}</ul></div>',
        '<div class="examiner"><div class="bl">考官视角 <em>Examiner note</em></div>'
        f'<p>{render_text(case["examiner"], kws)}</p></div>',
        '<div class="pitfalls"><div class="bl">常见踩坑 <em>Pitfalls</em></div>'
        f'<ul>{render_pitfalls(case, kws)}</ul></div>',
        "</div>",
        "</div>",
        "</div>",
        "</article>",
    ]
    return "".join(out)


def render_toc(meta: dict, task1: list, task2: list) -> str:
    out = ['<nav class="toc" aria-label="目录">', '<p class="toc-title">目录</p>']
    out.append('<div class="toc-group"><div class="toc-head"><b>Task 1 小作文</b><span>学术类</span></div>')
    for i, case in enumerate(task1, 1):
        out.append(
            f'<a href="#case-{esc(case["id"])}" data-cat="{esc(case["cat"])}">'
            f'<span class="n">{i:02d}</span><span>{esc(case["catLabel"])}</span></a>'
        )
    out.append("</div>")
    out.append('<div class="toc-group"><div class="toc-head"><b>Task 2 大作文</b><span>议论文</span></div>')
    for i, case in enumerate(task2, 1):
        out.append(
            f'<a href="#case-{esc(case["id"])}" data-cat="{esc(case["cat"])}">'
            f'<span class="n">{i:02d}</span><span>{esc(case["catLabel"])}</span></a>'
        )
    out.append("</div>")
    out.append('<div class="toc-group"><div class="toc-head"><b>附录</b><span>数据</span></div>')
    out.append('<a href="#appendix" data-cat="appendix"><span class="n">—</span><span>高频话题与数据说明</span></a>')
    out.append("</div>")
    out.append(f'<div class="toc-foot">{esc(meta.get("tocFoot", ""))}</div>')
    out.append("</nav>")
    return "".join(out)


def render_header(meta: dict, stats: dict) -> str:
    chips = "".join(f'<span class="chip chip-accent">{esc(c)}</span>' for c in meta.get("chips", []))
    return (
        '<header class="topbar"><div class="topbar-inner">'
        '<div class="brand"><div class="brand-mark" aria-hidden="true">W</div>'
        '<div class="brand-text">'
        f'<h1>{esc(meta["title"])}</h1>'
        f'<p class="brand-sub">{esc(meta["subtitle"])}</p>'
        f'<div class="meta-chips">{chips}</div>'
        "</div></div>"
        '<div class="top-actions">'
        '<button type="button" class="btn btn-primary" id="toggleAll"><span class="btn-label">收起全部解析</span></button>'
        '<button type="button" class="btn" id="gistBtn" aria-pressed="false">隐藏段意</button>'
        '<button type="button" class="btn action-secondary" id="printBtn">打印 / PDF</button>'
        "</div></div></header>"
    )


def render_hero(meta: dict, stats: dict, t1: list, t2: list) -> str:
    cats = []
    seen = set()
    for case in t1 + t2:
        if case["cat"] not in seen:
            seen.add(case["cat"])
            cats.append(case)

    chips = [
        '<span class="lb">筛选</span>',
        '<button type="button" class="fchip" data-filter="all" aria-pressed="true">全部</button>',
        '<button type="button" class="fchip" data-filter="task1" aria-pressed="false">Task 1</button>',
        '<button type="button" class="fchip" data-filter="task2" aria-pressed="false">Task 2</button>',
    ]
    for case in cats:
        chips.append(
            f'<button type="button" class="fchip" data-filter="{esc(case["cat"])}" aria-pressed="false">'
            f'{esc(case["catLabel"])}</button>'
        )

    stat_items = [
        (str(len(t1) + len(t2)), "篇原创范文"),
        (str(len(t1)), "种 Task 1 图表"),
        (str(len(t2)), "类 Task 2 题型"),
        (f'{stats["records"]:,}', "条写作考场记录"),
    ]
    cards = "".join(
        f'<div class="stat"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for v, k in stat_items
    )

    return (
        '<section class="hero" id="top"><div class="hero-inner">'
        f'<p class="hero-kicker">{esc(meta.get("kicker", ""))}</p>'
        f'<h2>{inline(meta["headline"])}</h2>'
        f'<p class="hero-lead">{inline(meta["lead"])}</p>'
        f'<div class="stat-grid">{cards}</div>'
        "</div>"
        f'<div class="filterbar" role="group" aria-label="按题型筛选">{"".join(chips)}</div>'
        "</section>"
    )


def render_task_block(task: str, intro: str, cases: list) -> str:
    title = "Task 1 · 图表小作文" if task == "task1" else "Task 2 · 议论文大作文"
    out = [f'<div class="task-block" data-task="{task}">']
    out.append(
        '<div class="task-head">'
        f"<div><h2>{esc(title)}</h2><p>{rendered(intro)}</p></div>"
        f'<span class="count">{len(cases)} 个题型 · {len(cases)} 篇范文</span>'
        "</div>"
    )
    for i, case in enumerate(cases):
        if i == 0 or cases[i - 1]["cat"] != case["cat"]:
            note = case.get("catNote") or ""
            out.append(
                f'<div class="cat-head" id="cat-{esc(case["cat"])}">'
                f'<h3>{esc(case["catLabel"])}</h3>'
                f'<span class="cat-en">{esc(case.get("catEn", ""))}</span>'
                + (f'<span class="cat-note">{esc(note)}</span>' if note else "")
                + "</div>"
            )
        out.append(render_case(case, i))
    out.append("</div>")
    return "".join(out)


def rendered(text: str) -> str:
    return inline(text)


def render_appendix(meta: dict, stats: dict) -> str:
    blocks = []
    for group in meta.get("hotTopics", []):
        items = "".join(
            "<li><span class=\"hits\">" + esc(item[0]) + "</span>"
            '<span class="tx">' + esc(item[1])
            + (f"<i>{esc(item[2])}</i>" if len(item) > 2 and item[2] else "")
            + "</span></li>"
            for item in group["items"]
        )
        blocks.append(
            '<div class="hot-block">'
            f'<h3>{esc(group["title"])}<span>{esc(group.get("note", ""))}</span></h3>'
            f'<ul class="hot-list">{items}</ul></div>'
        )

    source = meta.get("source", {})
    return (
        '<section class="appendix" id="appendix"><div class="card">'
        "<h2>附录 · 数据来源与高频话题</h2>"
        f'<p class="sub">{esc(meta.get("appendixSub", ""))}</p>'
        f'<div class="hot-grid">{"".join(blocks)}</div>'
        f'<div class="method-note">{meta.get("method", "")}</div>'
        "</div></section>"
    )


def render_footer(meta: dict, stats: dict) -> str:
    return (
        '<footer class="site-footer">'
        f'<p>{esc(meta.get("footerLine", ""))}</p>'
        f'<p class="fine">{esc(meta.get("footerFine", ""))}</p>'
        f'<p class="fine">{esc(meta.get("footerLegal", ""))}</p>'
        "</footer>"
    )


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the IELTS writing HTML.")
    parser.add_argument("--check", action="store_true", help="validate without writing output")
    parser.add_argument("-o", "--output", default=str(OUTPUT))
    args = parser.parse_args(argv)

    meta = load("meta.json")
    stats = load("stats.json")
    t1: list[dict] = []
    t2: list[dict] = []
    for path in sorted(CONTENT.glob("*.json")):
        if path.name in {"meta.json", "stats.json"}:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = payload["cases"] if isinstance(payload, dict) else payload
        for case in cases:
            task = case.get("task")
            case["_src"] = path.name
            (t1 if task == "task1" else t2).append(case)
    t1.sort(key=lambda c: c.get("order", 999))
    t2.sort(key=lambda c: c.get("order", 999))

    issues = Issues()
    for case in t1:
        case["task"] = "task1"
        case["catNote"] = next((c.get("catNote") for c in t1 if c["cat"] == case["cat"]), "")
        validate_case(case, issues)
    for case in t2:
        case["task"] = "task2"
        case["catNote"] = next((c.get("catNote") for c in t2 if c["cat"] == case["cat"]), "")
        validate_case(case, issues)

    # category notes come from the first case of each category
    for group in (t1, t2):
        notes = {}
        for case in group:
            note = case.get("catNote")
            if case["cat"] not in notes and note:
                notes[case["cat"]] = note
        for case in group:
            case["catNote"] = notes.get(case["cat"], "")

    if issues.errors:
        for e in issues.errors:
            print("ERROR " + e, file=sys.stderr)
    for w in issues.warns:
        print("WARN  " + w, file=sys.stderr)
    if issues.errors:
        print(f"\n{len(issues.errors)} 个错误，未生成 HTML。", file=sys.stderr)
        return 1
    if args.check:
        print(f"OK · {len(t1)} 篇 Task 1 + {len(t2)} 篇 Task 2，{len(issues.warns)} 条提醒")
        return 0

    template = TEMPLATE.read_text(encoding="utf-8")
    body = (
        render_hero(meta, stats, t1, t2)
        + '<div class="shell">'
        + render_toc(meta, t1, t2)
        + '<main class="content">'
        + render_task_block("task1", meta.get("task1Intro", ""), t1)
        + render_task_block("task2", meta.get("task2Intro", ""), t2)
        + render_appendix(meta, stats)
        + '<div class="empty" id="emptyState" hidden>这个筛选下暂时没有内容。</div>'
        + "</main></div>"
    )
    page = (
        template.replace("<!--BUILD:TITLE-->", esc(meta["pageTitle"]))
        .replace("<!--BUILD:HEADER-->", render_header(meta, stats))
        .replace("<!--BUILD:BODY-->", body)
        .replace("<!--BUILD:FOOTER-->", render_footer(meta, stats))
    )
    out = Path(args.output)
    out.write_text(page, encoding="utf-8")
    print(f"OK · {out} · {len(page) / 1024:.0f} KB · {len(issues.warns)} 条提醒")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
