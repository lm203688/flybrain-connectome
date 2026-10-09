#!/usr/bin/env python3
"""Render a repo markdown doc into a standalone HTML view (same skin as the roadmap).

    python scripts/render_doc.py docs/FOUNDATION_ROADMAP.md
    python scripts/render_doc.py docs/X.md --out docs/X.html --title "..." --sub "..." \
        --pill "门禁 19/19 PASS" --pill "v2.48.0"

The HTML is a *view* artifact: `*.html` is gitignored, so it never lands in the
tree. It exists so a long doc is readable without a markdown renderer.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#1a1d24;--muted:#5b6472;--line:#e4e7ec;--accent:#0e8a6a;--accent2:#2f5fe0;--code:#f2f4f8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.75;font-size:15.5px;
font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",Roboto,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:48px 24px 120px}
.hero{background:linear-gradient(135deg,#123a5e 0%,#2f5fe0 100%);color:#fff;border-radius:18px;
padding:38px 34px;margin-bottom:34px;box-shadow:0 18px 40px rgba(18,58,94,.22)}
.hero h1{margin:0 0 8px;font-size:28px;line-height:1.35}
.hero .sub{opacity:.92;font-size:14.5px}
.hero .pill{display:inline-block;margin:10px 8px 0 0;padding:4px 12px;background:rgba(255,255,255,.16);
border:1px solid rgba(255,255,255,.3);border-radius:999px;font-size:12.5px}
article{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:8px 40px 56px;
box-shadow:0 4px 20px rgba(16,24,40,.05)}
article>h1:first-child{display:none}
h1,h2,h3,h4{line-height:1.4;font-weight:700}
h2{font-size:22px;margin:44px 0 14px;padding-bottom:10px;border-bottom:2px solid var(--line)}
h2::before{content:"";display:inline-block;width:6px;height:20px;background:var(--accent);
border-radius:3px;margin-right:11px;vertical-align:-3px}
h3{font-size:18px;margin:30px 0 10px}
h4{font-size:15.5px;margin:20px 0 8px;color:var(--muted)}
a{color:var(--accent2);text-decoration:none}
hr{border:none;border-top:1px dashed var(--line);margin:40px 0}
code{background:var(--code);padding:2px 6px;border-radius:6px;font-family:"SF Mono",Consolas,monospace;
font-size:13px;color:#0b4f3f}
pre{background:#0f172a;color:#e2e8f0;padding:18px 20px;border-radius:12px;overflow:auto;
font-size:13px;line-height:1.6}
pre code{background:none;color:inherit;padding:0}
table{width:100%;border-collapse:collapse;margin:18px 0;font-size:14px;border:1px solid var(--line);
border-radius:10px;overflow:hidden}
th{background:#eaf5f0;text-align:left;font-weight:700;color:#0f3d33}
th,td{padding:10px 13px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:nth-child(even){background:#fafbfd}
tbody tr:hover{background:#eefaf5}
blockquote{margin:18px 0;padding:14px 20px;background:#eefaf5;border-left:4px solid var(--accent);
border-radius:0 10px 10px 0;color:#134e42}
strong{color:#0b1220}
ul,ol{padding-left:24px}
li{margin:5px 0}
.foot{margin-top:28px;text-align:center;color:var(--muted);font-size:12.5px}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style></head><body><div class="wrap">
<div class="hero"><h1>{title}</h1>
<div class="sub">{sub}</div>
<div>{pills}</div></div>
<article>{body}</article>
<div class="foot">{foot}</div>
</div></body></html>"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="markdown file to render")
    ap.add_argument("--out", default=None, help="output html (default: src with .html)")
    ap.add_argument("--title", default=None, help="hero title (default: first H1)")
    ap.add_argument("--sub", default="", help="hero subtitle")
    ap.add_argument("--pill", action="append", default=[], dest="pills")
    ap.add_argument("--foot", default="活文档 · 每个结论须有脚本 + 数字 + 门禁三重证据")
    args = ap.parse_args(argv)

    try:
        import markdown
    except ImportError:
        print("ERROR: needs `pip install markdown`", file=sys.stderr)
        return 2

    src = Path(args.src)
    if not src.exists():
        print("ERROR: no such file: %s" % src, file=sys.stderr)
        return 2
    dst = Path(args.out) if args.out else src.with_suffix(".html")

    text = src.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])

    title = args.title
    if not title:
        for ln in text.splitlines():
            if ln.startswith("# "):
                title = ln[2:].strip()
                break
    title = title or src.stem

    pills = "".join('<span class="pill">%s</span>' % p for p in args.pills)
    html = HTML.format(title=title, sub=args.sub, pills=pills,
                       body=body, foot=args.foot, css=CSS)
    dst.write_text(html, encoding="utf-8")
    print("WROTE %s (%d bytes)" % (dst, len(html)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
