"""Render accessible SVG charts from calculation-register values (spec visualizations).

Each chart spec binds every plotted value to a calc_id, so fa_verify.py can check that
the chart shows exactly the registered figures (ver_chart_data). Standard library only.
Supported types: aging_stacked_bar, waterfall_bridge, variance_bar_diverging,
pareto_chart, bar_comparison.
"""
from __future__ import annotations

from decimal import Decimal
from xml.sax.saxutils import escape

from fa_common import fmt_value

W, H = 760, 400
PAD_L, PAD_R, PAD_T, PAD_B = 170, 40, 70, 60
# Colour-blind-safe palette: blue (favourable/neutral series), orange (unfavourable), greys.
BLUE, ORANGE, GREY, DARK, LIGHT = "#2F6DB5", "#E8890C", "#8C8C8C", "#222222", "#E6E6E6"
AGING = ["#9ECAE1", "#6BAED6", "#FDD0A2", "#FDAE6B", "#F16913", "#D94801", "#8C2D04"]


def label(value, unit):
    return fmt_value(Decimal(value), unit, mode="chart" if unit == "money" else "narrative")


def wrap(text, width=22):
    """Split a long category label into at most two lines."""
    if len(text) <= width:
        return [text]
    cut = text.rfind(" ", 0, width + 1)
    cut = cut if cut > 0 else width
    rest = text[cut:].strip()
    return [text[:cut].strip(), rest if len(rest) <= width + 4 else rest[:width + 1] + "…"]


def _frame(spec, body):
    h = spec.get("_height", H)
    title = escape(spec["title"])
    sub = escape(spec.get("subtitle", ""))
    alt = escape(spec.get("alt", spec["title"]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'role="img" aria-labelledby="t d" font-family="Helvetica, Arial, sans-serif">'
            f'<title id="t">{title}</title><desc id="d">{alt}</desc>'
            f'<rect width="{W}" height="{h}" fill="#FFFFFF"/>'
            f'<text x="20" y="30" font-size="19" font-weight="bold" fill="{DARK}">{title}</text>'
            f'<text x="20" y="51" font-size="13" fill="{GREY}">{sub}</text>'
            + body +
            f'<text x="20" y="{h - 14}" font-size="10" fill="{GREY}">{escape(spec.get("source", ""))}</text>'
            "</svg>")


def _hbars(spec, signed=False):
    series = spec["series"]
    vals = [Decimal(s["value"]) for s in series]
    n = max(len(series), 1)
    plot_w = W - PAD_L - PAD_R
    bar_h = 30
    spec["_height"] = int(PAD_T + n * (bar_h + 8) + PAD_B)  # height follows the number of bars
    mx = max([abs(v) for v in vals] + [Decimal(1)])
    zero_x = PAD_L + (plot_w / 2 if signed else 0)
    scale = ((plot_w / 2 - 85) if signed else (plot_w - 90)) / float(mx)  # leave room for value labels
    out = []
    if signed:
        out.append(f'<line x1="{zero_x}" y1="{PAD_T - 6}" x2="{zero_x}" y2="{spec["_height"] - PAD_B + 4}" '
                   f'stroke="{GREY}"/>')
    for i, (s, v) in enumerate(zip(series, vals)):
        y = PAD_T + i * (bar_h + 8)
        length = abs(float(v)) * scale
        x = zero_x - length if (signed and v < 0) else zero_x
        colour = s.get("colour") or (ORANGE if s.get("unfavourable") else BLUE)
        parts = wrap(s["label"])
        ty = y + bar_h / 2 + (4 if len(parts) == 1 else -3)
        out.append(f'<text x="{PAD_L - 8}" y="{ty}" font-size="13" text-anchor="end" fill="{DARK}">'
                   + "".join(f'<tspan x="{PAD_L - 8}" dy="{0 if k == 0 else 14}">{escape(p)}</tspan>'
                             for k, p in enumerate(parts)) + "</text>")
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(length, 1):.1f}" height="{bar_h:.1f}" '
                   f'fill="{colour}"/>')
        tx = (x - 6) if (signed and v < 0) else (zero_x + length + 6)
        anchor = "end" if (signed and v < 0) else "start"
        out.append(f'<text x="{tx:.1f}" y="{y + bar_h / 2 + 4}" font-size="13" font-weight="bold" '
                   f'text-anchor="{anchor}" fill="{DARK}">{escape(s["value_label"])}</text>')
    return "".join(out)


def _aging(spec):
    series = spec["series"]
    vals = [max(Decimal(s["value"]), Decimal(0)) for s in series]
    total = sum(vals) or Decimal(1)
    plot_w = W - 80
    x = 40.0
    out = []
    for i, (s, v) in enumerate(zip(series, vals)):
        w = plot_w * float(v / total)
        if w > 0:
            out.append(f'<rect x="{x:.1f}" y="90" width="{w:.1f}" height="44" fill="{AGING[i % len(AGING)]}"/>')
        x += w
    for i, s in enumerate(series):
        row, col = divmod(i, 2)
        lx, ly = 40 + col * 340, 175 + row * 30
        out.append(f'<rect x="{lx}" y="{ly - 11}" width="14" height="14" fill="{AGING[i % len(AGING)]}"/>')
        out.append(f'<text x="{lx + 22}" y="{ly}" font-size="14" fill="{DARK}">{escape(s["label"])}: '
                   f'<tspan font-weight="bold">{escape(s["value_label"])}</tspan></text>')
    return "".join(out)


def _waterfall(spec):
    series = spec["series"]
    vals = [Decimal(s["value"]) for s in series]
    n = len(series)
    plot_w, plot_h = W - 80, H - PAD_T - PAD_B - 30
    running, tops = Decimal(0), []
    for s, v in zip(series, vals):
        if s.get("kind") == "total":
            tops.append((Decimal(0), v))
            running = v
        else:
            start = running
            running = running + v
            tops.append((start, running))
    hi = max([max(a, b) for a, b in tops] + [Decimal(1)])
    lo = min([min(a, b) for a, b in tops] + [Decimal(0)])
    span = float(hi - lo) or 1.0
    plot_h -= 30
    y_of = lambda v: PAD_T + 40 + plot_h * (float(hi - v) / span)  # noqa: E731  (room for staggered labels)
    bw = plot_w / n * 0.62
    out = [f'<line x1="40" y1="{y_of(Decimal(0)):.1f}" x2="{W - 40}" y2="{y_of(Decimal(0)):.1f}" stroke="{GREY}"/>']
    for i, (s, (a, b)) in enumerate(zip(series, tops)):
        x = 40 + i * plot_w / n + (plot_w / n - bw) / 2
        top, bottom = y_of(max(a, b)), y_of(min(a, b))
        colour = GREY if s.get("kind") == "total" else (s.get("colour") or (ORANGE if b < a else BLUE))
        out.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(bottom - top, 1):.1f}" '
                   f'fill="{colour}"/>')
        lift = 18 if (i % 2 and s.get("kind") != "total") else 0  # stagger neighbouring labels
        out.append(f'<text x="{x + bw / 2:.1f}" y="{top - 6 - lift:.1f}" font-size="12" font-weight="bold" '
                   f'text-anchor="middle" fill="{DARK}">{escape(s["value_label"])}</text>')
        parts = wrap(s["label"], 14)
        out.append(f'<text x="{x + bw / 2:.1f}" y="{H - PAD_B + 16}" font-size="11.5" text-anchor="middle" '
                   f'fill="{DARK}">' + "".join(f'<tspan x="{x + bw / 2:.1f}" dy="{0 if k == 0 else 13}">'
                                               f'{escape(p)}</tspan>' for k, p in enumerate(parts)) + "</text>")
    return "".join(out)


def _pareto(spec):
    series = spec["series"]
    vals = [Decimal(s["value"]) for s in series]
    n = max(len(series), 1)
    plot_w, plot_h = W - 120, H - PAD_T - PAD_B - 20
    mx = max(vals + [Decimal("0.0001")])
    bw = plot_w / n * 0.6
    out = []
    cum, pts = Decimal(0), []
    for i, (s, v) in enumerate(zip(series, vals)):
        x = 60 + i * plot_w / n + (plot_w / n - bw) / 2
        h = plot_h * float(v / mx)
        y = PAD_T + 10 + plot_h - h
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{BLUE}"/>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 6:.1f}" font-size="11" text-anchor="middle" '
                   f'fill="{DARK}">{escape(s["value_label"])}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{H - PAD_B + 18}" font-size="11" text-anchor="middle" '
                   f'fill="{DARK}">{escape(s["label"])}</text>')
        cum += v
        pts.append((x + bw / 2, PAD_T + 10 + plot_h * (1 - float(min(cum, Decimal(1))))))
    out.append('<polyline fill="none" stroke="' + ORANGE + '" stroke-width="2" points="'
               + " ".join(f"{px:.1f},{py:.1f}" for px, py in pts) + '"/>')
    out.append(f'<text x="{W - 40}" y="{PAD_T}" font-size="11" text-anchor="end" fill="{ORANGE}">cumulative share'
               f'</text>')
    return "".join(out)


def _grouped(spec):
    groups = spec["groups"]  # [{label, items: [{series, value, value_label}]}]
    names = spec["series_names"]
    n = max(len(groups), 1)
    plot_w, plot_h = W - 120, H - PAD_T - PAD_B - 30
    vals = [Decimal(it["value"]) for g in groups for it in g["items"]]
    mx = max([abs(v) for v in vals] + [Decimal("0.0001")])
    gw = plot_w / n
    bw = gw * 0.7 / max(len(names), 1)
    colours = [BLUE, GREY, ORANGE]
    out = []
    for gi, g in enumerate(groups):
        for si, it in enumerate(g["items"]):
            v = Decimal(it["value"])
            h = plot_h * float(abs(v) / mx)
            x = 60 + gi * gw + gw * 0.15 + si * bw
            y = PAD_T + 20 + plot_h - h
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw - 4:.1f}" height="{h:.1f}" '
                       f'fill="{colours[si % 3]}"/>')
            out.append(f'<text x="{x + (bw - 4) / 2:.1f}" y="{y - 5:.1f}" font-size="10" text-anchor="middle" '
                       f'fill="{DARK}">{escape(it["value_label"])}</text>')
        out.append(f'<text x="{60 + gi * gw + gw / 2:.1f}" y="{H - PAD_B + 18}" font-size="11" '
                   f'text-anchor="middle" fill="{DARK}">{escape(g["label"])}</text>')
    for si, nm in enumerate(names):
        out.append(f'<rect x="{W - 230 + si * 110}" y="58" width="12" height="12" fill="{colours[si % 3]}"/>')
        out.append(f'<text x="{W - 213 + si * 110}" y="68" font-size="11" fill="{DARK}">{escape(nm)}</text>')
    return "".join(out)


RENDERERS = {"aging_stacked_bar": _aging, "waterfall_bridge": _waterfall,
             "variance_bar_diverging": lambda s: _hbars(s, signed=True), "pareto_chart": _pareto,
             "bar_comparison": _grouped}


def render_svg(spec):
    body = RENDERERS[spec["type"]](spec)  # may set spec["_height"]
    svg = _frame(spec, body)
    spec.pop("_height", None)
    return svg
