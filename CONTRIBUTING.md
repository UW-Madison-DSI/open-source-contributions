# Contributing

This repo tracks open source contributions by **UW–Madison Data Science
Institute** members and affiliates. Adding yourself takes about two minutes.

## Add yourself as a member

1. Open [`data/members.yaml`](data/members.yaml).
2. Append an entry to the `members:` list:

   ```yaml
     - name: Your Name
       github: your-github-username
       role: student          # faculty | staff | student | postdoc | affiliate | member
       affiliation: Your Lab or Dept   # optional, defaults to "DSI"
       joined: 2026-06         # optional, YYYY-MM
   ```

3. Open a pull request. A GitHub Action validates your entry automatically.
   Once a maintainer merges it, your **merged pull requests across all public
   GitHub repositories** are picked up automatically and appear on the
   dashboard within a day (or immediately if a maintainer re-runs the build).

That's it — you don't need to list individual GitHub PRs. The automation finds
them from your username.

## Add a non-GitHub contribution

Some work isn't a merged GitHub PR — a GitLab merge request, a conference talk,
a maintainer role, a tutorial. Record those in
[`data/contributions.yaml`](data/contributions.yaml):

```yaml
  - member: your-github-username     # must match your members.yaml entry
    project: Apache Arrow
    title: Talk — "Zero-copy data interchange"
    url: https://example.com/talk
    type: talk                       # pr | issue | review | docs | talk | maintainer | release | other
    date: 2026-05-20
    description: Optional one-liner.
```

## Validate locally (optional)

```bash
pip install -r scripts/requirements.txt
python scripts/validate.py
```

## How the data is built

- `scripts/validate.py` checks both YAML files (schema + referential integrity).
- `scripts/build_data.py` reads the registry, queries the GitHub Search API for
  each member's merged PRs, merges in the manual contributions, computes
  summary stats, and writes `docs/data.json`.
- The **Build & deploy** workflow runs this on every merge to `main`, nightly,
  and on demand, then publishes `docs/` to GitHub Pages.

To regenerate the dashboard data locally:

```bash
export GITHUB_TOKEN=ghp_your_personal_access_token   # avoids rate limits
python scripts/build_data.py
# then open docs/index.html (see README for a local server one-liner)
```

## Removing or deactivating an entry

To keep a historical record without counting someone in active stats, set
`active: false` on their member entry instead of deleting it.
