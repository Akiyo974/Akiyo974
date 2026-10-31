#!/usr/bin/env python3
"""Rebuild the "Recently shipped" block of README.md from public GitHub activity.

Lists the most recently pushed public, non-fork, non-archived repositories of
the profile owner and rewrites the content between the markers:

    <!--START_SECTION:shipped-->
    <!--END_SECTION:shipped-->

Env:
    GITHUB_TOKEN   token for the GitHub API (optional locally, set in Actions)
    GH_USER        profile owner (default: Akiyo974)
    SHIPPED_LIMIT  number of rows (default: 5)
    SHIPPED_SKIP   comma separated repo names to ignore

Repositories without a description are skipped: add one on GitHub to list it.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER = os.environ.get("GH_USER", "Akiyo974")
LIMIT = int(os.environ.get("SHIPPED_LIMIT", "5"))
SKIP = {s.strip().lower() for s in os.environ.get("SHIPPED_SKIP", "").split(",") if s.strip()}
SKIP.add(USER.lower())  # the profile repo itself

README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!--START_SECTION:shipped-->"
END = "<!--END_SECTION:shipped-->"


def api(path: str):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USER}-readme")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def ago(iso: str) -> str:
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    days = (datetime.now(timezone.utc) - then).days
    if days < 1:
        return "today"
    if days < 2:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return then.strftime("%b %Y")


def clean(text: str, limit: int = 90) -> str:
    text = " ".join((text or "").split()).replace("|", "/")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build() -> str:
    repos = api(f"/users/{USER}/repos?per_page=100&sort=pushed&type=owner")
    picked = [
        r for r in repos
        if not r["fork"] and not r["archived"] and not r["private"]
        and r["name"].lower() not in SKIP
        and (r.get("description") or "").strip()  # an empty row reads as unfinished
    ][:LIMIT]

    rows = ["| Repo | What | Stack | Last push |", "| :-- | :-- | :-- | :-- |"]
    for r in picked:
        name = f"[**{r['name']}**]({r['html_url']})"
        if r.get("homepage"):
            name += f" [↗]({r['homepage']})"
        desc = clean(r.get("description") or "")
        lang = f"`{r['language']}`" if r.get("language") else ""
        rows.append(f"| {name} | {desc} | {lang} | <sub>{ago(r['pushed_at'])}</sub> |")
    return "\n".join(rows)


def main() -> int:
    content = README.read_text(encoding="utf-8")
    if START not in content or END not in content:
        print("markers not found in README.md", file=sys.stderr)
        return 1
    block = f"{START}\n{build()}\n{END}"
    updated = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, content, flags=re.S)
    if updated != content:
        README.write_text(updated, encoding="utf-8")
        print("README updated")
    else:
        print("no change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
