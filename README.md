# open-source-contributions

Tracking open source contributions for **UW–Madison Data Science Institute**
members and affiliates.

A live dashboard shows who's contributing, to which projects, and how activity
grows over time. Members register themselves with a one-line pull request; the
rest is automated.

➡️ **Live dashboard:** _enable GitHub Pages (Settings → Pages → Source: GitHub
Actions) and the site publishes to_ `https://<owner>.github.io/open-source-contributions/`

## How it works

```
data/members.yaml        ──┐
data/contributions.yaml  ──┤   scripts/build_data.py      docs/ (static site)
                           ├──▶  + GitHub Search API  ──▶  data.json  ──▶  GitHub Pages
GitHub public activity   ──┘
```

- **Hybrid data.** Members are listed manually; their merged GitHub PRs are
  fetched automatically. Non-GitHub work (talks, GitLab MRs, maintainer roles)
  can be recorded by hand.
- **PR workflow.** Contributors add themselves via pull request; a GitHub
  Action validates every change.
- **Auto-refresh.** A scheduled Action rebuilds the data nightly and redeploys
  the dashboard.

## Add yourself

See **[CONTRIBUTING.md](CONTRIBUTING.md)** — it's a two-minute pull request.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`data/members.yaml`](data/members.yaml) | The member/affiliate registry (edit this to join). |
| [`data/contributions.yaml`](data/contributions.yaml) | Manually recorded contributions the automation can't see. |
| [`scripts/validate.py`](scripts/validate.py) | Schema + integrity checks, run on every PR. |
| [`scripts/build_data.py`](scripts/build_data.py) | Fetches GitHub data and builds `docs/data.json`. |
| [`docs/`](docs/) | The static dashboard served by GitHub Pages. |
| [`.github/workflows/`](.github/workflows/) | Validation and build/deploy automation. |

## Run it locally

```bash
pip install -r scripts/requirements.txt

# Validate the registry
python scripts/validate.py

# Build the dashboard data (a token avoids GitHub rate limits)
export GITHUB_TOKEN=ghp_your_token
python scripts/build_data.py

# Preview the dashboard
python -m http.server -d docs 8000   # then open http://localhost:8000
```

No token handy? `OFFLINE=1 python scripts/build_data.py` builds from the manual
registry only, so you can preview the site without hitting the network.

## One-time setup for a new deployment

1. Push this repository to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Run the **Build & deploy dashboard** workflow once (Actions tab →
   _Run workflow_), or just merge a change to `main`.

## License

See [LICENSE](LICENSE).
