"""Renders the one-time hero-photo QA contact sheet. Visual reference:
scratchpad hero_contact_sheet_mockup.html. Self-contained; thumbs are data URIs."""
import html as html_lib

_CSS = """
*{box-sizing:border-box}body{margin:0;background:#f6f7f9;color:#14181f;
font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.45}
@media(prefers-color-scheme:dark){body{background:#0e1116;color:#e8ebf0}
.card,.chip,table.problems{background:#161b22;border-color:#232a33}}
.wrap{max-width:1060px;margin:0 auto;padding:28px 20px 60px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 26px}
.chip{font-size:12px;padding:5px 11px;border-radius:999px;border:1px solid #e4e7ec;background:#fff}
.card{background:#fff;border:1px solid #e4e7ec;border-radius:14px;padding:18px;margin-bottom:16px}
.card.fallback{border-color:#e0a353}
.card h2{font-size:15.5px;margin:0 0 12px}
.row{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
figure{margin:0}.thumb{position:relative;aspect-ratio:4/3;border-radius:10px;overflow:hidden;border:1px solid #e4e7ec}
.thumb img{width:100%;height:100%;object-fit:cover}
.chosen .thumb{border:2px solid #1f7a4d;box-shadow:0 0 0 4px #e6f4ec}
.rejected .thumb{opacity:.5;filter:grayscale(.3)}
.badge{position:absolute;top:8px;left:8px;background:#1f7a4d;color:#fff;font-size:10px;font-weight:700;padding:3px 7px;border-radius:6px}
.rej{position:absolute;top:8px;left:8px;background:rgba(20,24,31,.72);color:#fff;font-size:10px;padding:3px 7px;border-radius:6px}
figcaption{font-size:11px;color:#626b7a;margin-top:6px}
.reason{margin-top:14px;padding:10px 12px;background:#e6f4ec;border-radius:9px;font-size:12.5px}
.fallback .reason{background:#fbeee2}
table.problems{width:100%;border-collapse:collapse;font-size:12.5px;background:#fff;border:1px solid #e4e7ec;border-radius:12px;overflow:hidden;margin-top:12px}
table.problems th,table.problems td{text-align:left;padding:10px 12px;border-bottom:1px solid #e4e7ec}
h3.section{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#626b7a;margin:34px 0 12px}
"""


def _esc(s):
    return html_lib.escape(str(s or ""))


def _story_card(rec):
    cls = "card fallback" if rec.get("fallback") else "card"
    figs = []
    for i, c in enumerate(rec["candidates"]):
        chosen = (i == rec.get("chosen_index"))
        fcls = "chosen" if chosen else "rejected"
        badge = '<span class="badge">HERO</span>' if chosen else (
            f'<span class="rej">{_esc(c["rejected_why"])}</span>' if c.get("rejected_why") else "")
        figs.append(
            f'<figure class="{fcls}"><div class="thumb">'
            f'<img src="data:image/jpeg;base64,{c["b64"]}" alt="">{badge}</div>'
            f'<figcaption>{_esc(c["name"])}</figcaption></figure>')
    label = "Auto-fallback" if rec.get("fallback") else "Chosen"
    return (
        f'<div class="{cls}"><h2>{_esc(rec["title"])} '
        f'<span style="color:#626b7a;font-size:12px;font-weight:400">{_esc(rec.get("meta"))}</span></h2>'
        f'<div class="row">{"".join(figs)}</div>'
        f'<div class="reason"><b>{label}:</b> {_esc(rec["reason"])}</div></div>')


def render_contact_sheet(records):
    stored = [r for r in records if r["status"] in ("stored", "dry")]
    fallback = [r for r in stored if r.get("fallback")]
    problems = [r for r in records if r["status"] == "problem"]
    chips = (f'<span class="chip">{len(stored)} stored</span>'
             f'<span class="chip">{len(fallback)} fallback</span>'
             f'<span class="chip">{len(problems)} problems</span>')
    cards = "".join(_story_card(r) for r in stored)
    prob_rows = "".join(
        f'<tr><td>{_esc(r["title"])}</td><td>{_esc(r["problem_reason"])}</td></tr>'
        for r in problems)
    prob = (f'<h3 class="section">Problems ({len(problems)} skipped)</h3>'
            f'<table class="problems"><thead><tr><th>Story</th><th>Reason</th></tr></thead>'
            f'<tbody>{prob_rows}</tbody></table>') if problems else ""
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Story Hero Contact Sheet</title><style>{_CSS}</style></head><body>'
        f'<div class="wrap"><h1 style="font-size:20px;margin:0 0 4px">Story Hero Contact Sheet</h1>'
        f'<div class="chips">{chips}</div>{cards}{prob}</div></body></html>')
