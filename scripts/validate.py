#!/usr/bin/env python3
"""Validate data/members.yaml and data/contributions.yaml.

Run by the `validate` GitHub Action on every pull request, and usable locally:

    python scripts/validate.py

Exits non-zero and prints every problem found if anything is invalid.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

VALID_ROLES = {"faculty", "staff", "student", "postdoc", "affiliate", "member"}
VALID_TYPES = {"pr", "issue", "review", "docs", "talk", "maintainer", "release", "other"}

GITHUB_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def load(self, path: Path):
        if not path.exists():
            self.err(path.name, "file is missing")
            return None
        try:
            return yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            self.err(path.name, f"invalid YAML — {exc}")
            return None

    def _valid_date(self, value) -> bool:
        # PyYAML may parse YYYY-MM-DD into a date object already.
        if hasattr(value, "isoformat") and not isinstance(value, str):
            return True
        if not isinstance(value, str):
            return False
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def validate_members(self, doc) -> set[str]:
        usernames: set[str] = set()
        if doc is None:
            return usernames
        members = doc.get("members") if isinstance(doc, dict) else None
        if not isinstance(members, list) or not members:
            self.err("members.yaml", "must contain a non-empty `members` list")
            return usernames

        seen: dict[str, int] = {}
        for i, m in enumerate(members):
            where = f"members.yaml[{i}]"
            if not isinstance(m, dict):
                self.err(where, "entry must be a mapping")
                continue

            name = m.get("name")
            if not isinstance(name, str) or not name.strip():
                self.err(where, "`name` is required and must be a non-empty string")

            gh = m.get("github")
            if not isinstance(gh, str) or not GITHUB_USERNAME_RE.match(gh):
                self.err(where, f"`github` is required and must be a valid username (got {gh!r})")
            else:
                key = gh.lower()
                if key in seen:
                    self.err(where, f"duplicate github username {gh!r} (first seen at index {seen[key]})")
                else:
                    seen[key] = i
                    usernames.add(gh)

            role = m.get("role")
            if role not in VALID_ROLES:
                self.err(where, f"`role` must be one of {sorted(VALID_ROLES)} (got {role!r})")

            joined = m.get("joined")
            if joined is not None and not (isinstance(joined, str) and MONTH_RE.match(joined)):
                self.err(where, f"`joined` must be YYYY-MM if set (got {joined!r})")

            active = m.get("active")
            if active is not None and not isinstance(active, bool):
                self.err(where, f"`active` must be true/false if set (got {active!r})")

            links = m.get("links")
            if links is not None:
                if not isinstance(links, dict):
                    self.err(where, "`links` must be a mapping of label -> url")
                else:
                    for label, url in links.items():
                        if not isinstance(url, str) or not URL_RE.match(url):
                            self.err(where, f"link {label!r} must be an http(s) URL")

        return usernames

    def validate_contributions(self, doc, usernames: set[str]) -> None:
        if doc is None:
            return
        contribs = doc.get("contributions") if isinstance(doc, dict) else None
        if contribs is None:
            return  # optional file/section
        if not isinstance(contribs, list):
            self.err("contributions.yaml", "`contributions` must be a list")
            return

        known = {u.lower() for u in usernames}
        for i, c in enumerate(contribs):
            where = f"contributions.yaml[{i}]"
            if not isinstance(c, dict):
                self.err(where, "entry must be a mapping")
                continue

            member = c.get("member")
            if not isinstance(member, str) or not member.strip():
                self.err(where, "`member` is required")
            elif member.lower() not in known:
                self.err(where, f"`member` {member!r} is not a github username in members.yaml")

            for field in ("project", "title"):
                if not isinstance(c.get(field), str) or not c.get(field).strip():
                    self.err(where, f"`{field}` is required and must be a non-empty string")

            url = c.get("url")
            if not isinstance(url, str) or not URL_RE.match(url):
                self.err(where, f"`url` is required and must be an http(s) URL (got {url!r})")

            ctype = c.get("type")
            if ctype not in VALID_TYPES:
                self.err(where, f"`type` must be one of {sorted(VALID_TYPES)} (got {ctype!r})")

            if not self._valid_date(c.get("date")):
                self.err(where, f"`date` is required and must be YYYY-MM-DD (got {c.get('date')!r})")

    def run(self) -> int:
        members_doc = self.load(DATA / "members.yaml")
        usernames = self.validate_members(members_doc)
        contribs_doc = self.load(DATA / "contributions.yaml")
        self.validate_contributions(contribs_doc, usernames)

        if self.errors:
            print(f"❌ Validation failed with {len(self.errors)} problem(s):\n")
            for e in self.errors:
                print(f"  - {e}")
            return 1

        print(f"✅ Validation passed: {len(usernames)} member(s) registered.")
        return 0


if __name__ == "__main__":
    sys.exit(Validator().run())
