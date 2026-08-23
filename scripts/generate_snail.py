#!/usr/bin/env python3
"""
Generates an animated SVG of a snail crawling across a GitHub contribution
grid, colored by real contribution levels (fetched from the public,
unauthenticated GitHub contributions endpoint - no token required).

Usage: python3 generate_snail.py <github_username> <output_path>
"""
import re
import sys
import urllib.request

CELL = 11
GAP = 3
PITCH = CELL + GAP
MARGIN_L = 16
MARGIN_T = 30
MARGIN_R = 16
MARGIN_B = 14
TOTAL_DURATION = 30  # seconds for one full crawl of the whole grid

LEVEL_COLORS = {
    "0": "#161b22",
    "1": "#4c3575",
    "2": "#7c3aed",
    "3": "#a855f7",
    "4": "#e879f9",
}
LEVEL_STROKE = {
    "0": "#22272e",
    "1": "#5b3f8f",
    "2": "#8b4ff0",
    "3": "#c084fc",
    "4": "#f0abfc",
}


def fetch_contributions(username: str):
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    pattern = re.compile(
        r'data-date="([\d-]+)" id="contribution-day-component-(\d+)-(\d+)" data-level="(\d)"'
    )
    matches = pattern.findall(html)
    cells = []
    for date, day, week, level in matches:
        cells.append({"date": date, "day": int(day), "week": int(week), "level": level})
    return cells


def build_svg(cells, username: str) -> str:
    if not cells:
        raise ValueError("no contribution cells parsed")

    max_week = max(c["week"] for c in cells)
    max_day = max(c["day"] for c in cells)
    cols = max_week + 1
    rows = max_day + 1

    grid = {(c["week"], c["day"]): c for c in cells}

    # boustrophedon (column-major, alternating direction) traversal order
    order = []
    for w in range(cols):
        day_range = range(rows) if w % 2 == 0 else range(rows - 1, -1, -1)
        for d in day_range:
            if (w, d) in grid:
                order.append(grid[(w, d)])

    n = len(order)
    step = TOTAL_DURATION / n

    def cx(week):
        return MARGIN_L + week * PITCH + CELL / 2

    def cy(day):
        return MARGIN_T + day * PITCH + CELL / 2

    width = MARGIN_L + cols * PITCH - GAP + MARGIN_R
    height = MARGIN_T + rows * PITCH - GAP + MARGIN_B

    # motion path through cell centers, in crawl order
    path_pts = [(cx(c["week"]), cy(c["day"])) for c in order]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in path_pts)

    total_contribs = sum(1 for c in order if c["level"] != "0")

    svg_parts = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" font-family="Segoe UI, Helvetica, Arial, sans-serif">'
    )

    svg_parts.append(f"""
  <defs>
    <linearGradient id="shellGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#c4b5fd"/>
      <stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>
    <linearGradient id="bodyGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#f0abfc" stop-opacity="0"/>
      <stop offset="100%" stop-color="#e9d5ff" stop-opacity="0.85"/>
    </linearGradient>
    <radialGradient id="trailGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#c084fc" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#c084fc" stop-opacity="0"/>
    </radialGradient>
    <filter id="softBlur" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="1.6"/>
    </filter>
    <filter id="dropGlow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="0.9" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <style>
      .cell {{
        animation-name: cellPulse;
        animation-duration: {TOTAL_DURATION}s;
        animation-iteration-count: infinite;
        animation-timing-function: cubic-bezier(.2,.8,.3,1);
        transform-box: fill-box;
        transform-origin: center;
      }}
      @keyframes cellPulse {{
        0%   {{ filter: brightness(2.5) saturate(1.3); }}
        7%   {{ filter: brightness(1) saturate(1); }}
        100% {{ filter: brightness(1) saturate(1); }}
      }}
      .title {{ fill: #8b949e; font-size: 11px; }}
      .sub   {{ fill: #565f6d; font-size: 8.5px; font-style: italic; }}
    </style>
  </defs>
""")

    svg_parts.append(
        f'  <rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" rx="10" '
        f'fill="#0d1117" stroke="#21262d" stroke-width="1"/>'
    )
    svg_parts.append(
        f'  <text x="{MARGIN_L}" y="16" class="title">🐌 a year of commits, one slow lap</text>'
    )

    # cells
    for idx, c in enumerate(order):
        x = MARGIN_L + c["week"] * PITCH
        y = MARGIN_T + c["day"] * PITCH
        level = c["level"]
        fill = LEVEL_COLORS.get(level, LEVEL_COLORS["0"])
        stroke = LEVEL_STROKE.get(level, LEVEL_STROKE["0"])
        delay = -(idx * step)
        svg_parts.append(
            f'  <rect class="cell" x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" '
            f'rx="2.5" fill="{fill}" stroke="{stroke}" stroke-width="0.6" '
            f'style="animation-delay:{delay:.3f}s">'
            f'<title>{c["date"]}</title></rect>'
        )

    # trailing glow blob that follows the snail
    svg_parts.append(f"""
  <g>
    <ellipse cx="0" cy="0" rx="10" ry="4" fill="url(#trailGlow)" filter="url(#softBlur)">
      <animateMotion dur="{TOTAL_DURATION}s" repeatCount="indefinite" rotate="auto" path="{path_d}"/>
    </ellipse>
  </g>
""")

    # the snail itself
    svg_parts.append(f"""
  <g filter="url(#dropGlow)">
    <g>
      <ellipse cx="-4" cy="2" rx="7" ry="2.1" fill="url(#bodyGrad)"/>
      <circle cx="1.5" cy="-0.6" r="4" fill="url(#shellGrad)" stroke="#3b2166" stroke-width="0.5"/>
      <path d="M 1.5 -0.6 m -2.6 0 a 2.6 2.6 0 1 1 5.2 0" fill="none" stroke="#3b2166" stroke-width="0.5" opacity="0.6"/>
      <line x1="6" y1="0.4" x2="9.2" y2="-1.6" stroke="#e9d5ff" stroke-width="0.7" stroke-linecap="round"/>
      <circle cx="9.2" cy="-1.6" r="0.7" fill="#f472b6"/>
      <line x1="6" y1="1.8" x2="9.6" y2="1.1" stroke="#e9d5ff" stroke-width="0.7" stroke-linecap="round"/>
      <circle cx="9.6" cy="1.1" r="0.7" fill="#f472b6"/>
      <animateMotion dur="{TOTAL_DURATION}s" repeatCount="indefinite" rotate="auto" path="{path_d}"/>
    </g>
  </g>
""")

    svg_parts.append(
        f'  <text x="{width - MARGIN_R:.0f}" y="{height - 5:.0f}" text-anchor="end" class="sub">'
        f'{total_contribs} active days tracked</text>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def main():
    if len(sys.argv) != 3:
        print("usage: generate_snail.py <github_username> <output_path>", file=sys.stderr)
        sys.exit(1)
    username, out_path = sys.argv[1], sys.argv[2]
    cells = fetch_contributions(username)
    svg = build_svg(cells, username)
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"wrote {out_path} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
