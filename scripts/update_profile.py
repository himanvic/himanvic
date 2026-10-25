#!/usr/bin/env python3
"""
Rebuilds the LIVE parts of the profile from REAL GitHub data (public API only):
  assets/card-<repo>.svg   one animated card per real public repo
  assets/terminal.svg      terminal listing your real repos
  assets/stats.svg         real counts + real language split
  README.md                project table between the REPOS markers

Nothing here is invented: every name, description, language, star count and date
comes from GitHub. If GitHub can't be reached, it falls back to the project
descriptions you wrote yourself in your README (no numbers, no dates).

Run by .github/workflows/update-profile.yml (every 6 hours). Needs only Python 3.
"""
import datetime
import json
import os
import re
import textwrap
import urllib.request
from collections import Counter
from xml.sax.saxutils import escape as esc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "himanvic"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_CARDS = 6
THEME = "default"  # default | neon-pink | matrix-green | gold-luxury

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono','DejaVu Sans Mono',monospace"
COLORS = ["#67E8F9", "#A78BFA", "#34D399", "#F472B6", "#FBBF24", "#60A5FA"]

THEMES = {
    "neon-pink": {"#67E8F9": "#F472B6", "#22D3EE": "#EC4899", "#A5F3FC": "#FBCFE8", "#7DD3FC": "#F9A8D4", "#60A5FA": "#EC4899",
                  "#A78BFA": "#C084FC", "#F472B6": "#22D3EE"},
    "matrix-green": {"#67E8F9": "#4ADE80", "#22D3EE": "#22C55E", "#A5F3FC": "#BBF7D0", "#7DD3FC": "#86EFAC", "#60A5FA": "#22C55E",
                     "#A78BFA": "#A3E635", "#F472B6": "#FACC15"},
    "gold-luxury": {"#67E8F9": "#FBBF24", "#22D3EE": "#F59E0B", "#A5F3FC": "#FDE68A", "#7DD3FC": "#FCD34D", "#60A5FA": "#F59E0B",
                    "#A78BFA": "#FB923C", "#F472B6": "#F9A8D4"},
}

# Fallback ONLY: the descriptions you wrote yourself in your README.
SEED = [
    {"name": "sanskode", "description": "A local-first coding arcade concept with mini-games and bite-sized programming practice.",
     "homepage": "https://sanskode.pages.dev/", "html_url": "https://github.com/himanvic/sanskode"},
    {"name": "bottelneck.sys", "description": "A laptop-finder experiment focused on organizing device information and workload-oriented recommendations.",
     "homepage": "", "html_url": "https://github.com/himanvic/bottelneck.sys"},
    {"name": "Mausam-India", "description": "A responsive India weather dashboard with forecast and air-quality information.",
     "homepage": "https://mausam-india.pages.dev/", "html_url": "https://github.com/himanvic/Mausam-India"},
    {"name": "NaradNow", "description": "An Indian news and current-affairs dashboard with topic filters, search, and bookmarks.",
     "homepage": "https://naradnow.pages.dev/", "html_url": "https://github.com/himanvic/NaradNow"},
]


# ------------------------------------------------------------------ data
def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-updater"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r), r.status


def load():
    try:
        user, _ = api(f"/users/{USER}")
        repos, _ = api(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed")
        repos = [r for r in repos if not r["fork"] and not r["archived"] and r["name"].lower() != USER.lower()]
        repos.sort(key=lambda r: r["pushed_at"], reverse=True)
        for r in repos[:MAX_CARDS]:
            r["spark"] = weekly_commits(r["name"])
        return user, repos, True
    except Exception as e:  # offline / rate-limited -> honest fallback
        print("Live data unavailable, using README seed:", e)
        return None, [dict(s, seed=True) for s in SEED], False


def weekly_commits(name):
    try:
        data, status = api(f"/repos/{USER}/{name}/stats/commit_activity")
        if status == 200 and isinstance(data, list) and len(data) >= 12:
            w = [x["total"] for x in data[-12:]]
            return w if sum(w) > 0 else None
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ svg helpers
def fmt(v):
    return ("%.5f" % v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def anim(attr, pts, cycle, discrete=False):
    pts = sorted(pts, key=lambda p: p[0])
    if pts[0][0] > 0:
        pts.insert(0, (0, pts[0][1]))
    if pts[-1][0] < cycle:
        pts.append((cycle, pts[-1][1]))
    kt = ";".join(fmt(round(t / cycle, 5)) for t, _ in pts)
    vs = ";".join(fmt(v) for _, v in pts)
    mode = ' calcMode="discrete"' if discrete else ""
    return f'<animate attributeName="{attr}" dur="{cycle}s" repeatCount="indefinite" keyTimes="{kt}" values="{vs}"{mode}/>'


def typed(uid, text, x, y, size, fill, cycle, t0, t_type, t_end, charw, cur_end=None):
    n = max(len(text), 1)
    dt = t_type / n
    w = [(0, 0)] + [(round(t0 + i * dt, 3), round(i * charw + (14 if i == n else 0), 1)) for i in range(1, n + 1)] + [(t_end, 0)]
    defs = (f'<clipPath id="{uid}"><rect x="{x}" y="{y - size}" height="{round(size * 1.6)}" width="0">{anim("width", w, cycle, True)}</rect></clipPath>')
    ce = cur_end if cur_end else t0 + t_type + 0.5
    xs = sorted([(0, x)] + [(round(t0 + i * dt, 3), round(x + i * charw, 1)) for i in range(1, n + 1)] + [(ce, x), (cycle, x)])
    body = (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{fill}" clip-path="url(#{uid})" xml:space="preserve">{esc(text)}</text>'
            f'<g opacity="0">{anim("opacity", [(0, 0), (t0, 1), (ce, 0)], cycle, True)}'
            f'<rect x="{x}" y="{round(y - size + 2)}" width="{round(size * 0.55, 1)}" height="{round(size * 1.15, 1)}" fill="{fill}">'
            f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur=".9s" repeatCount="indefinite" calcMode="discrete"/>'
            f'<animate attributeName="x" dur="{cycle}s" repeatCount="indefinite" calcMode="discrete" keyTimes="{";".join(fmt(round(t / cycle, 5)) for t, _ in xs)}" values="{";".join(fmt(v) for _, v in xs)}"/>'
            f'</rect></g>')
    return defs, body


def themed(svg):
    if THEME in THEMES:
        mp = {k.upper(): v for k, v in THEMES[THEME].items()}
        svg = re.compile("|".join(re.escape(k) for k in mp), re.I).sub(lambda m: mp[m.group(0).upper()], svg)
    return svg


def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(themed(text))


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def short_date(iso):
    return iso[:10] if iso else ""


# ------------------------------------------------------------------ card
def card_svg(r, color):
    spark = r.get("spark")
    wrap = 34 if spark else 50
    desc = (r.get("description") or "").strip() or "No description on GitHub yet."
    lines = textwrap.wrap(desc, wrap) or [""]
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][:wrap - 3].rstrip() + "..."
    lines += [""] * (2 - len(lines))
    if r.get("seed"):
        tag = "PUBLIC REPO"
    else:
        tag = f'{(r.get("language") or "REPO")} // STARS {r.get("stargazers_count", 0)} // PUSHED {short_date(r.get("pushed_at"))}'.upper()
    tag = tag[:40]
    title = r["name"].upper()
    tsize = 22 if len(title) <= 16 else 17
    sp = ""
    if spark:
        mx = max(spark)
        pts = " ".join(f"{400 + i * 14},{round(112 - (v / mx) * 62)}" for i, v in enumerate(spark))
        sp = (f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" pathLength="300" stroke-dasharray="300" stroke-dashoffset="300" filter="url(#gl)">'
              f'<animate attributeName="stroke-dashoffset" values="300;0;0;300" keyTimes="0;.45;.9;1" dur="5s" repeatCount="indefinite"/></polyline>'
              f'<text x="400" y="132" font-family="{FONT}" font-size="8.5" letter-spacing="1.5" fill="{color}" opacity=".7">COMMITS/WK, 12 WEEKS</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="580" height="170" viewBox="0 0 580 170" role="img" aria-label="{esc(r["name"])} project card">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0A1128"/><stop offset="1" stop-color="#120C26"/></linearGradient>
<linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="{color}" stop-opacity="0"/><stop offset=".5" stop-color="{color}" stop-opacity=".16"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient>
<pattern id="gr" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="{color}" stroke-opacity=".06"/></pattern>
<filter id="gl" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="c"><rect x="1" y="1" width="578" height="168" rx="14"/></clipPath>
</defs>
<rect x="1" y="1" width="578" height="168" rx="14" fill="url(#bg)"/>
<g clip-path="url(#c)"><rect width="580" height="170" fill="url(#gr)"/><rect x="-120" y="0" width="120" height="170" fill="url(#beam)"><animate attributeName="x" values="-120;580" dur="4.5s" repeatCount="indefinite"/></rect></g>
<rect x="1" y="1" width="578" height="168" rx="14" fill="none" stroke="{color}" stroke-opacity=".25"/>
<rect x="1" y="1" width="578" height="168" rx="14" fill="none" stroke="{color}" stroke-width="2.5" pathLength="1000" stroke-dasharray="130 870" filter="url(#gl)"><animate attributeName="stroke-dashoffset" from="0" to="-1000" dur="5s" repeatCount="indefinite"/></rect>
<g transform="translate(58 72)">
<polygon points="0,-30 26,-15 26,15 0,30 -26,15 -26,-15" fill="none" stroke="{color}" stroke-width="2"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="12s" repeatCount="indefinite"/></polygon>
<rect x="-10" y="-10" width="20" height="20" fill="{color}" fill-opacity=".85" transform="rotate(45)"><animateTransform attributeName="transform" type="rotate" from="45" to="-315" dur="6s" repeatCount="indefinite"/></rect>
<circle r="38" fill="none" stroke="{color}" stroke-opacity=".4"><animate attributeName="r" values="30;44" dur="2.4s" repeatCount="indefinite"/><animate attributeName="opacity" values=".7;0" dur="2.4s" repeatCount="indefinite"/></circle>
</g>
<g font-family="{FONT}">
<text x="118" y="62" font-size="{tsize}" font-weight="800" fill="#F0FDFF" letter-spacing="1">{esc(title)}</text>
<rect x="118" y="70" width="0" height="2" fill="{color}"><animate attributeName="width" values="0;150;150;0" keyTimes="0;.3;.8;1" dur="5s" repeatCount="indefinite"/></rect>
<text x="118" y="96" font-size="12.5" fill="#9FB6D9">{esc(lines[0])}</text>
<text x="118" y="115" font-size="12.5" fill="#9FB6D9">{esc(lines[1])}</text>
<circle cx="124" cy="147" r="4" fill="{color}" filter="url(#gl)"><animate attributeName="opacity" values="1;.2;1" dur="1.6s" repeatCount="indefinite"/></circle>
<text x="136" y="151" font-size="10" letter-spacing="2" fill="{color}">{esc(tag)}</text>
<text x="530" y="151" font-size="10" letter-spacing="2" fill="#E0FCFF" text-anchor="end">OPEN</text>
<path d="M538 146h14m-5-5 5 5-5 5" fill="none" stroke="{color}" stroke-width="2"><animateTransform attributeName="transform" type="translate" values="0 0;5 0;0 0" dur="1.2s" repeatCount="indefinite"/></path>
</g>
{sp}
</svg>'''


# ------------------------------------------------------------------ terminal
def terminal_svg(user, repos, live):
    cw, px = 8.4, 28
    cmdx = px + 9 * cw
    rows = [("cmd", "whoami"), ("out", f'{esc((user or {}).get("name") or USER)} <tspan fill="#67E8F9">::</tspan> learner / builder'),
            ("cmd", "cat focus.txt"), ("out", '<tspan fill="#67E8F9" font-weight="700">C++</tspan>  +  <tspan fill="#A78BFA" font-weight="700">PYTHON</tspan>'),
            ("cmd", "ls projects/")]
    for r in repos[:MAX_CARDS]:
        d = (r.get("description") or "").strip()
        d = (d[:46] + "...") if len(d) > 49 else d
        rows.append(("out", f'<tspan fill="#34D399">[ ok ]</tspan> {esc(r["name"][:16]):<16} <tspan fill="#536C91">{esc(d)}</tspan>'))
    if live and repos:
        rows += [("cmd", "git log -1 --format=%cd"), ("out", f'<tspan fill="#F472B6">{short_date(repos[0]["pushed_at"])}</tspan>  <tspan fill="#536C91">({esc(repos[0]["name"])})</tspan>')]
    n = len(rows) + 1
    h = 70 + n * 24 + 26
    t, items = 0.5, []
    for kind, val in rows:
        if kind == "cmd":
            tt = round(0.07 * len(val) + 0.35, 2)
            items.append((kind, val, t, tt))
            t += tt + 0.6
        else:
            items.append((kind, val, t, 0))
            t += 0.35
    last = t + 0.2
    TE = last + 6
    C = round(TE + 2, 1)

    def fade(a):
        return anim("opacity", [(0, 0), (a, 0), (a + .25, 1), (TE, 1), (TE + .4, 0)], C)

    prompt = (lambda y, a: f'<text x="{px}" y="{y}" font-family="{FONT}" font-size="14" fill="#67E8F9" opacity="0" xml:space="preserve">{fade(a)}h@sys<tspan fill="#8FA9CF">:</tspan><tspan fill="#A78BFA">~</tspan><tspan fill="#8FA9CF">$</tspan></text>')
    defs, body = [], []
    for i, (kind, val, a, tt) in enumerate(items):
        y = 70 + i * 24
        if kind == "cmd":
            d, b = typed(f"c{i}", val, round(cmdx, 1), y, 14, "#E0FCFF", C, a, tt, TE + .2, cw)
            defs.append(d)
            body += [prompt(y, a - .05), b]
        else:
            body.append(f'<text x="{px}" y="{y}" font-family="{FONT}" font-size="14" fill="#B6C8E6" opacity="0" xml:space="preserve">{fade(a)}{val}</text>')
    y = 70 + len(items) * 24
    body += [prompt(y, last),
             f'<g opacity="0">{anim("opacity", [(0, 0), (last, 1), (TE, 1), (TE + .3, 0)], C, True)}<rect x="{round(cmdx, 1)}" y="{y - 12}" width="8" height="16" fill="#67E8F9"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite" calcMode="discrete"/></rect></g>']
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{h}" viewBox="0 0 900 {h}" role="img" aria-label="Animated terminal listing real repositories">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#060914"/><stop offset="1" stop-color="#120C26"/></linearGradient>
<linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#67E8F9" stop-opacity="0"/><stop offset=".5" stop-color="#67E8F9" stop-opacity=".12"/><stop offset="1" stop-color="#67E8F9" stop-opacity="0"/></linearGradient>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity=".035"/></pattern>
<clipPath id="win"><rect x="1" y="1" width="898" height="{h - 2}" rx="14"/></clipPath>{"".join(defs)}
</defs>
<rect x="1" y="1" width="898" height="{h - 2}" rx="14" fill="url(#bg)" stroke="#67E8F9" stroke-opacity=".35" stroke-width="1.5"/>
<g clip-path="url(#win)">
<rect x="1" y="1" width="898" height="38" fill="#0B1230"/><path d="M1 39H899" stroke="#67E8F9" stroke-opacity=".25"/>
<circle cx="24" cy="20" r="6" fill="#F87171"/><circle cx="46" cy="20" r="6" fill="#FBBF24"/><circle cx="68" cy="20" r="6" fill="#34D399"/>
<text x="450" y="25" text-anchor="middle" font-family="{FONT}" font-size="12" fill="#7DD3FC" letter-spacing="1.5">{esc(USER)}@h-system : ~/learn</text>
{"".join(body)}
<rect x="1" y="1" width="898" height="{h - 2}" fill="url(#scan)"/>
<rect x="1" y="-80" width="898" height="80" fill="url(#beam)"><animate attributeName="y" values="-80;{h};{h}" dur="5s" repeatCount="indefinite"/></rect>
</g></svg>'''


# ------------------------------------------------------------------ stats
def stats_svg(user, repos, live):
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="230" viewBox="0 0 900 230" role="img" aria-label="Real GitHub numbers">'
            f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#060914"/><stop offset="1" stop-color="#120C26"/></linearGradient>'
            f'<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="#22D3EE" stop-opacity="0"/><stop offset=".5" stop-color="#67E8F9"/><stop offset="1" stop-color="#A78BFA" stop-opacity="0"/></linearGradient>'
            f'<filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
            f'<rect x="1" y="1" width="898" height="228" rx="14" fill="url(#bg)" stroke="#67E8F9" stroke-opacity=".3" stroke-width="1.5"/>')
    title = lambda s: f'<text x="30" y="36" font-family="{FONT}" font-size="12" letter-spacing="3" fill="#7DD3FC">{s}</text><path d="M30 46H870" stroke="url(#ln)"/>'
    if not live:
        return (head + title("LIVE GITHUB NUMBERS") +
                f'<text x="450" y="130" text-anchor="middle" font-family="{FONT}" font-size="14" fill="#8FA9CF">Real numbers appear here after the first auto-update run.</text>'
                f'<text x="450" y="154" text-anchor="middle" font-family="{FONT}" font-size="11" letter-spacing="2" fill="#536C91">ACTIONS TAB  &gt;  UPDATE LIVE PROFILE DATA  &gt;  RUN WORKFLOW</text></svg>')
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    since = (user or {}).get("created_at", "")[:4]
    boxes = [("PUBLIC REPOS", (user or {}).get("public_repos", len(repos))), ("FOLLOWERS", (user or {}).get("followers", 0)),
             ("STARS (REPOS)", stars), ("ON GITHUB SINCE", since)]
    b = title(f"LIVE GITHUB NUMBERS // {esc(USER)} // UPDATED {datetime.datetime.utcnow().strftime('%Y-%m-%d')}")
    for i, (lab, val) in enumerate(boxes):
        x = 30 + i * 100
        c = COLORS[i]
        b += (f'<text x="{x}" y="100" font-family="{FONT}" font-size="30" font-weight="800" fill="{c}" filter="url(#gl)">{esc(str(val))}</text>'
              f'<text x="{x}" y="120" font-family="{FONT}" font-size="8.5" letter-spacing="1.2" fill="#8FA9CF">{lab}</text>'
              f'<rect x="{x}" y="128" width="0" height="2" fill="{c}"><animate attributeName="width" values="0;70;70;0" keyTimes="0;.3;.85;1" dur="5s" begin="{i * .2}s" repeatCount="indefinite"/></rect>')
    langs = Counter(r["language"] for r in repos if r.get("language"))
    top = langs.most_common(5)
    b += f'<text x="450" y="76" font-family="{FONT}" font-size="10" letter-spacing="3" fill="#7DD3FC">PRIMARY LANGUAGE PER REPO</text>'
    total = sum(langs.values()) or 1
    for i, (lang, cnt) in enumerate(top):
        y = 96 + i * 24
        c = COLORS[i % len(COLORS)]
        w = round(300 * cnt / total)
        b += (f'<text x="450" y="{y + 10}" font-family="{FONT}" font-size="12" font-weight="700" fill="{c}">{esc(lang)}</text>'
              f'<rect x="560" y="{y}" width="300" height="12" rx="6" fill="#0B1230" stroke="{c}" stroke-opacity=".35"/>'
              f'<rect x="561" y="{y + 1}" width="0" height="10" rx="5" fill="{c}" fill-opacity=".85">{anim("width", [(0, 0), (2 + i * .25, max(w - 2, 4)), (7, max(w - 2, 4)), (8, 0)], 8)}</rect>'
              f'<text x="868" y="{y + 10}" text-anchor="end" font-family="{FONT}" font-size="10" fill="#8FA9CF">{cnt}</text>')
    if not top:
        b += f'<text x="450" y="110" font-family="{FONT}" font-size="12" fill="#536C91">No languages detected yet.</text>'
    return head + b + "</svg>"


# ------------------------------------------------------------------ readme
def projects_table(repos):
    cells = []
    for r in repos[:MAX_CARDS]:
        s = slug(r["name"])
        live = (r.get("homepage") or "").strip()
        live = live if live.startswith("http") else ""
        target = live or r["html_url"]
        links = f'<a href="{r["html_url"]}">repo</a>' + (f' · <a href="{live}">live</a>' if live else "")
        cells.append(f'    <td width="50%" align="center">\n      <a href="{target}"><img src="assets/card-{s}.svg" alt="{esc(r["name"])} project card" width="100%" /></a>\n      <br /><sub>{links}</sub>\n    </td>')
    if len(cells) % 2:
        cells.append('    <td width="50%"></td>')
    rows = ["  <tr>\n" + "\n".join(cells[i:i + 2]) + "\n  </tr>" for i in range(0, len(cells), 2)]
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def main():
    user, repos, live = load()
    repos = repos[:MAX_CARDS]
    keep = set()
    for i, r in enumerate(repos):
        fn = f"assets/card-{slug(r['name'])}.svg"
        keep.add(os.path.basename(fn))
        write(fn, card_svg(r, COLORS[i % len(COLORS)]))
    for f in os.listdir(os.path.join(ROOT, "assets")):
        if f.startswith("card-") and f not in keep:
            os.remove(os.path.join(ROOT, "assets", f))
    write("assets/terminal.svg", terminal_svg(user, repos, live))
    write("assets/stats.svg", stats_svg(user, repos, live))
    readme = os.path.join(ROOT, "README.md")
    txt = open(readme, encoding="utf-8").read()
    new = re.sub(r"(<!--REPOS:START-->).*?(<!--REPOS:END-->)", lambda m: m.group(1) + "\n" + projects_table(repos) + "\n" + m.group(2), txt, flags=re.S)
    open(readme, "w", encoding="utf-8").write(new)
    print(("LIVE" if live else "SEED"), "-", len(repos), "repos")


if __name__ == "__main__":
    main()
