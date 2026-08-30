#!/usr/bin/env python3
"""
Generates a self-hosted GitHub stats card (repos, stars, followers,
contributions, streaks, top languages) as a static SVG - no dependency
on third-party Vercel services that can go down or get rate-limited.

Uses the GitHub REST API (authenticated via GITHUB_TOKEN env var when
available, e.g. automatically inside GitHub Actions - falls back to
unauthenticated for local testing, which has a much lower rate limit)
plus the same public contribution-calendar scrape used by
generate_snail.py.

Usage: python3 generate_stats.py <github_username> <output_path>
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, timedelta

API = "https://api.github.com"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#563d7c", "Java": "#b07219", "C": "#555555",
    "C++": "#f34b7d", "Jupyter Notebook": "#DA5B0B", "Shell": "#89e051",
    "Dockerfile": "#384d54", "Go": "#00ADD8", "Rust": "#dea584",
}
DEFAULT_LANG_COLOR = "#8b8fa3"


def _req(url):
    headers = {"User-Agent": "profile-stats-script", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_profile(username):
    return _req(f"{API}/users/{username}")


def fetch_repos(username):
    return _req(f"{API}/users/{username}/repos?per_page=100")


def fetch_languages(repo_full_name):
    try:
        return _req(f"{API}/repos/{repo_full_name}/languages")
    except Exception:
        return {}


def fetch_contribution_days(username):
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")

    total_match = re.search(r'(\d+)\s*\n\s*contributions', html)
    total = int(total_match.group(1)) if total_match else 0

    pattern = re.compile(r'data-date="([\d-]+)"[^>]*data-level="(\d)"')
    days = [{"date": d, "level": int(l)} for d, l in pattern.findall(html)]
    days.sort(key=lambda x: x["date"])
    return total, days


def compute_streaks(days):
    if not days:
        return 0, 0
    longest = cur_run = 0
    prev_date = None
    for d in days:
        this_date = date.fromisoformat(d["date"])
        active = d["level"] > 0
        if active:
            if prev_date is not None and (this_date - prev_date).days == 1:
                cur_run += 1
            else:
                cur_run = 1
            longest = max(longest, cur_run)
        else:
            cur_run = 0
        prev_date = this_date

    # current streak = trailing run of active days ending at the last tracked day
    current = 0
    for d in reversed(days):
        if d["level"] > 0:
            current += 1
        else:
            break
    return current, longest


def build_svg(username, profile, repos, days, total_contribs):
    non_fork = [r for r in repos if not r.get("fork")]
    total_stars = sum(r.get("stargazers_count", 0) for r in non_fork)
    public_repos = profile.get("public_repos", len(repos))
    followers = profile.get("followers", 0)

    current_streak, longest_streak = compute_streaks(days)

    lang_bytes = {}
    for r in non_fork:
        full_name = r.get("full_name")
        if not full_name:
            continue
        langs = fetch_languages(full_name)
        for lang, n in langs.items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + n

    total_bytes = sum(lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:5]

    width = 460
    stat_rows = [
        ("Public repos", str(public_repos)),
        ("Total stars", str(total_stars)),
        ("Followers", str(followers)),
        ("Contributions (last yr)", str(total_contribs)),
        ("Current streak", f"{current_streak} day{'s' if current_streak != 1 else ''}"),
        ("Longest streak", f"{longest_streak} day{'s' if longest_streak != 1 else ''}"),
    ]

    body = []
    body.append(f'  <text x="20" y="28" class="h1">GitHub Stats — {username}</text>')

    y = 55
    for label, value in stat_rows:
        body.append(f'  <text x="20" y="{y}" class="label">{label}</text>')
        body.append(f'  <text x="{width-20}" y="{y}" text-anchor="end" class="value">{value}</text>')
        y += 24

    y += 10
    body.append(f'  <text x="20" y="{y}" class="label">Top languages</text>')
    y += 14
    bar_x = 20
    bar_w = width - 40
    bar_h = 10
    if top_langs:
        x_cursor = bar_x
        for lang, n in top_langs:
            frac = n / total_bytes
            seg_w = max(bar_w * frac, 2)
            color = LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)
            body.append(
                f'  <rect x="{x_cursor:.1f}" y="{y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}"/>'
            )
            x_cursor += seg_w
        y += bar_h + 18
        for lang, n in top_langs:
            frac = n / total_bytes
            color = LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)
            body.append(f'  <circle cx="24" cy="{y-4}" r="4" fill="{color}"/>')
            body.append(f'  <text x="34" y="{y}" class="langname">{lang}</text>')
            body.append(f'  <text x="{width-20}" y="{y}" text-anchor="end" class="pct">{frac*100:.1f}%</text>')
            y += 20
    else:
        body.append(f'  <text x="20" y="{y}" class="pct">no language data yet</text>')

    height = y + 14

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="Segoe UI, Helvetica, Arial, sans-serif">'
    )
    svg.append(f"""
  <defs>
    <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#7c3aed"/>
      <stop offset="100%" stop-color="#e879f9"/>
    </linearGradient>
    <style>
      .card {{ fill: #0d1117; stroke: #21262d; }}
      .h1 {{ fill: #e6e6ef; font-size: 15px; font-weight: 600; }}
      .label {{ fill: #8b949e; font-size: 12px; }}
      .value {{ fill: #c4b5fd; font-size: 12px; font-weight: 600; }}
      .langname {{ fill: #c9d1d9; font-size: 11px; }}
      .pct {{ fill: #8b949e; font-size: 10px; }}
    </style>
  </defs>
""")
    svg.append(f'  <rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="10" class="card"/>')
    svg.extend(body)
    svg.append("</svg>")
    return "\n".join(svg)


def main():
    if len(sys.argv) != 3:
        print("usage: generate_stats.py <github_username> <output_path>", file=sys.stderr)
        sys.exit(1)
    username, out_path = sys.argv[1], sys.argv[2]

    profile = fetch_profile(username)
    repos = fetch_repos(username)
    total_contribs, days = fetch_contribution_days(username)

    svg = build_svg(username, profile, repos, days, total_contribs)
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()