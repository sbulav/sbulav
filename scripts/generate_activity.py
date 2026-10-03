#!/usr/bin/env python3
"""Generate activity SVGs using GitHub's contribution calendar and the gh CLI.

Run from the repository root: python3 scripts/generate_activity.py
Locally, uses gh's login; Actions supplies its built-in token via GH_TOKEN.
Only dates and aggregate contribution counts are requested and published.
"""

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import math
from pathlib import Path
import subprocess


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

THEMES = {
    "light": {"text": "#1f2328", "muted": "#59636e", "line": "#1a7f37", "grid": "#d1d9e0"},
    "dark": {"text": "#f0f6fc", "muted": "#9198a1", "line": "#3fb950", "grid": "#3d444d"},
}


def calendar_days(payload, start, end):
    """Reject incomplete/error responses instead of drawing misleading zeros."""
    if payload.get("errors"):
        raise ValueError("GitHub returned GraphQL errors; keeping existing charts")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts = {}
    for week in weeks:
        for day in week["contributionDays"]:
            when = date.fromisoformat(day["date"])
            if start <= when <= end:
                count = day["contributionCount"]
                if type(count) is not int or count < 0 or when in counts:
                    raise ValueError("Invalid or duplicate contribution count")
                counts[when] = count
    expected = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if set(counts) != set(expected):
        raise ValueError("Incomplete contribution calendar; keeping existing charts")
    return [(when, counts[when]) for when in expected]


def render(days, theme):
    colors = THEMES[theme]
    left, right, top, bottom = 46, 818, 76, 192
    # A nonzero scale also keeps an entirely quiet month legible.
    step = max(1, math.ceil(max(count for _, count in days) / 4))
    ceiling = step * 4
    points = [
        (left + i * (right - left) / (len(days) - 1), bottom - count / ceiling * (bottom - top))
        for i, (_, count) in enumerate(days)
    ]
    line = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    total = sum(count for _, count in days)
    start, end = days[0][0], days[-1][0]
    period = f"{start:%d %b %Y} – {end:%d %b %Y} · UTC"
    description = "; ".join(f"{when.isoformat()}: {count}" for when, count in days)
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="840" height="232" viewBox="0 0 840 232" role="img" aria-labelledby="title description">',
        '<title id="title">Recent GitHub activity</title>',
        f'<desc id="description">{total} contributions over 30 completed days. {escape(description)}</desc>',
        '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">',
        f'<text x="12" y="26" fill="{colors["text"]}" font-size="18" font-weight="600">Recent GitHub activity</text>',
        f'<text x="12" y="49" fill="{colors["muted"]}" font-size="12">{period}</text>',
        f'<text x="818" y="26" text-anchor="end" fill="{colors["muted"]}" font-size="13">{total} contributions</text>',
    ]
    for value in range(0, ceiling + 1, step):
        y = bottom - value / ceiling * (bottom - top)
        svg.extend([
            f'<path d="M {left} {y:.2f} H {right}" stroke="{colors["grid"]}" stroke-opacity="0.5"/>',
            f'<text x="36" y="{y + 4:.2f}" text-anchor="end" fill="{colors["muted"]}" font-size="11">{value}</text>',
        ])
    svg.extend([
        f'<polygon points="{left},{bottom} {line} {right},{bottom}" fill="{colors["line"]}" fill-opacity="0.08"/>',
        f'<polyline points="{line}" fill="none" stroke="{colors["line"]}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>',
    ])
    for (when, count), (x, y) in zip(days, points):
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5" fill="{colors["line"]}"><title>{when.isoformat()}: {count} contributions</title></circle>')
    for i in (0, 7, 14, 21, 29):
        anchor = "start" if i == 0 else "end" if i == 29 else "middle"
        svg.append(f'<text x="{points[i][0]:.2f}" y="216" text-anchor="{anchor}" fill="{colors["muted"]}" font-size="11">{days[i][0]:%d %b}</text>')
    svg.append("</g></svg>\n")
    return "\n".join(svg)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="sbulav")
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    args = parser.parse_args()
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=29)
    request = {"query": QUERY, "variables": {
        "login": args.username,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{end.isoformat()}T23:59:59Z",
    }}
    response = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"], input=json.dumps(request),
        capture_output=True, text=True, check=True, timeout=60,
    )
    days = calendar_days(json.loads(response.stdout), start, end)
    charts = {theme: render(days, theme) for theme in THEMES}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for theme, chart in charts.items():
        (args.output_dir / f"activity-{theme}.svg").write_text(chart, encoding="utf-8")
    print(f"Generated activity charts for {start} to {end}")


if __name__ == "__main__":
    main()
