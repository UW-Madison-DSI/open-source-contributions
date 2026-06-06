"""Unit tests for the data builder's pure logic.

Run from the repo root:

    pip install -r scripts/requirements-dev.txt
    pytest

These cover the transformations that don't touch the network: URL parsing,
manual-contribution normalization, and the collaboration-graph construction.
"""
import sys
from pathlib import Path

# Allow `import build_data` when pytest is invoked from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_data import build_network, normalize_manual, repo_from_url


def test_repo_from_url():
    assert repo_from_url("https://api.github.com/repos/numpy/numpy") == "numpy/numpy"
    assert repo_from_url("https://api.github.com/repos/scikit-hep/pyhf") == "scikit-hep/pyhf"


def test_normalize_manual_defaults_and_dates():
    out = normalize_manual(
        [
            {
                "member": "alice",
                "project": "gitlab/thing",
                "title": "A talk",
                "url": "https://example.com/talk",
                "type": "talk",
                "date": "2025-03-04",
            }
        ]
    )
    assert len(out) == 1
    c = out[0]
    assert c["source"] == "manual"
    assert c["external"] is True
    assert c["date"] == "2025-03-04"
    assert c["type"] == "talk"


def test_normalize_manual_handles_date_objects():
    import datetime

    out = normalize_manual(
        [
            {
                "member": "bob",
                "project": "p",
                "title": "t",
                "url": "https://x/y",
                "date": datetime.date(2024, 1, 2),
            }
        ]
    )
    assert out[0]["date"] == "2024-01-02"
    assert out[0]["type"] == "other"  # default when unset


def test_normalize_manual_empty():
    assert normalize_manual([]) == []
    assert normalize_manual(None) == []


def _members():
    return [
        {"github": "Alice", "name": "Alice A"},
        {"github": "Bob", "name": "Bob B"},
        {"github": "Carol", "name": "Carol C"},
    ]


def _contribs():
    # Logins are lower-cased; member matching is case-insensitive.
    return [
        {"member": "alice", "project": "numpy/numpy"},
        {"member": "alice", "project": "numpy/numpy"},
        {"member": "bob", "project": "numpy/numpy"},
        {"member": "bob", "project": "scipy/scipy"},
        {"member": "carol", "project": "carol/solo"},
        {"member": "ghost", "project": "x/y"},  # not a registered member
    ]


def test_build_network_shared_flags_and_counts():
    net = build_network(_contribs(), _members())
    projects = {n["id"]: n for n in net["nodes"] if n["type"] == "project"}

    assert projects["p:numpy/numpy"]["members"] == 2
    assert projects["p:numpy/numpy"]["shared"] is True
    assert projects["p:numpy/numpy"]["contributions"] == 3
    assert projects["p:scipy/scipy"]["shared"] is False
    assert net["shared_projects"] == 1


def test_build_network_ignores_non_members():
    net = build_network(_contribs(), _members())
    assert not any("ghost" in n["id"] for n in net["nodes"])
    assert not any(n["id"] == "p:x/y" for n in net["nodes"])


def test_build_network_link_weight_is_per_member_count():
    net = build_network(_contribs(), _members())
    edge = next(
        l for l in net["links"] if l["source"] == "m:alice" and l["target"] == "p:numpy/numpy"
    )
    assert edge["weight"] == 2


def test_build_network_member_projection():
    net = build_network(_contribs(), _members())
    ml = net["member_links"]
    assert len(ml) == 1
    link = ml[0]
    assert {link["source"], link["target"]} == {"m:alice", "m:bob"}
    assert link["weight"] == 1
    assert link["projects"] == ["numpy/numpy"]


def test_build_network_member_degree():
    net = build_network(_contribs(), _members())
    members = {n["id"]: n for n in net["nodes"] if n["type"] == "member"}
    assert members["m:bob"]["degree"] == 2  # numpy + scipy
    assert members["m:carol"]["degree"] == 1


def test_build_network_empty():
    net = build_network([], _members())
    assert net["shared_projects"] == 0
    assert net["links"] == []
    assert net["member_links"] == []
    # Members still appear as nodes even with no contributions.
    assert all(n["type"] == "member" for n in net["nodes"])
    assert len(net["nodes"]) == 3
