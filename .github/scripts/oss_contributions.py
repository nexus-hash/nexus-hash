"""Render assets/oss-contributions.svg: an animated card of the notable
repos (MIN_STARS+) where USERNAME has merged PRs.

Logos are embedded as data URIs because GitHub serves README SVGs as
images, which can't load external resources.
"""
import base64
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GH_USERNAME", "nexus-hash")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = "assets/oss-contributions.svg"
MIN_STARS = 500
MAX_TILES = 6
COLS = 3

WIDTH = 840
PAD = 24
GAP = 14
HEADER_H = 78
TILE_H = 68
TILE_W = (WIDTH - 2 * PAD - (COLS - 1) * GAP) // COLS
ACCENT = "#FFB454"


def gh(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def merged_prs():
    q = f"is:pr is:merged author:{USERNAME} -user:{USERNAME}"
    prs, page = [], 1
    while True:
        qs = urllib.parse.urlencode({"q": q, "sort": "updated", "per_page": 100, "page": page})
        batch = gh(f"/search/issues?{qs}")["items"]
        prs += batch
        if len(batch) < 100 or page == 10:
            return prs
        page += 1


def notable_repos(prs):
    """[(stars, name, meta, pr_count)] for MIN_STARS+ repos, most stars first."""
    counts = defaultdict(int)
    for pr in prs:
        counts[pr["repository_url"].removeprefix("https://api.github.com/repos/")] += 1
    repos = []
    for name, n in counts.items():
        meta = gh(f"/repos/{name}")
        if meta["stargazers_count"] >= MIN_STARS:
            repos.append((meta["stargazers_count"], name, meta, n))
    return sorted(repos, key=lambda r: r[0], reverse=True)


def logo_data_uri(avatar_url):
    with urllib.request.urlopen(f"{avatar_url}&s=80", timeout=30) as resp:
        mime = resp.headers.get_content_type()
        return f"data:{mime};base64,{base64.b64encode(resp.read()).decode()}"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def short_stars(n):
    if n >= 100_000:
        return f"{round(n / 1000)}k"
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def clip(text, limit=22):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tile(i, count, stars, name, meta):
    col, row = i % COLS, i // COLS
    # Center a partially filled row.
    in_row = min(COLS, count - row * COLS)
    offset = (COLS - in_row) * (TILE_W + GAP) // 2
    x = PAD + offset + col * (TILE_W + GAP)
    y = HEADER_H + row * (TILE_H + GAP)
    owner, repo = name.split("/")
    return f"""
  <g transform="translate({x},{y})">
    <g class="tile" style="animation-delay:{0.25 + i * 0.12:.2f}s">
      <rect class="card" width="{TILE_W}" height="{TILE_H}" rx="12" style="animation-delay:{i * 0.6:.1f}s"/>
      <clipPath id="logo{i}"><rect x="14" y="14" width="40" height="40" rx="10"/></clipPath>
      <image href="{logo_data_uri(meta['owner']['avatar_url'])}" x="14" y="14" width="40" height="40" clip-path="url(#logo{i})"/>
      <text x="68" y="31" class="owner">{escape(clip(owner, 26))}</text>
      <text x="68" y="51" class="repo">{escape(clip(repo))}</text>
      <text x="{TILE_W - 14}" y="51" class="stars" text-anchor="end">★ {short_stars(stars)}</text>
    </g>
  </g>"""


def render(prs):
    repos = notable_repos(prs)
    shown = repos[:MAX_TILES]
    rows = max(1, -(-len(shown) // COLS))
    height = HEADER_H + rows * TILE_H + (rows - 1) * GAP + PAD + (22 if len(repos) > MAX_TILES else 0)

    if repos:
        total = sum(r[3] for r in repos)
        orgs = {r[1].split("/")[0] for r in repos}
        summary = (
            f"{plural(total, 'merged PR')} · {plural(len(repos), 'repo')} · "
            f"{plural(len(orgs), 'org')}"
        )
        body = "".join(tile(i, len(shown), s, n, m) for i, (s, n, m, _) in enumerate(shown))
        if len(repos) > MAX_TILES:
            body += (
                f'\n  <text x="{WIDTH // 2}" y="{height - PAD + 4}" class="more" '
                f'text-anchor="middle">+ {plural(len(repos) - MAX_TILES, "more repo")}</text>'
            )
    else:
        summary = "first merged PRs incoming"
        body = (
            f'\n  <text x="{WIDTH // 2}" y="{HEADER_H + TILE_H // 2 + 5}" class="more" '
            f'text-anchor="middle">check back soon</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .label {{ font-size: 12px; font-weight: 700; letter-spacing: 2.5px; fill: {ACCENT}; }}
    .summary {{ font-size: 13px; fill: #8B949E; }}
    .owner {{ font-size: 11px; fill: #8B949E; }}
    .repo {{ font-size: 15px; font-weight: 600; fill: #E6EDF3; }}
    .stars {{ font-size: 12px; font-weight: 600; fill: {ACCENT}; }}
    .more {{ font-size: 12px; fill: #8B949E; }}
    .card {{ fill: #161B22; stroke: {ACCENT}; stroke-width: 1; stroke-opacity: .18;
             animation: glow 4.8s ease-in-out infinite; }}
    .tile, .fade {{ opacity: 0; animation: rise .6s cubic-bezier(.2,.7,.3,1) forwards; }}
    .dot {{ transform-origin: {PAD + 4}px 31px; animation: pulse 1.8s ease-in-out infinite; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes glow {{ 0%, 70%, 100% {{ stroke-opacity: .18; }} 35% {{ stroke-opacity: .85; }} }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: .35; transform: scale(.6); }} }}
    @media (prefers-reduced-motion: reduce) {{
      .tile, .fade, .card, .dot {{ animation: none; opacity: 1; }}
    }}
  </style>
  <defs>
    <linearGradient id="sweep" x1="0" x2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
      <stop offset=".5" stop-color="{ACCENT}"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="divider"><rect x="{PAD}" y="50" width="{WIDTH - 2 * PAD}" height="5"/></clipPath>
  </defs>
  <rect width="{WIDTH}" height="{height}" rx="16" fill="#0D1117"/>

  <circle class="dot" cx="{PAD + 4}" cy="31" r="4" fill="{ACCENT}"/>
  <text x="{PAD + 16}" y="35" class="label">OPEN SOURCE</text>
  <text x="{WIDTH - PAD}" y="35" class="summary fade" text-anchor="end">{escape(summary)}</text>
  <rect x="{PAD}" y="52" width="{WIDTH - 2 * PAD}" height="1" fill="#21262D"/>
  <rect x="{PAD}" y="51.5" width="140" height="2" fill="url(#sweep)" clip-path="url(#divider)">
    <animate attributeName="x" values="{PAD - 140};{WIDTH - PAD}" dur="3.2s" repeatCount="indefinite"/>
  </rect>
{body}
</svg>
"""


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(merged_prs()))


if __name__ == "__main__":
    main()
