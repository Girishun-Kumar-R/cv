"""Render report.md to print-ready HTML (inline SVG charts) and, when a headless Chromium is available, PDF.

    python3 fa_render.py --run-dir RUN [--pdf]

Standard library only. The HTML is generated from the verified report.md text without changing any figure.
PDF uses Chromium's --print-to-pdf (A4, page numbers via CSS page-margin boxes); if no browser is found the
HTML is still produced and the reason is returned.
"""
from __future__ import annotations

import argparse
import glob
import html
import os
import re
import shutil
import subprocess
import sys

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 8pt Helvetica, Arial, sans-serif;
                  color: #666; }
  @bottom-left { content: "Finance Analyst report — decision support, not an audit opinion"; font: 8pt Helvetica,
                 Arial, sans-serif; color: #666; } }
:root { --ink: #1d2733; --muted: #5c6b7a; --rule: #d5dde6; --head: #eef3f8; --ok: #1f7a4d; --warn: #9a5b00;
        --bad: #b3261e; }
html { font: 10pt/1.42 Helvetica, Arial, sans-serif; color: var(--ink); }
body { margin: 0 auto; max-width: 182mm; }
h1 { font-size: 18pt; margin: 0 0 4pt; }
h2 { font-size: 13pt; margin: 16pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5pt solid var(--ink);
     break-after: avoid; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
.status { border: 1pt solid var(--rule); border-left: 5pt solid var(--warn); padding: 6pt 8pt; margin: 8pt 0 10pt;
          background: #fffaf0; break-inside: avoid; }
.status.ok { border-left-color: var(--ok); background: #f2fbf6; }
.status.bad { border-left-color: var(--bad); background: #fdf3f2; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-size: 8.8pt; break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: var(--head); text-align: left; font-weight: 600; }
th, td { border: 0.5pt solid var(--rule); padding: 3pt 5pt; vertical-align: top; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tbody tr:nth-child(even) td { background: #fafcfe; }
figure { margin: 8pt 0 12pt; break-inside: avoid; }
figure svg { width: 100%; height: auto; display: block; }
figcaption { font-size: 8.5pt; color: var(--muted); margin-top: 3pt; }
blockquote { margin: 6pt 0; padding: 4pt 8pt; border-left: 3pt solid var(--rule); color: var(--muted); }
code { font-size: 8.5pt; background: #f3f5f7; padding: 0 2pt; }
em { color: var(--muted); }
.ev { display: block; font-size: 7.5pt; color: var(--muted); }
li { margin-bottom: 2pt; }
"""


LIST_MARK = re.compile(r"^\s*(\d+\.|-)\s+")


def inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<em>\1</em>", t)
    return t


def md_to_html(md, run_dir, title):
    out, lines, i = [], md.split("\n"), 0
    list_tag = None

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None
    while i < len(lines):
        ln = lines[i]
        img = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", ln.strip())
        if img:
            close_list()
            path = os.path.join(run_dir, img.group(2))
            caption = html.escape(img.group(1))
            if img.group(2).endswith(".svg") and os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    svg = fh.read()
                out.append(f"<figure>{svg}<figcaption>{caption}</figcaption></figure>")
            else:
                out.append(f'<figure><img alt="{caption}" src="{html.escape(img.group(2))}">'
                           f"<figcaption>{caption}</figcaption></figure>")
        elif ln.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|[\s:|-]+\|", lines[i + 1].strip()):
            close_list()
            heads = [c.strip() for c in ln.strip().strip("|").split("|")]
            aligns = ["num" if c.strip().endswith(":") else "" for c in lines[i + 1].strip().strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(
                f'<th class="{a}">{inline(h)}</th>' for h, a in zip(heads, aligns)) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f'<td class="{a}">{inline(c)}</td>' for c, a in zip(cells, aligns))
                           + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        elif ln.startswith("#"):
            close_list()
            level = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{level}>{inline(ln[level:].strip())}</h{level}>")
        elif re.match(r"^\s*(\d+\.|-)\s+", ln):
            tag = "ol" if re.match(r"^\s*\d+\.", ln) else "ul"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            item = LIST_MARK.sub("", ln)
            body, sep, ev = item.partition(" — evidence: ")
            ev_html = f' <span class="ev">evidence: {inline(ev)}</span>' if sep else ""
            out.append(f"<li>{inline(body)}{ev_html}</li>")
        elif ln.startswith(">"):
            close_list()
            out.append(f"<blockquote>{inline(ln.lstrip('> '))}</blockquote>")
        elif ln.startswith("**Status:"):
            close_list()
            cls = "bad" if "NOT VERIFIED" in ln else ("ok" if "no open data issues" in ln else "")
            out.append(f'<div class="status {cls}">{inline(ln)}</div>')
        elif ln.strip():
            close_list()
            out.append(f"<p>{inline(ln)}</p>")
        else:
            close_list()
        i += 1
    close_list()
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f"<style>{CSS}</style></head><body>" + "\n".join(out) + "</body></html>")


def find_browser():
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux*/chrome", "/opt/pw-browsers/chromium*/chrome-linux*/chrome",
                    os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


def render(run_dir, pdf=True):
    with open(os.path.join(run_dir, "report.md"), encoding="utf-8") as fh:
        md = fh.read()
    title = md.split("\n", 1)[0].lstrip("# ").strip()
    out_html = os.path.join(run_dir, "report.html")
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(md_to_html(md, run_dir, title))
    result = {"html": out_html, "pdf": None, "pdf_status": "not requested"}
    if pdf:
        exe = find_browser()
        if not exe:
            result["pdf_status"] = "no headless Chromium found; use the HTML or the host's PDF tools"
            return result
        out_pdf = os.path.join(run_dir, "report.pdf")
        cmd = [exe, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
               f"--print-to-pdf={out_pdf}", "file://" + os.path.abspath(out_html)]
        proc = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
        if os.path.isfile(out_pdf) and os.path.getsize(out_pdf) > 1000:
            result.update(pdf=out_pdf, pdf_status="ok")
        else:
            result["pdf_status"] = f"PDF generation failed: {proc.stderr.decode(errors='ignore')[-300:]}"
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args(argv)
    res = render(a.run_dir, a.pdf)
    print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
