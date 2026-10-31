#!/usr/bin/env python3
"""Build the IELTS Speaking Part 2 material library into HTML and PDF.

Usage:
    python -X utf8 build.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "speaking-part2-materials.md"
HTML_OUT = ROOT / "speaking-part2-materials.html"
PDF_OUT = ROOT / "speaking-part2-materials.pdf"

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

CSS = """
@page {
  size: A4;
  margin: 18mm 16mm 18mm 16mm;
}

* { box-sizing: border-box; }

html { font-size: 10.5pt; }

body {
  font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;
  line-height: 1.72;
  color: #1a1a1a;
  margin: 0;
}

@media screen {
  body {
    max-width: 860px;
    margin: 0 auto;
    padding: 32px 22px 72px;
    background: #fffdf8;
    color: #1f2933;
  }
  html { background: #f2efe7; }
  .toolbar { margin: 0 0 14px; }
  .toolbar a {
    display: inline-block; padding: 7px 15px; border-radius: 999px;
    border: 1px solid #0f766e; background: #0f766e; color: #fff;
    font-size: 12.5px; font-weight: 600; text-decoration: none;
  }
  .toolbar a:hover { background: #115e59; border-color: #115e59; }
}

@media print {
  body { padding: 0; }
  .toolbar { display: none; }
}

h1 {
  font-size: 22pt;
  font-weight: 700;
  line-height: 1.3;
  margin: 0 0 4mm 0;
  padding-bottom: 4mm;
  border-bottom: 2.4pt solid #1a1a1a;
  letter-spacing: 0.5pt;
}

h1 + p {
  color: #666;
  font-size: 9.5pt;
  letter-spacing: 1.2pt;
  margin: 0 0 8mm 0;
}

h2 {
  font-size: 13.5pt;
  font-weight: 700;
  margin: 9mm 0 3.5mm 0;
  padding-left: 3mm;
  border-left: 3.4pt solid #1a1a1a;
  line-height: 1.4;
  break-after: avoid;
}

h3 {
  font-size: 11.5pt;
  font-weight: 700;
  margin: 6mm 0 2.5mm 0;
  color: #111;
  break-after: avoid;
}

p { margin: 0 0 2.6mm 0; text-align: justify; }

strong { font-weight: 700; color: #000; }

ul, ol { margin: 0 0 3mm 0; padding-left: 5.5mm; }

li { margin: 0 0 1.4mm 0; }

li::marker { color: #888; }

ul + p, ol + p { margin-top: 1.6mm; }

h3 + p { margin-top: 0.6mm; }

table {
  width: 100%;
  border-collapse: collapse;
  margin: 2mm 0 5mm 0;
  font-size: 9pt;
  break-inside: avoid;
}

thead { background: #f1f1ef; }

th {
  text-align: left;
  font-weight: 700;
  padding: 2mm 2.4mm;
  border: 0.5pt solid #c8c8c4;
  line-height: 1.4;
}

td {
  padding: 2mm 2.4mm;
  border: 0.5pt solid #d8d8d4;
  vertical-align: top;
  line-height: 1.5;
}

tbody tr:nth-child(even) { background: #fafaf8; }

th:first-child, td:first-child { white-space: nowrap; width: 1%; }

hr {
  border: none;
  border-top: 0.5pt solid #d0d0cc;
  margin: 7mm 0;
}

blockquote {
  margin: 3mm 0;
  padding: 3mm 4mm;
  background: #f6f6f3;
  border-left: 2.4pt solid #999;
  color: #444;
}

code {
  font-family: "Cascadia Mono", "Consolas", monospace;
  font-size: 8.6pt;
  background: #f2f2ef;
  padding: 0.4mm 1.2mm;
  border-radius: 1mm;
  color: #7a3b1c;
}

em { color: #666; font-style: normal; font-size: 9pt; }

p:has(> code:only-child) {
  background: #f6f6f3;
  border-left: 2.4pt solid #bbb;
  padding: 3mm 4mm;
  font-size: 9pt;
}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>雅思口语 Part 2 素材库</title>
<style>{css}</style>
</head>
<body>
<div class="toolbar"><a href="materials.pdf" download>下载 PDF 版</a></div>
{body}
</body>
</html>
"""


def find_edge() -> Path:
    for path in EDGE_CANDIDATES:
        if path.exists():
            return path
    raise SystemExit("找不到 Microsoft Edge，无法导出 PDF")


def build_pdf(html_path: Path, pdf_path: Path) -> None:
    edge = find_edge()
    if pdf_path.exists():
        pdf_path.unlink()
    subprocess.run(
        [
            str(edge),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"缺少源文件: {SOURCE}")

    text = SOURCE.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "sane_lists", "attr_list"],
        output_format="html5",
    )
    body = re.sub(r"\s*\n\s*<table", "\n<table", body)

    HTML_OUT.write_text(TEMPLATE.format(css=CSS, body=body), encoding="utf-8")
    print(f"HTML: {HTML_OUT}")

    build_pdf(HTML_OUT, PDF_OUT)
    size = PDF_OUT.stat().st_size / 1024
    print(f"PDF : {PDF_OUT} ({size:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
