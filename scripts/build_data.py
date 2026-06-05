#!/usr/bin/env python3
"""Build docs/data.json for the dashboard.

Reads the member registry, fetches each member's merged pull requests from the
GitHub Search API, merges in the manual contributions, computes summary stats,
and writes a single JSON file the static site consumes.

Usage:
    GITHUB_TOKEN=ghp_xxx python scripts/build_data.py

Environment:
    GITHUB_TOKEN   Strongly recommended. Without it you are limited to ~10
                   search requests/min and will likely be rate-limited.
    SINCE_YEAR     Optional. Only count PRs created on/after Jan 1 of this year.
    OFFLINE        Optional. If set to "1", skip all network calls and build
                   from manual contributions only (used for local testing/CI
                   smoke tests).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data.json"

API = "https://api.github.com/search/issues"
PER_PAGE = 100
MAX_PAGES = 5  # up to 500 most-recent merged PRs per member
USER_AGENT = "dsi-oss-tracker"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def gh_get(url: str, token: str | None) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", USER_AGENT)
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            # 403 with a rate-limit reset → wait and retry.
            if exc.code in (403, 429):
                reset = exc.headers.get("X-RateLimit-Reset")
                wait = 60
                if reset:
                    wait = max(1, int(reset) - int(time.time())) + 1
                wait = min(wait, 90)
                print(f"  rate-limited, sleeping {wait}s (attempt {attempt + 1})", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as exc:
            print(f"  network error: {exc}; retrying", file=sys.stderr)
            time.sleep(5)
    raise RuntimeError(f"giving up on {url}")


def repo_from_url(repo_api_url: str) -> str:
    # https://api.github.com/repos/numpy/numpy -> numpy/numpy
    return repo_api_url.split("/repos/", 1)[-1]


def fetch_merged_prs(login: str, token: str | None, since_year: int | None) -> list[dict]:
    query = f"type:pr is:merged author:{login}"
    if since_year:
        query += f" created:>={since_year}-01-01"
    results: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        params = urllib.parse.urlencode(
            {"q": query, "per_page": PER_PAGE, "page": page, "sort": "created", "order": "desc"}
        )
        data = gh_get(f"{API}?{params}", token)
        items = data.get("items", [])
        for it in items:
            repo = repo_from_url(it["repository_url"])
            results.append(
                {
                    "member": login,
                    "project": repo,
                    "title": it.get("title", "").strip(),
                    "url": it.get("html_url"),
                    "type": "pr",
                    "date": (it.get("closed_at") or it.get("created_at") or "")[:10],
                    "source": "github",
                    "external": not repo.lower().startswith(login.lower() + "/"),
                }
            )
        if len(items) < PER_PAGE:
            break
        # Be gentle with the search rate limit (30 req/min authenticated).
        time.sleep(2)
    return results


def normalize_manual(contribs: list[dict]) -> list[dict]:
    out = []
    for c in contribs or []:
        date = c.get("date")
        if hasattr(date, "isoformat"):
            date = date.isoformat()
        out.append(
            {
                "member": c["member"],
                "project": c["project"],
                "title": c["title"],
                "url": c["url"],
                "type": c.get("type", "other"),
                "date": str(date)[:10] if date else "",
                "source": "manual",
                "external": True,
                "description": c.get("description"),
            }
        )
    return out


def build() -> dict:
    members_doc = load_yaml(DATA / "members.yaml")
    contribs_doc = load_yaml(DATA / "contributions.yaml")
    members = members_doc.get("members", [])
    manual = normalize_manual(contribs_doc.get("contributions", []))

    token = os.environ.get("GITHUB_TOKEN")
    offline = os.environ.get("OFFLINE") == "1"
    since_year = None
    if os.environ.get("SINCE_YEAR"):
        since_year = int(os.environ["SINCE_YEAR"])

    if not token and not offline:
        print("⚠️  No GITHUB_TOKEN set — requests will be rate-limited.", file=sys.stderr)

    all_contribs: list[dict] = list(manual)
    member_out: list[dict] = []

    for m in members:
        login = m["github"]
        gh_contribs: list[dict] = []
        if not offline:
            print(f"Fetching contributions for @{login} …", file=sys.stderr)
            try:
                gh_contribs = fetch_merged_prs(login, token, since_year)
            except Exception as exc:  # don't let one member break the whole build
                print(f"  failed for @{login}: {exc}", file=sys.stderr)

        all_contribs.extend(gh_contribs)
        member_manual = [c for c in manual if c["member"].lower() == login.lower()]
        combined = gh_contribs + member_manual

        projects = {c["project"] for c in combined if c.get("project")}
        external_prs = [c for c in combined if c.get("external")]
        member_out.append(
            {
                "name": m.get("name", login),
                "github": login,
                "role": m.get("role", "member"),
                "affiliation": m.get("affiliation", "DSI"),
                "joined": m.get("joined"),
                "active": m.get("active", True),
                "links": m.get("links", {}),
                "stats": {
                    "total": len(combined),
                    "merged_prs": len([c for c in combined if c["type"] == "pr"]),
                    "external": len(external_prs),
                    "projects": len(projects),
                },
            }
        )

    # De-duplicate contributions by URL (a manual entry may mirror a GitHub PR).
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for c in sorted(all_contribs, key=lambda x: x.get("date") or "", reverse=True):
        key = (c.get("url") or "").lower()
        if key and key in seen_urls:
            continue
        if key:
            seen_urls.add(key)
        deduped.append(c)

    by_project = Counter(c["project"] for c in deduped if c.get("project"))
    by_type = Counter(c["type"] for c in deduped)
    by_month = Counter(c["date"][:7] for c in deduped if c.get("date"))

    summary = {
        "members": len(member_out),
        "active_members": len([m for m in member_out if m["active"]]),
        "contributions": len(deduped),
        "projects": len(by_project),
        "external_contributions": len([c for c in deduped if c.get("external")]),
        "top_projects": by_project.most_common(15),
        "by_type": dict(by_type),
        "by_month": dict(sorted(by_month.items())),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "members": sorted(member_out, key=lambda m: m["stats"]["total"], reverse=True),
        "contributions": deduped,
    }


def main() -> int:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    s = payload["summary"]
    print(
        f"✅ Wrote {OUT.relative_to(ROOT)}: "
        f"{s['members']} members, {s['contributions']} contributions, "
        f"{s['projects']} projects."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
